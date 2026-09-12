"""Aggregate a 24-month VNI or QNI study and build reproducible reports."""
from __future__ import annotations

import argparse
import hashlib
import gzip
import json
import sys
from pathlib import Path

import markdown
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "report_theme"))

from nemic.common import DATA, PROCESSED  # noqa: E402
from nemic.constraint_longitudinal import load_study, months_between, path_bytes  # noqa: E402
from report_theme import VERSION, finding, hero, metric, render_page, style_plotly  # noqa: E402


SEASONS = {12: "Summer", 1: "Summer", 2: "Summer", 3: "Autumn", 4: "Autumn", 5: "Autumn",
           6: "Winter", 7: "Winter", 8: "Winter", 9: "Spring", 10: "Spring", 11: "Spring"}


def season(series):
    return series.dt.month.map(SEASONS)


def q(series, value):
    return pd.to_numeric(series, errors="coerce").quantile(value)


def fmt(value, digits=1):
    return "—" if pd.isna(value) else f"{value:,.{digits}f}"


def md_table(frame):
    return frame.to_markdown(index=False).replace("nan", "—")


def weighted(values, weights):
    valid = pd.notna(values) & pd.notna(weights) & (weights > 0)
    return np.average(values[valid], weights=weights[valid]) if valid.any() else np.nan


def aggregate(config_path):
    config = load_study(config_path)
    root = DATA / config["output_dir"]
    periods = months_between(config["start"], config["end"])
    month_dirs = [root / "months" / str(period) for period in periods]
    incomplete = [str(period) for period, path in zip(periods, month_dirs)
                  if not (path / "unit_pressure_5min.parquet").exists()]
    if incomplete:
        raise RuntimeError(f"Study is incomplete; missing compact outputs for: {incomplete}")

    population, influences, sensitivity, audits = [], [], [], []
    contraction_events, contraction_thresholds = [], []
    pressure_groups = []
    for period, path in zip(periods, month_dirs):
        label = SEASONS[period.month]
        p = pd.read_parquet(path / "constraint_population_summary.parquet")
        p["month"], p["season"] = str(period), label
        population.append(p)
        g = pd.read_csv(path / "generator_influence.csv")
        g["month"], g["season"] = str(period), label
        influences.append(g)
        s = pd.read_parquet(path / "unit_sensitivities.parquet")
        sensitivity.append(s)
        pressure = pd.read_parquet(path / "unit_pressure_5min.parquet")
        pressure["season"] = season(pressure.time)
        pressure["abs_impact"] = pressure.bound_impact_mw.abs()
        pressure["tightening_positive"] = pressure.tightening_mw.clip(lower=0)
        pressure["relief_positive"] = -pressure.tightening_mw.clip(upper=0)
        pressure["contraction_abs_impact"] = pressure.abs_impact.where(pressure.contraction, 0)
        pressure["contraction_tightening"] = pressure.tightening_positive.where(pressure.contraction, 0)
        pressure["contraction_relief"] = pressure.relief_positive.where(pressure.contraction, 0)
        pressure["contraction_positive"] = pressure.contraction & pressure.tightening_mw.gt(0)
        grouped = pressure.groupby(["season", "direction", "DUID"], as_index=False).agg(
            contribution_rows=("time", "size"), total_abs_impact=("abs_impact", "sum"),
            mean_abs_impact=("abs_impact", "mean"), p95_abs_impact=("abs_impact", lambda x: x.quantile(.95)),
            total_tightening=("tightening_positive", "sum"), total_relief=("relief_positive", "sum"),
            contraction_rows=("contraction", "sum"), reversal_rows=("reversal", "sum"),
            forced_rows=("forced", "sum"), contraction_onsets=("contraction_onset", "sum"),
            forced_onsets=("forced_onset", "sum"), contraction_abs_impact=("contraction_abs_impact", "sum"),
            contraction_tightening=("contraction_tightening", "sum"),
            contraction_relief=("contraction_relief", "sum"),
            contraction_positive_rows=("contraction_positive", "sum"))
        pressure_groups.append(grouped)
        audits.append(json.loads((path / "feature_audit.json").read_text(encoding="utf-8")))
        event = pd.read_parquet(path / "influence_events.parquet")
        event = event[event.contraction_onset].copy()
        event["month"], event["season"] = str(period), label
        event["drop_mw"] = -event.limit_change_30m
        event["half_hour"] = event.time.dt.hour * 2 + (event.time.dt.minute >= 30).astype(int)
        contraction_events.append(event)
        influence_summary = json.loads((path / "influence_summary.json").read_text(encoding="utf-8"))
        for direction in ["upper", "lower"]:
            contraction_thresholds.append({
                "month": str(period), "season": label, "direction": direction,
                "threshold_mw": influence_summary[f"{direction}_contraction_threshold_mw"],
                "contraction_intervals": influence_summary[f"{direction}_contraction_intervals"],
                "contraction_episodes": influence_summary[f"{direction}_contraction_episodes"],
            })

    pop = pd.concat(population, ignore_index=True)
    influence = pd.concat(influences, ignore_index=True)
    factors = pd.concat(sensitivity, ignore_index=True).drop_duplicates(["version_key", "DUID"])
    unit_season = pd.concat(pressure_groups, ignore_index=True).groupby(
        ["season", "direction", "DUID"], as_index=False).agg(
            contribution_rows=("contribution_rows", "sum"), total_abs_impact=("total_abs_impact", "sum"),
            mean_abs_impact=("mean_abs_impact", "mean"), p95_abs_impact=("p95_abs_impact", "max"),
            total_tightening=("total_tightening", "sum"), total_relief=("total_relief", "sum"),
            contraction_rows=("contraction_rows", "sum"), reversal_rows=("reversal_rows", "sum"),
            forced_rows=("forced_rows", "sum"), contraction_onsets=("contraction_onsets", "sum"),
            forced_onsets=("forced_onsets", "sum"), contraction_abs_impact=("contraction_abs_impact", "sum"),
            contraction_tightening=("contraction_tightening", "sum"),
            contraction_relief=("contraction_relief", "sum"),
            contraction_positive_rows=("contraction_positive_rows", "sum"))

    unit = unit_season.groupby("DUID", as_index=False).agg(
        contribution_rows=("contribution_rows", "sum"), total_abs_impact_mw_observations=("total_abs_impact", "sum"),
        mean_abs_bound_impact_mw=("mean_abs_impact", "mean"), p95_abs_bound_impact_mw=("p95_abs_impact", "max"),
        total_tightening_mw_observations=("total_tightening", "sum"),
        total_relief_mw_observations=("total_relief", "sum"), contraction_contribution_rows=("contraction_rows", "sum"),
        reversal_contribution_rows=("reversal_rows", "sum"), forced_contribution_rows=("forced_rows", "sum"),
        contraction_onsets=("contraction_onsets", "sum"), forced_onsets=("forced_onsets", "sum"),
        contraction_abs_impact_mw_observations=("contraction_abs_impact", "sum"),
        contraction_tightening_mw_observations=("contraction_tightening", "sum"),
        contraction_relief_mw_observations=("contraction_relief", "sum"),
        contraction_positive_rows=("contraction_positive_rows", "sum"))
    monthly = influence.groupby("DUID")
    corr = monthly.apply(lambda x: pd.Series({
        "active_months": x.month.nunique(),
        "active_constraint_versions": x.active_constraint_versions.max(),
        "limit_move_spearman": weighted(x.limit_move_spearman.to_numpy(), x.contribution_rows.to_numpy()),
        "flow_move_spearman": weighted(x.flow_move_spearman.to_numpy(), x.contribution_rows.to_numpy()),
        "top_contributor_intervals": x.top_contributor_intervals.sum(),
    }), include_groups=False).reset_index()
    unit = unit.merge(corr, on="DUID", how="left")
    factor_stats = factors.groupby("DUID", as_index=False).agg(
        equation_versions=("version_key", "nunique"), factor_min=("FACTOR", "min"), factor_max=("FACTOR", "max"),
        sensitivity_min=("sensitivity", "min"), sensitivity_mean=("sensitivity", "mean"),
        sensitivity_max=("sensitivity", "max"), sensitivity_abs_max=("sensitivity", lambda x: x.abs().max()))
    unit = unit.merge(factor_stats, on="DUID", how="left")
    unit["overall_rank"] = unit.total_abs_impact_mw_observations.rank(method="min", ascending=False).astype(int)
    unit["contraction_positive_share"] = (unit.contraction_positive_rows
                                           / unit.contraction_contribution_rows.replace(0, np.nan))
    unit["contraction_mean_positive_tightening_mw"] = (unit.contraction_tightening_mw_observations
                                                        / unit.contraction_contribution_rows.replace(0, np.nan))
    unit["contraction_rank"] = unit.contraction_tightening_mw_observations.rank(
        method="min", ascending=False).astype(int)
    unit["reversal_rank"] = unit.reversal_contribution_rows.rank(method="min", ascending=False).astype(int)
    unit["forced_rank"] = unit.forced_contribution_rows.rank(method="min", ascending=False).astype(int)
    unit = unit.sort_values("overall_rank")

    set_rows = pd.read_parquet(root / "standing" / "GENCONSET.parquet")
    set_map = set_rows.groupby("GENCONID").GENCONSETID.agg(lambda x: ", ".join(sorted(set(x.dropna().astype(str)))))
    invokes = pd.read_parquet(root / "standing" / "GENCONSETINVOKE.parquet")
    invokes["STARTINTERVALDATETIME"] = pd.to_datetime(invokes.STARTINTERVALDATETIME, errors="coerce")
    invokes["ENDINTERVALDATETIME"] = pd.to_datetime(invokes.ENDINTERVALDATETIME, errors="coerce")
    invoked = set(invokes.loc[(invokes.STARTINTERVALDATETIME <= pd.Timestamp(config["end"]))
                              & (invokes.ENDINTERVALDATETIME.isna()
                                 | (invokes.ENDINTERVALDATETIME >= pd.Timestamp(config["start"]))), "GENCONSETID"].dropna())
    equations = pop.groupby(["CONSTRAINTID", "version_key", "direction", "EFFECTIVEDATE", "VERSIONNO", "ic_factor",
                             "LIMITTYPE", "DESCRIPTION"], dropna=False, as_index=False).agg(
        applicable_intervals=("applicable_intervals", "sum"), binding_intervals=("binding_intervals", "sum"),
        near_binding_intervals=("near_binding_intervals", "sum"), near_setting_intervals=("near_setting_intervals", "sum"),
        leading_intervals=("leading_intervals", "sum"), mean_abs_marginal_value=("mean_abs_marginal_value", "mean"),
        min_ic_slack_mw=("min_ic_slack_mw", "min"), median_ic_slack_mw=("median_ic_slack_mw", "median"))
    equations["constraint_sets"] = equations.CONSTRAINTID.map(set_map).fillna("")
    equations["invoked_sets"] = equations.constraint_sets.map(
        lambda text: ", ".join(sorted(set(text.split(", ")) & set(map(str, invoked)))) if text else "")
    equations = equations.sort_values(["leading_intervals", "binding_intervals", "near_setting_intervals"], ascending=False)

    ic = pd.read_parquet(PROCESSED / "ic_5min.parquet")
    ic = ic[ic.INTERCONNECTORID.eq(config["interconnector"])
            & ic.time.between(pd.Timestamp(config["start"]), pd.Timestamp(config["end"]))].copy()
    ic["season"], ic["half_hour"] = season(ic.time), ic.time.dt.hour * 2 + (ic.time.dt.minute >= 30).astype(int)
    signs = np.sign(ic.flow).replace(0, np.nan).ffill()
    ic["flow_reversal"] = signs.ne(signs.shift()) & signs.notna() & signs.shift().notna()
    ic["forced_export"], ic["forced_import"] = ic["export"].lt(0), ic["import"].lt(0)

    def state_summary(frame, cols):
        rows = []
        for keys, x in frame.groupby(cols, observed=True):
            keys = keys if isinstance(keys, tuple) else (keys,)
            rows.append(dict(zip(cols, keys)) | {
                "intervals": len(x), "flow_mean_mw": x.flow.mean(), "flow_median_mw": x.flow.median(),
                "flow_p05_mw": q(x.flow, .05), "flow_p95_mw": q(x.flow, .95),
                "export_limit_median_mw": x["export"].median(), "export_limit_p05_mw": q(x["export"], .05),
                "import_limit_median_mw": x["import"].median(), "import_limit_p05_mw": q(x["import"], .05),
                "northward_flow_share": x.flow.gt(0).mean(), "southward_flow_share": x.flow.lt(0).mean(),
                "flow_reversals": x.flow_reversal.sum(), "forced_export_intervals": x.forced_export.sum(),
                "forced_import_intervals": x.forced_import.sum()})
        return pd.DataFrame(rows)

    seasonal = state_summary(ic, ["season"])
    diurnal = state_summary(ic, ["half_hour"])
    diurnal["time_of_day"] = diurnal.half_hour.map(lambda h: f"{h//2:02d}:{(h%2)*30:02d}")

    setter_rows = []
    for period, path in zip(periods, month_dirs):
        features = pd.read_parquet(path / "constraint_features_5min.parquet",
                                   columns=["time", "upper_constraint", "lower_constraint"])
        observed = ic[ic.time.between(period.start_time, period.end_time.floor("5min"))][
            ["time", "EXPORTGENCONID", "IMPORTGENCONID"]]
        joined = features.merge(observed, on="time", how="left")
        joined["season"] = season(joined.time)
        setter_rows.append(joined)
    setters = pd.concat(setter_rows, ignore_index=True)
    setter_match = setters.groupby("season", as_index=False).agg(
        upper_intervals=("upper_constraint", "size"),
        upper_setter_match=("upper_constraint", lambda x: x.eq(setters.loc[x.index, "EXPORTGENCONID"]).mean()),
        lower_setter_match=("lower_constraint", lambda x: x.eq(setters.loc[x.index, "IMPORTGENCONID"]).mean()))

    constraint_season = pop.groupby(["season", "direction"], as_index=False).agg(
        applicable_constraint_intervals=("applicable_intervals", "sum"), binding_constraint_intervals=("binding_intervals", "sum"),
        near_binding_constraint_intervals=("near_binding_intervals", "sum"), near_setting_constraint_intervals=("near_setting_intervals", "sum"),
        leading_constraint_intervals=("leading_intervals", "sum"))
    seasonal = seasonal.merge(setter_match, on="season", how="left")

    audit_weights = np.array([a["five_minute_rows"] for a in audits])
    coverage = {key: weighted(np.array([a[key] for a in audits]), audit_weights) for key in [
        "upper_coverage", "lower_coverage", "upper_reconstruction_mae_mw",
        "lower_reconstruction_mae_mw", "exact_version_match_fraction"]}
    events = pd.concat(contraction_events, ignore_index=True)
    thresholds = pd.DataFrame(contraction_thresholds)
    contraction_constraints = (events.groupby(["direction", "constraint"], dropna=False, as_index=False)
                               .agg(episodes=("time", "size"), median_drop_mw=("drop_mw", "median"),
                                    p90_drop_mw=("drop_mw", lambda x: x.quantile(.9)),
                                    max_drop_mw=("drop_mw", "max"))
                               .sort_values(["direction", "episodes"], ascending=[True, False]))
    return (config, root, unit, unit_season, factors, equations, seasonal, diurnal,
            constraint_season, coverage, events, thresholds, contraction_constraints)


def build(config_path):
    (config, root, units, unit_season, factors, equations, seasonal, diurnal,
     constraint_season, coverage, contraction_events, contraction_thresholds,
     contraction_constraints) = aggregate(config_path)
    labels = {
        "VIC1-NSW1": {"code": "vni", "name": "VNI", "flow": "VIC→NSW"},
        "NSW1-QLD1": {"code": "qni", "name": "QNI", "flow": "NSW→QLD"},
    }
    metadata = labels[config["interconnector"]]
    prefix, name = f"{metadata['code']}_2y", metadata["name"]
    built_label = pd.Timestamp.now().strftime("%d %b %Y").lstrip("0")
    def artifact(suffix):
        return f"{prefix}_{suffix}"
    docs_data = ROOT / "docs" / "data"
    docs_data.mkdir(parents=True, exist_ok=True)
    units.to_csv(docs_data / artifact("generator_rankings.csv"), index=False)
    unit_season.to_csv(docs_data / artifact("generator_seasonal_rankings.csv"), index=False)
    factors_path = docs_data / artifact("unit_equation_factors.csv.gz")
    # Fix the gzip timestamp so repeated report builds produce the same
    # snapshot hash and do not create needless repository churn.
    with gzip.GzipFile(filename=str(factors_path), mode="wb", mtime=0) as handle:
        factors.sort_values(["GENCONID", "version_key", "DUID"]).to_csv(
            handle, index=False, lineterminator="\n")
    equations.to_csv(docs_data / artifact("constraint_equations.csv"), index=False)
    seasonal.to_csv(docs_data / artifact("seasonal_summary.csv"), index=False)
    diurnal.to_csv(docs_data / artifact("diurnal_summary.csv"), index=False)
    constraint_season.to_csv(docs_data / artifact("constraint_population_by_season.csv"), index=False)
    event_columns = ["time", "month", "season", "half_hour", "direction", "constraint", "version_key",
                     "drop_mw", "contraction_threshold_mw", "limit", "flow"]
    contraction_events[event_columns].to_csv(docs_data / artifact("contraction_events.csv"), index=False)
    contraction_thresholds.to_csv(docs_data / artifact("contraction_thresholds_monthly.csv"), index=False)
    contraction_constraints.to_csv(docs_data / artifact("contraction_constraints.csv"), index=False)

    contraction_overall = units[["DUID", "contraction_contribution_rows", "contraction_onsets",
                                 "contraction_tightening_mw_observations",
                                 "contraction_relief_mw_observations",
                                 "contraction_abs_impact_mw_observations",
                                 "contraction_mean_positive_tightening_mw",
                                 "contraction_positive_share", "contraction_rank"]].copy()
    contraction_overall.insert(0, "scope", "overall")
    contraction_by_direction = (unit_season.groupby(["direction", "DUID"], as_index=False)
                                .agg(contraction_contribution_rows=("contraction_rows", "sum"),
                                     contraction_onsets=("contraction_onsets", "sum"),
                                     contraction_tightening_mw_observations=("contraction_tightening", "sum"),
                                     contraction_relief_mw_observations=("contraction_relief", "sum"),
                                     contraction_abs_impact_mw_observations=("contraction_abs_impact", "sum"),
                                     contraction_positive_rows=("contraction_positive_rows", "sum")))
    contraction_by_direction["contraction_mean_positive_tightening_mw"] = (
        contraction_by_direction.contraction_tightening_mw_observations
        / contraction_by_direction.contraction_contribution_rows.replace(0, np.nan))
    contraction_by_direction["contraction_positive_share"] = (
        contraction_by_direction.contraction_positive_rows
        / contraction_by_direction.contraction_contribution_rows.replace(0, np.nan))
    contraction_by_direction["contraction_rank"] = (contraction_by_direction.groupby("direction")
        .contraction_tightening_mw_observations.rank(method="min", ascending=False).astype(int))
    contraction_by_direction = contraction_by_direction.rename(columns={"direction": "scope"}).drop(
        columns="contraction_positive_rows")
    contraction_rankings = pd.concat([contraction_overall, contraction_by_direction], ignore_index=True)
    contraction_rankings = contraction_rankings.sort_values(["scope", "contraction_rank"])
    contraction_rankings.to_csv(docs_data / artifact("generator_contraction_rankings.csv"), index=False)
    feature_dictionary = pd.DataFrame([
        ("conditional_upper/lower", "MW", "Tightest reconstructed directional envelope", "2"),
        ("upper/lower_room", "MW", "Distance between observed flow and reconstructed envelope", "2"),
        ("upper/lower_switch_gap", "MW", "Gap between leading and runner-up equation", "2"),
        ("upper/lower_gen_tightening", "MW", "Sum of signed unit movements that contract capacity", "2"),
        ("upper/lower_sharp_contraction_risk", "rate/MW", "Recent episode rate and magnitude of 30-minute directional-limit contractions", "4"),
        ("upper/lower_gen_relief", "MW", "Sum of signed unit movements that expand capacity", "2"),
        ("upper/lower_pressure_change", "MW", "Thirty-minute change in aggregate equation pressure", "2"),
        ("upper/lower_available_relief", "MW", "Ramp and availability limited local relief proxy", "2"),
        ("upper/lower_candidate_count", "count", "Applicable equation count", "2"),
        ("partial_candidate_fraction", "fraction", "Share of candidate bounds with incomplete pressure", "1"),
        ("pressure_complete_fraction", "fraction", "Share of equation pressure mapped to unit dispatch", "1"),
        ("envelope_inconsistent", "flag", "Reconstructed lower bound exceeds upper bound", "1"),
        ("upper/lower_family", "category", "Low-cardinality leading constraint family", "2 categorical"),
        ("reported/reconstructed setter disagreement", "flag", "Published setter differs from reconstructed leader", "2"),
        ("selected unit pressure", "MW", "Frozen top-unit sensitivity multiplied by forecast movement", "4–8"),
        ("clock/annual harmonics", "unitless", "Compact diurnal and seasonal phase", "4–8"),
    ], columns=["feature_group", "unit", "definition", "recommended_variable_count"])
    feature_dictionary.to_csv(docs_data / artifact("feature_dictionary.csv"), index=False)
    standing_audit = json.loads((root / "standing" / "standing_audit.json").read_text(encoding="utf-8"))
    (docs_data / artifact("source_manifest.json")).write_text(json.dumps(standing_audit, indent=2), encoding="utf-8")

    top = units.head(20).copy()
    top_display = top[["overall_rank", "DUID", "active_months", "equation_versions", "total_abs_impact_mw_observations",
                       "mean_abs_bound_impact_mw", "p95_abs_bound_impact_mw", "total_tightening_mw_observations",
                       "contraction_rank", "reversal_rank", "forced_rank", "flow_move_spearman"]].copy()
    top_display.columns = ["Rank", "DUID", "Active months", "Equation versions", "Abs impact MW-observations",
                           "Mean abs impact MW", "P95 abs impact MW", "Tightening MW-observations",
                           "Contraction rank", "Reversal rank", "Forced rank", "Flow-move rho"]
    for col in ["Abs impact MW-observations", "Tightening MW-observations"]:
        top_display[col] = top_display[col].map(lambda x: fmt(x, 0))
    for col in ["Mean abs impact MW", "P95 abs impact MW", "Flow-move rho"]:
        top_display[col] = top_display[col].map(lambda x: fmt(x, 3))

    eq_display = equations.head(40)[["direction", "CONSTRAINTID", "VERSIONNO", "ic_factor", "binding_intervals",
                                     "near_binding_intervals", "near_setting_intervals", "leading_intervals",
                                     "LIMITTYPE", "constraint_sets"]].copy()
    eq_display.columns = ["Direction", "Constraint", "Version", "VNI coefficient", "Binding", "Near binding",
                          "Near setting", "Leading", "Type", "Constraint sets"]
    eq_display["VNI coefficient"] = eq_display["VNI coefficient"].map(lambda x: fmt(x, 5))

    seasonal_display = seasonal[["season", "intervals", "flow_median_mw", "flow_p05_mw", "flow_p95_mw",
                                 "export_limit_median_mw", "import_limit_median_mw", "northward_flow_share",
                                 "southward_flow_share", "flow_reversals", "forced_export_intervals",
                                 "forced_import_intervals", "upper_setter_match", "lower_setter_match"]].copy()
    seasonal_display.columns = ["Season", "Intervals", "Median flow MW", "Flow P05", "Flow P95", "Median export limit",
                                "Median import limit", "Northward share", "Southward share", "Reversals",
                                "Forced export", "Forced import", "Upper setter match", "Lower setter match"]
    for col in ["Median flow MW", "Flow P05", "Flow P95", "Median export limit", "Median import limit"]:
        seasonal_display[col] = seasonal_display[col].map(lambda x: fmt(x, 1))
    for col in ["Northward share", "Southward share", "Upper setter match", "Lower setter match"]:
        seasonal_display[col] = seasonal_display[col].map(lambda x: f"{x:.1%}")

    contraction_direction = (contraction_events.groupby("direction", as_index=False)
                             .agg(episodes=("time", "size"), median_drop_mw=("drop_mw", "median"),
                                  p90_drop_mw=("drop_mw", lambda x: x.quantile(.9)),
                                  max_drop_mw=("drop_mw", "max")))
    severity = (contraction_events.groupby("direction").drop_mw.apply(lambda x: pd.Series({
        "episodes_ge_250_mw": x.ge(250).sum(), "episodes_ge_500_mw": x.ge(500).sum(),
        "episodes_ge_1000_mw": x.ge(1000).sum()})).unstack().reset_index())
    threshold_stats = (contraction_thresholds.groupby("direction", as_index=False)
                       .agg(monthly_threshold_min_mw=("threshold_mw", "min"),
                            monthly_threshold_median_mw=("threshold_mw", "median"),
                            monthly_threshold_max_mw=("threshold_mw", "max")))
    contraction_direction = (contraction_direction.merge(severity, on="direction", how="left")
                             .merge(threshold_stats, on="direction", how="left"))
    contraction_direction_display = contraction_direction.copy()
    contraction_direction_display.columns = ["Direction", "Episodes", "Median drop MW", "P90 drop MW",
                                               "Maximum drop MW", "Episodes ≥250 MW", "Episodes ≥500 MW",
                                               "Episodes ≥1,000 MW", "Minimum monthly threshold MW",
                                               "Median monthly threshold MW", "Maximum monthly threshold MW"]
    for col in ["Median drop MW", "P90 drop MW", "Maximum drop MW", "Minimum monthly threshold MW",
                "Median monthly threshold MW", "Maximum monthly threshold MW"]:
        contraction_direction_display[col] = contraction_direction_display[col].map(lambda x: fmt(x, 1))

    contraction_seasonal = (contraction_events.groupby(["season", "direction"], as_index=False)
                           .agg(episodes=("time", "size"), median_drop_mw=("drop_mw", "median"),
                                p90_drop_mw=("drop_mw", lambda x: x.quantile(.9)),
                                max_drop_mw=("drop_mw", "max")))
    contraction_seasonal_display = contraction_seasonal.copy()
    contraction_seasonal_display.columns = ["Season", "Direction", "Episodes", "Median drop MW",
                                             "P90 drop MW", "Maximum drop MW"]
    for col in contraction_seasonal_display.columns[3:]:
        contraction_seasonal_display[col] = contraction_seasonal_display[col].map(lambda x: fmt(x, 1))

    contraction_top = units.sort_values("contraction_rank").head(15).copy()
    contraction_top_display = contraction_top[["contraction_rank", "DUID", "contraction_contribution_rows",
                                               "contraction_onsets", "contraction_tightening_mw_observations",
                                               "contraction_mean_positive_tightening_mw",
                                               "contraction_positive_share"]].copy()
    contraction_top_display.columns = ["Rank", "DUID", "Contraction rows", "Episode-onset exposures",
                                       "Positive tightening MW-observations", "Mean positive tightening MW",
                                       "Positive tightening share"]
    contraction_top_display["Positive tightening MW-observations"] = contraction_top_display[
        "Positive tightening MW-observations"].map(lambda x: fmt(x, 0))
    contraction_top_display["Mean positive tightening MW"] = contraction_top_display[
        "Mean positive tightening MW"].map(lambda x: fmt(x, 2))
    contraction_top_display["Positive tightening share"] = contraction_top_display[
        "Positive tightening share"].map(lambda x: f"{x:.1%}")

    contraction_constraint_display = (contraction_constraints.groupby("direction", group_keys=False).head(6)
                                      [["direction", "constraint", "episodes", "median_drop_mw", "max_drop_mw"]]
                                      .copy())
    contraction_constraint_display.columns = ["Direction", "Leading constraint", "Episodes",
                                               "Median drop MW", "Maximum drop MW"]
    for col in ["Median drop MW", "Maximum drop MW"]:
        contraction_constraint_display[col] = contraction_constraint_display[col].map(lambda x: fmt(x, 1))

    upper_contraction_names = ", ".join(contraction_rankings[contraction_rankings.scope.eq("upper")]
                                        .sort_values("contraction_rank").DUID.head(5))
    lower_contraction_names = ", ".join(contraction_rankings[contraction_rankings.scope.eq("lower")]
                                        .sort_values("contraction_rank").DUID.head(5))

    top_names = ", ".join(top.DUID.head(8))
    spring = seasonal.set_index("season").loc["Spring"]
    largest_contraction = contraction_events.loc[contraction_events.drop_mw.idxmax()]
    report = f"""# VNI two-year constraint, topology and generator-influence study

## Result and scope

This study reconstructs the constraint-derived `VIC1-NSW1` (VNI) directional envelope at five-minute resolution from **1 September 2024 through 31 August 2026**. It evaluates every directly linked or observed setter equation available inside that same 24-month acquisition window, then separates four operational populations: AEMO binding equations, equations within 50 MW of binding, reported directional setters, and reconstructed envelope leaders.

The broadest generator-pressure candidates by persistence-weighted absolute impact are **{top_names}**. Their signs and magnitudes vary by equation version and direction, so the forecast representation should use signed `-b/a × ΔMW` pressure under the active constraint regime rather than raw unit generation alone. These are mechanical attributions from solved equations and simultaneous dispatch; they are not independent causal estimates.

## Coverage and integrity

| Item | Result |
|---|---:|
| Analysis window | 1 Sep 2024–31 Aug 2026 |
| Calendar months / seasons | 24 / two complete cycles of each season |
| Five-minute VNI observations | {int(seasonal.intervals.sum()):,} |
| Generator DUIDs with valid sensitivities | {len(units):,} |
| Exact equation versions researched | {len(equations):,} |
| Distinct constraint IDs researched | {equations.CONSTRAINTID.nunique():,} |
| Reconstructed upper/lower coverage | {coverage['upper_coverage']:.2%} / {coverage['lower_coverage']:.2%} |
| Mean upper/lower reconstruction MAE | {coverage['upper_reconstruction_mae_mw']:.2f} / {coverage['lower_reconstruction_mae_mw']:.2f} MW |
| Exact dispatch-to-equation version match | {coverage['exact_version_match_fraction']:.2%} |
| Available standing archives | {len(standing_audit['manifest']):,} |
| Peak-controlled study footprint at report build | {path_bytes(root) / 1e9:.2f} GB of 10.00 GB |

Both standing and interval acquisition are hard-bounded to the same two years. The run downloads only six small monthly standing tables and two monthly interval tables. Each interval month is dependency-filtered, reduced to compact Parquet outputs, checked, and its large archives are removed before the following month. The [source manifest](data/vni_2y_source_manifest.json) records every available standing archive, byte size and SHA-256 digest; unavailable monthly table archives are listed explicitly.

The dispatch-supplied exact equation version matched {coverage['exact_version_match_fraction']:.2%} of reconstructed rows; remaining rows use the documented time-effective fallback. The upper/lower reconstruction MAE of {coverage['upper_reconstruction_mae_mw']:.2f}/{coverage['lower_reconstruction_mae_mw']:.2f} MW is therefore a material quality diagnostic, and forecast testing should retain the match/fallback flag rather than treating every reconstructed bound as equally certain.

## Seasonal network state

{md_table(seasonal_display)}

Spring’s median flow was {spring.flow_median_mw:,.1f} MW, with a {spring.southward_flow_share:.1%} share of southward intervals. Seasonal medians describe the realised mix of demand, renewable output, outages, dispatch and constraint regimes. They do not isolate a single physical driver.

The full machine-readable seasonal summaries are [network state](data/vni_2y_seasonal_summary.csv), [constraint populations](data/vni_2y_constraint_population_by_season.csv), and [generator influence by season and direction](data/vni_2y_generator_seasonal_rankings.csv).

The HTML report adds a seasonal generator-pressure heatmap for the twelve highest two-year contributors. It makes it easy to distinguish persistent units such as {top.iloc[0].DUID} from units whose exposure is concentrated in one season.

## Diurnal behaviour

The [48-bin diurnal table](data/vni_2y_diurnal_summary.csv) contains mean, median, P05 and P95 flow; median and P05 directional limits; directional-flow shares; reversal counts; and forced-direction interval counts for every half-hour of the day across the two-year sample. This preserves the morning ramp, solar-hours transfer pattern, evening ramp and overnight regime without adding 48 raw dummy variables to a forecast.

For modelling, compress the diurnal shape into clock sine/cosine, season × clock interactions, and a small set of learned training-only profiles or principal components. Retain explicit ramp-window flags only when cross-validation shows they improve event forecasts.

The HTML report also shows reversal and forced-export/import rates by half-hour. These event-rate curves are useful for identifying ramp windows and directional-regime risk before adding any high-cardinality clock features.

## Sharp limit contractions

A sharp contraction is a fall in the reported directional limit over 30 minutes that is at or above the **90th percentile of positive 30-minute falls within the same calendar month and direction**. The threshold is recalculated by month and direction so the study captures locally exceptional moves across different seasonal regimes. `Contraction onset` marks the first five-minute interval of each contiguous contraction episode, preventing a sustained move from being presented as a new event at every interval.

{md_table(contraction_direction_display)}

Across the full study there were **{len(contraction_events):,} directional contraction episodes**. The largest observed episode began at **{largest_contraction.time}**, when the {largest_contraction.direction} directional limit fell **{largest_contraction.drop_mw:,.1f} MW** over 30 minutes and the reconstructed leading constraint was `{largest_contraction.constraint}`. Very large moves, especially those ending in negative reported limits, should be reviewed as forced-flow or ramp-constraint regimes rather than treated as ordinary capacity changes.

Event timing and drop size come directly from the reported directional-limit series. Generator attribution then uses the reconstructed leading equation and mapped unit sensitivities, so the {coverage['exact_version_match_fraction']:.2%} exact-version match rate and fallback flag remain material when interpreting unit ranks.

### Seasonal contraction pattern

{md_table(contraction_seasonal_display)}

### Generators exposed during contractions

The contraction leaderboard ranks units by the sum of **positive equation-derived tightening pressure only during contraction intervals**. This corrects the earlier report build, which displayed a contraction rank based on tightening across all intervals. Upper-direction leaders were **{upper_contraction_names}**; lower-direction leaders were **{lower_contraction_names}**.

{md_table(contraction_top_display)}

`Positive tightening share` is the fraction of a unit's contraction-state equation rows in which its 30-minute movement mechanically tightened the active directional bound. A unit can rank highly through a smaller number of very large conditional impacts. For example, TUMUT3 is a major lower-direction contraction exposure, but that does not mean every Tumut 3 movement contracts QNI or that its movement independently caused the observed limit change.

The most frequently leading reconstructed constraints at contraction onsets were:

{md_table(contraction_constraint_display)}

The full event ledger, adaptive monthly thresholds, constraint episode summary and direction-specific generator rankings are available in [contraction events](data/vni_2y_contraction_events.csv), [monthly thresholds](data/vni_2y_contraction_thresholds_monthly.csv), [contraction constraints](data/vni_2y_contraction_constraints.csv), and [generator contraction rankings](data/vni_2y_generator_contraction_rankings.csv).

## Generator influence

`Abs impact MW-observations` sums `abs(-b/a × ΔMW)` while a unit appears in an applicable VNI equation. Tightening preserves the direction-specific sign; contraction rank uses positive tightening during sharp-contraction intervals, while reversal and forced ranks count event exposure. `Flow-move rho` is a weighted monthly Spearman association, not causation.

{md_table(top_display)}

The complete ranking, factor extrema, equation-version coverage and event measures are in [vni_2y_generator_rankings.csv](data/vni_2y_generator_rankings.csv). The compressed [unit-by-equation factor file](data/vni_2y_unit_equation_factors.csv.gz) preserves every distinct exact-version `b` coefficient, VNI `a` coefficient and derived `-b/a` sensitivity. Seasonal ranks should be used to decide which unit-specific pressure terms are stable enough to keep. Units that rank highly in only one season should be pooled into constraint-family or regional pressure features until an untouched period confirms persistence.

## Binding, near-binding, setter and leading equations

`Binding` means absolute published marginal value above numerical zero. `Near binding` means solved constraint slack divided by the absolute VNI coefficient is between 0 and 50 MW. `Near setting` means the equation’s implied bound is within 50 MW of the reconstructed directional envelope. `Leading` means it is the reconstructed tightest valid upper or lower equation. Reported setters come from `EXPORTGENCONID` and `IMPORTGENCONID`; reconstructed leaders are kept separately so disagreement remains visible.

The 40 most operationally relevant exact versions are shown below. The [complete equation file](data/vni_2y_constraint_equations.csv) includes every researched exact version, VNI coefficient, description, constraint-set membership, overlapping invoked sets, applicable counts, binding/near-binding/near-setting counts, leading counts, marginal-value summary and VNI-normalised slack.

{md_table(eq_display)}

## Compact feature design

Use a compact network-state block of roughly 20–30 continuous variables plus small categorical encodings:

1. Conditional upper/lower envelope, flow room, runner-up switch gaps and envelope-move persistence.
2. Aggregate signed generator tightening and relief for each direction, plus 30-minute pressure changes.
3. Ramp-and-availability-limited relief, candidate counts and pressure-completeness fractions.
4. Reported setter and reconstructed leader families as separate low-cardinality encodings, with a disagreement flag.
5. Four to eight frozen unit-pressure features chosen only on training history; pool the remaining units by constraint family, region or hydro/thermal/renewable class.
6. Seasonal and diurnal context through two clock harmonics, two annual harmonics, and selected season × clock interactions.
7. Regime flags for binding, near-binding, near-setting, forced-direction limits, crossed envelopes and recent leader switches.

This representation keeps topology-dependent signs while avoiding one variable per generator or constraint. The exact leader ID is valuable for diagnosis, but operational forecasts should also carry top-K candidate summaries because the active equation can switch within the horizon.

The reusable [feature dictionary](data/vni_2y_feature_dictionary.csv) records each feature group, unit, definition and recommended variable count. The configuration and orchestrator accept the interconnector ID, dates, thresholds and storage limits as parameters, so the same method can be applied to another interconnector after its study config is reviewed.

## Calculation method

For each exact effective generic-constraint version:

```text
a * VNI + sum(b_i * P_i) + other solved terms <= RHS
conditional VNI bound = observed VNI flow + (RHS - solved LHS) / a
unit sensitivity = -b_i / a
30-minute unit pressure = sensitivity * (P_i[t] - P_i[t-30m])
```

Positive `a` yields an upper signed-flow bound; negative `a` yields a lower bound. The minimum upper and maximum lower valid candidates form the reconstructed envelope. Constraint versions are matched using dispatch-supplied effective date/version where available, with time-effective fallback recorded by the feature audit. The first 30 minutes of each independently processed month lack a within-file 30-minute unit change and are excluded from movement attribution; this affects 12 hours across two years, about 0.07% of the study timeline, while equation, binding, limit, flow, seasonal and diurnal coverage remain intact.

## Interpretation limits and testing use

- Generator rankings describe mechanical exposure under observed dispatch and constraint regimes. Simultaneous system responses prevent a causal claim.
- Reported directional limits depend on solved dispatch and should not be interpreted as independent transmission ratings or jointly feasible counterfactual capacities.
- Near-binding and near-setting thresholds are both 50 MW in VNI-normalised space and should be sensitivity-tested at 25 and 100 MW before feature selection is frozen.
- Feature selection must use training seasons only. Evaluate the frozen compact block on a later untouched chronological period against persistence, reported-setter history and a non-topological fundamentals baseline.
- Forecast-horizon pressure requires lagged dispatch plus generator scenarios or unit forecasts. Realised future dispatch must never enter an operational backtest.

## Rebuild

```powershell
python -m nemic.constraint_longitudinal run --config configs/constraint_vni_2y.json
python scripts/build_vni_two_year_report.py --config configs/constraint_vni_2y.json
python scripts/build_docs_html.py
python -m unittest discover -s tests -v
```
"""
    if name != "VNI":
        report = (report.replace("VIC1-NSW1", config["interconnector"])
                  .replace("VIC→NSW", metadata["flow"])
                  .replace("VNI", name)
                  .replace("vni_2y_", f"{prefix}_")
                  .replace("configs/constraint_vni_2y.json", "configs/constraint_qni_2y.json")
                  .replace("build_vni_two_year_report.py", "build_qni_two_year_report.py"))
    markdown_path = ROOT / "docs" / f"{name}_TWO_YEAR_CONSTRAINT_STUDY.md"
    markdown_path.write_text(report, encoding="utf-8")

    fig_units = px.bar(top.head(15).sort_values("total_abs_impact_mw_observations"),
                       x="total_abs_impact_mw_observations", y="DUID", orientation="h",
                       color="active_months", labels={"total_abs_impact_mw_observations": "Absolute impact (MW-observations)",
                                                     "active_months": "Active months", "DUID": "Generator"})
    style_plotly(fig_units, "Persistent generator pressure under VNI equations", height=580)
    fig_season = go.Figure()
    for column, label in [("flow_median_mw", "Median flow"), ("export_limit_median_mw", "Median export limit"),
                          ("import_limit_median_mw", "Median import limit")]:
        fig_season.add_bar(name=label, x=seasonal.season, y=seasonal[column])
    fig_season.update_layout(barmode="group")
    style_plotly(fig_season, "Two complete seasonal cycles of VNI state", height=480)
    season_order = [s for s in ["Summer", "Autumn", "Winter", "Spring"] if s in unit_season["season"].unique()]
    top_heat = (unit_season.groupby(["DUID", "season"], as_index=False)["total_abs_impact"]
                .sum().pivot(index="DUID", columns="season", values="total_abs_impact").fillna(0))
    heat_names = top.DUID.head(12).tolist()
    top_heat = top_heat.reindex(index=heat_names, columns=season_order).fillna(0)
    fig_heat = go.Figure(go.Heatmap(z=top_heat.to_numpy(), x=season_order, y=top_heat.index.tolist(),
                                    colorscale="Blues", colorbar={"title": "MW-impact"},
                                    hovertemplate="%{y} · %{x}<br>Absolute impact: %{z:,.0f}<extra></extra>"))
    style_plotly(fig_heat, "Top generator pressure by season", height=520)
    fig_day = go.Figure()
    fig_day.add_scatter(x=diurnal.time_of_day, y=diurnal.flow_median_mw, name="Median flow", mode="lines")
    fig_day.add_scatter(x=diurnal.time_of_day, y=diurnal.export_limit_median_mw, name="Median export limit", mode="lines")
    fig_day.add_scatter(x=diurnal.time_of_day, y=-diurnal.import_limit_median_mw, name="Signed import limit", mode="lines")
    fig_day.update_xaxes(dtick=4)
    style_plotly(fig_day, "Diurnal VNI flow and directional limits", height=480)
    fig_events = go.Figure()
    for column, label in [("flow_reversals", "Reversals"),
                          ("forced_export_intervals", "Forced export"),
                          ("forced_import_intervals", "Forced import")]:
        fig_events.add_scatter(x=diurnal.time_of_day,
                               y=diurnal[column] / diurnal.intervals.replace(0, np.nan),
                               name=label, mode="lines")
    fig_events.update_xaxes(dtick=4)
    fig_events.update_yaxes(tickformat=".1%")
    style_plotly(fig_events, "Diurnal event regime rates", height=420)
    contraction_diurnal = (contraction_events.groupby(["direction", "half_hour"], as_index=False)
                           .agg(episodes=("time", "size"))
                           .merge(diurnal[["half_hour", "intervals", "time_of_day"]], on="half_hour", how="left"))
    contraction_diurnal["episode_rate"] = contraction_diurnal.episodes / contraction_diurnal.intervals
    fig_contraction_day = go.Figure()
    for direction, label in [("upper", "Upper / export"), ("lower", "Lower / import")]:
        x = contraction_diurnal[contraction_diurnal.direction.eq(direction)]
        fig_contraction_day.add_scatter(x=x.time_of_day, y=x.episode_rate, name=label, mode="lines")
    fig_contraction_day.update_xaxes(dtick=4)
    fig_contraction_day.update_yaxes(tickformat=".1%")
    style_plotly(fig_contraction_day, "Sharp-contraction onset rate by time of day", height=430)

    fig_contraction_units = px.bar(
        contraction_top.sort_values("contraction_tightening_mw_observations"),
        x="contraction_tightening_mw_observations", y="DUID", orientation="h",
        color="contraction_positive_share",
        labels={"contraction_tightening_mw_observations": "Positive tightening during contractions (MW-observations)",
                "contraction_positive_share": "Positive share", "DUID": "Generator"})
    fig_contraction_units.update_coloraxes(colorbar_tickformat=".0%")
    style_plotly(fig_contraction_units, "Generator tightening during sharp contractions", height=590)

    rendered = markdown.markdown(report, extensions=["tables", "fenced_code"])
    rendered = rendered.replace('href="data/', 'href="../data/')
    rendered = rendered.replace("<table>", '<div class="table-wrap" tabindex="0"><table>').replace("</table>", "</table></div>")
    body = (hero("NEM · TWO-YEAR CONSTRAINT RECONSTRUCTION", "What moves VNI?", "Two full seasonal cycles",
                 "Binding, near-binding, reported-setter and reconstructed-envelope analysis with generator pressure, seasonal structure and diurnal regimes.",
                 ["Data: Sep 2024–Aug 2026", f"Built: {built_label}", "5-minute resolution", "Offline report"])
            + '<nav><a href="#findings">Findings</a><a href="#seasonal">Seasonal</a><a href="#diurnal">Diurnal</a><a href="#contractions">Contractions</a><a href="#generators">Generators</a><a href="#methods">Full report</a></nav>'
            + '<div class="metrics">' + ''.join([
                metric("Observations", f"{int(seasonal.intervals.sum()):,}", "Two complete years at five-minute resolution"),
                metric("Generators", f"{len(units):,}", "DUIDs with valid equation sensitivities"),
                metric("Equation versions", f"{len(equations):,}", "Binding, near and leading populations retained"),
                metric("Storage", f"{path_bytes(root)/1e9:.2f} GB", "Live study output against a 10 GB guard"),
            ]) + '</div>'
            + '<section id="findings"><div class="section-kicker">KEY FINDINGS</div><div class="findings">' + ''.join([
                finding(1, "Topology changes the sign", "A generator's VNI effect is represented by its exact equation sensitivity −b/a and movement, preserving constraint direction and version."),
                finding(2, "Season and clock both matter", "Two complete cycles expose recurring seasonal transfer regimes and a 48-bin intraday shape without requiring one model variable per interval."),
                finding(3, "Keep setter populations separate", "Published binding equations, near-binding candidates, reported setters and reconstructed leaders answer different questions and are all retained."),
                finding(4, "Sharp contractions are episodic", f"{len(contraction_events):,} upper/lower episode onsets identify the generators and leading equations present during abrupt 30-minute limit reductions."),
            ]) + '</div></section>'
            + '<section id="seasonal"><div class="section-kicker">SEASONAL STATE</div><figure><figcaption>Flow and median directional capability</figcaption><div class="chart-scroll">'
            + fig_season.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">Signed positive flow is VIC→NSW; import capability is shown as a positive directional magnitude.</p></figure>'
            + '<figure><figcaption>Seasonal generator-pressure concentration</figcaption><div class="chart-scroll">'
            + fig_heat.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">Top-12 units are selected by two-year absolute impact; colour shows seasonal mechanical exposure.</p></figure></section>'
            + '<section id="diurnal"><div class="section-kicker">DIURNAL STATE</div><figure><figcaption>Half-hour profiles across two years</figcaption><div class="chart-scroll">'
            + fig_day.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">Import limit is plotted on the signed-flow axis as a negative value.</p></figure>'
            + '<figure><figcaption>Half-hour event regime rates</figcaption><div class="chart-scroll">'
            + fig_events.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">Rates are event counts divided by the available two-year observations in each half-hour bin.</p></figure></section>'
            + '<section id="contractions"><div class="section-kicker">SHARP LIMIT CONTRACTIONS</div><figure><figcaption>When contraction episodes begin</figcaption><div class="chart-scroll">'
            + fig_contraction_day.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">An onset is the first interval in a contiguous episode above the month-and-direction 90th-percentile 30-minute drop threshold.</p></figure>'
            + '<figure><figcaption>Generator tightening during contraction intervals</figcaption><div class="chart-scroll">'
            + fig_contraction_units.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">Bars sum positive equation-derived tightening only while the reported directional limit is in a sharp-contraction state; colour shows how often the unit pressure is tightening rather than relieving.</p></figure></section>'
            + '<section id="generators"><div class="section-kicker">GENERATOR PRESSURE</div><figure><figcaption>Persistence-weighted mechanical exposure</figcaption><div class="chart-scroll">'
            + fig_units.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True, "displaylogo": False})
            + '</div><p class="figure-note">Colour records the number of study months in which the unit contributes.</p></figure></section>'
            + '<section id="methods" class="method">' + rendered + '</section>'
            + f'<footer>Generated from locally retained compact outputs. Theme {VERSION}. Rebuild with <code>python scripts/build_vni_two_year_report.py --config configs/constraint_vni_2y.json</code>.</footer>')
    if name != "VNI":
        body = (body.replace("VIC1-NSW1", config["interconnector"])
                .replace("VIC→NSW", metadata["flow"])
                .replace("VNI", name)
                .replace("vni_2y_", f"{prefix}_")
                .replace("configs/constraint_vni_2y.json", "configs/constraint_qni_2y.json")
                .replace("build_vni_two_year_report.py", "build_qni_two_year_report.py"))
    html_path = ROOT / "docs" / "html" / f"{prefix}_constraint_study.html"
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_page(f"{name} two-year constraint study", body, plotly=True, accent="blue"), encoding="utf-8")
    inputs = [artifact("generator_rankings.csv"), artifact("generator_seasonal_rankings.csv"),
              artifact("unit_equation_factors.csv.gz"), artifact("constraint_equations.csv"),
              artifact("seasonal_summary.csv"), artifact("diurnal_summary.csv"),
              artifact("constraint_population_by_season.csv"), artifact("feature_dictionary.csv"),
              artifact("source_manifest.json"), artifact("contraction_events.csv"),
              artifact("contraction_thresholds_monthly.csv"), artifact("contraction_constraints.csv"),
              artifact("generator_contraction_rankings.csv")]
    manifest = {"config": str(Path(config_path).resolve().relative_to(ROOT)),
                "config_sha256": hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
                "inputs": {name: hashlib.sha256((docs_data / name).read_bytes()).hexdigest() for name in inputs},
                "visualizations": [
                    {"id": "seasonal_state", "source": artifact("seasonal_summary.csv"), "description": "Seasonal median flow and directional limits"},
                    {"id": "seasonal_generator_heatmap", "source": artifact("generator_seasonal_rankings.csv"), "description": "Top-12 generator absolute pressure by season"},
                    {"id": "diurnal_state", "source": artifact("diurnal_summary.csv"), "description": "48-bin median flow and directional limits"},
                    {"id": "diurnal_event_rates", "source": artifact("diurnal_summary.csv"), "description": "Reversal and forced-direction rates by half-hour"},
                    {"id": "contraction_diurnal", "source": artifact("contraction_events.csv"), "description": "Sharp-contraction onset rates by half-hour and direction"},
                    {"id": "contraction_generators", "source": artifact("generator_contraction_rankings.csv"), "description": "Generator tightening exposure during sharp contractions"},
                    {"id": "generator_pressure", "source": artifact("generator_rankings.csv"), "description": "Persistence-weighted generator exposure"},
                ],
                "theme_version": VERSION, "offline": True,
                "command": ("python scripts/build_vni_two_year_report.py --config configs/constraint_vni_2y.json"
                            if name == "VNI" else "python scripts/build_qni_two_year_report.py")}
    (ROOT / "docs" / "html" / f"{prefix}_constraint_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(markdown_path)
    print(html_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(ROOT / "configs" / "constraint_vni_2y.json"))
    args = parser.parse_args()
    build(args.config)
