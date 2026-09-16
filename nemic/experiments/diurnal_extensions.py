"""Evaluate extended targets/horizons with the primary-fold procedure frozen."""
import argparse
import json
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from threadpoolctl import threadpool_limits

from .core import Store,clean,digest,fingerprint,load_config
from .diurnal import CapacityReference,metrics,origin_weights,periods
from .diurnal_runner import CONFIG,fit_candidate,frame
from .runner import save_model
from .validation import folds


def _source_target(target):
    return target if target.endswith('_tight') else target+'_tight'


def _job(config_path,fold_name,band,target):
    c=load_config(config_path);store=Store(c)
    fold=next(f for f in folds(c) if f.name==fold_name)
    primary_path=store.root/'diurnal'/fold_name/'band0'/_source_target(target)/'result.json'
    primary=json.loads(primary_path.read_text())
    folder=store.root/'diurnal'/fold_name/f'band{band}'/target
    ident=str(folder.relative_to(store.root))
    fp=fingerprint([fold.dict(),band,target,digest(primary_path),digest(__file__)])
    if store.valid(ident,fp):return {'job':ident,'status':'cached'}
    started=time.monotonic();x,meta,masks=frame(c,c['connectors'][0],fold,band,target)
    tr,va,ca,te=[masks[k] for k in ('train','select','calibrate','evaluate')]
    families=list(dict.fromkeys(['T0',primary['selected_family']]))
    predictions={'persistence':meta.anchor.to_numpy(),'seasonal_daily':meta.seasonal_48.to_numpy(),
                 'seasonal_weekly':meta.seasonal_336.to_numpy()}
    models={};references={};search={}
    for family in families:
        name=family+'_mae';source=primary['search'][name]
        model,reference=fit_candidate(family,source['chosen'],x,meta,tr,'mae')
        models[name]=model;references[name]=reference
        predictions[name]=meta.anchor.to_numpy()+model.predict(x)
        search[name]={'family':family,'objective':'mae','chosen':source['chosen'],
            'actual_parameters':model.base.model.get_params() if family=='T4' else model.model.get_params(),
            'profile':source['profile'],'history':[],
            'stop':'procedure and hyperparameters frozen from this fold primary target/band before extension evaluation',
            'frozen_from':str(primary_path.relative_to(store.root)),'frozen_from_sha256':digest(primary_path)}
    selection={name:float(np.average(abs(meta.actual.to_numpy()[va]-p[va]),
        weights=origin_weights(meta.loc[va,'origin']))) for name,p in predictions.items()}
    winner=min(selection,key=selection.get)
    selected_family=min((n for n in models),key=selection.get).split('_')[0]
    reference_model=CapacityReference().fit(meta.loc[tr].drop_duplicates('origin').anchor)
    reference=reference_model.predict(meta.anchor)
    evaluated=meta.loc[te].copy();evaluated['period']=periods(evaluated.delivery)
    scores=[]
    for name,p in predictions.items():
        evaluated[name]=p[te]
        scores.append({'model':name,'selected':name==winner,'selection_mae':selection[name],
            **metrics(meta.actual.to_numpy()[te],p[te],reference[te],origin_weights(meta.loc[te,'origin']))})
    evaluated['reference']=reference[te]
    residual=meta.actual.to_numpy()[ca]-predictions[winner][ca]
    quantiles=[.025,.1,.5,.9,.975];pooled=np.quantile(residual,quantiles)
    group=periods(meta.loc[ca,'delivery']);adjustments={j:np.quantile(residual[group==j],quantiles)
        if sum(group==j)>=100 else pooled for j in range(5)}
    intervals=[]
    for mode in ('pooled','period'):
        adj=np.tile(pooled,(len(evaluated),1)) if mode=='pooled' else np.stack([adjustments[int(j)] for j in evaluated.period])
        qpred=evaluated[winner].to_numpy()[:,None]+adj
        for k,q in enumerate(quantiles):evaluated[f'{mode}_q{q}']=qpred[:,k]
        for lower,upper,nominal in ((0,4,.95),(1,3,.8)):
            y=evaluated.actual.to_numpy();width=qpred[:,upper]-qpred[:,lower]
            score=width+2/(1-nominal)*(np.maximum(qpred[:,lower]-y,0)+np.maximum(y-qpred[:,upper],0))
            intervals.append({'mode':mode,'nominal':nominal,'coverage':float(np.mean((y>=qpred[:,lower])&(y<=qpred[:,upper]))),
                              'width':float(width.mean()),'interval_score':float(score.mean())})
    artifacts=[];path=store.parquet(folder/'predictions.parquet',evaluated)
    artifacts.append({'path':str(path.relative_to(store.root)),'sha256':digest(path)})
    for name,model in models.items():
        path=folder/f'{name}.joblib';save_model(store,path,model)
        artifacts.append({'path':str(path.relative_to(store.root)),'sha256':digest(path)})
    bundle={'winner':winner,'models':models,'reference':reference_model,'pooled_adjustments':pooled,
        'period_adjustments':adjustments,'quantiles':quantiles,'fold':fold.dict(),'target':target,'band':band,
        'information_track':'retrospective reconstructed network','operationally_eligible':False,'input_columns':list(x.columns)}
    path=folder/'policy.joblib';save_model(store,path,bundle)
    artifacts.append({'path':str(path.relative_to(store.root)),'sha256':digest(path)})
    result={'fold':fold.dict(),'target':target,'band':band,'winner':winner,'selected_family':selected_family,
        'scores':scores,'intervals':intervals,'selection':selection,'search':search,'artifacts':artifacts,
        'seconds':time.monotonic()-started,'training_pairs':int(tr.sum()),
        'information_track':'retrospective reconstructed network','claim':'development only; primary-fold procedure frozen'}
    store.json(folder/'result.json',result);store.complete(ident,fp,folder/'result.json')
    print('EXTENSION',ident,winner,round(result['seconds'],1),flush=True)
    return {'job':ident,'winner':winner,'seconds':result['seconds']}


def job(args):
    with threadpool_limits(limits=2):return _job(*args)


def run_extensions(config_path=CONFIG,fold_name=None):
    c=load_config(config_path);jobs=[]
    for fold in folds(c):
        if fold_name and fold.name!=fold_name:continue
        for band in range(len(c['bands'])):
            for target in c['targets']:
                if band==0 and target.endswith('_tight'):continue
                jobs.append((config_path,fold.name,band,target))
    Store(c).json(c['_run']/f'frozen_extensions_{fold_name or "all"}_manifest.json',
        {'jobs':jobs,'objective':'mae','procedure':'fold-primary shortlist and hyperparameters frozen'})
    with ProcessPoolExecutor(max_workers=c['limits']['workers']) as pool:
        for result in pool.map(job,jobs):print(json.dumps(clean(result)),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=CONFIG);p.add_argument('--fold')
    a=p.parse_args();run_extensions(a.config,a.fold)
