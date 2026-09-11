"""Dependency-scoped AEMO downloads for the VNI constraint-feature pilot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd

from .common import DATA, ROOT, dump, session

CONFIG = ROOT / "configs" / "constraint_vni_pilot.json"
PILOT = DATA / "constraint_pilot"
RAW = PILOT / "raw"
TABLES = PILOT / "tables"


def load_config(path=CONFIG):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    files = config.get("files", [])
    if not files:
        raise ValueError("Download manifest contains no files")
    if len({x["url"] for x in files}) != len(files):
        raise ValueError("Download manifest contains duplicate URLs")
    allowed_tables = {x["table"] for x in files}
    for entry in files:
        name = unquote(urlparse(entry["url"]).path.rsplit("/", 1)[-1])
        if not entry["url"].startswith("https://nemweb.com.au/"):
            raise ValueError("Only explicit NEMWEB HTTPS URLs are allowed")
        if f"#{entry['table']}#" not in name or not name.lower().endswith(".zip"):
            raise ValueError(f"URL is not the declared table archive: {name}")
        if entry["table"] not in allowed_tables or entry["phase"] not in {"static", "interval"}:
            raise ValueError(f"Invalid manifest entry: {entry}")
    total = sum(int(x["expected_bytes"]) for x in files)
    if total > int(config["limits"]["pilot_compressed_bytes"]):
        raise ValueError("Manifest exceeds pilot compressed-byte cap")
    return config


def audit_manifest(config):
    limits = config["limits"]
    rows = []
    client = session()
    for entry in config["files"]:
        name = unquote(urlparse(entry["url"]).path.rsplit("/", 1)[-1])
        cached = RAW / name
        size = cached.stat().st_size if cached.exists() else None
        if size is None:
            response = client.head(entry["url"], timeout=(20, 60), allow_redirects=True)
            response.raise_for_status()
            header = response.headers.get("Content-Length")
            size = int(header) if header else None
        if size is None:
            raise ValueError(f"Server gave no size for {name}; explicit override required")
        if size > int(limits["file_compressed_bytes"]):
            raise ValueError(f"File exceeds compressed-byte cap: {name}")
        rows.append({**entry, "file": name, "actual_or_remote_bytes": size,
                     "cached": cached.exists()})
    if sum(x["actual_or_remote_bytes"] for x in rows) > int(limits["pilot_compressed_bytes"]):
        raise ValueError("Audited files exceed pilot compressed-byte cap")
    free = shutil.disk_usage(PILOT.parent).free
    if free < int(limits["min_free_bytes"]):
        raise ValueError("Insufficient free disk space for guarded extraction")
    audit = {"experiment_id": config["experiment_id"], "files": rows,
             "compressed_bytes": sum(x["actual_or_remote_bytes"] for x in rows),
             "cached_bytes": sum(x["actual_or_remote_bytes"] for x in rows if x["cached"]),
             "free_bytes": free, "limits": limits}
    dump(PILOT / "download_audit.json", audit)
    return audit


def download_entry(entry, limits):
    name = unquote(urlparse(entry["url"]).path.rsplit("/", 1)[-1])
    path = RAW / name
    RAW.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with zipfile.ZipFile(path) as archive:
            archive.testzip()
        return path
    partial = path.with_suffix(path.suffix + ".partial")
    response = session().get(entry["url"], stream=True, timeout=(20, 180))
    response.raise_for_status()
    length = response.headers.get("Content-Length")
    cap = int(limits["file_compressed_bytes"])
    if length and int(length) > cap:
        raise ValueError(f"File exceeds compressed-byte cap: {name}")
    written = 0
    with partial.open("wb") as handle:
        for chunk in response.iter_content(1024 * 1024):
            if not chunk:
                continue
            written += len(chunk)
            if written > cap:
                handle.close()
                partial.unlink(missing_ok=True)
                raise ValueError(f"Stream exceeded compressed-byte cap: {name}")
            handle.write(chunk)
    with zipfile.ZipFile(partial) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Corrupt member {bad} in {name}")
        expanded = sum(x.file_size for x in archive.infolist())
        if expanded > int(limits["batch_decompressed_bytes"]):
            raise ValueError(f"Archive exceeds decompressed-byte cap: {name}")
    partial.replace(path)
    return path


def _table_rows(path, table, keep=None, value_filter=None):
    """Stream one MMS table archive and retain only requested columns/records."""
    result, schema = [], None
    with zipfile.ZipFile(path) as archive:
        members = [x for x in archive.infolist() if x.filename.lower().endswith(".csv")]
        if not members:
            raise ValueError(f"No CSV member in {path.name}")
        for member in members:
            with archive.open(member) as raw:
                lines = (line.decode("utf-8-sig", errors="strict") for line in raw)
                for row in csv.reader(lines):
                    if len(row) < 4:
                        continue
                    if row[0] == "I":
                        schema = row[4:]
                        continue
                    if row[0] != "D" or schema is None:
                        continue
                    values = row[4:4 + len(schema)]
                    record = dict(zip(schema, values))
                    if value_filter and not value_filter(record):
                        continue
                    result.append({k: record.get(k, "") for k in (keep or schema)})
    return pd.DataFrame(result)


def extract_static(config):
    outputs = {}
    for entry in config["files"]:
        if entry["phase"] != "static":
            continue
        path = download_entry(entry, config["limits"])
        frame = _table_rows(path, entry["table"])
        out = TABLES / f"{entry['table']}.parquet"
        out.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(out, index=False, compression="zstd")
        outputs[entry["table"]] = {"rows": len(frame), "columns": list(frame)}
    dump(PILOT / "static_extraction.json", outputs)
    return outputs


def discover_dependencies(config):
    interconnector = config["interconnector"]
    ic_terms = pd.read_parquet(TABLES / "SPDINTERCONNECTORCONSTRAINT.parquet")
    unit_terms = pd.read_parquet(TABLES / "SPDCONNECTIONPOINTCONSTRAINT.parquet")
    details = pd.read_parquet(TABLES / "DUDETAILSUMMARY.parquet")
    ic_terms = ic_terms[ic_terms["INTERCONNECTORID"].eq(interconnector)].copy()
    constraint_ids = sorted(ic_terms["GENCONID"].dropna().unique())
    unit_terms = unit_terms[
        unit_terms["GENCONID"].isin(constraint_ids)
        & unit_terms["BIDTYPE"].fillna("ENERGY").eq("ENERGY")
    ].copy()
    start = pd.Timestamp(config["start"])
    end = pd.Timestamp(config["end"])
    details["START_DATE"] = pd.to_datetime(details["START_DATE"], errors="coerce")
    details["END_DATE"] = pd.to_datetime(details["END_DATE"], errors="coerce")
    details["LASTCHANGED"] = pd.to_datetime(details["LASTCHANGED"], errors="coerce")
    active = details[
        (details.START_DATE <= end)
        & (details.END_DATE.isna() | (details.END_DATE > start))
    ].copy()
    mapping = active[["DUID", "CONNECTIONPOINTID", "DISPATCHTYPE", "REGIONID",
                      "STATIONID", "START_DATE", "END_DATE"]].drop_duplicates()
    resolved = unit_terms.merge(mapping, on="CONNECTIONPOINTID", how="left")
    duids = sorted(resolved["DUID"].dropna().unique())
    audit = {
        "interconnector": interconnector,
        "constraint_count": len(constraint_ids),
        "energy_connection_point_count": int(unit_terms.CONNECTIONPOINTID.nunique()),
        "mapped_duid_count": len(duids),
        "mapping_rows_changed_after_pilot_end": int((active.LASTCHANGED > end).sum()),
        "unmapped_connection_points": sorted(resolved.loc[resolved.DUID.isna(), "CONNECTIONPOINTID"].unique()),
        "tumut3": resolved[resolved.DUID.eq("TUMUT3")][
            ["GENCONID", "CONNECTIONPOINTID", "FACTOR", "DUID"]
        ].drop_duplicates().to_dict("records"),
    }
    dump(PILOT / "dependency_audit.json", audit)
    resolved.to_parquet(TABLES / "VNI_ENERGY_TERMS.parquet", index=False, compression="zstd")
    dump(PILOT / "dependency_ids.json", {"constraints": constraint_ids, "duids": duids})
    return constraint_ids, duids


def extract_interval(config):
    constraint_ids, duids = discover_dependencies(config)
    outputs = {}
    keep = {
        "DISPATCHCONSTRAINT": ["SETTLEMENTDATE", "RUNNO", "CONSTRAINTID", "RHS", "MARGINALVALUE",
                               "VIOLATIONDEGREE", "INTERVENTION", "LASTCHANGED"],
        "DISPATCHLOAD": ["SETTLEMENTDATE", "RUNNO", "DUID", "CONNECTIONPOINTID", "DISPATCHMODE", "AGCSTATUS", "INITIALMW",
                         "TOTALCLEARED", "RAMPDOWNRATE", "RAMPUPRATE", "AVAILABILITY",
                         "INTERVENTION", "LASTCHANGED"],
    }
    for entry in config["files"]:
        if entry["phase"] != "interval":
            continue
        path = download_entry(entry, config["limits"])
        table = entry["table"]
        if table == "DISPATCHCONSTRAINT":
            wanted = set(constraint_ids)
            predicate = lambda row: row.get("CONSTRAINTID", row.get("GENCONID")) in wanted
        elif table == "DISPATCHLOAD":
            wanted = set(duids)
            predicate = lambda row: row.get("DUID") in wanted
        else:
            raise ValueError(f"No scoped filter for interval table {table}")
        frame = _table_rows(path, table, keep=keep[table], value_filter=predicate)
        out = TABLES / f"{table}.parquet"
        frame.to_parquet(out, index=False, compression="zstd")
        outputs[table] = {"rows": len(frame), "columns": list(frame),
                          "filter_values": len(wanted)}
    dump(PILOT / "interval_extraction.json", outputs)
    return outputs


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_expanded_total(paths, limit):
    expanded = 0
    for path in paths:
        with zipfile.ZipFile(path) as archive:
            expanded += sum(member.file_size for member in archive.infolist())
    if expanded > int(limit):
        raise ValueError("Downloaded batch exceeds decompressed-byte cap")
    return expanded


def run(phase="static", config_path=CONFIG):
    config = load_config(config_path)
    audit_manifest(config)
    selected = [x for x in config["files"] if phase == "all" or x["phase"] == "static"]
    paths = [download_entry(x, config["limits"]) for x in selected] if phase != "audit" else []
    if paths:
        validate_expanded_total(paths, config["limits"]["batch_decompressed_bytes"])
    if phase in {"static", "all"}:
        extract_static(config)
    if phase == "all":
        extract_interval(config)
    records = []
    for entry in config["files"]:
        name = unquote(urlparse(entry["url"]).path.rsplit("/", 1)[-1])
        path = RAW / name
        if path.exists():
            records.append({"table": entry["table"], "url": entry["url"],
                            "bytes": path.stat().st_size, "sha256": sha256(path)})
    dump(PILOT / "manifest.json", records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["audit", "static", "all"], default="static", nargs="?")
    parser.add_argument("--config", default=str(CONFIG))
    args = parser.parse_args()
    run(args.phase, args.config)
