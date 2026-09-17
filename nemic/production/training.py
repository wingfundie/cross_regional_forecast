"""Chronological, purged training with data-informed search and held-out calibration."""
import platform
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.dummy import DummyRegressor
from sklearn.base import BaseEstimator, RegressorMixin
from threadpoolctl import threadpool_limits

from .contracts import QUANTILES, digest, write_json


class AnchorRegressor(RegressorMixin, BaseEstimator):
    def fit(self, X, y):
        self.is_fitted_ = True
        return self

    def predict(self, X):
        return X["own_anchor"].to_numpy()


class SeasonalRegressor(RegressorMixin, BaseEstimator):
    def fit(self, X, y):
        f = X[["hour_sin", "hour_cos"]].round(6).copy()
        f["actual"] = np.asarray(y)
        self.lookup_ = f.groupby(["hour_sin", "hour_cos"]).actual.median().to_dict()
        self.default_ = float(np.median(y))
        return self

    def predict(self, X):
        return np.asarray([self.lookup_.get(tuple(row), self.default_) for row in X[["hour_sin", "hour_cos"]].round(6).to_numpy()])


def metrics(actual, predicted, scale=None, mape_floor=1.):
    actual, predicted = np.asarray(actual, float), np.asarray(predicted, float)
    valid = np.isfinite(actual) & np.isfinite(predicted)
    actual, predicted = actual[valid], predicted[valid]
    if not len(actual):
        return {"n": 0}
    error = np.abs(actual - predicted)
    keep = np.abs(actual) >= mape_floor
    return {"n": len(actual), "mae_mw": float(error.mean()),
            "mape_pct": float((error[keep] / np.abs(actual[keep])).mean() * 100) if keep.any() else None,
            "mape_excluded": int((~keep).sum()), "mape_floor_mw": mape_floor,
            "normalized_mae_pct": float(error.mean() / scale * 100) if scale and scale > 0 else None,
            "overstatement_100_rate": float(((predicted - actual) > 100).mean()),
            "overstatement_200_rate": float(((predicted - actual) > 200).mean())}


def folds(frame, n_splits=3):
    origins = pd.DatetimeIndex(sorted(frame.origin.unique()))
    if len(origins) < 12:
        raise ValueError("At least 12 distinct forecast origins required")
    chunks = np.array_split(origins, n_splits + 1)
    for chunk in chunks[1:]:
        start, end = chunk[0], chunk[-1]
        train = frame.index[(frame.origin < start) & (frame.delivery < start)]
        test = frame.index[(frame.origin >= start) & (frame.origin <= end)]
        if len(train) < 5 or not len(test):
            raise ValueError("Insufficient history after purging overlapping forecast labels")
        yield train, test


def estimator(family, params):
    if family == "persistence":
        return AnchorRegressor()
    if family == "seasonal":
        return SeasonalRegressor()
    if family == "median":
        return DummyRegressor(strategy="median")
    if family == "ridge":
        return make_pipeline(StandardScaler(), Ridge(**params))
    if family == "boosting":
        return HistGradientBoostingRegressor(loss="absolute_error", random_state=17, early_stopping=False, **params)
    raise ValueError(f"Unknown family: {family}")


def train(frame, manifest, destination, *, budget_seconds=60, max_trials=24, objective_metric="mae"):
    """Only called explicitly. The caller supplies genuine as-of feature rows."""
    import optuna
    from importlib.metadata import version
    frame = frame.copy().reset_index(drop=True)
    for col in ("origin", "delivery"):
        frame[col] = pd.to_datetime(frame[col], utc=True)
    frame = frame.sort_values(["origin", "delivery"]).reset_index(drop=True)
    features = manifest["features"]
    if objective_metric not in {"mae", "capacity_normalized_mae"}:
        raise ValueError("Unsupported optimization objective")
    if objective_metric == "capacity_normalized_mae":
        if "capacity_reference_mw" not in frame or not (frame.capacity_reference_mw > 0).all() or not np.isfinite(frame.capacity_reference_mw).all():
            raise ValueError("Normalized objective requires positive issue-known capacity_reference_mw")
        if not manifest.get("capacity_reference_definition"):
            raise ValueError("Document issue-known capacity reference derivation in manifest")
    if budget_seconds <= 0 or max_trials < 1:
        raise ValueError("Positive tuning budget required")
    if not np.isfinite(frame[features + ["actual"]].to_numpy(dtype=float)).all():
        raise ValueError("Training features/labels must be finite")
    if not (frame.delivery > frame.origin).all():
        raise ValueError("Training deliveries must follow origins")
    from .contracts import connector
    if "connector" not in frame or set(frame.connector.map(connector)) != set(map(connector, manifest["connectors"])):
        raise ValueError("Training rows do not match manifest connector scope")
    computed_leads = (frame.delivery - frame.origin).dt.total_seconds() / 1800
    if not ((computed_leads >= manifest["lead_min"]) & (computed_leads <= manifest["lead_max"]) & (computed_leads % 1 == 0)).all():
        raise ValueError("Training leads outside manifest horizon")
    if "lead" in frame and not np.allclose(frame.lead, computed_leads):
        raise ValueError("Training lead inconsistent with timestamps")
    if computed_leads.min() != manifest["lead_min"] or computed_leads.max() != manifest["lead_max"]:
        raise ValueError("Declared horizon endpoints must be represented in training data")
    origins = sorted(frame.origin.unique())
    if len(origins) < 20:
        raise ValueError("At least 20 origins required for development and calibration")
    calibration_start = origins[int(len(origins) * .8)]
    dev = frame[(frame.origin < calibration_start) & (frame.delivery < calibration_start)].copy()
    cal = frame[frame.origin >= calibration_start].copy()
    splits = list(folds(dev))
    min_rows = min(len(a) for a, _ in splits)
    independent_days = max(1, dev.origin.dt.normalize().nunique())
    p = len(features)
    scale = max(float(np.abs(dev.actual).quantile(.95)), 1.)
    # Bounds depend on usable fold size and dimension, not total overlapping rows.
    leaf_low = max(2, min_rows // max(4, min(independent_days, 32)))
    leaf_high = max(leaf_low, min_rows // 3)
    leaves_high = max(2, min(63, min_rows // leaf_low))
    alpha_mid = max(1e-6, p / min_rows)
    search = {"independent_days": independent_days, "minimum_fold_rows": min_rows, "feature_count": p,
              "alpha": [alpha_mid / 100, alpha_mid * 10000],
              "min_samples_leaf": [leaf_low, leaf_high], "max_leaf_nodes": [2, leaves_high],
              "scale_mw": scale, "scale_definition": "development-label absolute 95th percentile; diagnostic, not physical capacity"}
    start = time.perf_counter()
    probe = estimator("boosting", {"max_iter": 30, "min_samples_leaf": leaf_low, "max_leaf_nodes": leaves_high})
    with threadpool_limits(limits=1):
        probe.fit(dev.loc[splits[0][0], features], dev.loc[splits[0][0], "actual"])
    pilot = max(time.perf_counter() - start, .01)
    trials = max(1, min(int(max_trials), int(budget_seconds / (pilot * len(splits) * 5))))
    search.update(pilot_seconds=pilot, trial_budget=trials, wall_clock_budget_seconds=budget_seconds)
    evaluations, predictions = [], []

    def evaluate(family, params, label):
        errors, records = [], []
        for train_idx, test_idx in splits:
            model = estimator(family, params)
            with threadpool_limits(limits=1):
                model.fit(dev.loc[train_idx, features], dev.loc[train_idx, "actual"])
                pred = model.predict(dev.loc[test_idx, features])
            actual = dev.loc[test_idx, "actual"].to_numpy()
            error = np.abs(actual - pred)
            if objective_metric == "capacity_normalized_mae":
                error = error / dev.loc[test_idx, "capacity_reference_mw"].to_numpy()
            errors.extend(error)
            for idx, prediction in zip(test_idx, pred):
                records.append({"origin": dev.loc[idx, "origin"], "delivery": dev.loc[idx, "delivery"],
                                "actual": dev.loc[idx, "actual"], "forecast_mw": float(prediction), "model": label})
        score = float(np.mean(errors))
        return score, records

    candidates = []
    families = ["median", "ridge"]
    if "own_anchor" in features:
        families.append("persistence")
    if {"hour_sin", "hour_cos"} <= set(features):
        families.append("seasonal")
    for family in families:
        params = {"alpha": alpha_mid} if family == "ridge" else {}
        if family == "ridge":
            ridge_results = []
            for alpha in np.geomspace(search["alpha"][0], search["alpha"][1], 5):
                candidate_score, candidate_records = evaluate(family, {"alpha": float(alpha)}, family)
                ridge_results.append((candidate_score, float(alpha), candidate_records))
            score, alpha, records = min(ridge_results, key=lambda item: item[0])
            params = {"alpha": alpha}
        else:
            score, records = evaluate(family, params, family)
        candidates.append((score, family, params))
        predictions.extend(records)
        evaluations.append({"family": family, **metrics([r["actual"] for r in records], [r["forecast_mw"] for r in records], scale)})
    study = optuna.create_study(direction="minimize", sampler=optuna.samplers.TPESampler(seed=17))

    def objective(trial):
        params = {"learning_rate": trial.suggest_float("learning_rate", .02, .15, log=True),
                  "max_iter": trial.suggest_int("max_iter", 30, max(30, min(300, independent_days * 5))),
                  "min_samples_leaf": trial.suggest_int("min_samples_leaf", leaf_low, leaf_high),
                  "max_leaf_nodes": trial.suggest_int("max_leaf_nodes", 2, leaves_high),
                  "l2_regularization": trial.suggest_float("l2_regularization", alpha_mid / 100, alpha_mid * 10000, log=True)}
        score, _ = evaluate("boosting", params, "boosting")
        return score

    study.optimize(objective, n_trials=trials, timeout=budget_seconds)
    score, records = evaluate("boosting", study.best_params, "boosting")
    candidates.append((score, "boosting", study.best_params))
    predictions.extend(records)
    evaluations.append({"family": "boosting", **metrics([r["actual"] for r in records], [r["forecast_mw"] for r in records], scale)})
    _, family, params = min(candidates, key=lambda x: x[0])
    fitted = estimator(family, params)
    with threadpool_limits(limits=1):
        fitted.fit(dev[features], dev.actual)
        cal_pred = fitted.predict(cal[features])
    residuals = cal.actual.to_numpy() - cal_pred
    adjustments = np.quantile(residuals, QUANTILES)
    path = Path(destination)
    path.mkdir(parents=True, exist_ok=False)
    joblib.dump({"estimator": fitted, "adjustments": adjustments}, path / "model.joblib")
    pd.DataFrame(predictions).to_csv(path / "validation_predictions.csv", index=False)
    # Held-out permutation importance; model-appropriate additive decomposition below.
    from sklearn.inspection import permutation_importance
    with threadpool_limits(limits=1):
        importance = permutation_importance(fitted, cal[features], cal.actual, scoring="neg_mean_absolute_error", n_repeats=3, random_state=17)
    explanation = {"permutation_mae_increase": dict(zip(features, importance.importances_mean.tolist())), "family": family}
    sample = cal[features].iloc[:min(50, len(cal))]
    if family == "ridge":
        scaler, ridge = fitted.steps[0][1], fitted.steps[1][1]
        background = scaler.transform(dev[features]).mean(axis=0)
        values = (scaler.transform(sample) - background) * ridge.coef_
        explanation.update(method="interventional linear SHAP", base_value=float(ridge.intercept_ + background @ ridge.coef_), shap_values=values.tolist())
    elif family == "boosting":
        import shap
        with threadpool_limits(limits=1):
            explainer = shap.TreeExplainer(fitted)
            values = explainer.shap_values(sample)
        explanation.update(method="TreeSHAP", base_value=float(np.asarray(explainer.expected_value).ravel()[0]), shap_values=np.asarray(values).tolist())
    elif family == "median":
        explanation.update(method="constant model: zero feature contributions", base_value=float(fitted.constant_.ravel()[0]), shap_values=np.zeros(sample.shape).tolist())
    else:
        import shap
        background = dev[features].iloc[:min(30, len(dev))]
        explainer = shap.Explainer(lambda x: fitted.predict(pd.DataFrame(x, columns=features)), background.to_numpy(), algorithm="permutation")
        values = explainer(sample.to_numpy(), max_evals=2 * len(features) + 1)
        explanation.update(method="Permutation SHAP", base_value=float(values.base_values[0]), shap_values=values.values.tolist())
    explanation["features"] = features
    write_json(path / "explanations.json", explanation)
    all_explanations = {family: explanation}
    for _, other_family, other_params in candidates:
        if other_family == family:
            continue
        other = estimator(other_family, other_params)
        with threadpool_limits(limits=1):
            other.fit(dev[features], dev.actual)
            other_importance = permutation_importance(other, cal[features], cal.actual, scoring="neg_mean_absolute_error", n_repeats=3, random_state=17)
        local = {"features": features, "family": other_family,
                 "permutation_mae_increase": dict(zip(features, other_importance.importances_mean.tolist()))}
        if other_family == "median":
            local.update(method="constant model: zero feature contributions", base_value=float(other.constant_.ravel()[0]), shap_values=np.zeros(sample.shape).tolist())
        elif other_family == "boosting":
            import shap
            with threadpool_limits(limits=1):
                exp = shap.TreeExplainer(other)
                vals = exp.shap_values(sample)
            local.update(method="TreeSHAP", base_value=float(np.asarray(exp.expected_value).ravel()[0]), shap_values=np.asarray(vals).tolist())
        elif other_family == "ridge":
            scaler, ridge = other.steps[0][1], other.steps[1][1]
            background = scaler.transform(dev[features]).mean(axis=0)
            local.update(method="interventional linear SHAP", base_value=float(ridge.intercept_ + background @ ridge.coef_),
                         shap_values=((scaler.transform(sample) - background) * ridge.coef_).tolist())
        else:
            import shap
            background = dev[features].iloc[:min(20, len(dev))]
            exp = shap.Explainer(lambda x: other.predict(pd.DataFrame(x, columns=features)), background.to_numpy(), algorithm="permutation")
            vals = exp(sample.iloc[:10].to_numpy(), max_evals=2 * len(features) + 1)
            local.update(method="Permutation SHAP", base_value=float(vals.base_values[0]), shap_values=vals.values.tolist())
        all_explanations[other_family] = local
    write_json(path / "all_explanations.json", all_explanations)
    write_json(path / "search.json", search)
    study.trials_dataframe().to_csv(path / "trials.csv", index=False)
    write_json(path / "evaluation.json", {"models": evaluations, "selection": family, "selection_metric": objective_metric,
               "calibration_rows": len(cal), "calibration_start": calibration_start,
               "note": "Calibration residuals are not an independent interval-coverage test. Prospective validation required."})
    manifest = {**manifest, "adapter": "sklearn", "family": family, "parameters": params,
                "status": "research", "training_cutoff": dev.delivery.max().isoformat(),
                "evaluation": "evaluation.json", "calibration_version": "heldout-residual-v1",
                "calibration_end": cal.delivery.max().isoformat(),
                "dependencies": {k: version(k) for k in ("numpy", "pandas", "scikit-learn", "joblib")},
                "python": platform.python_version(),
                "artifacts": {p.name: digest(p) for p in path.iterdir() if p.is_file()}}
    write_json(path / "manifest.json", manifest)
    return manifest
