"""Matched four-way VNI fundamentals/NOS contraction-risk assessment."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from threadpoolctl import threadpool_limits

from nemic.experiments.core import load_config
from nemic.experiments.data import connector_data
from nemic.experiments.diurnal_risk import ConstantClassifier, ProbabilityCalibrator, joint_threshold, score_events
from nemic.experiments.events import detect, incidents, probability_score, window_label
from .modelling import folds, masks
from .tracking import atomic


NOS_COLUMNS=['nos_count','nos_sets','nos_primary','nos_secondary','nos_starts','nos_ends','nos_overlap',
    'nos_upper_sets','nos_lower_sets','nos_thermal_sets','nos_stability_sets','nos_voltage_sets',
    'nos_unknown_mechanism','nos_changes24','nos_start_shift_minutes','nos_end_shift_minutes',
    'nos_status_changes24','nos_revision_age_minutes','nos_booking_age_hours','nos_overdue',
    'nos_uncertain_status','nos_recall_day','nos_recall_night']


def _fit(x,y):
    if np.unique(y).size<2:return make_pipeline(SimpleImputer(keep_empty_features=True),ConstantClassifier(float(np.mean(y)),x.shape[1])).fit(x,y)
    return make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),
        lgb.LGBMClassifier(objective='binary',num_leaves=15,n_estimators=150,min_child_samples=50,
            learning_rate=.04,n_jobs=2,verbosity=-1,random_state=741,deterministic=True,force_col_wise=True)).fit(x,y)


def _predict(model,x):
    return np.clip(model.predict_proba(x)[:,1],1e-6,1-1e-6)


def _eligible_times(origins,catalogue,minimum=30,maximum=120):
    origins=pd.DatetimeIndex(origins);times=pd.DatetimeIndex(catalogue.time)
    if not len(origins) or not len(times):return []
    oi=origins.asi8;low=times.asi8-pd.Timedelta(minutes=maximum).value;high=times.asi8-pd.Timedelta(minutes=minimum).value
    keep=np.searchsorted(oi,high,side='right')>np.searchsorted(oi,low,side='left')
    return [str(t) for t in times[keep]]


def _interactions(frame):
    out=frame.copy()
    for left in ('nos_count','nos_overlap','nos_upper_sets','nos_lower_sets'):
        for right in ('upper_room','lower_room','upper_setter_age','lower_setter_age','hour_sin','hour_cos'):
            if left in out and right in out:out[f'{left}:{right}']=out[left]*out[right]
    return out


def _paired_recall(rows,recipe,direction,repeats=5000):
    observations=[]
    for row in rows:
        events={x['direction']:x for x in row['scores']['network']}[direction]
        candidate={x['direction']:x for x in row['scores'][recipe]}[direction]
        universe=events['eligible_times'];base=set(events['events']['matched_times']);test=set(candidate['events']['matched_times'])
        observations.extend([(int(t in test),int(t in base)) for t in universe])
    if not observations:return {'incidents':0,'delta_recall':None,'ci95':None}
    values=np.asarray(observations,float);rng=np.random.default_rng(741)
    samples=[]
    for _ in range(repeats):
        picked=values[rng.integers(0,len(values),len(values))];samples.append(float((picked[:,0]-picked[:,1]).mean()))
    delta=float((values[:,0]-values[:,1]).mean())
    return {'incidents':len(values),'delta_recall':delta,'ci95':np.quantile(samples,[.025,.975]).tolist(),
            'method':'paired incident bootstrap'}


def run_risk(ledger,connector='VNI'):
    if connector!='VNI':raise ValueError('Balanced risk closure must complete VNI before QNI')
    profile=ledger.c['balanced_campaign'];version=profile['version']
    feature_path=ledger.data/'features/VNI/pasa_coal/table.parquet'
    schema=json.loads(feature_path.with_suffix('.schema.json').read_text(encoding='utf-8'))
    frozen=json.loads((ledger.data/'balanced/VNI'/version/'frozen.json').read_text(encoding='utf-8'))
    network=[c for c,g in schema['groups'].items() if g=='network']
    directional={d:list(dict.fromkeys(network+[c for c in frozen[f'{d}_tight/band0']['columns'] if c!='own_anchor']))
                 for d in ('export','import')}
    required=set(network+directional['export']+directional['import'])|{'origin','delivery','lead'}
    import pyarrow.parquet as pq
    names=set(pq.ParquetFile(feature_path).schema_arrow.names)
    table=pd.read_parquet(feature_path,columns=[c for c in required if c in names],filters=[('lead','=',4)]).sort_values('origin').reset_index(drop=True)
    exposure_root=Path('data/forecast_experiments/vni_diurnal_nos_v2/nos')
    coverage=json.loads((exposure_root/'coverage_audit.json').read_text(encoding='utf-8'))
    mapping=json.loads((exposure_root/'mapping_audit.json').read_text(encoding='utf-8'))
    feasibility=json.loads((exposure_root/'nos_feasibility.json').read_text(encoding='utf-8'))
    if not coverage.get('historical_gate') or not mapping.get('historical_model_gate'):
        raise RuntimeError('Historical NOS coverage/mapping gate failed')
    exposure=pd.read_parquet(exposure_root/'exposure.parquet')
    exposure=exposure[exposure.lead.eq(4)].drop_duplicates('origin').set_index('origin')
    joined=table.join(exposure[NOS_COLUMNS+['nos_report_generated']],on='origin')
    age=joined.origin-joined.nos_report_generated-pd.Timedelta(minutes=30)
    known=joined.nos_report_generated.add(pd.Timedelta(minutes=30)).le(joined.origin)&age.le(pd.Timedelta(minutes=90))&age.ge(pd.Timedelta(0))
    old=load_config('configs/experiments/vni_diurnal_nos_v2.json');raw=connector_data(old,old['connectors'][0])['raw']
    fs=list(folds(table,ledger.c));results=[]
    with threadpool_limits(limits=2):
        for bounds in fs:
            fold=str(bounds[-2].date());ms=masks(table,bounds)
            coverage_by_part={k:float(known[v].mean()) if v.any() else 0. for k,v in ms.items()}
            if min(coverage_by_part.values())<.8:continue
            catalogues={};labels={}
            for direction in ('export','import'):
                detector,thresholds=detect(raw[direction],bounds[0],bounds[1])
                labels[direction]=window_label(detector.onset,detector.valid,table.origin)
                catalogues[direction]=incidents(detector)
            valid=known.to_numpy()&np.isfinite(labels['export'])&np.isfinite(labels['import'])
            use={k:v&valid for k,v in ms.items()}
            if min(v.sum() for v in use.values())<100:continue
            ident=f'assessment/VNI/{version}/risk/{fold}';folder=ledger.data/ident;result_path=folder/'result.json'
            if ledger.valid(ident):results.append(json.loads(result_path.read_text()));continue
            with ledger.job(ident,acceptance='Matched calibrated NOS/fundamentals contraction-risk fold') as (artifacts,checkpoint):
                scores={};models={};predictions=[]
                recipe_names=('network','fundamentals','nos','both')
                probabilities={name:{} for name in recipe_names};models={name:{} for name in recipe_names}
                for recipe in recipe_names:
                    for direction in ('export','import'):
                        columns=list(network)
                        if recipe in ('fundamentals','both'):columns=list(directional[direction])
                        x=joined[columns].replace([np.inf,-np.inf],np.nan).copy()
                        if recipe in ('nos','both'):
                            for col in NOS_COLUMNS:x[col]=joined[col]
                        if recipe=='both':x=_interactions(x)
                        y=labels[direction].astype(int);model=_fit(x.loc[use['train']],y[use['train']]);rawp=_predict(model,x)
                        logits=np.log(rawp/(1-rawp)).reshape(-1,1);cal=ProbabilityCalibrator().fit(logits[use['calibrate']],y[use['calibrate']])
                        probabilities[recipe][direction]=cal.predict_proba(logits)[:,1]
                        models[recipe][direction]=(model,cal,list(x.columns));checkpoint({'fold':fold,'recipe':recipe,'direction':direction})
                for recipe in recipe_names:
                    thresholds=joint_threshold([(table.origin[use['alert']],probabilities[recipe][d][use['alert']],catalogues[d]) for d in ('export','import')],ledger.c['acceptance']['false_alerts_per_day'])
                    scores[recipe]=[]
                    for direction,threshold in zip(('export','import'),thresholds):
                        p=probabilities[recipe][direction];event=score_events(table.origin[use['evaluate']],p[use['evaluate']],threshold,catalogues[direction])
                        item={'direction':direction,'threshold':threshold,'events':event,
                              'eligible_times':_eligible_times(table.origin[use['evaluate']],catalogues[direction]),
                              'probability':probability_score(labels[direction][use['evaluate']],p[use['evaluate']])}
                        scores[recipe].append(item)
                        predictions.append(pd.DataFrame({'origin':table.origin[use['evaluate']],'fold':fold,'recipe':recipe,
                            'direction':direction,'actual_window':labels[direction][use['evaluate']],
                            'probability':p[use['evaluate']],'threshold':threshold}))
                folder.mkdir(parents=True,exist_ok=True);pred_path=folder/'predictions.parquet';pd.concat(predictions).to_parquet(pred_path,index=False)
                model_path=folder/'models.joblib';joblib.dump({'models':models,'status':'research','operationally_eligible':False},model_path)
                result={'fold':fold,'bounds':[str(x) for x in bounds],'coverage':coverage_by_part,'scores':scores,
                        'information_track':'retrospective NOS generation vintages and reconstructed equation mapping','promotion':False}
                atomic(result_path,json.dumps(result,indent=2));artifacts.extend([pred_path,model_path,result_path]);results.append(result)
    if not results:raise RuntimeError('No balanced folds passed the matched NOS coverage floor')
    aggregate={}
    for recipe in ('network','fundamentals','nos','both'):
        directions={}
        total_fp=0;exposure_days=0
        for direction in ('export','import'):
            items=[next(x for x in r['scores'][recipe] if x['direction']==direction) for r in results]
            incidents_n=sum(x['events']['incidents'] for x in items);tp=sum(x['events']['tp'] for x in items);fp=sum(x['events']['fp'] for x in items)
            total_fp+=fp
            directions[direction]={'incidents':incidents_n,'tp':tp,'fp':fp,'fn':sum(x['events']['fn'] for x in items),
                'recall':tp/incidents_n if incidents_n else None,'precision':tp/(tp+fp) if tp+fp else None,
                'brier':float(np.average([x['probability']['brier'] for x in items],weights=[x['probability']['n'] for x in items])),
                'average_precision':float(np.average([x['probability']['average_precision'] or 0 for x in items],weights=[x['probability']['n'] for x in items]))}
        exposure_days=sum(next(x for x in r['scores'][recipe] if x['direction']=='export')['events']['exposure_days'] for r in results)
        aggregate[recipe]={'directions':directions,'joint_false_alarms_per_day':total_fp/exposure_days,'exposure_days':exposure_days,
                           'recall_difference':{d:_paired_recall(results,recipe,d) for d in ('export','import')}}
    both=aggregate['both'];gate={'minimum_incidents':all(both['directions'][d]['incidents']>=ledger.c['acceptance']['min_incidents'] for d in ('export','import')),
        'joint_false_alert_budget':both['joint_false_alarms_per_day']<=ledger.c['acceptance']['false_alerts_per_day'],
        'recall_noninferiority':all(both['recall_difference'][d]['ci95'][0]>=-ledger.c['acceptance']['recall_margin_pp']/100 for d in ('export','import'))}
    summary={'connector':'VNI','profile':version,'folds':len(results),'aggregate':aggregate,'gates':gate,'historical_statistical_gate':all(gate.values()),
        'operational_provenance_gate':False,'promotion':False,'limitations':mapping['limitations'],
        'power':{'risk_floor':feasibility['risk_floor'],'pre_evaluation_design_incidents':feasibility['pre_evaluation_design_incidents'],
                 'minimum_detectable_gain_80pct':feasibility['minimum_detectable_gain_80pct']}}
    output=ledger.data/'balanced/VNI'/version/'risk_summary.json';atomic(output,json.dumps(summary,indent=2))
    ledger.record(f'assessment/VNI/{version}/risk','completed','Historical NOS/risk gates measured; operational provenance remains blocked',[output])
    return output
