"""Executable VNI-first v2 campaign; held-out MAE selects the routed policy."""
import argparse
import json
import time
import hashlib
from concurrent.futures import ProcessPoolExecutor

import joblib
import numpy as np
import optuna
import pandas as pd
from threadpoolctl import threadpool_limits

from .core import Store, clean, load_config, fingerprint, digest
from .data import connector_data, base_frame, design, inventory
from .validation import folds
from .diurnal import (DiurnalModel, ResidualCorrection, CapacityReference, origin_weights,
                      mature_masks, metrics, periods)
from .runner import save_model

CONFIG = 'configs/experiments/vni_diurnal_nos_v2.json'


def frame(c, ic, fold, band, target):
    d = connector_data(c, ic); d['base'] = base_frame(d)
    idx = d['y'].index
    lo, hi = c['bands'][band]; leads = [h for h in c['leads'] if lo <= h <= hi]
    o = np.repeat(np.arange(len(idx)), len(leads)); h = np.tile(leads, len(idx))
    good = (o > 0) & (o + h < len(idx))
    o, h = o[good], h[good]
    anchor = d['y'][target].to_numpy()[o - 1]; actual = d['y'][target].to_numpy()[o + h]
    good = np.isfinite(anchor) & np.isfinite(actual) & (idx[o] >= pd.Timestamp(fold.train_start))
    o, h, anchor, actual = o[good], h[good], anchor[good], actual[good]
    meta = pd.DataFrame({'origin': idx[o], 'delivery': idx[o + h], 'lead': h,
                         'actual': actual, 'anchor': anchor})
    x = design(d, o, h, 'full').astype('float64')
    x['own_anchor'] = anchor
    masks = mature_masks(pd.DatetimeIndex(meta.origin), pd.DatetimeIndex(meta.delivery), fold)
    for period in (48, 336):
        previous = o + h - np.ceil((h + 1) / period).astype(int) * period
        ref = np.full(len(o), np.nan); valid = previous >= 0
        ref[valid] = d['y'][target].to_numpy()[previous[valid]]
        meta[f'seasonal_{period}'] = np.where(np.isfinite(ref), ref, anchor)
    return x, meta, masks


def inner_windows(meta, mask):
    end = pd.DatetimeIndex(meta.loc[mask, 'origin']).max().normalize()
    windows = []
    for offset in (60, 30):
        start = end - pd.Timedelta(days=offset)
        stop = start + pd.Timedelta(days=30)
        train = mask & (meta.delivery + pd.Timedelta(minutes=30) < start)
        valid = mask & (meta.origin >= start) & (meta.delivery + pd.Timedelta(minutes=30) < stop)
        if train.sum() >= 500 and valid.sum() >= 100:
            windows.append((np.asarray(train), np.asarray(valid)))
    if len(windows) < 2:
        raise ValueError('Insufficient chronological inner windows')
    return windows


def harmonic_profile(x, meta, train):
    # Candidate complexity from stable daily correction profiles; no validation targets.
    f = meta.loc[train, ['delivery', 'actual', 'anchor']].copy()
    f['slot'] = f.delivery.dt.hour * 2 + f.delivery.dt.minute // 30
    f['correction'] = f.actual - f.anchor
    profile = f.groupby('slot').correction.mean().reindex(range(48)).fillna(0).to_numpy()
    energy = abs(np.fft.rfft(profile - profile.mean()))**2
    chosen = np.flatnonzero(np.cumsum(energy[1:]) >= .95 * energy[1:].sum())
    k = max(2, min(23, int(chosen[0]) + 1 if len(chosen) else 2))
    return {'harmonics': k, 'harmonic_energy': energy.tolist()}


def fit_candidate(family, settings, x, meta, mask, objective):
    m = meta.loc[mask]
    reference = CapacityReference().fit(m.drop_duplicates('origin').anchor)
    weights = origin_weights(m.origin)
    if objective == 'dr_nmae':
        total = weights.sum(); weights /= reference.predict(m.anchor); weights *= total / weights.sum()
    model = (ResidualCorrection(settings['complexity'], settings['harmonics']) if family == 'T4'
             else DiurnalModel(family, settings['complexity'], settings['harmonics'], settings.get('tree')))
    model.fit(x.loc[mask], (m.actual - m.anchor).to_numpy(), weights, m.origin.to_numpy())
    return model, reference


def tune(family, x, meta, train, objective, folder, store):
    data_hash=hashlib.sha256(pd.util.hash_pandas_object(x.loc[train],index=True).to_numpy().tobytes()
        +pd.util.hash_pandas_object(meta.loc[train],index=True).to_numpy().tobytes()).hexdigest()
    tune_fp=fingerprint([family,objective,data_hash,digest(__file__),digest(__file__.replace('diurnal_runner.py','diurnal.py'))])
    cache=folder/f'{family}_{objective}_fit.joblib'; search_path=folder/f'{family}_{objective}_search.json'
    if cache.exists() and search_path.exists():
        saved=json.loads(search_path.read_text())
        if saved.get('fingerprint')==tune_fp and saved.get('fit_sha256')==digest(cache):
            fitted=joblib.load(cache)
            return fitted['model'],fitted['reference'],saved
    windows = inner_windows(meta, train)
    profile = harmonic_profile(x, meta, windows[0][0])
    origins = meta.loc[windows[0][0], 'origin'].nunique()
    settings = []
    for fraction in (.05, .15, .35, .65, .9, .99):
        settings.append({'complexity': fraction, 'harmonics': profile['harmonics']})
    history = []
    def evaluate(setting):
        started = time.monotonic(); losses = []; daily = []
        for tr, va in windows:
            # Complexity is proposed on earliest inner training; numerical penalties fitted locally.
            local = dict(setting); local['harmonics'] = harmonic_profile(x, meta, tr)['harmonics']
            model, reference = fit_candidate(family, local, x, meta, tr, objective)
            prediction = meta.loc[va, 'anchor'].to_numpy() + model.predict(x.loc[va])
            error = abs(meta.loc[va, 'actual'].to_numpy() - prediction)
            if objective == 'dr_nmae':
                error = 100 * error / reference.predict(meta.loc[va, 'anchor'])
            losses.append(float(np.average(error, weights=origin_weights(meta.loc[va, 'origin']))))
            daily.extend(pd.DataFrame({'day': meta.loc[va, 'origin'].dt.normalize(), 'loss': error}).groupby('day').loss.mean().tolist())
        row = {'settings': setting, 'loss': float(np.mean(losses)), 'block_losses': losses,
               'seconds': time.monotonic() - started, 'daily_loss_se': float(np.std(daily) / np.sqrt(max(len(daily) / 7, 1)))}
        history.append(row)
        return row['loss']
    if family == 'T6':
        max_leaves = max(4, min(63, int(np.sqrt(origins))))
        min_leaf = max(20, int(origins / max_leaves))
        # Learning-rate probes are benchmark-relative, with round bounds measured
        # on chronological training/validation curves before the Optuna search.
        pilots = []
        import lightgbm as lgb
        ptr, pva = windows[0]
        for rate in (.02, .04, .08):
            probe, reference = fit_candidate(family, {'complexity': .65,
                'harmonics': profile['harmonics'], 'tree': {'num_leaves': max(4, min(15, max_leaves)),
                'min_child_samples': min_leaf, 'learning_rate': rate, 'n_estimators': 400}}, x, meta, ptr, objective)
            a = probe.transformed(x.loc[pva]); anchor = meta.loc[pva, 'anchor'].to_numpy()
            actual = meta.loc[pva, 'actual'].to_numpy()
            weights = origin_weights(meta.loc[pva, 'origin'])
            if objective == 'dr_nmae':
                weights = weights / reference.predict(anchor)
            curve = [{'round': r, 'loss': float(np.average(abs(actual - anchor - probe.model.booster_.predict(a, num_iteration=r, num_threads=2)), weights=weights))}
                     for r in (25, 50, 100, 200, 400)]
            best_round = min(curve, key=lambda r: r['loss'])
            pilots.append({'rate': rate, 'curve': curve, 'best_round': best_round['round'], 'best_loss': best_round['loss']})
        best_pilot = min(pilots, key=lambda p: p['best_loss'])
        rounds = sorted(set(p['best_round'] for p in pilots))
        rate_low, rate_high = min(p['rate'] for p in pilots), max(p['rate'] for p in pilots)
        profile['tree_pilots'] = pilots
        profile['round_boundary_unresolved'] = best_pilot['best_round'] == 400
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        study = optuna.create_study(direction='minimize', sampler=optuna.samplers.TPESampler(seed=741))
        def objective_fn(trial):
            leaves = trial.suggest_int('num_leaves', 4, max_leaves, log=True)
            tree = {'num_leaves': leaves, 'min_child_samples': trial.suggest_int('min_child_samples', min_leaf, max(min_leaf + 1, origins // 8), log=True),
                    'learning_rate': trial.suggest_float('learning_rate', rate_low, rate_high, log=True),
                    'n_estimators': trial.suggest_categorical('n_estimators', rounds)}
            return evaluate({'complexity': .65, 'harmonics': profile['harmonics'], 'tree': tree})
        study.optimize(objective_fn, n_trials=7)
        # Two further batches test whether gain exceeds chronological block noise.
        stable = 0
        while stable < 2 and len(history) < 31:
            previous = min(r['loss'] for r in history)
            study.optimize(objective_fn, n_trials=4)
            best = min(history, key=lambda r: r['loss'])
            stable = stable + 1 if previous - best['loss'] <= best['daily_loss_se'] else 0
        stop = ('two batches below block-noise floor; pilot boundary remains unresolved'
                if profile['round_boundary_unresolved'] else 'two batches below block-noise floor') if stable >= 2 else 'budget-limited; not convergence'
    else:
        for setting in settings:
            evaluate(setting)
        stop = 'profile-derived EDF path assessed; finite-path result, not global optimum'
    best = min(history, key=lambda r: r['loss'])
    # Prefer the smallest EDF among settings within the best model's noise allowance.
    if family != 'T6':
        best = min((r for r in history if r['loss'] <= best['loss'] + best['daily_loss_se']), key=lambda r: r['settings']['complexity'])
    final_settings = dict(best['settings']); final_settings['harmonics'] = harmonic_profile(x, meta, train)['harmonics']
    model, reference = fit_candidate(family, final_settings, x, meta, train, objective)
    payload = {'family': family, 'objective': objective, 'history': history, 'chosen': final_settings,
               'stop': stop, 'profile': profile, 'training_origins': int(meta.loc[train, 'origin'].nunique()),
               'training_pairs': int(train.sum()), 'p90_trial_seconds': float(np.quantile([r['seconds'] for r in history], .9)),
               'actual_parameters': model.base.model.get_params() if family == 'T4' else model.model.get_params()}
    save_model(store,cache,{'model':model,'reference':reference})
    payload.update(fingerprint=tune_fp,data_sha256=data_hash,fit_sha256=digest(cache))
    profile_model=model.base if family=='T4' else model
    training=meta.loc[train]
    payload['data_shape']={'origins':int(training.origin.nunique()),'pairs':len(training),
        'days':int(training.origin.dt.normalize().nunique()),'features':len(x.columns),
        'expanded_rank':profile_model.rank,'rank99':profile_model.rank99,
        'constant_columns':x.loc[train].nunique().loc[lambda s:s<=1].index.tolist(),
        'missing_fractions':x.loc[train].isna().mean().to_dict(),
        'target_quantiles':training.actual.quantile([0,.01,.1,.5,.9,.99,1]).to_dict(),
        'reference_floor':reference.floor,'reference_median':reference.median,
        'sum_origin_weights':float(origin_weights(training.origin).sum())}
    store.json(search_path, payload)
    return model, reference, payload


def job(args):
    with threadpool_limits(limits=2):
        return _job(*args)


def _job(config_path, fold_name, band, target, source_fp):
    c = load_config(config_path); store = Store(c)
    fold = next(f for f in folds(c) if f.name == fold_name)
    folder = store.root / 'diurnal' / fold_name / f'band{band}' / target
    ident = str(folder.relative_to(store.root)); fp = fingerprint([source_fp, ident, digest(__file__), digest(__file__.replace('diurnal_runner.py', 'diurnal.py'))])
    if store.valid(ident, fp):
        return {'job': ident, 'status': 'cached'}
    started = time.monotonic()
    x, meta, masks = frame(c, c['connectors'][0], fold, band, target)
    tr, va, ca, te = [masks[k] for k in ('train', 'select', 'calibrate', 'evaluate')]
    if min(tr.sum(), va.sum(), ca.sum(), te.sum()) < 100:
        raise ValueError('Insufficient fold support')
    families = list(c['calendar']['families'])
    if band != 0 or target in ('export', 'import'):
        primary = store.root / 'diurnal' / fold_name / 'band0' / (target if target.endswith('_tight') else target + '_tight') / 'result.json'
        selected = json.loads(primary.read_text())['selected_family']
        families = list(dict.fromkeys(['T0', selected]))
    predictions = {'persistence': meta.anchor.to_numpy(), 'seasonal_daily': meta.seasonal_48.to_numpy(), 'seasonal_weekly': meta.seasonal_336.to_numpy()}
    models, references, search = {}, {}, {}
    for family in families:
        name = family + '_mae'
        model, ref, log = tune(family, x, meta, tr, 'mae', folder, store)
        models[name] = model; references[name] = ref; search[name] = log
        predictions[name] = meta.anchor.to_numpy() + model.predict(x)
        print(ident, name, 'selection MAE', round(float(abs(meta.actual.to_numpy()[va] - predictions[name][va]).mean()), 3), flush=True)
    selected_families = sorted(models, key=lambda n: np.average(abs(meta.actual.to_numpy()[va] - predictions[n][va]), weights=origin_weights(meta.loc[va, 'origin'])))[:2]
    if band == 0 and target.endswith('_tight'):
        for selected in selected_families:
            family = selected.split('_')[0]; name = family + '_dr_nmae'
            model, ref, log = tune(family, x, meta, tr, 'dr_nmae', folder, store)
            models[name] = model; references[name] = ref; search[name] = log
            predictions[name] = meta.anchor.to_numpy() + model.predict(x)
    selection = {name: float(np.average(abs(meta.actual.to_numpy()[va] - p[va]), weights=origin_weights(meta.loc[va, 'origin']))) for name, p in predictions.items()}
    winner = min(selection, key=selection.get)
    selected_family = min((n for n in models if n.endswith('_mae')), key=selection.get).split('_')[0]
    ref = CapacityReference().fit(meta.loc[tr].drop_duplicates('origin').anchor)
    reference = ref.predict(meta.anchor)
    evaluated = meta.loc[te].copy(); evaluated['period'] = periods(evaluated.delivery)
    scores, artifacts, intervals = [], [], []
    for name, p in predictions.items():
        evaluated[name] = p[te]
        scores.append({'model': name, 'selected': name == winner, 'selection_mae': selection[name],
                       **metrics(meta.actual.to_numpy()[te], p[te], reference[te], origin_weights(meta.loc[te, 'origin']))})
    evaluated['reference'] = reference[te]
    calibration = meta.loc[ca, ['delivery', 'actual']].copy()
    residual = calibration.actual.to_numpy() - predictions[winner][ca]
    quantiles = [.025, .1, .5, .9, .975]
    pooled = np.quantile(residual, quantiles)
    group = periods(calibration.delivery); adjustments = {}
    for j in range(5):
        m = group == j
        adjustments[j] = np.quantile(residual[m], quantiles) if m.sum() >= 100 else pooled
    for mode in ('pooled', 'period'):
        adj = np.tile(pooled, (len(evaluated), 1)) if mode == 'pooled' else np.stack([adjustments[int(j)] for j in evaluated.period])
        qpred = evaluated[winner].to_numpy()[:, None] + adj
        for k, q in enumerate(quantiles):
            evaluated[f'{mode}_q{q}'] = qpred[:, k]
        for lower, upper, nominal in ((0, 4, .95), (1, 3, .8)):
            y = evaluated.actual.to_numpy(); width = qpred[:, upper] - qpred[:, lower]
            score = width + 2 / (1 - nominal) * (np.maximum(qpred[:, lower] - y, 0) + np.maximum(y - qpred[:, upper], 0))
            intervals.append({'mode': mode, 'nominal': nominal, 'coverage': float(np.mean((y >= qpred[:, lower]) & (y <= qpred[:, upper]))), 'width': float(width.mean()), 'interval_score': float(score.mean())})
    path = store.parquet(folder / 'predictions.parquet', evaluated)
    artifacts.append({'path': str(path.relative_to(store.root)), 'sha256': digest(path)})
    for name, model in models.items():
        path = folder / f'{name}.joblib'; save_model(store, path, model)
        artifacts.append({'path': str(path.relative_to(store.root)), 'sha256': digest(path)})
    bundle = {'winner': winner, 'models': models, 'reference': ref, 'pooled_adjustments': pooled,
              'period_adjustments': adjustments, 'quantiles': quantiles, 'fold': fold.dict(),
              'target': target, 'band': band, 'information_track': 'retrospective reconstructed network',
              'operationally_eligible': False, 'input_columns': list(x.columns)}
    path = folder / 'policy.joblib'; save_model(store, path, bundle)
    artifacts.append({'path': str(path.relative_to(store.root)), 'sha256': digest(path)})
    result = {'fold': fold.dict(), 'target': target, 'band': band, 'winner': winner,
              'selected_family': selected_family, 'scores': scores, 'intervals': intervals,
              'selection': selection, 'search': search, 'artifacts': artifacts,
              'seconds': time.monotonic() - started, 'training_pairs': int(tr.sum()),
              'information_track': 'retrospective reconstructed network', 'claim': 'development only'}
    store.json(folder / 'result.json', result); store.complete(ident, fp, folder / 'result.json')
    print('COMPLETE', ident, winner, round(result['seconds'], 1), flush=True)
    return {'job': ident, 'winner': winner, 'seconds': result['seconds']}


def run(config_path=CONFIG, stage='primary', fold_name=None):
    c = load_config(config_path); inv = inventory(c)
    source_fp=fingerprint({'sources':inv['sources'],'configuration':inv['configuration'],
        'data_adapter':digest(__file__.replace('diurnal_runner.py','data.py'))})
    jobs = []
    for fold in folds(c):
        if fold_name and fold.name != fold_name:
            continue
        for band in range(len(c['bands'])):
            for target in c['targets']:
                primary = band == 0 and target.endswith('_tight')
                if primary != (stage == 'primary'):
                    continue
                jobs.append((config_path, fold.name, band, target, source_fp))
    Store(c).json(c['_run'] / f'{stage}_manifest.json', {'jobs': jobs, 'objective': 'mae', 'source_fingerprint': source_fp})
    with ProcessPoolExecutor(max_workers=c['limits']['workers']) as pool:
        for result in pool.map(job, jobs):
            print(json.dumps(clean(result)), flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--config', default=CONFIG)
    p.add_argument('--stage', choices=['primary', 'extensions'], default='primary'); p.add_argument('--fold')
    a = p.parse_args(); run(a.config, a.stage, a.fold)
