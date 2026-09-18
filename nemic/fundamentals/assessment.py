"""Conservative, multi-cell paired acceptance audit; missing evidence never passes."""
import json
import numpy as np
import pandas as pd

from .tracking import atomic


def holm(pvalues):
    p=np.asarray(pvalues,dtype=float);order=np.argsort(p);adjusted=np.empty(len(p));last=0.
    for rank,index in enumerate(order):
        last=max(last,min(1.,p[index]*(len(p)-rank)));adjusted[index]=last
    return adjusted


def block_evidence(frame,block_days,skill=.02,overstatement_margin=.02,repeats=2000):
    f=frame.copy();e=f.point-f.actual;b=f.network-f.actual
    f['skill_delta']=abs(e)-(1-skill)*abs(b)
    f['overstatement_delta']=e.clip(lower=0)-(1+overstatement_margin)*b.clip(lower=0)
    # First average leads within each origin, then origins within calendar days.
    daily=f.groupby('origin')[['skill_delta','overstatement_delta']].mean()
    daily=daily.groupby(daily.index.normalize()).mean()
    blocks=daily.groupby((daily.index-daily.index.min()).days//block_days).mean()
    if len(blocks)<4:return dict(status='insufficient_blocks',blocks=len(blocks),days=len(daily),pvalue=1.)
    values=blocks.to_numpy();rng=np.random.default_rng(741)
    samples=values[rng.integers(0,len(values),size=(repeats,len(values)))].mean(axis=1)
    observed=values.mean(axis=0)
    pvalue=(1+np.sum(samples[:,0]-observed[0]<=observed[0]))/(repeats+1)
    return dict(status='measured',blocks=len(blocks),days=len(daily),block_days=block_days,pvalue=float(pvalue),
                skill_delta=float(observed[0]),skill_ci95=np.quantile(samples[:,0],[.025,.975]).tolist(),
                overstatement_upper95=float(np.quantile(samples[:,1],.95)))


def assess(ledger):
    grouped={}
    for path in (ledger.data/'train').glob('**/result.json'):
        result=json.loads(path.read_text())
        key=(result['connector'],result['target'],result['band'],result['information_track'])
        grouped.setdefault(key,[]).append(path.parent/'predictions.parquet')
    rows=[]
    for key,paths in grouped.items():
        f=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
        if f.duplicated(['origin','lead']).any():raise ValueError('Overlapping evaluation predictions in acceptance audit')
        evidence=[block_evidence(f,b,ledger.c['acceptance']['mae_skill'],ledger.c['acceptance']['overstatement_margin']) for b in (7,14)]
        lo,hi=ledger.c['bands'][key[2]]
        complete_leads=all(set(g.lead)==set(range(lo,hi+1)) for _,g in f.groupby('origin'))
        rows.append(dict(connector=key[0],target=key[1],band=key[2],cohort=key[3],folds=len(paths),
            evidence=evidence,pvalue=max(e['pvalue'] for e in evidence),full_band_leads=complete_leads,
            evaluation_days=int(f.origin.dt.normalize().nunique()),promotion=False,
            outstanding=['Joint-direction incident recall/false-alert and power audit','Coal daily-boundary and publication-delay sensitivities','Historical network/source receipt validation']+
                        ([] if complete_leads else ['Exhaustive 336-lead evaluation'])))
    adjusted=holm([r['pvalue'] for r in rows])
    for row,p in zip(rows,adjusted):
        row['holm_pvalue']=float(p)
        row['point_skill_supported']=bool(p<.05 and row['evaluation_days']>=7*ledger.c['acceptance']['min_evaluation_weeks'])
        row['overstatement_supported']=row['target']=='flow' or all(e.get('overstatement_upper95',float('inf'))<=0 for e in row['evidence'])
        row['decision']='inconclusive_pending_acceptance_gates'
    output=ledger.data/'assessment/results.json';atomic(output,json.dumps(rows,indent=2))
    ledger.record('assessment/point_audit','completed' if rows else 'ready',
                  'Paired point audit complete; remaining acceptance gates explicitly unresolved' if rows else 'No measured model cells yet',[output] if rows else [])
    return output
