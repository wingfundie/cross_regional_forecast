"""Reconstruct compact constraint-derived features for the guarded VNI pilot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer

from .common import DATA, PROCESSED, dump
from .constraint_ingest import CONFIG, PILOT, TABLES, load_config

CORE_FEATURES = [
    "conditional_upper", "conditional_lower", "upper_room", "lower_room",
    "upper_gen_tightening", "upper_gen_relief", "lower_gen_tightening",
    "lower_gen_relief", "upper_switch_gap", "lower_switch_gap",
    "upper_available_relief", "lower_available_relief",
    "upper_pressure_change", "lower_pressure_change",
]


def canonical_bound(rhs, ic_factor, other_lhs=0.0, relative_tol=1e-8):
    scale = max(abs(float(ic_factor)), abs(float(other_lhs)), 1.0)
    if not np.isfinite(ic_factor) or abs(ic_factor) <= relative_tol * scale:
        return np.nan
    return (float(rhs) - float(other_lhs)) / float(ic_factor)


def canonicalise_inequality(kind, rhs, factors):
    kind = str(kind).strip()
    multiplier = -1.0 if kind in {">", ">="} else 1.0
    return "<=", multiplier * float(rhs), {k: multiplier * float(v) for k, v in factors.items()}


def bound_from_solution(flow, rhs, lhs, ic_factor):
    """Isolate the target IC using AEMO's published solved LHS."""
    return np.asarray(flow) + (np.asarray(rhs) - np.asarray(lhs)) / np.asarray(ic_factor)


def envelope(bounds):
    frame = pd.DataFrame(bounds)
    upper = np.sort(frame.loc[frame.direction.eq("upper"), "bound"].dropna().to_numpy())
    lower = np.sort(frame.loc[frame.direction.eq("lower"), "bound"].dropna().to_numpy())[::-1]
    return {
        "conditional_upper": upper[0] if len(upper) else np.nan,
        "conditional_lower": lower[0] if len(lower) else np.nan,
        "upper_switch_gap": upper[1] - upper[0] if len(upper) > 1 else np.nan,
        "lower_switch_gap": lower[0] - lower[1] if len(lower) > 1 else np.nan,
    }


def _num(frame, columns):
    for column in columns:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _latest_version(frame, end):
    frame = frame.copy()
    frame["EFFECTIVEDATE"] = pd.to_datetime(frame.EFFECTIVEDATE, errors="coerce")
    frame["VERSIONNO"] = pd.to_numeric(frame.VERSIONNO, errors="coerce")
    eligible = frame[frame.EFFECTIVEDATE <= end]
    keys = (eligible[["GENCONID", "EFFECTIVEDATE", "VERSIONNO"]]
            .drop_duplicates().sort_values(["GENCONID", "EFFECTIVEDATE", "VERSIONNO"])
            .groupby("GENCONID", as_index=False).tail(1))
    return eligible.merge(keys, on=["GENCONID", "EFFECTIVEDATE", "VERSIONNO"], how="inner")


def _physical(frame, key):
    frame = frame.copy()
    frame["time"] = pd.to_datetime(frame.SETTLEMENTDATE, errors="coerce")
    for name in ["INTERVENTION", "RUNNO"]:
        if name not in frame:
            frame[name] = 0
    _num(frame, ["INTERVENTION", "RUNNO"])
    frame["LASTCHANGED"] = pd.to_datetime(frame.LASTCHANGED, errors="coerce")
    return (frame.sort_values(["time", key, "INTERVENTION", "RUNNO", "LASTCHANGED"])
            .drop_duplicates(["time", key], keep="last"))


def _matrix(frame, row, column, value, rows, columns):
    if frame.empty:
        return np.zeros((len(rows), len(columns)), dtype="float64")
    grouped = frame.groupby([row, column], as_index=False)[value].sum()
    return (grouped.pivot(index=row, columns=column, values=value)
            .reindex(index=rows, columns=columns).fillna(0).to_numpy(dtype="float64"))


def build(config_path=CONFIG):
    config = load_config(config_path)
    start, end = pd.Timestamp(config["start"]), pd.Timestamp(config["end"])
    times = pd.date_range(start.ceil("5min"), end.floor("5min"), freq="5min")

    solution = _physical(pd.read_parquet(TABLES / "DISPATCHCONSTRAINT.parquet"), "CONSTRAINTID")
    solution = solution[solution.time.between(start, end)].copy()
    _num(solution, ["RHS", "LHS", "MARGINALVALUE", "VIOLATIONDEGREE", "GENCONID_VERSIONNO"])
    solution["EFFECTIVEDATE"] = pd.to_datetime(solution.GENCONID_EFFECTIVEDATE, errors="coerce")
    solution["VERSIONNO"] = solution.GENCONID_VERSIONNO

    ic_factors = pd.read_parquet(TABLES / "SPDINTERCONNECTORCONSTRAINT.parquet")
    _num(ic_factors, ["FACTOR", "VERSIONNO"])
    ic_factors["EFFECTIVEDATE"] = pd.to_datetime(ic_factors.EFFECTIVEDATE, errors="coerce")
    target = (ic_factors[ic_factors.INTERCONNECTORID.eq(config["interconnector"])]
              [["GENCONID", "EFFECTIVEDATE", "VERSIONNO", "FACTOR"]]
              .drop_duplicates().rename(columns={"GENCONID": "CONSTRAINTID", "FACTOR": "ic_factor"}))
    solution = solution.merge(target, on=["CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO"], how="left")
    solution["version_key"] = (solution.CONSTRAINTID.astype(str) + "|" +
        solution.EFFECTIVEDATE.dt.strftime("%Y-%m-%d %H:%M:%S") + "|" + solution.VERSIONNO.astype(str))

    observed = pd.read_parquet(PROCESSED / "ic_5min.parquet")
    observed = observed[observed.INTERCONNECTORID.eq(config["interconnector"])].set_index("time")
    solution["flow"] = solution.time.map(observed.flow)
    solution["bound"] = bound_from_solution(solution.flow, solution.RHS, solution.LHS, solution.ic_factor)
    solution["direction"] = np.where(solution.ic_factor > 0, "upper", "lower")
    solution["complete"] = (solution[["flow", "RHS", "LHS", "ic_factor"]].notna().all(axis=1)
                            & solution.ic_factor.abs().gt(1e-8))

    versions = (solution[["version_key", "CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO", "ic_factor"]]
                .dropna(subset=["version_key", "ic_factor"]).drop_duplicates("version_key")
                .sort_values("version_key").reset_index(drop=True))
    version_keys = versions.version_key.tolist()
    units_frame = _physical(pd.read_parquet(TABLES / "DISPATCHLOAD.parquet"), "DUID")
    units_frame = units_frame[units_frame.time.between(start, end)].copy()
    _num(units_frame, ["TOTALCLEARED", "AVAILABILITY", "RAMPUPRATE", "RAMPDOWNRATE"])
    units = sorted(units_frame.DUID.unique())
    cleared = units_frame.pivot(index="time", columns="DUID", values="TOTALCLEARED").reindex(index=times, columns=units)
    availability = units_frame.pivot(index="time", columns="DUID", values="AVAILABILITY").reindex(index=times, columns=units)
    ramp_up = units_frame.pivot(index="time", columns="DUID", values="RAMPUPRATE").reindex(index=times, columns=units)
    ramp_down = units_frame.pivot(index="time", columns="DUID", values="RAMPDOWNRATE").reindex(index=times, columns=units)

    # A dispatch unit is structurally zero before its first published row in the
    # study month; missing values inside its observed span remain missing.
    for unit in units:
        valid = cleared[unit].notna()
        if valid.any():
            first, last = valid[valid].index[0], valid[valid].index[-1]
            outside = (cleared.index < first) | (cleared.index > last)
            for frame in [cleared, availability, ramp_up, ramp_down]:
                frame.loc[outside, unit] = 0.0

    cp_factors = pd.read_parquet(TABLES / "SPDCONNECTIONPOINTCONSTRAINT.parquet")
    _num(cp_factors, ["FACTOR", "VERSIONNO"])
    cp_factors["EFFECTIVEDATE"] = pd.to_datetime(cp_factors.EFFECTIVEDATE, errors="coerce")
    cp_factors = cp_factors[cp_factors.BIDTYPE.fillna("ENERGY").eq("ENERGY")]
    cp_factors = cp_factors.merge(
        units_frame[["DUID", "CONNECTIONPOINTID"]].drop_duplicates(), on="CONNECTIONPOINTID", how="left")
    cp_factors["version_key"] = (cp_factors.GENCONID.astype(str) + "|" +
        cp_factors.EFFECTIVEDATE.dt.strftime("%Y-%m-%d %H:%M:%S") + "|" + cp_factors.VERSIONNO.astype(str))
    terms = cp_factors[cp_factors.version_key.isin(version_keys) & cp_factors.DUID.isin(units)].copy()
    unit_sensitivity = (terms.groupby(["version_key", "GENCONID", "DUID"], as_index=False).FACTOR.sum()
                        .merge(versions[["version_key", "ic_factor"]], on="version_key", how="left"))
    unit_sensitivity["sensitivity"] = -unit_sensitivity.FACTOR / unit_sensitivity.ic_factor
    unit_sensitivity.to_parquet(PILOT / "unit_sensitivities.parquet", index=False, compression="zstd")
    movements = units_frame[["time", "DUID", "CONNECTIONPOINTID", "TOTALCLEARED"]].copy()
    movements = movements.sort_values(["DUID", "time"])
    movements["delta_30m"] = movements.groupby("DUID").TOTALCLEARED.diff(6)
    movements.to_parquet(PILOT / "unit_movements.parquet", index=False, compression="zstd")
    b = _matrix(terms, "version_key", "DUID", "FACTOR", version_keys, units)
    a = versions.set_index("version_key").reindex(version_keys).ic_factor.to_numpy(dtype="float64")
    sensitivity = -b / a[:, None]
    p = cleared.to_numpy(dtype="float64")
    delta = cleared.diff(6).to_numpy(dtype="float64")
    delta_zero = np.nan_to_num(delta)
    bound_move = delta_zero @ sensitivity.T
    pos, neg = np.maximum(delta_zero, 0), np.maximum(-delta_zero, 0)
    upper_tight = pos @ np.maximum(-sensitivity, 0).T + neg @ np.maximum(sensitivity, 0).T
    upper_relief = pos @ np.maximum(sensitivity, 0).T + neg @ np.maximum(-sensitivity, 0).T
    lower_tight, lower_relief = upper_relief, upper_tight
    missing_pressure = np.isnan(delta).astype("int16") @ (b != 0).T.astype("int16")

    up = np.minimum(np.maximum(availability.to_numpy() - p, 0),
                    np.maximum(ramp_up.to_numpy(), 0) * 30)
    down = np.minimum(np.maximum(p, 0), np.maximum(ramp_down.to_numpy(), 0) * 30)
    upper_flex = np.nan_to_num(up) @ np.maximum(sensitivity, 0).T + np.nan_to_num(down) @ np.maximum(-sensitivity, 0).T
    lower_flex = np.nan_to_num(up) @ np.maximum(-sensitivity, 0).T + np.nan_to_num(down) @ np.maximum(sensitivity, 0).T

    ti = pd.Series(np.arange(len(times)), index=times)
    vi = pd.Series(np.arange(len(version_keys)), index=version_keys)
    solution["ti"] = solution.time.map(ti)
    solution["vi"] = solution.version_key.map(vi)
    eligible = solution.ti.notna() & solution.vi.notna()
    row_t = solution.loc[eligible, "ti"].astype(int).to_numpy()
    row_v = solution.loc[eligible, "vi"].astype(int).to_numpy()
    for name, matrix in [("bound_move", bound_move), ("upper_tightening", upper_tight),
                         ("upper_relief", upper_relief), ("lower_tightening", lower_tight),
                         ("lower_relief", lower_relief), ("upper_flex", upper_flex),
                         ("lower_flex", lower_flex)]:
        solution.loc[eligible, name] = matrix[row_t, row_v]
    solution["pressure_complete"] = False
    solution.loc[eligible, "pressure_complete"] = missing_pressure[row_t, row_v] == 0

    meta = pd.read_parquet(TABLES / "GENCONDATA.parquet")
    _num(meta, ["VERSIONNO"])
    meta["EFFECTIVEDATE"] = pd.to_datetime(meta.EFFECTIVEDATE, errors="coerce")
    meta = meta[["GENCONID", "EFFECTIVEDATE", "VERSIONNO", "LIMITTYPE", "DESCRIPTION"]].drop_duplicates()
    solution = solution.merge(meta, left_on=["CONSTRAINTID", "EFFECTIVEDATE", "VERSIONNO"],
                              right_on=["GENCONID", "EFFECTIVEDATE", "VERSIONNO"], how="left")
    solution.to_parquet(PILOT / "equation_state.parquet", index=False, compression="zstd")

    flow = pd.read_parquet(PROCESSED / "ic_5min.parquet")
    flow = flow[flow.INTERCONNECTORID.eq(config["interconnector"])].set_index("time").flow
    rows = []
    for time, group in solution.groupby("time", sort=True):
        trusted = group[group.complete & np.isfinite(group.bound)]
        upper = trusted[trusted.direction.eq("upper")].sort_values("bound")
        lower = trusted[trusted.direction.eq("lower")].sort_values("bound", ascending=False)
        up0 = upper.iloc[0] if len(upper) else None
        lo0 = lower.iloc[0] if len(lower) else None
        f = flow.get(time, np.nan)
        rows.append({
            "time": time,
            "conditional_upper": up0.bound if up0 is not None else np.nan,
            "conditional_lower": lo0.bound if lo0 is not None else np.nan,
            "upper_room": up0.bound - f if up0 is not None else np.nan,
            "lower_room": f - lo0.bound if lo0 is not None else np.nan,
            "upper_gen_tightening": up0.upper_tightening if up0 is not None and up0.pressure_complete else np.nan,
            "upper_gen_relief": up0.upper_relief if up0 is not None and up0.pressure_complete else np.nan,
            "lower_gen_tightening": lo0.lower_tightening if lo0 is not None and lo0.pressure_complete else np.nan,
            "lower_gen_relief": lo0.lower_relief if lo0 is not None and lo0.pressure_complete else np.nan,
            "upper_switch_gap": upper.iloc[1].bound - up0.bound if len(upper) > 1 else np.nan,
            "lower_switch_gap": lo0.bound - lower.iloc[1].bound if len(lower) > 1 else np.nan,
            "upper_family": up0.LIMITTYPE if up0 is not None else "UNKNOWN",
            "lower_family": lo0.LIMITTYPE if lo0 is not None else "UNKNOWN",
            "upper_available_relief": up0.upper_flex if up0 is not None else np.nan,
            "lower_available_relief": lo0.lower_flex if lo0 is not None else np.nan,
            "upper_candidate_count": len(upper), "lower_candidate_count": len(lower),
            "partial_candidate_fraction": 1 - len(trusted) / max(len(group), 1),
            "pressure_complete_fraction": float(group.pressure_complete.mean()),
            "envelope_inconsistent": bool(up0 is not None and lo0 is not None and lo0.bound > up0.bound),
            "upper_constraint": up0.CONSTRAINTID if up0 is not None else None,
            "lower_constraint": lo0.CONSTRAINTID if lo0 is not None else None,
            "upper_version_key": up0.version_key if up0 is not None else None,
            "lower_version_key": lo0.version_key if lo0 is not None else None,
        })
    features = pd.DataFrame(rows).set_index("time").reindex(times)
    features["upper_pressure_change"] = (features.upper_gen_tightening - features.upper_gen_relief).diff(6)
    features["lower_pressure_change"] = (features.lower_gen_tightening - features.lower_gen_relief).diff(6)
    features["upper_envelope_move_persistence"] = 0.0
    features["lower_envelope_move_persistence"] = 0.0
    features.index.name = "time"
    features.reset_index().to_parquet(PILOT / "constraint_features_5min.parquet", index=False, compression="zstd")
    native = features.reset_index()
    f30 = native[native.time.dt.minute.isin([0, 30])].set_index("time")
    f30.reset_index().to_parquet(PILOT / "constraint_features_30min.parquet", index=False, compression="zstd")

    movement = np.nanmean(np.abs(delta), axis=0)
    active_frequency = np.array([(solution.version_key.eq(key)).sum() for key in version_keys], dtype="float64")
    scores = np.nansum(np.abs(sensitivity) * active_frequency[:, None], axis=0) * movement
    discovery = pd.DataFrame({"DUID": units, "typical_30min_movement": movement, "influence_score": scores})
    discovery.sort_values("influence_score", ascending=False).to_csv(PILOT / "generator_discovery.csv", index=False)
    observed_audit = observed.reindex(features.index)
    upper_valid = features.conditional_upper.notna() & observed_audit.export.notna()
    lower_valid = features.conditional_lower.notna() & observed_audit["import"].notna()
    audit = {"five_minute_rows": len(features), "equation_state_rows": len(solution),
             "trusted_equation_fraction": float(solution.complete.mean()),
             "exact_version_match_fraction": float(solution.ic_factor.notna().mean()),
             "pressure_complete_fraction": float(solution.pressure_complete.mean()),
             "upper_coverage": float(features.conditional_upper.notna().mean()),
             "lower_coverage": float(features.conditional_lower.notna().mean()),
             "upper_reconstruction_mae_mw": float((features.loc[upper_valid, "conditional_upper"] -
                                                     observed_audit.loc[upper_valid, "export"]).abs().mean()),
             "lower_reconstruction_mae_mw": float((-features.loc[lower_valid, "conditional_lower"] -
                                                     observed_audit.loc[lower_valid, "import"]).abs().mean()),
             "upper_setter_match_fraction": float((features.loc[upper_valid, "upper_constraint"] ==
                                                     observed_audit.loc[upper_valid, "EXPORTGENCONID"]).mean()),
             "lower_setter_match_fraction": float((features.loc[lower_valid, "lower_constraint"] ==
                                                     observed_audit.loc[lower_valid, "IMPORTGENCONID"]).mean()),
             "inconsistent_envelopes": int(features.envelope_inconsistent.eq(True).sum()),
             "tumut3_present": "TUMUT3" in units,
             "tumut3_constraint_count": int(unit_sensitivity[unit_sensitivity.DUID.eq("TUMUT3")].GENCONID.nunique())}
    dump(PILOT / "feature_audit.json", audit)
    return f30, audit


def evaluate(config_path=CONFIG):
    config = load_config(config_path)
    if not (PILOT / "constraint_features_30min.parquet").exists():
        build(config_path)
    features = pd.read_parquet(PILOT / "constraint_features_30min.parquet").set_index("time")
    target = pd.read_parquet(PROCESSED / "targets.parquet")
    target = target[target.ic.eq("VIC1-NSW1")].set_index("time")
    target = target.loc[pd.Timestamp(config["start"]):pd.Timestamp(config["end"])]
    rows, predictions = [], []
    for name in ["export_tight", "import_tight"]:
        frame = pd.DataFrame({"actual": target[name], "baseline": target[name].shift(1)})
        x = features[CORE_FEATURES].shift(1).reindex(frame.index)
        frame = frame.join(x)
        frame = frame.dropna(subset=["actual", "baseline"])
        population_rows = len(frame)
        frame = frame[frame[CORE_FEATURES].notna().any(axis=1)]
        if len(frame) < 120:
            rows.append({"target": name, "population_rows": population_rows,
                         "matched_rows": len(frame), "status": "insufficient feature coverage"})
            continue
        split = frame.index.min() + (frame.index.max() - frame.index.min()) * 2 / 3
        train, test = frame.index <= split, frame.index > split
        usable = [c for c in CORE_FEATURES if frame.loc[train, c].notna().any()]
        imputer = SimpleImputer(strategy="median", add_indicator=True)
        x_train = imputer.fit_transform(frame.loc[train, usable])
        x_test = imputer.transform(frame.loc[test, usable])
        model = HistGradientBoostingRegressor(loss="absolute_error", max_iter=120,
                    max_leaf_nodes=15, min_samples_leaf=30, l2_regularization=5, random_state=741)
        model.fit(np.column_stack([frame.loc[train, "baseline"], x_train]), frame.loc[train, "actual"])
        candidate = model.predict(np.column_stack([frame.loc[test, "baseline"], x_test]))
        baseline = frame.loc[test, "baseline"].to_numpy()
        actual = frame.loc[test, "actual"].to_numpy()
        bmae, cmae = np.mean(np.abs(baseline - actual)), np.mean(np.abs(candidate - actual))
        rows.append({"target": name, "population_rows": population_rows, "matched_rows": len(frame),
                     "coverage": len(frame) / population_rows,
                     "train_rows": int(train.sum()), "test_rows": int(test.sum()),
                     "feature_count": len(usable), "baseline_mae": bmae, "candidate_mae": cmae,
                     "mae_improvement": bmae - cmae, "relative_improvement": (bmae - cmae) / bmae})
        predictions.append(pd.DataFrame({"time": frame.index[test], "target": name, "actual": actual,
                                         "baseline": baseline, "candidate": candidate}))
    report = {"design": "retrospective one-month feasibility pilot; not untouched or operational",
              "targets": rows}
    dump(PILOT / "pilot_scores.json", report)
    pd.concat(predictions).to_parquet(PILOT / "pilot_predictions.parquet", index=False)
    return report


def run(config_path=CONFIG):
    _, audit = build(config_path)
    report = evaluate(config_path)
    print(json.dumps({"feature_audit": audit, "evaluation": report}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(CONFIG))
    args = parser.parse_args()
    run(args.config)
