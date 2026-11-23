"""Retain original reports and extract the fields needed for the PEC study."""

import csv
import hashlib
import io
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urljoin

import pandas as pd

from nemic.common import DATA, ROOT, get
from nemic.constraint_ingest import _table_rows
from nemic.constraint_longitudinal import archive_url

NEM = timezone(timedelta(hours=10))
START = pd.Timestamp("2026-10-01")
CONNECTOR = "NSW1-SA1"
REGIONS = {"NSW1": "nsw", "SA1": "sa", "VIC1": "vic"}
DATA_DIR = DATA / "pec_limits_v1"
OUTPUT_DIR = ROOT / "local_exports" / "pec_limits_v1"
NEMWEB = "https://nemweb.com.au/"
DISPATCH = "DispatchIS_Reports"
STANDING = ("GENCONDATA", "GENCONSET", "GENCONSETINVOKE", "GENCONSETTRK",
            "SPDINTERCONNECTORCONSTRAINT", "DISPATCHINTERCONNECTORRES", "DISPATCHREGIONSUM")

DISPATCH_FIELDS = {
    "INTERCONNECTORRES": (
        "SETTLEMENTDATE", "INTERCONNECTORID", "RUNNO", "INTERVENTION", "LASTCHANGED",
        "MWFLOW", "METEREDMWFLOW", "EXPORTLIMIT", "IMPORTLIMIT", "EXPORTGENCONID", "IMPORTGENCONID",
        "LOCALLY_CONSTRAINED_EXPORT", "LOCALLY_CONSTRAINED_IMPORT",
    ),
    "REGIONSUM": (
        "SETTLEMENTDATE", "REGIONID", "RUNNO", "INTERVENTION", "LASTCHANGED",
        "TOTALDEMAND", "SS_WIND_CLEAREDMW", "SS_SOLAR_CLEAREDMW",
    ),
    "CONSTRAINT": (
        "SETTLEMENTDATE", "CONSTRAINTID", "RUNNO", "INTERVENTION", "LASTCHANGED", "RHS", "LHS",
        "MARGINALVALUE", "VIOLATIONDEGREE", "GENCONID_EFFECTIVEDATE", "GENCONID_VERSIONNO",
    ),
}


@dataclass(frozen=True)
class Source:
    product: str
    url: str
    path: Path
    local_reuse: bool = False


def last_closed_day() -> pd.Timestamp:
    return pd.Timestamp(datetime.now(NEM).date() - timedelta(days=1))


def listing(period, product):
    url = urljoin(NEMWEB, f"Reports/{period}/{product}/")
    response = get(url)
    return [urljoin(response.url, name) for name in re.findall(r'href="([^"]+)"', response.text, re.I)]


def require_zip(path, blob):
    if path.suffix.lower() == ".zip" and not zipfile.is_zipfile(io.BytesIO(blob)):
        raise ValueError(f"Expected ZIP: {path.name}")


def retain(source):
    path = source.path
    evidence = {
        "product": source.product, "archive": path.name, "source_url": source.url,
        "file": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
        "retained_input": source.local_reuse, "status": "available",
    }
    if not path.is_file():
        response = get(source.url)
        require_zip(path, response.content)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".partial")
        temporary.write_bytes(response.content)
        temporary.replace(path)
    with path.open("rb") as stream:
        evidence["sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    evidence["bytes"] = path.stat().st_size
    return evidence


def dispatch_sources(data_dir, end_day):
    dates = {day.strftime("%Y%m%d") for day in pd.date_range(START, end_day)}
    archives = {
        match[1]: url for url in listing("Archive", DISPATCH)
        if (match := re.search(r"PUBLIC_DISPATCHIS_(\d{8})\.zip$", url)) and match[1] in dates
    }
    sources = []
    for stamp, url in sorted(archives.items()):
        name = f"PUBLIC_DISPATCHIS_{stamp}.zip"
        retained = DATA / "raw" / "pec_dispatch_sample" / name
        sources.append(Source("DispatchIS daily", url, retained if retained.exists() else data_dir / "raw" / "dispatch" / name, retained.exists()))
    for url in listing("Current", DISPATCH):
        match = re.search(r"PUBLIC_DISPATCHIS_(\d{12})_\d+\.zip$", url)
        if match is None:
            continue
        day = (pd.to_datetime(match[1], format="%Y%m%d%H%M") - pd.Timedelta(minutes=1)).strftime("%Y%m%d")
        if day in dates.difference(archives):
            name = url.rsplit("/", 1)[-1]
            sources.append(Source("DispatchIS original", url, data_dir / "raw" / "dispatch" / name))
    return sources


def standing_sources(data_dir):
    sources = []
    october = START.to_period("M")
    for month, tables in [(october, STANDING), (october - 1, STANDING[:-2]), (october - 2, STANDING[:-2])]:
        for table in tables:
            url = archive_url(month, table)
            name = unquote(url.rsplit("/", 1)[-1])
            roots = [DATA / "raw", DATA / "constraint_pilot" / "raw",
                     DATA / "forecast_experiments" / "conditional_regimes_v1" / "raw"]
            cached = next((root / name for root in roots if (root / name).exists()), None)
            sources.append(Source(table, url, cached or data_dir / "raw" / "standing" / name, cached is not None))
    return sources


def acquire_standing(data_dir=DATA_DIR):
    with ThreadPoolExecutor(max_workers=6) as pool:
        audited = list(pool.map(retain, standing_sources(data_dir)))
    index = data_dir / "dispatch_sources.csv"
    if index.exists():
        original = pd.read_csv(index)
        index_rows = original[~original["product"].isin(STANDING)]
        pd.concat([index_rows, pd.DataFrame(audited)], ignore_index=True).to_csv(index, index=False)
    return audited


def members(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        for name in archive.namelist():
            if name.lower().endswith(".zip"):
                yield from members(archive.read(name))
            elif name.lower().endswith(".csv"):
                yield name, archive.read(name)


def read_dispatch(source, cache_dir, direct):
    with source.path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    direct_digest = hashlib.sha256("\n".join(sorted(direct)).encode()).hexdigest()[:12]
    cache = cache_dir / f"dispatch3-{direct_digest}-{digest}"
    if all((cache / f"{table}.parquet").is_file() for table in DISPATCH_FIELDS):
        return {table: pd.read_parquet(cache / f"{table}.parquet") for table in DISPATCH_FIELDS}
    fields = {table: [*columns, "report_created", "report_vintage", "source_archive"] for table, columns in DISPATCH_FIELDS.items()}
    records = {table: [] for table in fields}
    for name, blob in members(source.path.read_bytes()):
        indexes = {}
        lines = list(csv.reader(io.StringIO(blob.decode("utf-8-sig", errors="replace"))))
        wanted = direct.copy()
        for line in lines:
            if line[:3] == ["I", "DISPATCH", "INTERCONNECTORRES"]:
                connector, upper, lower = (line.index(key) for key in ("INTERCONNECTORID", "EXPORTGENCONID", "IMPORTGENCONID"))
            if line[:3] == ["D", "DISPATCH", "INTERCONNECTORRES"] and line[connector] == CONNECTOR:
                wanted.update((line[upper], line[lower]))
        created = None
        for line in lines:
            if line[:3] == ["C", "NEMP.WORLD", "DISPATCHIS"]:
                created = f"{line[5]} {line[6]}"
                continue
            if len(line) < 4 or line[1] != "DISPATCH" or line[2] not in fields:
                continue
            table = line[2]
            if line[0] == "I":
                indexes[table] = {field: (line.index(field) if field in line else None) for field in DISPATCH_FIELDS[table]}
            elif line[0] == "D":
                lookup = indexes[table]
                if table == "INTERCONNECTORRES" and line[lookup["INTERCONNECTORID"]] != CONNECTOR:
                    continue
                if table == "REGIONSUM" and line[lookup["REGIONID"]] not in REGIONS:
                    continue
                if table == "CONSTRAINT" and line[lookup["CONSTRAINTID"]] not in wanted:
                    continue
                records[table].append([line[index] or None if index is not None else None for index in lookup.values()]
                                      + [created, name, source.path.name])
    frames = {table: pd.DataFrame(rows, columns=fields[table]) for table, rows in records.items()}
    cache.mkdir(parents=True, exist_ok=True)
    for table, frame in frames.items():
        path = cache / f"{table}.parquet"
        temporary = path.with_suffix(".partial")
        frame.to_parquet(temporary, index=False, compression="zstd")
        temporary.replace(path)
    return frames


def acquire_dispatch(data_dir=DATA_DIR, end_day=None):
    end_day = last_closed_day() if end_day is None else pd.Timestamp(end_day).normalize()
    if end_day < START or end_day > last_closed_day():
        raise ValueError("End day must be a closed NEM day on or after 1 October 2026")
    dispatch = dispatch_sources(data_dir, end_day)
    standing = standing_sources(data_dir)
    with ThreadPoolExecutor(max_workers=10) as pool:
        audited = list(pool.map(retain, [*dispatch, *standing]))
    print(f"Retained {len(dispatch)} dispatch archives or originals and {len(standing)} monthly tables", flush=True)
    pd.DataFrame(audited).to_csv(data_dir / "dispatch_sources.csv", index=False)
    if not dispatch:
        raise ValueError("NEMWEB returned no dispatch reports for the requested dates")
    factors = next(source.path for source in standing if source.product == "SPDINTERCONNECTORCONSTRAINT")
    direct = set(_table_rows(factors, "SPDINTERCONNECTORCONSTRAINT", keep=["GENCONID"],
                            value_filter=lambda row: row["INTERCONNECTORID"] == CONNECTOR).GENCONID)
    totals = {table: [] for table in DISPATCH_FIELDS}
    for source in dispatch:
        for table, frame in read_dispatch(source, data_dir / "parsed", direct).items():
            if not frame.empty:
                totals[table].append(frame)
    for table, frames in totals.items():
        pd.concat(frames, ignore_index=True).to_parquet(data_dir / f"dispatch_{table.lower()}.parquet", index=False, compression="zstd")
    return end_day
