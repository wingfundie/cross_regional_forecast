"""Validated conditional scenarios using historical origin information only."""
import json
import numpy as np
import pandas as pd
import joblib
from .common import *
from .model import Design,IDS,predict,chosen
from .prepare import START,season

def required_columns(d):
    return [c for c in d.weather_cols if c not in ['hour_sin','hour_cos','year_sin','year_cos','weekday','trend_days']]+[r+'__'+f+'_available' for r in REGIONS for f in ['wind','solar']]

def template(origin='2026-08-24 00:00',d=None):
    d=d or Design();origin=pd.Timestamp(origin)
    times=pd.date_range(origin+pd.Timedelta(minutes=30),periods=336,freq='30min')
    out=d.drivers.reindex(times)[required_columns(d)].copy()
    out.index.name='time'
    return out

def run_scenario(origin,inputs,d=None):
    d=d or Design();origin=pd.Timestamp(origin)
    if origin not in d.time:raise ValueError('Choose an origin with observed network history: '+str(d.time.min())+' to '+str(d.time.max()))
    if inputs.index.tz is not None:raise ValueError('Use fixed NEM time (UTC+10), without a timezone suffix.')
    expected=pd.date_range(origin+pd.Timedelta(minutes=30),periods=336,freq='30min')
    if len(inputs)!=336 or not inputs.index.equals(expected):raise ValueError('Supply exactly 336 consecutive half-hours, beginning 30 minutes after the selected origin.')
    required=required_columns(d);missing=set(required)-set(inputs)
    if missing:raise ValueError('Missing scenario fields: '+', '.join(sorted(missing)))
    inputs=inputs[required].apply(pd.to_numeric,errors='coerce')
    if not np.isfinite(inputs.to_numpy()).all():raise ValueError('Scenario values must be finite numbers. Fill missing inputs explicitly.')
    for c in inputs:
        if c.endswith(('__wind','__solar','__rooftop','_available','wind_speed_100m','shortwave_radiation')) and (inputs[c]<0).any():raise ValueError('Generation, availability, wind speed and radiation cannot be negative: '+c)
    inputs=inputs.copy()
    # Derive residual demand rather than trusting inconsistent edited columns.
    for r in REGIONS:inputs[r+'__residual_demand']=inputs[r+'__demand']-inputs[r+'__wind']-inputs[r+'__solar']
    times=d.time.union(expected).sort_values()
    drivers=d.drivers.reindex(times)
    drivers.loc[expected,required]=inputs
    drivers['hour_sin']=np.sin(2*np.pi*(times.hour+times.minute/60)/24)
    drivers['hour_cos']=np.cos(2*np.pi*(times.hour+times.minute/60)/24)
    drivers['year_sin']=np.sin(2*np.pi*times.dayofyear/365.25)
    drivers['year_cos']=np.cos(2*np.pi*times.dayofyear/365.25)
    drivers['weekday']=times.dayofweek;drivers['trend_days']=(times-START).total_seconds()/86400
    extension=len(times)-len(d.time)
    if extension:
        d.y=np.pad(d.y,((0,0),(0,extension),(0,0)),constant_values=np.nan)
        d.state=np.pad(d.state,((0,0),(0,extension),(0,0)),constant_values=np.nan)
        d.published=np.pad(d.published,((0,0),(0,extension)),constant_values=np.datetime64('NaT'))
        refs=pd.read_csv(RESULTS/'seasonal_references.csv').set_index(['ic','season'])
        extra=np.stack([refs.loc[[(k,int(s)) for s in season(times[-extension:])],['export','import']].to_numpy()/2 for k in IDS])
        d.threshold=np.concatenate([d.threshold,extra],axis=1)
    d.time=times;d.drivers=drivers
    d.future=drivers[d.weather_cols].to_numpy(dtype='float32');d.available=d.future.copy()
    for r in REGIONS:
        for f in ['wind','solar']:d.available[:,d.weather_cols.index(r+'__'+f)]=drivers[r+'__'+f+'_available']
        d.available[:,d.weather_cols.index(r+'__residual_demand')]=drivers[r+'__demand']-drivers[r+'__wind_available']-drivers[r+'__solar_available']
    d.origin_gen=drivers[[r+'__available_generation' for r in REGIONS]].to_numpy(dtype='float32')
    ci=np.repeat(np.arange(6),336);oi=np.full(len(ci),times.get_loc(origin));h=np.tile(np.arange(1,337),6);vi=oi+h
    cache={}
    for kind in ['fundamentals','weather','availability']:
        x=d.features(ci,oi,h,kind)
        a=np.full((6,len(times),5),np.nan,dtype='float32')
        for j,t in enumerate(TARGETS):a[ci,vi,j]=joblib.load(MODELS/f'{kind}_{t}.joblib').booster_.predict(x,num_threads=4)*d.scale[ci,j]
        cache[kind]=a
    models=[joblib.load(MODELS/f'network_{t}.joblib') for t in TARGETS]
    pred=predict(d,ci,oi,h,cache,models)
    cfg=json.loads((MODELS/'selection.json').read_text());sel=chosen(d,ci,vi,h,pred,cfg)
    out=pd.DataFrame({'ic':np.array(IDS)[ci],'origin':origin,'time':times[vi],'lead_hours':h/2})
    for t,cols in sel.items():
        for q,a in cols.items():
            if t=='flow' and q in ['probability','cutoff']:continue
            out[t+'_'+q]=a
    for j,direction in enumerate(['export','import']):out[direction+'_threshold']=d.threshold[ci,vi,j]
    return out

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--origin',default='2026-08-24 00:00');p.add_argument('--input');p.add_argument('--output',default=str(RESULTS/'scenario_example.csv'));a=p.parse_args()
    if a.input:
        inputs=pd.read_csv(a.input,index_col='time',parse_dates=['time'])
    else:
        inputs=template(a.origin);inputs.to_csv(RESULTS/'scenario_template.csv')
    out=run_scenario(a.origin,inputs);out.to_csv(a.output,index=False)
    print('SCENARIO COMPLETE',out.shape,a.output)
