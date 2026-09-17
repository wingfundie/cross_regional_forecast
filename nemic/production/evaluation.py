"""Outcome attachment and comparable connector/target/horizon scorecards."""
import numpy as np
import pandas as pd

from .training import metrics


def attach_actuals(forecasts, actuals):
    keys = ["connector", "target", "delivery"]
    if actuals.duplicated(keys).any():
        raise ValueError("Actual outcomes must be unique by connector/target/delivery")
    return forecasts.merge(actuals[keys + ["actual"]], on=keys, how="left", validate="many_to_one")


def scorecard(frame):
    f = frame.copy()
    f["horizon"] = pd.cut(f.lead, [0, 12, 48, 144, 336, 672, 1440], labels=["0–6h", "6–24h", "1–3d", "3–7d", "7–14d", "14–30d"])
    delivery = pd.to_datetime(f.delivery, utc=True).dt.tz_convert("Australia/Brisbane")
    hour = delivery.dt.hour + delivery.dt.minute / 60
    f["period"] = pd.cut(hour, [0, 6, 10, 16, 21, 24], right=False, labels=["overnight", "morning", "solar", "evening", "late"])
    rows = []
    keys = ["connector", "target", "model", "horizon", "period"]
    for key, group in f.groupby(keys, observed=True, dropna=False):
        valid = group.status.eq("complete") & group.actual.notna() & group.forecast_mw.notna()
        g = group[valid]
        row = {**dict(zip(keys, key)), **metrics(g.actual, g.forecast_mw), "requested": len(group), "unscored": int((~valid).sum())}
        for lower, upper, label in (("p10_mw", "p90_mw", "coverage_80"), ("p02_5_mw", "p97_5_mw", "coverage_95")):
            if lower in g and upper in g:
                eligible = g[[lower, upper]].notna().all(axis=1)
                row[label] = float(((g.loc[eligible, "actual"] >= g.loc[eligible, lower]) & (g.loc[eligible, "actual"] <= g.loc[eligible, upper])).mean()) if eligible.any() else None
        rows.append(row)
    return pd.DataFrame(rows)
