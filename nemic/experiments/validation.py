"""Chronological partitions, point scores and paired uncertainty."""
from dataclasses import dataclass,asdict
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class Fold:
    name:str
    protocol:str
    train_start:str
    train_end:str
    select_end:str
    calibrate_end:str
    alert_end:str
    evaluate_end:str

    def bounds(self):
        return [(pd.Timestamp(a),pd.Timestamp(b)) for a,b in zip([self.train_start,self.train_end,self.select_end,self.calibrate_end,self.alert_end],[self.train_end,self.select_end,self.calibrate_end,self.alert_end,self.evaluate_end])]

    def masks(self,index,horizon):
        end=index+pd.to_timedelta(horizon,unit='min')
        return {name:np.asarray((index>=a)&(end<b)) for name,(a,b) in zip(['train','select','calibrate','alert','evaluate'],self.bounds())}

    def dict(self):return asdict(self)


def folds(c):
    result=[]
    if 'fixed' in c['protocols']:result.append(Fold('fixed','fixed',c['start'],'2025-09-01','2025-12-01','2026-02-01','2026-03-01',c['end']))
    if 'rolling' in c['protocols']:
        for t in pd.date_range('2025-09-01','2026-08-01',freq='MS'):
            result.append(Fold(str(t.date())[:7],'rolling',c['start'],str((t-pd.DateOffset(months=3)).date()),str((t-pd.DateOffset(months=2)).date()),str((t-pd.DateOffset(months=1)).date()),str(t.date()),str((t+pd.DateOffset(months=1)).date())))
    return result


def pairs(index,fold,leads,training=False,seed=741):
    origin=np.arange(len(index))
    if training:
        rng=np.random.default_rng(seed);h=rng.choice(leads,len(origin));m=fold.masks(index,h*30)['train']
        return origin[m],h[m]
    o=np.repeat(origin,len(leads));h=np.tile(leads,len(origin))
    good=(o+h<len(index))&(index[o]>=pd.Timestamp(fold.train_end))&(index[o]+pd.to_timedelta(h*30,unit='min')<pd.Timestamp(fold.evaluate_end))
    return o[good],h[good]


def regression_score(actual,pred,reference=None):
    m=np.isfinite(actual)&np.isfinite(pred)
    y=np.asarray(actual)[m];p=np.asarray(pred)[m]
    if len(y)==0:return {'n':0}
    e=p-y;r={'n':len(y),'mae':float(np.abs(e).mean()),'rmse':float(np.sqrt((e*e).mean())),'bias':float(e.mean()),'p95_absolute_error':float(np.quantile(np.abs(e),.95))}
    for band in [0,25,50]:
        z=np.abs(y)>band;r[f'sign_accuracy_{band}']=float((np.sign(y[z])==np.sign(p[z])).mean()) if z.any() else None
    if reference is not None:r['reference_mae']=float(np.abs(y-np.asarray(reference)[m]).mean())
    return r


def paired_interval(y,p,reference,dates,replicates=300):
    good=np.isfinite(y)&np.isfinite(p)&np.isfinite(reference)
    a=pd.DataFrame({'date':pd.DatetimeIndex(dates)[good].normalize(),'delta':np.abs(y[good]-reference[good])-np.abs(y[good]-p[good])}).groupby('date').delta.agg(['sum','count']).to_numpy()
    n=len(a)
    if n<7:return None
    rng=np.random.default_rng(741);values=[]
    for _ in range(replicates):
        ix=np.concatenate([np.arange(s,s+7) for s in rng.integers(0,n-6,int(np.ceil(n/7)))])[:n]
        b=a[ix];values.append(b[:,0].sum()/b[:,1].sum())
    return np.quantile(values,[.025,.975]).tolist()


def interval_score(y,quantiles,levels):
    y=np.asarray(y);q=np.asarray(quantiles);valid=np.isfinite(y)&np.isfinite(q).all(axis=1)
    y=y[valid];q=np.sort(q[valid],axis=1)
    if not len(y):return {'n':0}
    error=y[:,None]-q;levels=np.asarray(levels)
    result={'n':len(y),'pinball':float(np.maximum(levels*error,(levels-1)*error).mean())}
    scores=[]
    for lo,hi,coverage in [(0,6,.95),(1,5,.8),(2,4,.5)]:
        a=1-coverage;width=q[:,hi]-q[:,lo]
        score=width+2/a*np.maximum(q[:,lo]-y,0)+2/a*np.maximum(y-q[:,hi],0)
        result[f'coverage_{int(coverage*100)}']=float(((y>=q[:,lo])&(y<=q[:,hi])).mean())
        result[f'width_{int(coverage*100)}']=float(width.mean());scores.append(a/2*score)
    result['wis']=float((.5*np.abs(y-q[:,3])+np.sum(scores,axis=0)).mean()/3.5)
    return result
