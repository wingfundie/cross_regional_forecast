"""Build the six-interconnector diurnal, regime, constraint and DUID-pressure report.

The script consumes retained processed market data and completed longitudinal
constraint studies. It writes compact analytical tables before rendering the
standalone HTML, so every published chart can be audited independently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "report_theme"))

from nemic.common import IC  # noqa: E402
from report_theme import figure_html, finding, hero, metric, render_page, style_plotly  # noqa: E402

REPORT_ID = "all_interconnector_regime_research_20260921"
OUT = ROOT / "reports" / REPORT_ID
DATA_OUT = OUT / "downloads"
SOURCES_OUT = OUT / "sources"
COLORS = {"Summer": "#ce9a48", "Autumn": "#8370b4", "Winter": "#5696b9", "Spring": "#268a87"}
SEASON_ORDER = ["Summer", "Autumn", "Winter", "Spring"]
DAILY_PERIOD_ORDER = ["Overnight", "Morning peak", "Solar period", "Evening peak"]
IC_ORDER = ["NSW1-QLD1", "N-Q-MNSP1", "VIC1-NSW1", "V-SA", "V-S-MNSP1", "T-V-MNSP1"]
IC_NAMES = {key: value["name"] for key, value in IC.items()}
REGION_PREFIX = {"NSW1": "NSW_", "QLD1": "QLD_", "VIC1": "VIC_", "SA1": "SA_", "TAS1": "TAS_"}
CONSTRAINT_DIRS = {
    "NSW1-QLD1": "constraint_qni_2y", "N-Q-MNSP1": "constraint_directlink_2y",
    "VIC1-NSW1": "constraint_vni_2y", "V-SA": "constraint_vsa_2y",
    "V-S-MNSP1": "constraint_murraylink_2y", "T-V-MNSP1": "constraint_basslink_2y",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def australian_season(time: pd.Series) -> pd.Series:
    month = time.dt.month
    return pd.Series(np.select(
        [month.isin([12, 1, 2]), month.isin([3, 4, 5]), month.isin([6, 7, 8])],
        ["Summer", "Autumn", "Winter"], default="Spring"), index=time.index)


def season_block(time: pd.Series) -> pd.Series:
    season = australian_season(time)
    year = time.dt.year
    summer_end = year + month_is_dec(time)
    value = np.where(season.eq("Summer"),
                     "Summer " + (summer_end - 1).astype(str) + "–" + summer_end.astype(str).str[-2:],
                     season + " " + year.astype(str))
    return pd.Series(value, index=time.index)


def month_is_dec(time: pd.Series) -> pd.Series:
    return time.dt.month.eq(12).astype(int)


def calendar_quarter(time: pd.Series) -> pd.Series:
    period = time.dt.to_period("Q")
    return pd.Series([f"{p.year} Q{p.quarter}" for p in period], index=time.index)


def complete_calendar_quarter(time: pd.Series, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    period = time.dt.to_period("Q")
    return (period.dt.start_time.ge(start) & period.dt.end_time.dt.floor("5min").le(end))


def weather_region(weather: pd.DataFrame, region: str, variable: str, how="mean") -> pd.Series:
    cols = [c for c in weather.columns if c.startswith(REGION_PREFIX[region]) and c.endswith("__" + variable)]
    if not cols:
        return pd.Series(np.nan, index=weather.index)
    return weather[cols].max(axis=1) if how == "max" else weather[cols].mean(axis=1)


def build_panel() -> pd.DataFrame:
    targets = pd.read_parquet(ROOT / "data/processed/targets.parquet")
    targets = targets[targets.ic.isin(IC_ORDER)].copy()
    targets["name"] = targets.ic.map(IC_NAMES)
    targets["season"] = australian_season(targets.time)
    targets["season_block"] = season_block(targets.time)
    targets["calendar_quarter"] = calendar_quarter(targets.time)
    targets["complete_calendar_quarter"] = complete_calendar_quarter(
        targets.time, pd.Timestamp("2023-09-01"), pd.Timestamp("2026-09-01") - pd.Timedelta(minutes=5))
    targets["half_hour"] = ((targets.time.dt.hour * 2 + (targets.time.dt.minute >= 30).astype(int)) % 48).astype(int)
    targets["half_hour_label"] = targets.time.dt.strftime("%H:%M")

    regional = pd.read_parquet(ROOT / "data/processed/regional_30min.parquet").reset_index()
    wide = regional.pivot(index="time", columns="region")
    wide.columns = [f"{region}__{variable}" for variable, region in wide.columns]
    weather = pd.read_parquet(ROOT / "data/processed/weather_30min.parquet")
    for region in REGION_PREFIX:
        weather[f"{region}__temperature_mean"] = weather_region(weather, region, "temperature_2m")
        weather[f"{region}__temperature_max"] = weather_region(weather, region, "temperature_2m", "max")
        weather[f"{region}__humidity_mean"] = weather_region(weather, region, "relative_humidity_2m")
    drivers = wide.join(weather[[c for c in weather if c.endswith(("__temperature_mean", "__temperature_max", "__humidity_mean"))]], how="left")
    targets = targets.merge(drivers.reset_index(), on="time", how="left", validate="many_to_one")

    rows = []
    for ic, base in targets.groupby("ic", sort=False):
        source, sink = IC[ic]["source"], IC[ic]["sink"]
        for direction, sign, capacity, tight in [
            ("forward", 1.0, "export", "export_tight"), ("reverse", -1.0, "import", "import_tight")]:
            frame = base.copy()
            frame["direction"] = direction
            frame["direction_label"] = IC[ic]["label"] if direction == "forward" else " → ".join(IC[ic]["label"].split(" → ")[::-1])
            frame["directional_flow"] = sign * frame.flow
            frame["capacity"] = frame[capacity]
            frame["tight_capacity"] = frame[tight]
            frame["headroom"] = frame.capacity - frame.directional_flow
            frame["utilization"] = np.where((frame.capacity > 0) & (frame.directional_flow > 0), frame.directional_flow / frame.capacity, np.nan)
            frame["forced_direction"] = frame.capacity < 0
            frame["source_temperature"] = frame[f"{source}__temperature_mean"]
            frame["sink_temperature"] = frame[f"{sink}__temperature_mean"]
            frame["temperature_mean"] = frame[[f"{source}__temperature_mean", f"{sink}__temperature_mean"]].mean(axis=1)
            frame["temperature_max"] = frame[[f"{source}__temperature_max", f"{sink}__temperature_max"]].max(axis=1)
            frame["humidity_mean"] = frame[[f"{source}__humidity_mean", f"{sink}__humidity_mean"]].mean(axis=1)
            for side, region in [("source", source), ("sink", sink)]:
                frame[f"{side}_wind"] = frame[f"{region}__wind"]
                frame[f"{side}_solar"] = frame[f"{region}__solar"]
                frame[f"{side}_vre"] = frame[f"{region}__wind"] + frame[f"{region}__solar"]
                frame[f"{side}_demand"] = frame[f"{region}__demand"]
                frame[f"{side}_residual"] = frame[f"{region}__residual_demand"]
            frame["vre_difference"] = frame.source_vre - frame.sink_vre
            frame["residual_difference"] = frame.source_residual - frame.sink_residual
            rows.append(frame)
    panel = pd.concat(rows, ignore_index=True)
    panel.sort_values(["ic", "direction", "time"], inplace=True)
    for col in ["source_wind", "source_solar", "source_vre", "sink_wind", "sink_solar", "sink_vre",
                "source_residual", "sink_residual", "vre_difference", "residual_difference"]:
        group = panel.groupby(["ic", "direction"], sort=False)[col]
        panel[f"{col}_ramp_1h"] = group.diff(2)
        panel[f"{col}_ramp_3h"] = group.diff(6)
    ref = (panel[panel.capacity > 0].groupby(["ic", "direction", "season"]).capacity.median().rename("season_reference"))
    panel = panel.join(ref, on=["ic", "direction", "season"])
    panel["restricted"] = panel.capacity < .5 * panel.season_reference
    panel["zero_capacity"] = panel.capacity.abs() <= 1e-9
    panel["capacity_change_30m"] = panel.groupby(["ic", "direction"]).capacity.diff()
    return panel


def quantiles(series):
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return pd.Series({"mean": np.nan, "median": np.nan, "p05": np.nan, "p10": np.nan, "p90": np.nan, "p95": np.nan})
    return pd.Series({"mean": clean.mean(), "median": clean.median(), "p05": clean.quantile(.05),
                      "p10": clean.quantile(.10), "p90": clean.quantile(.90), "p95": clean.quantile(.95)})


def diurnal_profiles(panel: pd.DataFrame) -> pd.DataFrame:
    parts = []
    schemes = [
        ("season_pooled", ["season"]), ("australian_season_block", ["season", "season_block"]),
        ("calendar_quarter", ["calendar_quarter"])]
    for scheme, block_cols in schemes:
        source = panel if scheme != "calendar_quarter" else panel[panel.complete_calendar_quarter]
        keys = ["ic", "name", "direction", "direction_label", *block_cols, "half_hour", "half_hour_label"]
        for key, group in source.groupby(keys, observed=True, sort=False):
            row = dict(zip(keys, key if isinstance(key, tuple) else (key,)))
            row.update({"quarter_system": scheme, "n": len(group),
                        "flow_mean": group.directional_flow.mean(), "flow_median": group.directional_flow.median(),
                        "flow_p05": group.directional_flow.quantile(.05), "flow_p95": group.directional_flow.quantile(.95),
                        "capacity_median": group.capacity.median(), "capacity_p10": group.capacity.quantile(.10),
                        "tight_capacity_median": group.tight_capacity.median(), "headroom_median": group.headroom.median(),
                        "utilization_median": group.utilization.median(), "restricted_rate": group.restricted.mean(),
                        "forced_rate": group.forced_direction.mean()})
            parts.append(row)
    return pd.DataFrame(parts)


def connector_summary(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, group in panel.groupby(["ic", "name", "direction", "direction_label"], sort=False):
        row = dict(zip(["ic", "name", "direction", "direction_label"], key))
        row.update({"intervals": len(group), "start": group.time.min(), "end": group.time.max(),
                    "flow_median": group.directional_flow.median(), "flow_p05": group.directional_flow.quantile(.05),
                    "flow_p95": group.directional_flow.quantile(.95), "capacity_median": group.capacity.median(),
                    "capacity_p10": group.capacity.quantile(.10), "tight_capacity_p10": group.tight_capacity.quantile(.10),
                    "headroom_median": group.headroom.median(), "restricted_rate": group.restricted.mean(),
                    "forced_rate": group.forced_direction.mean(), "missing_capacity": group.capacity.isna().sum()})
        rows.append(row)
    return pd.DataFrame(rows)


def seasonal_limit_summaries(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarise directional operating limits by pooled season and exact quarter block."""
    measures = {
        "intervals": ("time", "size"),
        "capacity_p10": ("capacity", lambda s: s.quantile(.10)),
        "capacity_median": ("capacity", "median"),
        "capacity_p90": ("capacity", lambda s: s.quantile(.90)),
        "headroom_median": ("headroom", "median"),
        "restricted_rate": ("restricted", "mean"),
        "forced_rate": ("forced_direction", "mean"),
    }
    common = ["ic", "name", "direction", "direction_label"]
    pooled = panel.groupby(common + ["season"], as_index=False, observed=True).agg(**measures)
    blocks = panel.groupby(common + ["season", "season_block"], as_index=False, observed=True).agg(
        flow_median=("directional_flow", "median"), **measures)
    return pooled, blocks


def regime_tables(panel: pd.DataFrame) -> pd.DataFrame:
    variables = ["temperature_mean", "temperature_max", "humidity_mean", "source_wind", "source_solar",
                 "source_vre", "sink_vre", "vre_difference", "residual_difference",
                 "source_vre_ramp_1h", "sink_vre_ramp_1h"]
    rows = []
    for (ic, direction, season), group in panel.groupby(["ic", "direction", "season"], sort=False):
        for variable in variables:
            values = group[variable]
            if values.notna().sum() < 200:
                continue
            p10, p20, p80, p90 = values.quantile([.1, .2, .8, .9])
            if not np.isfinite([p10, p20, p80, p90]).all() or p20 >= p80:
                continue
            labels = pd.cut(values, [-np.inf, p20, p80, np.inf], labels=["low", "normal", "high"], include_lowest=True)
            for regime in ["low", "normal", "high"]:
                subset = group[labels.eq(regime)]
                rows.append({"ic": ic, "name": IC_NAMES[ic], "direction": direction, "season": season,
                             "variable": variable, "regime": regime, "n": len(subset), "p10": p10, "p20": p20,
                             "p80": p80, "p90": p90, "value_median": subset[variable].median(),
                             "flow_median": subset.directional_flow.median(), "capacity_median": subset.capacity.median(),
                             "tight_capacity_median": subset.tight_capacity.median(), "headroom_median": subset.headroom.median(),
                             "restricted_rate": subset.restricted.mean(), "forced_rate": subset.forced_direction.mean()})
    return pd.DataFrame(rows)


def scatter_sample(panel: pd.DataFrame) -> pd.DataFrame:
    """Deterministic observed-point sample for legible browser scatterplots."""
    cols = ["time", "ic", "name", "direction", "season", "season_block", "half_hour_label",
            "directional_flow", "capacity", "tight_capacity", "temperature_mean", "temperature_max",
            "humidity_mean", "source_wind", "source_solar", "source_vre", "sink_vre",
            "vre_difference", "residual_difference", "restricted", "forced_direction"]
    parts = []
    for _, group in panel[cols].groupby(["ic", "direction"], sort=False):
        parts.append(group.sample(min(3000, len(group)), random_state=260921))
    return pd.concat(parts, ignore_index=True)


def load_constraints() -> tuple[pd.DataFrame, list[tuple[str, Path, Path]], pd.DataFrame]:
    population_parts, pressure_paths, coverage = [], [], []
    for ic, folder in CONSTRAINT_DIRS.items():
        root = ROOT / "data" / folder / "months"
        months = sorted(root.glob("*")) if root.exists() else []
        complete = [m for m in months if (m / "constraint_population_summary.parquet").exists()]
        coverage.append({"ic": ic, "name": IC_NAMES[ic], "expected_months": 24, "complete_months": len(complete),
                         "status": "complete" if len(complete) == 24 else "partial"})
        for month in complete:
            period = month.name
            pop = pd.read_parquet(month / "constraint_population_summary.parquet")
            pop["ic"], pop["name"], pop["month"] = ic, IC_NAMES[ic], period
            population_parts.append(pop)
            pressure_path = month / "unit_pressure_5min.parquet"
            if pressure_path.exists():
                pressure_paths.append((ic, pressure_path, month / "unit_sensitivities.parquet"))
    population = pd.concat(population_parts, ignore_index=True) if population_parts else pd.DataFrame()
    return population, pressure_paths, pd.DataFrame(coverage)


def constraint_summaries(population: pd.DataFrame, pressure_paths: list[tuple[str, Path, Path]]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if population.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    family = (population.groupby(["ic", "name", "direction", "CONSTRAINTID", "LIMITTYPE", "DESCRIPTION"], dropna=False)
              .agg(applicable_intervals=("applicable_intervals", "sum"), binding_intervals=("binding_intervals", "sum"),
                   near_binding_intervals=("near_binding_intervals", "sum"), near_setting_intervals=("near_setting_intervals", "sum"),
                   leading_intervals=("leading_intervals", "sum"), exact_versions=("version_key", "nunique"),
                   mean_abs_marginal_value=("mean_abs_marginal_value", "mean"))
              .reset_index())
    family["binding_rate"] = family.binding_intervals / family.applicable_intervals.replace(0, np.nan)
    family["binding_rank"] = family.groupby(["ic", "direction"]).binding_intervals.rank(method="min", ascending=False)
    family["leading_rank"] = family.groupby(["ic", "direction"]).leading_intervals.rank(method="min", ascending=False)
    family["top_constraint"] = family.binding_rank.le(10) | family.leading_rank.le(10)
    if not pressure_paths:
        return family, pd.DataFrame(), pd.DataFrame()
    top_ids = set(family.loc[family.top_constraint, "CONSTRAINTID"])
    pressure_scans, sensitivity_scans = [], []
    for ic, pressure_path, sens_path in pressure_paths:
        pressure_scans.append(
            pl.scan_parquet(str(pressure_path)).filter(pl.col("constraint").is_in(list(top_ids))).with_columns(
                pl.lit(ic).alias("ic"), pl.lit(IC_NAMES[ic]).alias("name"),
                pl.col("time").dt.year().alias("year"), pl.col("time").dt.month().alias("month"),
                ((pl.col("time").dt.hour() * 2 + (pl.col("time").dt.minute() >= 30).cast(pl.Int8)) % 48).alias("half_hour"),
                pl.col("tightening_mw").clip(lower_bound=0).alias("tightening_positive"),
                (-pl.col("tightening_mw").clip(upper_bound=0)).alias("relief_positive")))
        if sens_path.exists():
            sensitivity_scans.append(pl.scan_parquet(str(sens_path)).with_columns(
                pl.lit(ic).alias("ic"), pl.col("GENCONID").alias("constraint")))
    if not pressure_scans:
        return family, pd.DataFrame(), pd.DataFrame()
    scan = pl.concat(pressure_scans)
    keys = ["ic", "name", "direction", "constraint", "DUID"]
    duid = scan.group_by(keys).agg(
        pl.len().alias("contribution_rows"), pl.col("time").n_unique().alias("active_intervals"),
        pl.col("bound_impact_mw").abs().sum().alias("total_abs_impact"),
        pl.col("bound_impact_mw").abs().quantile(.95).alias("p95_abs_impact"),
        pl.col("tightening_positive").sum().alias("total_tightening"),
        pl.col("tightening_positive").quantile(.95).alias("p95_tightening"),
        pl.col("relief_positive").sum().alias("total_relief"), pl.col("contraction").sum().alias("contraction_rows"),
        pl.col("forced").sum().alias("forced_rows")).collect(engine="streaming").to_pandas()
    if sensitivity_scans:
        sens = (pl.concat(sensitivity_scans).group_by(["ic", "constraint", "DUID"]).agg(
            pl.col("sensitivity").median().alias("sensitivity_median"),
            pl.col("sensitivity").abs().max().alias("sensitivity_max_abs"))
            .collect(engine="streaming").to_pandas())
        duid = duid.merge(sens, on=["ic", "constraint", "DUID"], how="left")
    else:
        duid["sensitivity_median"] = np.nan; duid["sensitivity_max_abs"] = np.nan
    duid["mean_abs_impact"] = duid.total_abs_impact / duid.contribution_rows.replace(0, np.nan)
    duid["mean_tightening"] = duid.total_tightening / duid.contribution_rows.replace(0, np.nan)
    duid["tightening_rank"] = duid.groupby(["ic", "direction", "constraint"]).total_tightening.rank(method="min", ascending=False)
    duid["impact_rank"] = duid.groupby(["ic", "direction", "constraint"]).total_abs_impact.rank(method="min", ascending=False)
    duid["relief_rank"] = duid.groupby(["ic", "direction", "constraint"]).total_relief.rank(method="min", ascending=False)
    regime = scan.group_by(keys + ["year", "month", "half_hour"]).agg(
        pl.len().alias("rows"), pl.col("tightening_positive").sum().alias("tightening"),
        pl.col("relief_positive").sum().alias("relief"), pl.col("bound_impact_mw").abs().sum().alias("abs_impact"),
        pl.col("contraction").sum().alias("contractions")).collect(engine="streaming").to_pandas()
    block_time = pd.to_datetime(dict(year=regime.year, month=regime.month, day=1))
    regime["season"] = australian_season(pd.Series(block_time))
    regime["season_block"] = season_block(pd.Series(block_time))
    regime.drop(columns=["year", "month"], inplace=True)
    block_counts = (regime.groupby(["ic", "name", "direction", "constraint", "DUID"], as_index=False)
                    .season_block.nunique().rename(columns={"season_block": "season_blocks"}))
    duid = duid.merge(block_counts, on=["ic", "name", "direction", "constraint", "DUID"], how="left")
    duid = duid.sort_values(keys, kind="mergesort").reset_index(drop=True)
    regime = regime.sort_values(keys + ["season_block", "half_hour"], kind="mergesort").reset_index(drop=True)
    return family, duid, regime


def plot_div(fig) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displaylogo": False, "responsive": True})


def table_html(frame: pd.DataFrame, columns, formats=None, limit=30) -> str:
    formats = formats or {}
    use = frame.loc[:, columns].head(limit).copy()
    for col, fmt in formats.items():
        if col in use:
            use[col] = use[col].map(lambda x: "—" if pd.isna(x) else fmt(x))
    use = use.astype(object).where(use.notna(), "—")
    return '<div class="table-wrap" tabindex="0">' + use.to_html(index=False, classes="data-table", border=0, escape=True) + "</div>"


def clock_label(value) -> str:
    half_hour = int(value)
    return f"{half_hour // 2:02d}:{(half_hour % 2) * 30:02d}"


def regime_delta_table(regimes: pd.DataFrame) -> pd.DataFrame:
    rows = []
    variables = {
        "temperature_mean": "Temperature",
        "humidity_mean": "Humidity",
        "source_vre": "Source VRE",
    }
    selected = regimes[regimes.variable.isin(variables)]
    for (ic, name, direction, variable), group in selected.groupby(
            ["ic", "name", "direction", "variable"], sort=False):
        pivot = group.pivot_table(index="season", columns="regime", values="capacity_median")
        if not {"low", "high"}.issubset(pivot.columns):
            continue
        pivot["delta"] = pivot.high - pivot.low
        season = pivot.delta.abs().idxmax()
        rows.append({
            "ic": ic, "name": name, "direction": direction.title(),
            "driver": variables[variable], "season": season,
            "low_regime_limit": pivot.loc[season, "low"],
            "high_regime_limit": pivot.loc[season, "high"],
            "high_minus_low": pivot.loc[season, "delta"],
        })
    return pd.DataFrame(rows)


def enso_tables(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Attach the historical ONI episode definition without fitting an effect model."""
    path = SOURCES_OUT / "noaa_oni_v6_study_context.csv"
    monthly = pd.read_csv(path, parse_dates=["center_month"]).sort_values("center_month").reset_index(drop=True)
    monthly["threshold_sign"] = np.select([monthly.oni_c.ge(.5), monthly.oni_c.le(-.5)], [1, -1], default=0)
    run_id = monthly.threshold_sign.ne(monthly.threshold_sign.shift()).cumsum()
    monthly["threshold_run"] = monthly.groupby(run_id).threshold_sign.transform("size")
    monthly["enso_state"] = np.select(
        [monthly.threshold_sign.eq(1) & monthly.threshold_run.ge(5),
         monthly.threshold_sign.eq(-1) & monthly.threshold_run.ge(5)],
        ["El Niño", "La Niña"], default="Neutral")
    monthly["provisional"] = monthly.center_month.ge(pd.Timestamp("2026-06-01"))

    source = panel.copy()
    source["center_month"] = source.time.dt.to_period("M").dt.to_timestamp()
    source = source.merge(monthly[["center_month", "season_code", "oni_c", "enso_state", "provisional"]],
                          on="center_month", how="left", validate="many_to_one")
    retained = source[source.enso_state.notna()]
    summary = (retained.groupby(["ic", "name", "direction", "direction_label", "enso_state"], as_index=False)
               .agg(n=("time", "size"), months=("center_month", "nunique"), oni_median=("oni_c", "median"),
                    flow_median=("directional_flow", "median"), capacity_median=("capacity", "median"),
                    capacity_p10=("capacity", lambda s: s.quantile(.1)),
                    headroom_median=("headroom", "median"), restricted_rate=("restricted", "mean"),
                    forced_rate=("forced_direction", "mean")))
    return monthly, summary


def daily_period(time: pd.Series) -> pd.Series:
    hour = time.dt.hour
    return pd.Series(np.select(
        [hour.ge(21) | hour.lt(6), hour.lt(9), hour.lt(16)],
        ["Overnight", "Morning peak", "Solar period"], default="Evening peak"), index=time.index)


def _rank_constraint_counts(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    counts = (frame.groupby(keys + ["constraint"], observed=True, as_index=False)
              .size().rename(columns={"size": "setter_intervals"}))
    counts["period_intervals"] = counts.groupby(keys, observed=True).setter_intervals.transform("sum")
    counts["setter_share"] = counts.setter_intervals / counts.period_intervals
    counts.sort_values(keys + ["setter_intervals", "constraint"],
                       ascending=[True] * len(keys) + [False, True], inplace=True)
    counts["rank"] = counts.groupby(keys, observed=True).cumcount() + 1
    return counts[counts["rank"].le(3)].reset_index(drop=True)


def constraint_regime_setters(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Rank active reconstructed setters by day period, quarter block and weather/VRE regime."""
    lookup = panel[["time", "ic", "name", "direction", "season", "season_block",
                    "temperature_mean", "source_vre"]].copy()
    for variable, label in [("temperature_mean", "temperature_regime"), ("source_vre", "source_vre_regime")]:
        grouped = lookup.groupby(["ic", "direction", "season"], observed=True)[variable]
        p20 = grouped.transform(lambda s: s.quantile(.2))
        p80 = grouped.transform(lambda s: s.quantile(.8))
        lookup[label] = np.select(
            [lookup[variable].le(p20), lookup[variable].ge(p80)],
            ["low", "high"], default="normal")
        lookup.loc[lookup[variable].isna(), label] = np.nan

    parts = []
    for ic, folder in CONSTRAINT_DIRS.items():
        paths = sorted((ROOT / "data" / folder / "months").glob("*/constraint_features_5min.parquet"))
        for path in paths:
            features = pd.read_parquet(path, columns=["time", "upper_constraint", "lower_constraint"])
            upper = features[["time", "upper_constraint"]].rename(columns={"upper_constraint": "constraint"})
            upper["direction"] = "upper"
            lower = features[["time", "lower_constraint"]].rename(columns={"lower_constraint": "constraint"})
            lower["direction"] = "lower"
            long = pd.concat([upper, lower], ignore_index=True).dropna(subset=["constraint"])
            long["ic"] = ic
            parts.append(long)
    setters = pd.concat(parts, ignore_index=True)
    setters["name"] = setters.ic.map(IC_NAMES)
    setters["panel_direction"] = setters.direction.map({"upper": "forward", "lower": "reverse"})
    setters["join_time"] = setters.time.dt.ceil("30min")
    setters["daily_period"] = daily_period(setters.time)
    joined = setters.merge(
        lookup.rename(columns={"time": "join_time", "direction": "panel_direction"}),
        on=["join_time", "ic", "name", "panel_direction"], how="left", validate="many_to_one")
    joined = joined[joined.season.notna()].copy()

    common = ["ic", "name", "direction", "daily_period"]
    period_top = _rank_constraint_counts(joined, common)
    constraint_window = lookup[lookup.time.between(pd.Timestamp("2024-09-01"), pd.Timestamp("2026-08-31 23:59"))]
    complete_blocks = (constraint_window.groupby("season_block").time.nunique()
                       .loc[lambda s: s.ge(4000)].index)
    season_top = _rank_constraint_counts(
        joined[joined.season_block.isin(complete_blocks)], common + ["season", "season_block"])
    weather = pd.concat([
        joined[common + ["constraint", "temperature_regime"]].rename(columns={"temperature_regime": "regime"}).assign(driver="Temperature"),
        joined[common + ["constraint", "source_vre_regime"]].rename(columns={"source_vre_regime": "regime"}).assign(driver="Source VRE"),
    ], ignore_index=True).dropna(subset=["regime"])
    regime_top = _rank_constraint_counts(weather, common + ["driver", "regime"])
    return period_top, season_top, regime_top


def constraint_rank_tables(family: pd.DataFrame, duid: pd.DataFrame):
    binders = (family.sort_values(["ic", "direction", "binding_intervals", "leading_intervals"],
                                  ascending=[True, True, False, False])
               .groupby(["ic", "direction"], as_index=False).head(3).copy())
    setters = (family.sort_values(["ic", "direction", "leading_intervals", "binding_intervals"],
                                  ascending=[True, True, False, False])
               .groupby(["ic", "direction"], as_index=False).head(3).copy())
    pressure = (duid.sort_values(["ic", "direction", "total_tightening"],
                                 ascending=[True, True, False])
                .groupby(["ic", "direction"], as_index=False).head(3).copy())
    return binders, setters, pressure


def connector_story(name: str, summary: pd.DataFrame, diurnal: pd.DataFrame,
                    seasonal: pd.DataFrame, regime_deltas: pd.DataFrame, enso: pd.DataFrame,
                    family: pd.DataFrame, duid: pd.DataFrame, period_top: pd.DataFrame) -> str:
    score = summary[summary.name.eq(name)].set_index("direction")
    forward, reverse = score.loc["forward"], score.loc["reverse"]
    net_direction = forward.direction_label if forward.flow_median >= 0 else reverse.direction_label
    net_flow = abs(forward.flow_median)

    pooled = diurnal[(diurnal.name.eq(name)) & diurnal.quarter_system.eq("season_pooled")]
    clock = (pooled.groupby(["direction", "half_hour"], as_index=False)
             .agg(flow=("flow_median", "median"), capacity=("capacity_median", "median")))
    f_clock = clock[clock.direction.eq("forward")]
    r_clock = clock[clock.direction.eq("reverse")]
    f_lo, f_hi = f_clock.loc[f_clock.flow.idxmin()], f_clock.loc[f_clock.flow.idxmax()]
    f_cap_lo, f_cap_hi = f_clock.loc[f_clock.capacity.idxmin()], f_clock.loc[f_clock.capacity.idxmax()]
    r_cap_lo, r_cap_hi = r_clock.loc[r_clock.capacity.idxmin()], r_clock.loc[r_clock.capacity.idxmax()]

    complete = seasonal[(seasonal.name.eq(name)) & seasonal.intervals.ge(4000)]
    f_season = complete[complete.direction.eq("forward")]
    r_season = complete[complete.direction.eq("reverse")]
    f_slo, f_shi = f_season.loc[f_season.capacity_median.idxmin()], f_season.loc[f_season.capacity_median.idxmax()]
    r_slo, r_shi = r_season.loc[r_season.capacity_median.idxmin()], r_season.loc[r_season.capacity_median.idxmax()]

    deltas = regime_deltas[regime_deltas.name.eq(name)]
    temperature = deltas[deltas.driver.eq("Temperature")].sort_values("high_minus_low", key=lambda s: s.abs(), ascending=False).iloc[0]
    vre = deltas[deltas.driver.eq("Source VRE")].sort_values("high_minus_low", key=lambda s: s.abs(), ascending=False).iloc[0]

    enso_name = enso[enso.name.eq(name)].pivot(index="direction", columns="enso_state", values="capacity_median")
    f_enso_delta = enso_name.loc["forward", "El Niño"] - enso_name.loc["forward", "Neutral"]
    r_enso_delta = enso_name.loc["reverse", "El Niño"] - enso_name.loc["reverse", "Neutral"]

    fam = family[family.name.eq(name)]
    top_upper_binding = fam[fam.direction.eq("upper")].sort_values("binding_intervals", ascending=False).iloc[0]
    top_lower_binding = fam[fam.direction.eq("lower")].sort_values("binding_intervals", ascending=False).iloc[0]
    top_upper_setter = fam[fam.direction.eq("upper")].sort_values("leading_intervals", ascending=False).iloc[0]
    top_lower_setter = fam[fam.direction.eq("lower")].sort_values("leading_intervals", ascending=False).iloc[0]

    influence = duid[duid.name.eq(name)]
    top_upper_duid = influence[influence.direction.eq("upper")].sort_values("total_tightening", ascending=False).iloc[0]
    top_lower_duid = influence[influence.direction.eq("lower")].sort_values("total_tightening", ascending=False).iloc[0]

    dayparts = period_top[(period_top.name.eq(name)) & period_top["rank"].eq(1)].copy()
    dayparts["daily_period"] = pd.Categorical(dayparts.daily_period, DAILY_PERIOD_ORDER, ordered=True)
    def daypart_text(direction: str) -> str:
        selected = dayparts[dayparts.direction.eq(direction)].sort_values("daily_period")
        return "; ".join(
            f"{str(row.daily_period).lower()} <code>{escape(str(row.constraint))}</code> ({row.setter_share:.0%})"
            for row in selected.itertuples())
    upper_dayparts, lower_dayparts = daypart_text("upper"), daypart_text("lower")

    temp_direction = "higher" if temperature.high_minus_low > 0 else "lower"
    vre_direction = "higher" if vre.high_minus_low > 0 else "lower"
    anchor = name.lower().replace(" ", "-")
    return f'''<section class="connector-section" id="connector-{anchor}">
<div class="section-kicker">CONNECTOR ANALYSIS · {escape(str(forward.direction_label))}</div>
<h2>{escape(name)}</h2>
<p><strong>Observed transfer and operating envelope.</strong> The three-year median transfer is {net_flow:,.1f} MW toward {escape(net_direction)}. The median dispatch limit is {forward.capacity_median:,.1f} MW in the named forward direction and {reverse.capacity_median:,.1f} MW in reverse. The forward limit is classified as restricted in {forward.restricted_rate:.1%} of half-hours and negative—meaning the solved envelope forces flow the other way—in {forward.forced_rate:.1%}. The comparable reverse shares are {reverse.restricted_rate:.1%} and {reverse.forced_rate:.1%}. This asymmetry matters: a single nameplate rating would conceal the direction in which the market was actually permitted to move.</p>
<p><strong>Diurnal shape.</strong> The pooled seasonal median forward flow ranges from {f_lo.flow:,.1f} MW at {clock_label(f_lo.half_hour)} to {f_hi.flow:,.1f} MW at {clock_label(f_hi.half_hour)}, a {f_hi.flow - f_lo.flow:,.1f} MW within-day swing. The forward limit itself ranges from {f_cap_lo.capacity:,.1f} MW at {clock_label(f_cap_lo.half_hour)} to {f_cap_hi.capacity:,.1f} MW at {clock_label(f_cap_hi.half_hour)}. Reverse capability ranges from {r_cap_lo.capacity:,.1f} MW at {clock_label(r_cap_lo.half_hour)} to {r_cap_hi.capacity:,.1f} MW at {clock_label(r_cap_hi.half_hour)}. The coincidence—or lack of it—between the flow turning point and the limit trough indicates whether the daily pattern is primarily dispatch-led or envelope-led.</p>
<p><strong>Quarter-block variation.</strong> Across complete Australian three-month blocks, median forward capability is lowest in {escape(str(f_slo.season_block))} at {f_slo.capacity_median:,.1f} MW and highest in {escape(str(f_shi.season_block))} at {f_shi.capacity_median:,.1f} MW, a spread of {f_shi.capacity_median - f_slo.capacity_median:,.1f} MW. Reverse capability spans {r_slo.capacity_median:,.1f} MW in {escape(str(r_slo.season_block))} to {r_shi.capacity_median:,.1f} MW in {escape(str(r_shi.season_block))}. These are realised quarterly operating regimes, not an assumption that every summer or winter behaves alike.</p>
<p><strong>Weather and VRE regimes.</strong> The largest temperature-regime separation occurs for the {temperature.direction.lower()} direction in {temperature.season}: the median limit under the high-temperature regime is {temperature.high_regime_limit:,.1f} MW versus {temperature.low_regime_limit:,.1f} MW in the low-temperature regime, or {abs(temperature.high_minus_low):,.1f} MW {temp_direction}. The largest source-VRE separation occurs for the {vre.direction.lower()} direction in {vre.season}: {vre.high_regime_limit:,.1f} MW under high VRE versus {vre.low_regime_limit:,.1f} MW under low VRE, or {abs(vre.high_minus_low):,.1f} MW {vre_direction}. These are unadjusted conditional comparisons: temperature, humidity, demand, outages and VRE can move together.</p>
<p><strong>ENSO context.</strong> Under the NOAA ONI historical episode rule, the study window contains an El Niño segment from September 2023 through April 2024 and otherwise neutral-labelled observations; no run qualifies as La Niña. Relative to neutral-labelled months, the El Niño median limit differs by {f_enso_delta:+,.1f} MW forward and {r_enso_delta:+,.1f} MW reverse. Because ENSO state is strongly confounded with the specific months and network conditions in a three-year sample, this is a sample comparison, not an estimated ENSO effect.</p>
<p><strong>Constraints and generator pressure.</strong> The most frequently published upper binding family is <code>{escape(str(top_upper_binding.CONSTRAINTID))}</code> ({int(top_upper_binding.binding_intervals):,} binding five-minute intervals), while <code>{escape(str(top_upper_setter.CONSTRAINTID))}</code> is the most frequent reconstructed upper limit-setter ({int(top_upper_setter.leading_intervals):,} intervals). On the lower side the corresponding families are <code>{escape(str(top_lower_binding.CONSTRAINTID))}</code> ({int(top_lower_binding.binding_intervals):,} binding intervals) and <code>{escape(str(top_lower_setter.CONSTRAINTID))}</code> ({int(top_lower_setter.leading_intervals):,} leader intervals). Within active leader equations, the largest cumulative upper tightening pressure is associated with {escape(str(top_upper_duid.DUID))} under <code>{escape(str(top_upper_duid.constraint))}</code> ({top_upper_duid.total_tightening:,.0f} MW-observations); the lower-side leader is {escape(str(top_lower_duid.DUID))} under <code>{escape(str(top_lower_duid.constraint))}</code> ({top_lower_duid.total_tightening:,.0f}). These pressure rankings attribute realised movement through −b/a; they do not claim that the DUID independently caused the constraint to bind.</p>
<p><strong>Key-period setters.</strong> The leading upper equations by time block are {upper_dayparts}. The leading lower equations are {lower_dayparts}. Percentages are each constraint's share of reconstructed setter intervals within that connector, side and time block; the regime matrices later in the report show how these leaders change by quarter block, temperature and source VRE.</p>
</section>'''


def figures(panel, diurnal, seasonal, regimes, scatter, family, duid, pressure_regime):
    figs = []
    pooled = diurnal[diurnal.quarter_system.eq("season_pooled")]
    fig = make_subplots(rows=3, cols=2, subplot_titles=[IC_NAMES[x] for x in IC_ORDER], shared_xaxes=True)
    for i, ic in enumerate(IC_ORDER):
        row, col = i // 2 + 1, i % 2 + 1
        part = pooled[(pooled.ic.eq(ic)) & pooled.direction.eq("forward")]
        for season in SEASON_ORDER:
            s = part[part.season.eq(season)].sort_values("half_hour")
            fig.add_trace(go.Scatter(x=s.half_hour, y=s.flow_median, name=season, legendgroup=season,
                                     showlegend=i == 0, line=dict(color=COLORS[season])), row=row, col=col)
    style_plotly(fig, "Forward-direction median flow by Australian season", 900)
    fig.update_xaxes(title="Half-hour bin"); fig.update_yaxes(title="MW")
    figs.append((fig, "Three-year diurnal flow profiles", "Medians by Australian three-month season; positive values indicate flow in the named forward direction.", "diurnal_profiles.csv"))

    fig = make_subplots(rows=3, cols=2, subplot_titles=[IC_NAMES[x] for x in IC_ORDER], shared_xaxes=True)
    for i, ic in enumerate(IC_ORDER):
        row, col = i // 2 + 1, i % 2 + 1
        for direction, color in [("forward", "#5696b9"), ("reverse", "#ce9a48")]:
            part = pooled[(pooled.ic.eq(ic)) & pooled.direction.eq(direction)].groupby("half_hour", as_index=False).capacity_median.median()
            fig.add_trace(go.Scatter(x=part.half_hour, y=part.capacity_median, name=direction.title(), legendgroup=direction,
                                     showlegend=i == 0, line=dict(color=color)), row=row, col=col)
    style_plotly(fig, "Median directional dispatch limits", 900); fig.update_yaxes(title="MW")
    figs.append((fig, "Forward and reverse dispatch-limit shape", "Median across pooled seasonal profiles; reverse capacity is the negated lower signed bound.", "diurnal_profiles.csv"))

    block = diurnal[diurnal.quarter_system.eq("australian_season_block")]
    heat = block.groupby(["name", "season_block"], as_index=False).flow_median.median()
    pivot = heat.pivot(index="name", columns="season_block", values="flow_median").reindex([IC_NAMES[x] for x in IC_ORDER])
    fig = px.imshow(pivot, aspect="auto", color_continuous_scale="RdBu", color_continuous_midpoint=0,
                    labels=dict(color="Median forward flow MW"))
    style_plotly(fig, "Quarter-block forward-flow comparison", 560)
    figs.append((fig, "Australian seasonal quarter blocks", "Each column is one complete three-month block; values aggregate its 48-bin median profile.", "diurnal_profiles.csv"))

    for variable, caption in [("temperature_mean", "Temperature regimes"), ("source_vre", "Source-region VRE regimes")]:
        part = regimes[(regimes.variable.eq(variable)) & regimes.season.eq("Summer")]
        fig = px.bar(part, x="name", y="capacity_median", color="regime", facet_col="direction", barmode="group",
                     category_orders={"regime": ["low", "normal", "high"]},
                     labels={"capacity_median": "Median directional limit MW", "name": ""})
        style_plotly(fig, caption + " — summer descriptive comparison", 520)
        figs.append((fig, caption, "Regimes use connector-season P20/P80 cutoffs; these are unadjusted conditional comparisons.", "weather_vre_regimes.csv"))

    scatter_specs = [
        ("temperature_mean", "capacity", "Temperature versus directional limit", "Endpoint mean temperature °C", "Directional limit MW"),
        ("humidity_mean", "capacity", "Humidity versus directional limit", "Endpoint mean relative humidity %", "Directional limit MW"),
        ("source_vre", "directional_flow", "Source-region VRE versus directional flow", "Source wind + solar MW", "Directional flow MW"),
        ("source_vre", "capacity", "Source-region VRE versus directional limit", "Source wind + solar MW", "Directional limit MW"),
    ]
    for x, y, title, xlabel, ylabel in scatter_specs:
        fig = px.scatter(scatter, x=x, y=y, color="season", facet_col="name", facet_col_wrap=2,
                         symbol="direction", opacity=.16, render_mode="webgl",
                         category_orders={"season": SEASON_ORDER}, color_discrete_map=COLORS,
                         labels={x: xlabel, y: ylabel, "name": "Interconnector"})
        style_plotly(fig, title + " — observed half-hours", 980)
        fig.update_traces(marker=dict(size=3))
        figs.append((fig, title, "Deterministic observed-point sample; no trend line or fitted effect model. Use hover to inspect quarter, direction and time.", "regime_scatter_sample.csv.gz"))

    if not family.empty:
        top = family.sort_values("binding_intervals", ascending=False).groupby(["ic", "direction"], as_index=False).head(5)
        top["label"] = top.name + " · " + top.direction + " · " + top.CONSTRAINTID.astype(str)
        fig = px.bar(top.sort_values("binding_intervals"), x="binding_intervals", y="label", orientation="h", color="name",
                     labels={"binding_intervals": "Binding five-minute intervals", "label": ""})
        style_plotly(fig, "Most frequently binding constraint families", 900)
        figs.append((fig, "Top binding constraints", "Published marginal value defines binding; exact versions are aggregated by constraint ID.", "constraint_family_summary.csv.gz"))

    if not duid.empty:
        top = duid.sort_values("total_tightening", ascending=False).groupby(["ic", "direction", "constraint"], as_index=False).head(3)
        top = top.sort_values("total_tightening", ascending=False).head(80)
        matrix = top.pivot_table(index="DUID", columns="name", values="total_tightening", aggfunc="sum", fill_value=0)
        matrix = matrix.loc[matrix.sum(axis=1).sort_values(ascending=False).head(25).index]
        fig = px.imshow(np.log1p(matrix), aspect="auto", color_continuous_scale="Purples",
                        labels=dict(color="log(1 + tightening MW-observations)"))
        style_plotly(fig, "DUID tightening pressure within top constraints", 760)
        figs.append((fig, "Generator pressure heatmap", "Pressure uses the active reconstructed leader and direction-normalized −b/a × ΔMW contribution.", "constraint_duid_influence.csv"))

    for direction in ["forward", "reverse"]:
        fig = make_subplots(rows=3, cols=2, subplot_titles=[IC_NAMES[x] for x in IC_ORDER], shared_xaxes=True)
        for i, ic in enumerate(IC_ORDER):
            row, col = i // 2 + 1, i % 2 + 1
            part = pooled[(pooled.ic.eq(ic)) & pooled.direction.eq(direction)]
            for season in SEASON_ORDER:
                use = part[part.season.eq(season)].sort_values("half_hour")
                fig.add_trace(go.Scatter(
                    x=use.half_hour, y=use.capacity_median, name=season, legendgroup=season,
                    showlegend=i == 0, line=dict(color=COLORS[season])), row=row, col=col)
        style_plotly(fig, f"{direction.title()} directional limits by Australian season", 900)
        fig.update_xaxes(title="NEM time", tickvals=[0, 12, 24, 36, 47],
                         ticktext=["00:00", "06:00", "12:00", "18:00", "23:30"])
        fig.update_yaxes(title="Directional limit MW")
        figs.append((
            fig, f"{direction.title()} seasonal limit profiles",
            "Each line is the median limit at that half-hour across all observations in the named Australian season; reverse capacity is sign-normalised.",
            "diurnal_profiles.csv"))

    complete = seasonal[seasonal.intervals.ge(4000)].copy()
    block_order = (panel.groupby("season_block", as_index=False).time.min()
                   .sort_values("time").season_block.tolist())
    row_order = [f"{IC_NAMES[ic]} · {direction.title()}" for ic in IC_ORDER for direction in ["forward", "reverse"]]
    complete["row"] = complete.name + " · " + complete.direction.str.title()
    median = complete.pivot(index="row", columns="season_block", values="capacity_median").reindex(
        index=row_order, columns=[x for x in block_order if x in complete.season_block.unique()])
    p10 = complete.pivot(index="row", columns="season_block", values="capacity_p10").reindex_like(median)
    p90 = complete.pivot(index="row", columns="season_block", values="capacity_p90").reindex_like(median)
    restricted = complete.pivot(index="row", columns="season_block", values="restricted_rate").reindex_like(median)
    custom = np.dstack([p10.values, p90.values, restricted.values])
    text_values = np.vectorize(lambda x: "—" if pd.isna(x) else f"{x:,.0f}")(median.values)
    fig = go.Figure(go.Heatmap(
        z=median.values, x=median.columns, y=median.index, customdata=custom,
        colorscale="RdBu", zmid=0, text=text_values, texttemplate="%{text}",
        hovertemplate=("%{y}<br>%{x}<br>median %{z:,.1f} MW<br>"
                       "P10 %{customdata[0]:,.1f} MW<br>P90 %{customdata[1]:,.1f} MW<br>"
                       "restricted %{customdata[2]:.1%}<extra></extra>"),
        colorbar=dict(title="Median limit MW")))
    style_plotly(fig, "Directional operating limits by Australian seasonal block", 760)
    figs.append((
        fig, "Quarter-block directional limits",
        "Cells show the actual median MW limit for each complete three-month block; hover adds P10, P90 and the restricted-limit share.",
        "seasonal_profiles.csv"))
    return figs


def methodology_text(coverage: pd.DataFrame) -> str:
    coverage_table = coverage.to_markdown(index=False) if not coverage.empty else "No constraint runs were available."
    return f"""# Methodology — all-interconnector diurnal and constraint-pressure research

## Scope and frozen windows

The flow, dispatch-limit, weather, VRE and ENSO study covers `(2023-09-01 00:00, 2026-09-01 00:00]` in fixed UTC+10 NEM time. The constraint and DUID-pressure study covers `2024-09-01 00:00` through `2026-08-31 23:55`. The six links are QNI, Directlink, VNI, Heywood, Murraylink and Basslink. Nominal ratings and prices are outside scope.

Australian seasons are complete three-month blocks: Summer December–February, Autumn March–May, Winter June–August and Spring September–November. December belongs to the summer ending in the next year. Calendar-quarter sensitivity uses only complete Q1–Q4 blocks; partial boundary quarters are excluded.

## Flow and dispatch limits

Signed flow follows each connector's declared forward orientation. `forward_capacity = upper_bound`; `reverse_capacity = -lower_bound`. Headroom is capacity less directional flow. Negative capacities are retained and counted as forced-direction observations. A restricted limit is below 50% of the connector-direction Australian-season median of strictly positive capacity. A complete half-hour requires six distinct five-minute observations.

## Weather and VRE

Weather is the mean of retained representative sites in each endpoint region; endpoint maximum temperature is also retained. Regional VRE is cleared semi-scheduled wind plus solar. Residual demand is regional demand less those wind and solar fields; rooftop PV is not subtracted again. Regimes are defined within connector and Australian season: low ≤P20, normal P20–P80 and high ≥P80. Scatterplots use a deterministic sample of 3,000 observed half-hours per connector-direction for browser performance. No trend line, regression or model-derived effect is fitted.

ENSO context uses the NOAA Climate Prediction Center ONI version 6 table retrieved 21 September 2026. ONI is the three-month running mean of ERSST.v6 Niño 3.4 anomalies. Warm and cold historical episodes require at least five consecutive overlapping seasons at or beyond ±0.5°C; shorter threshold excursions remain neutral-labelled. The study window contains an El Niño segment from September 2023 through April 2024 and no qualifying La Niña segment. NOAA identifies the most recent values as estimates; August 2026 has no centered-season ONI value in the retained snapshot and is excluded from ENSO summaries.

## Constraint reconstruction

For `aF + Σ(bᵢPᵢ) + Z ≤ RHS`, the conditional bound is `observed flow + (RHS − solved LHS)/a`, and DUID sensitivity is `−bᵢ/a`. Positive `a` forms an upper candidate; negative `a` forms a lower candidate. Minimum upper and maximum lower candidates form the reconstructed envelope. Binding means absolute published marginal value above `1e-9`; near-binding means interconnector-normalized slack from 0 to 50 MW. Reported setters and reconstructed leaders remain separate.

Regime-resolved constraint tables use the active reconstructed upper or lower leader at each five-minute interval. The full day is partitioned into overnight (21:00–05:59), morning peak (06:00–08:59), solar period (09:00–15:59) and evening peak (16:00–20:59). Each five-minute setter is joined to the corresponding half-hour connector-direction weather/VRE observation. Temperature and source-VRE regimes reuse the connector-direction-season P20/P80 definitions. Quarterly constraint tables use complete Australian season blocks within the two-year constraint window. These tables describe which equation set the retained envelope; only the separate published-binding table uses non-zero marginal value.

Constraint run coverage at build time:

{coverage_table}

## DUID pressure

For the active reconstructed leader, movement contribution is `sᵢ × (Pᵢ[t] − Pᵢ[t−30m])`. Upper capacity uses that sign; lower/reverse capacity negates it. Tightening is the positive part of a capacity reduction; relief is the positive part of a capacity increase. Rankings therefore reflect observed movement under an active equation, not coefficient size alone and not independent causation. Pumps, batteries and loads retain source dispatch signs. Compact monthly files preserve leader-based pressure; simultaneous non-leading binding equations remain in the constraint-population table but do not receive duplicated connector-level pressure.

## Output lineage

`connector_summary.csv`, `diurnal_profiles.csv`, `seasonal_limit_summary.csv`, `seasonal_profiles.csv`, `weather_vre_regimes.csv`, `enso_monthly.csv`, `enso_regimes.csv`, `regime_scatter_sample.csv`, `constraint_family_summary.csv`, `constraint_diurnal_setters.csv`, `constraint_season_block_setters.csv`, `constraint_weather_vre_setters.csv`, `constraint_duid_influence.csv`, `constraint_duid_regime_matrix.csv` and `coverage_audit.csv` are generated before report rendering. The build manifest records input and output hashes. Missing observations are never converted to zero.

## Rebuild

```powershell
python scripts/build_all_ic_regime_report.py
python C:\\Users\\HomePC\\.codex\\skills\\editorial-html-report\\scripts\\validate_report.py reports\\{REPORT_ID}\\index.html
```
"""


def build():
    OUT.mkdir(parents=True, exist_ok=True); DATA_OUT.mkdir(parents=True, exist_ok=True); SOURCES_OUT.mkdir(parents=True, exist_ok=True)
    panel = build_panel()
    summary = connector_summary(panel)
    diurnal = diurnal_profiles(panel)
    seasonal_pooled, seasonal = seasonal_limit_summaries(panel)
    regimes = regime_tables(panel)
    enso_monthly, enso = enso_tables(panel)
    scatter = scatter_sample(panel)
    population, pressure_paths, constraint_coverage = load_constraints()
    family, duid, pressure_regime = constraint_summaries(population, pressure_paths)
    period_setters, season_setters, regime_setters = constraint_regime_setters(panel)

    outputs = {
        "connector_summary.csv": summary, "diurnal_profiles.csv": diurnal,
        "seasonal_limit_summary.csv": seasonal_pooled,
        "seasonal_profiles.csv": seasonal, "weather_vre_regimes.csv": regimes,
        "enso_monthly.csv": enso_monthly, "enso_regimes.csv": enso,
        "regime_scatter_sample.csv.gz": scatter,
        "constraint_family_summary.csv.gz": family, "constraint_duid_influence.csv": duid,
        "constraint_diurnal_setters.csv.gz": period_setters,
        "constraint_season_block_setters.csv.gz": season_setters,
        "constraint_weather_vre_setters.csv.gz": regime_setters,
        "constraint_duid_regime_matrix.csv.gz": pressure_regime, "coverage_audit.csv": constraint_coverage,
    }
    for name, frame in outputs.items():
        compression = {"method": "gzip", "mtime": 0} if name.endswith(".gz") else None
        target = DATA_OUT / name
        temporary = target.with_name(target.name + ".tmp")
        frame.to_csv(temporary, index=False, compression=compression)
        temporary.replace(target)
    (OUT / "METHODOLOGY.md").write_text(methodology_text(constraint_coverage), encoding="utf-8")

    complete_constraints = int(constraint_coverage.complete_months.sum()) if not constraint_coverage.empty else 0
    top_family = family.sort_values("binding_intervals", ascending=False).iloc[0] if not family.empty else None
    top_duid = duid.sort_values("total_tightening", ascending=False).iloc[0] if not duid.empty else None
    regime_deltas = regime_delta_table(regimes)
    binders, setters, pressure = constraint_rank_tables(family, duid)
    figs = figures(panel, diurnal, seasonal, regimes, scatter, family, duid, pressure_regime)

    body = hero("NEM · SIX INTERCONNECTORS · FIVE-MINUTE EVIDENCE",
                "When interconnectors move —", "and what tightens them",
                "A descriptive research report on three years of observed interconnector flows and dispatch limits, with quarterly seasonal blocks, weather and renewable regimes, two years of constraint evidence, and generator-level tightening pressure. The analysis is visual and conditional: no effect model is fitted.",
                ["Flow and limits: Sep 2023–Aug 2026", "Constraints: Sep 2024–Aug 2026", "NOAA ONI v6 ENSO context", "631,296 directional half-hours"])
    body += '<nav class="anchor-nav"><a href="#executive">Executive analysis</a><a href="#system">System comparison</a><a href="#quarters">Seasonal limits</a><a href="#connectors">Connector chapters</a><a href="#weather">Weather & VRE</a><a href="#constraints">Constraints</a><a href="#duids">DUID pressure</a><a href="#methods">Methods</a></nav>'
    body += '<section class="metrics">' + metric("Market observations", f"{len(panel)//2:,}", "connector × half-hour rows before directional expansion")
    body += metric("Seasonal blocks", "12", "three complete blocks for each Australian season")
    body += metric("Constraint months", f"{complete_constraints}/144", "completed connector-months at build time")
    body += metric("DUID pressure pairs", f"{len(duid):,}", "DUID × governing-constraint rankings") + '</section>'
    body += '<section class="callout"><strong>What this report measures.</strong> Reported dispatch limits are solved operating outcomes, not nominal physical ratings. A negative directional limit is retained because it shows the solved envelope forcing flow the opposite way. Weather and VRE regimes compare observed high, normal and low conditions within each connector-season. Constraint binding, reconstructed limit-setting and DUID pressure are kept as separate concepts throughout.</section>'
    body += '<section class="callout scope-note"><strong>ENSO coverage.</strong> ENSO labels use the NOAA Climate Prediction Center ONI version 6 historical episode rule: at least five consecutive overlapping three-month seasons at or beyond ±0.5°C. The study window includes El Niño-labelled observations from September 2023 through April 2024 and no qualifying La Niña segment. August 2026 is excluded from ENSO summaries because the retained official table ends at centered July 2026.</section>'

    body += '<section id="executive"><div class="section-kicker">EXECUTIVE ANALYSIS</div><h2>What the evidence says</h2><p>The six links do not behave as interchangeable pipes. Their realised transfer bias, available direction, daily turning points and exposure to constraint equations differ materially. The clearest result is asymmetry: QNI carries a median reverse-oriented transfer while retaining much more reverse than forward capability; VNI carries a median VIC-to-NSW transfer while its reverse envelope generally has more unused headroom; and the two South Australian links show different limit and constraint signatures despite connecting the same broad region pair.</p><p>The second result is that quarter blocks matter more than a single pooled seasonal label suggests. Several links move from positive to negative median capability between blocks of the same broad study window. Basslink is the strongest example: its forward median limit ranges by almost 500 MW across complete Australian seasonal blocks, while the reverse range is of similar size. QNI also shows large inter-quarter changes, particularly in reverse capability. The report therefore gives block-level values before presenting pooled seasonal summaries.</p><p>The third result is that weather and VRE scatter is descriptive, not a fitted effect. Large high-versus-low regime gaps exist—especially for VNI, Basslink and QNI—but those gaps can reflect correlated demand, outage and network states. A scatter cloud or regime median is useful for seeing where the operating envelope sits; it is not a causal coefficient. That distinction is why the report does not draw regression lines through the data.</p><p>Finally, the constraint evidence has three layers. Published binding counts identify equations with non-zero marginal value. Reconstructed leader counts identify the equation forming the tightest conditional upper or lower envelope at each interval. Generator pressure then attributes the movement of that active equation to DUID dispatch changes using −b/a × ΔMW. A family can bind frequently without being the reconstructed leader, and a DUID can have a large pressure total because it moves often, has a large sensitivity, or both.</p><div class="findings">'
    restricted = summary.sort_values("restricted_rate", ascending=False).iloc[0]
    forced = summary.sort_values("forced_rate", ascending=False).iloc[0]
    body += finding(1, "Restrictions are link and direction specific", f"{restricted['name']} {restricted['direction']} has the highest three-year restricted-limit share in this build ({restricted['restricted_rate']:.1%}). Parallel links are therefore kept separate.")
    body += finding(2, "Forced-direction limits are visible", f"{forced['name']} {forced['direction']} has the highest negative directional-limit share ({forced['forced_rate']:.1%}); negative limits are preserved rather than clipped.")
    body += finding(3, "Quarter blocks expose variation", "Each complete December–February, March–May, June–August and September–November block is shown separately. Partial boundary blocks are excluded from block-extreme claims.")
    if top_family is not None:
        body += finding(4, "Binding evidence is equation specific", f"{top_family['CONSTRAINTID']} on {top_family['name']} is the most frequent binding family in the completed archive ({int(top_family['binding_intervals']):,} five-minute intervals).")
    if top_duid is not None:
        body += finding(5, "Movement matters as much as sensitivity", f"{top_duid['DUID']} has the largest cumulative tightening pressure among retained top-constraint pairs; the ranking uses realised 30-minute movement, not coefficient magnitude alone.")
    body += finding(6, "Coverage is complete but attribution is conditional", "All 144 requested connector-months completed. Pressure is only assigned while an equation is the reconstructed active leader; unsupported or non-leading equations are not given duplicated generator attribution.")
    body += '</div></section>'

    body += '<section id="system"><div class="section-kicker">SYSTEM COMPARISON</div><h2>Direction, diurnal shape and operating room</h2><p>The scorecard below is the starting point for the report. Flow is expressed in each named direction, while capacity is the solved limit for that direction. A negative median directional flow therefore means that actual transfer is usually opposite the label; a negative capacity means that the envelope itself usually requires the opposite direction. Restricted shares use a connector-direction-season reference rather than a universal MW threshold.</p>'
    show = summary.copy(); show["direction"] = show.direction.str.title()
    body += table_html(show.sort_values(["name", "direction"]),
                       ["name", "direction", "direction_label", "flow_median", "capacity_median", "capacity_p10", "headroom_median", "restricted_rate", "forced_rate"],
                       {"flow_median": lambda x: f"{x:,.1f}", "capacity_median": lambda x: f"{x:,.1f}",
                        "capacity_p10": lambda x: f"{x:,.1f}", "headroom_median": lambda x: f"{x:,.1f}",
                        "restricted_rate": lambda x: f"{x:.1%}", "forced_rate": lambda x: f"{x:.1%}"}, 20)
    body += figure_html(plot_div(figs[0][0]), figs[0][1], figs[0][2], "downloads/" + figs[0][3])
    body += '<p>The diurnal flow profiles show that the daily turning points are not common across links. VNI’s pooled forward median rises from a reverse-oriented trough around the morning solar period to a strong VIC-to-NSW transfer overnight. QNI displays the opposite sign pattern in the forward convention, while Murraylink’s much smaller envelope turns within a narrower band. These differences argue against using one generic “interconnector hour” feature across the fleet.</p>'
    body += figure_html(plot_div(figs[1][0]), figs[1][1], figs[1][2], "downloads/" + figs[1][3])
    body += '<p>Limit profiles explain only part of the flow shape. On some links the flow turning point occurs close to the daily limit trough, which is consistent with the operating envelope shaping dispatch. Elsewhere the available limit stays well above realised flow, indicating that regional supply-demand conditions are more important than the interconnector ceiling during the median day. The connector chapters quantify those timings individually.</p></section>'

    seasonal_spread = (seasonal_pooled.groupby(["name", "direction"])
                       .capacity_median.agg(["min", "max"]).assign(spread=lambda x: x["max"] - x["min"])
                       .reset_index().sort_values("spread", ascending=False).iloc[0])
    spread_rows = seasonal_pooled[(seasonal_pooled.name.eq(seasonal_spread["name"])) &
                                  (seasonal_pooled.direction.eq(seasonal_spread["direction"]))]
    spread_low = spread_rows.loc[spread_rows.capacity_median.idxmin()]
    spread_high = spread_rows.loc[spread_rows.capacity_median.idxmax()]
    body += f'<section id="quarters"><div class="section-kicker">SEASONAL LIMITS · QUARTERLY BLOCKS</div><h2>Directional limits are shown by season and by exact three-month block</h2><p>Australian seasons are treated as quarterly blocks: summer is December–February, autumn March–May, winter June–August and spring September–November. December is assigned to the summer ending in the following year. The pooled-season curves answer whether a repeatable within-day limit shape exists across summers, autumns, winters and springs; the block heatmap then keeps each individual quarter separate so structural changes are not mistaken for climatology.</p><p>Across the pooled seasonal medians, the largest seasonal separation is on {escape(str(seasonal_spread["name"]))} {escape(str(seasonal_spread["direction"]))}: {spread_low.capacity_median:,.1f} MW in {escape(str(spread_low.season))} versus {spread_high.capacity_median:,.1f} MW in {escape(str(spread_high.season))}, a {seasonal_spread.spread:,.1f} MW range. This is a descriptive operating-envelope comparison and can include outages, network configuration and demand conditions that recur within those months.</p>'
    body += figure_html(plot_div(figs[2][0]), figs[2][1], figs[2][2], "downloads/" + figs[2][3])
    body += '<p>The forward-flow heatmap provides dispatch context, but flow is not the same as capability. The next two figures isolate the directional operating limits themselves and show how the median envelope changes over the 48 half-hours of the day within each pooled Australian season.</p>'
    body += figure_html(plot_div(figs[11][0]), figs[11][1], figs[11][2], "downloads/" + figs[11][3])
    body += figure_html(plot_div(figs[12][0]), figs[12][1], figs[12][2], "downloads/" + figs[12][3])
    body += '<h3>Pooled-season limit distribution</h3><p>The table reports the median operating limit together with P10 and P90, so a season with a similar median but a much weaker lower tail remains visible. Restricted share is measured against the connector-direction seasonal reference; forced share is the proportion of intervals where the directional limit is negative.</p>'
    pooled_show = seasonal_pooled.copy()
    pooled_show["direction"] = pooled_show.direction.str.title()
    pooled_show["season"] = pd.Categorical(pooled_show.season, SEASON_ORDER, ordered=True)
    pooled_show.sort_values(["name", "direction", "season"], inplace=True)
    body += table_html(pooled_show,
                       ["name", "direction", "season", "intervals", "capacity_p10", "capacity_median", "capacity_p90", "headroom_median", "restricted_rate", "forced_rate"],
                       {"intervals": lambda x: f"{int(x):,}", "capacity_p10": lambda x: f"{x:,.1f}",
                        "capacity_median": lambda x: f"{x:,.1f}", "capacity_p90": lambda x: f"{x:,.1f}",
                        "headroom_median": lambda x: f"{x:,.1f}", "restricted_rate": lambda x: f"{x:.1%}",
                        "forced_rate": lambda x: f"{x:.1%}"}, 60)
    body += '<h3>Exact quarter-block limits</h3><p>Cell labels below are median directional limits in MW. Hovering a cell adds the P10, P90 and restricted-limit share. Only complete blocks with at least 4,000 directional half-hours are shown, so the one-observation September 2026 boundary fragment is excluded.</p>'
    body += figure_html(plot_div(figs[13][0]), figs[13][1], figs[13][2], "downloads/" + figs[13][3])
    block_order = (panel.groupby("season_block", as_index=False).time.min().sort_values("time").season_block.tolist())
    for connector_name in [IC_NAMES[x] for x in IC_ORDER]:
        block_show = seasonal[(seasonal.name.eq(connector_name)) & seasonal.intervals.ge(4000)].copy()
        block_show["direction"] = block_show.direction.str.title()
        block_show["season_block"] = pd.Categorical(block_show.season_block, block_order, ordered=True)
        block_show.sort_values(["direction", "season_block"], inplace=True)
        body += f'<details><summary>{escape(connector_name)} — directional limit statistics by quarter block</summary>'
        body += table_html(block_show,
                           ["direction", "season_block", "intervals", "capacity_p10", "capacity_median", "capacity_p90", "headroom_median", "restricted_rate", "forced_rate"],
                           {"intervals": lambda x: f"{int(x):,}", "capacity_p10": lambda x: f"{x:,.1f}",
                            "capacity_median": lambda x: f"{x:,.1f}", "capacity_p90": lambda x: f"{x:,.1f}",
                            "headroom_median": lambda x: f"{x:,.1f}", "restricted_rate": lambda x: f"{x:.1%}",
                            "forced_rate": lambda x: f"{x:.1%}"}, 30) + '</details>'
    body += '<p>The block comparison reveals structural shifts as well as recurring seasonality. A gap between two winters or two summers is evidence that the network state changed within the same climatological season; it should not be smoothed away as a weather effect. These are realised solved limits, not nominal ratings.</p></section>'

    body += '<section id="connectors"><div class="section-kicker">CONNECTOR CHAPTERS</div><h2>Six links, twelve directional operating regimes</h2><p>Each chapter follows the same logic: first the realised transfer and directional envelope, then the within-day pattern, quarterly seasonal blocks, weather/VRE regime separation, and finally the published binding, reconstructed setter and DUID-pressure evidence. “Upper” corresponds to the named forward limit; “lower” corresponds to the reverse-side limit before sign normalization.</p></section>'
    for connector_name in [IC_NAMES[x] for x in IC_ORDER]:
        body += connector_story(connector_name, summary, diurnal, seasonal, regime_deltas, enso, family, duid, period_setters)

    body += '<section id="weather"><div class="section-kicker">WEATHER & RENEWABLE REGIMES</div><h2>Conditional differences are large—but not causal estimates</h2><p>For each connector, direction and Australian season, the low regime is at or below the within-season 20th percentile and the high regime is at or above the 80th percentile. This controls for the broad seasonal level without fitting a model. The table reports the season with the largest absolute high-minus-low difference for each driver, which is useful for screening where a regime matters most. It should not be read as an all-else-equal temperature or VRE effect.</p>'
    body += table_html(regime_deltas.sort_values(["driver", "name", "direction"]),
                       ["name", "direction", "driver", "season", "low_regime_limit", "high_regime_limit", "high_minus_low"],
                       {"low_regime_limit": lambda x: f"{x:,.1f}", "high_regime_limit": lambda x: f"{x:,.1f}", "high_minus_low": lambda x: f"{x:+,.1f}"}, 50)
    body += '<p>Temperature and humidity often show opposite-signed splits because they proxy the same synoptic conditions from different directions. The clearest example is VNI forward in summer: the high-temperature regime has a much lower median limit than the low-temperature regime, while the high-humidity regime has a much higher limit than the low-humidity regime. That is a useful operating pattern, but it is also a warning against treating either variable independently without controlling for concurrent demand, outages and network configuration.</p>'
    body += figure_html(plot_div(figs[3][0]), figs[3][1], figs[3][2], "downloads/" + figs[3][3])
    body += figure_html(plot_div(figs[4][0]), figs[4][1], figs[4][2], "downloads/" + figs[4][3])
    enso_fig = px.bar(enso, x="name", y="capacity_median", color="enso_state", facet_col="direction", barmode="group",
                      category_orders={"enso_state": ["El Niño", "Neutral"]},
                      color_discrete_map={"El Niño": "#ce9a48", "Neutral": "#66717e"},
                      labels={"capacity_median": "Median directional limit MW", "name": "", "enso_state": "ONI episode state"})
    style_plotly(enso_fig, "Directional dispatch limits by ONI historical episode state", 540)
    body += '<h3>ENSO state comparison</h3><p>The study window is not balanced across ENSO states: El Niño covers eight months at the front of the sample, while the remainder is neutral-labelled under the five-overlapping-season rule. The late-2025 cold excursion and April–July 2026 warm excursion do not meet the duration rule in the retained data. Differences below therefore combine ENSO state with the particular seasons, outages and demand conditions present in those months.</p>'
    body += figure_html(plot_div(enso_fig), "Interconnector limits by ENSO state", "NOAA CPC ONI v6 historical episode labels; August 2026 excluded because the centered-season value was unavailable.", "downloads/enso_regimes.csv")
    body += table_html(enso.sort_values(["name", "direction", "enso_state"]),
                       ["name", "direction", "direction_label", "enso_state", "months", "oni_median", "flow_median", "capacity_median", "capacity_p10", "restricted_rate", "forced_rate"],
                       {"months": lambda x: f"{int(x):,}", "oni_median": lambda x: f"{x:+.1f}", "flow_median": lambda x: f"{x:,.1f}", "capacity_median": lambda x: f"{x:,.1f}", "capacity_p10": lambda x: f"{x:,.1f}", "restricted_rate": lambda x: f"{x:.1%}", "forced_rate": lambda x: f"{x:.1%}"}, 30)
    body += '<h3>Observed-point scatter: inspect the shape, not a fitted line</h3><p>The scatterplots retain individual observed half-hours in a deterministic sample. Vertical bands indicate repeated operating limits; sloped or curved clouds can reflect changing network states, demand and correlated weather rather than a stable response coefficient. Hovering a point shows the connector, direction, season and timestamp so apparent clusters can be traced back to the underlying regime.</p>'
    for index in [5, 6, 7, 8]:
        body += figure_html(plot_div(figs[index][0]), figs[index][1], figs[index][2], "downloads/" + figs[index][3])
    body += '</section>'

    binders["limit_side"] = binders.direction.map({"upper": "Forward / upper", "lower": "Reverse / lower"})
    setters["limit_side"] = setters.direction.map({"upper": "Forward / upper", "lower": "Reverse / lower"})
    body += '<section id="constraints"><div class="section-kicker">CONSTRAINT EVIDENCE</div><h2>Binding families and active limit-setters answer different questions</h2><p>A published binding interval is one in which AEMO’s marginal value for the constraint is non-zero. It tells us that relaxing the equation would have changed the dispatch solution. A reconstructed active limit-setter is the equation producing the tightest conditional interconnector bound after solving its generic-constraint equation for the interconnector term. It tells us which retained equation most directly formed the directional envelope. The same family can appear in both lists, but it need not.</p>'
    body += '<h3>Most frequent published binding families</h3><p>Counts below are five-minute intervals across the two-year constraint window. Binding rate is calculated only over intervals in which the exact family version was applicable. Descriptions are retained because IDs alone often obscure whether the equation addresses an outage, thermal limit, stability limit or a broader transfer requirement.</p>'
    body += table_html(binders, ["name", "limit_side", "CONSTRAINTID", "DESCRIPTION", "binding_intervals", "binding_rate", "near_binding_intervals", "exact_versions"],
                       {"binding_intervals": lambda x: f"{int(x):,}", "binding_rate": lambda x: f"{x:.1%}", "near_binding_intervals": lambda x: f"{int(x):,}", "exact_versions": lambda x: f"{int(x):,}"}, 40)
    body += figure_html(plot_div(figs[9][0]), figs[9][1], figs[9][2], "downloads/" + figs[9][3])
    body += '<h3>Most frequent reconstructed directional setters</h3><p>This ranking focuses on the equations that actually formed the tightest retained upper or lower candidate. A zero leader count beside a high binding count is not an error: the equation could bind for another term in the dispatch solution without becoming the tightest reconstructed interconnector bound.</p>'
    body += table_html(setters, ["name", "limit_side", "CONSTRAINTID", "DESCRIPTION", "leading_intervals", "binding_intervals", "near_setting_intervals", "exact_versions"],
                       {"leading_intervals": lambda x: f"{int(x):,}", "binding_intervals": lambda x: f"{int(x):,}", "near_setting_intervals": lambda x: f"{int(x):,}", "exact_versions": lambda x: f"{int(x):,}"}, 40)
    body += '<p>For QNI and Directlink, <code>N&gt;&gt;NIL_33_34</code> is a prominent reconstructed upper setter, but the lower-side published binding leaders are different families. Murraylink and VNI share some Victorian/NSW constraint families, yet their realised leader frequencies and DUID pressure differ. This is why equation IDs should not be transferred from one interconnector model to another without checking the interconnector coefficient and active direction.</p>'

    body += '<h3>Diurnal constraint leaders: overnight, morning peak, solar and evening peak</h3><p>The next view ranks the active reconstructed equation inside four exhaustive time blocks: overnight 21:00–05:59, morning peak 06:00–08:59, solar period 09:00–15:59 and evening peak 16:00–20:59. Colour measures concentration—the share of retained setter intervals accounted for by the leading equation. Hover reveals the equation ID. A high share indicates a stable dominant envelope constraint; a low share indicates a rotating constraint set.</p>'
    period_leaders = period_setters[period_setters["rank"].eq(1)].copy()
    period_leaders["side"] = period_leaders.direction.map({"upper": "forward / upper", "lower": "reverse / lower"})
    period_leaders["row"] = period_leaders.name + " · " + period_leaders.side
    row_order = [f"{IC_NAMES[ic]} · {side}" for ic in IC_ORDER for side in ["forward / upper", "reverse / lower"]]
    share_matrix = period_leaders.pivot(index="row", columns="daily_period", values="setter_share").reindex(index=row_order, columns=DAILY_PERIOD_ORDER)
    id_matrix = period_leaders.pivot(index="row", columns="daily_period", values="constraint").reindex(index=row_order, columns=DAILY_PERIOD_ORDER)
    period_fig = go.Figure(go.Heatmap(
        z=share_matrix.values, x=share_matrix.columns, y=share_matrix.index,
        customdata=id_matrix.values, colorscale="Blues", zmin=0, zmax=1,
        text=np.vectorize(lambda x: "—" if pd.isna(x) else f"{x:.0%}")(share_matrix.values),
        texttemplate="%{text}",
        hovertemplate="%{y}<br>%{x}<br>%{customdata}<br>setter share %{z:.1%}<extra></extra>",
        colorbar=dict(title="Top setter share")))
    style_plotly(period_fig, "Dominant reconstructed constraint by key daily period", 720)
    period_fig.update_layout(hovermode="closest")
    body += figure_html(plot_div(period_fig), "Dominant constraint by daily operating period", "Cell labels are the leading constraint's share; hover for constraint ID. Active reconstructed setters, not marginal-value binding classifications.", "downloads/constraint_diurnal_setters.csv.gz")

    body += '<h3>Temperature and source-VRE regime matrices</h3><p>Each cell below shows the top reconstructed setter and its share for one connector side, daily period and within-season regime. Reading across a row answers the practical question: does the constraint that sets the morning, solar or evening envelope change when temperature or source-region VRE moves from low to high? The downloadable table retains the top three equations for every cell.</p>'
    for connector_name in [IC_NAMES[x] for x in IC_ORDER]:
        use = regime_setters[(regime_setters.name.eq(connector_name)) & regime_setters["rank"].eq(1)].copy()
        use["side"] = use.direction.map({"upper": "Forward / upper", "lower": "Reverse / lower"})
        use["daily_period"] = pd.Categorical(use.daily_period, DAILY_PERIOD_ORDER, ordered=True)
        use["cell"] = use.constraint.astype(str) + " (" + use.setter_share.map(lambda x: f"{x:.0%}") + ")"
        matrix = use.pivot_table(index=["side", "daily_period"], columns=["driver", "regime"], values="cell", aggfunc="first", observed=True).reset_index()
        matrix.columns = [" · ".join([str(x) for x in col if str(x)]) if isinstance(col, tuple) else str(col) for col in matrix.columns]
        wanted = ["side", "daily_period", "Temperature · low", "Temperature · normal", "Temperature · high",
                  "Source VRE · low", "Source VRE · normal", "Source VRE · high"]
        matrix = matrix.rename(columns={"side · ": "side", "daily_period · ": "daily_period"})
        matrix = matrix[[col for col in wanted if col in matrix.columns]].sort_values(["side", "daily_period"])
        matrix = matrix.astype(object).where(matrix.notna(), "—")
        body += f'<details><summary>{escape(connector_name)} — regime × daily-period leaders</summary>'
        body += table_html(matrix, list(matrix.columns), limit=20) + '</details>'

    body += '<h3>Quarter-block × daily-period matrices</h3><p>These matrices repeat the same ranking for each complete Australian seasonal block in the two-year constraint window. They make persistent seasonality distinguishable from one-off network configurations: a constraint that dominates the same daily period across several blocks is structurally different from one appearing only during a single outage-rich quarter.</p>'
    constraint_start, constraint_end = pd.Timestamp("2024-09-01"), pd.Timestamp("2026-08-31 23:59")
    season_order = (panel[panel.time.between(constraint_start, constraint_end)]
                    .groupby("season_block", as_index=False).time.min().sort_values("time").season_block.tolist())
    for connector_name in [IC_NAMES[x] for x in IC_ORDER]:
        use = season_setters[(season_setters.name.eq(connector_name)) & season_setters["rank"].eq(1)].copy()
        use["side"] = use.direction.map({"upper": "Forward / upper", "lower": "Reverse / lower"})
        use["daily_period"] = pd.Categorical(use.daily_period, DAILY_PERIOD_ORDER, ordered=True)
        use["cell"] = use.constraint.astype(str) + " (" + use.setter_share.map(lambda x: f"{x:.0%}") + ")"
        matrix = use.pivot_table(index=["side", "daily_period"], columns="season_block", values="cell", aggfunc="first", observed=True).reset_index()
        matrix.columns.name = None
        matrix = matrix[["side", "daily_period"] + [col for col in season_order if col in matrix.columns]]
        matrix.sort_values(["side", "daily_period"], inplace=True)
        matrix = matrix.astype(object).where(matrix.notna(), "—")
        body += f'<details><summary>{escape(connector_name)} — quarter-block × daily-period leaders</summary>'
        body += table_html(matrix, list(matrix.columns), limit=20) + '</details>'
    body += '<p class="callout scope-note"><strong>Binding-versus-setting limitation.</strong> Exact equation-level marginal values were compacted to monthly published-binding counts, so the retained files cannot truthfully split published binding intervals by weather regime or time block without rerunning the raw dispatch-equation pipeline. The regime matrices therefore use the retained five-minute active reconstructed setter—the equation actually forming the conditional upper or lower envelope. The overall published-binding tables above remain the authoritative marginal-value ranking.</p></section>'

    pressure["limit_side"] = pressure.direction.map({"upper": "Forward / upper", "lower": "Reverse / lower"})
    body += '<section id="duids"><div class="section-kicker">GENERATOR PRESSURE</div><h2>Which DUIDs move the active constraint envelope?</h2><p>For an active equation written as aF + Σ(bᵢPᵢ) + Z ≤ RHS, the DUID sensitivity of the interconnector bound is −bᵢ/a. The report multiplies that sensitivity by observed dispatch movement and then normalizes the sign so positive pressure means directional capacity tightened. Cumulative tightening therefore combines three things: how often the equation leads, how sensitive the bound is to the unit, and how much the unit actually moves while that equation leads.</p>'
    body += figure_html(plot_div(figs[10][0]), figs[10][1], figs[10][2], "downloads/" + figs[10][3])
    body += '<p>The heatmap should be read within connector and constraint context, not as a league table of “bad” generators. A DUID may appear as the largest tightening contributor on one equation and provide relief on another. Storage, pumps and loads retain their source dispatch signs, and simultaneous non-leading equations do not receive duplicate pressure attribution.</p>'
    body += table_html(pressure, ["name", "limit_side", "constraint", "DUID", "sensitivity_median", "active_intervals", "season_blocks", "total_tightening", "p95_tightening", "total_relief"],
                       {"sensitivity_median": lambda x: f"{x:,.3f}", "active_intervals": lambda x: f"{int(x):,}", "season_blocks": lambda x: f"{int(x):,}", "total_tightening": lambda x: f"{x:,.0f}", "p95_tightening": lambda x: f"{x:,.1f}", "total_relief": lambda x: f"{x:,.0f}"}, 40)
    body += '<p>Several rankings are operationally intuitive. Basslink’s strongest retained pressure pairs are tied to Tasmanian units under Basslink-specific frequency or transfer equations. The QNI/Directlink rankings concentrate on northern NSW and Queensland renewable DUIDs under NSW–Queensland transfer families. Victorian and South Australian links show a broader mixture of wind, solar, hydro, battery and thermal DUIDs because the active equations span shared western-Victorian and NSW–Victoria network elements.</p></section>'

    body += '<section id="methods"><div class="section-kicker">METHODS & LIMITATIONS</div><h2>How to use the results</h2><p>The analysis window for flow, limits, weather and VRE is 1 September 2023 through 31 August 2026 in fixed UTC+10 NEM market time. The constraint and pressure archive covers 1 September 2024 through 31 August 2026. Half-hour observations require six distinct five-minute records. Weather is the mean of retained representative sites at the connector endpoints; VRE is cleared semi-scheduled wind plus solar in the source or sink region.</p><p>“Restricted” means the directional limit is below 50% of the positive connector-direction-season median. This is a comparative operating-regime definition, not an engineering derating declaration. Quarter-block claims use only blocks with at least 4,000 half-hours, excluding the one-observation boundary block at 1 September 2026. Regime comparisons use P20/P80 splits within connector and Australian season.</p><p>The constraint reconstruction solves each applicable generic equation for the interconnector term. Minimum upper and maximum lower candidates form the retained envelope. Published marginal value defines binding; 0–50 MW normalized slack defines near-binding. The generator-pressure method is a deterministic equation decomposition, not an econometric estimate and not proof of operator intent.</p><p><strong>Most important limitation.</strong> Local weather, VRE, demand, outages, constraint configuration and ENSO state are correlated. The report deliberately presents scatter, medians and counts rather than fitted coefficients. The ENSO comparison contains one El Niño episode segment and no qualifying La Niña segment, so it cannot separate episode effects from the specific months represented. Any decision that requires an isolated weather or ENSO sensitivity, or a forecast, should be built as a separate model with explicit train/test periods and stability checks.</p><p>The full field definitions, equations, calendars, sampling design and interpretation boundaries are in <a href="METHODOLOGY.md">METHODOLOGY.md</a>. The ONI source is the <a href="https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/">NOAA Climate Prediction Center historical ONI v6 table</a>.</p>'
    body += table_html(constraint_coverage, ["name", "expected_months", "complete_months", "status"], limit=10)
    body += '<div class="downloads"><h3>Research data</h3><ul>' + ''.join(f'<li><a href="downloads/{name}" download>{name}</a></li>' for name in outputs)
    body += '</ul><h3>Source snapshots</h3><ul><li><a href="sources/noaa_oni_v6_study_context.csv" download>NOAA CPC ONI v6 study-window snapshot</a></li></ul></div></section>'
    body += '<footer><p>Prepared 21 September 2026 · NEM market time UTC+10 · Descriptive research report generated from retained public-market, constraint and weather data. No fitted effect model.</p></footer>'
    html = render_page("NEM interconnector diurnal and constraint-pressure research", body, plotly=True, accent="purple")
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    (OUT / "index.html").write_text(html, encoding="utf-8")
    if (SOURCES_OUT / "nos_outage_regime_section.html").exists():
        # Re-insert the cached outage-regime section (scripts/build_nos_regime_section.py) after a base rebuild.
        from build_nos_regime_section import inject
        inject(OUT)

    manifest = {"report_id": REPORT_ID, "built_at": pd.Timestamp.now(tz="Asia/Singapore").isoformat(),
                "inputs": {}, "outputs": {}, "constraint_coverage": constraint_coverage.to_dict("records"),
                "rebuild": "python scripts/build_all_ic_regime_report.py"}
    for path in [ROOT / "data/processed/targets.parquet", ROOT / "data/processed/regional_30min.parquet", ROOT / "data/processed/weather_30min.parquet",
                 SOURCES_OUT / "noaa_oni_v6_study_context.csv"]:
        manifest["inputs"][str(path.relative_to(ROOT))] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    for path in sorted(OUT.rglob("*")):
        excluded_local_outputs = {
            "build_manifest.json", "finalization_status.json", "constraint_duid_regime_matrix.csv",
            "constraint_family_summary.csv", "regime_scatter_sample.csv",
        }
        if path.is_file() and path.name not in excluded_local_outputs:
            manifest["outputs"][str(path.relative_to(OUT))] = {"bytes": path.stat().st_size, "sha256": digest(path)}
    (OUT / "build_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"report": str(OUT / "index.html"), "rows": len(panel), "constraints": len(family),
                      "duid_pairs": len(duid), "constraint_months": complete_constraints}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    build()
