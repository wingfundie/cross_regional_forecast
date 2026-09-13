"""Bounded retrospective research probe; reads retained data, never downloads.

This is not a production backtest: retained topology lacks full issue-time vintages.
"""
from pathlib import Path
import hashlib
import json
import platform
import time

import numpy as np
import pandas as pd
import sklearn
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, SplineTransformer
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/data/qni_vni_simple_model_research.json'
SOURCES = []


def read(path):
    path = Path(path)
    SOURCES.append({'path': path.relative_to(ROOT).as_posix(),
                    'bytes': path.stat().st_size,
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return pd.read_parquet(path)


def run():
    started = time.monotonic()
    targets = read(ROOT / 'data/processed/targets.parquet')
    scores, coverage, selected = [], [], []
    for name, ident in [('vni', 'VIC1-NSW1'), ('qni', 'NSW1-QLD1')]:
        files = sorted((ROOT / f'data/constraint_{name}_2y/months').glob('*/constraint_features_30min.parquet'))
        if len(files) != 24:
            raise ValueError(f'{name}: expected 24 monthly feature partitions, got {len(files)}')
        frames = []
        for path in files:
            f = read(path)
            coverage.append({'ic': name.upper(), 'month': path.parent.name,
                             'rows': len(f),
                             'upper_nonmissing_fraction': float(f.conditional_upper.notna().mean()),
                             'lower_nonmissing_fraction': float(f.conditional_lower.notna().mean()),
                             'upper_pressure_nonmissing_fraction': float(f.upper_gen_tightening.notna().mean()),
                             'lower_pressure_nonmissing_fraction': float(f.lower_gen_tightening.notna().mean())})
            frames.append(f)
        f = pd.concat(frames).sort_values('time').set_index('time')
        if not f.index.is_unique:
            raise ValueError('Duplicate feature timestamp')
        y = targets[targets.ic.eq(ident)].set_index('time').sort_index()
        # Retain the model's complete half-hour grid; no row-based shifting over holes.
        y = y.reindex(pd.date_range(y.index.min(), y.index.max(), freq='30min'))
        cols = ['flow', 'export_tight', 'import_tight']
        base = pd.concat([y[cols].shift(lag).add_suffix(f'_lag{lag}') for lag in [1, 48, 336]], axis=1)
        base = pd.concat([base, (y[cols].shift(1) - y[cols].shift(2)).add_suffix('_change30')], axis=1)
        topology = f.select_dtypes(include='number').reindex(y.index).shift(1)
        topology = topology.replace([np.inf, -np.inf], np.nan)
        for h in [1, 2, 6]:
            delivery = y.index + pd.Timedelta(minutes=30*h)
            xbase = base.copy()
            hour = delivery.hour + delivery.minute/60
            xbase['hour_sin'] = np.sin(2*np.pi*hour/24)
            xbase['hour_cos'] = np.cos(2*np.pi*hour/24)
            xbase['year_sin'] = np.sin(2*np.pi*delivery.dayofyear/365.25)
            xbase['year_cos'] = np.cos(2*np.pi*delivery.dayofyear/365.25)
            xbase['weekend'] = (delivery.dayofweek >= 5).astype(int)
            X = {'base': xbase, 'topology': pd.concat([xbase, topology], axis=1)}
            masks = {
                'train': (y.index >= '2024-09-08') & (delivery <= pd.Timestamp('2025-09-01')),
                'validation': (y.index >= '2025-09-01') & (delivery <= pd.Timestamp('2026-03-01')),
                'evaluation': (y.index >= '2026-03-01') & (delivery <= pd.Timestamp('2026-08-31 23:30')),
            }
            for target in cols:
                truth = y[target].reindex(delivery).to_numpy()
                baseline = y[target].shift(1).to_numpy()
                valid = np.isfinite(truth) & np.isfinite(baseline)
                mask = {k: v & valid for k, v in masks.items()}
                tr, va, te = (mask[k] for k in ['train', 'validation', 'evaluation'])
                residual = truth - baseline
                scores.append({'ic': name.upper(), 'horizon_minutes': h*30, 'target': target,
                               'model': 'persistence', 'mae_mw': float(np.abs(residual[te]).mean()),
                               'n': int(te.sum())})
                for block, data in X.items():
                    # Fixed training-only extreme-value treatment for unstable sensitivity ratios.
                    low, high = data.loc[tr].quantile(.001), data.loc[tr].quantile(.999)
                    data = data.clip(lower=low, upper=high, axis=1)
                    for kind in ['ridge', 'additive']:
                        best = None
                        for alpha in [10., 100., 1000.]:
                            steps = [SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True)]
                            if kind == 'additive':
                                steps.append(SplineTransformer(n_knots=4, degree=2, include_bias=False, extrapolation='constant'))
                            steps.extend([StandardScaler(), Ridge(alpha=alpha)])
                            model = make_pipeline(*steps)
                            model.fit(data.loc[tr], residual[tr])
                            val_mae = float(np.abs(truth[va] - (baseline[va] + model.predict(data.loc[va]))).mean())
                            if best is None or val_mae < best[0]:
                                best = (val_mae, alpha, model)
                        prediction = baseline[te] + best[2].predict(data.loc[te])
                        scores.append({'ic': name.upper(), 'horizon_minutes': h*30, 'target': target,
                                       'model': f'{kind}_{block}', 'alpha': best[1],
                                       'validation_mae_mw': best[0],
                                       'mae_mw': float(np.abs(truth[te] - prediction).mean()),
                                       'n': int(te.sum()), 'raw_features': data.shape[1]})
                candidates = [s for s in scores if s['ic'] == name.upper() and s['horizon_minutes'] == h*30
                              and s['target'] == target and 'validation_mae_mw' in s]
                winner = min(candidates, key=lambda s: s['validation_mae_mw'])
                selected.append({k: winner[k] for k in ['ic', 'horizon_minutes', 'target', 'model', 'mae_mw']})
                print(name, h*30, target, 'complete', flush=True)
    result = {
        'status': 'exploratory retrospective diagnostic, not operational forecast validation',
        'scope': 'VNI and QNI; existing retained half-hour topology only; no future realised fundamentals',
        'cutoff': '2026-08-31 23:30 fixed UTC+10',
        'observation_delay_minutes': 30,
        'training': 'origins from 2024-09-08; deliveries through 2025-09-01 00:00',
        'validation': 'origins from 2025-09-01; deliveries through 2026-03-01 00:00',
        'evaluation': 'origins from 2026-03-01; deliveries through 2026-08-31 23:30',
        'limitations': ['Entire study period has already been inspected.',
                       'Retained topology uses retrospective standing-data dependencies and imperfect equation versions.',
                       'A 30-minute lag does not establish actual public availability of unit targets.',
                       'No publication-vintage reconstruction or source-specific latency audit.',
                       'No future demand/weather inputs: not directly comparable to existing conditional-model scores.',
                       'No event-specific or probabilistic performance test; no statistical significance claim.',
                       'Training-only 0.1/99.9 percentile clipping may suppress important extremes; requires ablation.'],
        'settings': {'ridge_alpha_grid': [10,100,1000], 'spline_knots': 4, 'spline_degree': 2,
                     'selection': 'validation MAE, no refit after selection',
                     'targets': ['flow','export_tight','import_tight']},
        'scores': scores, 'validation_selected': selected, 'monthly_coverage': coverage,
        'sources': SOURCES, 'downloads': [],
        'environment': {'python': platform.python_version(), 'sklearn': sklearn.__version__, 'pandas': pd.__version__},
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'runtime_seconds': time.monotonic()-started,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')
    print('saved', OUT, flush=True)


if __name__ == '__main__':
    with threadpool_limits(limits=2):
        run()
