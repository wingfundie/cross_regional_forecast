"""Select physical solutions and form signed, interval-ending PEC targets."""

import numpy as np
import pandas as pd

from .sources import REGIONS, START

DIRECTIONS = {"nsw_sa": ("EXPORTLIMIT", "EXPORTGENCONID", 1),
              "sa_nsw": ("IMPORTLIMIT", "IMPORTGENCONID", -1)}
REGIONAL = {"demand": "TOTALDEMAND", "wind": "SS_WIND_CLEAREDMW", "solar": "SS_SOLAR_CLEAREDMW"}
REGIONAL_MW = [f"{region}_{metric}" for region in REGIONS.values() for metric in (*REGIONAL, "residual")]


def prepare(raw):
    frame = raw.copy()
    frame["time"] = pd.to_datetime(frame.SETTLEMENTDATE)
    frame["LASTCHANGED"] = pd.to_datetime(frame.LASTCHANGED)
    frame["report_created"] = pd.to_datetime(frame.report_created)
    for name in ("RUNNO", "INTERVENTION"):
        frame[name] = pd.to_numeric(frame[name], errors="raise")
    return frame


def physical(frame, key):
    return (frame.sort_values(["time", key, "INTERVENTION", "RUNNO", "LASTCHANGED", "report_created"])
            .drop_duplicates(["time", key], keep="last").reset_index(drop=True))


def calendar_days(times):
    return (times - pd.Timedelta(nanoseconds=1)).dt.normalize()


def observed_intervals(connectors, regions, end_day):
    end = end_day + pd.Timedelta(days=1)
    all_runs = prepare(connectors)
    grid_aligned = all_runs.time.eq(all_runs.time.dt.floor("5min"))
    all_runs = all_runs[all_runs.time.gt(START) & all_runs.time.le(end) & grid_aligned]
    frame = physical(all_runs, "INTERCONNECTORID")
    counts = all_runs.groupby("time").agg(
        observed_run_rows=("RUNNO", "size"), intervention_run_rows=("INTERVENTION", "sum"),
    )
    frame = frame.join(counts, on="time")
    frame["dispatch_flow_mw"] = pd.to_numeric(frame.MWFLOW)
    frame["metered_flow_mw"] = pd.to_numeric(frame.METEREDMWFLOW)
    for name, (limit, setter, sign) in DIRECTIONS.items():
        frame[f"{name}_mw"] = sign * pd.to_numeric(frame[limit])
        frame[f"{name}_setter"] = frame[setter].replace("", None)
    frame["fixed_transfer"] = np.isclose(frame.nsw_sa_mw, -frame.sa_nsw_mw, atol=0.01, rtol=0)
    frame["forced_flow"] = frame.nsw_sa_mw.lt(0) | frame.sa_nsw_mw.lt(0)
    frame["zero_limits"] = frame.nsw_sa_mw.eq(0) & frame.sa_nsw_mw.eq(0)
    frame["study_day"] = calendar_days(frame.time)
    # The observation becomes usable no earlier than delivery end or the report creation time.
    frame["published_at"] = frame[["time", "report_created"]].max(axis=1)
    regional = prepare(regions)
    # Use the same physical run selected for the interconnector, preserving missing context.
    regional = regional.merge(frame[["time", "RUNNO", "INTERVENTION"]], on=["time", "RUNNO", "INTERVENTION"], how="inner")
    regional = physical(regional, "REGIONID")
    for metric, column in REGIONAL.items():
        regional[metric] = pd.to_numeric(regional[column], errors="coerce")
    regional["residual"] = regional.demand - regional.wind - regional.solar
    wide = regional.pivot(index="time", columns="REGIONID", values=[*REGIONAL, "residual"])
    wide.columns = [f"{REGIONS[region]}_{metric}" for metric, region in wide.columns]
    return frame.merge(wide.reindex(columns=REGIONAL_MW), on="time", how="left", validate="one_to_one")


def half_hours(five):
    eligible = five.dropna(subset=["nsw_sa_mw", "sa_nsw_mw"]).copy()
    eligible["half_hour"] = eligible.time.dt.ceil("30min")
    grouped = eligible.groupby("half_hour", sort=True)
    sizes = grouped.time.nunique()
    complete = sizes[sizes.eq(6)].index
    eligible = eligible.loc[eligible.half_hour.isin(complete)]
    grouped = eligible.groupby("half_hour", sort=True)
    result = grouped.agg(
        n5=("time", "size"), study_day=("study_day", "first"), intervention=("INTERVENTION", "max"),
        published_at=("published_at", "max"), dispatch_flow_mean=("dispatch_flow_mw", "mean"),
        metered_flow_mean=("metered_flow_mw", "mean"),
    )
    all_regional = grouped[REGIONAL_MW].mean().where(grouped[REGIONAL_MW].count().eq(6))
    result = result.join(all_regional)
    configurations = grouped.configuration.agg(lambda values: " | ".join(dict.fromkeys(values)))
    result["configuration"] = configurations
    for name in DIRECTIONS:
        tight_rows = (eligible.sort_values([f"{name}_mw", "time"])
                      .drop_duplicates("half_hour").set_index("half_hour"))
        result[f"{name}_tight"] = tight_rows[f"{name}_mw"]
        result[f"{name}_mean"] = grouped[f"{name}_mw"].mean()
        result[f"{name}_minimum_time"] = tight_rows.time
        result[f"{name}_setter"] = tight_rows[f"{name}_setter"]
        if f"{name}_episode_id" in tight_rows:
            result[f"{name}_episode_id"] = tight_rows[f"{name}_episode_id"]
    result["different_minimum_times"] = result.nsw_sa_minimum_time.ne(result.sa_nsw_minimum_time)
    return result.rename_axis("time").reset_index()


def coverage(five, half, end_day):
    index = pd.date_range(START, end_day, name="study_day")
    valid = five.dropna(subset=["nsw_sa_mw", "sa_nsw_mw"])
    result = pd.DataFrame({
        "expected_five_minute": 288,
        "observed_five_minute": five.groupby("study_day").size(),
        "valid_five_minute": valid.groupby("study_day").size(),
        "expected_half_hours": 48,
        "complete_half_hours": half.groupby("study_day").size(),
        "selected_intervention_intervals": five.groupby("study_day").INTERVENTION.sum(),
        "raw_dispatch_rows": five.groupby("study_day").observed_run_rows.sum(),
        "raw_intervention_rows": five.groupby("study_day").intervention_run_rows.sum(),
        "different_minimum_times": half.groupby("study_day").different_minimum_times.sum(),
        "negative_direction_intervals": five.groupby("study_day").forced_flow.sum(),
        "nonzero_fixed_intervals": five.loc[~five.zero_limits].groupby("study_day").fixed_transfer.sum(),
        "both_zero_intervals": five.groupby("study_day").zero_limits.sum(),
    }, index=index).fillna(0).astype(int)
    result["missing_five_minute"] = result.expected_five_minute - result.observed_five_minute
    result["missing_directional_values"] = result.observed_five_minute - result.valid_five_minute
    result["incomplete_half_hours"] = result.expected_half_hours - result.complete_half_hours
    return result.reset_index()
