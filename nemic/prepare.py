"""Construct audited five-minute observations and interval-ending half-hours."""
import json
import numpy as np
import pandas as pd
from .common import *

START=pd.Timestamp('2023-09-01'); END=pd.Timestamp('2026-09-01')
TRAIN_END=pd.Timestamp('2025-09-01'); TEST_START=pd.Timestamp('2026-03-01')
IC_COLS=['SETTLEMENTDATE','INTERCONNECTORID','INTERVENTION','RUNNO','MWFLOW','METEREDMWFLOW',
         'EXPORTLIMIT','IMPORTLIMIT','EXPORTGENCONID','IMPORTGENCONID','LOCALLY_CONSTRAINED_EXPORT',
         'LOCALLY_CONSTRAINED_IMPORT','LASTCHANGED','MARGINALVALUE','VIOLATIONDEGREE']
REG_COLS=['SETTLEMENTDATE','REGIONID','INTERVENTION','RUNNO','TOTALDEMAND','SS_WIND_CLEAREDMW',
          'SS_SOLAR_CLEAREDMW','SS_WIND_UIGF','SS_SOLAR_UIGF','AVAILABLEGENERATION','AVAILABLELOAD',
          'DISPATCHABLELOAD','TOTALINTERMITTENTGENERATION','DEMAND_AND_NONSCHEDGEN','LASTCHANGED']

def read_table(table,columns=None):
    paths=sorted((DATA/'tables'/table).glob('*.parquet'))
    if not paths:raise ValueError('Missing table '+table)
    import pyarrow.parquet as pq
    frames=[]
    for p in paths:
        available=pq.read_schema(p).names
        use=[c for c in (columns or available) if c in available]
        frames.append(pd.read_parquet(p,columns=use))
    return pd.concat(frames,ignore_index=True)

def numeric(df,columns):
    for c in columns:
        if c in df:df[c]=pd.to_numeric(df[c],errors='coerce')
    return df

def physical(df,key,price=False):
    df['time']=pd.to_datetime(df['SETTLEMENTDATE'],format='%Y/%m/%d %H:%M:%S',errors='coerce')
    df=df[(df.time>START)&(df.time<=END)].copy()
    numeric(df,['INTERVENTION','RUNNO'])
    df['LASTCHANGED']=pd.to_datetime(df['LASTCHANGED'],errors='coerce')
    # Physical dispatch is intervention=1 when present. Pricing is intervention=0.
    if price:df=df[df.INTERVENTION==0]
    df=df.sort_values(['time',key,'INTERVENTION','RUNNO','LASTCHANGED'])
    return df.drop_duplicates(['time',key],keep='last')

def season(dates):
    return (pd.DatetimeIndex(dates).month%12//3).astype(int)

def run():
    audit={}
    raw=read_table('DISPATCHINTERCONNECTORRES',IC_COLS)
    audit['ic_original_rows']=len(raw)
    ic=physical(raw,'INTERCONNECTORID')
    numeric(ic,[c for c in IC_COLS if c not in ['SETTLEMENTDATE','INTERCONNECTORID','EXPORTGENCONID','IMPORTGENCONID','LASTCHANGED']])
    unexpected=set(ic.INTERCONNECTORID)-set(IC)
    if unexpected:raise ValueError('Unmapped connectors require standing-data review: '+str(unexpected))
    # Keep negative directional limits: these denote forced flow, not negative
    # physical capacity. Never take abs(), which would reverse their meaning.
    ic['flow']=ic.MWFLOW
    ic['export']=ic.EXPORTLIMIT
    ic['import']=-ic.IMPORTLIMIT
    ic['time30']=ic.time.dt.ceil('30min')
    ic.to_parquet(PROCESSED/'ic_5min.parquet',index=False)
    summaries=[]
    for ident,g in ic.groupby('INTERCONNECTORID'):
        b=g.groupby('time30').agg(flow=('flow','mean'),export=('export','mean'),
          import_mean=('import','mean'),export_tight=('export','min'),import_tight=('import','min'),
          metered=('METEREDMWFLOW','mean'),n5=('time','nunique'),intervention=('INTERVENTION','max'),
          export_setter=('EXPORTGENCONID','last'),import_setter=('IMPORTGENCONID','last'),
          export_network=('LOCALLY_CONSTRAINED_EXPORT','max'),import_network=('LOCALLY_CONSTRAINED_IMPORT','max'),
          lastchanged=('LASTCHANGED','max'),violation=('VIOLATIONDEGREE','max')).rename(columns={'import_mean':'import'})
        b.index.name='time'; b['ic']=ident
        # Incomplete target intervals are not silently averaged or interpolated.
        b.loc[b.n5!=6,TARGETS]=np.nan
        summaries.append(b.reset_index())
    targets=pd.concat(summaries,ignore_index=True)
    audit['interconnectors']={k:{'five_min_rows':int(len(g)),'start':str(g.time.min()),'end':str(g.time.max()),
        'intervention_rows':int((g.INTERVENTION==1).sum()),'negative_export':int((g.export<0).sum()),
        'negative_import_directional':int((g['import']<0).sum())} for k,g in ic.groupby('INTERCONNECTORID')}
    audit['incomplete_halfhours']=targets.loc[targets.n5!=6,['time','ic','n5']].to_dict('records')
    del raw,ic
    reg=physical(read_table('DISPATCHREGIONSUM',REG_COLS),'REGIONID')
    numeric(reg,[c for c in REG_COLS if c not in ['SETTLEMENTDATE','REGIONID','LASTCHANGED']])
    reg=reg[reg.REGIONID.isin(REGIONS)]
    reg['time30']=reg.time.dt.ceil('30min')
    rename={'TOTALDEMAND':'demand','SS_WIND_CLEAREDMW':'wind','SS_SOLAR_CLEAREDMW':'solar',
            'SS_WIND_UIGF':'wind_available','SS_SOLAR_UIGF':'solar_available',
            'AVAILABLEGENERATION':'available_generation','AVAILABLELOAD':'available_load',
            'DISPATCHABLELOAD':'dispatchable_load','TOTALINTERMITTENTGENERATION':'nonscheduled'}
    regional=reg.groupby(['time30','REGIONID'])[list(rename)].mean().rename(columns=rename)
    counts=reg.groupby(['time30','REGIONID']).time.nunique()
    regional.loc[counts!=6,:]=np.nan
    regional.index.names=['time','region']
    audit['regional_incomplete_halfhours']=int((counts!=6).sum())
    del reg
    roof=read_table('ROOFTOP_PV_ACTUAL')
    roof['time']=pd.to_datetime(roof.INTERVAL_DATETIME,errors='coerce')
    roof=roof[(roof.time>START)&(roof.time<=END)&roof.REGIONID.isin(REGIONS)].copy()
    roof['POWER']=pd.to_numeric(roof.POWER,errors='coerce')
    roof['quality_rank']=(roof.TYPE=='MEASUREMENT').astype(int)
    roof=roof.sort_values(['quality_rank','LASTCHANGED']).drop_duplicates(['time','REGIONID'],keep='last')
    roof=roof.set_index(['time','REGIONID']).POWER.rename('rooftop')
    roof.index.names=['time','region']
    regional=regional.join(roof)
    # TOTALDEMAND is already net of embedded rooftop generation. Do not subtract
    # rooftop again; keep its level as a separate explanatory variable.
    regional['residual_demand']=regional.demand-regional.wind-regional.solar
    regional.to_parquet(PROCESSED/'regional_30min.parquet')
    wide=regional.unstack('region'); wide.columns=[r+'__'+c for c,r in wide.columns]
    weather=pd.read_parquet(PROCESSED/'weather_30min.parquet')
    drivers=wide.join(weather)
    drivers['hour_sin']=np.sin(2*np.pi*(drivers.index.hour+drivers.index.minute/60)/24)
    drivers['hour_cos']=np.cos(2*np.pi*(drivers.index.hour+drivers.index.minute/60)/24)
    drivers['year_sin']=np.sin(2*np.pi*drivers.index.dayofyear/365.25)
    drivers['year_cos']=np.cos(2*np.pi*drivers.index.dayofyear/365.25)
    drivers['weekday']=drivers.index.dayofweek
    drivers['trend_days']=(drivers.index-START).total_seconds()/86400
    drivers.to_parquet(PROCESSED/'drivers.parquet')
    prices=physical(read_table('DISPATCHPRICE',['SETTLEMENTDATE','REGIONID','INTERVENTION','RUNNO','RRP','LASTCHANGED']),'REGIONID',price=True)
    prices['RRP']=pd.to_numeric(prices.RRP,errors='coerce')
    prices['time30']=prices.time.dt.ceil('30min')
    prices=prices.groupby(['time30','REGIONID']).RRP.mean().unstack('REGIONID')
    prices.index.name='time'; prices.to_parquet(PROCESSED/'prices.parquet')
    targets['season']=season(targets.time)
    refs=targets[targets.time<=TRAIN_END].groupby(['ic','season'])[['export','import']].agg(lambda x:x[x>0].median())
    targets=targets.join(refs.add_suffix('_reference'),on=['ic','season'])
    for d in ['export','import']:
        targets[d+'_threshold']=.5*targets[d+'_reference']
        # A nonpositive reference is not a meaningful proportional capacity.
        targets.loc[targets[d+'_reference']<=0,d+'_threshold']=np.nan
        for suffix in ['', '_tight']:
            targets[d+suffix+'_event']=(targets[d+suffix]<targets[d+'_threshold']).where(targets[d+suffix].notna()&targets[d+'_threshold'].notna())
    targets.to_parquet(PROCESSED/'targets.parquet',index=False)
    refs.to_csv(RESULTS/'seasonal_references.csv')
    audit['driver_missing_fraction']=drivers.isna().mean().to_dict()
    audit['target_missing_fraction']=targets[TARGETS].isna().mean().to_dict()
    audit['half_hour_count']=len(targets)
    audit['expected_half_hour_count']=int((END-START).total_seconds()/1800)*len(IC)
    audit['time_convention']='Fixed UTC+10 NEM time; interval-ending, (start,end]; no daylight saving'
    audit['physical_run']='INTERVENTION=1 preferred when available; otherwise 0. Price context uses pricing run 0.'
    audit['imports']='Directional import = - raw signed IMPORTLIMIT; negative values retained as forced-flow states.'
    audit['renewables']='AEMO regional semi-scheduled cleared wind/solar; nonscheduled and rooftop separate; UIGF availability retained.'
    audit['seasonal_reference']='Training-only seasonal median of positive reported directional limits; forced-flow/zero observations remain targets and events.'
    dump(RESULTS/'data_audit.json',audit)
    dump(RESULTS/'split.json',dict(start=START,train_end=TRAIN_END,tune_end='2025-12-01',
        calibration_end='2026-02-01',test_start=TEST_START,end=END,
        origin_step_minutes=30,max_horizon_steps=336,observation_delay_minutes=30,
        rule='Every target stays inside its split; validation/test origins begin at split start. No cross-boundary training targets.'))
    print('PREPARED',len(targets),'target half-hours',drivers.shape,'drivers',flush=True)
    print('MISSING',audit['target_missing_fraction'],flush=True)
    if len(targets)!=audit['expected_half_hour_count']:raise ValueError('Missing target time grid; inspect audit')

if __name__=='__main__':run()
