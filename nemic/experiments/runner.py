"""Resumable bounded campaigns. Selection always precedes the scored period."""
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import argparse
import gc
import json
import os
import time
import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits
from .core import ROOT,Store,load_config,fingerprint,clean,digest
from .data import inventory,connector_data,base_frame,design,registry
from .validation import Fold,folds,pairs,regression_score,paired_interval,interval_score
from .models import select,forecast_pressure,Transform,LinearQuantiles
from .events import detect,window_label,incidents,match,tune_joint,probability_score,incident_interval

POINT_RECIPES=[('ridge_base','ridge','base'),('ridge_state','ridge','state'),('ridge_pressure','ridge','pressure'),
    ('ridge_full','ridge','full'),('ridge_forecast','ridge','forecast'),('ridge_context','ridge','context'),
    ('elastic_context','elastic','context'),('additive_context','additive','context'),('regime_context','regime','context'),
    ('boost_base','boost','base'),('boost_context','boost','context'),('boost_l2_context','boost_l2','context')]


def save_model(store,path,model):
    p=store.owned(path)
    with store.reserve(40_000_000):
        p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');joblib.dump(model,tmp,compress=3);os.replace(tmp,p)


def reference(d,o,h,target,period=None):
    index=o-1 if period is None else o+h-np.ceil((h+1)/period).astype(int)*period
    result=np.full(len(o),np.nan);good=index>=0
    result[good]=d['y'][target].to_numpy()[index[good]]
    return result


def numeric_job(config_path,ic_index,fold_dict,band_no,inv_fp):
    with threadpool_limits(limits=2):return _numeric_job(config_path,ic_index,fold_dict,band_no,inv_fp)


def _numeric_job(config_path,ic_index,fold_dict,band_no,inv_fp):
    c=load_config(config_path);store=Store(c);ic=c['connectors'][ic_index];fold=Fold(**fold_dict)
    ident=f"{ic['name']}/{fold.name}/band{band_no}";out=store.root/'trials'/ident
    fp=fingerprint([inv_fp,ident]);resultpath=out/'result.json'
    if store.valid(ident,fp):return {'job':ident,'status':'cached'}
    started=time.monotonic();d=connector_data(c,ic);d['base']=base_frame(d)
    lo,hi=c['bands'][band_no];leads=[h for h in c['leads'] if lo<=h<=hi]
    if not leads:return {'job':ident,'status':'unsupported','reason':'No configured leads in band'}
    forecast=forecast_pressure(d,fold,int(np.median(leads)))
    ot,ht=pairs(d['y'].index,fold,leads,True);oe,he=pairs(d['y'].index,fold,leads)
    idx=d['y'].index;mask=fold.masks(idx[oe],he*30)
    train_x={recipe:design(d,ot,ht,recipe,forecast) for recipe in ['base','state','pressure','full','forecast','context','oracle']}
    eval_x={recipe:design(d,oe,he,recipe,forecast) for recipe in train_x}
    rows=[];slices=[];selections=[];warnings=[];quantile_scores=[];artifacts=[]
    for target in c['targets']:
        y=d['y'][target].to_numpy();anchor_train=reference(d,ot,ht,target);anchor=reference(d,oe,he,target)
        truth_train=y[ot+ht];truth=y[oe+he]
        tr=np.isfinite(truth_train)&np.isfinite(anchor_train)
        good=np.isfinite(truth)&np.isfinite(anchor)
        va=mask['select']&good;ca=mask['calibrate']&good;te=mask['evaluate']&good
        if tr.sum()<500 or va.sum()<100 or te.sum()==0:
            warnings.append({'target':target,'status':'unavailable','reason':'Insufficient eligible train/selection/evaluation rows'});continue
        predictions={'persistence':anchor,'seasonal_daily':reference(d,oe,he,target,48),'seasonal_weekly':reference(d,oe,he,target,336)}
        validation={k:float(np.nanmean(np.abs(truth[va]-v[va]))) for k,v in predictions.items()}
        candidates={};settings={}
        for name,family,recipe in POINT_RECIPES:
            model,trials=select(family,train_x[recipe].loc[tr],truth_train[tr]-anchor_train[tr],eval_x[recipe].loc[va],truth[va]-anchor[va],c)
            pred=anchor+model.predict(eval_x[recipe]);predictions[name]=pred
            validation[name]=float(np.abs(truth[va]-pred[va]).mean());candidates[name]=(model,recipe);settings[name]=trials
        simple=min([n for n in candidates if not n.startswith('boost')],key=validation.get)
        boosted=min([n for n in candidates if n.startswith('boost')],key=validation.get)
        weights=[0,.25,.5,.75,1]
        weight=min(weights,key=lambda w:np.abs(truth[va]-(w*predictions[simple][va]+(1-w)*predictions[boosted][va])).mean())
        predictions['blend']=weight*predictions[simple]+(1-weight)*predictions[boosted]
        validation['blend']=float(np.abs(truth[va]-predictions['blend'][va]).mean())
        winner=min(validation,key=lambda k:(validation[k],list(validation).index(k)))
        # Future-actual diagnostic does not enter the retrospective winner selection.
        oracle,oracle_trials=select('ridge',train_x['oracle'].loc[tr],truth_train[tr]-anchor_train[tr],eval_x['oracle'].loc[va],truth[va]-anchor[va],c)
        predictions['oracle_ridge']=anchor+oracle.predict(eval_x['oracle']);settings['oracle_ridge']=oracle_trials
        validation['oracle_ridge']=float(np.abs(truth[va]-predictions['oracle_ridge'][va]).mean())
        for name,pred in predictions.items():
            track='oracle' if name.startswith('oracle') else 'retrospective'
            common={'ic':ic['name'],'connector':ic['id'],'protocol':fold.protocol,'fold':fold.name,'band':band_no,'target':target,'model':name,'track':track,'selected':name==winner}
            score=regression_score(truth[te],pred[te],anchor[te]);score.update(common)
            score['validation_mae']=validation[name]
            if name==winner:score['improvement_ci']=paired_interval(truth[te],pred[te],anchor[te],idx[oe[te]])
            rows.append(score)
            season=np.array(['Summer','Autumn','Winter','Spring'])[(idx[oe[te]+he[te]].month%12)//3]
            hour=idx[oe[te]+he[te]].hour
            for kind,values in [('season',season),('hour',hour),('lead_minutes',he[te]*30)]:
                for value in np.unique(values):
                    m=values==value;slices.append({**common,'slice':kind,'value':str(value),**regression_score(truth[te][m],pred[te][m])})
        # Fit uncertainty challengers only on the selected simple recipe, reducing the Cartesian product.
        recipe=candidates[simple][1];levels=c['models']['quantiles']
        residual_train=truth_train[tr]-anchor_train[tr]
        linear=LinearQuantiles().fit(train_x[recipe].loc[tr],residual_train,levels)
        qlinear=linear.predict(eval_x[recipe])+anchor[:,None]
        transform=Transform().fit(train_x[recipe].loc[tr]);zt=transform.apply(train_x[recipe].loc[tr]);ze=transform.apply(eval_x[recipe])
        qb=[];boost_quantiles=[]
        for q in levels:
            m=lgb.LGBMRegressor(objective='quantile',alpha=q,n_estimators=150,num_leaves=7,learning_rate=.04,min_child_samples=150,reg_lambda=10,n_jobs=2,verbosity=-1,random_state=741,deterministic=True,force_col_wise=True)
            m.fit(zt,residual_train);qb.append(m.booster_.predict(ze,num_threads=2)+anchor);boost_quantiles.append(m)
        qboost=np.sort(np.column_stack(qb),axis=1)
        # Model selection uses the selection partition; location calibration uses later residuals.
        qkind=min(['linear','boost'],key=lambda n:interval_score(truth[va],{'linear':qlinear,'boost':qboost}[n][va],levels)['wis'])
        qselected={'linear':qlinear,'boost':qboost}[qkind]
        adjustments=np.quantile((truth[:,None]-qselected)[ca],levels,axis=0).diagonal() if ca.any() else np.zeros(len(levels))
        qcal=np.sort(qselected+adjustments,axis=1)
        for name,qpred in [('linear',qlinear),('boost',qboost),('selected_calibrated',qcal)]:
            quantile_scores.append({'ic':ic['name'],'protocol':fold.protocol,'fold':fold.name,'band':band_no,'target':target,'model':name,'selected_family':qkind,'linear_converged':linear.converged,**interval_score(truth[te],qpred[te],levels)})
        selected=predictions[winner]
        frame=pd.DataFrame({'origin':idx[oe[te]],'delivery':idx[oe[te]+he[te]],'lead':he[te],'actual':truth[te],'prediction':selected[te],'persistence':anchor[te],'model':winner,'ic':ic['name'],'target':target,'fold':fold.name,'protocol':fold.protocol,'band':band_no})
        for i,q in enumerate(levels):frame[f'q{q}']=qcal[te,i]
        predpath=store.parquet(out/f'{target}_predictions.parquet',frame);artifacts.append({'path':str(predpath.relative_to(store.root)),'sha256':digest(predpath)})
        bundle={'winner':winner,'simple':simple,'boosted':boosted,'blend_weight':weight,'models':{k:candidates[k] for k in {simple,boosted,winner} if k in candidates},'quantile_family':qkind,'linear_quantiles':linear if qkind=='linear' else None,'boost_quantiles':boost_quantiles if qkind=='boost' else None,'quantile_transform':transform if qkind=='boost' else None,'quantile_recipe':recipe,'quantile_adjustments':adjustments,'columns':{r:list(x.columns) for r,x in train_x.items()},'fold':fold.dict(),'information_track':'retrospective','operationally_eligible':False}
        modelpath=out/f'{target}_model.joblib';save_model(store,modelpath,bundle);artifacts.append({'path':str(modelpath.relative_to(store.root)),'sha256':digest(modelpath)})
        # Full-resolution 336-step curve is generated at a declared evaluated origin; scoring remains on 14 leads.
        curve_origin=pd.Timestamp(fold.evaluate_end)-pd.Timedelta(days=7,minutes=30)
        pos=idx.get_indexer([curve_origin])[0]
        if pos>=0:
            hh=np.arange(lo,hi+1);oo=np.repeat(pos,len(hh));an=reference(d,oo,hh,target)
            def cp(name):
                if name=='persistence':return an
                if name.startswith('seasonal'):return reference(d,oo,hh,target,48 if name.endswith('daily') else 336)
                m,r=candidates[name];return an+m.predict(design(d,oo,hh,r,forecast))
            curve=weight*cp(simple)+(1-weight)*cp(boosted) if winner=='blend' else cp(winner)
            store.parquet(out/f'{target}_curve.parquet',pd.DataFrame({'origin':curve_origin,'delivery':idx[oo]+pd.to_timedelta(hh*30,unit='min'),'lead':hh,'prediction':curve,'target':target,'model':winner,'track':'retrospective'}))
        selections.append({'target':target,'winner':winner,'simple':simple,'boost':boosted,'blend_weight':weight,'settings':settings,'n_train':int(tr.sum()),'n_validation':int(va.sum()),'n_evaluation':int(te.sum()),'feature_recipe':candidates.get(winner,(None,'baseline'))[1] if winner!='blend' else 'blend','quantile_family':qkind})
        print(ident,target,'winner',winner,'done',flush=True)
        gc.collect()
    payload={'job':ident,'fingerprint':fp,'fold':fold.dict(),'scores':rows,'slices':slices,'quantiles':quantile_scores,'selection':selections,'warnings':warnings,'artifacts':artifacts,'runtime_seconds':time.monotonic()-started,'pressure_forecast_lead_halfhours':int(np.median(leads)),'claim':'retrospective development; selected curves do not establish live performance'}
    store.json(resultpath,payload);store.complete(ident,fp,resultpath)
    return {'job':ident,'status':'complete','seconds':payload['runtime_seconds']}


def event_job(c,ic,fold,inv_fp):
    store=Store(c);ident=f"{ic['name']}/{fold.name}/events";fp=fingerprint([inv_fp,ident]);out=store.root/'trials'/ident
    if store.valid(ident,fp):return {'job':ident,'status':'cached'}
    d=connector_data(c,ic);d['base']=base_frame(d);idx=d['y'].index
    o=np.arange(len(idx));h=np.repeat(4,len(idx));forecast=forecast_pressure(d,fold,4)
    xs={r:design(d,o,h,r,forecast) for r in ['base','full','context']}
    masks=fold.masks(idx,120);labels={};detectors={};catalogues={};thresholds={}
    for direction in ['export','import']:
        de,th=detect(d['raw'][direction],fold.train_start,fold.train_end,c['events']['percentile'],c['events']['minimum_positive'])
        detectors[direction]=de;thresholds[direction]=th;catalogues[direction]=incidents(de)
        labels[direction]=window_label(de.onset,de.valid,idx)
    recipes=[('logistic_base','ridge','base'),('logistic_full','ridge','full'),('logistic_context','ridge','context'),('additive_context','additive','context'),('regime_context','regime','context'),('boost_base','boost','base'),('boost_context','boost','context')]
    results=[];selections=[];predictions={};trial_settings={};models={}
    for name,family,recipe in recipes:
        predictions[name]={};models[name]={};trial_settings[name]={}
        for direction in ['export','import']:
            y=labels[direction];good=np.isfinite(y);tr=masks['train']&good;va=masks['select']&good;ca=masks['calibrate']&good
            if len(np.unique(y[tr]))<2 or len(np.unique(y[ca]))<2:
                predictions[name][direction]=np.full(len(idx),np.nan);continue
            model,settings=select(family,xs[recipe].loc[tr],y[tr],xs[recipe].loc[va],y[va],c,True)
            p=np.clip(model.predict(xs[recipe]),1e-6,1-1e-6)
            logits=np.log(p/(1-p)).reshape(-1,1)
            calibration=LogisticRegression(C=1e6,max_iter=1000).fit(logits[ca],y[ca])
            predictions[name][direction]=calibration.predict_proba(logits)[:,1]
            models[name][direction]=(model,calibration,recipe);trial_settings[name][direction]=settings
    # Family selected on uncalibrated validation loss, before calibration/alert/evaluation.
    winner=min(recipes,key=lambda r:sum(min(s['validation_loss'] for s in trial_settings[r[0]].get(dr,[{'validation_loss':1e9}])) for dr in ['export','import']))[0]
    for name,_,_ in recipes:
        tune=[]
        for direction in ['export','import']:
            y=labels[direction];p=predictions[name][direction];al=masks['alert']&np.isfinite(y)&np.isfinite(p)
            tune.append((idx[al],p[al],catalogues[direction]))
        if any(len(x[0])==0 for x in tune):continue
        cutoffs=tune_joint(tune,c['events']['false_alarms_per_day'])
        for direction,cutoff in zip(['export','import'],cutoffs):
            y=labels[direction];p=predictions[name][direction];te=masks['evaluate']&np.isfinite(y)&np.isfinite(p)
            event=match(idx[te],p[te],cutoff,catalogues[direction])
            row={'ic':ic['name'],'protocol':fold.protocol,'fold':fold.name,'direction':direction,'model':name,'selected':name==winner,'threshold':cutoff,'probability':probability_score(y[te],p[te]),'incidents':event,'uncertainty':incident_interval(event),'absolute':{}}
            for absolute in c['events']['absolute_drops_mw']:
                de,_=detect(d['raw'][direction],fold.train_start,fold.train_end,absolute=absolute)
                row['absolute'][str(absolute)]=match(idx[te],p[te],cutoff,incidents(de))
            results.append(row)
            if name==winner:
                store.parquet(out/f'{direction}_predictions.parquet',pd.DataFrame({'origin':idx[te],'probability':p[te],'actual_window':y[te],'threshold':cutoff,'direction':direction,'model':name}))
                store.parquet(out/f'{direction}_incidents.parquet',catalogues[direction])
        if name==winner:save_model(store,out/'selected_model.joblib',{'models':models[name],'thresholds':cutoffs,'winner':winner,'fold':fold.dict(),'operationally_eligible':False})
    # Secondary tasks use reported setters/bounds and flow direction, not reconstructed future features.
    secondary=[]
    for task in ['flow_reversal','setter_switch','forced_direction']:
        y=d['y'];future=y.shift(-4)
        if task=='flow_reversal':label=((np.sign(y.flow.shift(1))!=np.sign(future.flow))&(y.flow.shift(1).abs()>25)&(future.flow.abs()>25)).astype(float).where(y.flow.shift(1).notna()&future.flow.notna())
        elif task=='setter_switch':label=(future.export_setter.ne(y.export_setter.shift(1))|future.import_setter.ne(y.import_setter.shift(1))).astype(float).where(future.export_setter.notna()&future.import_setter.notna()&y.export_setter.shift(1).notna()&y.import_setter.shift(1).notna())
        else:label=(future.export_tight.lt(0)|future.import_tight.lt(0)).astype(float).where(future.export_tight.notna()&future.import_tight.notna())
        yy=label.to_numpy();good=np.isfinite(yy);tr=masks['train']&good;va=masks['select']&good;ca=masks['calibrate']&good;te=masks['evaluate']&good
        for family in ['ridge','boost']:
            if len(np.unique(yy[tr]))<2:secondary.append({'task':task,'model':family,'status':'unavailable','reason':'Single training class'});continue
            model,settings=select(family,xs['full'].loc[tr],yy[tr],xs['full'].loc[va],yy[va],c,True)
            p=np.clip(model.predict(xs['full']),1e-6,1-1e-6)
            if len(np.unique(yy[ca]))==2:
                logits=np.log(p/(1-p)).reshape(-1,1);cal=LogisticRegression(C=1e6,max_iter=1000).fit(logits[ca],yy[ca]);p=cal.predict_proba(logits)[:,1]
            secondary.append({'ic':ic['name'],'protocol':fold.protocol,'fold':fold.name,'task':task,'model':family,'horizon_minutes':120,**probability_score(yy[te],p[te])})
    result={'job':ident,'fingerprint':fp,'fold':fold.dict(),'winner':winner,'scores':results,'secondary':secondary,'settings':trial_settings,'thresholds':thresholds,'event_window':[30,120],'track':'retrospective'}
    store.json(out/'result.json',result);store.complete(ident,fp,out/'result.json')
    return {'job':ident,'status':'complete'}


def run(c,kind='all',only_ic=None,only_fold=None):
    store=Store(c);inv=inventory(c);store.json(store.root/'feature_registry.json',registry())
    started=time.monotonic();deadline=started+c['limits']['batch_hours']*3600;progress=[]
    for i,ic in enumerate(c['connectors']):
        if only_ic and only_ic not in [ic['name'],ic['id']]:continue
        selected_folds=[f for f in folds(c) if only_fold is None or f.name==only_fold]
        if kind in ['all','numeric']:
            with ProcessPoolExecutor(max_workers=c['limits']['workers']) as pool:
                # Keep only two tasks in flight; checkpoint before scheduling after the deadline.
                jobs=iter((f,b) for f in selected_folds for b in range(len(c['bands'])))
                active={}
                def submit():
                    if time.monotonic()>=deadline:return
                    try:f,b=next(jobs)
                    except StopIteration:return
                    fut=pool.submit(numeric_job,str(c['_path']),i,f.dict(),b,inv['fingerprint']);active[fut]=(f.name,b)
                for _ in range(c['limits']['workers']):submit()
                while active:
                    future=next(as_completed(active));key=active.pop(future)
                    try:r=future.result()
                    except Exception as exc:
                        r={'ic':ic['name'],'fold':key[0],'band':key[1],'status':'failed','error':repr(exc)}
                    progress.append(r);store.json(store.root/'progress.json',{'jobs':progress,'elapsed_seconds':time.monotonic()-started});print(json.dumps(r),flush=True);submit()
        if kind in ['all','events']:
            for fold in selected_folds:
                if time.monotonic()>=deadline:break
                try:
                    with threadpool_limits(limits=2):r=event_job(c,ic,fold,inv['fingerprint'])
                except Exception as exc:r={'ic':ic['name'],'fold':fold.name,'status':'failed','error':repr(exc)}
                progress.append(r);store.json(store.root/'progress.json',{'jobs':progress,'elapsed_seconds':time.monotonic()-started});print(json.dumps(r),flush=True)
        if time.monotonic()>=deadline:break
    failures=[x for x in progress if x['status']=='failed']
    store.json(store.root/'batch_summary.json',{'jobs':progress,'failures':failures,'elapsed_seconds':time.monotonic()-started,'checkpointed':time.monotonic()>=deadline})
    if failures:raise RuntimeError(f'{len(failures)} failed jobs; see batch_summary.json')
