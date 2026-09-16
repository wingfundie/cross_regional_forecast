"""V2 chronological, origin-balanced directional-limit experiment primitives."""
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
import lightgbm as lgb

PERIODS = ['overnight', 'morning', 'solar', 'evening', 'late']
DRIVERS = ['upper_room', 'lower_room', 'upper_switch_gap', 'lower_switch_gap',
           'upper_gen_tightening', 'lower_gen_tightening', 'export_tight_delta', 'import_tight_delta']


def periods(delivery):
    t = pd.DatetimeIndex(delivery)
    return np.searchsorted([6, 10, 16, 21], t.hour + t.minute / 60, side='right')


def origin_weights(origins):
    _, inverse, counts = np.unique(np.asarray(origins), return_inverse=True, return_counts=True)
    return 1. / counts[inverse]


def mature_masks(origin, delivery, fold, delay=30):
    return {name: np.asarray((origin >= a) & (delivery + pd.Timedelta(minutes=delay) < b))
            for name, (a, b) in zip(['train', 'select', 'calibrate', 'alert', 'evaluate'], fold.bounds())}


def metrics(y, p, reference=None, weights=None):
    y, p = np.asarray(y), np.asarray(p)
    if not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError('Metrics require explicit matched finite rows')
    if not len(y):
        return {'n': 0}
    e = p - y
    w = np.ones(len(y)) if weights is None else np.asarray(weights)
    result = {'n': len(y), 'mae': float(np.mean(abs(e))), 'weighted_mae': float(np.average(abs(e), weights=w)),
              'rmse': float(np.sqrt(np.mean(e**2))), 'bias': float(e.mean()),
              'p95_error': float(np.quantile(abs(e), .95)),
              'over100': float(np.mean(e > 100)), 'over200': float(np.mean(e > 200)),
              'positive_overstatement': float(np.maximum(e, 0).mean())}
    for floor in (0, 25, 50, 100):
        good = abs(y) >= floor if floor else y != 0
        result[f'mape_{floor}'] = float(np.mean(abs(e[good]) / abs(y[good])) * 100) if good.any() else None
        result[f'mape_{floor}_coverage'] = float(good.mean())
    result['mape_full'] = result['mape_0'] if np.all(y != 0) else None
    near = abs(y) < 50
    result['nearzero_mae'] = float(abs(e[near]).mean()) if near.any() else None
    if reference is not None:
        if not (np.isfinite(reference).all() and np.all(reference > 0)):
            raise ValueError('Capacity reference must be finite and positive')
        result['dr_nmae'] = float(100 * np.average(abs(e) / reference, weights=w))
    return result


class CapacityReference:
    def fit(self, observed):
        v = abs(np.asarray(observed)); v = v[np.isfinite(v) & (v > 0)]
        if not len(v):
            raise ValueError('No positive reference support')
        self.floor = float(np.quantile(v, .1)); self.median = float(np.median(v))
        return self

    def predict(self, observed):
        v = abs(np.asarray(observed))
        return np.maximum(np.where(np.isfinite(v), v, self.median), self.floor)


def expansion(x, family, harmonics):
    z = x.copy()
    phase = np.arctan2(z.hour_sin, z.hour_cos)
    if family != 'T0':
        for k in range(2, harmonics + 1):
            z[f'daily_sin_{k}'] = np.sin(k * phase)
            z[f'daily_cos_{k}'] = np.cos(k * phase)
    drivers = [n for n in DRIVERS if n in z]
    if family == 'T2':
        hour = np.round(np.mod(phase * 24 / (2 * np.pi), 24), 5) % 24
        for j in range(1, 5):
            gate = np.searchsorted([6, 10, 16, 21], hour, side='right') == j
            z[f'period_{j}'] = gate.astype(float)
            for n in drivers:
                z[f'{n}:period_{j}'] = z[n] * gate
    if family == 'T3':
        for n in drivers:
            for phase_name in ('hour_sin', 'hour_cos'):
                z[f'{n}:{phase_name}'] = z[n] * z[phase_name]
    return z


class DiurnalModel:
    """Predicts MW corrections; preprocessing is fitted within each training split."""
    def __init__(self, family='T0', complexity=.5, harmonics=2, tree=None):
        self.family, self.complexity, self.harmonics = family, complexity, harmonics
        self.tree = tree

    def fit(self, x, y, weights, origins):
        self.input_columns = list(x.columns)
        z = expansion(x, self.family, self.harmonics)
        self.names = list(z.columns)
        self.imputer = SimpleImputer(keep_empty_features=True).fit(z)
        a = self.imputer.transform(z).astype('float64')
        self.scaler = StandardScaler().fit(a, sample_weight=weights)
        a = self.scaler.transform(a)
        spectrum = np.linalg.eigvalsh((a.T * weights) @ a / weights.sum())
        spectrum = spectrum[spectrum > max(spectrum.max(), 1) * 1e-10]
        self.rank = len(spectrum)
        edf = max(.1, self.complexity * self.rank)
        if self.rank:
            self.penalty = float(brentq(lambda v: (spectrum / (spectrum + v)).sum() - edf,
                                       1e-12, max(spectrum.max(), 1) * self.rank * 1000))
        else:
            self.penalty = 1.
        self.alpha = float(weights.sum() * self.penalty)
        self.edf = edf
        self.rank99 = int(np.searchsorted(np.cumsum(spectrum[::-1]), .99 * spectrum.sum()) + 1) if self.rank else 0
        if self.family == 'T6':
            settings = dict(self.tree or {})
            self.model = lgb.LGBMRegressor(objective='regression_l1', verbosity=-1, n_jobs=2,
                                           random_state=741, deterministic=True, force_col_wise=True, **settings)
        else:
            self.model = Ridge(alpha=self.alpha)
        self.model.fit(a, y, sample_weight=weights)
        self.specialists = {}
        if self.family == 'T5':
            phase = np.round(np.mod(np.arctan2(x.hour_sin, x.hour_cos) * 24 / (2 * np.pi), 24), 5) % 24
            groups = np.searchsorted([6, 10, 16, 21], phase, side='right')
            for j in range(5):
                m = groups == j
                dates = pd.DatetimeIndex(np.asarray(origins)[m])
                if m.sum() >= 500 and dates.normalize().nunique() >= 90:
                    self.specialists[j] = Ridge(alpha=self.penalty * weights[m].sum()).fit(a[m], np.asarray(y)[m], sample_weight=weights[m])
        return self

    def transformed(self, x):
        if list(x.columns) != self.input_columns:
            raise ValueError('Input feature schema mismatch')
        return self.scaler.transform(self.imputer.transform(expansion(x, self.family, self.harmonics)))

    def predict(self, x):
        a = self.transformed(x)
        p = self.model.booster_.predict(a, num_threads=2) if self.family == 'T6' else self.model.predict(a)
        if self.family == 'T5':
            # Smooth triangular membership centred on the prespecified periods.
            hour = np.mod(np.arctan2(x.hour_sin, x.hour_cos) * 24 / (2 * np.pi), 24).to_numpy()
            centres = np.array([3, 8, 13, 18.5, 22.5])
            distance = abs(hour[:, None] - centres); distance = np.minimum(distance, 24 - distance)
            blend = np.maximum(1 - distance / 6, 0); blend /= blend.sum(axis=1, keepdims=True)
            p = sum(blend[:, j] * (self.specialists[j].predict(a) if j in self.specialists else p) for j in range(5))
        return p


class ResidualCorrection:
    """T4: base fitted on early training, correction on later held-out residuals."""
    def __init__(self, complexity=.5, harmonics=2):
        self.complexity, self.harmonics = complexity, harmonics
        self.family = 'T4'

    def fit(self, x, y, weights, origins):
        unique = pd.DatetimeIndex(origins).unique().sort_values()
        split = unique[int(len(unique) * .75)]
        early = pd.DatetimeIndex(origins) < split - pd.Timedelta(days=8)
        late = pd.DatetimeIndex(origins) >= split
        self.base = DiurnalModel('T1', self.complexity, self.harmonics).fit(x.loc[early], y[early], weights[early], np.asarray(origins)[early])
        residual = y[late] - self.base.predict(x.loc[late])
        self.correction = DiurnalModel('T1', self.complexity, self.harmonics).fit(x.loc[late, ['hour_sin','hour_cos']], residual, weights[late], np.asarray(origins)[late])
        self.base.fit(x, y, weights, origins)
        self.input_columns = list(x.columns)
        return self

    def predict(self, x):
        return self.base.predict(x) + self.correction.predict(x[['hour_sin','hour_cos']])
