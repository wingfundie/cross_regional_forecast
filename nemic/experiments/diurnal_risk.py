"""Separate probability fitting, calibration and joint-budget alert selection."""
import json
import time
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from threadpoolctl import threadpool_limits

from .core import Store, load_config, fingerprint, digest
from .data import connector_data, base_frame, design, inventory
from .diurnal import expansion, mature_masks
from .diurnal_runner import inner_windows, CONFIG
from .validation import folds
from .events import detect, incidents, window_label, match, probability_score
from .runner import save_model


class ConstantClassifier:
    def __init__(self,probability,features):
        self.probability=float(np.clip(probability,1e-6,1-1e-6))
        self.coef_=np.zeros((1,features));self.intercept_=np.array([np.log(self.probability/(1-self.probability))])
    def fit(self,x,y):return self
    def predict_proba(self,x):
        p=np.repeat(self.probability,len(x));return np.column_stack([1-p,p])
    def get_params(self):return {'constant_probability':self.probability}


class ProbabilityCalibrator:
    def fit(self,logits,y):
        if np.unique(y).size<2:
            p=float(np.clip(np.mean(y),1e-6,1-1e-6));self.model=ConstantClassifier(p,1)
        else:self.model=LogisticRegression(C=1e6,max_iter=1000).fit(logits,y)
        self.coef_=self.model.coef_;self.intercept_=self.model.intercept_
        return self
    def predict_proba(self,logits):return self.model.predict_proba(logits)


def score_events(origins, probability, threshold, catalogue):
    result = match(origins, probability, threshold, catalogue)
    result['legacy_calendar_days'] = result.get('days', 0)
    result['exposure_days'] = len(origins) / 48
    result['false_alarms_per_day'] = result['fp'] / result['exposure_days'] if len(origins) else None
    return result


def joint_threshold(entries, budget=3.):
    choices = []
    for origins, p, catalogue in entries:
        candidates = np.unique(np.r_[0, np.quantile(p, np.linspace(0, 1, 41)), 1])
        choices.append([(float(t), score_events(origins, p, t, catalogue)) for t in candidates])
    feasible = [(a, b) for a in choices[0] for b in choices[1]
                if a[1]['false_alarms_per_day'] + b[1]['false_alarms_per_day'] <= budget]
    winner = max(feasible, key=lambda pair: (pair[0][1]['tp'] + pair[1][1]['tp'],
                    -pair[0][1]['fp'] - pair[1][1]['fp']))
    return [winner[0][0], winner[1][0]]


class RiskModel:
    def __init__(self, family, strength=.1, leaves=7):
        self.family, self.strength, self.leaves = family, strength, leaves

    def fit(self, x, y):
        self.names = list(x.columns)
        z = expansion(x, 'T3', 2)
        self.imputer = SimpleImputer(keep_empty_features=True).fit(z)
        a = self.imputer.transform(z)
        self.scaler = StandardScaler().fit(a); a = self.scaler.transform(a)
        prevalence = float(np.mean(y))
        fisher = np.linalg.eigvalsh(a.T @ a / len(a)) * prevalence * (1 - prevalence)
        scale = max(float(np.max(fisher)), 1e-6)
        self.C = 1 / (len(a) * scale * self.strength)
        self.profile = {'rows': len(a), 'prevalence': prevalence, 'fisher_max': scale,
                        'positive_rows': int(np.sum(y)), 'features': a.shape[1]}
        self.is_constant=np.unique(y).size<2
        self.model = (ConstantClassifier(prevalence,a.shape[1]) if self.is_constant else
            (LogisticRegression(C=self.C, max_iter=2000) if self.family == 'logistic'
            else lgb.LGBMClassifier(num_leaves=self.leaves, n_estimators=150, min_child_samples=max(20, int(len(a) / 100)),
                 learning_rate=.04, n_jobs=2, verbosity=-1, random_state=741, deterministic=True, force_col_wise=True)))
        self.model.fit(a, y)
        return self

    def transformed(self, x):
        if list(x.columns) != self.names:
            raise ValueError('Risk feature schema mismatch')
        return self.scaler.transform(self.imputer.transform(expansion(x, 'T3', 2)))

    def predict(self, x):
        a = self.transformed(x)
        p = self.model.predict_proba(a)[:,1] if self.is_constant or self.family == 'logistic' else self.model.booster_.predict(a, num_threads=2)
        return np.clip(p, 1e-6, 1 - 1e-6)


def run_risk(config_path=CONFIG):
    c = load_config(config_path); store = Store(c); inv = inventory(c)
    d = connector_data(c, c['connectors'][0]); d['base'] = base_frame(d); idx = d['y'].index
    x = design(d, np.arange(len(idx)), np.repeat(4, len(idx)), 'full').astype(float)
    with threadpool_limits(limits=2):
        for fold in folds(c):
            ident = f'risk/{fold.name}'; folder = store.root / ident
            fp = fingerprint([inv['fingerprint'], fold.dict(), digest(__file__)])
            if store.valid(ident, fp):
                continue
            masks = mature_masks(idx, idx + pd.Timedelta(minutes=120), fold)
            meta = pd.DataFrame({'origin': idx, 'delivery': idx + pd.Timedelta(minutes=120)})
            catalogues, labels = {}, {}
            for direction in ('export', 'import'):
                detector, thresholds = detect(d['raw'][direction], fold.train_start, fold.train_end)
                labels[direction] = window_label(detector.onset, detector.valid, idx)
                catalogues[direction] = incidents(detector)
                store.parquet(folder / f'{direction}_incidents.parquet', catalogues[direction])
                store.json(folder / f'{direction}_detector.json', thresholds)
            good = np.isfinite(labels['export']) & np.isfinite(labels['import'])
            train, select, calibrate, alert, evaluate = [masks[n] & good for n in ('train','select','calibrate','alert','evaluate')]
            windows = inner_windows(meta, train)
            models, probabilities, records, scores = {}, {}, [], []
            for family in ('logistic', 'boost'):
                models[family], probabilities[family] = {}, {}
                for direction in ('export', 'import'):
                    y = labels[direction]; trial_rows = []
                    positive_support=int(np.sum(y[windows[0][0]]))
                    leaf_cap=max(2,min(63,int(np.sqrt(max(positive_support,1)))))
                    tree_candidates=sorted(set([2**j for j in range(1,7) if 2**j<=leaf_cap]+[leaf_cap]))
                    settings = [.001, .01, .1, 1., 10.] if family == 'logistic' else tree_candidates
                    for setting in settings:
                        losses = []
                        for tr, va in windows:
                            model = RiskModel(family, strength=setting if family == 'logistic' else .1,
                                              leaves=int(setting) if family == 'boost' else 7).fit(x.loc[tr], y[tr])
                            losses.append(float(log_loss(y[va], model.predict(x.loc[va]), labels=[0,1])))
                        trial_rows.append({'setting': setting, 'log_loss': float(np.mean(losses)), 'blocks': losses})
                    setting = min(trial_rows, key=lambda t: t['log_loss'])['setting']
                    model = RiskModel(family, strength=setting if family == 'logistic' else .1,
                                      leaves=int(setting) if family == 'boost' else 7).fit(x.loc[train], y[train])
                    raw = model.predict(x); logits = np.log(raw / (1 - raw)).reshape(-1,1)
                    cal = ProbabilityCalibrator().fit(logits[calibrate], y[calibrate])
                    models[family][direction] = (model, cal)
                    probabilities[family][direction] = (raw, cal.predict_proba(logits)[:,1])
                    records.append({'family':family, 'direction':direction, 'trials':trial_rows, 'chosen':setting,
                                    'profile':model.profile, 'parameters':model.model.get_params()})
                # Select family on selection-only uncalibrated probabilities at provisional budget.
                provisional = joint_threshold([(idx[select], probabilities[family][dr][0][select], catalogues[dr]) for dr in ('export','import')])
                selection_results = [score_events(idx[select], probabilities[family][dr][0][select], threshold, catalogues[dr]) for dr, threshold in zip(('export','import'), provisional)]
                final = joint_threshold([(idx[alert], probabilities[family][dr][1][alert], catalogues[dr]) for dr in ('export','import')])
                for direction, threshold in zip(('export','import'), final):
                    p = probabilities[family][direction][1]
                    severity={}
                    for drop in c['events']['absolute_drops_mw']:
                        detector,_=detect(d['raw'][direction],fold.train_start,fold.train_end,absolute=drop)
                        severity[str(drop)]=score_events(idx[evaluate],p[evaluate],threshold,incidents(detector))
                    scores.append({'family':family, 'direction':direction, 'threshold':threshold,
                        'selection_tp':sum(r['tp'] for r in selection_results),
                        'selection_incidents':sum(r['incidents'] for r in selection_results),
                        'probability':probability_score(labels[direction][evaluate], p[evaluate]),
                        'events':score_events(idx[evaluate], p[evaluate], threshold, catalogues[direction]),
                        'absolute_drop_scorecards':severity})
                    store.parquet(folder / f'{family}_{direction}_predictions.parquet', pd.DataFrame({'origin':idx[evaluate],
                        'actual_window': labels[direction][evaluate], 'probability':p[evaluate], 'threshold':threshold}))
            winner = max(('logistic','boost'), key=lambda f: sum(s['selection_tp'] for s in scores if s['family']==f))
            save_model(store, folder / 'models.joblib', {'models':models,'winner':winner,'scores':scores,'fold':fold.dict(), 'operationally_eligible':False})
            result = {'fold':fold.dict(),'winner':winner,'scores':scores,'search':records,
                      'claim':'Historical development; retrospective mapping inputs; evaluation budget must be checked separately'}
            store.json(folder / 'result.json', result); store.complete(ident, fp, folder / 'result.json')
            print('RISK', fold.name, winner, flush=True)


if __name__ == '__main__':
    run_risk()
