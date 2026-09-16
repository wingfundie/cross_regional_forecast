"""Research bundle handoff with exact schemas, parameters and prediction parity."""
import json
import platform
import importlib.metadata
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from .core import Store,load_config,digest,clean
from .validation import Fold
from .diurnal_runner import CONFIG,frame,fit_candidate
from .diurnal import periods,origin_weights,CapacityReference
from .runner import save_model


def predict_bundle(bundle, features):
    if list(features.columns)!=bundle['input_columns']:
        raise ValueError('Bundle feature schema/order mismatch')
    if not np.isfinite(features.own_anchor).all():
        raise ValueError('A finite issue-known persistence anchor is required')
    name=bundle['winner']
    if name=='persistence':p=features.own_anchor.to_numpy()
    elif name.startswith('seasonal_'):
        raise ValueError('Seasonal policy requires the packaged history adapter')
    else:p=features.own_anchor.to_numpy()+bundle['models'][name].predict(features)
    return p


def refit_final(config_path=CONFIG):
    c=load_config(config_path);store=Store(c);end=pd.Timestamp(c['end'])
    fold=Fold('final','refit',c['start'],str((end-pd.DateOffset(months=6)).date()),
              str((end-pd.DateOffset(months=3)).date()),str((end-pd.DateOffset(months=1)).date()),str(end.date()),str(end.date()))
    catalogue=[]
    with threadpool_limits(limits=2):
        for band in range(len(c['bands'])):
            for target in c['targets']:
                previous=store.root/'diurnal/2026-08'/f'band{band}'/target/'result.json'
                if not previous.exists():raise ValueError(f'Latest historical cell missing: {previous}')
                prior=json.loads(previous.read_text());folder=store.root/'final'/f'band{band}'/target
                x,meta,masks=frame(c,c['connectors'][0],fold,band,target)
                tr,va,ca=[masks[k] for k in ('train','select','calibrate')]
                predictions={'persistence':meta.anchor.to_numpy()};models={};history={}
                # Family shortlist and parameters came from earlier training/selection, not an evaluation leaderboard.
                for family in dict.fromkeys(['T0',prior['selected_family']]):
                    name=family+'_mae';source=prior['search'][name]
                    model,reference=fit_candidate(family,source['chosen'],x,meta,tr,'mae')
                    models[name]=model;history[name]={**source,
                        'refit_policy':'family and hyperparameters frozen from August 2026 historical selection'}
                    predictions[name]=meta.anchor.to_numpy()+model.predict(x)
                scores={name:float(np.average(abs(meta.actual.to_numpy()[va]-p[va]),weights=origin_weights(meta.loc[va,'origin']))) for name,p in predictions.items()}
                winner=min(scores,key=scores.get)
                residual=meta.actual.to_numpy()[ca]-predictions[winner][ca]
                levels=[.025,.1,.5,.9,.975];pooled=np.quantile(residual,levels)
                group=periods(meta.loc[ca,'delivery'])
                adjustments={j:np.quantile(residual[group==j],levels) if sum(group==j)>=100 else pooled for j in range(5)}
                refit_mask=tr|va|ca|masks['alert'];final_models={}
                for family in dict.fromkeys(['T0',prior['selected_family']]):
                    name=family+'_mae';source=prior['search'][name]
                    final_models[name],_=fit_candidate(family,source['chosen'],x,meta,refit_mask,'mae')
                bundle={'winner':winner,'models':final_models,'input_columns':list(x.columns),'fold':fold.dict(),
                    'target':target,'band':band,'quantiles':levels,'pooled_adjustments':pooled,
                    'period_adjustments':adjustments,'reference':CapacityReference().fit(meta.loc[refit_mask].drop_duplicates('origin').anchor),
                    'information_track':'retrospective reconstructed network','operationally_eligible':False,
                    'selection_metric':'mae','mape_role':'assessment_only','observation_delay_minutes':30,
                    'parameters':{k:(v.base.model.get_params() if k.startswith('T4_') else v.model.get_params()) for k,v in final_models.items()},
                    'refit_pairs':int(refit_mask.sum()),
                    'calibration_policy':'interval residual adjustments estimated before full-history point-model refit'}
                path=folder/'model.joblib';save_model(store,path,bundle)
                sample=x.loc[masks['alert']].iloc[:20]
                expected=predict_bundle(bundle,sample);loaded=joblib.load(path)
                np.testing.assert_allclose(expected,predict_bundle(loaded,sample),rtol=1e-10,atol=1e-8)
                store.parquet(folder/'example_features.parquet',sample)
                store.parquet(folder/'example_predictions.parquet',pd.DataFrame({'prediction_mw':expected}))
                manifest={'winner':winner,'selection_mae':scores,'parameters':bundle['parameters'],
                    'model_sha256':digest(path),'schema':list(x.columns),'fold':fold.dict(),
                    'python':platform.python_version(),'packages':{n:importlib.metadata.version(n) for n in
                        ['numpy','pandas','scikit-learn','lightgbm','optuna','shap','joblib']},
                    'information_track':bundle['information_track'],'operationally_eligible':False,
                    'refit_pairs':bundle['refit_pairs'],'calibration_policy':bundle['calibration_policy'],
                    'reload_parity':'passed','claim':'Full-history frozen-procedure research bundle; historical scores belong to rolling models, not this new refit'}
                store.json(folder/'manifest.json',manifest)
                catalogue.append({'target':target,'band':band,'winner':winner,'path':str(path.relative_to(store.root)),'sha256':digest(path)})
                print('REFIT',target,band,winner,flush=True)
    store.json(store.root/'final/catalogue.json',catalogue)
    return catalogue


if __name__=='__main__':refit_final()
