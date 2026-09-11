"""Exhaustive 30-minute origins × 336 horizons, streamed to disk."""
import json, gc
from collections import defaultdict
import numpy as np
import pandas as pd
import joblib
from .common import *
from .model import Design, IDS, TARGETS, BANDS, band, predict, chosen
from .prepare import TEST_START,END,season

METHODS=['persistence','seasonal','fundamentals','weather','availability','network','selected']

def score_rows(frame,d,aggregate,daily):
    i=int(frame.ic_code.iloc[0]);k=IDS[i]
    bs=frame.band.to_numpy(); vi=frame.valid_idx.to_numpy()
    seasons=season(d.time[vi]);origin_days=d.time[frame.origin_idx].floor('D')
    stress=(frame.export_actual.to_numpy()<d.threshold[i,vi,0])|(frame.import_actual.to_numpy()<d.threshold[i,vi,1])
    intervention=d.targets[k].intervention.to_numpy()[vi]>0
    for j,t in enumerate(TARGETS):
      actual=frame[t+'_actual'].to_numpy()
      for b in range(4):
       mask=bs==b
       slices={'all':mask,'restricted':mask&stress,'intervention':mask&intervention}
       slices.update({['summer','autumn','winter','spring'][s]:mask&(seasons==s) for s in range(4)})
       for method in METHODS:
        pred=frame[t+('_p50' if method=='selected' else '_'+method)].to_numpy()
        err=pred-actual
        for label,selection in slices.items():
         good=selection&np.isfinite(err)
         if not good.any():continue
         key=(k,t,b,method,label)
         a=aggregate[key]; a['n']+=int(good.sum());a['ae']+=float(np.abs(err[good]).sum());a['se']+=float((err[good]**2).sum());a['bias']+=float(err[good].sum())
         if method=='selected':
            low=frame[t+'_p10'].to_numpy();high=frame[t+'_p90'].to_numpy()
            a['covered']+=int(((actual>=low)&(actual<=high)&good).sum());a['width']+=float((high-low)[good].sum())
            for q,col in [(.1,'p10'),(.5,'p50'),(.9,'p90')]:
                e=actual[good]-frame.loc[good,t+'_'+col].to_numpy()
                a['pinball']+=float(np.maximum(q*e,(q-1)*e).sum())/3
            if t!='flow':
                threshold=d.threshold[i,vi,0 if t.startswith('export') else 1]
                good=good&np.isfinite(threshold)
                yes=actual<threshold; p=frame[t+'_probability'].to_numpy(); flag=p>=frame[t+'_cutoff'].to_numpy()
                a['event_n']+=int(good.sum());a['events']+=int((yes&good).sum())
                a['tp']+=int((yes&flag&good).sum());a['fp']+=int((~yes&flag&good).sum());a['fn']+=int((yes&~flag&good).sum());a['tn']+=int((~yes&~flag&good).sum())
                a['brier']+=float(((p[good]-yes[good])**2).sum())
       # Keep paired daily absolute-error sums for a seven-day block bootstrap.
       for day in pd.unique(origin_days[mask]):
        good=mask&(origin_days==day)&np.isfinite(actual)
        if not good.any():continue
        key=(k,t,b,str(pd.Timestamp(day).date()))
        a=daily[key]
        for method in ['selected','persistence','seasonal']:
            p=frame[t+('_p50' if method=='selected' else '_'+method)].to_numpy()
            ok=good&np.isfinite(p)
            a[method+'_ae']+=float(np.abs(p[ok]-actual[ok]).sum());a[method+'_n']+=int(ok.sum())

def run():
    d=Design();cache=joblib.load(MODELS/'conditional_cache.joblib')
    models=[joblib.load(MODELS/f'network_{t}.joblib') for t in TARGETS]
    configs=json.loads((MODELS/'selection.json').read_text())
    aggregate=defaultdict(lambda:defaultdict(float));daily=defaultdict(lambda:defaultdict(float))
    lo=d.time.searchsorted(TEST_START);hi=d.time.searchsorted(END,side='right')
    outdir=RESULTS/'predictions';outdir.mkdir(exist_ok=True)
    import hashlib
    signature={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [MODELS/'selection.json',PROCESSED/'drivers.parquet',PROCESSED/'targets.parquet',ROOT/'nemic/model.py']+list(MODELS.glob('network_*.joblib'))}
    sigpath=outdir/'run_signature.json'
    if sigpath.exists() and json.loads(sigpath.read_text())!=signature:
        raise ValueError('Existing test predictions belong to different data/models. Archive them before a new test run.')
    dump(sigpath,signature)
    for i,k in enumerate(IDS):
      for begin in range(lo,hi-1,336):
        path=outdir/f'{k}_{begin}.parquet'
        if path.exists():frame=pd.read_parquet(path)
        else:
            origins=np.arange(begin,min(begin+336,hi-1))
            oi=np.repeat(origins,336);h=np.tile(np.arange(1,337),len(origins))
            ok=oi+h<hi;oi=oi[ok];h=h[ok];ci=np.full(len(h),i,dtype='int8');vi=oi+h
            pred=predict(d,ci,oi,h,cache,models);sel=chosen(d,ci,vi,h,pred,configs)
            frame=pd.DataFrame({'ic_code':ci,'origin_idx':oi.astype('int32'),'valid_idx':vi.astype('int32'),'h':h.astype('int16'),'band':band(h)})
            for j,t in enumerate(TARGETS):
                frame[t+'_actual']=d.y[ci,vi,j]
                for m,a in pred.items():frame[t+'_'+m]=a[:,j].astype('float32')
                for q,a in sel[t].items():
                    if t=='flow' and q in ['probability','cutoff']:continue
                    frame[t+'_'+q]=a
            frame.to_parquet(path,index=False,compression='zstd')
            del pred,sel;gc.collect()
        score_rows(frame,d,aggregate,daily)
        print('TEST',k,str(d.time[begin]),len(frame),'origin/lead pairs',flush=True)
        del frame;gc.collect()
    rows=[]
    for (k,t,b,m,s),a in aggregate.items():
        n=a['n'];row=dict(ic=k,target=t,band=b,model=m,slice=s,n=int(n),mae=a['ae']/n,rmse=np.sqrt(a['se']/n),bias=a['bias']/n)
        if m=='selected':
            row.update(coverage80=a['covered']/n,width80=a['width']/n,pinball=a['pinball']/n)
            if t!='flow':
                tp,fp,fn=a['tp'],a['fp'],a['fn']
                row.update(events=int(a['events']),tp=int(tp),fp=int(fp),fn=int(fn),tn=int(a['tn']),
                    recall=tp/(tp+fn) if tp+fn else np.nan,precision=tp/(tp+fp) if tp+fp else np.nan,
                    f2=5*tp/(5*tp+4*fn+fp) if 5*tp+4*fn+fp else np.nan,
                    brier=a['brier']/a['event_n'] if a['event_n'] else np.nan)
        rows.append(row)
    pd.DataFrame(rows).to_csv(RESULTS/'scores.csv',index=False)
    days=pd.DataFrame([dict(ic=k,target=t,band=b,date=day,**a) for (k,t,b,day),a in daily.items()])
    days.to_csv(RESULTS/'daily_errors.csv',index=False)
    bootstrap(days)
    dump(RESULTS/'test_proof.json',dict(start=TEST_START,end=END,origin_step_minutes=30,
       horizons=list(range(1,337)),connectors=IDS,targets=TARGETS,files=len(list(outdir.glob('*.parquet'))),
       selection_sha256=__import__('hashlib').sha256((MODELS/'selection.json').read_bytes()).hexdigest(),
       note='All valid half-hour origin/horizon pairs; end-of-test origins have truncated horizons. Models frozen before test.'))
    print('EXHAUSTIVE BACKTEST COMPLETE',flush=True)

def bootstrap(days):
    rng=np.random.default_rng(741);rows=[]
    for (k,t,b),g in days.groupby(['ic','target','band']):
        g=g.sort_values('date');n=len(g)
        for baseline in ['persistence','seasonal']:
            arr=g[['selected_ae','selected_n',baseline+'_ae',baseline+'_n']].to_numpy()
            draws=[]
            for _ in range(400):
                starts=rng.integers(0,max(1,n-6),int(np.ceil(n/7)))
                idx=np.concatenate([np.arange(s,min(s+7,n)) for s in starts])[:n]
                sums=arr[idx].sum(axis=0)
                draws.append(sums[2]/sums[3]-sums[0]/sums[1])
            rows.append(dict(ic=k,target=t,band=b,baseline=baseline,improvement_mw=float(np.mean(draws)),
                             ci_low=float(np.quantile(draws,.025)),ci_high=float(np.quantile(draws,.975)),block_days=7))
    pd.DataFrame(rows).to_csv(RESULTS/'skill_confidence.csv',index=False)

if __name__=='__main__':run()
