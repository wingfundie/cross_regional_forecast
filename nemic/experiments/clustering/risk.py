"""Two-hour contraction-warning comparison for clustered state features."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import time

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.preprocessing import StandardScaler

from nemic.experiments.core import ROOT, digest, fingerprint
from nemic.experiments.events import (
    detect,
    incident_interval,
    incidents,
    match,
    probability_score,
    tune_joint,
    window_label,
)
from .campaign import _save_joblib, _state_specs
from .config import store
from .data import META_COLUMNS, connector_config, feature_contract, inventory, load_feature_rows, unique_origin_rows
from .protocol import ProtocolFold, limited_support_flags, partition_masks
from .state import StateClusterer


@dataclass
class ProbabilityModel:
    columns: list[str]
    imputer: SimpleImputer
    scaler: StandardScaler
    estimator: LogisticRegression
    calibrator: LogisticRegression | None = None

    def _values(self, frame: pd.DataFrame) -> np.ndarray:
        values = self.imputer.transform(frame[self.columns].astype(float))
        return self.scaler.transform(values)

    def raw_probability(self, frame: pd.DataFrame) -> np.ndarray:
        return self.estimator.predict_proba(self._values(frame))[:, 1]

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        raw = np.clip(self.raw_probability(frame), 1e-6, 1 - 1e-6)
        if self.calibrator is None:
            return raw
        logits = np.log(raw / (1 - raw)).reshape(-1, 1)
        return self.calibrator.predict_proba(logits)[:, 1]


def _fit_probability(
    train_x: pd.DataFrame,
    train_y: np.ndarray,
    select_x: pd.DataFrame,
    select_y: np.ndarray,
    calibration_x: pd.DataFrame,
    calibration_y: np.ndarray,
    c_values: list[float],
    seed: int,
) -> tuple[ProbabilityModel, list[dict]]:
    columns = [
        column for column in train_x
        if pd.to_numeric(train_x[column], errors="coerce").notna().any()
    ]
    if not columns:
        raise ValueError("No training-supported risk features")
    train_x = train_x[columns].apply(pd.to_numeric, errors="coerce")
    select_x = select_x[columns].apply(pd.to_numeric, errors="coerce")
    calibration_x = calibration_x[columns].apply(pd.to_numeric, errors="coerce")
    imputer = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True).fit(train_x)
    scaler = StandardScaler().fit(imputer.transform(train_x))
    z = scaler.transform(imputer.transform(train_x))
    zs = scaler.transform(imputer.transform(select_x))
    trials, models = [], []
    for value in c_values:
        estimator = LogisticRegression(
            C=float(value), max_iter=2000, class_weight="balanced", random_state=seed
        ).fit(z, train_y)
        p = np.clip(estimator.predict_proba(zs)[:, 1], 1e-6, 1 - 1e-6)
        loss = float(log_loss(select_y, p, labels=[0, 1]))
        trials.append({"C": float(value), "selection_log_loss": loss})
        models.append(estimator)
    choice = int(np.argmin([row["selection_log_loss"] for row in trials]))
    model = ProbabilityModel(columns, imputer, scaler, models[choice])
    if len(np.unique(calibration_y)) == 2:
        raw = np.clip(model.raw_probability(calibration_x), 1e-6, 1 - 1e-6)
        logits = np.log(raw / (1 - raw)).reshape(-1, 1)
        model.calibrator = LogisticRegression(C=1e6, max_iter=1000, random_state=seed).fit(logits, calibration_y)
    return model, trials


def _raw_capacities(config: dict, connector: str) -> pd.DataFrame:
    identity = connector_config(config, connector)["id"]
    frame = pd.read_parquet(
        ROOT / "data/processed/ic_5min.parquet",
        columns=["time", "INTERCONNECTORID", "export", "import"],
    )
    frame = frame.loc[frame.INTERCONNECTORID.eq(identity)].set_index("time").sort_index()
    if not frame.index.is_unique:
        raise ValueError("Duplicate five-minute capacity rows")
    return frame[["export", "import"]]


def _paired_recall_interval(candidate: dict, control: dict, event_times: pd.DatetimeIndex, seed: int, replicates: int = 1000) -> dict | None:
    if not len(event_times):
        return None
    candidate_hits = np.array([str(value) in set(candidate.get("matched_times", [])) for value in event_times], dtype=float)
    control_hits = np.array([str(value) in set(control.get("matched_times", [])) for value in event_times], dtype=float)
    delta = candidate_hits - control_hits
    rng = np.random.default_rng(seed)
    draws = delta[rng.integers(0, len(delta), size=(replicates, len(delta)))].mean(axis=1)
    return {
        "incidents": len(delta),
        "recall_difference": float(delta.mean()),
        "recall_difference_ci95": np.quantile(draws, [0.025, 0.975]).tolist(),
        "method": "paired incident bootstrap",
    }


def run_risk_fold(config: dict, connector: str, fold: ProtocolFold) -> dict:
    manager = store(config)
    inv = inventory(config)
    ident = f"risk/{connector}/{fold.name}"
    job_fp = fingerprint([inv["fingerprint"], ident, fold.as_dict(), config["events"], config["clustering"]])
    folder = manager.root / ident
    result_path = folder / "result.json"
    if manager.valid(ident, job_fp):
        return json.loads(result_path.read_text(encoding="utf-8"))

    contract = feature_contract(config, connector)
    columns = list(dict.fromkeys(META_COLUMNS + contract["network_model"] + contract["origin"]))
    frame = load_feature_rows(config, connector, columns=columns)
    rows = frame.loc[frame.lead.eq(4)].copy().reset_index(drop=True)
    masks = partition_masks(rows.origin, rows.delivery, fold, config["folds"]["maturity_minutes"])
    raw = _raw_capacities(config, connector)
    labels, catalogues, detector_settings = {}, {}, {}
    for direction in ("export", "import"):
        detector, settings = detect(raw[direction], fold.train_start, fold.train_end)
        labels[direction] = window_label(
            detector.onset, detector.valid, pd.DatetimeIndex(rows.origin),
            config["events"]["minimum_lead_minutes"], config["events"]["maximum_lead_minutes"],
        )
        catalogues[direction] = incidents(detector)
        detector_settings[direction] = settings

    network_columns = [column for column in contract["network_model"] if column in rows]
    unique = unique_origin_rows(rows, contract["origin"]).set_index("origin").sort_index()
    train_origins = unique.loc[(unique.index >= fold.train_start) & (unique.index < fold.train_end), contract["origin"]]
    assignments = {}
    clusterers = {}
    for method, k in _state_specs(config):
        clusterer = StateClusterer(
            n_clusters=k, method=method, feature_groups=contract["origin_groups"],
            random_state=config["seed"],
            maximum_missing_fraction=config["clustering"]["maximum_missing_fraction"],
            near_duplicate_threshold=config["clustering"]["near_duplicate_correlation"],
            ood_quantile=config["clustering"]["ood_quantile"],
        ).fit(train_origins)
        clusterers[(method, k)] = clusterer
        assignments[(method, k)] = clusterer.transform(rows[contract["origin"]])

    control_models, control_probabilities, cluster_candidates = {}, {}, []
    for direction in ("export", "import"):
        y = labels[direction]
        good = np.isfinite(y)
        partitions = {key: value & good for key, value in masks.items()}
        if any(len(np.unique(y[partitions[name]])) < 2 for name in ("train", "select", "calibrate")):
            raise ValueError(f"{direction} risk partition has a single class")
        model, trials = _fit_probability(
            rows.loc[partitions["train"], network_columns], y[partitions["train"]],
            rows.loc[partitions["select"], network_columns], y[partitions["select"]],
            rows.loc[partitions["calibrate"], network_columns], y[partitions["calibrate"]],
            config["models"]["logistic_c"], config["seed"],
        )
        control_models[direction] = {"model": model, "trials": trials, "partitions": partitions}
        control_probabilities[direction] = model.predict(rows[network_columns])

    for key, assignment in assignments.items():
        direction_models, direction_probabilities, losses = {}, {}, []
        augmented = rows[network_columns].copy()
        for index in range(assignment.probabilities.shape[1]):
            augmented[f"cluster_probability_{index}"] = assignment.probabilities.iloc[:, index].to_numpy()
        for direction in ("export", "import"):
            y = labels[direction]
            partitions = control_models[direction]["partitions"]
            model, trials = _fit_probability(
                augmented.loc[partitions["train"]], y[partitions["train"]],
                augmented.loc[partitions["select"]], y[partitions["select"]],
                augmented.loc[partitions["calibrate"]], y[partitions["calibrate"]],
                config["models"]["logistic_c"], config["seed"],
            )
            probability = model.predict(augmented)
            probability[assignment.out_of_distribution.to_numpy()] = control_probabilities[direction][assignment.out_of_distribution.to_numpy()]
            selection = partitions["select"]
            losses.append(float(log_loss(y[selection], probability[selection], labels=[0, 1])))
            direction_models[direction] = {"model": model, "trials": trials}
            direction_probabilities[direction] = probability
        cluster_candidates.append({
            "method": key[0], "k": key[1], "selection_log_loss": float(sum(losses)),
            "models": direction_models, "probabilities": direction_probabilities,
        })
    selected = min(cluster_candidates, key=lambda row: (row["selection_log_loss"], row["k"], row["method"]))

    thresholds, results = {}, []
    for model_name, probabilities in (("network", control_probabilities), ("cluster", selected["probabilities"])):
        tune_items = []
        for direction in ("export", "import"):
            alert = control_models[direction]["partitions"]["alert"]
            tune_items.append((pd.DatetimeIndex(rows.origin[alert]), probabilities[direction][alert], catalogues[direction]))
        cutoffs = tune_joint(tune_items, config["events"]["false_alarms_per_day"])
        thresholds[model_name] = dict(zip(("export", "import"), cutoffs))
        for direction, cutoff in zip(("export", "import"), cutoffs):
            evaluation = control_models[direction]["partitions"]["evaluate"]
            origins = pd.DatetimeIndex(rows.origin[evaluation])
            event_result = match(
                origins, probabilities[direction][evaluation], cutoff, catalogues[direction],
                config["events"]["minimum_lead_minutes"], config["events"]["maximum_lead_minutes"],
            )
            results.append({
                "model": model_name, "direction": direction, "threshold": cutoff,
                "probability": probability_score(labels[direction][evaluation], probabilities[direction][evaluation]),
                "events": event_result, "uncertainty": incident_interval(event_result),
                "support": limited_support_flags(origins, event_result["incidents"]),
            })

    paired = {}
    for direction in ("export", "import"):
        candidate = next(row for row in results if row["model"] == "cluster" and row["direction"] == direction)["events"]
        control = next(row for row in results if row["model"] == "network" and row["direction"] == direction)["events"]
        evaluation = control_models[direction]["partitions"]["evaluate"]
        origins = pd.DatetimeIndex(rows.origin[evaluation])
        event_times = pd.DatetimeIndex(catalogues[direction].time)
        low, high = origins.min(), origins.max() + pd.Timedelta(minutes=config["events"]["maximum_lead_minutes"])
        paired[direction] = _paired_recall_interval(
            candidate, control, event_times[(event_times >= low) & (event_times <= high)], config["seed"]
        )

    prediction_frame = pd.DataFrame({"origin": rows.origin})
    for direction in ("export", "import"):
        prediction_frame[f"actual_{direction}"] = labels[direction]
        prediction_frame[f"network_probability_{direction}"] = control_probabilities[direction]
        prediction_frame[f"cluster_probability_{direction}"] = selected["probabilities"][direction]
    prediction_path = manager.parquet(folder / "predictions.parquet", prediction_frame)
    bundle_path = _save_joblib(config, folder / "bundle.joblib", {
        "control_models": control_models,
        "cluster_models": selected["models"],
        "clusterer": clusterers[(selected["method"], selected["k"])],
        "thresholds": thresholds,
        "fold": fold.as_dict(),
        "operationally_eligible": False,
    })
    payload = {
        "job": ident, "status": "complete", "fingerprint": job_fp,
        "connector": connector, "fold": fold.as_dict(),
        "selected_cluster": {key: selected[key] for key in ("method", "k", "selection_log_loss")},
        "cluster_candidates": [
            {key: row[key] for key in ("method", "k", "selection_log_loss")} for row in cluster_candidates
        ],
        "detectors": detector_settings, "thresholds": thresholds,
        "results": results, "paired_recall": paired,
        "claim": config["claims"]["primary"],
        "artifacts": [
            {"path": str(prediction_path.relative_to(manager.root)), "sha256": digest(prediction_path)},
            {"path": str(bundle_path.relative_to(manager.root)), "sha256": digest(bundle_path)},
        ],
    }
    manager.json(result_path, payload)
    manager.complete(ident, job_fp, result_path)
    return payload


def run_risk_track(config: dict, connector: str, folds: tuple[ProtocolFold, ...], deadline: float) -> list[dict]:
    progress = []
    for fold in folds:
        if time.monotonic() >= deadline:
            break
        try:
            result = run_risk_fold(config, connector, fold)
            progress.append({"stage": "risk", "fold": fold.name, "status": result["status"]})
        except Exception as exc:
            progress.append({"stage": "risk", "fold": fold.name, "status": "failed", "error": repr(exc)})
    return progress

