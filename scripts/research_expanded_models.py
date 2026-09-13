"""Exploratory matched model/feature ablations and contraction classifiers.

Reads existing local evidence only; no downloads and no production model changes.
All evaluation periods have already been inspected. Publication-vintage gaps remain.
"""
from pathlib import Path
import hashlib
import json
import time
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge, LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/data/qni_vni_expanded_model_evidence.json'
SOURCES = {}


def read(path, **kwargs):
    path = Path(path)
    SOURCES[path.as_posix()] = dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size,
                                  sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    return pd.read_parquet(path, **kwargs) if path.suffix == '.parquet' else json.loads(path.read_text())


def paired_ci(base_error, new_error, dates):
    days = pd.DataFrame({'d': dates.normalize(), 'delta': base_error-new_error}).groupby('d').delta.agg(['sum','count'])
    rng = np.random.default_rng(741)
    values = days.to_numpy()
    n = len(values)
    samples = []
    for _ in range(300):
        starts = rng.integers(0, n-6, size=int(np.ceil(n/7)))
        idx = np.concatenate([np.arange(s,s+7) for s in starts])[:n]
        v = values[idx]
        samples.append(float(v[:,0].sum()/v[:,1].sum()))
    return {'mean_improvement_mw': float((base_error-new_error).mean()),
            'block_95ci_mw': np.quantile(samples,[.025,.975]).tolist()}


def base_design(y, h):
    cols = ['flow','export_tight','import_tight']
    x = pd.concat([y[cols].shift(k).add_suffix(f'_lag{k}') for k in [1,48,336]],axis=1)
    x = pd.concat([x,(y[cols].shift(1)-y[cols].shift(2)).add_suffix('_delta30')],axis=1)
    delivery = y.index+pd.Timedelta(minutes=30*h)
    hour = delivery.hour+delivery.minute/60
    for key, value in [('hour_sin',np.sin(2*np.pi*hour/24)),('hour_cos',np.cos(2*np.pi*hour/24)),
                       ('year_sin',np.sin(2*np.pi*delivery.dayofyear/365.25)),
                       ('year_cos',np.cos(2*np.pi*delivery.dayofyear/365.25)),('weekend',delivery.dayofweek>=5)]:
        x[key] = np.asarray(value,dtype=float)
    return x


def masks(index, horizon):
    end = index+pd.Timedelta(minutes=horizon)
    return {'train': (index >= '2024-09-08') & (end < pd.Timestamp('2025-09-01')),
            'select': (index >= '2025-09-01') & (end < pd.Timestamp('2025-12-01')),
            'calibrate': (index >= '2025-12-01') & (end < pd.Timestamp('2026-02-01')),
            'alert': (index >= '2026-02-01') & (end < pd.Timestamp('2026-03-01')),
            'evaluate': (index >= '2026-03-01') & (end <= pd.Timestamp('2026-08-31 23:30'))}


def fit_ridge(x, residual, tr, va):
    lo, hi = x.loc[tr].quantile(.001), x.loc[tr].quantile(.999)
    z = x.clip(lo,hi,axis=1)
    best = None
    for alpha in [10,100,1000]:
        m = make_pipeline(SimpleImputer(add_indicator=True,keep_empty_features=True),StandardScaler(),Ridge(alpha=alpha))
        m.fit(z.loc[tr],residual[tr])
        score = float(np.abs(residual[va]-m.predict(z.loc[va])).mean())
        if best is None or score < best[0]: best=(score,m,z,{'alpha':alpha})
    return best


def fit_boost(x, residual, tr, va, objective):
    best=None
    for leaves in [7,15]:
        m=lgb.LGBMRegressor(objective=objective,n_estimators=150,num_leaves=leaves,
                            learning_rate=.04,min_child_samples=150,reg_lambda=10,
                            verbosity=-1,n_jobs=2,random_state=741,deterministic=True,force_col_wise=True)
        m.fit(x.loc[tr],residual[tr])
        score=float(np.abs(residual[va]-m.predict(x.loc[va])).mean())
        if best is None or score<best[0]:best=(score,m,x,{'leaves':leaves,'trees':150,'objective':objective})
    return best


def run():
    started=time.monotonic()
    targets=read(ROOT/'data/processed/targets.parquet')
    ic5=read(ROOT/'data/processed/ic_5min.parquet',columns=['time','INTERCONNECTORID','export','import'])
    regression,events,quality,attribution,features=[],[],[],[],{}
    for name,ident in [('vni','VIC1-NSW1'),('qni','NSW1-QLD1')]:
        root=ROOT/f'data/constraint_{name}_2y/months'
        partitions=sorted(root.glob('*/constraint_features_30min.parquet'))
        assert len(partitions)==24
        fs=[]
        for p in partitions:
            fs.append(read(p))
            q=read(p.parent/'feature_audit.json')
            quality.append({'ic':name.upper(),'month':p.parent.name,**q})
        f=pd.concat(fs).set_index('time').sort_index()
        assert f.index.is_unique
        y=targets[targets.ic.eq(ident)].set_index('time').sort_index()
        y=y.reindex(pd.date_range(y.index.min(),y.index.max(),freq='30min'))
        f=f.reindex(y.index).shift(1).replace([np.inf,-np.inf],np.nan)
        state=['upper_room','lower_room','upper_switch_gap','lower_switch_gap','upper_candidate_count',
               'lower_candidate_count','partial_candidate_fraction','pressure_complete_fraction']
        pressure=['upper_gen_tightening','upper_gen_relief','lower_gen_tightening','lower_gen_relief',
                  'upper_pressure_change','lower_pressure_change','upper_available_relief','lower_available_relief']
        features[name]={'state':state,'pressure':pressure}
        for h in [1,6,48]:
            base=base_design(y,h)
            blocks={'base':base,'state':pd.concat([base,f[state]],axis=1),
                    'pressure':pd.concat([base,f[pressure]],axis=1),
                    'full':pd.concat([base,f[state+pressure]],axis=1)}
            mm=masks(y.index,h*30)
            for target in ['flow','export_tight','import_tight']:
                truth=y[target].reindex(y.index+pd.Timedelta(minutes=h*30)).to_numpy()
                anchor=y[target].shift(1).to_numpy()
                ok=np.isfinite(truth)&np.isfinite(anchor)
                tr,va,te=[mm[k]&ok for k in ['train','select','evaluate']]
                residual=truth-anchor
                baseerr=np.abs(residual[te])
                common=dict(ic=name.upper(),target=target,horizon_minutes=h*30,n=int(te.sum()))
                predictions={'persistence':anchor[te]}
                candidates={}
                for block in blocks:
                    candidates['ridge_'+block]=fit_ridge(blocks[block],residual,tr,va)
                for block in ['base','full']:
                    candidates['boost_l1_'+block]=fit_boost(blocks[block],residual,tr,va,'regression_l1')
                candidates['boost_l2_full']=fit_boost(blocks['full'],residual,tr,va,'regression')
                for model,(score,m,z,settings) in candidates.items():predictions[model]=anchor[te]+m.predict(z.loc[te])
                for model,pred in predictions.items():
                    err=np.abs(truth[te]-pred)
                    row={**common,'model':model,'mae_mw':float(err.mean()),'rmse_mw':float(np.sqrt(np.mean((truth[te]-pred)**2))),
                         'bias_mw':float((pred-truth[te]).mean()),'vs_persistence':paired_ci(baseerr,err,y.index[te])}
                    if model!='persistence':row.update(validation_mae_mw=candidates[model][0],settings=candidates[model][3])
                    for season,months in [('autumn',[3,4,5]),('winter',[6,7,8])]:
                        s=np.isin(y.index[te].month,months)
                        row[season+'_mae_mw']=float(err[s].mean())
                    if model=='boost_l1_full':
                        row['vs_boost_l1_base']=paired_ci(np.abs(truth[te]-predictions['boost_l1_base']),err,y.index[te])
                        row['vs_ridge_full']=paired_ci(np.abs(truth[te]-predictions['ridge_full']),err,y.index[te])
                    regression.append(row)
                print(name,h*30,target,'regression done',flush=True)
        raw=ic5[ic5.INTERCONNECTORID.eq(ident)].set_index('time').sort_index()
        raw=raw.reindex(pd.date_range('2024-09-01','2026-08-31 23:55',freq='5min'))
        for direction in ['export','import']:
            c=raw[direction]
            drop=c.shift(6)-c
            eligible=(c.notna().rolling(7,min_periods=7).sum()==7)
            pos=drop.where((drop>0)&eligible)
            history=pos[pos.index<pd.Timestamp('2025-09-01')]
            thresholds=history.groupby(history.index.month).quantile(.9)
            threshold=pd.Series(c.index.month,index=c.index).map(thresholds)
            sharp=eligible&(drop>0)&(drop>=threshold)
            onset=sharp&~sharp.shift(1,fill_value=False)
            future=pd.concat([onset.shift(-k).astype(float) for k in range(1,13)],axis=1)
            complete=raw[direction].notna()
            future_complete=pd.concat([complete.shift(-k) for k in range(1,13)],axis=1).eq(True).all(axis=1)
            label=future.max(axis=1).where(future_complete).reindex(y.index).to_numpy()
            base=base_design(y,2)
            block={'base':base,'full':pd.concat([base,f[state+pressure]],axis=1)}
            mm=masks(y.index,60);ok=np.isfinite(label)
            tr,va,ca,al,te=[mm[k]&ok for k in ['train','select','calibrate','alert','evaluate']]
            yy=label.astype(float)
            predictors={'climatology':np.full(len(y),float(yy[tr].mean()))}
            settings={}
            for b,x in block.items():
                lo,hi=x.loc[tr].quantile(.001),x.loc[tr].quantile(.999)
                z=x.clip(lo,hi,axis=1)
                best=None
                for strength in [.01,.1,1.]:
                    m=make_pipeline(SimpleImputer(add_indicator=True,keep_empty_features=True),StandardScaler(),
                                    LogisticRegression(C=strength,max_iter=2000,solver='lbfgs'))
                    m.fit(z.loc[tr],yy[tr])
                    score=log_loss(yy[va],m.predict_proba(z.loc[va])[:,1])
                    if best is None or score<best[0]:best=(score,m,strength)
                predictors['logistic_'+b]=best[1].predict_proba(z)[:,1]
                settings['logistic_'+b]={'C':best[2]}
                best=None
                for leaves in [7,15]:
                    m=lgb.LGBMClassifier(n_estimators=150,num_leaves=leaves,learning_rate=.04,min_child_samples=150,
                                         reg_lambda=10,verbosity=-1,n_jobs=2,random_state=741,deterministic=True,force_col_wise=True)
                    m.fit(x.loc[tr],yy[tr])
                    score=log_loss(yy[va],m.predict_proba(x.loc[va])[:,1])
                    if best is None or score<best[0]:best=(score,m,leaves)
                predictors['boost_'+b]=best[1].predict_proba(x)[:,1]
                settings['boost_'+b]={'leaves':best[2],'trees':150}
            for model,p in predictors.items():
                p=np.clip(p,1e-6,1-1e-6)
                if model!='climatology':
                    logits=np.log(p/(1-p)).reshape(-1,1)
                    calibration=LogisticRegression(C=1e6,max_iter=1000).fit(logits[ca],yy[ca])
                    p=calibration.predict_proba(logits)[:,1]
                # Strict '>' provides <=5% false-positive rate on the alert-tuning negatives, including ties.
                cutoff=float(np.quantile(p[al&(yy==0)],.95))
                pred=p[te]>cutoff
                actual=yy[te].astype(bool)
                tp=int((pred&actual).sum());fp=int((pred&~actual).sum());fn=int((~pred&actual).sum())
                events.append(dict(ic=name.upper(),direction=direction,horizon_minutes=60,model=model,
                                   n=int(te.sum()),positives=int(actual.sum()),base_rate=float(actual.mean()),
                                   brier=float(brier_score_loss(actual,p[te])),log_loss=float(log_loss(actual,p[te])),
                                   average_precision=float(average_precision_score(actual,p[te])),
                                   threshold=cutoff,recall=tp/max(tp+fn,1),precision=tp/max(tp+fp,1),
                                   false_positive_rate=fp/max(int((~actual).sum()),1),tp=tp,fp=fp,fn=fn,
                                   false_positive_origins_per_day=fp/len(np.unique(y.index[te].date)),
                                   detector_month_thresholds_mw={str(k):float(v) for k,v in thresholds.items()},
                                   settings=settings.get(model,{})))
            print(name,direction,'events done',flush=True)
        a=read(ROOT/f'data/event_{name}_2y/event_attribution.parquet')
        attribution.append(dict(ic=name.upper(),cases=len(a),exact_share_median=float(a.exact_step_share.median()),
                                cases_all_exact=int(a.exact_step_share.ge(.999999).sum()),
                                cases_no_exact=int(a.exact_step_share.eq(0).sum()),
                                complete_terms_share_median=float(a.complete_terms_share.median()),
                                cases_with_switch_component=int(a.switch_composite_mw.abs().gt(1).sum()),
                                note='Case-level summaries; overlapping windows, not population contribution percentages.'))
    result=dict(status='exploratory retrospective development assessment',generated_date='2026-09-13',
                regression_scores=regression,event_scores=events,monthly_quality=quality,attribution_quality=attribution,
                feature_blocks=features,sources=list(SOURCES.values()),downloads=[],
                settings={'regression_horizons_minutes':[30,180,1440],'event_horizon_minutes':60,
                          'train':'2024-09-08 origins; deliveries before 2025-09-01',
                          'select':'September-November 2025, deliveries remain inside partition',
                          'event_calibration':'December 2025-January 2026','alert_tuning':'February 2026',
                          'evaluate':'March-August 2026; deliveries through 2026-08-31 23:30',
                          'observation_delay_minutes':30,'bootstrap':'300 non-circular seven-day origin blocks; seed 741',
                          'event_label':'any new frozen-threshold contraction onset in next 60 minutes; overlapping origin windows',
                          'event_threshold':'month-of-year 90th percentile of positive 30-minute falls in first study year; frozen',
                          'event_alarm':'strictly above 95th percentile of February negative-origin probabilities'},
                limitations=['Previously inspected evaluation period; no independent final holdout.',
                             'Retained topology is retrospective and has version/publication gaps.',
                             'Pressure includes solved-target and availability quantities; not verified live public inputs.',
                             'No future realised fundamentals supplied; not matched to original conditional backtest.',
                             'Event metrics count origin windows, not deduplicated incident warnings.',
                             'Point regressions use an older observation anchor; no AEMO input correction in this probe.',
                             'Linear models use training-only clipping; boosting uses native missing values and no clipping.',
                             'Intervals are exploratory paired uncertainty estimates without multiple-comparison correction.'],
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),runtime_seconds=time.monotonic()-started,
                versions={'pandas':pd.__version__,'lightgbm':lgb.__version__})
    OUT.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
    print('saved',OUT,flush=True)


if __name__=='__main__':
    with threadpool_limits(limits=2):run()
