"""Versioned recipes. Forecast fundamentals never overwrite observed state."""
import numpy as np
import pandas as pd

from .contracts import CONNECTORS, connector
from .inputs import asof


def build(manifest, origin, delivery, name, inputs, history=None, context=None):
    origin, delivery = pd.Timestamp(origin), pd.Timestamp(delivery)
    if origin.tzinfo is None or delivery.tzinfo is None:
        raise ValueError("Origin and delivery must be timezone aware")
    origin = origin.tz_convert("Australia/Brisbane")
    delivery = delivery.tz_convert("Australia/Brisbane")
    lead = (delivery - origin).total_seconds() / 1800
    if lead != int(lead) or lead < 1:
        raise ValueError("Delivery must be a positive half-hour lead")
    if manifest["recipe"] == "legacy-vni-v1":
        raise ValueError("Legacy recipe requires prepared, target-specific feature rows")
    if manifest["recipe"] not in {"regional-v1", "calendar-v1"}:
        raise ValueError("Unknown feature recipe")
    hour = delivery.hour + delivery.minute / 60
    values = {"lead": lead, "log_lead": np.log1p(lead),
              "hour_sin": np.sin(2 * np.pi * hour / 24), "hour_cos": np.cos(2 * np.pi * hour / 24),
              "year_sin": np.sin(2 * np.pi * delivery.dayofyear / 365.25),
              "year_cos": np.cos(2 * np.pi * delivery.dayofyear / 365.25),
              "weekend": float(delivery.dayofweek >= 5)}
    context = context or {}
    if "outages" in context and "links" in context:
        from .constraints import candidates
        exposures = candidates(context["outages"], context["links"], origin, delivery, connector(name))
        values["nos_outage_count"] = float(exposures.outage_id.nunique())
        values["nos_constraint_count"] = float(exposures.constraint_id.nunique())
    # These tables must contain published or cross-fitted estimates; availability
    # filtering is identical in training and inference.
    for table_name, prefix in (("aemo", "aemo"), ("constraint_forecasts", "constraint")):
        if table_name in context:
            table = context[table_name]
            eligible = table[(table.connector == connector(name)) & (table.target == manifest["target"])
                             & (table.delivery == delivery) & (table.issue <= origin) & (table.received <= origin)]
            if len(eligible):
                row = eligible.sort_values(["issue", "received"]).iloc[-1]
                values[f"{prefix}_limit"] = float(row.value)
                if "probability" in row:
                    values[f"{prefix}_setter_probability"] = float(row.probability)
    if manifest["recipe"] == "regional-v1":
        if inputs.empty:
            raise ValueError("Regional recipe requires forecast inputs")
        selected = asof(inputs, origin, manifest.get("max_age_hours", 48))
        for side, region in zip(("source", "sink"), CONNECTORS[connector(name)][1:]):
            for variable in ("demand", "wind", "solar", "temperature"):
                records = selected[(selected.region == region) & (selected.variable == variable)
                                   & (selected.delivery >= delivery)
                                   & (selected.delivery - pd.to_timedelta(selected.interval_minutes, unit="m") < delivery)]
                source = manifest.get("sources", {}).get(variable)
                if source:
                    records = records[records.source == source]
                if records.source.nunique() > 1:
                    raise ValueError(f"Ambiguous provider for {region}/{variable}; configure sources")
                if len(records):
                    if records.member.duplicated().any():
                        raise ValueError("Overlapping input intervals")
                    values[f"{side}_{variable}"] = records.value.mean()
                    values[f"{side}_{variable}_spread"] = records.value.std(ddof=0)
                    values[f"{side}_{variable}_age_hours"] = (origin - records.issue.min()).total_seconds() / 3600
                    values[f"{side}_{variable}_coarse"] = float(records.interval_minutes.max() > 30)
                    previous_delivery = delivery - pd.Timedelta(minutes=30)
                    previous = selected[(selected.region == region) & (selected.variable == variable)
                                        & (selected.delivery >= previous_delivery)
                                        & (selected.delivery - pd.to_timedelta(selected.interval_minutes, unit="m") < previous_delivery)]
                    if source:
                        previous = previous[previous.source == source]
                    if len(previous) and previous.source.nunique() == 1:
                        values[f"{side}_{variable}_ramp"] = records.value.mean() - previous.value.mean()
            if all(f"{side}_{v}" in values for v in ("demand", "wind", "solar")):
                values[f"{side}_residual"] = values[f"{side}_demand"] - values[f"{side}_wind"] - values[f"{side}_solar"]
        if "source_residual" in values and "sink_residual" in values:
            values["residual_difference"] = values["source_residual"] - values["sink_residual"]
            period = next(i for i, end in enumerate((6, 10, 16, 21, 24)) if hour < end)
            for i in range(5):
                values[f"period_{i}"] = float(i == period)
                values[f"residual_difference_period_{i}"] = values["residual_difference"] * float(i == period)
    if history is not None and len(history):
        h = history[(history.connector == connector(name)) & (history.target == manifest["target"])
                    & (history.delivery <= origin - pd.Timedelta(minutes=30)) & (history.received <= origin)]
        h = h.sort_values(["delivery", "received"]).drop_duplicates("delivery", keep="last")
        if len(h) and origin - h.iloc[-1].delivery <= pd.Timedelta(hours=manifest.get("max_history_age_hours", 2)):
            values["own_anchor"] = float(h.iloc[-1].value)
        for lag in (1, 48, 336):
            row = h[h.delivery == origin - pd.Timedelta(minutes=30 * lag)]
            if len(row):
                values[f"limit_lag{lag}"] = float(row.iloc[-1].value)
    missing = set(manifest["features"]) - values.keys()
    if missing:
        raise ValueError(f"Missing features: {sorted(missing)}")
    frame = pd.DataFrame([{key: values[key] for key in manifest["features"]}])
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("Non-finite engineered features")
    return frame


def training_table(manifest, requests, inputs, history=None, context=None):
    """Requests have origin, delivery, connector and actual; features built as-of each origin."""
    rows = []
    for row in requests.to_dict("records"):
        features = build(manifest, row["origin"], row["delivery"], row["connector"], inputs, history, context=context)
        rows.append({**features.iloc[0].to_dict(), **{k: row[k] for k in ("origin", "delivery", "connector", "actual")}})
    return pd.DataFrame(rows)
