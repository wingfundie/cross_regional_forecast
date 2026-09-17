"""Provider mappings, immutable snapshots and explicitly recorded scenarios."""
from pathlib import Path
import pandas as pd
import numpy as np

from .contracts import digest, write_json


def read_table(path):
    path = Path(path)
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    raise ValueError("Use CSV or Parquet")


def timestamps(values, timezone=None):
    parsed = pd.to_datetime(values, errors="raise")
    if parsed.dt.tz is None:
        if not timezone:
            raise ValueError("Naive timestamps require an explicit timezone")
        parsed = parsed.dt.tz_localize(timezone, ambiguous="raise", nonexistent="raise")
    return parsed.dt.tz_convert("Australia/Brisbane")


def normalize(frame, mapping):
    """Long format: one variable/region/interval/member per issued forecast."""
    out = frame.rename(columns={v: k for k, v in mapping["columns"].items()}).copy()
    required = {"issue", "received", "delivery", "region", "variable", "value"}
    if required - set(out):
        raise ValueError(f"Missing input columns: {required - set(out)}")
    for field in ("issue", "received", "delivery"):
        out[field] = timestamps(out[field], mapping.get("timezone"))
    if (out.received < out.issue).any():
        raise ValueError("Receipt precedes forecast issue")
    minutes = int(mapping["interval_minutes"])
    if minutes <= 0 or mapping["interval_label"] not in {"start", "end"}:
        raise ValueError("Invalid interval convention")
    if mapping["interval_label"] == "start":
        out["delivery"] += pd.Timedelta(minutes=minutes)
    out["interval_minutes"] = minutes
    out["region"] = out.region.replace(mapping.get("regions", {}))
    out["variable"] = out.variable.replace(mapping.get("variables", {}))
    conversions = {"MW": (1., 0.), "GW": (1000., 0.), "C": (1., 0.), "K": (1., -273.15), "m/s": (1., 0.)}
    units = mapping["units"]
    for variable, rows in out.groupby("variable").groups.items():
        if variable not in units or units[variable] not in conversions:
            raise ValueError(f"Unsupported unit for {variable}")
        factor, offset = conversions[units[variable]]
        if variable in {"demand", "wind", "solar"} and units[variable] not in {"MW", "GW"}:
            raise ValueError("Power forecasts require MW/GW")
        if variable == "temperature" and units[variable] not in {"C", "K"}:
            raise ValueError("Temperature forecasts require C/K")
        out.loc[rows, "value"] = pd.to_numeric(out.loc[rows, "value"], errors="raise") * factor + offset
    out["value"] = out.value.astype(float)
    if not np.isfinite(out.value).all():
        raise ValueError("Non-finite forecast values")
    out["source"] = mapping["source"]
    if "member" not in out:
        out["member"] = "central"
    keys = ["source", "issue", "received", "delivery", "region", "variable", "member"]
    if out.duplicated(keys).any():
        raise ValueError("Duplicate forecast records")
    return out


def asof(frame, origin, max_age_hours):
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None:
        raise ValueError("Origin must include timezone")
    selected = frame[(frame.issue <= origin) & (frame.received <= origin)].copy()
    selected = selected[(origin - selected.issue) <= pd.Timedelta(hours=max_age_hours)]
    keys = ["source", "region", "variable", "delivery", "member"]
    return selected.sort_values(["issue", "received"]).drop_duplicates(keys, keep="last")


def archive(frame, folder):
    """Content-addressed normalized snapshot; identical imports are idempotent."""
    import hashlib
    identity = hashlib.sha256(frame.to_json(date_format="iso", orient="table").encode()).hexdigest()
    path = Path(folder) / f"{identity}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        frame.to_parquet(path, index=False)
        write_json(path.with_suffix(".json"), {"sha256": digest(path), "rows": len(frame), "schema": 1})
    return path


def scenario(frame, overrides, name):
    if not name or name == "baseline":
        raise ValueError("Assumptions require a named scenario")
    out = frame.copy()
    keys = ["region", "variable", "delivery"]
    if overrides.duplicated(keys).any():
        raise ValueError("Duplicate scenario overrides")
    for row in overrides.to_dict("records"):
        mask = (out.region == row["region"]) & (out.variable == row["variable"]) & (out.delivery == pd.Timestamp(row["delivery"]))
        if not mask.any():
            raise ValueError("Override has no matching input interval; supply a complete scenario input for uncovered days")
        out.loc[mask, "value"] = float(row["value"])
        out.loc[mask, "assumption"] = name
    return out
