"""Matched-history NOS ablations, admitted only after the pre-model audit."""
import json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .core import Store,load_config,fingerprint,digest
from .validation import folds
from .diurnal_runner import CONFIG,frame,tune,fit_candidate
from .diurnal import origin_weights,metrics,CapacityReference
from .runner import save_model

BLOCKS={
    'O1':['nos_count','nos_sets','nos_primary','nos_secondary'],
    'O2':['nos_overlap','nos_starts','nos_ends'],
    'O3':['nos_upper_sets','nos_lower_sets','nos_thermal_sets','nos_stability_sets','nos_voltage_sets','nos_unknown_mechanism'],
    'O4':['nos_changes24','nos_start_shift_minutes','nos_end_shift_minutes','nos_status_changes24','nos_revision_age_minutes',
          'nos_booking_age_hours','nos_overdue','nos_uncertain_status','nos_recall_day','nos_recall_night']}


def add_interactions(x):
    """Restricted, physically reviewable outage × operating-state interactions."""
    outage=['nos_count','nos_overlap','nos_upper_sets','nos_lower_sets']
    state=['upper_room','lower_room','upper_gen_tightening','lower_gen_tightening','hour_sin','hour_cos']
    for left in outage:
        for right in state:
            if left in x and right in x:x[f'{left}:{right}']=x[left]*x[right]
    return x


def run_nos(config_path=CONFIG):
    c=load_config(config_path);store=Store(c)
    coverage=json.loads((store.root/'nos/coverage_audit.json').read_text())
    impact_path=store.root/'nos/impact/full_development/status.json'
    feasibility=store.root/'nos/nos_feasibility.json'
    if not coverage['historical_gate']:
        store.json(store.root/'nos/model_status.json',{'status':'prospective-only','reason':'historical coverage/fold gate failed'})
        return
    if not impact_path.exists():raise ValueError('Pre-model matched-impact analysis has not run')
    if not feasibility.exists():raise ValueError('Pre-model NOS feasibility/power audit has not run')
    mapping_audit=json.loads((store.root/'nos/mapping_audit.json').read_text())
    if not mapping_audit.get('historical_model_gate'):
        raise ValueError('NOS mapping/temporal gate has not passed')
    exposure=pd.read_parquet(store.root/'nos/exposure.parquet').drop(columns='nos_mapping_track')
    primary={f['fold']:f for f in coverage['folds'] if f['eligible']}
    with threadpool_limits(limits=2):
        for fold in folds(c):
            if fold.name not in primary:continue
            history_start=pd.Timestamp(primary[fold.name]['partitions']['train']['fitted_start'])
            for target in ('export_tight','import_tight'):
                ident=f'nos_models/{fold.name}/{target}';folder=store.root/ident
                source=[store.root/'nos/exposure.parquet',impact_path]
                fp=fingerprint([fold.dict(),target,[(str(p),digest(p)) for p in source],digest(__file__)])
                if store.valid(ident,fp):continue
                base,meta,masks=frame(c,c['connectors'][0],fold,0,target)
                joined=meta[['origin','lead']].merge(exposure,on=['origin','lead'],how='left',validate='many_to_one')
                known=joined.nos_report_generated.notna() & ((joined.origin-joined.nos_report_generated-pd.Timedelta(minutes=30))<=pd.Timedelta(minutes=90))
                known &= joined.nos_report_generated.add(pd.Timedelta(minutes=30)).le(joined.origin)
                tr=masks['train'] & meta.origin.ge(history_start) & known
                va=masks['select'] & known;te=masks['evaluate'];common=te & known
                if min(tr.sum(),va.sum(),common.sum())<100:raise ValueError('Matched NOS support below row floor')
                primary_result=json.loads((store.root/'diurnal'/fold.name/'band0'/target/'result.json').read_text())
                family=min(('T2','T3'),key=lambda f:primary_result['selection'][f+'_mae'])
                models={};predictions={};records=[];parameters={}
                fallback=None
                recipe_specs=[('O0',0,False)]+[('+'.join(list(BLOCKS)[:count]),count,False) for count in range(1,5)]
                recipe_specs.append(('+'.join(BLOCKS)+'+OX',4,True))
                for calendar in ('T0',family):
                    for recipe,count,interact in recipe_specs:
                        name=calendar+'_'+recipe
                        x=base.copy()
                        for block in list(BLOCKS)[:count]:
                            for col in BLOCKS[block]:x[col]=joined[col].to_numpy()
                        if count:
                            x['nos_source_age_minutes']=(joined.origin-joined.nos_report_generated).dt.total_seconds()/60
                            x['nos_unknown_source']=(~known).astype(float)
                        if interact:add_interactions(x)
                        model,ref,search=tune(calendar,x,meta,np.asarray(tr),'mae',folder/name,store)
                        p=meta.anchor.to_numpy()+model.predict(x)
                        if count==0:
                            no_outage=p
                            if fallback is None:fallback=p.copy()
                        else:p=np.where(known,p,no_outage)
                        models[name]={'model':model,'columns':list(x.columns)};predictions[name]=p;parameters[name]=search
                        selection=float(np.average(abs(meta.actual.to_numpy()[va]-p[va]),weights=origin_weights(meta.loc[va,'origin'])))
                        reference=ref.predict(meta.anchor)
                        records.append({'model':name,'selection_mae':selection,
                            'full_population':metrics(meta.actual.to_numpy()[te],p[te],reference[te],origin_weights(meta.loc[te,'origin'])),
                            'common_source':metrics(meta.actual.to_numpy()[common],p[common],reference[common],origin_weights(meta.loc[common,'origin'])),
                            'known_evaluation_fraction':float(known[te].mean()),'train_pairs':int(tr.sum())})
                        print('NOS FIT',fold.name,target,name,round(selection,2),flush=True)
                # Nonlinear challenger receives the same selection-chosen NOS block and
                # the fold-primary tree settings; it gets no extra evaluation-informed search.
                scheduled=min((r for r in records if not r['model'].endswith('_O0')),
                              key=lambda r:r['selection_mae'])['model'].split('_',1)[1]
                for recipe in ('O0',scheduled):
                    name='T6_'+recipe;x=base.copy();parts=[] if recipe=='O0' else recipe.split('+')
                    for block in [p for p in parts if p in BLOCKS]:
                        for col in BLOCKS[block]:x[col]=joined[col].to_numpy()
                    if recipe!='O0':
                        x['nos_source_age_minutes']=(joined.origin-joined.nos_report_generated).dt.total_seconds()/60
                        x['nos_unknown_source']=(~known).astype(float)
                    if 'OX' in parts:add_interactions(x)
                    source_search=primary_result['search']['T6_mae']
                    model,ref=fit_candidate('T6',source_search['chosen'],x,meta,np.asarray(tr),'mae')
                    p=meta.anchor.to_numpy()+model.predict(x)
                    models[name]={'model':model,'columns':list(x.columns)};predictions[name]=p
                    parameters[name]={'family':'T6','objective':'mae','chosen':source_search['chosen'],
                        'actual_parameters':model.model.get_params(),'history':[],
                        'stop':'tree configuration frozen from fold-primary chronological HPO',
                        'frozen_from':str((store.root/'diurnal'/fold.name/'band0'/target/'result.json').relative_to(store.root))}
                    selection=float(np.average(abs(meta.actual.to_numpy()[va]-p[va]),weights=origin_weights(meta.loc[va,'origin'])))
                    reference=ref.predict(meta.anchor)
                    records.append({'model':name,'selection_mae':selection,
                        'full_population':metrics(meta.actual.to_numpy()[te],p[te],reference[te],origin_weights(meta.loc[te,'origin'])),
                        'common_source':metrics(meta.actual.to_numpy()[common],p[common],reference[common],origin_weights(meta.loc[common,'origin'])),
                        'known_evaluation_fraction':float(known[te].mean()),'train_pairs':int(tr.sum())})
                    print('NOS FIT',fold.name,target,name,round(selection,2),flush=True)
                winner=min(records,key=lambda r:r['selection_mae'])['model']
                evaluated=meta.loc[te].copy();evaluated['nos_known']=np.asarray(known)[te]
                for name,p in predictions.items():evaluated[name]=p[te]
                store.parquet(folder/'predictions.parquet',evaluated)
                save_model(store,folder/'models.joblib',{'models':models,'winner':winner,'operationally_eligible':False,
                    'information_track':'original NOS generation vintages + retrospective equation mapping/context'})
                store.json(folder/'result.json',{'fold':fold.dict(),'target':target,'winner':winner,'scores':records,
                    'search':parameters,'history_start':history_start,'risk_status':'separate risk/power assessment required',
                    'claim':'Matched-history development comparison; null NOS results conditional on absent forward-generation vintages'})
                store.complete(ident,fp,folder/'result.json')


if __name__=='__main__':run_nos()
