"""Conditional EnergyConnect limit lookup and supporting observations."""

from pathlib import Path

import numpy as np
import pandas as pd

from .scenario_html import render_scenario

DIRECTIONS = ("nsw_sa", "sa_nsw")
AGGREGATIONS = ("tight", "mean")
REGIONS = ("nsw", "sa", "vic")
FEATURES = tuple(f"{region}_{metric}" for region in REGIONS for metric in ("demand", "wind", "solar"))
ANALYSIS_FEATURES = (*FEATURES, *(f"{region}_residual" for region in REGIONS))
PERIODS = (("morning", 360, 540), ("solar", 540, 960), ("evening", 960, 1260))
QUANTILES = (0.10, 0.50, 0.90)
BOOTSTRAP_REPLICATES = 500
CALIPER_FLOOR_MW = 100
UNVERIFIED_CONFIGURATION = "Commissioning cap unverified"


def delivery_period(times: pd.Series) -> pd.Series:
    """Classify each complete half-hour by its NEM-time midpoint."""
    midpoint = pd.to_datetime(times) - pd.Timedelta(minutes=15)
    minutes = midpoint.dt.hour * 60 + midpoint.dt.minute
    return pd.Series(
        np.select([minutes.ge(start) & minutes.lt(end) for _, start, end in PERIODS],
                  [name for name, _, _ in PERIODS], default="overnight"),
        index=times.index,
    )


def prepare_observations(half_hour: pd.DataFrame) -> pd.DataFrame:
    columns = ["time", "configuration"]
    for direction in DIRECTIONS:
        columns.extend(f"{direction}_{suffix}" for suffix in (*AGGREGATIONS, "setter", "minimum_time"))
        episode = f"{direction}_episode_id"
        if episode in half_hour:
            columns.append(episode)
    frame = half_hour.loc[:, columns].copy()
    frame["time"] = pd.to_datetime(frame["time"])
    if (frame["time"].dt.tz is not None or frame["time"].isna().any()
            or frame["time"].duplicated().any() or not frame["time"].eq(frame["time"].dt.floor("30min")).all()):
        raise ValueError("Scenario observations require unique interval-ending half-hours in fixed NEM time.")
    frame["configuration"] = frame["configuration"].astype("string").str.strip().replace("", pd.NA)
    frame["configuration_evidenced"] = (
        frame["configuration"].notna()
        & ~frame["configuration"].str.contains(UNVERIFIED_CONFIGURATION, regex=False, na=False)
    )
    frame["study_day"] = (frame["time"] - pd.Timedelta(seconds=1)).dt.strftime("%Y-%m-%d")
    frame["delivery_period"] = delivery_period(frame["time"])
    for feature in ANALYSIS_FEATURES:
        frame[feature] = pd.to_numeric(half_hour.get(feature, np.nan), errors="coerce")
    for direction in DIRECTIONS:
        for aggregation in AGGREGATIONS:
            target = f"{direction}_{aggregation}"
            frame[target] = pd.to_numeric(frame[target], errors="coerce")
            if not np.isfinite(frame[target]).all():
                raise ValueError(f"Scenario observations require finite values for {target}.")
        frame[f"{direction}_minimum_time"] = pd.to_datetime(frame[f"{direction}_minimum_time"])
        frame[f"{direction}_setter"] = frame[f"{direction}_setter"].astype("string").replace("", pd.NA)
    return frame.sort_values("time", ignore_index=True)


def day_bootstrap(values: np.ndarray, days: pd.Series) -> np.ndarray:
    """Return a 95% interval for each quantile after resampling whole NEM days."""
    day_index, unique_days = pd.factorize(days, sort=True)
    num_days = len(unique_days)
    if num_days < 2:
        return np.full((2, len(QUANTILES)), np.nan)
    # The browser uses the same deterministic draws so the two exports agree.
    counts = np.zeros((BOOTSTRAP_REPLICATES, num_days), dtype=np.int32)
    state = 713
    mask = (1 << 32) - 1
    for replicate in counts:
        for _ in range(num_days):
            state ^= (state << 13) & mask
            state ^= state >> 17
            state ^= (state << 5) & mask
            replicate[(state * num_days) >> 32] += 1
    ordered = np.argsort(values, kind="stable")
    cumulative_counts = counts[:, day_index[ordered]].cumsum(axis=1)
    ranks = (cumulative_counts[:, -1, None] - 1) * np.asarray(QUANTILES)
    lower = np.floor(ranks)
    upper = np.ceil(ranks)
    sorted_values = values[ordered]
    left = sorted_values[(cumulative_counts[:, :, None] > lower[:, None, :]).argmax(axis=1)]
    right = sorted_values[(cumulative_counts[:, :, None] > upper[:, None, :]).argmax(axis=1)]
    samples = left + (right - left) * (ranks - lower)
    return np.quantile(samples, [0.025, 0.975], axis=0)


def support_label(days: int) -> str:
    return "multi_day" if days > 1 else "single_day_example"


def limits_lookup(observations: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (configuration, period), cohort in observations.groupby(["configuration", "delivery_period"], sort=True):
        days = cohort["study_day"].nunique()
        for direction in DIRECTIONS:
            setters = cohort[f"{direction}_setter"].fillna("unresolved").value_counts()
            dominant = min(setters.index[setters.eq(setters.max())])
            for aggregation in AGGREGATIONS:
                values = cohort[f"{direction}_{aggregation}"].to_numpy()
                estimates = np.quantile(values, QUANTILES)
                confidence = day_bootstrap(values, cohort["study_day"])
                row = {
                    "configuration": configuration, "delivery_period": period,
                    "direction": direction, "aggregation": aggregation, "unit": "MW",
                    "intervals": len(cohort), "distinct_days": days, "support": support_label(days),
                    "dominant_setter": dominant, "dominant_setter_intervals": int(setters[dominant]),
                }
                for column, estimate, (low, high) in zip(("p10", "p50", "p90"), estimates, confidence.T):
                    row[f"{column}_mw"] = estimate
                    row[f"{column}_ci_low_mw"] = low
                    row[f"{column}_ci_high_mw"] = high
                rows.append(row)
    return pd.DataFrame(rows)


def supporting_intervals(observations: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for direction in DIRECTIONS:
        fields = ["tight", "mean", "setter", "minimum_time"]
        if f"{direction}_episode_id" in observations:
            fields.append("episode_id")
        columns = {f"{direction}_{field}": field for field in fields}
        parts.append(
            observations[["configuration", "configuration_evidenced", "delivery_period",
                          "study_day", "time", *columns, *ANALYSIS_FEATURES]]
            .rename(columns=columns).assign(direction=direction, unit="MW")
        )
    return pd.concat(parts, ignore_index=True)


def relationships(observations: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (configuration, period), cohort in observations.groupby(["configuration", "delivery_period"], sort=True):
        for direction in DIRECTIONS:
            partitions = [
                ("all_setters", "", cohort),
                *(("within_setter", setter, subset)
                  for setter, subset in cohort.groupby(f"{direction}_setter", sort=True)),
            ]
            for population, setter, subset in partitions:
                for aggregation in AGGREGATIONS:
                    target = f"{direction}_{aggregation}"
                    for feature in ANALYSIS_FEATURES:
                        matched = subset.loc[
                            np.isfinite(subset[feature]), [feature, target, "study_day"]
                        ]
                        days = matched["study_day"].nunique()
                        variable = matched[feature].nunique() > 1
                        low, high = matched[feature].quantile([0.25, 0.75])
                        # Separate the quartile groups when the feature has many ties.
                        split = variable and low < high
                        correlation = (
                            matched[feature].rank().corr(matched[target].rank())
                            if variable and matched[target].nunique() > 1 and days >= 2 else np.nan
                        )
                        contrast = (
                            matched.loc[matched[feature].ge(high), target].median()
                            - matched.loc[matched[feature].le(low), target].median()
                            if split and days >= 2 else np.nan
                        )
                        rows.append({
                            "configuration": configuration, "delivery_period": period,
                            "direction": direction, "aggregation": aggregation,
                            "population": population, "setter": setter, "feature": feature,
                            "matched_intervals": len(matched), "distinct_days": days,
                            "support": support_label(days) if days else "missing_feature",
                            "spearman_r": correlation, "high_minus_low_mw": contrast,
                            "feature_p25_mw": low, "feature_p75_mw": high,
                        })
    return pd.DataFrame(rows)


def condition_presets(observations: pd.DataFrame) -> pd.DataFrame:
    complete = observations[np.isfinite(observations[list(FEATURES)]).all(axis=1)].copy()
    load = [
        complete[f"{region}_demand"] - complete[f"{region}_wind"] - complete[f"{region}_solar"]
        for region in REGIONS
    ]
    complete["combined_residual_mw"] = sum(load)
    parts = []
    labels = ("lower_residual", "median_residual", "higher_residual")
    columns = ["configuration", "delivery_period", "time", "study_day", "combined_residual_mw", *FEATURES]
    for _, cohort in complete.groupby(["configuration", "delivery_period"], sort=True):
        residual = cohort["combined_residual_mw"]
        for label, value in zip(labels, residual.quantile([0.25, 0.50, 0.75])):
            closest = (residual - value).abs().idxmin()
            parts.append({"preset": label, **cohort.loc[closest, columns].to_dict()})
    return pd.DataFrame(parts, columns=["preset", *columns])


def run(half_hour: pd.DataFrame, output_dir: Path) -> dict[str, Path]:
    """Generate CSV assumptions and a portable scenario tool from the same observations."""
    observations = prepare_observations(half_hour)
    output_dir = Path(output_dir)
    downloads = output_dir / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    eligible = observations[observations["configuration_evidenced"]]
    presets = condition_presets(eligible)
    lookups = {
        "conditional_limits": limits_lookup(eligible),
        "conditional_support": supporting_intervals(observations),
        "conditional_relationships": relationships(eligible),
        "condition_presets": presets,
    }
    paths = {name: downloads / f"{name}.csv" for name in lookups}
    for name, frame in lookups.items():
        frame.to_csv(paths[name], index=False, date_format="%Y-%m-%d %H:%M")
    paths["scenario"] = output_dir / "scenario.html"
    paths["scenario"].write_text(render_scenario(
        observations, presets, FEATURES, DIRECTIONS, AGGREGATIONS,
        PERIODS, BOOTSTRAP_REPLICATES, CALIPER_FLOOR_MW,
    ), encoding="utf-8")
    return paths
