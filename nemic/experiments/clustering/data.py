"""Read-only adapters for retained forecast and constraint evidence."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import json

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from nemic.experiments.core import ROOT, digest
from .config import campaign_fingerprint, code_manifest, store

META_COLUMNS = [
    "origin", "delivery", "connector", "provenance", "source_cohort", "lead",
]
TARGET_COLUMNS = [
    f"{prefix}_{target}"
    for target in ("flow", "export_tight", "import_tight")
    for prefix in ("actual", "anchor", "seasonal48", "seasonal336")
]
CALENDAR_COLUMNS = ["hour_sin", "hour_cos", "year_sin", "year_cos", "weekend"]


def connector_config(config: dict, connector: str) -> dict:
    for item in config["connectors"]:
        if connector in (item["name"], item["id"]):
            return item
    raise KeyError(f"Unknown connector: {connector}")


def feature_paths(config: dict, connector: str) -> tuple[Path, Path]:
    name = connector_config(config, connector)["name"]
    folder = config["_source"] / "features" / name / "pasa_coal"
    return folder / "table.parquet", folder / "table.schema.json"


def schema_groups(config: dict, connector: str) -> dict[str, str]:
    _, path = feature_paths(config, connector)
    payload = json.loads(path.read_text(encoding="utf-8"))
    groups = payload.get("groups")
    if not isinstance(groups, dict) or not groups:
        raise ValueError(f"Missing feature groups in {path}")
    return {str(key): str(value) for key, value in groups.items()}


def feature_contract(config: dict, connector: str) -> dict[str, list[str]]:
    """Return compact, declared blocks used by clustering and matched models."""
    groups = schema_groups(config, connector)
    network = [key for key, value in groups.items() if value == "network"]
    origin_network = [
        key for key in network
        if key not in {"lead", "log_lead", *CALENDAR_COLUMNS}
    ]
    history = [key for key in origin_network if "lag" in key or key.endswith("_delta")]
    topology = [
        key for key in origin_network
        if any(token in key for token in ("room", "switch_gap", "candidate_count", "setter_age", "switch_recent"))
    ]
    pressure = [
        key for key in origin_network
        if any(token in key for token in ("gen_tightening", "gen_relief", "pressure_change", "available_relief"))
    ]
    quality = [
        key for key in origin_network
        if key not in set(history + topology + pressure)
    ]
    endpoint = [key for key, value in groups.items() if value == "endpoint"]
    source_quality = [
        key for key, value in groups.items()
        if value == "quality" and key.startswith("pasa_")
    ]
    origin = {
        "history": history,
        "topology": topology,
        "pressure": pressure,
        "quality": quality,
    }
    forecast = {**origin, "fundamentals": endpoint, "source_quality": source_quality}
    return {
        "origin": [column for block in origin.values() for column in block],
        "forecast": [column for block in forecast.values() for column in block],
        "network_model": network,
        "fundamentals_model": list(dict.fromkeys(network + endpoint + source_quality)),
        "calendar": CALENDAR_COLUMNS,
        "origin_groups": origin,
        "forecast_groups": forecast,
    }


def load_feature_rows(
    config: dict,
    connector: str,
    *,
    columns: list[str] | None = None,
    start: str | pd.Timestamp | None = None,
    end: str | pd.Timestamp | None = None,
    max_origins: int | None = None,
) -> pd.DataFrame:
    table, _ = feature_paths(config, connector)
    contract = feature_contract(config, connector)
    requested = list(dict.fromkeys(columns or (
        META_COLUMNS + TARGET_COLUMNS + contract["fundamentals_model"]
    )))
    available = set(pq.ParquetFile(table).schema_arrow.names)
    missing = sorted(set(requested) - available)
    if missing:
        raise ValueError(f"Source table lacks required columns: {missing}")
    frame = pd.read_parquet(table, columns=requested)
    frame["origin"] = pd.to_datetime(frame["origin"])
    frame["delivery"] = pd.to_datetime(frame["delivery"])
    if start is not None:
        frame = frame.loc[frame.origin >= pd.Timestamp(start)]
    if end is not None:
        frame = frame.loc[frame.origin < pd.Timestamp(end)]
    if max_origins is not None:
        keep = np.sort(frame.origin.unique())[: int(max_origins)]
        frame = frame.loc[frame.origin.isin(keep)]
    frame = frame.sort_values(["origin", "lead"], kind="stable").reset_index(drop=True)
    if not frame.empty:
        expected = (frame.delivery - frame.origin) / pd.Timedelta(minutes=30)
        if not np.array_equal(expected.astype(int).to_numpy(), frame.lead.astype(int).to_numpy()):
            raise ValueError("Lead does not match origin/delivery interval-ending arithmetic")
        if frame.duplicated(["origin", "delivery", "lead"]).any():
            raise ValueError("Duplicate origin/delivery/lead rows")
    return frame


def unique_origin_rows(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return exactly one row per origin after checking state is lead-invariant."""
    if not columns:
        raise ValueError("No origin-state columns supplied")
    values = frame[["origin", *columns]].copy()
    # Numeric state should be identical across repeated lead rows. Nunique keeps
    # missing explicit so mixed missing/non-missing states are rejected.
    counts = values.groupby("origin", sort=False)[columns].nunique(dropna=False)
    bad = counts.gt(1).any(axis=1)
    if bad.any():
        raise ValueError(f"Origin-state columns vary across leads for {int(bad.sum())} origins")
    return values.drop_duplicates("origin", keep="first").reset_index(drop=True)


def equal_origin_training_rows(frame: pd.DataFrame, seed: int) -> pd.DataFrame:
    """Choose one deterministic lead row per origin for unweighted estimators."""
    if frame.empty:
        return frame.copy()
    ordered = frame.sort_values(["origin", "lead"], kind="stable")
    chosen = []
    # Stable hash-like offset avoids always preferring the shortest lead while
    # remaining independent of outcomes. Iteration preserves the grouping
    # column, unlike DataFrameGroupBy.apply(include_groups=False).
    for origin, group in ordered.groupby("origin", sort=False):
        stamp = int(pd.Timestamp(origin).value // 10**9)
        chosen.append(group.iloc[[(stamp + int(seed)) % len(group)]])
    return pd.concat(chosen, ignore_index=True)


def _months_in_range(folder: Path, start: pd.Timestamp, end: pd.Timestamp) -> list[Path]:
    result = []
    for month in sorted((folder / "months").glob("????-??")):
        month_start = pd.Timestamp(month.name + "-01")
        month_end = month_start + pd.offsets.MonthBegin(1)
        if month_end > start and month_start < end:
            result.append(month)
    return result


def load_constraint_exposure(
    config: dict, connector: str, start: str | pd.Timestamp, end: str | pd.Timestamp
) -> pd.DataFrame:
    item = connector_config(config, connector)
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    rows = []
    for month in _months_in_range(ROOT / "data" / item["study"], lo, hi):
        path = month / "constraint_features_30min.parquet"
        part = pd.read_parquet(path, columns=["time", "upper_version_key", "lower_version_key"])
        part = part.loc[(part.time >= lo) & (part.time < hi)]
        for direction in ("upper", "lower"):
            counts = part[f"{direction}_version_key"].dropna().value_counts()
            rows.extend(
                {"version_key": key, "direction": direction, "exposure": int(value)}
                for key, value in counts.items()
            )
    if not rows:
        return pd.DataFrame(columns=["version_key", "direction", "exposure"])
    return pd.DataFrame(rows).groupby(["version_key", "direction"], as_index=False).exposure.sum()


def load_constraint_states(
    config: dict, connector: str, start: str | pd.Timestamp, end: str | pd.Timestamp
) -> pd.DataFrame:
    """Load the active reconstructed upper/lower equation versions by half hour."""
    item = connector_config(config, connector)
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    columns = [
        "time", "upper_constraint", "lower_constraint",
        "upper_version_key", "lower_version_key",
    ]
    frames = []
    for month in _months_in_range(ROOT / "data" / item["study"], lo, hi):
        path = month / "constraint_features_30min.parquet"
        part = pd.read_parquet(path, columns=columns)
        part = part.loc[(part.time >= lo) & (part.time < hi)]
        if not part.empty:
            frames.append(part)
    if not frames:
        return pd.DataFrame(columns=columns)
    combined = pd.concat(frames, ignore_index=True).sort_values("time")
    if combined.duplicated("time").any():
        raise ValueError("Duplicate half-hour constraint states")
    return combined.reset_index(drop=True)


def load_sensitivities(
    config: dict, connector: str, version_keys: set[str] | None = None
) -> pd.DataFrame:
    item = connector_config(config, connector)
    columns = ["version_key", "GENCONID", "DUID", "FACTOR", "ic_factor", "sensitivity"]
    frames = []
    for path in sorted((ROOT / "data" / item["study"] / "months").glob("*/unit_sensitivities.parquet")):
        frame = pd.read_parquet(path, columns=columns)
        if version_keys is not None:
            frame = frame.loc[frame.version_key.isin(version_keys)]
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=columns)
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates(columns, keep="last").reset_index(drop=True)


def load_unit_pressure(
    config: dict,
    connector: str,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> pd.DataFrame:
    item = connector_config(config, connector)
    lo, hi = pd.Timestamp(start), pd.Timestamp(end)
    columns = ["time", "direction", "constraint", "DUID", "tightening_mw"]
    frames = []
    for month in _months_in_range(ROOT / "data" / item["study"], lo, hi):
        path = month / "unit_pressure_5min.parquet"
        part = pd.read_parquet(path, columns=columns)
        part = part.loc[(part.time >= lo) & (part.time < hi)]
        if not part.empty:
            frames.append(part)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=columns)


def inventory(config: dict, save: bool = True) -> dict:
    sources: list[dict] = []
    coverage: list[dict] = []
    for item in config["connectors"]:
        table, schema = feature_paths(config, item["name"])
        for path, role in ((table, "forecast feature table"), (schema, "forecast feature schema")):
            if not path.exists():
                raise FileNotFoundError(path)
            sources.append({
                "path": path.relative_to(ROOT).as_posix(), "role": role,
                "bytes": path.stat().st_size, "sha256": digest(path),
            })
        meta = pd.read_parquet(table, columns=["origin", "delivery", "lead", "provenance", "source_cohort"])
        coverage.append({
            "connector": item["name"], "rows": len(meta),
            "origins": int(meta.origin.nunique()),
            "origin_start": meta.origin.min(), "origin_end": meta.origin.max(),
            "delivery_start": meta.delivery.min(), "delivery_end": meta.delivery.max(),
            "leads": sorted(int(value) for value in meta.lead.unique()),
            "provenance": sorted(str(value) for value in meta.provenance.dropna().unique()),
            "source_cohorts": Counter(str(value) for value in meta.source_cohort.fillna("missing")),
            "columns": len(pq.ParquetFile(table).schema_arrow.names),
        })
        study = ROOT / "data" / item["study"] / "months"
        for pattern, role in (
            ("*/constraint_features_30min.parquet", "constraint exposure"),
            ("*/unit_sensitivities.parquet", "signed generator sensitivity"),
            ("*/unit_pressure_5min.parquet", "historical DUID pressure"),
        ):
            for path in sorted(study.glob(pattern)):
                sources.append({
                    "path": path.relative_to(ROOT).as_posix(), "role": role,
                    "bytes": path.stat().st_size, "sha256": digest(path),
                })
    fingerprint = campaign_fingerprint(config, sources)
    payload = {
        "campaign": config["campaign"],
        "configuration": {key: value for key, value in config.items() if not key.startswith("_")},
        "coverage": coverage,
        "sources": sources,
        "code": code_manifest(),
        "fingerprint": fingerprint,
        "claim": config["claims"]["primary"],
        "weather_note": "No weather is admitted to the primary pasa_coal track.",
        "observed_limits_note": "Reported limits are dispatch-solution outputs, not maximum secure physical capability.",
    }
    if save:
        destination = config["_run"] / "inventory.json"
        store(config).json(destination, payload)
    return payload
