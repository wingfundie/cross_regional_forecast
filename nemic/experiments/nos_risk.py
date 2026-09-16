"""Historical NOS risk ablations on source-common rows and a joint alarm budget."""
import json
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss
from threadpoolctl import threadpool_limits

from .core import Store,load_config,fingerprint,digest
from .data import connector_data,base_frame,design
from .diurnal import mature_masks
from .diurnal_runner import CONFIG,inner_windows
from .diurnal_risk import RiskModel,ProbabilityCalibrator,joint_threshold,score_events
from .events import detect,incidents,window_label,probability_score
from .nos_runner import BLOCKS,add_interactions
from .runner import save_model
from .validation import folds


def _calibrate(raw,y,mask):
    logits=np.log(raw/(1-raw)).reshape(-1,1)
    model=ProbabilityCalibrator().fit(logits[mask],y[mask])
    return model,model.predict_proba(logits)[:,1]


def run_nos_risk(config_path=CONFIG):
    c=load_config(config_path);store=Store(c)
    coverage=json.loads((store.root/'nos/coverage_audit.json').read_text())
    audit=json.loads((store.root/'nos/mapping_audit.json').read_text())
    feasibility_path=store.root/'nos/nos_feasibility.json'
    if not coverage.get('historical_gate') or not audit.get('historical_model_gate'):
        store.json(store.root/'nos/risk_status.json',{'status':'prospective-only','reason':'historical NOS gate failed'})
        return
    if not feasibility_path.exists():raise ValueError('Pre-model NOS feasibility/power audit has not run')
    eligible={r['fold']:r for r in coverage['folds'] if r['eligible']}
    exposure=pd.read_parquet(store.root/'nos/exposure.parquet')
    exposure=exposure.loc[exposure.lead.eq(4)].drop_duplicates('origin').set_index('origin')
    d=connector_data(c,c['connectors'][0]);d['base']=base_frame(d);idx=d['y'].index
    base=design(d,np.arange(len(idx)),np.repeat(4,len(idx)),'full').astype(float)
    joined=exposure.reindex(idx)
    known=joined.nos_report_generated.notna()
    known &= joined.nos_report_generated.add(pd.Timedelta(minutes=30)).le(idx)
    known &= (idx-joined.nos_report_generated-pd.Timedelta(minutes=30))<=pd.Timedelta(minutes=90)
    recipes={'O0':[]}
    for count in range(1,5):recipes['+'.join(list(BLOCKS)[:count])]=list(BLOCKS)[:count]
    recipes['+'.join(BLOCKS)+'+OX']=list(BLOCKS)
    with threadpool_limits(limits=2):
        for fold in folds(c):
            if fold.name not in eligible:continue
            ident=f'nos_risk/{fold.name}';folder=store.root/ident
            fp=fingerprint([fold.dict(),digest(store.root/'nos/exposure.parquet'),digest(__file__)])
            if store.valid(ident,fp):continue
            masks=mature_masks(idx,idx+pd.Timedelta(minutes=120),fold)
            meta=pd.DataFrame({'origin':idx,'delivery':idx+pd.Timedelta(minutes=120)})
            catalogues={};labels={}
            for direction in ('export','import'):
                detector,thresholds=detect(d['raw'][direction],fold.train_start,fold.train_end)
                labels[direction]=window_label(detector.onset,detector.valid,idx)
                catalogues[direction]=incidents(detector)
                store.json(folder/f'{direction}_detector.json',thresholds)
            valid=np.isfinite(labels['export'])&np.isfinite(labels['import'])&np.asarray(known)
            history_start=pd.Timestamp(eligible[fold.name]['partitions']['train']['fitted_start'])
            masks={k:(v&valid&(idx>=history_start if k=='train' else True)) for k,v in masks.items()}
            train,select,calibrate,alert,evaluate=[masks[k] for k in ('train','select','calibrate','alert','evaluate')]
            if min(x.sum() for x in (train,select,calibrate,alert,evaluate))<100:
                raise ValueError(f'NOS risk support below row floor: {fold.name}')
            windows=inner_windows(meta,train);models={};probabilities={};search=[];scores=[]
            for recipe,blocks in recipes.items():
                x=base.copy()
                for block in blocks:
                    for col in BLOCKS[block]:x[col]=joined[col].to_numpy()
                if blocks:x['nos_source_age_minutes']=((idx.to_series(index=idx)-joined.nos_report_generated).dt.total_seconds()/60).to_numpy()
                if recipe.endswith('+OX'):add_interactions(x)
                models[recipe]={};probabilities[recipe]={}
                for family in ('logistic','boost'):
                    models[recipe][family]={};probabilities[recipe][family]={}
                    for direction in ('export','import'):
                        y=labels[direction];positive=int(np.sum(y[windows[0][0]]))
                        leaf_cap=max(2,min(63,int(np.sqrt(max(positive,1)))))
                        settings=[.001,.01,.1,1.,10.] if family=='logistic' else sorted(set([2**j for j in range(1,7) if 2**j<=leaf_cap]+[leaf_cap]))
                        trials=[]
                        for setting in settings:
                            losses=[]
                            for tr,va in windows:
                                m=RiskModel(family,strength=setting if family=='logistic' else .1,
                                    leaves=int(setting) if family=='boost' else 7).fit(x.loc[tr],y[tr])
                                losses.append(float(log_loss(y[va],m.predict(x.loc[va]),labels=[0,1])))
                            trials.append({'setting':setting,'log_loss':float(np.mean(losses)),'blocks':losses})
                        chosen=min(trials,key=lambda r:r['log_loss'])['setting']
                        m=RiskModel(family,strength=chosen if family=='logistic' else .1,
                            leaves=int(chosen) if family=='boost' else 7).fit(x.loc[train],y[train])
                        raw=m.predict(x);cal,p=_calibrate(raw,y,calibrate)
                        models[recipe][family][direction]=(m,cal,list(x.columns))
                        probabilities[recipe][family][direction]=(raw,p)
                        search.append({'recipe':recipe,'family':family,'direction':direction,'trials':trials,
                            'chosen':chosen,'data_shape':m.profile,'parameters':m.model.get_params()})
                for family in ('logistic','boost'):
                    provisional=joint_threshold([(idx[select],probabilities[recipe][family][dr][0][select],catalogues[dr]) for dr in ('export','import')])
                    selection=[score_events(idx[select],probabilities[recipe][family][dr][0][select],t,catalogues[dr]) for dr,t in zip(('export','import'),provisional)]
                    thresholds=joint_threshold([(idx[alert],probabilities[recipe][family][dr][1][alert],catalogues[dr]) for dr in ('export','import')])
                    for direction,threshold in zip(('export','import'),thresholds):
                        p=probabilities[recipe][family][direction][1]
                        scores.append({'recipe':recipe,'family':family,'direction':direction,'threshold':threshold,
                            'selection_tp':sum(v['tp'] for v in selection),'selection_fp':sum(v['fp'] for v in selection),
                            'selection_incidents':sum(v['incidents'] for v in selection),
                            'probability':probability_score(labels[direction][evaluate],p[evaluate]),
                            'events':score_events(idx[evaluate],p[evaluate],threshold,catalogues[direction])})
                        store.parquet(folder/f'{recipe.replace("+","_")}_{family}_{direction}_predictions.parquet',
                            pd.DataFrame({'origin':idx[evaluate],'actual_window':labels[direction][evaluate],
                                          'probability':p[evaluate],'threshold':threshold}))
            candidates={(r['recipe'],r['family']) for r in scores}
            winner=max(candidates,key=lambda k:(sum(r['selection_tp'] for r in scores if (r['recipe'],r['family'])==k),
                                                -sum(r['selection_fp'] for r in scores if (r['recipe'],r['family'])==k)))
            save_model(store,folder/'models.joblib',{'models':models,'winner':winner,'operationally_eligible':False,
                'information_track':'retrospective NOS source vintages and historical mapping'})
            result={'fold':fold.dict(),'winner':winner,'scores':scores,'search':search,
                'common_source_fraction':float(np.mean(known[masks['evaluate']])),
                'claim':'Historical source-common development comparison; separate prospective confirmation required'}
            store.json(folder/'result.json',result);store.complete(ident,fp,folder/'result.json')
            print('NOS RISK',fold.name,winner,flush=True)


if __name__=='__main__':run_nos_risk()
