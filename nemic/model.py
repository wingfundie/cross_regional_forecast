"""Direct multi-horizon boosting with chronological selection and calibration."""
import json, gc, hashlib
import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
from .common import *
from .prepare import START, END, TRAIN_END, TEST_START

LEADS=np.array([1,2,4,8,12,24,48,72,96,144,192,240,288,336],dtype=int)
BANDS=['0–6h','6–24h','Days 2–3','Days 4–7']
def band(h): return np.select([h<=12,h<=48,h<=144],[0,1,2],default=3).astype('int8')
IDS=list(IC)

class Design:
    def __init__(self):
        self.drivers=pd.read_parquet(PROCESSED/'drivers.parquet').sort_index()
        self.time=self.drivers.index
        t=pd.read_parquet(PROCESSED/'targets.parquet')
        self.targets={k:g.set_index('time').reindex(self.time) for k,g in t.groupby('ic')}
        cal=['hour_sin','hour_cos','year_sin','year_cos','weekday','trend_days']
        base=[c for c in self.drivers if c.endswith(('__demand','__wind','__solar','__rooftop','__residual_demand'))]+cal
        weather=[c for c in self.drivers if any('__'+v in c for v in ['temperature_2m','wind_speed_100m','shortwave_radiation','cloud_cover','relative_humidity_2m'])]
        self.base_cols=base; self.weather_cols=base+weather
        self.future=self.drivers[self.weather_cols].to_numpy(dtype='float32')
        self.available=self.future.copy()
        for region in REGIONS:
            for fuel in ['wind','solar']:
                self.available[:,self.weather_cols.index(region+'__'+fuel)]=self.drivers[region+'__'+fuel+'_available']
            self.available[:,self.weather_cols.index(region+'__residual_demand')]=self.drivers[region+'__demand']-self.drivers[region+'__wind_available']-self.drivers[region+'__solar_available']
        self.y=np.stack([self.targets[k][TARGETS].to_numpy(dtype='float32') for k in IDS])
        self.published=np.stack([pd.to_datetime(self.targets[k].lastchanged).to_numpy() for k in IDS])
        self.threshold=np.stack([self.targets[k][['export_threshold','import_threshold']].to_numpy(dtype='float32') for k in IDS])
        self.scale=np.ones((6,5),dtype='float32')
        train=self.time<=TRAIN_END
        for i in range(6):
            self.scale[i]=np.maximum(np.nanstd(self.y[i,train],axis=0),10)
        self.state=[]; self.state_names=[]; self.encoders={}
        statecols=['export_network','import_network','intervention','violation']
        for i,k in enumerate(IDS):
            g=self.targets[k]
            s=g[statecols].to_numpy(dtype='float32')
            for c in ['export_setter','import_setter']:
                vals=sorted(g.loc[train,c].dropna().unique())
                enc={v:j for j,v in enumerate(vals)}
                self.encoders[k+'__'+c]=enc
                s=np.column_stack([s,g[c].map(enc).fillna(-1).to_numpy(dtype='float32')])
            self.state.append(s)
        self.state=np.stack(self.state)
        self.network_cols=self.weather_cols+['ic','lead_halfhours','log_lead']
        self.network_cols += [f'lag{lag}_{target}' for lag in [1,48,336] for target in TARGETS]
        self.network_cols += statecols+['export_setter','import_setter']
        self.network_cols += ['origin_'+r+'__available_generation' for r in REGIONS]
        self.network_cols += ['origin_flow_'+k for k in IDS]
        self.origin_gen=self.drivers[[r+'__available_generation' for r in REGIONS]].to_numpy(dtype='float32')
        self.schema=dict(future=self.weather_cols,network=self.network_cols,ids=IDS,
            scale=self.scale.tolist(),encoders=self.encoders,delay_minutes=30,
            forbidden_future=['prices','constraint setters','IC flows','thermal availability'],
            note='Future wind/solar/demand/weather are realised conditional inputs. All origin observations delayed 30 minutes.')

    def features(self,ic,origin,h,kind='network'):
        ic=np.asarray(ic,dtype=int); origin=np.asarray(origin,dtype=int); h=np.asarray(h,dtype=int)
        valid=origin+h
        arr=self.available[valid] if kind=='availability' else self.future[valid]
        if kind=='fundamentals':arr=arr[:,:len(self.base_cols)]
        parts=[arr,ic[:,None].astype('float32')]
        if kind=='network':
            parts += [h[:,None],np.log1p(h)[:,None]]
            cutoff=self.time[origin].to_numpy()
            for lag in [1,48,336]:
                values=self.y[ic,origin-lag].copy()
                values[self.published[ic,origin-lag]>cutoff]=np.nan
                parts.append(values)
            state=self.state[ic,origin-1].copy()
            state[self.published[ic,origin-1]>cutoff]=np.nan
            gen=self.origin_gen[origin-1].copy()
            late=self.published[:,origin-1].T>cutoff[:,None]
            gen[late.any(axis=1)]=np.nan
            flows=self.y[:,origin-1,0].T.copy();flows[late]=np.nan
            parts += [state,gen,flows]
        return np.column_stack(parts).astype('float32')

    def pairs(self,start,end,leads=LEADS,training=False):
        lo=max(int(self.time.searchsorted(pd.Timestamp(start),side='left')),337)
        hi=int(self.time.searchsorted(pd.Timestamp(end),side='right'))
        origins=np.arange(lo,hi-1,dtype='int32')
        if training:
            rng=np.random.default_rng(741)
            hs=np.column_stack([rng.integers(a,b+1,len(origins)) for a,b in [(1,12),(13,48),(49,144),(145,336)]])
        else:hs=np.tile(leads,(len(origins),1))
        os=np.repeat(origins,hs.shape[1]); hs=hs.ravel()
        good=(os+hs<hi)
        os,hs=os[good],hs[good]
        return np.repeat(np.arange(6),len(os)),np.tile(os,6),np.tile(hs,6)

def estimator(leaves=23):
    return lgb.LGBMRegressor(objective='regression_l1',n_estimators=180,num_leaves=leaves,
       learning_rate=.055,min_child_samples=120,colsample_bytree=.9,reg_lambda=5,
       n_jobs=4,verbosity=-1,random_state=741,deterministic=True,force_col_wise=True)

def run_train():
    d=Design();dump(MODELS/'schema.json',d.schema)
    train=d.time<=TRAIN_END
    positions=np.flatnonzero(train)
    ci=np.repeat(np.arange(6),len(positions)); vi=np.tile(positions,6)
    # Static conditional ablations need only one copy of each delivery state.
    for kind in ['fundamentals','weather','availability']:
        x=d.features(ci,vi,np.zeros(len(ci),dtype=int),kind)
        cat=[x.shape[1]-1]
        for ti,target in enumerate(TARGETS):
            path=MODELS/f'{kind}_{target}.joblib'
            if path.exists():continue
            y=d.y[ci,vi,ti]/d.scale[ci,ti]; ok=np.isfinite(y)
            model=estimator();model.fit(x[ok],y[ok],categorical_feature=cat)
            joblib.dump(model,path)
            print('TRAINED',kind,target,int(ok.sum()),flush=True)
        del x;gc.collect()
    ci,oi,h=d.pairs(START,TRAIN_END,training=True)
    assert (d.time[oi+h]<=TRAIN_END).all()
    x=d.features(ci,oi,h)
    names=d.network_cols
    cats=[names.index(c) for c in ['ic','export_setter','import_setter']]
    trainproof={'samples':len(h),'min_origin':d.time[oi].min(),'max_target':d.time[oi+h].max(),
                'lead_min':int(h.min()),'lead_max':int(h.max()),'seed':741,
                'pair_sha256':hashlib.sha256(np.column_stack([ci,oi,h]).tobytes()).hexdigest()}
    dump(RESULTS/'training_proof.json',trainproof)
    for ti,target in enumerate(TARGETS):
        path=MODELS/f'network_{target}.joblib'
        safe=MODELS/f'network_{target}.safe.json'
        if path.exists() and safe.exists():continue
        y=d.y[ci,oi+h,ti]/d.scale[ci,ti];ok=np.isfinite(y)
        model=estimator();model.fit(x[ok],y[ok],categorical_feature=cats)
        joblib.dump(model,path)
        dump(safe,dict(timestamp_censoring=True,training_max_target=TRAIN_END,samples=int(ok.sum())))
        pd.DataFrame({'feature':names,'gain':model.booster_.feature_importance('gain')}).sort_values('gain',ascending=False).to_csv(RESULTS/f'importance_{target}.csv',index=False)
        print('TRAINED network',target,int(ok.sum()),flush=True)
    del x;gc.collect()
    # Cache one conditional prediction per delivery state. These are invariant
    # to horizon and avoid unnecessarily re-evaluating trees 336 times.
    d=Design()
    cache={}
    ci=np.repeat(np.arange(6),len(d.time)); vi=np.tile(np.arange(len(d.time)),6)
    for kind in ['fundamentals','weather','availability']:
        x=d.features(ci,vi,np.zeros(len(ci),dtype=int),kind)
        cache[kind]=np.stack([joblib.load(MODELS/f'{kind}_{t}.joblib').booster_.predict(x,num_threads=4)*d.scale[ci,j] for j,t in enumerate(TARGETS)],axis=1).reshape(6,len(d.time),5).astype('float32')
    joblib.dump(cache,MODELS/'conditional_cache.joblib')
    print('TRAINING COMPLETE',flush=True)

def predict(d,ci,oi,h,cache,models):
    vi=oi+h
    out={'persistence':d.y[ci,oi-1].copy(),'seasonal':d.y[ci,vi-336].copy()}
    late=d.published[ci,oi-1]>d.time[oi].to_numpy()
    out['persistence'][late]=d.y[ci[late],oi[late]-2]
    # For the exact seven-day endpoint, last week's same slot is the issue
    # interval and is not yet observable under the 30-minute delay.
    bad=(vi-336>oi-1)
    out['seasonal'][bad]=d.y[ci[bad],vi[bad]-672]
    for kind,a in cache.items():out[kind]=a[ci,vi]
    x=d.features(ci,oi,h)
    out['network']=np.stack([m.booster_.predict(x,num_threads=4)*d.scale[ci,j] for j,m in enumerate(models)],axis=1).astype('float32')
    return out

def run_validation():
    d=Design();cache=joblib.load(MODELS/'conditional_cache.joblib')
    models=[joblib.load(MODELS/f'network_{t}.joblib') for t in TARGETS]
    ci,oi,h=d.pairs(TRAIN_END,TEST_START)
    blocks=[]
    for start in range(0,len(h),60000):
        s=slice(start,start+60000); pred=predict(d,ci[s],oi[s],h[s],cache,models)
        frame=pd.DataFrame({'ic_code':ci[s],'origin_idx':oi[s],'h':h[s],'valid_idx':oi[s]+h[s],'band':band(h[s])})
        for j,t in enumerate(TARGETS):
            frame[t+'_actual']=d.y[ci[s],oi[s]+h[s],j]
            for kind,a in pred.items():frame[t+'_'+kind]=a[:,j]
        blocks.append(frame)
    v=pd.concat(blocks,ignore_index=True)
    v.to_parquet(RESULTS/'validation.parquet',index=False,compression='zstd')
    configs={};leader=[]
    tune_end=d.time.searchsorted(pd.Timestamp('2025-12-01'),side='right')
    cal_end=d.time.searchsorted(pd.Timestamp('2026-02-01'),side='right')
    for i,k in enumerate(IDS):
      for j,t in enumerate(TARGETS):
       for b in range(4):
        sub=v[(v.ic_code==i)&(v.band==b)]
        tune=sub[sub.valid_idx<tune_end]
        methods=['persistence','seasonal','fundamentals','weather','availability','network']
        scores={m:float(np.nanmean(np.abs(tune[t+'_actual']-tune[t+'_'+m]))) for m in methods}
        best=min(scores,key=scores.get)
        cal=sub[(sub.origin_idx>=tune_end)&(sub.valid_idx<cal_end)]
        residual=(cal[t+'_actual']-cal[t+'_'+best]).dropna().to_numpy()
        if len(residual)<100:raise ValueError('Insufficient calibration data')
        quant=np.quantile(residual,np.linspace(0,1,501)).tolist()
        cfg=dict(model=best,mae_tuning=scores,residual_quantiles=quant,calibration_n=len(residual),alert_cutoff=.2)
        alert=sub[sub.origin_idx>=cal_end]
        if t!='flow':
            direction=0 if t.startswith('export') else 1
            threshold=d.threshold[i,alert.valid_idx.to_numpy(),direction]
            pp=np.interp(threshold-alert[t+'_'+best],quant,np.linspace(0,1,501))
            yy=alert[t+'_actual'].to_numpy()<threshold
            ok=np.isfinite(threshold)&alert[t+'_actual'].notna().to_numpy()
            cfg['alert_validation_events']=int(yy[ok].sum())
            choices=[]
            for cutoff in np.arange(.05,.81,.025):
                pred=pp[ok]>=cutoff;actual=yy[ok]
                tp=int((pred&actual).sum()); fp=int((pred&~actual).sum());fn=int((~pred&actual).sum())
                f2=5*tp/max(5*tp+4*fn+fp,1)
                choices.append((f2,float(cutoff)))
            if yy[ok].sum():cfg['alert_cutoff']=max(choices,key=lambda z:(z[0],z[1]))[1]
            else:cfg['alert_note']='No February validation events; default cutoff 0.20, not tuned.'
        configs[f'{k}|{t}|{b}']=cfg
        leader.extend(dict(ic=k,target=t,band=b,model=m,mae=score,selected=m==best) for m,score in scores.items())
    dump(MODELS/'selection.json',configs)
    pd.DataFrame(leader).to_csv(RESULTS/'validation_leaderboard.csv',index=False)
    print('SELECTION AND CALIBRATION FROZEN',len(configs),flush=True)

def chosen(d,ci,vi,h,pred,configs):
    n=len(h); result={}
    for j,t in enumerate(TARGETS):
        columns={q:np.full(n,np.nan,dtype='float32') for q in ['p10','p50','p90','probability','cutoff']}
        bs=band(h)
        for i,k in enumerate(IDS):
          for b in range(4):
            mask=(ci==i)&(bs==b)
            if not mask.any():continue
            cfg=configs[f'{k}|{t}|{b}']; point=pred[cfg['model']][mask,j]
            quant=np.array(cfg['residual_quantiles'])
            for q,idx in [('p10',50),('p50',250),('p90',450)]:columns[q][mask]=point+quant[idx]
            if t!='flow':
                threshold=d.threshold[i,vi[mask],0 if t.startswith('export') else 1]
                columns['probability'][mask]=np.interp(threshold-point,quant,np.linspace(0,1,501))
                columns['cutoff'][mask]=cfg['alert_cutoff']
        result[t]=columns
    return result

if __name__=='__main__':
    import sys
    if len(sys.argv)>1 and sys.argv[1]=='validate':run_validation()
    else:run_train()
