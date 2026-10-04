"""Fold-fitted generator-sensitivity grouping and forecast ablations."""
from __future__ import annotations

from pathlib import Path
import json
import time

import numpy as np
import pandas as pd

from nemic.experiments.core import digest, fingerprint
from .config import store
from .data import (
    META_COLUMNS,
    TARGET_COLUMNS,
    feature_contract,
    inventory,
    load_constraint_exposure,
    load_constraint_states,
    load_feature_rows,
    load_sensitivities,
    load_unit_pressure,
)
from .generator import build_sensitivity_matrix, fit_generator_representations
from .campaign import _save_joblib
from .models import select_correction_model
from .protocol import (
    ProtocolFold,
    paired_effect_intervals,
    partition_masks,
    regression_metrics,
)


def _manual_mapping(config: dict, connector: str) -> dict[str, str]:
    result = {}
    for group, duids in config["generator"]["manual_groups"][connector].items():
        for duid in duids:
            if duid in result and result[duid] != group:
                raise ValueError(f"DUID {duid} belongs to multiple manual groups")
            result[duid] = group
    return result


def _pressure_observations(
    config: dict,
    connector: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """Map retained 5-minute DUID pressure to the prior complete half hour."""
    states = load_constraint_states(config, connector, start, end)
    if states.empty:
        return pd.DataFrame(columns=["observation_id", "version_key", "direction", "DUID", "tightening_mw"])
    upper = states[["time", "upper_constraint", "upper_version_key"]].rename(
        columns={"upper_constraint": "constraint", "upper_version_key": "version_key"}
    )
    upper["direction"] = "upper"
    lower = states[["time", "lower_constraint", "lower_version_key"]].rename(
        columns={"lower_constraint": "constraint", "lower_version_key": "version_key"}
    )
    lower["direction"] = "lower"
    active = pd.concat([upper, lower], ignore_index=True).dropna(subset=["constraint", "version_key"])
    active = active.rename(columns={"time": "state_time"})

    pressure = load_unit_pressure(config, connector, start, end)
    if pressure.empty:
        return pd.DataFrame(columns=["observation_id", "version_key", "direction", "DUID", "tightening_mw"])
    pressure["state_time"] = pd.to_datetime(pressure.time).dt.ceil("30min")
    joined = pressure.merge(
        active, on=["state_time", "direction", "constraint"], how="inner", validate="many_to_one"
    )
    joined["origin"] = joined.state_time + pd.Timedelta(minutes=30)
    joined["observation_id"] = (
        joined.origin.dt.strftime("%Y-%m-%dT%H:%M:%S") + "|" + joined.direction.astype(str)
    )
    return joined[["observation_id", "origin", "version_key", "direction", "DUID", "tightening_mw"]].copy()


def _model_columns(frame: pd.DataFrame, columns: list[str], training_mask: np.ndarray) -> list[str]:
    result = []
    for column in columns:
        if column not in frame:
            continue
        converted = pd.to_numeric(frame[column], errors="coerce")
        frame[column] = converted
        if converted.loc[training_mask].notna().any():
            result.append(column)
    return result


def _fit_fold_representations(config: dict, connector: str, fold: ProtocolFold):
    exposure = load_constraint_exposure(config, connector, fold.train_start, fold.train_end)
    if exposure.empty:
        raise ValueError("No training-period constraint exposure")
    weights = exposure.groupby("version_key", as_index=False).exposure.sum().rename(
        columns={"exposure": "exposure_weight"}
    )
    versions = set(weights.version_key.astype(str))
    sensitivities = load_sensitivities(config, connector, versions)
    matrix = build_sensitivity_matrix(
        sensitivities,
        weights,
        verified_versions=versions,
        weak_ic_factor=config["generator"]["weak_ic_factor"],
        max_abs_sensitivity=config["generator"]["extreme_sensitivity"],
    )
    suite = fit_generator_representations(
        matrix,
        manual_groups=_manual_mapping(config, connector),
        cluster_sizes=config["generator"]["learned_k"],
        svd_components=config["generator"]["svd_components"],
        random_state=config["seed"],
    )
    return exposure, matrix, suite


def _evaluate_ablation(
    config: dict,
    connector: str,
    fold: ProtocolFold,
    source: pd.DataFrame,
    generator_features: dict[str, pd.DataFrame],
    *,
    pilot_mode: bool,
) -> list[dict]:
    contract = feature_contract(config, connector)
    control_columns = contract["network_model"]
    outputs = []
    targets = ["flow"] if pilot_mode else config["targets"]
    bands = [0] if pilot_mode else range(len(config["bands"]))
    for band in bands:
        lo, hi = config["bands"][band]
        base = source.loc[source.lead.between(lo, hi)].copy().reset_index(drop=True)
        masks = partition_masks(base.origin, base.delivery, fold, config["folds"]["maturity_minutes"])
        for target in targets:
            y = base[f"actual_{target}"].to_numpy(dtype=float)
            anchor = base[f"anchor_{target}"].to_numpy(dtype=float)
            finite = np.isfinite(y) & np.isfinite(anchor)
            eligible = {key: value & finite for key, value in masks.items()}
            if eligible["train"].sum() < 500 or eligible["select"].sum() < 100 or eligible["evaluate"].sum() < 100:
                outputs.append({"target": target, "band": band, "status": "unsupported", "reason": "Insufficient chronological rows"})
                continue
            control_frame = base.copy()
            controls = _model_columns(control_frame, list(control_columns), eligible["train"])
            control_candidates = []
            for family in ("ridge", "boost"):
                control, control_trials = select_correction_model(
                    family,
                    control_frame.loc[eligible["train"], controls], y[eligible["train"]], anchor[eligible["train"]],
                    control_frame.loc[eligible["select"], controls], y[eligible["select"]], anchor[eligible["select"]],
                    config, seed=config["seed"],
                )
                control_prediction = control.predict(control_frame[controls], anchor)
                control_candidates.append({
                    "family": family,
                    "selection_mae": float(np.abs(
                        y[eligible["select"]] - control_prediction[eligible["select"]]
                    ).mean()),
                    "prediction": control_prediction,
                    "settings": control_trials,
                })
            control_winner = min(
                control_candidates,
                key=lambda row: (row["selection_mae"], row["family"]),
            )
            control_prediction = control_winner["prediction"]
            candidates = []
            for name, feature_frame in generator_features.items():
                merged = base.merge(feature_frame, on="origin", how="left", validate="many_to_one")
                additions = [column for column in feature_frame if column != "origin"]
                model_columns = _model_columns(merged, list(dict.fromkeys(controls + additions)), eligible["train"])
                for family in ("ridge", "boost"):
                    model, settings = select_correction_model(
                        family,
                        merged.loc[eligible["train"], model_columns], y[eligible["train"]], anchor[eligible["train"]],
                        merged.loc[eligible["select"], model_columns], y[eligible["select"]], anchor[eligible["select"]],
                        config, seed=config["seed"],
                    )
                    prediction = model.predict(merged[model_columns], anchor)
                    selection = float(np.abs(y[eligible["select"]] - prediction[eligible["select"]]).mean())
                    candidates.append({
                        "representation": name, "family": family, "selection_mae": selection,
                        "prediction": prediction, "settings": settings,
                    })
            if not candidates:
                outputs.append({"target": target, "band": band, "status": "unsupported", "reason": "No generator representations"})
                continue
            winner = min(candidates, key=lambda row: (row["selection_mae"], row["representation"], row["family"]))
            evaluation = eligible["evaluate"] & np.isfinite(winner["prediction"]) & np.isfinite(control_prediction)
            outputs.append({
                "target": target, "band": band, "status": "complete",
                "winner": {key: winner[key] for key in ("representation", "family", "selection_mae", "settings")},
                "control": {
                    key: control_winner[key]
                    for key in ("family", "selection_mae", "settings")
                },
                "winner_score": regression_metrics(y[evaluation], winner["prediction"][evaluation]),
                "control_score": regression_metrics(y[evaluation], control_prediction[evaluation]),
                "effects": paired_effect_intervals(
                    y[evaluation], winner["prediction"][evaluation], control_prediction[evaluation],
                    base.origin[evaluation], replicates=300, seed=config["seed"],
                ),
                "rows": int(evaluation.sum()),
            })
    return outputs


def run_generator_fold(
    config: dict,
    connector: str,
    fold: ProtocolFold,
    *,
    pilot_mode: bool = False,
    max_origins: int | None = None,
) -> dict:
    manager = store(config)
    inv = inventory(config)
    ident = f"{'pilot' if pilot_mode else 'generator'}/{connector}/{fold.name}/generator"
    job_fp = fingerprint([inv["fingerprint"], ident, fold.as_dict(), config["generator"]])
    folder = manager.root / ident
    result_path = folder / "result.json"
    if manager.valid(ident, job_fp):
        return json.loads(result_path.read_text(encoding="utf-8"))

    exposure, matrix, suite = _fit_fold_representations(config, connector, fold)
    pressure = _pressure_observations(config, connector, fold.train_start, fold.evaluate_end)
    if pressure.empty:
        raise ValueError("No origin-available DUID pressure rows")
    feature_tables: dict[str, pd.DataFrame] = {}
    artifacts = []
    for name, representation in suite.models.items():
        values = representation.aggregate_signed_pressure(pressure, allow_partial=False)
        observation_map = pressure[["observation_id", "origin"]].drop_duplicates()
        values = values.merge(observation_map, on="observation_id", how="left", validate="one_to_one")
        # Object identifiers are diagnostic, not model features. Preserve them
        # in the detailed artifact while expose numeric status/features to models.
        path = manager.parquet(folder / f"{name}_features.parquet", values)
        artifacts.append({"path": str(path.relative_to(manager.root)), "sha256": digest(path)})
        assignments = representation.assignments()
        assignment_path = manager.parquet(folder / f"{name}_assignments.parquet", assignments)
        artifacts.append({"path": str(assignment_path.relative_to(manager.root)), "sha256": digest(assignment_path)})
        feature_columns = list(representation.feature_columns)
        wide = values.groupby("origin", as_index=False)[feature_columns].sum(min_count=1)
        status_columns = [
            column for column in ("version_available", "unknown_version", "unknown_duid", "pressure_supported", "coverage_fraction")
            if column in values
        ]
        for direction in ("upper", "lower"):
            subset = values.loc[values.direction.eq(direction), ["origin", *status_columns]].copy()
            subset = subset.rename(columns={column: f"generator_{direction}__{column}" for column in status_columns})
            wide = wide.merge(subset, on="origin", how="left", validate="one_to_one")
        feature_tables[name] = wide

    contract = feature_contract(config, connector)
    columns = list(dict.fromkeys(META_COLUMNS + TARGET_COLUMNS + contract["network_model"]))
    source = load_feature_rows(config, connector, columns=columns, max_origins=max_origins)
    ablations = _evaluate_ablation(config, connector, fold, source, feature_tables, pilot_mode=pilot_mode)
    model_path = _save_joblib(config, folder / "representations.joblib", {
        "matrix": matrix, "suite": suite, "fold": fold.as_dict(),
        "operationally_eligible": False, "claim": config["claims"]["primary"],
    })
    artifacts.append({"path": str(model_path.relative_to(manager.root)), "sha256": digest(model_path)})
    payload = {
        "job": ident, "status": "complete", "fingerprint": job_fp,
        "connector": connector, "fold": fold.as_dict(),
        "exposure_rows": len(exposure), "pressure_rows": len(pressure),
        "matrix": matrix.audit, "representations": sorted(suite.models), "skipped": suite.skipped,
        "ablations": ablations, "artifacts": artifacts,
        "claim": config["claims"]["primary"],
    }
    manager.json(result_path, payload)
    manager.complete(ident, job_fp, result_path)
    return payload


def run_generator_track(
    config: dict, connector: str, folds: tuple[ProtocolFold, ...], deadline: float
) -> list[dict]:
    progress = []
    for fold in folds:
        if time.monotonic() >= deadline:
            break
        try:
            result = run_generator_fold(config, connector, fold)
            progress.append({"stage": "generator", "fold": fold.name, "status": result["status"]})
        except Exception as exc:
            progress.append({"stage": "generator", "fold": fold.name, "status": "failed", "error": repr(exc)})
    return progress
