"""Explicit, issue-time outage scenario snapshots for shadow forecasting."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .contracts import digest, write_json


REQUIRED = {"outage_id", "equipment", "issue", "received", "start", "end", "status"}


def asof_outages(outages, origin):
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None:
        raise ValueError("Scenario origin must be timezone aware")
    if REQUIRED - set(outages):
        raise ValueError(f"Missing outage fields: {sorted(REQUIRED - set(outages))}")
    frame = outages.copy()
    for column in ("issue", "received", "start", "end"):
        frame[column] = pd.to_datetime(frame[column], utc=True).dt.tz_convert("Australia/Brisbane")
    if (frame.received < frame.issue).any() or (frame.end < frame.start).any():
        raise ValueError("Invalid outage publication or schedule chronology")
    eligible = frame[(frame.issue <= origin) & (frame.received <= origin)]
    return eligible.sort_values(["issue", "received"]).drop_duplicates("outage_id", keep="last").reset_index(drop=True)


def standard_scenarios(outages, origin, extension_hours=24):
    baseline = asof_outages(outages, origin)
    active = baseline[~baseline.status.astype(str).str.lower().eq("cancelled")].copy()
    no_planned = active[~active.status.astype(str).str.lower().eq("planned")].copy()
    extended = active.copy()
    planned = extended.status.astype(str).str.lower().eq("planned")
    extended.loc[planned, "end"] += pd.Timedelta(hours=float(extension_hours))
    for name, frame in (("baseline", active), ("no_planned_outages", no_planned),
                        (f"planned_extended_{int(extension_hours)}h", extended)):
        frame["scenario"] = name
    return {"baseline": active, "no_planned_outages": no_planned,
            f"planned_extended_{int(extension_hours)}h": extended}


def apply_local_edits(baseline, edits, origin, name="local"):
    """Apply explicit add/update/cancel rows without altering the source snapshot."""
    if not name or name == "baseline":
        raise ValueError("Local edits require a non-baseline scenario name")
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None:
        raise ValueError("Scenario origin must be timezone aware")
    result = baseline.copy()
    required = {"action", "outage_id"}
    if required - set(edits):
        raise ValueError(f"Missing edit fields: {sorted(required - set(edits))}")
    for edit in edits.to_dict("records"):
        action = str(edit["action"]).lower()
        mask = result.outage_id.astype(str).eq(str(edit["outage_id"]))
        if action == "cancel":
            result = result.loc[~mask].copy()
        elif action == "update":
            if mask.sum() != 1:
                raise ValueError(f"Update requires exactly one outage: {edit['outage_id']}")
            for column in ("start", "end", "status"):
                if column in edit and pd.notna(edit[column]):
                    result.loc[mask, column] = pd.Timestamp(edit[column]) if column in {"start", "end"} else edit[column]
        elif action == "add":
            if mask.any():
                raise ValueError(f"Added outage already exists: {edit['outage_id']}")
            missing = REQUIRED - set(edit)
            if missing - {"issue", "received"}:
                raise ValueError(f"Added outage is missing: {sorted(missing - {'issue', 'received'})}")
            row = {key: edit.get(key) for key in result.columns}
            row.update(issue=origin, received=origin)
            result = pd.concat([result, pd.DataFrame([row])], ignore_index=True)
        else:
            raise ValueError(f"Unknown outage edit action: {action}")
    for column in ("issue", "received", "start", "end"):
        result[column] = pd.to_datetime(result[column], utc=True).dt.tz_convert("Australia/Brisbane")
    if (result.end < result.start).any():
        raise ValueError("Local edit creates an outage ending before it starts")
    result["scenario"] = name
    return result


def write_scenarios(outages, origin, output, edits=None, local_name="local"):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    scenarios = standard_scenarios(outages, origin)
    if edits is not None:
        scenarios[local_name] = apply_local_edits(scenarios["baseline"], edits, origin, local_name)
    records = []
    for name, frame in scenarios.items():
        path = output / f"{name}.parquet"
        frame.to_parquet(path, index=False)
        records.append({"scenario": name, "path": path.name, "rows": len(frame), "sha256": digest(path)})
    write_json(output / "manifest.json", {"schema": 1, "origin": str(pd.Timestamp(origin)), "scenarios": records})
    return output / "manifest.json"
