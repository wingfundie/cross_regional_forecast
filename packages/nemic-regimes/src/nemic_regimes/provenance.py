"""Strict eligibility for dated automatic selections and explicit user assumptions."""
from __future__ import annotations
import pandas as pd


def validate_inputs(records, origin, conditions=None):
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None:
        raise ValueError("Origin must include a timezone")
    groups = {}
    covered = set()
    values = {}
    for row in records:
        field = row.get("variable")
        if not field:
            raise ValueError("Input variable missing")
        if row.get("information_class") == "user_assumption":
            if not row.get("scenario_name") or "value" not in row:
                raise ValueError("User assumptions need a scenario name")
            covered.add(field)
            values[field] = row["value"]
            continue
        if conditions and conditions.get("connector"):
            from .core import CONNECTORS,connector_name
            name=connector_name(conditions["connector"])
            _,source,sink=CONNECTORS[name]
            if conditions.get("direction")=="reverse":source,sink=sink,source
            if field.startswith("source_") and row.get("region")!=source:
                raise ValueError(f"Input region for {field} does not match the connector direction")
            if field.startswith("sink_") and row.get("region")!=sink:
                raise ValueError(f"Input region for {field} does not match the connector direction")
            aggregate=field in {"temperature_max","humidity_mean","vre_difference","residual_difference","residual_difference_ramp_1h"} or field.startswith(("corridor_","electrical_"))
            if aggregate and set(row.get("regions",[]))!={source,sink}:
                raise ValueError(f"Input regional coverage for {field} differs from the condition contract")
            from .core import NUMERIC_FEATURES
            if field in NUMERIC_FEATURES:
                units="C" if "temperature" in field else "%" if "humidity" in field or "cloud" in field else "m/s" if field=="corridor_wind_ms" else "W/m2" if field=="corridor_radiation_wm2" else "MW"
                if row.get("units")!=units:raise ValueError(f"Input units for {field} must be {units}")
        required = {"source", "product", "run_id", "issue", "received", "receipt_completed", "delivery", "sha256", "availability_evidence"}
        if required - set(row):
            raise ValueError(f"Missing provenance fields: {sorted(required - set(row))}")
        if row["availability_evidence"] != "measured_receipt":
            raise ValueError("Historical publication proxy is not measured receipt evidence")
        times = {f: pd.Timestamp(row[f]) for f in ("issue", "received", "receipt_completed", "delivery")}
        if any(t.tzinfo is None for t in times.values()):
            raise ValueError("Input timestamps need timezones")
        if not times["issue"] <= times["received"] <= times["receipt_completed"] <= origin:
            raise ValueError("Input unavailable at origin or invalid receipt chronology")
        if "retrieval_started" in row and not times["issue"] <= pd.Timestamp(row["retrieval_started"]) <= times["received"]:
            raise ValueError("Invalid retrieval chronology")
        age = (origin - times["issue"]).total_seconds() / 3600
        if age > float(row.get("max_age_hours", 24)):
            raise ValueError("Stale input")
        if len(row["sha256"]) != 64 or any(x not in "0123456789abcdef" for x in row["sha256"].lower()):
            raise ValueError("Invalid source hash")
        group = row.get("coherence_group", row["source"] + ":" + row["product"])
        identity = (row["source"], row["product"], row["run_id"], str(times["issue"]))
        if group in groups and groups[group] != identity:
            raise ValueError("Mixed vintages in one coherence group")
        groups[group] = identity
        covered.add(field)
        if "value" not in row:
            raise ValueError("Input value missing")
        values[field] = row["value"]
        if conditions and conditions.get("delivery") and times["delivery"] != pd.Timestamp(conditions["delivery"]):
            raise ValueError("Input delivery differs from the requested dated condition; use a named scenario for transferred observations")
    if conditions:
        from .core import NUMERIC_FEATURES
        required_fields = {k for k, v in conditions.items() if k in NUMERIC_FEATURES and v is not None}
        required_fields |= {k for k in ("required_sets", "excluded_sets", "required_assets", "outage_state") if conditions.get(k) not in (None, "any", [])}
        if required_fields - covered:
            raise ValueError(f"Conditions without input provenance: {sorted(required_fields - covered)}")
        for field in required_fields:
            wanted, supplied = conditions[field], values[field]
            if isinstance(wanted, dict):
                if not wanted.get("min", float("-inf")) <= float(supplied) <= wanted.get("max", float("inf")):
                    raise ValueError(f"Condition {field} differs from its input evidence")
            elif field in NUMERIC_FEATURES:
                import math
                if not math.isclose(float(wanted), float(supplied), rel_tol=1e-9, abs_tol=1e-9):
                    raise ValueError(f"Condition {field} differs from its input evidence")
            elif wanted != supplied:
                raise ValueError(f"Condition {field} differs from its input evidence")
    return True
