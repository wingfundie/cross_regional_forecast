"""Retrospective diagnostic on a BSP workbook published after the experiment."""
from pathlib import Path
import io
import json
import sys

import pandas as pd
from openpyxl import load_workbook

out=Path(__file__).resolve().parent
sys.path.insert(0,str(out.parents[2]))
from scripts.rhs_sydney_sources import BSP,fetch

raw,meta=fetch(BSP)
book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
rows=iter(book['Avg'].values)
col=next(rows).index('TOT_TX')
trace={pd.Timestamp(r[0]):float(r[col]) for r in rows
       if str(r[0]).startswith('2026-02') and r[col] is not None}
book.close()
assert len(trace)==28*48
obs=pd.read_csv(out/'observed_inputs.csv',parse_dates=['end'])
obs['slot']=obs.end.dt.ceil('30min')
training=obs[obs.end.dt.day.between(9,15)].groupby('slot').nsw.agg(['mean','size'])
training=training[training['size'].eq(6)]
assert len(training)==28
fc=pd.read_csv(out/'forecast_inputs.csv',parse_dates=['end'])
fc=fc[fc.end.dt.day.isin([23,25,28])].groupby(['kind',fc.end.dt.ceil('30min')]).nsw.mean()
scored=[]
for label,minutes in [('Workbook label at period end',0),('Workbook label at period start',-30)]:
    offset=pd.Timedelta(minutes=minutes)
    train=training.assign(value=[trace[t+offset] for t in training.index])
    for (kind,slot),regional in fc.items():
        same=train[train.index.time==slot.time()]
        for method,estimate in [('Clock mean',same.value.mean()),
                ('Fixed electrical share',regional*train.value.sum()/train['mean'].sum()),
                ('Clock electrical share',regional*same.value.sum()/same['mean'].sum())]:
            scored.append(dict(alignment=label,kind=kind,slot=slot,method=method,estimate=estimate,
                               raw_site_value=trace[slot+offset],abs_error=abs(estimate-trace[slot+offset])))
df=pd.DataFrame(scored)
df.to_csv(out/'sydney_west_predictions.csv',index=False)
m=df.groupby(['alignment','kind','method']).abs_error.agg(n='size',mae='mean')
assert m.n.eq(12).all()
m.to_csv(out/'sydney_west_scores.csv')
(out/'sydney_west_source.json').write_text(json.dumps(meta,indent=2))
print(m)
