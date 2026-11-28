"""Ararat and Stawell state-dependent apparent loading at the Ararat terminal."""
from pathlib import Path
import pandas as pd
import numpy as np
out=Path(__file__).resolve().parent
keys=['ART_CB_F_STAT','STL_CB_B_STAT']
value='MVA_ART_STL'
obs=pd.concat([pd.read_csv(f) for f in sorted(out.glob('20*.csv'))])
obs=obs[obs.intervention.astype(str).str.lower().eq('false')].dropna(subset=[*keys,value])
obs['end']=pd.to_datetime(obs.end);obs['day']=obs.end.dt.normalize()
obs=obs[obs.groupby('day').end.transform('size').eq(6)].copy()
obs['state']=obs[keys].astype(int).astype(str).agg(''.join,axis=1)
rows=[];scenarios=[]
for day,g in obs[obs.day.ge('2026-02-01')].groupby('day'):
    for lead in [10,21,42]:
        origin=day+pd.Timedelta(hours=10)-pd.Timedelta(days=lead)
        past=obs[(obs.day+pd.Timedelta(days=2)<origin)&(pd.to_datetime(obs.modified)<origin)]
        for t in g.itertuples():
            pool=past[past.end.dt.minute.eq(t.end.minute)].sort_values('end')
            lookup=pool.groupby('state')[value].median()
            last=pool.iloc[-1]
            for state,v in lookup.items():
                scenarios.append((t.end,lead,state,v,int(pool.state.eq(state).sum())))
            for method,forecast in [('clock median',pool[value].median()),('last flow',last[value]),
                                    ('previous state',lookup[last.state]),('known delivery state diagnostic',lookup.get(t.state,np.nan))]:
                rows.append((day,t.end,origin,lead,method,forecast,getattr(t,value),last.state,t.state))
df=pd.DataFrame(rows,columns=['day','end','origin','lead','method','forecast','actual','prior_state','actual_state'])
df['partition']=np.where(df.day.dt.day.isin([19,22]),'stress','routine')
df.to_csv(out/'breaker_predictions.csv',index=False)
pd.DataFrame(scenarios,columns=['end','lead','scenario','terminal_mva','historical_cases']).to_csv(out/'breaker_scenarios.csv',index=False)
d=df.groupby(['day','partition','lead','method']).agg(actual=('actual','mean'),forecast=('forecast','mean'),n=('forecast','count')).query('n==6').reset_index()
d['absolute']=(d.actual-d.forecast).abs()
d.groupby(['partition','lead','method']).absolute.agg(n='size',mae='mean',max_abs='max').to_csv(out/'breaker_scores.csv')
