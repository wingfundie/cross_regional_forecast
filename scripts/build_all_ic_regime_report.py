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
COLORS = {"Summer": "#ce9a48", "Autumn": "#8370b4", "Winter": "#5696b9", "Spring": "#268a87"}
SEASON_ORDER = ["Summer", "Autumn", "Winter", "Spring"]
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
    return '<div class="table-wrap" tabindex="0">' + use.to_html(index=False, classes="data-table", border=0, escape=True) + "</div>"


def figures(panel, diurnal, regimes, scatter, family, duid, pressure_regime):
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
    return figs


def methodology_text(coverage: pd.DataFrame) -> str:
    coverage_table = coverage.to_markdown(index=False) if not coverage.empty else "No constraint runs were available."
    return f"""# Methodology — all-interconnector diurnal and constraint-pressure research

## Scope and frozen windows

The flow, dispatch-limit, weather and VRE study covers `(2023-09-01 00:00, 2026-09-01 00:00]` in fixed UTC+10 NEM time. The constraint and DUID-pressure study covers `2024-09-01 00:00` through `2026-08-31 23:55`. The six links are QNI, Directlink, VNI, Heywood, Murraylink and Basslink. Nominal ratings, ENSO and prices are outside scope.

Australian seasons are complete three-month blocks: Summer December–February, Autumn March–May, Winter June–August and Spring September–November. December belongs to the summer ending in the next year. Calendar-quarter sensitivity uses only complete Q1–Q4 blocks; partial boundary quarters are excluded.

## Flow and dispatch limits

Signed flow follows each connector's declared forward orientation. `forward_capacity = upper_bound`; `reverse_capacity = -lower_bound`. Headroom is capacity less directional flow. Negative capacities are retained and counted as forced-direction observations. A restricted limit is below 50% of the connector-direction Australian-season median of strictly positive capacity. A complete half-hour requires six distinct five-minute observations.

## Weather and VRE

Weather is the mean of retained representative sites in each endpoint region; endpoint maximum temperature is also retained. Regional VRE is cleared semi-scheduled wind plus solar. Residual demand is regional demand less those wind and solar fields; rooftop PV is not subtracted again. Regimes are defined within connector and Australian season: low ≤P20, normal P20–P80 and high ≥P80. Scatterplots use a deterministic sample of 3,000 observed half-hours per connector-direction for browser performance. No trend line, regression or model-derived effect is fitted.

## Constraint reconstruction

For `aF + Σ(bᵢPᵢ) + Z ≤ RHS`, the conditional bound is `observed flow + (RHS − solved LHS)/a`, and DUID sensitivity is `−bᵢ/a`. Positive `a` forms an upper candidate; negative `a` forms a lower candidate. Minimum upper and maximum lower candidates form the reconstructed envelope. Binding means absolute published marginal value above `1e-9`; near-binding means interconnector-normalized slack from 0 to 50 MW. Reported setters and reconstructed leaders remain separate.

Constraint run coverage at build time:

{coverage_table}

## DUID pressure

For the active reconstructed leader, movement contribution is `sᵢ × (Pᵢ[t] − Pᵢ[t−30m])`. Upper capacity uses that sign; lower/reverse capacity negates it. Tightening is the positive part of a capacity reduction; relief is the positive part of a capacity increase. Rankings therefore reflect observed movement under an active equation, not coefficient size alone and not independent causation. Pumps, batteries and loads retain source dispatch signs. Compact monthly files preserve leader-based pressure; simultaneous non-leading binding equations remain in the constraint-population table but do not receive duplicated connector-level pressure.

## Output lineage

`connector_summary.csv`, `diurnal_profiles.csv`, `seasonal_profiles.csv`, `weather_vre_regimes.csv`, `regime_scatter_sample.csv`, `constraint_family_summary.csv`, `constraint_duid_influence.csv`, `constraint_duid_regime_matrix.csv` and `coverage_audit.csv` are generated before report rendering. The build manifest records input and output hashes. Missing observations are never converted to zero.

## Rebuild

```powershell
python scripts/build_all_ic_regime_report.py
python C:\\Users\\HomePC\\.codex\\skills\\editorial-html-report\\scripts\\validate_report.py reports\\{REPORT_ID}\\index.html
```
"""


def build():
    OUT.mkdir(parents=True, exist_ok=True); DATA_OUT.mkdir(parents=True, exist_ok=True)
    panel = build_panel()
    summary = connector_summary(panel)
    diurnal = diurnal_profiles(panel)
    seasonal = (panel.groupby(["ic", "name", "direction", "season", "season_block"], as_index=False)
                .agg(intervals=("time", "size"), flow_median=("directional_flow", "median"),
                     capacity_median=("capacity", "median"), capacity_p10=("capacity", lambda s: s.quantile(.1)),
                     headroom_median=("headroom", "median"), restricted_rate=("restricted", "mean"),
                     forced_rate=("forced_direction", "mean")))
    regimes = regime_tables(panel)
    scatter = scatter_sample(panel)
    population, pressure_paths, constraint_coverage = load_constraints()
    family, duid, pressure_regime = constraint_summaries(population, pressure_paths)

    outputs = {
        "connector_summary.csv": summary, "diurnal_profiles.csv": diurnal,
        "seasonal_profiles.csv": seasonal, "weather_vre_regimes.csv": regimes,
        "regime_scatter_sample.csv.gz": scatter,
        "constraint_family_summary.csv.gz": family, "constraint_duid_influence.csv": duid,
        "constraint_duid_regime_matrix.csv.gz": pressure_regime, "coverage_audit.csv": constraint_coverage,
    }
    for name, frame in outputs.items():
        compression = {"method": "gzip", "mtime": 0} if name.endswith(".gz") else None
        frame.to_csv(DATA_OUT / name, index=False, compression=compression)
    (OUT / "METHODOLOGY.md").write_text(methodology_text(constraint_coverage), encoding="utf-8")

    complete_constraints = int(constraint_coverage.complete_months.sum()) if not constraint_coverage.empty else 0
    top_family = family.sort_values("binding_intervals", ascending=False).iloc[0] if not family.empty else None
    top_duid = duid.sort_values("total_tightening", ascending=False).iloc[0] if not duid.empty else None
    body = hero("NEM · SIX INTERCONNECTORS · FIVE-MINUTE EVIDENCE",
                "When interconnectors move —", "and what tightens them",
                "Three years of observed diurnal flow, dispatch-limit, weather and renewable regimes, joined to two years of constraint and DUID-level pressure evidence—without fitted effect models.",
                ["Data through 31 Aug 2026", "12 Australian seasonal blocks", "Calendar-quarter sensitivity", "Offline interactive report"])
    body += '<nav class="anchor-nav"><a href="#findings">Findings</a><a href="#diurnal">Diurnal</a><a href="#quarters">Quarter blocks</a><a href="#weather">Weather & VRE</a><a href="#constraints">Constraints</a><a href="#duids">DUID pressure</a><a href="#profiles">Profiles</a><a href="#methods">Methods</a></nav>'
    body += '<section class="metrics">' + metric("Market observations", f"{len(panel)//2:,}", "connector × half-hour rows before directional expansion")
    body += metric("Seasonal blocks", "12", "three complete blocks for each Australian season")
    body += metric("Constraint months", f"{complete_constraints}/144", "completed connector-months at build time")
    body += metric("DUID pressure pairs", f"{len(duid):,}", "DUID × governing-constraint rankings") + '</section>'
    body += '<section class="callout"><strong>Interpretation boundary.</strong> Reported dispatch limits are solved operating outcomes, not nominal physical ratings. Weather/VRE results are conditional associations. DUID pressure is a mechanical −b/a × dispatch-movement attribution under the active reconstructed equation, not independent causation.</section>'

    body += '<section id="findings"><h2>Evidence-led findings</h2><div class="findings">'
    restricted = summary.sort_values("restricted_rate", ascending=False).iloc[0]
    forced = summary.sort_values("forced_rate", ascending=False).iloc[0]
    body += finding(1, "Restrictions are link and direction specific", f"{restricted['name']} {restricted['direction']} has the highest three-year restricted-limit share in this build ({restricted['restricted_rate']:.1%}). Parallel links are therefore kept separate.")
    body += finding(2, "Forced-direction limits are visible", f"{forced['name']} {forced['direction']} has the highest negative directional-limit share ({forced['forced_rate']:.1%}); negative limits are preserved rather than clipped.")
    body += finding(3, "Quarter blocks expose variation", "The report shows each complete three-month Australian seasonal block before pooling by season, then repeats core tables on complete calendar quarters.")
    if top_family is not None:
        body += finding(4, "Binding evidence is equation specific", f"{top_family['CONSTRAINTID']} on {top_family['name']} is the most frequent binding family in the completed archive ({int(top_family['binding_intervals']):,} five-minute intervals).")
    if top_duid is not None:
        body += finding(5, "Movement matters as much as sensitivity", f"{top_duid['DUID']} has the largest cumulative tightening pressure among retained top-constraint pairs; the ranking uses realised 30-minute movement, not coefficient magnitude alone.")
    body += finding(6, "Coverage remains explicit", "Every table carries counts, and connector constraint coverage is published so control-mode or unsupported intervals remain unattributed rather than assigned to a generator.")
    body += '</div></section>'

    figs = figures(panel, diurnal, regimes, scatter, family, duid, pressure_regime)
    ids = ["diurnal", "diurnal-limits", "quarters", "weather", "vre", "temperature-scatter", "humidity-scatter", "vre-flow-scatter", "vre-limit-scatter", "constraints", "duids"]
    for ident, (fig, caption, note, data_file) in zip(ids, figs):
        body += f'<section id="{ident}"><h2>{caption}</h2>' + figure_html(plot_div(fig), caption, note, "downloads/" + data_file) + '</section>'

    body += '<section id="profiles"><h2>Connector and direction scorecard</h2><p>The scorecard uses the complete three-year half-hour panel. Restricted limits are below half of the positive Australian-season reference.</p>'
    show = summary.copy(); show["direction"] = show.direction.str.title()
    body += table_html(show.sort_values(["name", "direction"]),
                       ["name", "direction", "direction_label", "flow_median", "capacity_median", "capacity_p10", "headroom_median", "restricted_rate", "forced_rate"],
                       {"flow_median": lambda x: f"{x:,.1f}", "capacity_median": lambda x: f"{x:,.1f}",
                        "capacity_p10": lambda x: f"{x:,.1f}", "headroom_median": lambda x: f"{x:,.1f}",
                        "restricted_rate": lambda x: f"{x:.1%}", "forced_rate": lambda x: f"{x:.1%}"}, 20) + '</section>'

    if not duid.empty:
        leaders = duid.sort_values("total_tightening", ascending=False).groupby(["ic", "direction", "constraint"], as_index=False).head(3).head(60)
        body += '<section><h2>Top DUIDs within top constraints</h2><p>Each row is a DUID evaluated only while the named constraint was the active reconstructed directional leader. Full rankings are downloadable.</p>'
        body += table_html(leaders, ["name", "direction", "constraint", "DUID", "sensitivity_median", "active_intervals", "season_blocks", "total_tightening", "total_relief", "p95_tightening"],
                           {"sensitivity_median": lambda x: f"{x:,.4f}", "total_tightening": lambda x: f"{x:,.0f}",
                            "total_relief": lambda x: f"{x:,.0f}", "p95_tightening": lambda x: f"{x:,.1f}"}, 60) + '</section>'

    body += '<section id="methods"><h2>Methods, coverage and downloads</h2><p>The complete definitions, equations, quarterly calendars, sampling design and interpretation limits are in <a href="METHODOLOGY.md">METHODOLOGY.md</a>.</p>'
    body += table_html(constraint_coverage, ["name", "expected_months", "complete_months", "status"], limit=10)
    body += '<div class="downloads"><h3>Research data</h3><ul>' + ''.join(f'<li><a href="downloads/{name}" download>{name}</a></li>' for name in outputs) + '</ul></div></section>'
    body += '<footer><p>Prepared 21 September 2026 · NEM market time UTC+10 · Generated from retained public-market and weather data.</p></footer>'
    html = render_page("NEM interconnector diurnal and constraint-pressure research", body, plotly=True, accent="purple")
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    (OUT / "index.html").write_text(html, encoding="utf-8")

    manifest = {"report_id": REPORT_ID, "built_at": pd.Timestamp.now(tz="Asia/Singapore").isoformat(),
                "inputs": {}, "outputs": {}, "constraint_coverage": constraint_coverage.to_dict("records"),
                "rebuild": "python scripts/build_all_ic_regime_report.py"}
    for path in [ROOT / "data/processed/targets.parquet", ROOT / "data/processed/regional_30min.parquet", ROOT / "data/processed/weather_30min.parquet"]:
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
