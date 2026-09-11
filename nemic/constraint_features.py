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
    dependencies = json.loads((PILOT / "dependency_ids.json").read_text())
    constraints, units = dependencies["constraints"], dependencies["duids"]

    ic = _latest_version(pd.read_parquet(TABLES / "SPDINTERCONNECTORCONSTRAINT.parquet"), end)
    ic = _num(ic, ["FACTOR"])
    ic = ic[ic.GENCONID.isin(constraints)]
    target = ic[ic.INTERCONNECTORID.eq(config["interconnector"])].copy()
    target = target.sort_values(["GENCONID", "EFFECTIVEDATE", "VERSIONNO"]).drop_duplicates("GENCONID", keep="last")
    constraints = sorted(set(target.GENCONID))

    cp = _latest_version(pd.read_parquet(TABLES / "SPDCONNECTIONPOINTCONSTRAINT.parquet"), end)
    cp = _num(cp, ["FACTOR"])
    cp = cp[cp.GENCONID.isin(constraints) & cp.BIDTYPE.fillna("ENERGY").eq("ENERGY")]
    resolved = pd.read_parquet(TABLES / "VNI_ENERGY_TERMS.parquet")
    resolved = _num(resolved, ["FACTOR"])
    resolved = _latest_version(resolved, end)
    resolved = resolved[resolved.GENCONID.isin(constraints)]

    dispatch = _physical(pd.read_parquet(TABLES / "DISPATCHLOAD.parquet"), "DUID")
    dispatch = dispatch[(dispatch.time >= start) & (dispatch.time <= end)]
    _num(dispatch, ["TOTALCLEARED", "AVAILABILITY", "RAMPUPRATE", "RAMPDOWNRATE"])
    times = pd.date_range(start.ceil("5min"), end.floor("5min"), freq="5min")
    units = sorted(set(units) & set(dispatch.DUID))
    cleared = dispatch.pivot(index="time", columns="DUID", values="TOTALCLEARED").reindex(index=times, columns=units)
    availability = dispatch.pivot(index="time", columns="DUID", values="AVAILABILITY").reindex(index=times, columns=units)
    ramp_up = dispatch.pivot(index="time", columns="DUID", values="RAMPUPRATE").reindex(index=times, columns=units)
    ramp_down = dispatch.pivot(index="time", columns="DUID", values="RAMPDOWNRATE").reindex(index=times, columns=units)

    b = _matrix(resolved.dropna(subset=["DUID"]), "GENCONID", "DUID", "FACTOR", constraints, units)
    a = target.set_index("GENCONID").reindex(constraints).FACTOR.to_numpy(dtype="float64")
    sensitivity = -b / a[:, None]
    p = cleared.to_numpy(dtype="float64")
    delta = cleared.diff(6).to_numpy(dtype="float64")
    p_zero = np.nan_to_num(p)
    delta_zero = np.nan_to_num(delta)
    gen_lhs = p_zero @ b.T
    bound_move = delta_zero @ sensitivity.T
    pos, neg = np.maximum(delta_zero, 0), np.maximum(-delta_zero, 0)
    upper_tight = pos @ np.maximum(-sensitivity, 0).T + neg @ np.maximum(sensitivity, 0).T
    upper_relief = pos @ np.maximum(sensitivity, 0).T + neg @ np.maximum(-sensitivity, 0).T
    lower_tight, lower_relief = upper_relief, upper_tight

    up = np.minimum(np.maximum(availability.to_numpy() - p, 0),
                    np.maximum(ramp_up.to_numpy(), 0) * 30)
    down = np.minimum(np.maximum(p, 0), np.maximum(ramp_down.to_numpy(), 0) * 30)
    up, down = np.nan_to_num(up), np.nan_to_num(down)
    upper_flex = up @ np.maximum(sensitivity, 0).T + down @ np.maximum(-sensitivity, 0).T
    lower_flex = up @ np.maximum(-sensitivity, 0).T + down @ np.maximum(sensitivity, 0).T

    other_ic = ic[~ic.INTERCONNECTORID.eq(config["interconnector"]) & ic.GENCONID.isin(constraints)]
    ic_flow = pd.read_parquet(PROCESSED / "ic_5min.parquet")
    ic_flow = ic_flow.pivot(index="time", columns="INTERCONNECTORID", values="flow").reindex(times)
    other_ids = sorted(set(other_ic.INTERCONNECTORID) & set(ic_flow.columns))
    ic_b = _matrix(other_ic, "GENCONID", "INTERCONNECTORID", "FACTOR", constraints, other_ids)
    other_lhs = np.nan_to_num(ic_flow.reindex(columns=other_ids).to_numpy()) @ ic_b.T

    region = _latest_version(pd.read_parquet(TABLES / "SPDREGIONCONSTRAINT.parquet"), end)
    region = region[region.GENCONID.isin(constraints)]
    has_region = set(region.GENCONID)
    unmapped = set(resolved.loc[resolved.DUID.isna(), "GENCONID"])
    static_complete = np.array([c not in has_region and c not in unmapped for c in constraints])
    missing_units = np.isnan(p).astype("int16") @ (b != 0).T.astype("int16")
    missing_ics = np.isnan(ic_flow.reindex(columns=other_ids).to_numpy()).astype("int16") @ (ic_b != 0).T.astype("int16")

    solution = _physical(pd.read_parquet(TABLES / "DISPATCHCONSTRAINT.parquet"), "CONSTRAINTID")
    solution = solution[(solution.time >= start) & (solution.time <= end) & solution.CONSTRAINTID.isin(constraints)]
    _num(solution, ["RHS", "MARGINALVALUE", "VIOLATIONDEGREE"])
    ti = pd.Series(np.arange(len(times)), index=times)
    ci = pd.Series(np.arange(len(constraints)), index=constraints)
    solution["ti"] = solution.time.map(ti)
    solution["ci"] = solution.CONSTRAINTID.map(ci)
    solution = solution.dropna(subset=["ti", "ci", "RHS"])
    row_t = solution.ti.astype(int).to_numpy()
    row_c = solution.ci.astype(int).to_numpy()
    lhs = gen_lhs[row_t, row_c] + other_lhs[row_t, row_c]
    solution["bound"] = (solution.RHS.to_numpy() - lhs) / a[row_c]
    solution["direction"] = np.where(a[row_c] > 0, "upper", "lower")
    solution["complete"] = static_complete[row_c] & (missing_units[row_t, row_c] == 0) & (missing_ics[row_t, row_c] == 0)
    solution["bound_move"] = bound_move[row_t, row_c]
    solution["upper_tightening"] = upper_tight[row_t, row_c]
    solution["upper_relief"] = upper_relief[row_t, row_c]
    solution["lower_tightening"] = lower_tight[row_t, row_c]
    solution["lower_relief"] = lower_relief[row_t, row_c]
    solution["upper_flex"] = upper_flex[row_t, row_c]
    solution["lower_flex"] = lower_flex[row_t, row_c]
    meta = pd.read_parquet(TABLES / "GENCONDATA.parquet")
    meta = meta.sort_values(["GENCONID", "EFFECTIVEDATE", "VERSIONNO"]).drop_duplicates("GENCONID", keep="last")
    solution = solution.merge(meta[["GENCONID", "LIMITTYPE", "DESCRIPTION"]], left_on="CONSTRAINTID", right_on="GENCONID", how="left")
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
            "upper_gen_tightening": up0.upper_tightening if up0 is not None else np.nan,
            "upper_gen_relief": up0.upper_relief if up0 is not None else np.nan,
            "lower_gen_tightening": lo0.lower_tightening if lo0 is not None else np.nan,
            "lower_gen_relief": lo0.lower_relief if lo0 is not None else np.nan,
            "upper_switch_gap": upper.iloc[1].bound - up0.bound if len(upper) > 1 else np.nan,
            "lower_switch_gap": lo0.bound - lower.iloc[1].bound if len(lower) > 1 else np.nan,
            "upper_family": up0.LIMITTYPE if up0 is not None else "UNKNOWN",
            "lower_family": lo0.LIMITTYPE if lo0 is not None else "UNKNOWN",
            "upper_available_relief": up0.upper_flex if up0 is not None else np.nan,
            "lower_available_relief": lo0.lower_flex if lo0 is not None else np.nan,
            "upper_candidate_count": len(upper), "lower_candidate_count": len(lower),
            "partial_candidate_fraction": 1 - len(trusted) / max(len(group), 1),
            "envelope_inconsistent": bool(up0 is not None and lo0 is not None and lo0.bound > up0.bound),
            "upper_constraint": up0.CONSTRAINTID if up0 is not None else None,
            "lower_constraint": lo0.CONSTRAINTID if lo0 is not None else None,
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
    scores = np.nansum(np.abs(sensitivity) * movement[None, :], axis=0)
    discovery = pd.DataFrame({"DUID": units, "typical_30min_movement": movement, "influence_score": scores})
    discovery.sort_values("influence_score", ascending=False).to_csv(PILOT / "generator_discovery.csv", index=False)
    audit = {"five_minute_rows": len(features), "equation_state_rows": len(solution),
             "trusted_equation_fraction": float(solution.complete.mean()),
             "upper_coverage": float(features.conditional_upper.notna().mean()),
             "lower_coverage": float(features.conditional_lower.notna().mean()),
             "inconsistent_envelopes": int(features.envelope_inconsistent.eq(True).sum()),
             "tumut3_present": "TUMUT3" in units,
             "tumut3_constraint_count": int(resolved[resolved.DUID.eq("TUMUT3")].GENCONID.nunique())}
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
