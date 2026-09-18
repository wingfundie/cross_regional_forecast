"""Descriptive five-minute evidence, not a forecast or SRA settlement engine."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
START, END = pd.Timestamp('2024-09-01'), pd.Timestamp('2026-09-01')
paths = [ROOT / f'data/event_{ic}_2y/prices_5min.parquet' for ic in ('vni','qni','vsa')]
frames = [pd.read_parquet(p) for p in paths]
raw = pd.concat(frames, ignore_index=True)
raw = raw[(raw.time > START) & (raw.time <= END) & (raw.INTERVENTION == 0)].copy()
conflicts = raw.groupby(['time','REGIONID']).RRP.nunique().gt(1).sum()
assert conflicts == 0, f'{conflicts} conflicting regional prices'
raw = raw.drop_duplicates(['time','REGIONID']).sort_values(['time','REGIONID'])
p = raw.pivot(index='time',columns='REGIONID',values='RRP').sort_index()
expected = pd.date_range(START + pd.Timedelta(minutes=5), END, freq='5min')
assert p.index.equals(expected)
assert p.notna().all().all()
quarter = (p.index-pd.Timedelta(nanoseconds=1)).to_period('Q')
rows=[]
for region in p:
    for q, s in p[region].groupby(quarter):
        hit=s.gt(300); cap=(s-300).clip(lower=0)
        h=len(s)/12; episodes=int((hit & ~hit.shift(1,fill_value=False)).sum())
        daily=cap.groupby((s.index-pd.Timedelta(nanoseconds=1)).date).sum()
        h30=s.resample('30min',closed='right',label='right').mean()
        expected_n=int(((q+1).start_time-q.start_time).total_seconds()/300)
        rows.append(dict(quarter=str(q),region=region,complete=len(s)==expected_n,intervals=len(s),hours=h,
          mean_price=s.mean(),capped_energy=s.clip(upper=300).mean(),cap_excess=cap.mean(),
          above300_hours=hit.sum()/12,above300_pct=100*hit.mean(),episodes=episodes,
          excess_when_above=cap[hit].mean() if hit.any() else 0,
          negative_pct=100*s.lt(0).mean(),cap_from_halfhour=(h30-300).clip(lower=0).mean(),
          top5days_cap_pct=100*daily.nlargest(5).sum()/daily.sum() if daily.sum() else 0))
regional=pd.DataFrame(rows)
regional.to_csv(OUT/'historical_regional_decomposition.csv',index=False)
spread_rows=[]; states=[]; flow_rows=[]
for name,a,b,key in [('VIC to NSW','VIC1','NSW1','vni'),('NSW to QLD','NSW1','QLD1','qni'),('VIC to SA','VIC1','SA1','vsa')]:
    x=p[b]-p[a]; e=p[b].clip(upper=300)-p[a].clip(upper=300)
    c=(p[b]-300).clip(lower=0)-(p[a]-300).clip(lower=0)
    assert np.allclose(x,e+c)
    state=np.select([(p[a]<=300)&(p[b]<=300),(p[a]<=300)&(p[b]>300),(p[a]>300)&(p[b]<=300)],['neither','destination_only','origin_only'],default='both')
    for q in quarter.unique():
        mask=quarter==q
        expected_n=int(((q+1).start_time-q.start_time).total_seconds()/300)
        spread_rows.append(dict(quarter=str(q),direction=name,complete=mask.sum()==expected_n,spread=x[mask].mean(),energy=e[mask].mean(),scarcity=c[mask].mean(),hours=mask.sum()/12))
        for st in ['neither','destination_only','origin_only','both']:
            sel=mask&(state==st)
            states.append(dict(quarter=str(q),direction=name,state=st,hours=sel.sum()/12,frequency_pct=sel.sum()/mask.sum()*100,spread_contribution=x[sel].sum()/mask.sum(),energy_contribution=e[sel].sum()/mask.sum(),scarcity_contribution=c[sel].sum()/mask.sum()))
    fp=ROOT/f'data/event_{key}_2y/screen_timeseries.parquet'
    f=pd.read_parquet(fp).set_index('time').MWFLOW.reindex(p.index)
    assert f.notna().all()
    for origin,dest,fl in [(a,b,f),(b,a,-f)]:
        d=p[dest]-p[origin]; fl=fl.clip(lower=0)
        gate=d.gt(0); eff=fl.where(gate,0); pos=d.clip(lower=0)
        actual=(eff*pos).mean(); naive=eff.mean()*pos.mean()
        flow_rows.append(dict(direction=f'{origin} to {dest}',hours=len(p)/12,positive_gross_proxy_dollars=(eff*pos).sum()/12,
           mean_effective_flow=eff.mean(),mean_positive_spread=pos.mean(),mean_product=actual,product_means=naive,covariance=actual-naive,
           tail_proxy_pct=100*(eff*pos).where((p[origin]>300)|(p[dest]>300),0).sum()/(eff*pos).sum()))
pd.DataFrame(spread_rows).to_csv(OUT/'historical_spread_decomposition.csv',index=False)
pd.DataFrame(states).to_csv(OUT/'historical_joint_regimes.csv',index=False)
pd.DataFrame(flow_rows).to_csv(OUT/'historical_flow_diagnostics.csv',index=False)
audit=dict(start_exclusive=str(START),end_inclusive=str(END),intervals=len(p),regions=list(p.columns),conflicting_prices=int(conflicts),
   price_identity_max_error=float(max(abs(p[r]-p[r].clip(upper=300)-(p[r]-300).clip(lower=0)).max() for r in p)),
   apc_flag_rows=int(raw.APCFLAG.ne(0).sum()),suspended_rows=int(raw.MARKETSUSPENDEDFLAG.ne(0).sum()),
   source_files=[dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths],
   caveat='Descriptive archived dispatch prices and flows. No independent settlement-price revision audit, losses, SRA allocation or forecast backtest.')
(OUT/'historical_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps(audit,indent=2))
print(pd.DataFrame(spread_rows).query('complete').round(3).to_string(index=False))
print(regional.query('complete and quarter == "2026Q2"').round(3).to_string(index=False))
print(pd.DataFrame(flow_rows).round(3).to_string(index=False))
