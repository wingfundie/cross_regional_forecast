"""Bounded connector refinements after calendar and NOS recipe selection."""
import json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from .core import Store,digest,fingerprint,load_config
from .data import connector_data,base_frame
from .diurnal import CapacityReference,metrics,origin_weights
from .diurnal_runner import CONFIG,fit_candidate,frame
from .models import forecast_pressure
from .nos_runner import BLOCKS,add_interactions
from .runner import save_model
from .validation import folds


def _nos_features(base,joined,recipe,known):
    x=base.copy();parts=[] if recipe=='O0' else recipe.split('+')
    for block in [p for p in parts if p in BLOCKS]:
        for col in BLOCKS[block]:x[col]=joined[col].to_numpy()
    if recipe!='O0':
        x['nos_source_age_minutes']=(joined.origin-joined.nos_report_generated).dt.total_seconds()/60
        x['nos_unknown_source']=(~known).astype(float)
    if 'OX' in parts:add_interactions(x)
    return x


def run_refinements(config_path=CONFIG):
    c=load_config(config_path);store=Store(c)
    exposure_path=store.root/'nos/exposure.parquet';exposure=pd.read_parquet(exposure_path).drop(columns='nos_mapping_track')
    d=connector_data(c,c['connectors'][0]);d['base']=base_frame(d);idx=d['y'].index
    with threadpool_limits(limits=2):
        for result_path in sorted((store.root/'nos_models').glob('*/*/result.json')):
            result=json.loads(result_path.read_text());fold=next(f for f in folds(c) if f.name==result['fold']['name'])
            target=result['target'];folder=store.root/'refinements'/fold.name/target
            ident=str(folder.relative_to(store.root));fp=fingerprint([digest(result_path),digest(exposure_path),digest(__file__)])
            if store.valid(ident,fp):continue
            base,meta,masks=frame(c,c['connectors'][0],fold,0,target)
            joined=meta[['origin','lead']].merge(exposure,on=['origin','lead'],how='left',validate='many_to_one')
            known=joined.nos_report_generated.notna()
            known &= joined.nos_report_generated.add(pd.Timedelta(minutes=30)).le(joined.origin)
            known &= (joined.origin-joined.nos_report_generated-pd.Timedelta(minutes=30))<=pd.Timedelta(minutes=90)
            history_start=pd.Timestamp(result['history_start'])
            train=masks['train']&meta.origin.ge(history_start)&known;select=masks['select']&known;evaluate=masks['evaluate']&known
            winner=result['winner'];family,recipe=winner.split('_',1);settings=result['search'][winner]['chosen']
            x=_nos_features(base,joined,recipe,known)
            forecast={lead:forecast_pressure(d,fold,int(lead)) for lead in sorted(meta.lead.unique())}
            origin_position=idx.get_indexer(meta.origin)
            pressure=x.copy()
            pressure['predicted_pressure_upper']=[forecast[int(lead)][position,0] for lead,position in zip(meta.lead,origin_position)]
            pressure['predicted_pressure_lower']=[forecast[int(lead)][position,1] for lead,position in zip(meta.lead,origin_position)]
            latest=meta.loc[train,'origin'].max();variants={
                'expanding':(x,train),
                'lead_pressure':(pressure,train),
                'trailing_365d':(x,train&meta.origin.ge(latest-pd.Timedelta(days=365))),
                'trailing_180d':(x,train&meta.origin.ge(latest-pd.Timedelta(days=180)))}
            models={};predictions={};selection={};scores=[]
            dates=meta.loc[evaluate,'origin'].dt.normalize().unique()
            chosen_dates=dates[np.linspace(0,len(dates)-1,min(5,len(dates)),dtype=int)]
            explain_sample=evaluate&meta.origin.dt.normalize().isin(chosen_dates)
            for name,(features,fit_mask) in variants.items():
                if fit_mask.sum()<500:continue
                model,reference=fit_candidate(family,settings,features,meta,np.asarray(fit_mask),'mae')
                p=meta.anchor.to_numpy()+model.predict(features);models[name]={'model':model,'columns':list(features.columns)};predictions[name]=p
                selection[name]=float(np.average(abs(meta.actual.to_numpy()[select]-p[select]),weights=origin_weights(meta.loc[select,'origin'])))
                ref=reference.predict(meta.anchor)
                scores.append({'model':name,'selection_mae':selection[name],
                    **metrics(meta.actual.to_numpy()[evaluate],p[evaluate],ref[evaluate],origin_weights(meta.loc[evaluate,'origin'])),
                    'train_pairs':int(fit_mask.sum()),'training_days':int(meta.loc[fit_mask,'origin'].dt.normalize().nunique())})
                training_positions=np.flatnonzero(fit_mask)
                background_positions=training_positions[np.linspace(0,len(training_positions)-1,min(32,len(training_positions)),dtype=int)]
                explanation=pd.concat([features.iloc[background_positions].assign(_split='background',_actual=np.nan),
                    features.loc[explain_sample].assign(_split='sample',_actual=meta.loc[explain_sample,'actual'].to_numpy())],ignore_index=True)
                store.parquet(folder/f'{name}_explain_features.parquet',explanation)
            selected=min(selection,key=selection.get)
            evaluated=meta.loc[evaluate].copy()
            for name,p in predictions.items():evaluated[name]=p[evaluate]
            store.parquet(folder/'predictions.parquet',evaluated)
            save_model(store,folder/'models.joblib',{'models':models,'winner':selected,'base_nos_policy':winner,
                'operationally_eligible':False})
            payload={'fold':fold.dict(),'target':target,'base_nos_policy':winner,'winner':selected,'selection':selection,
                'scores':scores,'parameters':settings,
                'cross_connector_partial_pooling':{
                    'status':'not executed in single-connector campaign',
                    'reason':'A paired, jointly fitted VNI–QNI design is required; separate completed campaigns do not constitute partial pooling.'},
                'claim':'Post-selection bounded refinements; gains are not attributed to diurnal or NOS main effects'}
            store.json(folder/'result.json',payload);store.complete(ident,fp,folder/'result.json')
            print('REFINEMENT',fold.name,target,selected,flush=True)


if __name__=='__main__':run_refinements()
