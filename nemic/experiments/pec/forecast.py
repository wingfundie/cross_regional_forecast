"""Issue-time replay of directional-limit forecasts on a fixed NEM clock."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import json

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor

from .issued import (
    DIRECTIONS, NEM, PRODUCT_FEATURES, START, VINTAGE_FEATURES, audit_archived_timestamps, read_sources, schedule,
)

BANDS = {"intraday": 6, "6-24h": 24, "day 2-3": 72, "day 4-7": 168}
HORIZONS = {"daily_0800": 168, "updates": 6}
THRESHOLD_HISTORY_DAYS = 14
FOLD_DAYS = 7
TARGETS = {f"{direction}_{aggregation}": (direction, aggregation)
           for direction in DIRECTIONS for aggregation in ("tight", "mean")}
STATE = [f"known_{target}" for target in TARGETS]
CHALLENGERS = {
    "regional_forecast": STATE + VINTAGE_FEATURES + ["delivery_slot", "lead_hours"],
    "regional_plus_constraints": STATE + VINTAGE_FEATURES + ["delivery_slot", "lead_hours"] + PRODUCT_FEATURES,
}
MODELS = ("persistence", "delivery_period", "aemo", *CHALLENGERS)
PRODUCT_MAX_AGE = {"predispatch": 1.5, "stpasa": 3, "predispatch_proxy": 1.5}
ARCHIVE_PROXY_LAG_MINUTES = 35
SCORE_COLUMNS = [
    "schedule", "lead_band", "stratum", "stratum_value", "cohort", "model",
    "direction", "aggregation", "n", "days", "mae_mw", "bias_mw", "skill_vs_persistence",
    "skill_vs_delivery_period", "skill_vs_aemo", "interval_n", "interval_coverage",
    "interval_width_mw", "event_n", "misses", "false_alerts", "precision", "recall",
]


def _delivery_period(times):
    midpoint = times - pd.Timedelta(minutes=15)
    hours = midpoint.dt.hour
    return np.select(
        [hours.between(6, 8), hours.between(9, 15), hours.between(16, 20)],
        ["morning", "solar", "evening"], default="overnight",
    )


def _tag_delivery(frame):
    frame["delivery_period"] = _delivery_period(frame["time"])
    frame["delivery_day"] = (frame["time"] - pd.Timedelta(minutes=1)).dt.normalize()
    frame["delivery_slot"] = (frame["time"].dt.hour * 2 + frame["time"].dt.minute // 30) % 48
    month = frame["delivery_day"].dt.month
    frame["season"] = np.select(
        [month.isin([12, 1, 2]), month.isin([3, 4, 5]), month.isin([6, 7, 8])],
        ["summer", "autumn", "winter"], default="spring",
    )
    return frame


def _origins(halfhour, start, end):
    history = halfhour.copy().sort_values("time")
    for column in ["time", "published_at"]:
        history[column] = pd.to_datetime(history[column]).astype("datetime64[ns]")
    history = _tag_delivery(history)
    history["usable_at"] = history["published_at"].clip(lower=history["time"] + pd.Timedelta(minutes=30))
    origin_list = schedule(start, end)
    schedule_rows = []
    for name, origins in origin_list.items():
        source = history[["time", "usable_at", *TARGETS]].dropna(subset=["usable_at"]).sort_values("usable_at")
        anchor = pd.merge_asof(
            pd.DataFrame({"origin": origins}), source, left_on="origin", right_on="usable_at", direction="backward",
        ).rename(columns={"time": "anchor_time", **{target: f"known_{target}" for target in TARGETS}})
        stale = anchor["origin"] - anchor["anchor_time"] > pd.Timedelta(hours=2)
        anchor.loc[stale, STATE] = np.nan
        lead = np.arange(0.5, HORIZONS[name] + 0.1, 0.5)
        grid = anchor.loc[anchor.index.repeat(len(lead))].reset_index(drop=True)
        grid["lead_hours"] = np.tile(lead, len(origins))
        grid["time"] = grid["origin"] + pd.to_timedelta(grid["lead_hours"], unit="h")
        grid["schedule"] = name
        schedule_rows.append(grid)
    grid = pd.concat(schedule_rows, ignore_index=True).merge(
        history[["time", "configuration", "published_at", *TARGETS]], on="time", how="left",
        validate="many_to_one",
    )
    grid["lead_band"] = pd.cut(
        grid["lead_hours"], bins=[0, *BANDS.values()], labels=list(BANDS), ordered=True,
    ).astype("string")
    grid["origin_day"] = grid["origin"].dt.normalize()
    return _tag_delivery(grid), history


def gate_vintages(grid, vintages, product):
    """Select one whole published vintage per origin, then join by delivery."""
    candidates = vintages[vintages["product"].eq(product)].copy()
    if candidates.empty:
        return pd.DataFrame(index=grid.index)
    for column in ["time", "issued_at", "published_at"]:
        candidates[column] = pd.to_datetime(candidates[column]).astype("datetime64[ns]")
    metadata = candidates[["vintage", "issued_at", "published_at", "source_sha256"]].drop_duplicates()
    if metadata.duplicated("vintage").any():
        raise ValueError("A forecast vintage has conflicting timestamp or hash evidence")
    trustworthy = metadata["issued_at"].notna() & metadata["published_at"].notna()
    metadata = metadata[trustworthy & metadata["issued_at"].le(metadata["published_at"])]
    metadata = metadata.sort_values(["published_at", "issued_at", "vintage"])
    origins = pd.DataFrame({"origin": grid["origin"].drop_duplicates().sort_values()})
    matched = pd.merge_asof(
        origins, metadata, left_on="origin", right_on="published_at", direction="backward",
        tolerance=pd.Timedelta(hours=PRODUCT_MAX_AGE[product]),
    )
    metadata_columns = ["issued_at", "published_at", "source_sha256"]
    delivery = candidates.drop(columns=["product", *metadata_columns])
    if delivery.duplicated(["vintage", "time"]).any():
        raise ValueError("A forecast vintage has duplicate regional delivery rows")
    paired = (grid[["origin", "time"]].merge(matched, on="origin", how="left", validate="many_to_one")
              .merge(delivery, on=["vintage", "time"], how="left", validate="many_to_one"))
    paired["age_hours"] = (paired["origin"] - paired["issued_at"]).dt.total_seconds() / 3600
    stale = paired["age_hours"].gt(PRODUCT_MAX_AGE[product])
    if stale.any():
        paired.loc[stale, [column for column in paired.columns if column not in ["origin", "time"]]] = np.nan
    paired.index = grid.index
    return paired.drop(columns=["origin", "time"])


def _add_baselines(grid, history):
    chronological = history.dropna(subset=["published_at"])
    for target in TARGETS:
        grid[f"persistence_{target}"] = grid[f"known_{target}"]
        grid[f"delivery_period_{target}"] = np.nan
    for issue_day, index in grid.groupby("origin_day", sort=True).groups.items():
        eligible = chronological[(chronological["time"] < issue_day) & (chronological["published_at"] <= issue_day)]
        medians = eligible.groupby("delivery_slot")[list(TARGETS)].median()
        prior_days = eligible.groupby("delivery_slot")["delivery_day"].nunique()
        medians = medians.loc[prior_days.ge(2)]
        for target in TARGETS:
            grid.loc[index, f"delivery_period_{target}"] = grid.loc[index, "delivery_slot"].map(medians[target])


def _thresholds(history, freeze):
    past = history[(history["time"] < freeze) & (history["published_at"] <= freeze)]
    rows = []
    for target, (direction, aggregation) in TARGETS.items():
        for period, group in past.groupby("delivery_period", sort=True):
            values = group.dropna(subset=[target])
            days = values["delivery_day"].nunique()
            rows.append({
                "target": target, "direction": direction, "aggregation": aggregation,
                "delivery_period": period, "threshold_mw": values[target].quantile(.1) if days >= 7 else np.nan,
                "n": len(values), "days": days, "history_end": freeze,
            })
    return pd.DataFrame(rows, columns=[
        "target", "direction", "aggregation", "delivery_period", "threshold_mw", "n", "days", "history_end",
    ])


def _eligible_training(rows, cutoff, upper):
    complete = rows["origin"] + pd.Timedelta(hours=upper) <= cutoff
    return rows[complete & rows["published_at"].le(cutoff)]


def _enough(rows, days, samples):
    return len(rows) >= samples and rows["origin_day"].nunique() >= days


def _model_inputs(rows, features):
    matrix = rows[features].copy()
    # Presence of a predicted RHS is information. Missing coefficients use
    # a separate indicator so an absent RHS is distinguishable from zero.
    for column in features:
        if column in PRODUCT_FEATURES:
            matrix[f"{column}_present"] = matrix[column].notna().astype(float)
    return matrix.fillna(0).to_numpy()


def _split(rows, fold, upper):
    margin = pd.Timedelta(hours=upper)
    calibration_end = fold - margin
    calibration_start = calibration_end - pd.Timedelta(days=6)
    selection_end = calibration_start - margin
    selection_start = selection_end - pd.Timedelta(days=4)
    train = _eligible_training(rows, selection_start, upper)
    select = _eligible_training(rows[rows["origin"] >= selection_start], calibration_start, upper)
    calibrate = _eligible_training(rows[rows["origin"] >= calibration_start], fold, upper)
    if _enough(train, 5, 100) and _enough(select, 3, 60) and _enough(calibrate, 5, 100):
        return train, select, calibrate

    selection_start = fold - margin - pd.Timedelta(days=4)
    train = _eligible_training(rows, selection_start, upper)
    select = _eligible_training(rows[rows["origin"] >= selection_start], fold, upper)
    return train, select, calibrate.iloc[:0]


def _fit(rows, freeze, label):
    for model in CHALLENGERS:
        for target in TARGETS:
            rows[f"{model}_{target}"] = np.nan
    output = []
    fields = [*VINTAGE_FEATURES, *STATE]
    has_rhs = rows[PRODUCT_FEATURES].notna().any(axis=1)
    comparable = rows[rows[fields].notna().all(axis=1) & has_rhs]
    for (name, band), group in comparable.groupby(["schedule", "lead_band"], sort=True, observed=True):
        upper = BANDS[band]
        active = group.loc[group["origin"] >= freeze]
        if active.empty:
            continue
        history = group.dropna(subset=list(TARGETS))
        for fold in pd.date_range(freeze, active["origin"].max(), freq=f"{FOLD_DAYS}D"):
            requested = active[active["origin"].ge(fold) & active["origin"].lt(fold + pd.Timedelta(days=FOLD_DAYS))]
            if requested.empty:
                continue
            train, select, calibrate = _split(history, fold, upper)
            if not (_enough(train, 5, 100) and _enough(select, 3, 60)):
                output.append({
                    "product": label, "schedule": name, "lead_band": band, "evaluation_start": fold,
                    "train": len(train), "selection": len(select), "calibration": len(calibrate),
                    "evaluation": len(requested), "status": "insufficient earlier purged train or selection history",
                })
                continue
            model_cols = list(TARGETS)
            for model, features in CHALLENGERS.items():
                fit_x = _model_inputs(train, features)
                select_x = _model_inputs(select, features)
                validation = []
                for depth in (3, 5):
                    estimator = DecisionTreeRegressor(
                        max_depth=depth, min_samples_leaf=20, random_state=42,
                    ).fit(fit_x, train[model_cols])
                    validation.append(np.abs(
                        estimator.predict(select_x) - select[model_cols].to_numpy()
                    ).mean(axis=0))
                errors = np.asarray(validation)
                selection = errors.argmin(axis=0)
                refit = pd.concat([train, select])
                requested_x = _model_inputs(requested, features)
                for candidate in np.unique(selection):
                    depth = (3, 5)[candidate]
                    estimator = DecisionTreeRegressor(
                        max_depth=depth, min_samples_leaf=20, random_state=42,
                    ).fit(_model_inputs(refit, features), refit[model_cols])
                    predictions = estimator.predict(requested_x)
                    radius = np.full(len(model_cols), np.nan)
                    if not calibrate.empty:
                        residual = np.abs(estimator.predict(_model_inputs(calibrate, features))
                                          - calibrate[model_cols].to_numpy())
                        radius = np.quantile(residual, .8, axis=0, method="higher")
                    for index in np.flatnonzero(selection == candidate):
                        target = model_cols[index]
                        direction, aggregation = TARGETS[target]
                        rows.loc[requested.index, f"{model}_{target}"] = predictions[:, index]
                        rows.loc[requested.index, f"{model}_{target}_radius"] = radius[index]
                        output.append({
                            "product": label, "schedule": name, "lead_band": band, "evaluation_start": fold,
                            "model": model, "direction": direction, "aggregation": aggregation, "depth": depth,
                            "train": len(train), "selection": len(select), "calibration": len(calibrate),
                            "evaluation": len(requested), "train_days": train["origin_day"].nunique(),
                            "selection_days": select["origin_day"].nunique(),
                            "calibration_days": calibrate["origin_day"].nunique(),
                            "validation_mae_mw": errors[candidate, index],
                            "train_last_delivery": train["time"].max(),
                            "selection_last_delivery": select["time"].max(),
                            "calibration_last_delivery": calibrate["time"].max(), "status": "scored",
                        })
    return pd.DataFrame(output)


def _baseline_intervals(frame, freeze):
    for (name, band), group in frame.groupby(["schedule", "lead_band"], sort=True, observed=True):
        for fold in pd.date_range(freeze, group["origin"].max(), freq=f"{FOLD_DAYS}D"):
            prior = _eligible_training(group, fold, BANDS[band])
            if prior.empty:
                continue
            recent = prior[prior["origin"] >= prior["origin"].max() - pd.Timedelta(days=7)]
            target_rows = group[group["origin"].ge(fold) & group["origin"].lt(fold + pd.Timedelta(days=FOLD_DAYS))]
            for model in ("persistence", "delivery_period"):
                for target in TARGETS:
                    error = (recent[f"{model}_{target}"] - recent[target]).abs().dropna()
                    if len(error) < 100 or recent.loc[error.index, "origin_day"].nunique() < 5:
                        continue
                    frame.loc[target_rows.index, f"{model}_{target}_radius"] = error.quantile(.8, interpolation="higher")


def _ratio(num, denom):
    return float(num / denom) if denom else np.nan


def _skill(mae, baseline):
    return float(1 - mae / baseline) if np.isfinite(baseline) and baseline else np.nan


def _score_group(group, target, model, thresholds):
    value = group[target]
    forecast = group[f"{model}_{target}"]
    error = forecast - value
    mae = error.abs().mean()
    radius = group.get(f"{model}_{target}_radius", pd.Series(np.nan, index=group.index)).dropna()
    marked = group["delivery_period"].map(thresholds).dropna()
    actual_events = value.loc[marked.index].le(marked)
    alarms = forecast.loc[marked.index].le(marked)
    hits = (actual_events & alarms).sum()
    persistence = (group[f"persistence_{target}"] - value).abs().mean()
    seasonal = (group[f"delivery_period_{target}"] - value).abs().mean()
    aemo = (group.get(f"aemo_{target}", pd.Series(np.nan, index=group.index)) - value).abs().mean()
    return {
        "n": int(len(group)), "days": int(group["delivery_day"].nunique()), "mae_mw": mae, "bias_mw": error.mean(),
        "skill_vs_persistence": _skill(mae, persistence), "skill_vs_delivery_period": _skill(mae, seasonal),
        "skill_vs_aemo": _skill(mae, aemo), "interval_n": len(radius),
        "interval_coverage": (error.loc[radius.index].abs().le(radius)).mean() if len(radius) else np.nan,
        "interval_width_mw": 2 * radius.mean() if len(radius) else np.nan,
        "event_n": len(marked), "misses": int((actual_events & ~alarms).sum()) if len(marked) else np.nan,
        "false_alerts": int((~actual_events & alarms).sum()) if len(marked) else np.nan,
        "precision": _ratio(hits, alarms.sum()), "recall": _ratio(hits, actual_events.sum()),
    }


def _score(frame, cohorts, thresholds):
    scores = []
    for cohort, models in cohorts.items():
        for target, (direction, aggregation) in TARGETS.items():
            cutoff = thresholds[thresholds["target"].eq(target)].set_index("delivery_period")["threshold_mw"]
            matched = frame.dropna(subset=[target, *(f"{model}_{target}" for model in models)])
            for stratum in ("all", "configuration", "delivery_period", "season"):
                grouping = ["schedule", "lead_band"]
                if stratum != "all":
                    grouping.append(stratum)
                for key, group in matched.groupby(grouping, observed=True, dropna=False, sort=True):
                    for model in models:
                        scores.append({
                            "schedule": key[0], "lead_band": key[1], "stratum": stratum,
                            "stratum_value": key[2] if len(key) > 2 else "all", "cohort": cohort, "model": model,
                            "direction": direction, "aggregation": aggregation, **_score_group(group, target, model, cutoff),
                        })
    return scores


def _coverage(frame, label, flags, end, freeze):
    rows = []
    for (name, band), group in frame.groupby(["schedule", "lead_band"], observed=True, sort=True):
        evaluable = group["origin"].ge(freeze) & group["time"].le(end)
        for stage, mask in flags.items():
            passing = group[mask.loc[group.index]]
            rows.append({
                "schedule": name, "lead_band": band, "cohort": label, "stage": stage,
                "n": len(passing), "origins": passing["origin"].nunique(), "days": passing["delivery_day"].nunique(),
                "scheduled": len(group), "due": int(group["time"].le(end).sum()),
                "evaluation_due": int(evaluable.sum()),
                "observed": int(group.loc[evaluable, list(TARGETS)].notna().all(axis=1).sum()),
            })
    return rows


def run(half_hour, data_dir, downloads_dir, *, start=START, end=None):
    """Write the available baseline, matched benchmark and challenger evidence."""
    data_dir = Path(data_dir)
    downloads_dir = Path(downloads_dir)
    downloads_dir.mkdir(parents=True, exist_ok=True)
    start = pd.Timestamp(start)
    end = pd.Timestamp(end or datetime.now(NEM).date())
    freeze = start + pd.Timedelta(days=THRESHOLD_HISTORY_DAYS)
    grid, history = _origins(half_hour, start, end)
    _add_baselines(grid, history)
    _baseline_intervals(grid, freeze)
    thresholds = _thresholds(history, freeze)
    thresholds.to_csv(downloads_dir / "restriction_thresholds.csv", index=False)
    evaluated = grid["origin"].ge(freeze) & grid["time"].le(end)
    matured = grid[list(TARGETS)].notna().all(axis=1)
    baseline_models = ("persistence", "delivery_period")
    all_scores = _score(grid.loc[evaluated], {"historical_baselines": baseline_models}, thresholds)
    print(f"Built {len(grid):,} scheduled origin and delivery pairs for both outlook schedules", flush=True)
    coverage = _coverage(grid, "historical_baselines", {
        "scheduled": pd.Series(True, index=grid.index),
        "pending_delivery": grid["time"].gt(end),
        "missing_observation": grid["time"].le(end) & ~matured,
        "pre_evaluation": grid["origin"].lt(freeze),
        "missing_persistence_or_delivery_period": evaluated & matured & grid[
            [f"{model}_{target}" for model in baseline_models for target in TARGETS]].isna().any(axis=1),
        "observed_evaluation": evaluated & matured,
    }, end, freeze)
    vintages, source_table = read_sources(data_dir / "issued")
    if source_table.empty:
        source_table = pd.DataFrame(columns=[
            "product", "vintage", "url", "published_at", "issued_at", "sha256",
        ])
    proxy = source_table["product"].eq("predispatch_proxy")
    if proxy.any():
        proxy_times = pd.to_datetime(source_table.loc[proxy, "archive_member_time"]) + pd.Timedelta(
            minutes=ARCHIVE_PROXY_LAG_MINUTES
        )
        source_table.loc[proxy, "published_at"] = proxy_times.dt.strftime("%Y-%m-%dT%H:%M:%S")
        source_table.loc[proxy, "listing_publication_precision"] = (
            f"proxy from archive member mtime plus {ARCHIVE_PROXY_LAG_MINUTES} minutes"
        )
        vintages["published_at"] = pd.to_datetime(vintages["published_at"]).astype("datetime64[ns]")
        proxy_values = vintages["product"].eq("predispatch_proxy")
        proxy_index = pd.Series(proxy_times.to_numpy(), index=source_table.loc[proxy, "vintage"])
        vintages.loc[proxy_values, "published_at"] = vintages.loc[proxy_values, "vintage"].map(proxy_index)
    source_table.to_csv(downloads_dir / "forecast_sources.csv", index=False)
    archive_audit = audit_archived_timestamps(data_dir / "issued", source_table).reindex(columns=[
        "archive", "archive_sha256", "vintage", "archive_member_time_nem", "published_http_last_modified_nem",
        "publisher_lag_seconds", "same_archive_and_current_bytes",
    ])
    archive_audit.to_csv(downloads_dir / "forecast_publication_audit.csv", index=False)
    partitions = []
    vintage_matches = []
    source_keys = ["product", "schedule", "origin", "vintage", "issued_at", "product_published_at",
                   "age_hours", "source_sha256"]
    for product in PRODUCT_MAX_AGE:
        subset = grid.loc[grid["schedule"].eq("daily_0800")] if product == "stpasa" else grid
        if vintages.empty:
            variant = subset.copy()
        else:
            inputs = gate_vintages(subset, vintages, product).rename(columns={"published_at": "product_published_at"})
            variant = subset.join(inputs)
        for name in [*DIRECTIONS, *PRODUCT_FEATURES, *VINTAGE_FEATURES, "vintage"]:
            if name not in variant:
                variant[name] = np.nan
        for target, (direction, _) in TARGETS.items():
            variant[f"aemo_{target}"] = variant[direction]
        proxy = product.endswith("_proxy")
        label = "archive_predispatch_proxy" if proxy else f"verified_{product}"
        cohorts = {label: (*baseline_models, "aemo")}
        if not proxy:
            folds = _fit(variant, freeze, product)
            partitions.append(folds)
            cohorts[f"matched_challengers_{product}"] = (*baseline_models, "aemo", *CHALLENGERS)
        out = variant[variant["origin"].ge(freeze) & variant["time"].le(end)].copy()
        all_scores.extend(_score(out, cohorts, thresholds))
        eligible = evaluated.loc[variant.index] & matured.loc[variant.index]
        coherent = variant[VINTAGE_FEATURES].notna().all(axis=1)
        benchmarks = variant[list(DIRECTIONS)].notna().all(axis=1)
        challenger_columns = [f"{model}_{target}" for model in CHALLENGERS for target in TARGETS]
        challengers = variant.reindex(columns=challenger_columns).notna().all(axis=1)
        print(f"{product}: {int((eligible & benchmarks).sum()):,} AEMO comparisons and "
              f"{int((eligible & benchmarks & coherent & challengers).sum()):,} common challenger pairs", flush=True)
        available_label = "proxy_vintage_available" if proxy else "published_vintage_available"
        missing_label = "missing_proxy_vintage" if proxy else "missing_published_vintage"
        coverage.extend(_coverage(variant, label, {
            "observed_evaluation": eligible,
            available_label: eligible & variant["vintage"].notna(),
            missing_label: eligible & variant["vintage"].isna(),
            "same_vintage_regional_forecasts": eligible & coherent,
            "aemo_directional_values": eligible & benchmarks,
            "eligible_challenger_evaluation": eligible & benchmarks & coherent & challengers,
            "missing_product_delivery": eligible & variant["vintage"].notna() & ~benchmarks,
        }, end, freeze))
        if {"issued_at", "product_published_at", "age_hours", "source_sha256"}.issubset(variant.columns):
            linked = variant[variant["vintage"].notna() & (benchmarks | coherent)].copy()
            linked["product"] = product
            vintage_matches.append(linked.groupby(source_keys, as_index=False).agg(
                first_delivery=("time", "min"), last_delivery=("time", "max"), delivery_rows=("time", "size"),
            ))
        # Retain a row-level audit locally. Join its vintage to forecast_sources.csv for archive provenance.
        keep = ["origin", "time", "schedule", "lead_hours", "lead_band", "configuration", "anchor_time",
                "vintage", "issued_at", "product_published_at", "age_hours", "source_sha256",
                "predicted_export_setter", "predicted_import_setter", *VINTAGE_FEATURES, *PRODUCT_FEATURES,
                *TARGETS, *[f"{model}_{target}" for model in MODELS for target in TARGETS],
                *[f"{model}_{target}_radius" for model in MODELS for target in TARGETS]]
        variant.reindex(columns=keep).to_parquet(data_dir / f"forecast_rows_{product}.parquet", index=False)
    pd.DataFrame(all_scores, columns=SCORE_COLUMNS).to_csv(downloads_dir / "forecast_scores.csv", index=False)
    coverage = pd.DataFrame(coverage)
    coverage.to_csv(downloads_dir / "forecast_coverage.csv", index=False)
    matches = pd.concat(vintage_matches, ignore_index=True) if vintage_matches else pd.DataFrame(
        columns=[*source_keys, "first_delivery", "last_delivery", "delivery_rows"]
    )
    matches.to_csv(downloads_dir / "forecast_vintage_matches.csv", index=False)
    splits = pd.concat(partitions, ignore_index=True) if partitions else pd.DataFrame()
    if splits.empty:
        splits = pd.DataFrame(columns=["product", "schedule", "lead_band", "evaluation_start", "status"])
    splits.to_csv(downloads_dir / "forecast_partitions.csv", index=False)
    protocol = {
        "first_requested_origin_nem": str(start), "delivery_cutoff_nem": str(end),
        "evaluation_start_nem": str(freeze), "timezone": "UTC+10 fixed",
        "schedules": {"daily_0800": "Every day at 08:00 for each following half-hour through 168h",
                      "updates": "Every half-hour for each following half-hour through 6h"},
        "lead_bins_end_hours": BANDS,
        "persistence": "Latest published complete half-hour, at least 30 minutes old and at most 2 hours old.",
        "delivery_period": "Median of earlier published observations by exact half-hour of delivery. Refit each midnight with at least two distinct days.",
        "forecast_products": {
            "predispatch": "AEMO PredispatchIS non-intervention dispatch snapshot. Its single directional value is compared with each aggregation separately.",
            "stpasa": "AEMO ST PASA LOR adequacy scenario. Use the NSW and SA importing-region studies for their respective directions. Compare scenario bounds with subsequent dispatch limits as a product benchmark.",
            "predispatch_proxy": (
                f"Older original issues use the archive member timestamp plus {ARCHIVE_PROXY_LAG_MINUTES} minutes, "
                "above the largest lag measured in the overlap audit. Historical publication remains unverified."
            ),
        },
        "publication": "Use original publisher directory timestamps, conservatively rounded to the end of the displayed NEM minute, and corroborate against HTTP Last-Modified. Original report creation also precedes origin.",
        "archive_publication_audit": {
            "overlap": len(archive_audit),
            "longest_publisher_lag_seconds": None if archive_audit.empty else
            float(archive_audit["publisher_lag_seconds"].max()),
            "exact_byte_matches": 0 if archive_audit.empty else int(archive_audit["same_archive_and_current_bytes"].sum()),
        },
        "vintage_coherence": "Each regional row uses three regions from one original report, product, run type and delivery interval.",
        "model_features": "Known state is the lagged, published signed directional envelope. Both challengers use regional demand, wind and solar forecasts. The constraint challenger adds AEMO predicted binding count and published RHS and binding indicators at the predicted setters. Actual delivery configurations are used for score breakdowns.",
        "model_selection": "Seven-day expanding origin blocks. Select depth 3 or 5 by direction and aggregation within each lead band using MAE on a four-day prior origin block. Refit with the eligible training and selection rows.",
        "purge": "Separate training, selection, calibration and evaluation using each evaluated lead band's full upper window and confirmed observation publication.",
        "minimum_model_support": "Training requires 100 pairs across five origin days. Selection requires 60 pairs across three origin days. Calibration requires 100 pairs across five origin days and a separate earlier block.",
        "interval": "Central nominal 80 percent via separate empirical absolute residual radius. Coverage and width use the available interval rows. Matched AEMO point forecasts carry no interval.",
        "event": "Below or equal to the frozen pre-evaluation P10 for the same direction, aggregation and delivery period. Thresholds require seven distinct supporting days.",
        "skill": "1 minus the ratio of MAE to baseline MAE on the exact cohort. Zero denominator leaves skill undefined.",
        "target": "Signed AEMO dispatch-solution limits in MW. Point bias is forecast minus observed.",
        "sources": int(len(source_table)), "scheduled_pairs": int(len(grid)), "score_rows": int(len(all_scores)),
    }
    (downloads_dir / "forecast_protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    return protocol


def verify_evidence(data_dir, downloads_dir):
    """Recalculate the unstratified scores and confirm as-of metadata from exports."""
    data_dir, downloads_dir = Path(data_dir), Path(downloads_dir)
    protocol = json.loads((downloads_dir / "forecast_protocol.json").read_text(encoding="utf-8"))
    freeze = pd.Timestamp(protocol["evaluation_start_nem"])
    end = pd.Timestamp(protocol["delivery_cutoff_nem"])
    scores = pd.read_csv(downloads_dir / "forecast_scores.csv")
    overall = scores[scores["stratum"].eq("all")]
    sources = pd.read_csv(downloads_dir / "forecast_sources.csv", dtype={"sha256": str})
    cohorts = {
        "predispatch": ("historical_baselines", "verified_predispatch", "matched_challengers_predispatch"),
        "stpasa": ("verified_stpasa", "matched_challengers_stpasa"),
        "predispatch_proxy": ("archive_predispatch_proxy",),
    }
    metrics = 0
    for product, names in cohorts.items():
        path = data_dir / f"forecast_rows_{product}.parquet"
        if not path.exists():
            assert not overall["cohort"].isin(names).any()
            continue
        audit = pd.read_parquet(path)
        assert audit["origin"].lt(end).all()
        assert audit["time"].gt(audit["origin"]).all()
        anchor = audit.dropna(subset=["anchor_time"])
        assert (anchor["origin"] - anchor["anchor_time"]).ge(pd.Timedelta(minutes=30)).all()
        if not audit["vintage"].isna().all():
            issued = audit[audit["vintage"].notna()]
            assert issued["issued_at"].le(issued["product_published_at"]).all()
            assert issued["product_published_at"].le(issued["origin"]).all()
            assert issued["age_hours"].between(0, PRODUCT_MAX_AGE[product]).all()
            assert issued.groupby("origin")["vintage"].nunique().eq(1).all()
            reference = sources[sources["product"].eq(product)].set_index("vintage")["sha256"]
            assert issued["vintage"].map(reference).eq(issued["source_sha256"]).all()
        out = audit[audit["origin"].ge(freeze) & audit["time"].le(end)]
        grouping = ["schedule", "lead_band", "cohort", "direction", "aggregation"]
        for key, group in overall[overall["cohort"].isin(names)].groupby(grouping):
            schedule_name, band, _, direction, aggregation = key
            target = f"{direction}_{aggregation}"
            model_columns = [f"{model}_{target}" for model in group["model"]]
            matched = out.loc[out["schedule"].eq(schedule_name) & out["lead_band"].eq(band)]
            matched = matched.dropna(subset=[target, *model_columns])
            for row in group.itertuples(index=False):
                error = matched[f"{row.model}_{target}"] - matched[target]
                radius = matched[f"{row.model}_{target}_radius"].dropna()
                assert len(error) == row.n and len(radius) == row.interval_n
                assert np.isclose(error.abs().mean(), row.mae_mw) and np.isclose(error.mean(), row.bias_mw)
                if len(radius):
                    assert np.isclose(2 * radius.mean(), row.interval_width_mw)
                    assert np.isclose(error.loc[radius.index].abs().le(radius).mean(), row.interval_coverage)
                metrics += 1
    return metrics


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--downloads", type=Path, required=True)
    parser.add_argument("--end")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not args.verify:
        run(pd.read_parquet(args.data / "half_hour.parquet"), args.data, args.downloads, end=args.end)
    print(f"Recomputed {verify_evidence(args.data, args.downloads)} overall forecast score rows", flush=True)
