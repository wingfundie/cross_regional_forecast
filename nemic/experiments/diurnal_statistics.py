"""Paired chronological block inference for frozen historical policies."""
import json
import numpy as np
import pandas as pd
from .core import Store, load_config
from .diurnal_runner import CONFIG


def block_indices(n, block=7, replicates=2000, seed=741):
    if n < block:
        raise ValueError('Insufficient independent calendar support')
    rng=np.random.default_rng(seed)
    starts=rng.integers(0,n-block+1,(replicates,int(np.ceil(n/block))))
    return (starts[:,:,None]+np.arange(block)).reshape(replicates,-1)[:,:n]


def paired_improvement(frame, challenger, control, block=7):
    f=frame.assign(day=frame.origin.dt.normalize(),
        delta=abs(frame.actual-frame[control])-abs(frame.actual-frame[challenger]))
    # Calendar reindex keeps gaps visible rather than joining distant days together.
    daily=f.groupby('day').delta.agg(['sum','count'])
    daily=daily.reindex(pd.date_range(daily.index.min(),daily.index.max(),freq='D'),fill_value=0)
    if len(daily)<block:return {'status':'insufficient days'}
    ix=block_indices(len(daily),block)
    sums=daily['sum'].to_numpy();counts=daily['count'].to_numpy()
    denominator=counts[ix].sum(axis=1)
    valid=denominator>0
    draws=sums[ix].sum(axis=1)[valid]/denominator[valid]
    mean=sums.sum()/counts.sum()
    # Null-centred bootstrap, paired observations and identical blocks.
    null=((sums-mean*counts)[ix].sum(axis=1)[valid]/denominator[valid])
    p=(1+np.sum(null>=mean))/(1+len(null))
    return {'improvement_mw':float(mean),'ci_low':float(np.quantile(draws,.025)),
            'ci_high':float(np.quantile(draws,.975)),'p_one_sided':float(p),'block_days':block,'calendar_days':len(daily)}


def holm(values):
    values=np.asarray(values,dtype=float);order=np.argsort(values)
    adjusted=np.maximum.accumulate((len(values)-np.arange(len(values)))*values[order])
    result=np.empty(len(values));result[order]=np.minimum(adjusted,1.)
    return result


def model_confidence_set(frame,models,block=7,level=.9,replicates=2000):
    """Hansen-style sequential equal-predictive-ability elimination on daily losses."""
    f=frame.copy();f['day']=f.origin.dt.normalize()
    daily=pd.DataFrame({name:abs(f.actual-f[name]).groupby(f.day).mean() for name in models}).dropna()
    active=list(models);steps=[];indices=block_indices(len(daily),block,replicates)
    losses=daily.to_numpy()
    while len(active)>1:
        columns=[models.index(n) for n in active];a=losses[:,columns]
        differences=a[:,:,None]-a[:,None,:];means=differences.mean(axis=0)
        boot=differences[indices].mean(axis=1)-means
        se=boot.std(axis=0,ddof=1);scale=np.maximum(se,1e-12)
        observed=float(np.max(np.abs(means/scale)))
        simulated=np.max(np.abs(boot/scale[None,:,:]),axis=(1,2))
        p=float((1+np.sum(simulated>=observed))/(1+len(simulated)))
        worst=active[int(np.argmax(a.mean(axis=0)))]
        steps.append({'members':active.copy(),'p_equal_predictive_ability':p,'removed_if_rejected':worst})
        if p>1-level:break
        active.remove(worst)
    return {'level':level,'block_days':block,'members':active,'steps':steps,'calendar_days':len(daily),
        'method':'Sequential range statistic with centred moving-block bootstrap; development-only 90% model confidence set.'}


def run_statistics(config_path=CONFIG):
    c=load_config(config_path);store=Store(c);frames=[]
    for path in sorted((store.root/'diurnal').glob('*/band0/*tight/result.json')):
        r=json.loads(path.read_text())
        if r['fold']['protocol']!='rolling':continue
        f=pd.read_parquet(path.parent/'predictions.parquet')
        f['selected_policy']=f[r['winner']];f['target']=r['target'];frames.append(f)
    combined=pd.concat(frames,ignore_index=True)
    rows=[]
    for target,f in combined.groupby('target'):
        for control in ('persistence','T0_mae'):
            for block in (7,14):
                rows.append({'target':target,'control':control,**paired_improvement(f,'selected_policy',control,block)})
    primary=[r for r in rows if r.get('block_days')==7]
    for r,p in zip(primary,holm([r['p_one_sided'] for r in primary])):
        # Keep the historical key for cached VNI report compatibility while
        # exposing a connector-neutral field for all subsequent campaigns.
        r['holm_p_family']=float(p)
        r['holm_p_vni_family']=float(p)
    common=['persistence','seasonal_daily','seasonal_weekly']+[f'T{i}_mae' for i in range(7)]
    common=[name for name in common if all(name in f.columns for f in frames)]
    mcs=[]
    for target,f in combined.groupby('target'):
        for block in (7,14):mcs.append({'target':target,**model_confidence_set(f,common,block)})
    connector=c['connectors'][0]
    store.json(store.root/'statistics.json',{'comparisons':rows,
        'mcs90':mcs,
        'connector':connector['name'],
        'multiplicity':f"{connector['name']}-only execution: four primary hypotheses (two directions × two controls); other connectors are not silently treated as tested",
        'claim':'Development-only bootstrap evidence; no independent confirmation',
        'control_limitations':'T0 is the corrected shared full-feature ridge. Full legacy candidate/blend-policy bridge must be reported separately.'})


if __name__=='__main__':run_statistics()
