"""Bounded two-stage model campaign: discovery, confirmation and sensitivities."""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import pyarrow.parquet as pq
import joblib
from threadpoolctl import threadpool_limits

from nemic.experiments.diurnal import origin_weights
from .modelling import META, fit_estimator, folds, masks, metrics, paired_bootstrap
from .selection import select
from .tracking import Ledger, atomic


def _schema(path):
    path=Path(path)
    return json.loads(path.with_suffix('.schema.json').read_text(encoding='utf-8'))


def _specs(names,schema):
    features=[c for c in names if c not in META]
    group=schema['groups'];network=[c for c in features if group.get(c)=='network']
    no_nos=[c for c in features if group.get(c)!='nos' and 'nos_' not in c]
    return {
        'network':network,
        'main':[c for c in no_nos if not c.startswith('ix__')],
        'interactions':no_nos,
        'endpoint':[c for c in no_nos if group.get(c) not in ('cross_region','weather_cross','nem_context')],
    }


def _resolve_indices(length,indices):
    resolved=[]
    for index in indices:
        value=index if index>=0 else length+index
        if not 0<=value<length:raise IndexError(f'Fold index {index} unavailable for {length} folds')
        if value not in resolved:resolved.append(value)
    return resolved


def _read_band(path,lo,hi,columns):
    return pd.read_parquet(path,columns=columns,filters=[('lead','>=',lo),('lead','<=',hi)])


def _ensure_cohort_table(ledger,connector,cohort):
    """Repair a missing provider cohort cache from the verified base table."""
    base=ledger.data/'features'/connector/'table.parquet'
    destination=ledger.data/'features'/connector/cohort/'table.parquet'
    schema_destination=destination.with_suffix('.schema.json')
    if destination.exists() and schema_destination.exists():return destination
    if not base.exists() or not base.with_suffix('.schema.json').exists():
        raise FileNotFoundError(f'Verified base feature table missing: {base}')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(destination.name+f'.{os.getpid()}.tmp')
    rows=0
    dataset=ds.dataset(base,format='parquet')
    try:
        with pq.ParquetWriter(temporary,dataset.schema,compression='zstd') as writer:
            for batch in dataset.scanner(filter=ds.field('source_cohort')==cohort,batch_size=8192).to_batches():
                writer.write_batch(batch);rows+=batch.num_rows
        if rows==0:raise ValueError(f'No {cohort} rows in verified base feature table')
        os.replace(temporary,destination)
    finally:
        if temporary.exists():temporary.unlink()
    schema=json.loads(base.with_suffix('.schema.json').read_text(encoding='utf-8'))
    atomic(schema_destination,json.dumps({**schema,'cohort':cohort},indent=2))
    ledger.record(f'features/{connector}/{cohort}','completed',f'Atomically materialized {rows} labelled rows',
                  [destination,schema_destination])
    return destination


def _discovery_cell(config,path,bounds,band,target):
    os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2')
    ledger=Ledger(config);profile=ledger.c['balanced_campaign'];path=Path(path);schema=_schema(path)
    names=pq.ParquetFile(path).schema_arrow.names;specs=_specs(names,schema)
    selected_specs={name:specs[name] for name in profile['recipes']}
    lo,hi=ledger.c['bands'][band]
    required={'origin','delivery','lead','connector','actual_'+target,'anchor_'+target}
    for columns in selected_specs.values():required.update(columns)
    table=_read_band(path,lo,hi,[c for c in names if c in required]).reset_index(drop=True)
    ms=masks(table,bounds)
    if any(ms[k].sum()<30 for k in ms):raise ValueError('Insufficient rows in a balanced discovery partition')
    tr,se=(ms[k] for k in ('train','select'));y=table['actual_'+target].to_numpy();anchor=table['anchor_'+target].to_numpy()
    correction=y-anchor;weights=origin_weights(table.loc[tr,'origin'])
    ident=f"train/{table.connector.iloc[0]}/{profile['version']}/discovery/{bounds[-2].date()}/{target}/band{band}"
    folder=ledger.data/ident;result_path=folder/'result.json'
    if ledger.valid(ident):return str(result_path)
    with threadpool_limits(limits=2),ledger.job(ident,acceptance='Balanced training-only discovery scores and frozen feature candidates') as (artifacts,checkpoint):
        master=selected_specs['interactions'];master_x=table[master]
        chosen_master,review=select(master_x.loc[tr].reset_index(drop=True),correction[tr],
                                    table.loc[tr,['origin','delivery']].reset_index(drop=True),schema)
        records=[];chosen_by_recipe={};models=0
        for recipe,columns in selected_specs.items():
            chosen=list(columns) if recipe=='network' else [c for c in chosen_master if c in columns]
            chosen=list(dict.fromkeys(chosen+['own_anchor']));chosen_by_recipe[recipe]=chosen
            x=table[[c for c in chosen if c!='own_anchor']].copy();x['own_anchor']=anchor
            for family,settings in (('ridge',profile['ridge_alphas']),('boost',profile['boost_num_leaves'])):
                for setting in settings:
                    model=fit_estimator(family,setting,x.loc[tr,chosen],correction[tr],weights)
                    prediction=anchor[se]+model.predict(x.loc[se,chosen])
                    mae=float(np.average(abs(y[se]-prediction),weights=origin_weights(table.loc[se,'origin'])))
                    records.append(dict(key=f'{recipe}/{family}/{setting}',recipe=recipe,family=family,
                                        setting=setting,mae=mae,features=len(chosen)))
                    models+=1;del model
            checkpoint(dict(stage='discovery',band=band,target=target,recipe=recipe,models=models))
        payload=dict(stage='discovery',profile=profile['version'],connector=str(table.connector.iloc[0]),target=target,
                     band=band,fold=str(bounds[-2].date()),selection=records,selected_columns=chosen_by_recipe,
                     feature_selection=review,rows={k:int(v.sum()) for k,v in ms.items()},source_table=str(path))
        folder.mkdir(parents=True,exist_ok=True);atomic(result_path,json.dumps(payload,indent=2));artifacts.append(result_path)
    return str(result_path)


def discovery(ledger,connector):
    """Run 24 bounded discovery cells for one connector with two workers."""
    profile=ledger.c['balanced_campaign'];path=ledger.data/'features'/connector/'pasa_coal/table.parquet'
    if not path.exists():raise FileNotFoundError(f'Prepared PASA/coal table missing: {path}')
    meta=pd.read_parquet(path,columns=['origin','delivery']);fs=list(folds(meta,ledger.c))
    indices=_resolve_indices(len(fs),profile['discovery_fold_indices'])
    tasks=[(fs[index],band,target) for index in indices for band in range(len(ledger.c['bands'])) for target in profile['targets']]
    started=time.monotonic();outputs=[];workers=min(2,int(profile['cell_workers']))
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        future_map={pool.submit(_discovery_cell,ledger.c,str(path),bounds,band,target):(bounds,band,target)
                    for bounds,band,target in tasks}
        for future in as_completed(future_map):outputs.append(future.result())
    manifest=ledger.data/'balanced'/connector/profile['version']/'discovery_manifest.json'
    atomic(manifest,json.dumps(dict(stage='discovery',connector=connector,profile=profile['version'],cells=len(outputs),
                                    workers=workers,elapsed_seconds=time.monotonic()-started,outputs=sorted(outputs)),indent=2))
    ledger.record(f"balanced/{connector}/{profile['version']}/discovery",'completed','Balanced discovery complete',[manifest])
    return manifest


def freeze_discovery(ledger,connector):
    """Freeze one recipe/model/schema per target and band using discovery only."""
    profile=ledger.c['balanced_campaign'];version=profile['version']
    root=ledger.data/'train'/connector/version/'discovery'
    results=[json.loads(path.read_text(encoding='utf-8')) for path in root.glob('*/*/band*/result.json')]
    expected=len(_resolve_indices(len(list(folds(pd.read_parquet(ledger.data/'features'/connector/'pasa_coal/table.parquet',columns=['origin','delivery']),ledger.c))),profile['discovery_fold_indices']))*len(ledger.c['bands'])*len(profile['targets'])
    if len(results)!=expected:raise RuntimeError(f'Discovery incomplete: {len(results)}/{expected} cells')
    frozen={}
    for target in profile['targets']:
        for band in range(len(ledger.c['bands'])):
            cells=[r for r in results if r['target']==target and r['band']==band]
            scores=pd.DataFrame([x for cell in cells for x in cell['selection']])
            ranked=scores.groupby(['key','recipe','family','setting'],as_index=False).mae.mean().sort_values(['mae','key'])
            winner=ranked.iloc[0].to_dict();network=ranked[ranked.recipe.eq('network')].iloc[0].to_dict()
            chosen_sets=[set(cell['selected_columns'][winner['recipe']])-{'own_anchor'} for cell in cells]
            stable=set.intersection(*chosen_sets) if chosen_sets else set()
            if not stable:stable=set.union(*chosen_sets)
            ordered=[c for c in cells[0]['selected_columns'][winner['recipe']] if c in stable]+['own_anchor']
            network_columns=cells[0]['selected_columns']['network']
            frozen[f'{target}/band{band}']=dict(target=target,band=band,winner=winner,network=network,
                                               columns=ordered,network_columns=network_columns,
                                               discovery_folds=[c['fold'] for c in cells])
    output=ledger.data/'balanced'/connector/version/'frozen.json';atomic(output,json.dumps(frozen,indent=2))
    ledger.record(f'balanced/{connector}/{version}/freeze','completed','Balanced discovery choices frozen',[output])
    return output


def _confirmation_cell(config,path,bounds,band,target,frozen):
    os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2')
    ledger=Ledger(config);profile=ledger.c['balanced_campaign'];path=Path(path);names=pq.ParquetFile(path).schema_arrow.names
    lo,hi=ledger.c['bands'][band];columns=frozen['columns'];network_columns=frozen['network_columns']
    required={'origin','delivery','lead','connector','actual_'+target,'anchor_'+target,
              'seasonal48_'+target,'seasonal336_'+target}|set(columns)|set(network_columns)
    table=_read_band(path,lo,hi,[c for c in names if c in required]).reset_index(drop=True);ms=masks(table,bounds)
    if any(ms[k].sum()<30 for k in ms):raise ValueError('Insufficient rows in balanced confirmation partition')
    tr,cal,te=(ms[k] for k in ('train','calibrate','evaluate'));y=table['actual_'+target].to_numpy();anchor=table['anchor_'+target].to_numpy()
    correction=y-anchor;weights=origin_weights(table.loc[tr,'origin']);name=str(table.connector.iloc[0])
    ident=f"train/{name}/{profile['version']}/confirmation/{bounds[-2].date()}/{target}/band{band}"
    folder=ledger.data/ident;result_path=folder/'result.json'
    if ledger.valid(ident):return str(result_path)
    with threadpool_limits(limits=2),ledger.job(ident,acceptance='Frozen balanced winner and matched network baseline evaluated') as (artifacts,checkpoint):
        wx=table[[c for c in columns if c!='own_anchor']].copy();wx['own_anchor']=anchor
        winner=frozen['winner'];model=fit_estimator(winner['family'],winner['setting'],wx.loc[tr,columns],correction[tr],weights)
        checkpoint(dict(stage='confirmation',model='winner'))
        residual=y[cal]-anchor[cal]-model.predict(wx.loc[cal,columns]);levels=[.025,.1,.5,.9,.975];adjust=np.quantile(residual,levels)
        point=anchor[te]+model.predict(wx.loc[te,columns])
        nx=table[[c for c in network_columns if c!='own_anchor']].copy();nx['own_anchor']=anchor
        network=frozen['network'];network_model=fit_estimator(network['family'],network['setting'],nx.loc[tr,network_columns],correction[tr],weights)
        baseline=anchor[te]+network_model.predict(nx.loc[te,network_columns]);checkpoint(dict(stage='confirmation',model='network'))
        predictions=table.loc[te,['origin','delivery','lead']].copy();predictions['actual']=y[te];predictions['point']=point
        predictions['network']=baseline;predictions['persistence']=anchor[te]
        for period in (48,336):predictions[f'seasonal{period}']=table.loc[te,f'seasonal{period}_{target}'].to_numpy()
        for q,value in zip(levels,adjust):predictions['q'+str(q)]=point+value
        folder.mkdir(parents=True,exist_ok=True);predpath=folder/'predictions.parquet';predictions.to_parquet(predpath,index=False)
        bundle=dict(model=model,columns=columns,adjustments=adjust,levels=levels,target=target,connector=name,
                    feature_version='fundamentals-v3.0-balanced-v1',methodology=ledger.method_hash,
                    training_cutoff=str(bounds[1]),calibration_end=str(bounds[3]),status='research')
        modelpath=folder/'model.joblib';network_path=folder/'network.joblib';joblib.dump(bundle,modelpath);joblib.dump(network_model,network_path)
        loaded=joblib.load(modelpath);np.testing.assert_allclose(loaded['model'].predict(wx.loc[te,columns].iloc[:10]),model.predict(wx.loc[te,columns].iloc[:10]))
        score=metrics(y[te],point);network_score=metrics(y[te],baseline)
        result=dict(stage='confirmation',profile=profile['version'],connector=name,target=target,band=band,
                    fold=str(bounds[-2].date()),winner=winner,score=score,network_score=network_score,
                    persistence_score=metrics(y[te],anchor[te]),skill=1-score['mae']/network_score['mae'] if network_score['mae'] else None,
                    uncertainty=[paired_bootstrap(y[te],point,baseline,table.loc[te,'origin'].to_numpy(),days) for days in (7,14)],
                    promotion=False,risk_gate='pending balanced risk assessment',reload_parity=True,columns=columns)
        atomic(result_path,json.dumps(result,indent=2));artifacts.extend([modelpath,network_path,predpath,result_path])
    return str(result_path)


def confirmation(ledger,connector):
    profile=ledger.c['balanced_campaign'];version=profile['version'];path=ledger.data/'features'/connector/'pasa_coal/table.parquet'
    frozen_path=ledger.data/'balanced'/connector/version/'frozen.json'
    if not frozen_path.exists():freeze_discovery(ledger,connector)
    frozen=json.loads(frozen_path.read_text(encoding='utf-8'));meta=pd.read_parquet(path,columns=['origin','delivery']);fs=list(folds(meta,ledger.c))
    tasks=[]
    for bounds in fs:
        for band in range(len(ledger.c['bands'])):
            for target in profile['targets']:tasks.append((bounds,band,target,frozen[f'{target}/band{band}']))
    started=time.monotonic();outputs=[];workers=min(2,int(profile['cell_workers']))
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        future_map={pool.submit(_confirmation_cell,ledger.c,str(path),bounds,band,target,choice):(bounds,band,target)
                    for bounds,band,target,choice in tasks}
        for future in as_completed(future_map):outputs.append(future.result())
    manifest=ledger.data/'balanced'/connector/version/'confirmation_manifest.json'
    atomic(manifest,json.dumps(dict(stage='confirmation',connector=connector,profile=version,cells=len(outputs),workers=workers,
                                    elapsed_seconds=time.monotonic()-started,outputs=sorted(outputs)),indent=2))
    ledger.record(f'balanced/{connector}/{version}/confirmation','completed','Balanced confirmation complete',[manifest])
    return manifest


def _sensitivity_cell(config,path,bounds,band,target,frozen):
    """Provider sensitivity with frozen recipe/model family and training-only reselection."""
    os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2')
    ledger=Ledger(config);profile=ledger.c['balanced_campaign'];path=Path(path);schema=_schema(path)
    names=pq.ParquetFile(path).schema_arrow.names;specs=_specs(names,schema);recipe=frozen['winner']['recipe']
    lo,hi=ledger.c['bands'][band];recipe_columns=specs[recipe];network_columns=specs['network']+['own_anchor']
    required={'origin','delivery','lead','connector','actual_'+target,'anchor_'+target}|set(recipe_columns)|set(network_columns)
    table=_read_band(path,lo,hi,[c for c in names if c in required]).reset_index(drop=True);ms=masks(table,bounds)
    if any(ms[k].sum()<30 for k in ms):raise ValueError('Insufficient rows in ECMWF sensitivity partition')
    tr,cal,te=(ms[k] for k in ('train','calibrate','evaluate'));y=table['actual_'+target].to_numpy();anchor=table['anchor_'+target].to_numpy();correction=y-anchor
    weights=origin_weights(table.loc[tr,'origin']);name=str(table.connector.iloc[0])
    ident=f"train/{name}/{profile['version']}/ecmwf_sensitivity/{bounds[-2].date()}/{target}/band{band}"
    folder=ledger.data/ident;result_path=folder/'result.json'
    if ledger.valid(ident):return str(result_path)
    with threadpool_limits(limits=2),ledger.job(ident,acceptance='ECMWF sensitivity kept separate from primary confirmation') as (artifacts,checkpoint):
        if recipe=='network':columns=network_columns;review=None
        else:
            chosen,review=select(table.loc[tr,recipe_columns].reset_index(drop=True),correction[tr],
                                 table.loc[tr,['origin','delivery']].reset_index(drop=True),schema)
            columns=list(dict.fromkeys(chosen+['own_anchor']))
        checkpoint(dict(stage='ecmwf_sensitivity',step='feature_selection',features=len(columns)))
        x=table[[c for c in columns if c!='own_anchor']].copy();x['own_anchor']=anchor;winner=frozen['winner']
        model=fit_estimator(winner['family'],winner['setting'],x.loc[tr,columns],correction[tr],weights);checkpoint(dict(stage='ecmwf_sensitivity',model='winner'))
        residual=y[cal]-anchor[cal]-model.predict(x.loc[cal,columns]);levels=[.025,.1,.5,.9,.975];adjust=np.quantile(residual,levels)
        point=anchor[te]+model.predict(x.loc[te,columns])
        nx=table[[c for c in network_columns if c!='own_anchor']].copy();nx['own_anchor']=anchor;network=frozen['network']
        network_model=fit_estimator(network['family'],network['setting'],nx.loc[tr,network_columns],correction[tr],weights)
        baseline=anchor[te]+network_model.predict(nx.loc[te,network_columns]);pred=table.loc[te,['origin','delivery','lead']].copy()
        pred['actual']=y[te];pred['point']=point;pred['network']=baseline;pred['persistence']=anchor[te]
        predpath=folder/'predictions.parquet';folder.mkdir(parents=True,exist_ok=True);pred.to_parquet(predpath,index=False)
        modelpath=folder/'model.joblib';joblib.dump(dict(model=model,columns=columns,adjustments=adjust,levels=levels,
            target=target,connector=name,status='research',feature_version='fundamentals-v3.0-balanced-v1'),modelpath)
        result=dict(stage='ecmwf_sensitivity',profile=profile['version'],connector=name,target=target,band=band,
                    fold=str(bounds[-2].date()),winner=winner,score=metrics(y[te],point),network_score=metrics(y[te],baseline),
                    columns=columns,feature_selection=review,promotion=False)
        atomic(result_path,json.dumps(result,indent=2));artifacts.extend([modelpath,predpath,result_path])
    return str(result_path)


def sensitivity(ledger,connector):
    profile=ledger.c['balanced_campaign'];version=profile['version'];path=ledger.data/'features'/connector/'ecmwf_exploratory/table.parquet'
    path=_ensure_cohort_table(ledger,connector,'ecmwf_exploratory')
    frozen_path=ledger.data/'balanced'/connector/version/'frozen.json'
    if not frozen_path.exists():raise RuntimeError('Confirmation choices have not been frozen')
    frozen=json.loads(frozen_path.read_text(encoding='utf-8'));meta=pd.read_parquet(path,columns=['origin','delivery']);fs=list(folds(meta,ledger.c))
    indices=_resolve_indices(len(fs),profile['sensitivity_fold_indices']);tasks=[]
    for index in indices:
        for band in range(len(ledger.c['bands'])):
            for target in profile['targets']:tasks.append((fs[index],band,target,frozen[f'{target}/band{band}']))
    started=time.monotonic();outputs=[];workers=min(1,int(profile['cell_workers']))
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        future_map={pool.submit(_sensitivity_cell,ledger.c,str(path),bounds,band,target,choice):(bounds,band,target)
                    for bounds,band,target,choice in tasks}
        for future in as_completed(future_map):outputs.append(future.result())
    manifest=ledger.data/'balanced'/connector/version/'sensitivity_manifest.json'
    atomic(manifest,json.dumps(dict(stage='ecmwf_sensitivity',connector=connector,cells=len(outputs),workers=workers,
                                    elapsed_seconds=time.monotonic()-started,outputs=sorted(outputs)),indent=2))
    ledger.record(f'balanced/{connector}/{version}/sensitivity','completed','Balanced ECMWF sensitivity complete',[manifest])
    return manifest


def score_horizons(ledger,connector):
    """Score only source-supported literal horizons; 336h remains unavailable."""
    profile=ledger.c['balanced_campaign'];version=profile['version'];root=ledger.data/'train'/connector/version/'confirmation'
    rows=[]
    mapping={48:24,96:48,336:168}
    for path in root.glob('*/*/band*/predictions.parquet'):
        frame=pd.read_parquet(path)
        result=json.loads((path.parent/'result.json').read_text(encoding='utf-8'))
        for lead,hours in mapping.items():
            part=frame[frame.lead.eq(lead)]
            if part.empty:continue
            rows.append(dict(connector=connector,target=result['target'],fold=result['fold'],hours=hours,lead=lead,
                             model=metrics(part.actual,part.point),network=metrics(part.actual,part.network),available=True))
    output=ledger.data/'balanced'/connector/version/'horizon_scores.json'
    payload=dict(profile=version,requested_hours=profile['final_horizon_hours'],scores=rows,
                 unavailable=[dict(hours=336,lead=672,available=False,
                    reason='No retained ST PASA or PD PASA coherent row reaches 336 hours; maximums are 182.84h and 39.42h respectively.')])
    atomic(output,json.dumps(payload,indent=2));ledger.record(f'balanced/{connector}/{version}/horizon_scores','completed','Supported horizon scores cached',[output])
    return output


def run(ledger,connector,stage='discovery'):
    order=ledger.c['balanced_campaign']['connector_order']
    if connector not in order:raise ValueError(connector)
    if connector!='VNI':
        prior=ledger.data/'balanced/VNI'/ledger.c['balanced_campaign']['version']/'complete.json'
        if not prior.exists():raise RuntimeError('VNI balanced campaign must complete before QNI begins')
    if stage=='discovery':return discovery(ledger,connector)
    if stage=='confirmation':return confirmation(ledger,connector)
    if stage=='sensitivity':return sensitivity(ledger,connector)
    if stage=='score':return score_horizons(ledger,connector)
    raise ValueError(f'Balanced stage not implemented: {stage}')
