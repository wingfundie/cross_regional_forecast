"""Outcome attachment and comparable connector/target/horizon scorecards."""
import numpy as np
import pandas as pd

from .training import metrics


def attach_actuals(forecasts, actuals, as_of=None):
    keys = ["connector", "target", "delivery"]
    a = actuals.copy()
    if "received" in a:
        a["received"] = pd.to_datetime(a.received, utc=True)
        if as_of is not None:
            cutoff = pd.Timestamp(as_of)
            if cutoff.tzinfo is None:
                raise ValueError("Outcome as-of cutoff must be timezone aware")
            a = a[a.received <= cutoff.tz_convert("UTC")]
        a = a.sort_values("received").drop_duplicates(keys, keep="last")
    elif a.duplicated(keys).any():
        raise ValueError("Actual outcomes must be unique by connector/target/delivery")
    columns = keys + [column for column in ("actual", "received", "revision_id", "availability_evidence") if column in a]
    return forecasts.merge(a[columns], on=keys, how="left", validate="many_to_one", suffixes=("", "_actual"))


def scorecard(frame):
    f = frame.copy()
    f["horizon"] = pd.cut(
        f.lead,
        [0, 12, 48, 144, 336, 672, 1440, 2880, 4320],
        labels=["0–6h", "6–24h", "1–3d", "3–7d", "7–14d", "14–30d", "31–60d", "61–90d"],
    )
    delivery = pd.to_datetime(f.delivery, utc=True).dt.tz_convert("Australia/Brisbane")
    hour = delivery.dt.hour + delivery.dt.minute / 60
    f["period"] = pd.cut(hour, [0, 6, 10, 16, 21, 24], right=False, labels=["overnight", "morning", "solar", "evening", "late"])
    rows = []
    keys = ["connector", "target", "model", "horizon", "period"]
    for key, group in f.groupby(keys, observed=True, dropna=False):
        valid = group.status.eq("complete") & group.actual.notna() & group.forecast_mw.notna()
        g = group[valid]
        row = {**dict(zip(keys, key)), **metrics(g.actual, g.forecast_mw), "requested": len(group), "unscored": int((~valid).sum())}
        if "baseline_mw" in g and g.baseline_mw.notna().any():
            paired = g.actual.notna() & g.forecast_mw.notna() & g.baseline_mw.notna()
            model_mae = float((g.loc[paired, "actual"] - g.loc[paired, "forecast_mw"]).abs().mean()) if paired.any() else None
            baseline_mae = float((g.loc[paired, "actual"] - g.loc[paired, "baseline_mw"]).abs().mean()) if paired.any() else None
            row["baseline_mae"] = baseline_mae
            row["skill_vs_baseline"] = 1 - model_mae / baseline_mae if baseline_mae and model_mae is not None else None
        for lower, upper, label in (("p10_mw", "p90_mw", "coverage_80"), ("p02_5_mw", "p97_5_mw", "coverage_95")):
            if lower in g and upper in g:
                eligible = g[[lower, upper]].notna().all(axis=1)
                row[label] = float(((g.loc[eligible, "actual"] >= g.loc[eligible, lower]) & (g.loc[eligible, "actual"] <= g.loc[eligible, upper])).mean()) if eligible.any() else None
                row[label.replace("coverage", "width")] = float((g.loc[eligible, upper] - g.loc[eligible, lower]).mean()) if eligible.any() else None
        c80, c95 = row.get("coverage_80"), row.get("coverage_95")
        row["calibration_status"] = "calibrated" if c80 is not None and c95 is not None and c80 >= .77 and c95 >= .92 else "experimental"
        rows.append(row)
    return pd.DataFrame(rows)
