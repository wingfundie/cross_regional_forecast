"""Grouped permutation and SHAP evidence for historical NOS point models."""
import json
import re

import joblib
import numpy as np
import pandas as pd
import shap
from threadpoolctl import threadpool_limits

from .core import Store,digest,fingerprint,load_config
from .diurnal import metrics,mature_masks,expansion
from .diurnal_explain import full_prediction,groups
from .diurnal_runner import CONFIG,frame
from .data import connector_data,base_frame,design
from .events import detect,window_label
from .nos_runner import BLOCKS,add_interactions
from .validation import folds


def _features(base,joined,recipe,known):
    x=base.copy();parts=[] if recipe=='O0' else recipe.split('+');blocks=[p for p in parts if p in BLOCKS]
    for block in blocks:
        for col in BLOCKS[block]:x[col]=joined[col].to_numpy()
    if blocks:
        x['nos_source_age_minutes']=(joined.origin-joined.nos_report_generated).dt.total_seconds()/60
        x['nos_unknown_source']=(~known).astype(float)
    if 'OX' in parts:add_interactions(x)
    return x


def _safe(name):return re.sub(r'[^A-Za-z0-9_.-]+','_',name)


def explain_point(c,path):
    store=Store(c);folder=path.parent;result=json.loads(path.read_text())
    ident=str(folder.relative_to(store.root))+'/explanations'
    fp=fingerprint([digest(path),digest(store.root/'nos/exposure.parquet'),digest(__file__)])
    if store.valid(ident,fp):return
    fold=next(f for f in folds(c) if f.name==result['fold']['name'])
    base,meta,masks=frame(c,c['connectors'][0],fold,0,result['target'])
    exposure=pd.read_parquet(store.root/'nos/exposure.parquet').drop(columns='nos_mapping_track')
    joined=meta[['origin','lead']].merge(exposure,on=['origin','lead'],how='left',validate='many_to_one')
    known=joined.nos_report_generated.notna()
    known &= joined.nos_report_generated.add(pd.Timedelta(minutes=30)).le(joined.origin)
    known &= (joined.origin-joined.nos_report_generated-pd.Timedelta(minutes=30))<=pd.Timedelta(minutes=90)
    history_start=pd.Timestamp(result['history_start'])
    train=masks['train']&meta.origin.ge(history_start)&known
    available=masks['evaluate']&known
    dates=meta.loc[available,'origin'].dt.normalize().unique()
    chosen=dates[np.linspace(0,len(dates)-1,min(5,len(dates)),dtype=int)]
    sample=available&meta.origin.dt.normalize().isin(chosen)
    ms=meta.loc[sample].reset_index(drop=True);bundle=joblib.load(folder/'models.joblib')
    importance=[];statuses=[]
    for name,item in bundle['models'].items():
        model=item['model'];recipe=name.split('_',1)[1]
        x=_features(base,joined,recipe,known)
        xs=x.loc[sample].reset_index(drop=True);tr=x.loc[train]
        background=tr.iloc[np.linspace(0,len(tr)-1,min(32,len(tr)),dtype=int)]
        positions=np.linspace(0,len(xs)-1,min(12,len(xs)),dtype=int);local=xs.iloc[positions]
        prediction=full_prediction(model,xs);baseline=metrics(ms.actual.to_numpy(),prediction)['mae']
        rng=np.random.default_rng(741)
        for group,names in groups(xs.columns).items():
            losses=[]
            for replicate in range(5):
                shifted=xs.copy();n=len(shifted);offset=max(1,n//5)*(replicate+1)
                if group=='calendar':
                    phase=np.arctan2(xs.hour_sin,xs.hour_cos).to_numpy()+offset*2*np.pi/48
                    shifted['hour_sin'],shifted['hour_cos']=np.sin(phase),np.cos(phase)
                else:shifted[names]=np.roll(xs[names].to_numpy(),offset%n,axis=0)
                losses.append(metrics(ms.actual.to_numpy(),full_prediction(model,shifted))['mae']-baseline)
            importance.append({'model':name,'group':group,'mae_degradation':float(np.mean(losses)),
                               'replicates':losses,'n':len(xs)})
        a=model.transformed(local);transformed_background=model.transformed(background);names=list(model.names)
        if model.family=='T6':
            explanation=shap.TreeExplainer(model.model,
                feature_perturbation='tree_path_dependent')(a,check_additivity=True)
            phi=explanation.values.copy();base_values=np.asarray(explanation.base_values)+background.own_anchor.mean()
            method='exact path-dependent TreeSHAP correction plus explicit anchor'
        else:
            bg=transformed_background.mean(axis=0);phi=(a-bg)*model.model.coef_
            base_value=float(model.model.intercept_+bg@model.model.coef_+background.own_anchor.mean())
            base_values=np.repeat(base_value,len(local));method='exact linear transformed-feature decomposition including anchor'
        phi[:,names.index('own_anchor')]+=local.own_anchor.to_numpy()-background.own_anchor.mean()
        predicted=full_prediction(model,local)
        gap=float(np.max(abs(base_values+phi.sum(axis=1)-predicted)))
        if gap>max(1e-3,1e-5*np.max(abs(predicted))):raise ValueError(f'NOS SHAP reconstruction failed: {name}: {gap}')
        rows=[{'case':i,'feature':feature,'shap_mw':float(phi[i,j]),'base_mw':float(base_values[i]),
               'prediction_mw':float(predicted[i])} for i in range(len(local)) for j,feature in enumerate(names)]
        file=folder/f'{_safe(name)}_shap.parquet';store.parquet(file,pd.DataFrame(rows))
        statuses.append({'model':name,'method':method,
            'cases':len(local),'max_reconstruction_error_mw':gap,'artifact':file.name})
    store.json(folder/'explanations.json',{'importance':importance,'shap':statuses,
        'claim':'Predictive sensitivity on common-source historical rows; not causal outage effects'})
    store.complete(ident,fp,folder/'explanations.json')
    print('NOS EXPLAINED',folder.relative_to(store.root),flush=True)


def explain_risk(c,path):
    store=Store(c);folder=path.parent;result=json.loads(path.read_text())
    ident=str(folder.relative_to(store.root))+'/explanations'
    exposure_path=store.root/'nos/exposure.parquet'
    fp=fingerprint([digest(path),digest(exposure_path),digest(__file__),'risk'])
    if store.valid(ident,fp):return
    fold=next(f for f in folds(c) if f.name==result['fold']['name'])
    d=connector_data(c,c['connectors'][0]);d['base']=base_frame(d);idx=d['y'].index
    base=design(d,np.arange(len(idx)),np.repeat(4,len(idx)),'full').astype(float)
    raw=pd.read_parquet(exposure_path);raw=raw[raw.lead.eq(4)].drop_duplicates('origin').set_index('origin').reindex(idx)
    joined=raw.reset_index(names='origin')
    known=joined.nos_report_generated.notna()
    known &= joined.nos_report_generated.add(pd.Timedelta(minutes=30)).le(joined.origin)
    known &= (joined.origin-joined.nos_report_generated-pd.Timedelta(minutes=30))<=pd.Timedelta(minutes=90)
    masks=mature_masks(idx,idx+pd.Timedelta(minutes=120),fold)
    coverage=json.loads((store.root/'nos/coverage_audit.json').read_text())
    support=next(r for r in coverage['folds'] if r['fold']==fold.name)
    history_start=pd.Timestamp(support['partitions']['train']['fitted_start'])
    train=masks['train']&np.asarray(known)&(idx>=history_start);available=masks['evaluate']&np.asarray(known)
    sample_positions=np.flatnonzero(available)[::max(1,int(available.sum()/256))][:256]
    local_positions=np.linspace(0,len(sample_positions)-1,min(12,len(sample_positions)),dtype=int)
    bundle=joblib.load(folder/'models.joblib');importance=[];statuses=[]
    labels={}
    for direction in ('export','import'):
        detector,_=detect(d['raw'][direction],fold.train_start,fold.train_end)
        labels[direction]=window_label(detector.onset,detector.valid,idx)
    for recipe,families in bundle['models'].items():
        x=_features(base,joined,recipe,known)
        first_family=next(iter(families.values()));expected=next(iter(first_family.values()))[2]
        missing=[column for column in expected if column not in x]
        if missing:raise ValueError(f'NOS risk explanation features missing: {missing}')
        x=x[expected];sample=x.iloc[sample_positions];local=sample.iloc[local_positions]
        background=x.loc[train].iloc[np.linspace(0,train.sum()-1,min(32,train.sum()),dtype=int)]
        for family,directions in families.items():
            for direction,(model,calibration,columns) in directions.items():
                if list(x.columns)!=columns:raise ValueError('NOS risk feature schema mismatch')
                slope=float(calibration.coef_[0,0]);intercept=float(calibration.intercept_[0])
                a=model.transformed(local);bg=model.transformed(background);names=list(expansion(local,'T3',2).columns)
                if getattr(model,'is_constant',False) or family=='logistic':
                    phi=(a-bg.mean(axis=0))*model.model.coef_[0]*slope
                    bases=np.repeat(float((model.model.intercept_[0]+bg.mean(axis=0)@model.model.coef_[0])*slope+intercept),len(local))
                    method='exact calibrated logistic log-odds decomposition'
                else:
                    explanation=shap.TreeExplainer(model.model,feature_perturbation='tree_path_dependent',model_output='raw')(a,check_additivity=True)
                    phi=explanation.values*slope;bases=np.asarray(explanation.base_values)*slope+intercept
                    method='exact path-dependent TreeSHAP raw score followed by fixed calibration slope'
                raw_probability=model.predict(local);logits=np.log(raw_probability/(1-raw_probability))*slope+intercept
                error=float(np.max(abs(bases+phi.sum(axis=1)-logits)))
                if error>1e-3:raise ValueError(f'NOS risk SHAP reconstruction failed: {recipe} {family} {direction}')
                name=recipe+'_'+family+'_'+direction;file=folder/f'{_safe(name)}_shap.parquet'
                store.parquet(file,pd.DataFrame([{'case':i,'feature':feature,'shap_log_odds':float(phi[i,j]),
                    'base_log_odds':float(bases[i]),'prediction_probability':float(1/(1+np.exp(-logits[i])))}
                    for i in range(len(local)) for j,feature in enumerate(names)]))
                statuses.append({'model':name,'method':method,'units':'calibrated log odds','cases':len(local),
                    'max_reconstruction_error':error,'artifact':file.name})
                def predict(z):
                    p=model.predict(z);return calibration.predict_proba(np.log(p/(1-p)).reshape(-1,1))[:,1]
                y=labels[direction][sample_positions];good=np.isfinite(y);initial=predict(sample)
                baseline=float(np.mean((initial[good]-y[good])**2))
                for group,columns in groups(sample.columns).items():
                    shifted=sample.copy();shifted[columns]=np.roll(sample[columns].to_numpy(),max(1,len(sample)//3),axis=0)
                    value=float(np.mean((predict(shifted)[good]-y[good])**2)-baseline)
                    importance.append({'model':name,'group':group,'brier_degradation':value,'n':int(good.sum())})
    store.json(folder/'explanations.json',{'importance':importance,'shap':statuses,
        'claim':'Predictive sensitivity on common-source historical rows; calibrated log-odds units; not causal effects'})
    store.complete(ident,fp,folder/'explanations.json')
    print('NOS RISK EXPLAINED',folder.relative_to(store.root),flush=True)


def explain_refinement(c,path):
    store=Store(c);folder=path.parent;result=json.loads(path.read_text());bundle=joblib.load(folder/'models.joblib')
    ident=str(folder.relative_to(store.root))+'/explanations'
    inputs=[folder/f'{name}_explain_features.parquet' for name in bundle['models']]
    fp=fingerprint([digest(path),[(p.name,digest(p)) for p in inputs],digest(__file__),'refinement'])
    if store.valid(ident,fp):return
    importance=[];statuses=[]
    for name,item in bundle['models'].items():
        model=item['model'];f=pd.read_parquet(folder/f'{name}_explain_features.parquet')
        background=f[f._split.eq('background')].drop(columns=['_split','_actual'])
        sample_rows=f[f._split.eq('sample')];actual=sample_rows._actual.to_numpy()
        sample=sample_rows.drop(columns=['_split','_actual']);prediction=full_prediction(model,sample)
        baseline=metrics(actual,prediction)['mae']
        for group,columns in groups(sample.columns).items():
            losses=[]
            for replicate in range(5):
                shifted=sample.copy();offset=max(1,len(sample)//5)*(replicate+1)
                shifted[columns]=np.roll(sample[columns].to_numpy(),offset%len(sample),axis=0)
                losses.append(metrics(actual,full_prediction(model,shifted))['mae']-baseline)
            importance.append({'model':name,'group':group,'mae_degradation':float(np.mean(losses)),
                               'replicates':losses,'n':len(sample)})
        positions=np.linspace(0,len(sample)-1,min(12,len(sample)),dtype=int);local=sample.iloc[positions]
        a=model.transformed(local);bg=model.transformed(background);names=list(model.names)
        if model.family=='T6':
            explanation=shap.TreeExplainer(model.model,feature_perturbation='tree_path_dependent')(a,check_additivity=True)
            phi=explanation.values.copy();bases=np.asarray(explanation.base_values)+background.own_anchor.mean()
            method='exact path-dependent TreeSHAP correction plus explicit anchor'
        else:
            center=bg.mean(axis=0);phi=(a-center)*model.model.coef_
            bases=np.repeat(float(model.model.intercept_+center@model.model.coef_+background.own_anchor.mean()),len(local))
            method='exact linear transformed-feature decomposition including anchor'
        phi[:,names.index('own_anchor')]+=local.own_anchor.to_numpy()-background.own_anchor.mean()
        predicted=full_prediction(model,local);error=float(np.max(abs(bases+phi.sum(axis=1)-predicted)))
        if error>max(1e-3,1e-5*np.max(abs(predicted))):raise ValueError(f'Refinement SHAP reconstruction failed: {name}')
        file=folder/f'{_safe(name)}_shap.parquet';store.parquet(file,pd.DataFrame([
            {'case':i,'feature':feature,'shap_mw':float(phi[i,j]),'base_mw':float(bases[i]),'prediction_mw':float(predicted[i])}
            for i in range(len(local)) for j,feature in enumerate(names)]))
        statuses.append({'model':name,'method':method,'cases':len(local),'max_reconstruction_error_mw':error,'artifact':file.name})
    store.json(folder/'explanations.json',{'importance':importance,'shap':statuses,
        'claim':'Post-selection refinement sensitivity; not attributed to NOS or diurnal main effects'})
    store.complete(ident,fp,folder/'explanations.json')
    print('REFINEMENT EXPLAINED',folder.relative_to(store.root),flush=True)


def run(config_path=CONFIG):
    c=load_config(config_path)
    with threadpool_limits(limits=2):
        for path in sorted((c['_run']/'nos_models').glob('*/*/result.json')):explain_point(c,path)
        for path in sorted((c['_run']/'nos_risk').glob('*/result.json')):explain_risk(c,path)
        for path in sorted((c['_run']/'refinements').glob('*/*/result.json')):explain_refinement(c,path)


if __name__=='__main__':run()
