"""Run the NSW MAXGEN expression on whole native historical operating paths."""
from pathlib import Path
import numpy as np
import pandas as pd
import run

OUT=Path(__file__).resolve().parent
QC='N^^Q_NIL_MAXGEN'
def main():
    obs=pd.concat([pd.read_csv(f) for f in sorted(OUT.glob('20*.csv'))],ignore_index=True)
    obs['end']=pd.to_datetime(obs.end);obs['day']=obs.end.dt.normalize()
    obs=obs[~obs.intervention.astype(str).str.lower().eq('true')].copy()
    obs['replayed']=obs.apply(run.qni,axis=1)
    obs['replay_error']=obs.replayed-obs.QNI_solution
    applied=obs[obs.QNI_version.eq('20251202000000_1')][['end','QNI_version','replayed','QNI_solution','replay_error']]
    applied.to_csv(OUT/'qni_replay.csv',index=False)
    assert len(applied)>10 and applied.replay_error.abs().max()<0.01,applied.describe()
    for k in run.LEAVES.spd_id[run.LEAVES.spd_type.eq('S')].unique():assert obs[k].dropna().isin([0.,1.]).all()
    banks='TAMWORTH_CAP1_STATUS TAMWORTH_CAP2_STATUS TAMWORTH_CAP3_STATUS TAMWORTH_CAP4_STATUS TAMWORTH_R1_STATUS TAMWORTH_R2_STATUS'.split()
    weights=np.array([120,129,65,65,-50,-50])*.2091
    obs['bank_term']=obs[banks].dot(weights)
    obs['max_unit_term']=-1.0653*obs[run.EQUATIONS[QC].query("operation=='MAX'").spd_id].max(axis=1,skipna=False)
    quantities=['replayed','MW_DP_99N','MW_AR_TX3','MVA_AR_86','MVAR_AR_TX3','bank_term','max_unit_term']
    obs=obs[obs.groupby('day').end.transform('size').eq(6)]
    issued=OUT.parent/'feeds/regional_forecasts.csv'
    feed=pd.read_csv(issued,parse_dates=['end','origin']) if issued.exists() else None
    records=[]; scenarios=[]
    for day,actual in obs[obs.day.ge('2026-02-01')].groupby('day'):
        for lead in (10,21,42):
            origin=day+pd.Timedelta(hours=10)-pd.Timedelta(days=lead)
            h=obs[(obs.day+pd.Timedelta(days=2)<origin)&(pd.to_datetime(obs.modified)<origin)]
            complete=h.groupby('day')[quantities].count().eq(6).all(axis=1)
            h=h[h.day.isin(complete[complete].index)]
            d=h.groupby('day').mean(numeric_only=True)
            if len(d)<3:continue
            targets={'clock':d.index,'last sampled state':[d.index[-1]]}
            # Days represent physically co-observed cases across all inputs.
            topology=(d[banks]-d.loc[d.index[-1],banks]).abs().sum(axis=1)
            targets['prior bank configuration']=topology.sort_index(ascending=False).sort_values(kind='stable').head(3).index
            if feed is not None:
                row=feed[feed.end.eq(day+pd.Timedelta(hours=10,minutes=30))&feed.region.eq('NSW1')&feed.lead.eq(lead)&feed.origin.le(origin)]
                if len(row)==1:
                    delta=(d.NSW1-row.iloc[0].pasa).abs()
                    targets['issued demand analogue']=delta.nsmallest(3).index
                    targets['clock demand analogue']=(d.NSW1-row.iloc[0].clock).abs().nsmallest(3).index
                    if 'pasa_weekly' in row:
                        targets['issued weekly energy analogue']=(d.NSW1-row.iloc[0].pasa_weekly).abs().nsmallest(3).index
                    rank=(delta.rank(pct=True)+topology.rank(pct=True))
                    targets['demand plus bank analogue']=rank.nsmallest(3).index
            for method,days in targets.items():
                for k in quantities:
                    sample=d.loc[days,k]
                    pred=sample.mean();truth=actual[k].mean()
                    records.append((day,origin,lead,method,k,pred,truth,len(sample),sample.min(),sample.max()))
                for source_day in days:
                    row=d.loc[source_day]
                    scenarios.append((day,origin,lead,method,source_day,*[row[k] for k in quantities]))
    cols=['day','origin','lead','method','point','forecast','actual','paths','low','high']
    frame=pd.DataFrame(records,columns=cols)
    frame['phase']=np.where(frame.day.dt.day.isin([19,22]),'stress','routine')
    frame['absolute']=(frame.forecast-frame.actual).abs()
    frame['within']=(frame.actual>=frame.low)&(frame.actual<=frame.high)
    frame['width']=frame.high-frame.low
    frame.to_csv(OUT/'coherent_predictions.csv',index=False)
    pd.DataFrame(scenarios,columns=['day','origin','lead','method','source_day',*quantities]).to_csv(OUT/'scenario_paths.csv',index=False)
    frame.groupby(['phase','lead','method','point']).agg(n=('actual','count'),mae=('absolute','mean'),max_abs=('absolute','max'),width=('width','mean'),coverage=('within','mean')).to_csv(OUT/'coherent_scores.csv')
if __name__=='__main__':main()
