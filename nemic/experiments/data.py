"""Inventory and compact feature blocks. Retrospective evidence is never relabelled live."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from .core import ROOT, Store, source_item, fingerprint, code_manifest

STATE=['upper_room','lower_room','upper_switch_gap','lower_switch_gap','upper_candidate_count','lower_candidate_count']
PRESSURE=['upper_gen_tightening','upper_gen_relief','lower_gen_tightening','lower_gen_relief','upper_pressure_change','lower_pressure_change','upper_available_relief','lower_available_relief']
QUALITY=['partial_candidate_fraction','pressure_complete_fraction','envelope_inconsistent']
RECIPES={
    'base':['history'], 'state':['history','state','quality'],
    'pressure':['history','pressure','quality'], 'full':['history','state','pressure','quality'],
    'forecast':['history','state','pressure','quality','forecast_pressure'],
    'context':['history','state','pressure','quality','forecast_pressure','context'],
    'oracle':['history','state','pressure','quality','context','future_actuals']}


def inventory(c,save=True):
    paths={ROOT/'data/processed/targets.parquet':'targets',ROOT/'data/processed/ic_5min.parquet':'observed five-minute targets',ROOT/'data/processed/drivers.parquet':'retrospective regional drivers'}
    capabilities=[]
    for ic in c['connectors']:
        study=ROOT/'data'/ic['study'];atlas=ROOT/'data'/ic['atlas']
        features=sorted((study/'months').glob('*/constraint_features_30min.parquet'))
        for p in features:paths[p]='retrospective compact topology'
        for p in sorted((study/'months').glob('*/feature_audit.json')):paths[p]='feature audit'
        for p in sorted((study/'months').glob('*/unit_pressure_5min.parquet')):paths[p]='retained generator pressure (not full generator dispatch)'
        for name in ['summary.json','event_catalogue.parquet','event_attribution.parquet','event_equations.parquet','generator_contributions.parquet','prices_5min.parquet','coal_context.parquet','weather_context.parquet','unit_dispatch.parquet','constraint_states.parquet','event_bundles.json']:
            if (atlas/name).exists():paths[atlas/name]='selected event/context evidence'
        capabilities.append({'ic':ic['id'],'name':ic['name'],'feature_months':len(features),
             'supported':['history','state','pressure','regime','context','aggregate_pressure_forecast','retrospective_events'],
             'unavailable':[{'recipe':'verified_historical_network_features','reason':'Retained features lack immutable per-source first-publication vintages; LASTCHANGED alone is insufficient.'},
             {'recipe':'unit_generation_forecast','reason':'Full-period DISPATCHLOAD was compacted; selected-window observations cannot train a population model.'},
             {'recipe':'mechanical_future_setter_scenario','reason':'Full candidate equation states and all RHS/other-term forecasts are unavailable. Setter-switch classification remains supported.'},
             {'recipe':'forecast_weather_and_outage_vintages','reason':'Retained weather and status are retrospective; archived individual forecast issues and outage schedules are not established.'}]})
    p=ROOT/'results/aemo_vintages.parquet'
    if p.exists():paths[p]='original AEMO forecast issues; +1 minute ingestion allowance'
    manifest=[source_item(p,role) for p,role in paths.items() if p.exists()]
    d={'configuration':{k:v for k,v in c.items() if not k.startswith('_')},'code':code_manifest(),
       'sources':manifest,'capabilities':capabilities,'input_bytes':sum(x['bytes'] for x in manifest),
       'storage_scope':'additional framework artifacts across campaigns; existing input files preserved',
       'historical_claim':'development only; studied periods are not independently unseen'}
    # Presentation code should not invalidate fitted trials; modelling dependencies do.
    d['fingerprint']=fingerprint({'config':d['configuration'],'sources':manifest,
        'code':[x for x in d['code'] if Path(x['path']).name not in ['reports.py','__main__.py','shadow.py']]})
    if save:Store(c).json(c['_run']/'inventory.json',d)
    return d


def connector_data(c,ic):
    y=pd.read_parquet(ROOT/'data/processed/targets.parquet')
    y=y[y.ic.eq(ic['id'])].set_index('time').sort_index()
    y=y.reindex(pd.date_range('2024-08-25',pd.Timestamp(c['end'])-pd.Timedelta(minutes=30),freq='30min'))
    y.index.name='time'
    fs=[pd.read_parquet(p) for p in sorted((ROOT/'data'/ic['study']/'months').glob('*/constraint_features_30min.parquet'))]
    if not fs:raise ValueError(f"No topology capability for {ic['id']}")
    f=pd.concat(fs).set_index('time').sort_index()
    if not f.index.is_unique:raise ValueError('Duplicate topology timestamps')
    f=f.reindex(y.index)
    drivers=pd.read_parquet(ROOT/'data/processed/drivers.parquet').reindex(y.index)
    cols=[x for x in drivers if any(x.startswith(r+'__') for r in ic['regions']) and x.endswith(('__demand','__wind','__solar','__rooftop','__residual_demand','__available_generation'))]
    cols += [x for x in drivers if any(x.startswith(r[:3]+'_') for r in ic['regions']) and x.endswith(('__temperature_2m','__wind_speed_100m','__shortwave_radiation'))]
    context=drivers[cols].copy()
    raw=pd.read_parquet(ROOT/'data/processed/ic_5min.parquet',columns=['time','INTERCONNECTORID','export','import','MWFLOW'])
    raw=raw[raw.INTERCONNECTORID.eq(ic['id'])].set_index('time').sort_index()
    raw=raw.reindex(pd.date_range('2024-09-01',pd.Timestamp(c['end'])-pd.Timedelta(minutes=5),freq='5min'))
    return {'y':y,'f':f,'context':context,'raw':raw,'ic':ic}


def base_frame(d):
    y=d['y'];f=d['f'].shift(1);x=pd.DataFrame(index=y.index)
    for lag in [1,48,336]:
        for t in ['flow','export_tight','import_tight']:x[f'{t}_lag{lag}']=y[t].shift(lag)
    for t in ['flow','export_tight','import_tight']:x[t+'_delta']=y[t].shift(1)-y[t].shift(2)
    for col in STATE+PRESSURE+QUALITY:x[col]=pd.to_numeric(f[col],errors='coerce')
    for side in ['upper','lower']:
        # Aged observed setter is known only in retrospective track until lineage is verified.
        s=d['f'][side+'_constraint'];age=s.groupby(s.ne(s.shift()).cumsum()).cumcount()*30
        x[side+'_setter_age']=age.shift(1)
        x[side+'_switch_recent']=s.ne(s.shift()).astype(float).rolling(6).sum().shift(1)
    for col in d['context']:x['ctx_'+col]=d['context'][col].shift(1)
    return x.replace([np.inf,-np.inf],np.nan)


def design(d,origins,leads,recipe,pressure_forecast=None):
    """Integer positional origins and leads; future actuals only in explicit oracle recipe."""
    x=d['base'].iloc[origins].reset_index(drop=True)
    idx=d['y'].index;delivery=idx[origins]+pd.to_timedelta(leads*30,unit='min')
    hour=delivery.hour+delivery.minute/60
    for name,value in [('hour_sin',np.sin(2*np.pi*hour/24)),('hour_cos',np.cos(2*np.pi*hour/24)),('year_sin',np.sin(2*np.pi*delivery.dayofyear/365.25)),('year_cos',np.cos(2*np.pi*delivery.dayofyear/365.25)),('weekend',delivery.dayofweek>=5)]:x[name]=np.asarray(value,dtype=float)
    x['lead']=leads;x['log_lead']=np.log1p(leads)
    history=[col for col in x if '_lag' in col or col.endswith('_delta')]+['hour_sin','hour_cos','year_sin','year_cos','weekend','lead','log_lead']
    cols=history.copy();blocks=RECIPES[recipe]
    if 'state' in blocks:cols+=STATE+['upper_setter_age','lower_setter_age','upper_switch_recent','lower_switch_recent']
    if 'pressure' in blocks:cols+=PRESSURE
    if 'quality' in blocks:cols+=QUALITY
    if 'context' in blocks:cols += [col for col in x if col.startswith('ctx_')]
    if 'forecast_pressure' in blocks:
        if pressure_forecast is None:raise ValueError('Forecast pressure must be supplied as chronological out-of-fold estimates')
        for j in range(2):x[f'predicted_pressure_{j}']=pressure_forecast[origins,j];cols.append(f'predicted_pressure_{j}')
    if 'future_actuals' in blocks:
        for col in d['context']:
            x['actual_future_'+col]=d['context'][col].reindex(delivery).to_numpy();cols.append('actual_future_'+col)
    return x[cols].astype('float32')


def registry():
    return {'recipes':RECIPES,'state':STATE,'pressure':PRESSURE,'quality':QUALITY,
        'timing':'Topology samples minutes 00/30, then shifts 30 minutes. Targets average or minimise six five-minute observations.',
        'pressure_forecast':'Forecasts aggregate directional pressure, not unit generation. Trained with rolling monthly out-of-fold predictions.',
        'excluded':['constant envelope_move_persistence fields','future realised prices','full-period learned DUID rankings','future setters outside diagnostic labels'],
        'tracks':{'operational':'AEMO issue-vintage benchmark; unverified feature blocks unavailable','retrospective':'lagged reconstructed features and historical context','oracle':'explicit future-actual fundamentals diagnostic'}}
