"""Small forward dispatch study in fixed NEM time, executed in the project checkout."""
from pathlib import Path
import json
import hashlib
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
CONFIG={
    'qni':('NSW1-QLD1','N>>NIL_85_86_S','2025-09-22',-.986,'QLD1',8),
    'vni':('VIC1-NSW1','V^^N_NIL_1','2024-10-31',1.,'VIC1',17)}
FIT=pd.date_range('2025-09-23','2025-09-29')
CAL=pd.to_datetime(['2025-11-23','2025-11-24','2025-11-26','2025-11-28'])
ROUTINE=pd.to_datetime(['2026-02-04','2026-02-11','2026-02-18','2026-02-25'])
MONTHS=['2025-09','2025-10','2025-11','2025-12','2026-01','2026-02','2026-03']
LEADS=[10,21,42]

def scoped_inputs():
    d=pd.concat(pd.read_parquet(p) for p in sorted(OUT.glob('20*.parquet')))
    d['time']=pd.to_datetime(d.SETTLEMENTDATE)
    d['effective']=pd.to_datetime(d.GENCONID_EFFECTIVEDATE)
    for k in ['RHS','LHS','MARGINALVALUE']:d[k]=pd.to_numeric(d[k])
    s=d[d.CONSTRAINTID.isin(['DATASNAP_TE_967_1','N::Q_NIL_KC'])].pivot(index='time',columns='CONSTRAINTID',values='RHS')
    s.columns=['terr','kc']
    s['terr']-=10000
    return d,s

def load_panel(link,case,factor,other,version,eq,scada,all_ic,regional):
    linked=all_ic[all_ic.INTERCONNECTORID.eq(link)].set_index('time')
    frame=linked[['export','import','MWFLOW','EXPORTGENCONID','IMPORTGENCONID']].rename(columns={'MWFLOW':'flow'})
    c=eq[eq.CONSTRAINTID.eq(case) & eq.effective.eq(version) & eq.GENCONID_VERSIONNO.eq('1')].set_index('time')
    frame=frame.join(c[['RHS','LHS','MARGINALVALUE','released']]).join(scada)
    frame['directlink']=all_ic[all_ic.INTERCONNECTORID.eq('N-Q-MNSP1')].set_index('time').METEREDMWFLOW
    folder='constraint_'+('qni' if factor<0 else 'vni')+'_2y'
    paths=[ROOT/'data'/folder/'months'/m/'constraint_features_5min.parquet' for m in MONTHS]
    envelopes=pd.concat(pd.read_parquet(p,columns=['time','conditional_upper','conditional_lower']) for p in paths)
    frame=frame.join(envelopes.set_index('time'))
    frame['slot']=frame.index.ceil('30min')
    frame=frame.join(regional[['NSW1',other]].rename(columns={other:'other'}),on='slot')
    frame['h']=frame.RHS-frame.LHS
    frame['bound']=frame.flow+frame.h/factor
    frame['bind']=frame.MARGINALVALUE.abs()>1e-5
    return frame

def slices(day):
    return pd.date_range(day+pd.Timedelta(minutes=5),periods=288,freq='5min')

def paths(group,slot,method,factor,tag,nsw,other,scales):
    # An analogue is one coherent historical five-minute dispatch state.
    if method=='issued demand':
        diff=((group.NSW1-nsw)/scales['NSW1'])**2+((group.other-other)/scales['other'])**2
        group=group[group.day.isin(diff.groupby(group.day).mean().nsmallest(3).index)]
    estimates=[]
    for day,b in group.groupby('day'):
        assert len(b)==6
        limit=b.bound
        upper=np.minimum(b.conditional_upper,limit) if factor>0 else b.conditional_upper
        lower=np.maximum(b.conditional_lower,limit) if factor<0 else b.conditional_lower
        row={'export':upper.min(),'import':(-lower).min(),'rhs':b.RHS.mean(),
             'headroom':b.h.min(),'flow':b.flow.mean(),'economic_frequency':float(b.bind.any()),
             'native_rhs':b.RHS.to_numpy(),'native_lhs':b.LHS.to_numpy(),
             'adjusted_export':upper.min(),'adjusted_import':(-lower).min()}
        if tag=='qni':
            n=nsw if method=='issued demand' else b.NSW1
            q=other if method=='issued demand' else b.other
            kc=1383-.001*(b.directlink+b.terr)**2-.0239*n+.0524*q-.6394*b.terr
            row['kc']=kc.mean()
        estimates.append(row)
    return {k:np.mean([r[k] for r in estimates],axis=0) for k in estimates[0]}

def evaluate():
    eq,scada=scoped_inputs()
    ics=pd.read_parquet(ROOT/'data/processed/ic_5min.parquet')
    region=pd.read_parquet(ROOT/'data/processed/regional_30min.parquet',columns=['demand']).demand.unstack()
    feed=pd.read_csv(OUT.parent/'feeds/regional_forecasts.csv',parse_dates=['end','origin']).set_index(['end','lead','region']).sort_index()
    log=json.loads((OUT/'archive_sources.json').read_text())
    releases={r['month']:pd.Timestamp(r['available']) for r in log}
    rows=[];native=[]
    for tag,(link,case,version,factor,other,stress) in CONFIG.items():
        panel=load_panel(link,case,factor,other,pd.Timestamp(version),eq,scada,ics,region)
        train=panel.loc[FIT[0]+pd.Timedelta(minutes=5):FIT[-1]+pd.Timedelta(days=1)].copy()
        train['day']=(train.index-pd.Timedelta(seconds=1)).normalize()
        assert len(train)==len(FIT)*288 and train[['LHS','RHS','conditional_upper','conditional_lower','NSW1','other']].notna().all().all()
        scales=train[['NSW1','other']].std()
        train_clocks=dict(tuple(train.groupby(train.slot.dt.strftime('%H%M'))))
        clock_preds={clock:paths(g,None,'clock equation',factor,tag,None,None,scales) for clock,g in train_clocks.items()}
        errors=train.assign(b= train['bound'])
        # Stable retained difference between a conditional envelope and the reported limit.
        bias={'export':(errors.export-errors.conditional_upper).median(),
              'import':(errors['import']+errors.conditional_lower).median()}
        days=[*CAL,*ROUTINE,pd.Timestamp(2026,2,stress)]
        # Longer seasonal reference, fixed before all origins.
        hist=panel.loc['2024-01-01':'2025-09-30'].copy()
        hist['day']=(hist.index-pd.Timedelta(seconds=1)).normalize()
        hist['clock']=hist.slot.dt.strftime('%H%M')
        hhist=hist.groupby(['day','clock']).agg(n=('export','size'),export=('export','min'),imp=('import','min')).query('n==6').reset_index()
        for day in days:
            phase='calibration' if day in CAL else 'routine' if day in ROUTINE else 'stress'
            tm=slices(day);actual=panel.reindex(tm)
            for lead in LEADS:
                origin=day-pd.Timedelta(days=lead)
                assert releases['202509']<origin
                old_month=max(m for m,t in releases.items() if t<origin)
                # End of last completely published month; carry last observed interval (no future origin day profile).
                end=pd.Period(old_month,freq='M').end_time.normalize()+pd.Timedelta(days=1)
                anchor=panel.loc[:end].dropna(subset=['RHS','LHS','export','import']).iloc[-1]
                assert pd.Timestamp(anchor.released)<origin
                for j in range(48):
                    t=tm[j*6:j*6+6];truth=actual.loc[t];slot=t[-1]
                    if truth[['RHS','LHS','export','import','flow']].isna().any().any():
                        raise ValueError(f'Incomplete exact-version observed block {case}, {slot}')
                    clock=slot.strftime('%H%M')
                    histday=hhist[(hhist.clock==clock) & ((hhist.day.dt.dayofweek>=5)==(day.dayofweek>=5))]
                    distance=(histday.day.dt.dayofyear-day.dayofyear).abs()
                    histday=histday[np.minimum(distance,366-distance)<=35]
                    old=train_clocks[clock]
                    north=feed.loc[(slot,lead,'NSW1')];south=feed.loc[(slot,lead,other)]
                    assert north.origin==origin and south.origin==origin and north.run==south.run
                    for method in ['seasonal direct','carry last published archive','clock equation','issued demand']:
                        row=dict(link=tag,equation=case,day=day,end=slot,origin=origin,lead=lead,partition=phase,method=method,
                                 actual_export=truth.export.min(),actual_import=truth['import'].min(),actual_rhs=truth.RHS.mean(),
                                 actual_headroom=truth.h.min(),actual_kc=truth.kc.mean() if tag=='qni' else np.nan,
                                 bind=int(truth.bind.any()),actual_native_bind=int(truth.bind.sum()))
                        if method=='seasonal direct':
                            row.update(export=histday.export.median(),**{'import':histday.imp.median()})
                        elif method=='carry last published archive':
                            row.update(export=anchor.export,**{'import':anchor['import']},rhs=anchor.RHS,headroom=anchor.h,
                                       economic_frequency=float(anchor.bind),kc=anchor.kc if tag=='qni' else np.nan)
                        else:
                            pred=clock_preds[clock].copy() if method=='clock equation' else paths(old,slot,method,factor,tag,north.pasa_weekly,south.pasa_weekly,scales)
                            nr=pred.pop('native_rhs');nl=pred.pop('native_lhs')
                            for n,stamp in enumerate(t):
                                native.append([tag,stamp,origin,lead,phase,method,nr[n],nl[n],truth.loc[stamp,'RHS'],truth.loc[stamp,'LHS']])
                            for k in ['export','import']:pred['adjusted_'+k]=pred[k]+bias[k]
                            row.update(pred)
                        rows.append(row)
    n=pd.DataFrame(native,columns=['link','end','origin','lead','partition','method','rhs','lhs','actual_rhs','actual_lhs'])
    n.to_parquet(OUT/'native_predictions.parquet',index=False)
    return pd.DataFrame(rows)

def score(d):
    cal=d[d.partition.eq('calibration')];test=d[~d.partition.eq('calibration')]
    metrics=[];alerts=[]
    for (link,lead,method,part),group in test.groupby(['link','lead','method','partition']):
        earlier=cal[cal.link.eq(link)&cal.lead.eq(lead)&cal.method.eq(method)]
        assert pd.Timestamp('2025-12-08 12:05:38')<group.origin.min()
        for target in ['rhs','headroom','export','import','kc','adjusted_export','adjusted_import']:
            actual='actual_'+target.removeprefix('adjusted_')
            g=group.dropna(subset=[target,actual])
            if g.empty:continue
            err=g[target]-g[actual]
            band=(earlier[target]-earlier[actual]).abs().quantile(.9,interpolation='higher')
            metrics.append(dict(link=link,lead=lead,method=method,partition=part,target=target,n=len(g),days=g.day.nunique(),
                                mae=err.abs().mean(),bias=err.mean(),p90=err.abs().quantile(.9),band=band,
                                calibration_n=earlier[target].notna().sum(),coverage=(err.abs()<=band).mean() if pd.notna(band) else np.nan,width=2*band))
        for th in [.10,.25,.50]:
            g=group.dropna(subset=['economic_frequency'])
            if g.empty:continue
            a=g.economic_frequency>=th; actual=g.bind.astype(bool)
            alerts.append(dict(link=link,lead=lead,method=method,partition=part,cutoff=th,n=len(g),days=g.day.nunique(),event_days=g[actual].day.nunique(),positives=actual.sum(),tp=(a&actual).sum(),fp=(a&~actual).sum(),fn=(~a&actual).sum()))
    return pd.DataFrame(metrics),pd.DataFrame(alerts)

if __name__=='__main__':
    d=evaluate()
    d.to_csv(OUT/'predictions.csv',index=False)
    metrics,alerts=score(d)
    metrics.to_csv(OUT/'scores.csv',index=False)
    alerts.to_csv(OUT/'alerts.csv',index=False)
    print(metrics.query("partition=='routine' and lead==21 and target in ['export','import','rhs','kc']").pivot_table(index=['link','method'],columns='target',values='mae').round(2))

