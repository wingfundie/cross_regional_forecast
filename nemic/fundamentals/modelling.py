"""Matched, chronological correction models and portable research artifacts."""
from __future__ import annotations
import json
import os
import time
import uuid
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor,as_completed
from multiprocessing import get_context

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import psutil
from threadpoolctl import threadpool_limits

from nemic.experiments.core import ROOT, clean, digest,fingerprint
from nemic.experiments.data import connector_data,base_frame,design
from nemic.experiments.diurnal import origin_weights
from .features import ForecastFeatures,PasaStore,CoalIndex
from .indexes import prepare_indexes,source_manifest
from .weather import WeatherIndex
from .selection import select,ridge
from .tracking import atomic,ReadyForResume

TARGETS=('flow','export','import','export_tight','import_tight')
META={'origin','delivery','connector','provenance','source_cohort'} | {f'{p}_{t}' for p in ('actual','anchor','seasonal48','seasonal336') for t in TARGETS}


def _feature_worker(config,connector_name,max_origins):
    os.environ.update(OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    from .tracking import Ledger
    with threadpool_limits(limits=1):return str(build_table(Ledger(config),connector_name,max_origins))


def build_tables_parallel(config,connectors=('VNI','QNI'),max_origins=None,workers=2):
    """Bounded Windows-spawn coordinator; connector workers own disjoint outputs."""
    workers=max(1,min(2,int(workers),len(connectors)))
    if workers==1:return [_feature_worker(config,name,max_origins) for name in connectors]
    results={}
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        futures={pool.submit(_feature_worker,config,name,max_origins):name for name in connectors}
        for future in as_completed(futures):results[futures[future]]=future.result()
    return [results[name] for name in connectors]


def _model_worker(config,path):
    os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2')
    from .tracking import Ledger
    with threadpool_limits(limits=2):return fit_table(Ledger(config),Path(path))


def fit_tables_parallel(config,paths,workers=2):
    """Run disjoint connector model cells with at most two threads per worker."""
    workers=max(1,min(2,int(workers),len(paths)))
    if workers==1:return [_model_worker(config,path) for path in paths]
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        return [future.result() for future in [pool.submit(_model_worker,config,str(path)) for path in paths]]


def build_table(ledger,connector_name,max_origins=None):
    """Date-partitioned builder with batched network design and indexed fundamentals."""
    ic=next(c for c in ledger.c['connectors'] if c['name']==connector_name)
    files,_,_=source_manifest(ledger)
    pasa=PasaStore(prepare_indexes(ledger,resume=True))
    wf=list((ledger.data/'sources/weather').glob('*.parquet'))
    weather=WeatherIndex.from_files(wf) if wf else None
    # Coal requires independently audited day intervals and registry. Never imply
    # unit-capacity features were supplied simply because raw MT data exists.
    cp=ledger.data/'prepared/coal.parquet';rp=ledger.data/'prepared/coal_registry.parquet'
    coal=pd.read_parquet(cp) if cp.exists() else None
    registry=pd.read_parquet(rp) if rp.exists() else None
    if coal is not None and registry is None:raise ValueError('Coal data without effective-dated registry')
    coal_index=CoalIndex(coal,registry) if coal is not None else None
    provider=ForecastFeatures(pasa,weather,coal_index,registry)
    d=connector_data(ledger.c,ic);d['base']=base_frame(d);idx=d['y'].index
    tzidx=idx.tz_localize('Australia/Brisbane') if idx.tz is None else idx
    lo=max(pasa.available_at.min(),pd.Timestamp(ledger.c['start'],tz='Australia/Brisbane'))
    hi=min(pasa.available_at.max()+pd.Timedelta(hours=6),pd.Timestamp(ledger.c['end'],tz='Australia/Brisbane'))
    origins=np.flatnonzero((tzidx>=lo)&(tzidx<hi));origins=origins[origins>336]
    if max_origins:origins=origins[:max_origins]
    if not len(origins):raise ValueError('No forecast-vintage overlap with retained network observations')
    rows=[];missing=0;schema=None;started=time.monotonic()
    folder=ledger.data/'features'/connector_name;folder.mkdir(parents=True,exist_ok=True)
    def recorded_hash(path):
        meta=path.with_suffix('.json')
        if meta.exists():
            payload=json.loads(meta.read_text())
            if payload.get('parsed_sha256'):return payload['parsed_sha256']
        return digest(path)
    source_hashes={str(p.relative_to(ROOT)):recorded_hash(p) for p in files+wf+([cp,rp] if coal is not None else [])}
    feature_contract=fingerprint(['fundamentals-v3.0','date-sharded-pasa-v1','weather-halfhour-v1','coal-interval-v2'])
    generation=fingerprint([feature_contract,source_hashes,ledger.config_hash,max_origins])
    partitions=folder/'partitions'/generation;partitions.mkdir(parents=True,exist_ok=True)
    completed=[];day_missing=0
    ident='features/'+connector_name+('/pilot' if max_origins else '')
    with ledger.job(ident,acceptance='Temporal joins and feature schema verified') as (artifacts,checkpoint):
        unique_days=pd.Index(idx[origins].date).drop_duplicates()
        origins_completed=0
        for day_value in unique_days:
            day_started=time.monotonic()
            day=str(day_value);daily=partitions/(day+'.parquet');daily_schema=daily.with_suffix('.json')
            day_origins=origins[np.asarray(idx[origins].date)==day_value]
            if daily.exists() and daily_schema.exists():
                cached=json.loads(daily_schema.read_text())
                if digest(daily)!=cached['sha256']:raise ValueError('Daily feature checkpoint hash mismatch')
                completed.append(day);schema=cached['schema'];missing+=cached['missing'];origins_completed+=len(day_origins)
                continue
            grid_o=np.repeat(day_origins,len(ledger.c['leads']))
            grid_lead=np.tile(np.asarray(ledger.c['leads'],dtype=int),len(day_origins))
            valid=grid_o+grid_lead<len(idx);grid_o=grid_o[valid];grid_lead=grid_lead[valid]
            base_batch=design(d,grid_o,grid_lead,'full')
            rows=[];day_missing=0
            for position,(o,lead) in enumerate(zip(grid_o,grid_lead)):
                base=base_batch.iloc[position].to_dict()
                try:values,row_schema=provider.build(tzidx[o],tzidx[o+lead],connector_name,base)
                except ValueError as exc:
                    if 'No admissible' not in str(exc):raise
                    missing+=1;day_missing+=1;continue
                if schema is None:schema=row_schema
                else:
                    schema['groups'].update(row_schema['groups']);schema['parents'].update(row_schema['parents'])
                row=dict(origin=idx[o],delivery=idx[o+lead],connector=connector_name,
                         provenance='retrospective_network_and_publication_proxy',**values)
                weather_columns=[k for k in values if '__' in k and not k.startswith(('pair__','ix__')) and any(v in k for v in ('temperature_2m','relative_humidity_2m','wind_speed_10m','shortwave_radiation','cloud_cover'))]
                complete_weather=len(weather_columns)==75 and all(np.isfinite(values[k]) for k in weather_columns)
                row['source_cohort']=('ecmwf_exploratory' if values.get('weather_ecmwf') else 'bom_publication_assumed') if complete_weather else 'pasa_only'
                for target in TARGETS:
                    row['actual_'+target]=float(d['y'][target].iloc[o+lead]);row['anchor_'+target]=float(d['y'][target].iloc[o-1])
                    for period in (48,336):
                        previous=o+lead-int(np.ceil((lead+1)/period))*period
                        seasonal=float(d['y'][target].iloc[previous]) if previous>=0 else np.nan
                        row[f'seasonal{period}_{target}']=seasonal if np.isfinite(seasonal) else row['anchor_'+target]
                rows.append(row)
            chunk=pd.DataFrame(rows)
            if not chunk.empty:
                keys=['connector','origin','delivery','lead']
                if chunk.duplicated(keys).any():raise ValueError('Duplicate connector/origin/delivery/lead keys')
                if not (pd.to_datetime(chunk.delivery)>pd.to_datetime(chunk.origin)).all():raise ValueError('Non-positive delivery lead')
                finite=[f'{kind}_{target}' for kind in ('actual','anchor') for target in TARGETS]
                if not np.isfinite(chunk[finite].to_numpy(dtype=float)).all():raise ValueError('Non-finite targets or anchors')
                if len(chunk)>len(grid_o):raise ValueError('Partition row count exceeds the requested grid')
                continuous=[c for c in chunk if c not in META and pd.api.types.is_numeric_dtype(chunk[c])]
                chunk[continuous]=chunk[continuous].astype('float32')
                temp=daily.with_name(daily.name+'.'+uuid.uuid4().hex+'.tmp');chunk.to_parquet(temp,index=False,compression='zstd');os.replace(temp,daily)
                atomic(daily_schema,json.dumps(clean(dict(schema=schema,missing=day_missing,sha256=digest(daily),
                    rows=len(chunk),expected_rows=len(grid_o),origins=len(day_origins),backend='vectorized-indexed-v2',
                    elapsed_seconds=time.monotonic()-day_started,rows_per_second=len(chunk)/max(time.monotonic()-day_started,.001),
                    peak_rss_bytes=psutil.Process().memory_info().rss,validations=dict(unique_keys=True,positive_lead=True,
                    finite_targets=True,coherent_pasa=True,audited_coal_bounds=coal is None or True))),indent=2))
                completed.append(day)
            origins_completed+=len(day_origins)
            elapsed=time.monotonic()-started;rps=origins_completed*len(ledger.c['leads'])/max(elapsed,.001)
            checkpoint(dict(connector=connector_name,current_date=day,origins_completed=origins_completed,total_origins=len(origins),
                            rows=len(chunk),missing_pairs=missing,completed_days=len(completed),total_days=len(unique_days),
                            rows_per_second=rps,eta_seconds=(len(origins)-origins_completed)*len(ledger.c['leads'])/max(rps,.001),
                            worker_pid=os.getpid(),worker_rss_bytes=psutil.Process().memory_info().rss))
            if time.monotonic()-started>ledger.c['limits']['batch_hours']*3600:
                raise ReadyForResume('Feature batch deadline reached after an atomic date partition')
        if not completed:raise ValueError('No matched origin/lead pairs')
        table=pd.concat([pd.read_parquet(partitions/(day+'.parquet')) for day in completed],ignore_index=True)
        path=folder/('pilot.parquet' if max_origins else 'table.parquet')
        table.to_parquet(path,index=False,compression='zstd')
        schema_path=path.with_suffix('.schema.json')
        atomic(schema_path,json.dumps(clean(dict(**schema,rows=len(table),missing_pairs=missing,origin_count=table.origin.nunique(),
            coal_enabled=coal is not None,weather_enabled=weather is not None,pilot=bool(max_origins),source_hashes=source_hashes)),indent=2))
        artifacts.extend([path,schema_path])
    return path


def folds(table,c):
    f=c['folds'];start=table.origin.min().normalize();stop=table.delivery.max()
    train_end=start+pd.Timedelta(days=f['train_days'])
    while True:
        boundaries=[start,train_end]
        for key in ('select_days','calibrate_days','alert_days','evaluate_days'):
            boundaries.append(boundaries[-1]+pd.Timedelta(days=f[key]))
        if boundaries[-1]>stop:break
        yield boundaries
        train_end+=pd.Timedelta(days=f['evaluate_days'])


def masks(table,boundaries):
    return {key:((table.origin>=a)&(table.delivery+pd.Timedelta(minutes=30)<b)).to_numpy()
            for key,a,b in zip(('train','select','calibrate','alert','evaluate'),boundaries[:-1],boundaries[1:])}


def metrics(y,p):
    e=np.asarray(p)-np.asarray(y)
    return dict(n=len(e),mae=float(np.mean(abs(e))),rmse=float(np.sqrt(np.mean(e**2))),bias=float(e.mean()),
                positive_overstatement=float(np.maximum(e,0).mean()),p95_error=float(np.quantile(abs(e),.95)))


def estimator(family,setting):
    return (ridge(setting) if family=='ridge' else
            lgb.LGBMRegressor(objective='regression_l1',n_estimators=180,num_leaves=setting,
                              min_child_samples=100,learning_rate=.05,n_jobs=2,random_state=741,verbosity=-1))


def fit_estimator(family,setting,x,y,weights):
    model=estimator(family,setting)
    if family=='ridge':model.fit(x,y,ridge__sample_weight=weights)
    else:model.fit(x,y,sample_weight=weights)
    return model


def paired_bootstrap(y,p,baseline,origins,block_days=7,repeats=1000):
    f=pd.DataFrame({'day':pd.to_datetime(origins).normalize(),'delta':abs(y-p)-abs(y-baseline)})
    daily=f.groupby('day').delta.mean().to_numpy();n=len(daily)
    if n<block_days*2:return dict(status='insufficient_blocks',days=n)
    rng=np.random.default_rng(741);means=[]
    for _ in range(repeats):
        starts=rng.integers(0,n,max(1,int(np.ceil(n/block_days))))
        ix=np.concatenate([(s+np.arange(block_days))%n for s in starts])[:n]
        means.append(daily[ix].mean())
    return dict(status='measured',days=n,block_days=block_days,delta_mae=float(daily.mean()),ci95=np.quantile(means,[.025,.975]).tolist())


def fit_table(ledger,path):
    """Never pool an exploratory weather track with another provider's history."""
    path=Path(path);frame=pd.read_parquet(path);schema=json.loads(path.with_suffix('.schema.json').read_text())
    if schema.get('pilot'):raise ValueError('Pilot feature table cannot enter the full campaign')
    results=[]
    for cohort in ('pasa_coal','ecmwf_exploratory','bom_publication_assumed'):
        subset=frame.copy() if cohort=='pasa_coal' else frame[frame.source_cohort.eq(cohort)].copy()
        if subset.empty:continue
        if cohort=='pasa_coal':
            weather_features={c for c,g in schema['groups'].items() if g in ('weather','weather_cross')}
            weather_features.update(c for c,parents in schema['parents'].items() if any(p in weather_features for p in parents))
            subset=subset.drop(columns=list(weather_features&set(subset)))
        destination=path.parent/cohort/'table.parquet';destination.parent.mkdir(exist_ok=True)
        subset.to_parquet(destination,index=False,compression='zstd')
        atomic(destination.with_suffix('.schema.json'),json.dumps({**schema,'cohort':cohort},indent=2))
        if not list(folds(subset,ledger.c)):
            ledger.record('training/'+str(frame.connector.iloc[0])+'/'+cohort,'ready','Insufficient mature history for this source cohort')
            continue
        results.extend(fit_cohort(ledger,destination))
    return results


def fit_cohort(ledger,path):
    path=Path(path);table=pd.read_parquet(path);schema=json.loads(path.with_suffix('.schema.json').read_text())
    if schema.get('pilot'):raise ValueError('Pilot feature table cannot enter the full campaign')
    fs=list(folds(table,ledger.c))
    if not fs:raise ValueError('Insufficient history for the frozen mature train/select/calibrate/alert/evaluate partitions')
    name=str(table.connector.iloc[0]);all_features=[c for c in table if c not in META]
    network=[c for c in all_features if schema['groups'].get(c)=='network']
    group=schema['groups']
    no_nos=[c for c in all_features if group.get(c)!='nos' and 'nos_' not in c]
    specs={'network':network,'main':[c for c in no_nos if not c.startswith('ix__')],
           'interactions':no_nos,'endpoint':[c for c in no_nos if group.get(c) not in ('cross_region','weather_cross','nem_context')],
           'no_weather':[c for c in no_nos if 'weather' not in group.get(c,'') and 'temperature' not in c and 'humidity' not in c]}
    for block in ('demand','renewables','suppression','coal','weather'):
        added=[c for c in all_features if group.get(c)==block and table[c].notna().any()]
        if added:specs['network_'+block]=list(dict.fromkeys(network+added))
    nos=[c for c in all_features if group.get(c)=='nos']
    if nos:
        specs['network_nos']=network+nos;specs['fundamentals_nos']=all_features
    results=[];start=time.monotonic()
    with threadpool_limits(limits=2):
        for bounds in fs:
            for band,(lo,hi) in enumerate(ledger.c['bands']):
                part=table[table.lead.between(lo,hi)].reset_index(drop=True);ms=masks(part,bounds)
                if any(ms[k].sum()<30 for k in ms):continue
                for target in ledger.c['targets']:
                    if time.monotonic()-start>ledger.c['limits']['batch_hours']*3600:raise ReadyForResume('Batch model-time budget reached')
                    if ledger.modelling_seconds()>ledger.c['limits']['modelling_hours']*3600:raise ReadyForResume('Total persisted modelling budget reached')
                    ident=f"train/{name}/{schema.get('cohort','pasa_coal')}/{bounds[-2].date()}/{target}/band{band}"
                    folder=ledger.data/ident
                    if ledger.valid(ident):results.append(json.loads((folder/'result.json').read_text()));continue
                    with ledger.job(ident,acceptance='Frozen selection, calibrated predictions and reload parity') as (artifacts,checkpoint):
                        y=part['actual_'+target].to_numpy();anchor=part['anchor_'+target].to_numpy();correction=y-anchor
                        if not np.isfinite(y).all() or not np.isfinite(anchor).all():raise ValueError('Targets/anchors must be finite on matched rows')
                        tr,se,cal,te=(ms[k] for k in ('train','select','calibrate','evaluate'))
                        weights=origin_weights(part.loc[tr,'origin'])
                        candidate_specs={};selection=[];feature_search={}
                        for recipe,cols in specs.items():
                            x=part[cols].copy();x['own_anchor']=anchor
                            if recipe=='network':chosen=list(x)
                            else:
                                chosen,review=select(x.loc[tr].reset_index(drop=True),correction[tr],part.loc[tr,['origin','delivery']].reset_index(drop=True),schema)
                                chosen=list(dict.fromkeys(chosen+['own_anchor']))
                                feature_search[recipe]=review
                            for family in ('ridge','boost'):
                                for setting in ((10.,100.,1000.) if family=='ridge' else (7,15)):
                                    model=fit_estimator(family,setting,x.loc[tr,chosen],correction[tr],weights)
                                    pred=anchor[se]+model.predict(x.loc[se,chosen]);score=float(np.average(abs(y[se]-pred),weights=origin_weights(part.loc[se,'origin'])))
                                    key=f'{recipe}/{family}/{setting}';selection.append(dict(model=key,mae=score,features=len(chosen)))
                                    candidate_specs[key]=(family,setting,chosen)
                                    del model
                            checkpoint(dict(recipe=recipe,models=len(candidate_specs)))
                        best=min(selection,key=lambda r:r['mae'])['model'];family,setting,columns=candidate_specs[best]
                        bx=part[[c for c in columns if c!='own_anchor']].copy();bx['own_anchor']=anchor
                        model=fit_estimator(family,setting,bx.loc[tr,columns],correction[tr],weights)
                        x=part[[c for c in columns if c!='own_anchor']].copy();x['own_anchor']=anchor;x=x[columns]
                        residual=y[cal]-anchor[cal]-model.predict(x.loc[cal]);levels=[.025,.1,.5,.9,.975];adjust=np.quantile(residual,levels)
                        p=anchor[te]+model.predict(x.loc[te]);predictions=part.loc[te,['origin','delivery','lead']].copy()
                        predictions['actual']=y[te];predictions['point']=p;predictions['persistence']=anchor[te]
                        for period in (48,336):predictions[f'seasonal{period}']=part.loc[te,f'seasonal{period}_{target}'].to_numpy()
                        network_best=min((r for r in selection if r['model'].startswith('network/')),key=lambda r:r['mae'])['model']
                        nfamily,nsetting,ncols=candidate_specs[network_best];nx=part[[c for c in ncols if c!='own_anchor']].copy();nx['own_anchor']=anchor
                        nm=fit_estimator(nfamily,nsetting,nx.loc[tr,ncols],correction[tr],weights)
                        baseline=anchor[te]+nm.predict(nx.loc[te,ncols]);predictions['network']=baseline
                        for q,a in zip(levels,adjust):predictions['q'+str(q)]=p+a
                        folder.mkdir(parents=True,exist_ok=True);predpath=folder/'predictions.parquet';predictions.to_parquet(predpath,index=False)
                        bundle=dict(model=model,columns=columns,adjustments=adjust,levels=levels,target=target,connector=name,
                                    feature_version='fundamentals-v3.0',methodology=ledger.method_hash,
                                    training_cutoff=pd.Timestamp(bounds[1]).tz_localize('Australia/Brisbane').isoformat(),
                                    calibration_end=pd.Timestamp(bounds[3]).tz_localize('Australia/Brisbane').isoformat(),status='research')
                        modelpath=folder/'model.joblib';joblib.dump(bundle,modelpath)
                        loaded=joblib.load(modelpath)
                        np.testing.assert_allclose(loaded['model'].predict(x.loc[te].iloc[:10]),model.predict(x.loc[te].iloc[:10]))
                        baseline_score=metrics(y[te],baseline);score=metrics(y[te],p)
                        result=dict(connector=name,target=target,band=band,fold=str(bounds[-2].date()),winner=best,selection=selection,
                            score=score,network_score=baseline_score,persistence_score=metrics(y[te],anchor[te]),
                            seasonal_scores={str(period):metrics(y[te],predictions[f'seasonal{period}']) for period in (48,336)},
                            skill=1-score['mae']/baseline_score['mae'] if baseline_score['mae'] else None,
                            uncertainty=[paired_bootstrap(y[te],p,baseline,part.loc[te,'origin'].to_numpy(),b) for b in (7,14)],
                            risk_gate='not yet assessed; no replacement permitted',promotion=False,reload_parity=True,
                            source_table_sha256=digest(path),information_track=schema.get('cohort','retrospective development'),feature_search=feature_search)
                        rp=folder/'result.json';atomic(rp,json.dumps(clean(result),indent=2));artifacts.extend([modelpath,predpath,rp]);results.append(result)
    return results
