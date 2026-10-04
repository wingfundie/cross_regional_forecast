"""Resumable orchestration for the clustering research campaign."""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import get_context
from pathlib import Path
import json
import os
import sqlite3
import time
import uuid

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from nemic.experiments.core import digest, fingerprint
from .config import load_config, store
from .data import (
    META_COLUMNS,
    TARGET_COLUMNS,
    equal_origin_training_rows,
    feature_contract,
    inventory,
    load_feature_rows,
    unique_origin_rows,
)
from .models import (
    LocalExpertModel,
    ResidualIntervals,
    append_cluster_interactions,
    append_cluster_probabilities,
    select_correction_model,
)
from .protocol import (
    ProtocolConfig,
    ProtocolFold,
    expanding_folds,
    interval_metrics,
    limited_support_flags,
    paired_effect_intervals,
    partition_masks,
    recurring_regime_screen,
    regression_metrics,
)
from .state import StateClusterer, assess_stability, support_summary


def _public_config(config: dict) -> dict:
    return {key: value for key, value in config.items() if not key.startswith("_")}


def _protocol(config: dict) -> ProtocolConfig:
    mapping = dict(config["folds"])
    mapping["seed"] = config["seed"]
    return ProtocolConfig.from_mapping(mapping)


def _folds(config: dict, frame: pd.DataFrame) -> tuple[ProtocolFold, ...]:
    if frame.empty:
        return ()
    start = max(pd.Timestamp(config["start"]), frame.origin.min().floor("D"))
    end = min(pd.Timestamp(config["end"]), frame.origin.max().ceil("D"))
    return expanding_folds(start, end, _protocol(config))


def _state_specs(config: dict, *, pilot: bool = False) -> list[tuple[str, int]]:
    values = []
    for k in config["clustering"]["k"]:
        if pilot and k not in (1, 2, 3, 4):
            continue
        if k == 1:
            values.append(("kmeans", 1))
        else:
            values.extend((method, k) for method in ("kmeans", "gmm") if method != "k1")
    return values


def _fit_clusterer(
    config: dict,
    method: str,
    k: int,
    frame: pd.DataFrame,
    groups: dict[str, list[str]],
) -> StateClusterer:
    return StateClusterer(
        n_clusters=k,
        method=method,
        feature_groups=groups,
        random_state=config["seed"],
        maximum_missing_fraction=config["clustering"]["maximum_missing_fraction"],
        near_duplicate_threshold=config["clustering"]["near_duplicate_correlation"],
        ood_quantile=config["clustering"]["ood_quantile"],
    ).fit(frame)


def _finite_target(frame: pd.DataFrame, target: str) -> np.ndarray:
    return np.isfinite(pd.to_numeric(frame[f"actual_{target}"], errors="coerce")) & np.isfinite(
        pd.to_numeric(frame[f"anchor_{target}"], errors="coerce")
    )


def _safe_model_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    retained = []
    for column in columns:
        if column not in frame:
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().any():
            retained.append(column)
    if not retained:
        raise ValueError("No finite model features")
    return retained


def _save_joblib(config: dict, path: Path, value: object) -> Path:
    manager = store(config)
    path = manager.owned(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    joblib.dump(value, temporary, compress=3)
    size = temporary.stat().st_size
    with manager.reserve(size):
        os.replace(temporary, path)
    return path


def _assign_rows(clusterer: StateClusterer, rows: pd.DataFrame, columns: list[str]):
    return clusterer.transform(rows[columns].reset_index(drop=True))


def _cluster_diagnostics(
    config: dict,
    clusterer: StateClusterer,
    train: pd.DataFrame,
    evaluate: pd.DataFrame,
    groups: dict[str, list[str]],
    method: str,
    k: int,
) -> dict:
    if k == 1:
        seed_ari = block_ari = 1.0
        comparisons = 0
    else:
        stability = assess_stability(
            train,
            n_clusters=k,
            method=method,
            feature_groups=groups,
            seeds=config["seeds"],
            block_days=1,
            maximum_missing_fraction=config["clustering"]["maximum_missing_fraction"],
            near_duplicate_threshold=config["clustering"]["near_duplicate_correlation"],
            ood_quantile=config["clustering"]["ood_quantile"],
        )
        seed_ari, block_ari = stability.seed_mean_ari, stability.block_mean_ari
        comparisons = len(stability.seed_scores) + len(stability.block_scores)
    train_assignment = clusterer.transform(train)
    evaluation_assignment = clusterer.transform(evaluate)
    train_support = support_summary(train_assignment, n_clusters=k).reset_index()
    evaluation_support = support_summary(evaluation_assignment, n_clusters=k).reset_index()
    regime_rows = []
    for label in range(k):
        tr = train_support.loc[train_support.cluster.eq(label)]
        ev = evaluation_support.loc[evaluation_support.cluster.eq(label)]
        training_days = int(tr.unique_days.iloc[0]) if len(tr) else 0
        evaluation_days = int(ev.unique_days.iloc[0]) if len(ev) else 0
        regime_rows.append({
            "cluster": label,
            **recurring_regime_screen(
                [seed_ari, block_ari], training_days, evaluation_days,
                minimum_ari=config["clustering"]["recurring_ari"],
                minimum_training_days=config["clustering"]["minimum_train_days_per_regime"],
                minimum_evaluation_days=config["clustering"]["minimum_evaluate_days_per_regime"],
            ),
        })
    def records(frame: pd.DataFrame) -> list[dict]:
        safe = frame.astype(object).where(pd.notna(frame), None)
        return safe.to_dict("records")

    return {
        "method": method,
        "k": k,
        "seed_mean_ari": seed_ari,
        "block_mean_ari": block_ari,
        "stability_comparisons": comparisons,
        "train_support": records(train_support),
        "evaluation_support": records(evaluation_support),
        "regimes": regime_rows,
        "recurring_regimes": sum(bool(row["recurring"]) for row in regime_rows),
        "retained_features": list(clusterer.retained_features_),
        "dropped_features": clusterer.dropped_features_,
        "ood_threshold": clusterer.ood_threshold_,
    }


def _state_explanation_job(
    config: dict,
    connector: str,
    frame: pd.DataFrame,
    fold: ProtocolFold,
    *,
    pilot_mode: bool,
) -> tuple[list[dict], dict[tuple[str, int], StateClusterer]]:
    contract = feature_contract(config, connector)
    columns = contract["origin"]
    origins = unique_origin_rows(frame, columns).set_index("origin").sort_index()
    train = origins.loc[(origins.index >= fold.train_start) & (origins.index < fold.train_end), columns]
    evaluate = origins.loc[(origins.index >= fold.alert_end) & (origins.index < fold.evaluate_end), columns]
    if len(train) < 500 or len(evaluate) < 100:
        raise ValueError("Insufficient unique origins for state clustering")
    rows, models = [], {}
    for method, k in _state_specs(config, pilot=pilot_mode):
        model = _fit_clusterer(config, method, k, train, contract["origin_groups"])
        rows.append(_cluster_diagnostics(
            config, model, train, evaluate, contract["origin_groups"], method, k
        ))
        models[(method, k)] = model
    return rows, models


def _selection_mae(actual: np.ndarray, prediction: np.ndarray) -> float:
    good = np.isfinite(actual) & np.isfinite(prediction)
    return float(np.abs(actual[good] - prediction[good]).mean()) if good.any() else np.inf


def _forecast_cell(
    config: dict,
    connector: str,
    frame: pd.DataFrame,
    fold: ProtocolFold,
    band_index: int,
    target: str,
    *,
    pilot_mode: bool,
    inv_fingerprint: str,
) -> dict:
    manager = store(config)
    ident = f"{'pilot' if pilot_mode else 'forecast'}/{connector}/{fold.name}/band{band_index}/{target}"
    cell_fp = fingerprint([inv_fingerprint, ident, _public_config(config)])
    folder = manager.root / ident
    result_path = folder / "result.json"
    if manager.valid(ident, cell_fp):
        return json.loads(result_path.read_text(encoding="utf-8"))

    lo, hi = config["bands"][band_index]
    rows = frame.loc[frame.lead.between(lo, hi)].copy().reset_index(drop=True)
    if rows.empty:
        return {"job": ident, "status": "unsupported", "reason": "No configured leads in band"}
    masks = partition_masks(rows.origin, rows.delivery, fold, _protocol(config).maturity_delay_minutes)
    finite = _finite_target(rows, target)
    masks = {key: value & finite for key, value in masks.items()}
    if masks["train"].sum() < 500 or masks["select"].sum() < 100 or masks["evaluate"].sum() < 100:
        return {"job": ident, "status": "unsupported", "reason": "Insufficient chronological rows"}

    contract = feature_contract(config, connector)
    network_columns = _safe_model_columns(rows.loc[masks["train"]], contract["network_model"])
    full_columns = _safe_model_columns(rows.loc[masks["train"]], contract["fundamentals_model"])
    y = rows[f"actual_{target}"].to_numpy(dtype=float)
    anchor = rows[f"anchor_{target}"].to_numpy(dtype=float)
    predictions = {
        "persistence": anchor,
        "seasonal_daily": rows[f"seasonal48_{target}"].to_numpy(dtype=float),
        "seasonal_weekly": rows[f"seasonal336_{target}"].to_numpy(dtype=float),
    }
    trials: list[dict] = []
    fitted: dict[str, object] = {}
    for recipe, columns in (("network", network_columns), ("fundamentals", full_columns)):
        for family in ("ridge", "boost"):
            name = f"{family}_{recipe}"
            model, settings = select_correction_model(
                family,
                rows.loc[masks["train"], columns], y[masks["train"]], anchor[masks["train"]],
                rows.loc[masks["select"], columns], y[masks["select"]], anchor[masks["select"]],
                config, seed=config["seed"],
            )
            predictions[name] = model.predict(rows[columns], anchor)
            fitted[name] = model
            trials.append({"model": name, "settings": settings, "selection_mae": _selection_mae(y[masks["select"]], predictions[name][masks["select"]])})

    origin_columns = contract["origin"]
    unique_origins = unique_origin_rows(rows, origin_columns).set_index("origin").sort_index()
    train_origins = unique_origins.loc[
        (unique_origins.index >= fold.train_start) & (unique_origins.index < fold.train_end), origin_columns
    ]
    cluster_candidates = []
    cluster_models: dict[tuple[str, str, int], StateClusterer] = {}
    assignment_cache = {}
    for method, k in _state_specs(config, pilot=pilot_mode):
        model = _fit_clusterer(config, method, k, train_origins, contract["origin_groups"])
        assignment = _assign_rows(model, rows, origin_columns)
        key = ("origin", method, k)
        cluster_models[key] = model
        assignment_cache[key] = assignment
        augmented = append_cluster_probabilities(rows[full_columns], assignment.probabilities.to_numpy())
        candidate, settings = select_correction_model(
            "ridge",
            augmented.loc[masks["train"]], y[masks["train"]], anchor[masks["train"]],
            augmented.loc[masks["select"]], y[masks["select"]], anchor[masks["select"]],
            config, seed=config["seed"],
        )
        prediction = candidate.predict(augmented, anchor)
        loss = _selection_mae(y[masks["select"]], prediction[masks["select"]])
        cluster_candidates.append({
            "track": "origin", "method": method, "k": k,
            "selection_mae": loss, "settings": settings,
        })
        fitted[f"cluster_origin_probability__{method}_{k}"] = (candidate, augmented.columns.tolist())
        predictions[f"cluster_origin_probability__{method}_{k}"] = prediction

    # Forecast-condition clusters add only declared delivery-time fundamentals.
    # One deterministic row per origin prevents origins with more eligible leads
    # from receiving more clustering weight inside a lead band.
    condition_columns = contract["forecast"]
    condition_training = equal_origin_training_rows(
        rows.loc[masks["train"], ["origin", "lead", *condition_columns]],
        config["seed"],
    )
    for method, k in _state_specs(config, pilot=pilot_mode):
        model = _fit_clusterer(
            config, method, k, condition_training[condition_columns],
            contract["forecast_groups"],
        )
        assignment = _assign_rows(model, rows, condition_columns)
        key = ("condition", method, k)
        cluster_models[key] = model
        assignment_cache[key] = assignment
        augmented = append_cluster_probabilities(
            rows[full_columns], assignment.probabilities.to_numpy()
        )
        candidate, settings = select_correction_model(
            "ridge",
            augmented.loc[masks["train"]], y[masks["train"]], anchor[masks["train"]],
            augmented.loc[masks["select"]], y[masks["select"]], anchor[masks["select"]],
            config, seed=config["seed"],
        )
        prediction = candidate.predict(augmented, anchor)
        loss = _selection_mae(y[masks["select"]], prediction[masks["select"]])
        cluster_candidates.append({
            "track": "condition", "method": method, "k": k,
            "selection_mae": loss, "settings": settings,
        })
        fitted[f"cluster_condition_probability__{method}_{k}"] = (
            candidate, augmented.columns.tolist()
        )
        predictions[f"cluster_condition_probability__{method}_{k}"] = prediction

    selected_cluster = min(
        cluster_candidates,
        key=lambda value: (
            value["selection_mae"], value["k"], value["track"], value["method"]
        ),
    )
    cluster_key = (
        selected_cluster["track"], selected_cluster["method"], selected_cluster["k"]
    )
    selected_assignment = assignment_cache[cluster_key]
    interaction_parents = [
        column for column in (
            "flow_lag1", "upper_room", "lower_room",
            "endpoint__residual_uigf_difference", "endpoint__coal_available_difference",
        ) if column in full_columns
    ]
    interactions = append_cluster_interactions(
        rows[full_columns], selected_assignment.probabilities.to_numpy(), interaction_parents
    )
    interaction_model, interaction_settings = select_correction_model(
        "ridge",
        interactions.loc[masks["train"]], y[masks["train"]], anchor[masks["train"]],
        interactions.loc[masks["select"]], y[masks["select"]], anchor[masks["select"]],
        config, seed=config["seed"],
    )
    predictions["cluster_interactions"] = interaction_model.predict(interactions, anchor)
    fitted["cluster_interactions"] = (interaction_model, interactions.columns.tolist())
    trials.append({
        "model": "cluster_interactions", "settings": interaction_settings,
        "selection_mae": _selection_mae(y[masks["select"]], predictions["cluster_interactions"][masks["select"]]),
    })

    alpha = float(fitted["ridge_fundamentals"].settings["alpha"])
    local_trials = []
    for weight in config["clustering"]["local_expert_weights"]:
        model = LocalExpertModel(alpha=alpha, shrinkage=weight, seed=config["seed"]).fit(
            rows.loc[masks["train"], full_columns], y[masks["train"]], anchor[masks["train"]],
            selected_assignment.labels.to_numpy()[masks["train"]],
        )
        prediction = model.predict(
            rows[full_columns], anchor, selected_assignment.labels.to_numpy(),
            selected_assignment.out_of_distribution.to_numpy(),
        )
        local_trials.append((
            _selection_mae(y[masks["select"]], prediction[masks["select"]]), weight, model, prediction
        ))
    local_loss, local_weight, local_model, local_prediction = min(local_trials, key=lambda value: value[:2])
    predictions["cluster_local_experts"] = local_prediction
    fitted["cluster_local_experts"] = local_model
    trials.append({"model": "cluster_local_experts", "settings": {"shrinkage": local_weight, "alpha": alpha}, "selection_mae": local_loss})

    candidate_names = [
        name for name in predictions
        if name.startswith(("cluster_origin_probability", "cluster_condition_probability"))
        or name in {"cluster_interactions", "cluster_local_experts"}
    ]
    cluster_winner = min(candidate_names, key=lambda name: (_selection_mae(y[masks["select"]], predictions[name][masks["select"]]), name))
    control_names = ["persistence", "seasonal_daily", "seasonal_weekly", "ridge_network", "boost_network", "ridge_fundamentals", "boost_fundamentals"]
    control_winner = min(control_names, key=lambda name: (_selection_mae(y[masks["select"]], predictions[name][masks["select"]]), name))

    calibration = masks["calibrate"] & np.isfinite(predictions[cluster_winner])
    intervals = ResidualIntervals.fit(y[calibration], predictions[cluster_winner][calibration], config["models"]["quantiles"])
    quantiles = intervals.predict(predictions[cluster_winner])
    evaluation = masks["evaluate"] & np.isfinite(predictions[cluster_winner]) & np.isfinite(predictions[control_winner])
    scores = []
    for name, prediction in predictions.items():
        valid = masks["evaluate"] & np.isfinite(prediction)
        if not valid.any():
            continue
        scores.append({"model": name, "selected_cluster": name == cluster_winner, "selected_control": name == control_winner, **regression_metrics(y[valid], prediction[valid])})
    interval_score = interval_metrics(
        y[evaluation], quantiles[evaluation, 3], quantiles[evaluation, 1], quantiles[evaluation, 5],
        quantiles[evaluation, 0], quantiles[evaluation, 6],
    )
    effects = paired_effect_intervals(
        y[evaluation], predictions[cluster_winner][evaluation], predictions[control_winner][evaluation],
        rows.origin[evaluation], replicates=300, seed=config["seed"],
    )
    support = limited_support_flags(rows.origin[evaluation], incidents=0)

    prediction_frame = pd.DataFrame({
        "origin": rows.origin[evaluation].to_numpy(),
        "delivery": rows.delivery[evaluation].to_numpy(),
        "lead": rows.lead[evaluation].to_numpy(),
        "actual": y[evaluation],
        "anchor": anchor[evaluation],
        "cluster_prediction": predictions[cluster_winner][evaluation],
        "control_prediction": predictions[control_winner][evaluation],
        "cluster_label": selected_assignment.labels.to_numpy()[evaluation],
        "cluster_ood": selected_assignment.out_of_distribution.to_numpy()[evaluation],
        "target": target,
        "connector": connector,
        "fold": fold.name,
        "band": band_index,
    })
    for index, level in enumerate(config["models"]["quantiles"]):
        prediction_frame[f"q{level}"] = quantiles[evaluation, index]
    prediction_path = manager.parquet(folder / "predictions.parquet", prediction_frame)
    model_path = _save_joblib(config, folder / "bundle.joblib", {
        "clusterer": cluster_models[cluster_key],
        "cluster_winner": cluster_winner,
        "control_winner": control_winner,
        "fitted": fitted,
        "intervals": intervals,
        "feature_contract": contract,
        "fold": fold.as_dict(),
        "operationally_eligible": False,
        "information_track": config["claims"]["primary"],
    })
    payload = {
        "job": ident, "status": "complete", "fingerprint": cell_fp,
        "connector": connector, "fold": fold.as_dict(), "band": band_index, "target": target,
        "cluster_winner": cluster_winner, "control_winner": control_winner,
        "selected_cluster_spec": selected_cluster, "cluster_candidates": cluster_candidates,
        "trials": trials, "scores": scores, "intervals": interval_score,
        "effects": effects, "support": support,
        "n": {name: int(mask.sum()) for name, mask in masks.items()},
        "claim": config["claims"]["primary"],
        "artifacts": [
            {"path": str(prediction_path.relative_to(manager.root)), "sha256": digest(prediction_path)},
            {"path": str(model_path.relative_to(manager.root)), "sha256": digest(model_path)},
        ],
    }
    manager.json(result_path, payload)
    manager.complete(ident, cell_fp, result_path)
    return payload


def pilot(config: dict, connector: str = "VNI", max_origins: int | None = None) -> dict:
    """Run a bounded real-data pilot across state, generator and risk tracks."""
    started = time.monotonic()
    inv = inventory(config)
    contract = feature_contract(config, connector)
    columns = list(dict.fromkeys(META_COLUMNS + TARGET_COLUMNS + contract["fundamentals_model"]))
    # About 7,000 half-hour origins cover the first full chronological fold.
    frame = load_feature_rows(config, connector, columns=columns, max_origins=max_origins or 7_000)
    folds = _folds(config, frame)
    if not folds:
        raise ValueError("Pilot slice does not contain a full chronological fold")
    fold = folds[0]
    diagnostics, models = _state_explanation_job(config, connector, frame, fold, pilot_mode=True)
    explanation = min(
        diagnostics,
        key=lambda row: (-row["recurring_regimes"], -min(row["seed_mean_ari"], row["block_mean_ari"]), row["k"], row["method"]),
    )
    manager = store(config)
    explanation_path = manager.json(manager.root / f"pilot/{connector}/{fold.name}/state_diagnostics.json", {
        "connector": connector, "fold": fold.as_dict(), "candidates": diagnostics,
        "explanatory_choice": {"method": explanation["method"], "k": explanation["k"]},
        "selection_basis": "stability and support only; evaluation outcomes excluded",
    })
    selected_model = models[(explanation["method"], explanation["k"])]
    model_path = _save_joblib(config, manager.root / f"pilot/{connector}/{fold.name}/explanatory_clusterer.joblib", selected_model)
    forecast = _forecast_cell(
        config, connector, frame, fold, 0, "flow", pilot_mode=True,
        inv_fingerprint=inv["fingerprint"],
    )
    from .generator_campaign import run_generator_fold
    from .risk import run_risk_fold
    generator = run_generator_fold(
        config, connector, fold, pilot_mode=True, max_origins=max_origins or 7_000
    )
    risk = run_risk_fold(config, connector, fold)
    result = {
        "campaign": config["campaign"], "status": "pilot_complete", "connector": connector,
        "fold": fold.as_dict(), "origins_loaded": int(frame.origin.nunique()),
        "explanatory_choice": {"method": explanation["method"], "k": explanation["k"]},
        "forecast_job": forecast.get("job"), "forecast_status": forecast.get("status"),
        "cluster_winner": forecast.get("cluster_winner"), "control_winner": forecast.get("control_winner"),
        "effects": forecast.get("effects"), "elapsed_seconds": time.monotonic() - started,
        "generator_status": generator.get("status"),
        "generator_representations": generator.get("representations"),
        "generator_ablations": generator.get("ablations"),
        "risk_status": risk.get("status"),
        "risk_selected_cluster": risk.get("selected_cluster"),
        "risk_paired_recall": risk.get("paired_recall"),
        "claim": config["claims"]["primary"],
        "artifacts": [
            {"path": str(explanation_path.relative_to(manager.root)), "sha256": digest(explanation_path)},
            {"path": str(model_path.relative_to(manager.root)), "sha256": digest(model_path)},
        ],
    }
    manager.json(manager.root / f"pilot/{connector}/summary.json", result)
    return result


def _fold_from_dict(value: dict) -> ProtocolFold:
    return ProtocolFold(
        name=value["name"],
        train_start=pd.Timestamp(value["train_start"]),
        train_end=pd.Timestamp(value["train_end"]),
        select_end=pd.Timestamp(value["select_end"]),
        calibrate_end=pd.Timestamp(value["calibrate_end"]),
        alert_end=pd.Timestamp(value["alert_end"]),
        evaluate_end=pd.Timestamp(value["evaluate_end"]),
    )


def _forecast_worker(config_path: str, connector: str, fold_dict: dict, band: int, target: str, inv_fp: str) -> dict:
    os.environ.update(OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2", NUMEXPR_NUM_THREADS="2")
    config = load_config(config_path)
    contract = feature_contract(config, connector)
    columns = list(dict.fromkeys(META_COLUMNS + TARGET_COLUMNS + contract["fundamentals_model"]))
    frame = load_feature_rows(config, connector, columns=columns)
    with threadpool_limits(limits=2):
        return _forecast_cell(
            config, connector, frame, _fold_from_dict(fold_dict), band, target,
            pilot_mode=False, inv_fingerprint=inv_fp,
        )


def run(config: dict, connector: str, stage: str = "all") -> dict:
    """Run resumable connector stages with at most two parallel model cells."""
    if connector == "QNI":
        vni = config["_run"] / "run/VNI/summary.json"
        if not vni.exists():
            raise RuntimeError("VNI core run must complete before QNI starts")
        vni_summary = json.loads(vni.read_text(encoding="utf-8"))
        if vni_summary.get("status") != "complete" or vni_summary.get("stage") != "all":
            raise RuntimeError("VNI all-stage core run must complete before QNI starts")
    inv = inventory(config)
    contract = feature_contract(config, connector)
    columns = list(dict.fromkeys(META_COLUMNS + TARGET_COLUMNS + contract["fundamentals_model"]))
    frame = load_feature_rows(config, connector, columns=columns)
    folds = _folds(config, frame)
    if not folds:
        raise ValueError("No complete chronological folds")
    manager = store(config)
    started = time.monotonic()
    deadline = started + config["limits"]["batch_hours"] * 3600
    progress = []

    if stage in ("state", "all"):
        for fold in folds:
            diagnostics, _ = _state_explanation_job(config, connector, frame, fold, pilot_mode=False)
            path = manager.json(manager.root / f"state/{connector}/{fold.name}/result.json", {
                "connector": connector, "fold": fold.as_dict(), "candidates": diagnostics,
                "claim": config["claims"]["primary"],
            })
            progress.append({"stage": "state", "fold": fold.name, "status": "complete", "path": str(path.relative_to(manager.root))})
            if time.monotonic() >= deadline:
                break

    if stage in ("forecast", "all") and time.monotonic() < deadline:
        tasks = [
            (fold, band, target)
            for fold in folds for band in range(len(config["bands"])) for target in config["targets"]
        ]
        context = get_context("spawn")
        with ProcessPoolExecutor(max_workers=config["limits"]["workers"], mp_context=context) as pool:
            active = {}
            iterator = iter(tasks)

            def submit_one() -> None:
                if time.monotonic() >= deadline:
                    return
                try:
                    fold, band, target = next(iterator)
                except StopIteration:
                    return
                future = pool.submit(
                    _forecast_worker, str(config["_path"]), connector, fold.as_dict(), band, target, inv["fingerprint"]
                )
                active[future] = (fold.name, band, target)

            for _ in range(config["limits"]["workers"]):
                submit_one()
            while active:
                future = next(as_completed(active))
                key = active.pop(future)
                try:
                    value = future.result()
                    progress.append({"stage": "forecast", "fold": key[0], "band": key[1], "target": key[2], "status": value.get("status", "complete")})
                except Exception as exc:
                    progress.append({"stage": "forecast", "fold": key[0], "band": key[1], "target": key[2], "status": "failed", "error": repr(exc)})
                manager.json(manager.root / f"run/{connector}/progress.json", {"jobs": progress, "elapsed_seconds": time.monotonic() - started})
                submit_one()

    # Generator and risk stages are independently resumable and implemented in
    # their dedicated runners to keep their information contracts explicit.
    if stage in ("generator", "all") and time.monotonic() < deadline:
        from .generator_campaign import run_generator_track
        progress.extend(run_generator_track(config, connector, folds, deadline))
    if stage in ("risk", "all") and time.monotonic() < deadline:
        from .risk import run_risk_track
        progress.extend(run_risk_track(config, connector, folds, deadline))

    failures = [item for item in progress if item.get("status") == "failed"]
    summary = {
        "campaign": config["campaign"], "connector": connector,
        "stage": stage,
        "status": "failed" if failures else ("ready/resumable" if time.monotonic() >= deadline else "complete"),
        "jobs": progress, "failures": failures, "elapsed_seconds": time.monotonic() - started,
        "claim": config["claims"]["primary"],
    }
    manager.json(manager.root / f"run/{connector}/summary.json", summary)
    if failures:
        raise RuntimeError(f"{len(failures)} clustering jobs failed; see connector summary")
    return summary


def status(config: dict) -> dict:
    manager = store(config)
    trials = []
    if manager.db.exists():
        with sqlite3.connect(manager.db) as connection:
            trials = [
                {"id": row[0], "status": row[1], "output": row[2], "updated": row[3]}
                for row in connection.execute("SELECT id,status,output,updated FROM trials ORDER BY id")
            ]
    stages = {}
    for name in ("inventory.json", "pilot/VNI/summary.json", "run/VNI/summary.json", "run/QNI/summary.json", "report/manifest.json"):
        path = manager.root / name
        stages[name] = {"exists": path.exists(), "sha256": digest(path) if path.exists() else None}
    return {
        "campaign": config["campaign"], "stages": stages,
        "trials": trials, "trial_counts": pd.Series([item["status"] for item in trials]).value_counts().to_dict() if trials else {},
        "operationally_eligible": False,
    }
