"""Training-frozen onset labels and incident-level advance-warning scoring."""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score,brier_score_loss,log_loss


def detect(capacity,train_start,train_end,percentile=.9,minimum=100,absolute=None):
    drop=capacity.shift(6)-capacity
    valid=capacity.notna().rolling(7,min_periods=7).sum().eq(7)
    history=drop.where(valid&drop.gt(0)&(drop.index>=pd.Timestamp(train_start))&(drop.index<pd.Timestamp(train_end)))
    pooled=float(history.quantile(percentile)) if history.count()>=minimum else np.nan
    thresholds={};fallback=[]
    for month in range(1,13):
        v=history[history.index.month==month].dropna()
        thresholds[month]=float(v.quantile(percentile)) if len(v)>=minimum else pooled
        if len(v)<minimum:fallback.append(month)
    cutoff=pd.Series(capacity.index.month,index=capacity.index).map(thresholds) if absolute is None else pd.Series(float(absolute),index=capacity.index)
    sharp=valid&drop.gt(0)&drop.ge(cutoff)
    onset=sharp&~sharp.shift(1,fill_value=False)&valid.shift(1,fill_value=False)
    return pd.DataFrame({'drop_mw':drop,'threshold':cutoff,'valid':valid&cutoff.notna(),'sharp':sharp,'onset':onset}),{'monthly_thresholds':thresholds,'fallback_months':fallback,'pooled':pooled,'absolute':absolute}


def window_label(onset,valid,origins,minimum=30,maximum=120):
    # Inclusive minimum and maximum lead. Exclude any window with an unknown observation.
    steps=range(max(1,minimum//5),maximum//5+1)
    values=pd.concat([onset.shift(-s).astype(float) for s in steps],axis=1)
    known=pd.concat([valid.shift(-s).eq(True) for s in steps],axis=1).all(axis=1)
    return values.max(axis=1).where(known).reindex(origins).to_numpy()


def incidents(detector):
    times=detector.index[detector.onset]
    if not len(times):return pd.DataFrame(columns=['time','last_onset','drop_mw'])
    group=pd.Series(times).diff().gt(pd.Timedelta(minutes=30)).cumsum().to_numpy()
    f=pd.DataFrame({'time':times,'group':group,'drop_mw':detector.loc[times,'drop_mw'].to_numpy()})
    return f.groupby('group',as_index=False).agg(time=('time','min'),last_onset=('time','max'),drop_mw=('drop_mw','max'))


def alarms(origins,probabilities,threshold,refractory=120):
    result=[];last=None
    for t,p in zip(origins,probabilities):
        if not np.isfinite(p) or p<=threshold:continue
        if last is None or t-last>=pd.Timedelta(minutes=refractory):result.append(t);last=t
    return pd.DatetimeIndex(result)


def match(origins,probabilities,threshold,events,minimum=30,maximum=120):
    predictions=alarms(origins,probabilities,threshold,maximum)
    if len(origins)==0:return {'incidents':0,'tp':0,'fp':0,'fn':0,'alarms':[],'leads':[],'matched_times':[]}
    # Score only incidents with at least one evaluated issue capable of warning in time.
    alltimes=pd.DatetimeIndex(events.time)
    oi=pd.DatetimeIndex(origins).asi8
    low=alltimes.asi8-pd.Timedelta(minutes=maximum).value;high=alltimes.asi8-pd.Timedelta(minutes=minimum).value
    eligible=np.searchsorted(oi,high,side='right')>np.searchsorted(oi,low,side='left')
    times=alltimes[eligible];matched=set();leads=[];records=[]
    for t in predictions:
        candidates=np.flatnonzero((times>=t+pd.Timedelta(minutes=minimum))&(times<=t+pd.Timedelta(minutes=maximum)))
        selected=next((int(i) for i in candidates if int(i) not in matched),None)
        if selected is not None:matched.add(selected);leads.append((times[selected]-t).total_seconds()/60)
        records.append({'time':str(t),'matched_event':str(times[selected]) if selected is not None else None})
    tp=len(matched);fp=len(predictions)-tp;fn=len(times)-tp
    days=max(len(np.unique(pd.DatetimeIndex(origins).date)),1)
    return {'incidents':len(times),'tp':tp,'fp':fp,'fn':fn,'recall':tp/len(times) if len(times) else None,
        'precision':tp/len(predictions) if len(predictions) else None,'false_alarms_per_day':fp/days,'days':days,
        'median_lead_minutes':float(np.median(leads)) if leads else None,'p10_lead_minutes':float(np.quantile(leads,.1)) if leads else None,
        'alarms':records,'leads':leads,'matched_times':[str(times[i]) for i in sorted(matched)]}


def tune_joint(items,budget=3):
    choices=[]
    for origins,p,events in items:
        thresholds=np.unique(np.r_[np.quantile(p[np.isfinite(p)],np.linspace(.05,.99,24)),1.0])
        choices.append([(float(t),match(origins,p,t,events)) for t in thresholds])
    best=None
    for a in choices[0]:
        for b in choices[1]:
            burden=a[1]['false_alarms_per_day']+b[1]['false_alarms_per_day']
            if burden>budget:continue
            rank=(a[1]['tp']+b[1]['tp'],-burden,a[0]+b[0])
            if best is None or rank>best[0]:best=(rank,[a[0],b[0]])
    return best[1] if best else [1.,1.]


def probability_score(y,p):
    good=np.isfinite(y)&np.isfinite(p);y=np.asarray(y)[good];p=np.clip(np.asarray(p)[good],1e-6,1-1e-6)
    if not len(y):return {'n':0}
    bins=[]
    for a,b in zip(np.linspace(0,1,11)[:-1],np.linspace(0,1,11)[1:]):
        mask=(p>=a)&(p<b)
        if mask.any():bins.append({'n':int(mask.sum()),'predicted':float(p[mask].mean()),'observed':float(y[mask].mean())})
    return {'n':len(y),'positives':int(y.sum()),'base_rate':float(y.mean()),'brier':float(brier_score_loss(y,p)),
            'log_loss':float(log_loss(y,p,labels=[0,1])),'average_precision':float(average_precision_score(y,p)) if y.sum() else None,'reliability':bins}


def incident_interval(result,replicates=500):
    # Resample incidents for recall and complete days for false-alarm burden.
    n=result['incidents'];rng=np.random.default_rng(741)
    if not n:return None
    recalls=rng.binomial(n,result['tp']/n,replicates)/n
    counts=np.zeros(result['days'])
    false=[pd.Timestamp(x['time']).normalize() for x in result['alarms'] if x['matched_event'] is None]
    if false:
        v=pd.Series(false).value_counts().to_numpy();counts[:len(v)]=v
    rates=np.array([rng.choice(counts,len(counts)).mean() for _ in range(replicates)])
    return {'recall_95':np.quantile(recalls,[.025,.975]).tolist(),'false_alarms_day_95':np.quantile(rates,[.025,.975]).tolist(),'method':'incident bootstrap recall; day bootstrap false alarms; does not eliminate regime dependence'}
