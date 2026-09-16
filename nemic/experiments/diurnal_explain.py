"""Full-predictor explanations: corrections plus persistence in MW."""
import json
import numpy as np
import pandas as pd
import joblib
import shap
from threadpoolctl import threadpool_limits

from .core import Store, load_config, fingerprint, digest
from .diurnal_runner import frame, CONFIG
from .validation import Fold, folds
from .diurnal import metrics


def full_prediction(model, x):
    return x.own_anchor.to_numpy() + model.predict(x)


def groups(columns):
    result = {}
    for name in columns:
        if name.startswith('nos_'):
            group = 'scheduled_outage'
        elif name.startswith(('hour_', 'year_', 'daily_')) or name == 'weekend':
            group = 'calendar'
        elif '_gen_' in name or 'pressure' in name or 'relief' in name:
            group = 'generator_pressure'
        elif 'lag' in name or 'delta' in name or name == 'own_anchor':
            group = 'observed_history'
        elif 'fraction' in name or 'inconsistent' in name:
            group = 'quality'
        elif name in ('lead','log_lead'):
            group = 'horizon'
        else:
            group = 'network_state'
        result.setdefault(group, []).append(name)
    return result


def explain_job(c, result_path):
    store = Store(c); result = json.loads(result_path.read_text()); folder = result_path.parent
    ident = str(folder.relative_to(store.root)) + '/explanations'
    fp = fingerprint([digest(result_path), digest(__file__)])
    if store.valid(ident, fp):
        return
    fold = next((f for f in folds(c) if f.name == result['fold']['name']),
                Fold(**result['fold']))
    x, meta, masks = frame(c, c['connectors'][0], fold, result['band'], result['target'])
    # Deterministic complete-day sample shared by every candidate in this cell.
    dates = meta.loc[masks['evaluate'], 'origin'].dt.normalize().unique()
    chosen_dates = dates[np.linspace(0, len(dates)-1, min(5,len(dates)), dtype=int)]
    sample = masks['evaluate'] & meta.origin.dt.normalize().isin(chosen_dates)
    xs = x.loc[sample].reset_index(drop=True); ms = meta.loc[sample].reset_index(drop=True)
    train = x.loc[masks['train']]
    background = train.iloc[np.linspace(0, len(train)-1, min(32,len(train)), dtype=int)]
    local_positions=np.linspace(0,len(xs)-1,min(12,len(xs)),dtype=int)
    local = xs.iloc[local_positions]
    importance, statuses = [], []
    for name,column,feature in [('persistence','anchor','latest_observed_directional_limit'),
                                ('seasonal_daily','seasonal_48','daily_seasonal_reference'),
                                ('seasonal_weekly','seasonal_336','weekly_seasonal_reference')]:
        values=ms[column].to_numpy();base=float(values.mean());chosen=values[local_positions]
        store.parquet(folder/f'{name}_shap.parquet',pd.DataFrame({'case':np.arange(len(local)),
            'feature':feature,'shap_mw':chosen-base,'base_mw':base,'prediction_mw':chosen}))
        statuses.append({'model':name,'method':'exact one-input reference decomposition','cases':len(local),
            'max_reconstruction_error_mw':0.,'background':'shared deterministic evaluation sample; reference model has no fitted training parameters'})
        shifted=np.roll(values,max(1,len(values)//5))
        degradation=float(metrics(ms.actual.to_numpy(),shifted)['mae']-metrics(ms.actual.to_numpy(),values)['mae'])
        importance.append({'model':name,'group':'observed_history','mae_degradation':degradation,
                           'replicates':[degradation],'n':len(xs)})
    for name in result['search']:
        model = joblib.load(folder / f'{name}.joblib')
        prediction = full_prediction(model, xs); baseline = metrics(ms.actual.to_numpy(), prediction)['mae']
        rng = np.random.default_rng(741)
        for group, names in groups(xs.columns).items():
            losses = []
            for replicate in range(5):
                perturbed = xs.copy()
                if group == 'calendar':
                    # Daily phase changes must actually alter hour-of-day.
                    phase = np.arctan2(xs.hour_sin, xs.hour_cos).to_numpy()
                    offset = {day: rng.integers(1,48) for day in ms.origin.dt.normalize().unique()}
                    shifted = phase + ms.origin.dt.normalize().map(offset).to_numpy() * 2*np.pi/48
                    perturbed['hour_sin'], perturbed['hour_cos'] = np.sin(shifted), np.cos(shifted)
                else:
                    # Shift complete chronological blocks; preserve grouped feature structure.
                    n = len(perturbed); shift = max(1, n // 5) * (replicate + 1)
                    perturbed[names] = np.roll(xs[names].to_numpy(), shift % n, axis=0)
                losses.append(metrics(ms.actual.to_numpy(), full_prediction(model, perturbed))['mae'] - baseline)
            importance.append({'model':name, 'group':group, 'mae_degradation':float(np.mean(losses)),
                               'replicates':losses, 'n':len(xs)})
        # Linear explanations in transformed space have exact additive MW units.
        if model.family not in ('T4','T5','T6'):
            a = model.transformed(local); bg = model.transformed(background).mean(axis=0)
            phi = (a-bg) * model.model.coef_
            names = list(model.names)
            base = float(model.model.intercept_ + bg @ model.model.coef_ + background.own_anchor.mean())
            phi[:, names.index('own_anchor')] += local.own_anchor.to_numpy() - background.own_anchor.mean()
            base_values = np.repeat(base,len(local)); method = 'exact interventional linear transformed-feature decomposition including anchor'
        elif model.family == 'T6':
            # HistGradientBoosting's interventional approximation can fail SHAP's
            # additivity check even when the fitted feature schema is identical.
            # The path-dependent decomposition is exact for the fitted tree
            # ensemble and still uses training-node counts as its background.
            explainer = shap.TreeExplainer(model.model, feature_perturbation='tree_path_dependent')
            explanation = explainer(model.transformed(local), check_additivity=True)
            phi = explanation.values.copy(); names = list(model.names)
            phi[:, names.index('own_anchor')] += local.own_anchor.to_numpy() - background.own_anchor.mean()
            base_values = np.asarray(explanation.base_values) + background.own_anchor.mean()
            method = 'exact path-dependent TreeSHAP correction plus explicit anchor'
        else:
            def predict(values):
                return full_prediction(model, pd.DataFrame(values, columns=x.columns))
            explainer = shap.Explainer(predict, background, algorithm='permutation', seed=741)
            explanation = explainer(local, max_evals=2*len(x.columns)+1)
            phi = explanation.values; names = list(x.columns); base_values = explanation.base_values
            method = 'full-predictor permutation SHAP; one permutation path, approximation'
        predicted = full_prediction(model, local)
        gap = np.max(abs(base_values + phi.sum(axis=1) - predicted))
        if gap > max(1e-3, 1e-5 * np.max(abs(predicted))):
            raise ValueError(f'SHAP reconstruction failed: {name}: {gap}')
        rows = []
        for i in range(len(local)):
            for j, feature in enumerate(names):
                rows.append({'case':i, 'feature':feature, 'shap_mw':float(phi[i,j]),
                             'base_mw':float(base_values[i]), 'prediction_mw':float(predicted[i])})
        store.parquet(folder / f'{name}_shap.parquet', pd.DataFrame(rows))
        statuses.append({'model':name, 'method':method, 'cases':len(local), 'max_reconstruction_error_mw':float(gap),
                         'background':'32 deterministic chronological training rows; no evaluation rows'})
    store.json(folder / 'explanations.json', {'importance':importance, 'shap':statuses,
               'claim':'Predictive sensitivity, not causal fundamentals; sampled evaluation diagnostics'})
    store.complete(ident, fp, folder / 'explanations.json')
    print('EXPLAINED', folder.relative_to(store.root), flush=True)


def run(config_path=CONFIG):
    c=load_config(config_path)
    with threadpool_limits(limits=2):
        for path in sorted((c['_run']/'diurnal').glob('*/band*/*/result.json')):
            explain_job(c,path)
        explain_risk(c)


def explain_risk(c):
    from .data import connector_data,base_frame,design
    from .diurnal import mature_masks
    from .events import detect,window_label
    store=Store(c);d=connector_data(c,c['connectors'][0]);d['base']=base_frame(d);idx=d['y'].index
    x=design(d,np.arange(len(idx)),np.repeat(4,len(idx)),'full').astype(float)
    for folder in sorted((store.root/'risk').glob('*')):
        if not (folder/'models.joblib').exists():continue
        bundle=joblib.load(folder/'models.joblib')
        fold=next(f for f in folds(c) if f.name==folder.name)
        masks=mature_masks(idx,idx+pd.Timedelta(minutes=120),fold)
        background=x.loc[masks['train']].iloc[::max(1,int(masks['train'].sum()/32))].iloc[:32]
        sample=x.loc[masks['evaluate']].iloc[::max(1,int(masks['evaluate'].sum()/256))].iloc[:256]
        local=sample.iloc[:12]
        statuses=[];importance=[]
        for family,models in bundle['models'].items():
            for direction,(model,calibration) in models.items():
                slope=float(calibration.coef_[0,0]);intercept=float(calibration.intercept_[0])
                a=model.transformed(local);bg=model.transformed(background)
                from .diurnal import expansion
                names=list(expansion(local,'T3',2).columns)
                if getattr(model,'is_constant',False) or family=='logistic':
                    phi=(a-bg.mean(axis=0))*model.model.coef_[0]*slope
                    base=float((model.model.intercept_[0]+bg.mean(axis=0)@model.model.coef_[0])*slope+intercept)
                    bases=np.repeat(base,len(local))
                else:
                    explanation=shap.TreeExplainer(model.model,feature_perturbation='tree_path_dependent',model_output='raw')(a,check_additivity=True)
                    phi=explanation.values*slope;bases=np.asarray(explanation.base_values)*slope+intercept
                raw=model.predict(local);logits=np.log(raw/(1-raw))*slope+intercept
                error=float(np.max(abs(bases+phi.sum(axis=1)-logits)))
                if error>1e-3:raise ValueError('Calibrated risk log-odds SHAP reconstruction failed')
                name=family+'_'+direction
                store.parquet(folder/f'{name}_shap.parquet',pd.DataFrame([
                    {'case':i,'feature':n,'shap_log_odds':float(phi[i,j]),'base_log_odds':float(bases[i]),
                     'prediction_probability':float(1/(1+np.exp(-logits[i])))} for i in range(len(local)) for j,n in enumerate(names)]))
                statuses.append({'model':name,'units':'calibrated log odds','cases':len(local),'reconstruction_error':error})
                detector,_=detect(d['raw'][direction],fold.train_start,fold.train_end)
                y=window_label(detector.onset,detector.valid,idx)[sample.index]
                def predict(z):
                    p=model.predict(z);return calibration.predict_proba(np.log(p/(1-p)).reshape(-1,1))[:,1]
                initial=predict(sample);good=np.isfinite(y);base_loss=float(np.mean((initial[good]-y[good])**2))
                for group,names in groups(sample.columns).items():
                    modified=sample.copy();modified[names]=np.roll(modified[names].to_numpy(),max(1,len(sample)//3),axis=0)
                    prediction=predict(modified)
                    importance.append({'model':name,'group':group,'brier_degradation':float(np.mean((prediction[good]-y[good])**2)-base_loss)})
        store.json(folder/'explanations.json',{'shap':statuses,'importance':importance,'claim':'Sampled predictive sensitivity; calibrated log-odds decompositions are not MW effects'})


if __name__ == '__main__':
    run()
