"""Issue-vintage AEMO benchmarks and pooled linear transfer experiments."""
import json
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .core import ROOT,Store,fingerprint
from .validation import folds,pairs,regression_score
from .data import connector_data,base_frame,design
from .models import select


def aemo(c):
    store=Store(c);path=ROOT/'results/aemo_vintages.parquet'
    if not path.exists():return {'status':'unavailable','reason':'Original issue-vintage file missing'}
    a=pd.read_parquet(path)
    if (pd.to_datetime(a.issued)>pd.to_datetime(a.origin)).any():raise ValueError('AEMO issue after forecast origin')
    targets=pd.read_parquet(ROOT/'data/processed/targets.parquet');rows=[];excluded=[]
    for ic in c['connectors']:
        f=a[a.INTERCONNECTORID.eq(ic['id'])].copy()
        y=targets[targets.ic.eq(ic['id'])].set_index('time')
        for fold in folds(c):
            for b,(lo,hi) in enumerate(c['bands']):
                sub=f[f.h.between(lo,hi)&f.h.isin(c['leads'])].copy()
                if sub.empty:excluded.append({'ic':ic['name'],'fold':fold.name,'band':b,'reason':'No original AEMO issues at these leads'});continue
                mm=fold.masks(pd.DatetimeIndex(sub.origin),sub.h.to_numpy()*30)
                for t in ['flow','export','import']:
                    actual=y[t].reindex(pd.DatetimeIndex(sub.time)).to_numpy();pred=sub['aemo_'+t].to_numpy()
                    good=np.isfinite(actual)&np.isfinite(pred);te=mm['evaluate']&good;tr=mm['train']&good
                    if not te.any():continue
                    common={'ic':ic['name'],'protocol':fold.protocol,'fold':fold.name,'band':b,'target':t,'track':'operational_benchmark','timing':'Original file issue + assumed 1-minute ingestion buffer; target is half-hour dispatch aggregate'}
                    rows.append({**common,'model':'aemo_original',**regression_score(actual[te],pred[te])})
                    if tr.sum()>=100:
                        bias=float(np.mean(actual[tr]-pred[tr]));rows.append({**common,'model':'aemo_bias_corrected','bias_correction':bias,'training_pairs':int(tr.sum()),**regression_score(actual[te],pred[te]+bias)})
                    else:excluded.append({**common,'model':'aemo_bias_corrected','reason':'Insufficient AEMO vintage history preceding training cutoff'})
    result={'scores':rows,'unavailable':excluded,'claim':'Operational-input benchmark with explicit ingestion assumption; not complete per-source network-vintage validation'}
    store.json(store.root/'aemo_benchmark.json',result);return result


def pooled(c,inv):
    store=Store(c);ident='pooled';fp=fingerprint([inv['fingerprint'],ident]);out=store.root/'pooled.json'
    if store.valid(ident,fp):return
    datasets=[]
    for ic in c['connectors']:
        d=connector_data(c,ic);d['base']=base_frame(d);datasets.append(d)
    rows=[]
    with threadpool_limits(limits=2):
        for fold in folds(c):
            for b,(lo,hi) in enumerate(c['bands']):
                leads=[h for h in c['leads'] if lo<=h<=hi];train=[];evaluation=[];info=[]
                for j,d in enumerate(datasets):
                    ot,ht=pairs(d['y'].index,fold,leads,True);oe,he=pairs(d['y'].index,fold,leads)
                    xt=design(d,ot,ht,'full');xe=design(d,oe,he,'full')
                    xt['connector_code']=j;xe['connector_code']=j
                    train.append(xt);evaluation.append(xe);info.append((ot,ht,oe,he,fold.masks(d['y'].index[oe],he*30)))
                tx=pd.concat(train,ignore_index=True);ex=pd.concat(evaluation,ignore_index=True)
                for target in c['targets']:
                    yt=[];yv=[];scales=[];anchors=[];masks=[]
                    for d,(ot,ht,oe,he,mm) in zip(datasets,info):
                        y=d['y'][target].to_numpy();anchor=y[oe-1];r=y[ot+ht]-y[ot-1];scale=max(float(np.nanstd(r)),1)
                        yt.append(r/scale);yv.append((y[oe+he]-anchor)/scale);scales.append(scale);anchors.append(anchor);masks.append(mm)
                    tr_y=np.concatenate(yt);ev_y=np.concatenate(yv);tr=np.isfinite(tr_y)
                    va=np.concatenate([m['select'] for m in masks])&np.isfinite(ev_y)
                    if tr.sum()<500 or va.sum()<100:continue
                    model,settings=select('ridge',tx.loc[tr],tr_y[tr],ex.loc[va],ev_y[va],c)
                    p=model.predict(ex);start=0
                    for j,(d,meta,scale,anchor) in enumerate(zip(datasets,info,scales,anchors)):
                        ot,ht,oe,he,mm=meta;n=len(oe);prediction=p[start:start+n]*scale+anchor;start+=n
                        actual=d['y'][target].to_numpy()[oe+he];te=mm['evaluate']
                        rows.append({'ic':d['ic']['name'],'protocol':fold.protocol,'fold':fold.name,'band':b,'target':target,'model':'pooled_ridge_full','track':'retrospective','settings':settings,**regression_score(actual[te],prediction[te],anchor[te])})
                store.json(out,{'scores':rows,'complete':False});print('pooled',fold.name,b,'done',flush=True)
    store.json(out,{'scores':rows,'complete':True,'normalisation':'Per-connector training residual standard deviation; validation uses pooled normalised MAE','comparison':'Same full state/pressure feature block as connector-specific ridge_full; transfer challenger only'})
    store.complete(ident,fp,out)
