"""Explicit network adapter and legacy bundle import; nothing fetches on import."""
from pathlib import Path
import shutil
import pandas as pd

from .contracts import digest, read_json, write_json


def open_meteo_payload(payload, *, region, received, issue=None, source="open-meteo"):
    """Parse cached hourly responses. Require genuine model issue time from caller.

    API retrieval time must never be passed off as a historical model initialization.
    """
    if issue is None:
        raise ValueError("An explicit forecast issue timestamp is required")
    hourly = payload["hourly"]
    records = []
    for key, values in hourly.items():
        if key == "time":
            continue
        variable = {"temperature_2m": "temperature", "wind_speed_10m": "wind_speed"}.get(key.split("_member")[0])
        if variable is None:
            continue
        member = key.split("_member", 1)[1] if "_member" in key else "central"
        for time, value in zip(hourly["time"], values):
            if value is None:
                continue
            # API request must specify UTC. Weather timestamps are point estimates;
            # align at those endpoints without inventing a half-hour measurement.
            records.append(dict(issue=issue, received=received, delivery=pd.Timestamp(time, tz="UTC") if pd.Timestamp(time).tzinfo is None else pd.Timestamp(time),
                                region=region, variable=variable, value=value, source=source, member=member, interval_minutes=60))
    result = pd.DataFrame(records)
    for field in ("issue", "received", "delivery"):
        result[field] = pd.to_datetime(result[field], utc=True).dt.tz_convert("Australia/Brisbane")
    return result


def fetch_open_meteo(*, latitude, longitude, days=7, ensemble=False):
    """Explicit opt-in fetch. Payload needs model initialization provenance before use."""
    import requests
    if not 1 <= days <= (35 if ensemble else 16):
        raise ValueError("Requested horizon exceeds endpoint; choose ensemble/outlook")
    endpoint = "https://ensemble-api.open-meteo.com/v1/ensemble" if ensemble else "https://api.open-meteo.com/v1/forecast"
    response = requests.get(endpoint, params={"latitude": latitude, "longitude": longitude,
            "hourly": "temperature_2m,wind_speed_10m", "timezone": "UTC", "wind_speed_unit": "ms", "forecast_days": days}, timeout=60)
    response.raise_for_status()
    return {"received": pd.Timestamp.now(tz="UTC").isoformat(), "payload": response.json()}


def import_legacy(final_dir, registry, staging):
    """Copy original VNI artifacts into portable packages; never promote them."""
    import joblib
    final_dir, staging = Path(final_dir), Path(staging)
    result = []
    bands = [(1, 12), (13, 48), (49, 144), (145, 336)]
    for row in read_json(final_dir / "catalogue.json"):
        source = (final_dir.parent / row["path"].replace("\\", "/")).resolve()
        if not source.is_relative_to(final_dir.resolve()) or digest(source) != row["sha256"]:
            raise ValueError("Legacy artifact path/hash mismatch")
        bundle = joblib.load(source)
        target, band = row["target"], int(row["band"])
        if bundle["target"] != target or bundle["band"] != band:
            raise ValueError("Legacy identity mismatch")
        folder = staging / f"vni-{target}-{band}"
        folder.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(source, folder / "model.joblib")
        manifest = {"id": f"vni-legacy-{target}-band{band}", "version": "1", "connectors": ["VNI"],
                    "target": target, "lead_min": bands[band][0], "lead_max": bands[band][1],
                    "resolution_minutes": 30, "adapter": "legacy-vni", "recipe": "legacy-vni-v1",
                    "features": bundle["input_columns"], "status": "research", "training_cutoff": None,
                    "evaluation": "Legacy retrospective study; see VNI research report", "dependencies": {},
                    "artifacts": {"model.joblib": digest(folder / "model.joblib")}}
        write_json(folder / "manifest.json", manifest)
        result.append(registry.register(folder))
    return result
