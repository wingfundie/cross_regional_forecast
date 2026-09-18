"""Training-only chronological reduction with explicit interaction hierarchy."""
from __future__ import annotations
import time

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.pipeline import make_pipeline
import lightgbm as lgb


def parent_closure(columns, parents):
    selected=set(columns)
    for _ in range(len(parents)+1):
        extra={p for col in selected for p in parents.get(col,[])}-selected
        if not extra:return selected
        selected.update(extra)
    raise ValueError('Interaction hierarchy did not converge')


def basic_filter(x, parents=None):
    """Fit on inner training rows only; restore usable parents of interactions."""
    rejected={};keep=[]
    for col in x:
        if x[col].notna().mean()<.2 and not any(s in col for s in ('missing','coverage','quality')):
            rejected[col]='more than 80% missing'
        elif x[col].nunique(dropna=True)<=1:rejected[col]='constant or empty'
        else:keep.append(col)
    # Exact duplicates plus near-perfect correlation among main effects only.
    main=[c for c in keep if not c.startswith('ix__') and c not in (parents or {})]
    corr=x[main].corr(method='spearman').abs() if main else pd.DataFrame()
    redundant=set()
    for j,col in enumerate(main):
        previous=[c for c in main[:j] if c not in redundant]
        if previous and corr.loc[col,previous].max()>.98:
            redundant.add(col);rejected[col]='abs Spearman > 0.98 with earlier main effect'
    keep=[c for c in keep if c not in redundant]
    closure=parent_closure(keep,parents or {})
    for col in closure-set(keep):
        if col in x and x[col].notna().any():keep.append(col);rejected.pop(col,None)
    return keep,rejected


def ridge(alpha=100.):
    return make_pipeline(SimpleImputer(keep_empty_features=True),StandardScaler(),Ridge(alpha=alpha))


def chronological_splits(meta):
    last=meta.origin.max().normalize();splits=[]
    for days in (28,14):
        start=last-pd.Timedelta(days=days);end=start+pd.Timedelta(days=14)
        tr=(meta.delivery+pd.Timedelta(minutes=30)<start)
        va=(meta.origin>=start)&(meta.delivery+pd.Timedelta(minutes=30)<end)
        if tr.sum()>=100 and va.sum()>=30:splits.append((tr.to_numpy(),va.to_numpy()))
    if len(splits)<2:raise ValueError('Insufficient mature chronological inner partitions')
    return splits


def block_loss(y,p,meta):
    d=pd.DataFrame({'day':meta.origin.dt.normalize().to_numpy(),'loss':abs(y-p)})
    daily=d.groupby('day').loss.mean()
    if not len(daily):return np.nan,np.nan
    blocks=daily.groupby(np.arange(len(daily))//7).mean()
    return float(daily.mean()),float(blocks.std(ddof=1)/np.sqrt(len(blocks))) if len(blocks)>1 else 0.


def select(x,y,meta,schema):
    """No outer evaluation rows or labels accepted by this API."""
    start=time.monotonic();splits=chronological_splits(meta);parents=schema.get('parents',{})
    methods=('correlation','elastic','permutation');records=[];fold_rankings={}
    for fold,(tr,va) in enumerate(splits):
        cols,rejected=basic_filter(x.loc[tr],parents)
        if not cols:raise ValueError('No varying training features')
        groups={}
        for c in cols:groups.setdefault(schema.get('groups',{}).get(c,'network'),[]).append(c)
        # Interactions and parents stay together in nested candidate sets.
        for method in methods:
            rankings={}
            if method=='correlation':
                for group,names in groups.items():
                    scores=[abs(pd.Series(x.loc[tr,c].to_numpy()).corr(pd.Series(y[tr]),method='spearman')) for c in names]
                    rankings[group]=float(np.nanmax(scores)) if np.isfinite(scores).any() else 0.
            elif method=='elastic':
                model=make_pipeline(SimpleImputer(keep_empty_features=True),StandardScaler(),ElasticNet(alpha=.1,l1_ratio=.5,max_iter=3000,random_state=741))
                model.fit(x.loc[tr,cols],y[tr]);coef=dict(zip(cols,abs(model[-1].coef_)))
                rankings={g:float(sum(coef[c] for c in names)) for g,names in groups.items()}
            else:
                model=lgb.LGBMRegressor(n_estimators=60,num_leaves=7,objective='regression_l1',n_jobs=2,verbosity=-1,random_state=741)
                model.fit(x.loc[tr,cols],y[tr]);baseline=np.mean(abs(y[va]-model.predict(x.loc[va,cols])))
                validation=x.loc[va,cols].reset_index(drop=True)
                # Shift entire day blocks coherently, preserving within-day shape.
                days=meta.loc[va,'origin'].dt.normalize().reset_index(drop=True)
                unique=list(days.unique());shift=max(1,len(unique)//2)
                blocks=[np.flatnonzero(days.eq(d)) for d in unique]
                permutation=np.concatenate(blocks[shift:]+blocks[:shift])
                for group,names in groups.items():
                    z=validation.copy();z[names]=validation.iloc[permutation][names].to_numpy()
                    rankings[group]=float(np.mean(abs(y[va]-model.predict(z)))-baseline)
            order=sorted(rankings,key=lambda g:(-rankings[g],g))
            fold_rankings[f'{fold}/{method}']=dict(rankings=rankings,rejected=rejected)
            for fraction in (.25,.5,.75,1.):
                top=order[:max(1,int(np.ceil(len(order)*fraction)))]
                selected=parent_closure([c for g in top for c in groups[g]],parents)
                selected=[c for c in x if c in selected]
                model=ridge();model.fit(x.loc[tr,selected],y[tr]);pred=model.predict(x.loc[va,selected])
                loss,se=block_loss(y[va],pred,meta.loc[va])
                records.append(dict(fold=fold,method=method,fraction=fraction,mae=loss,block_se=se,n_features=len(selected),columns=selected))
    scores=pd.DataFrame([{k:v for k,v in r.items() if k!='columns'} for r in records]).groupby(['method','fraction'],as_index=False).agg(mae=('mae','mean'),se=('block_se','mean'),n_features=('n_features','mean'))
    best=scores.loc[scores.mae.idxmin()];eligible=scores[scores.mae<=best.mae+best.se]
    winner=eligible.sort_values(['n_features','mae','method']).iloc[0]
    # Union across the inner training fits retains stable parent closure and
    # avoids choosing by outer labels; final estimator fills on outer train only.
    selected=set().union(*(set(r['columns']) for r in records if r['method']==winner['method'] and r['fraction']==winner['fraction']))
    selected=[c for c in x if c in parent_closure(selected,parents)]
    return selected,dict(method=winner['method'],fraction=float(winner['fraction']),columns=selected,raw_count=x.shape[1],
                         selected_count=len(selected),inner_results=records,rankings=fold_rankings,seconds=time.monotonic()-start)
