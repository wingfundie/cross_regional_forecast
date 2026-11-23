"""Original NEMWEB forecast vintages for PEC, with publication evidence."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zipfile import ZipFile

import pandas as pd
import requests

from nemic.common import DATA, get, session

NEM = timezone(timedelta(hours=10))
START = pd.Timestamp("2026-10-01")
BASE = "https://nemweb.com.au/Reports/"
FOLDERS = {
    "predispatch": "CURRENT/PredispatchIS_Reports/",
    "stpasa": "CURRENT/Short_Term_PASA_Reports/",
}
REGIONS = {"NSW1": "nsw", "SA1": "sa", "VIC1": "vic"}
DIRECTIONS = {"nsw_sa": ("SA1", "EXPORT", 1), "sa_nsw": ("NSW1", "IMPORT", -1)}
WEATHER_FIELDS = ("demand", "wind", "solar")
VINTAGE_FEATURES = [f"{region}_{field}_forecast" for region in REGIONS.values()
                    for field in WEATHER_FIELDS]
PRODUCT_FEATURES = ["forecast_n_binding", "forecast_export_rhs", "forecast_import_rhs",
                    "forecast_export_binding", "forecast_import_binding"]
FILE_PATTERN = {
    "predispatch": re.compile(r"PUBLIC_PREDISPATCHIS_\d{12}_\d{14}\.zip"),
    "stpasa": re.compile(r"PUBLIC_STPASA_\d{12}_\d+\.zip"),
}
LISTING_PATTERN = re.compile(
    r"([A-Z][a-z]+ \d{1,2}, \d{4} +\d{1,2}:\d{2} [AP]M) +(\d+) +<A HREF=\"([^\"]+)\"",
    re.I,
)


def schedule(start, end):
    """Return the full scheduled issue grid including origins with missing inputs."""
    updates = pd.date_range(start, end, freq="30min", inclusive="left")
    daily = updates[(updates.hour == 8) & (updates.minute == 0)]
    return {"updates": updates, "daily_0800": daily}


def _timestamp(text):
    return pd.to_datetime(text, format="%Y/%m/%d %H:%M:%S", errors="raise")


def _listing(root, product):
    address = urljoin(BASE, FOLDERS[product])
    response = get(address)
    listing = response.content
    listing_hash = hashlib.sha256(listing).hexdigest()
    (root / f"{product}-listing-{listing_hash[:16]}.html").write_bytes(listing)
    records = []
    for stamp, size, href in LISTING_PATTERN.findall(response.text):
        url = urljoin(address, href)
        name = Path(urlparse(url).path).name
        if not FILE_PATTERN[product].fullmatch(name):
            continue
        published_upper = datetime.strptime(stamp, "%B %d, %Y %I:%M %p") + timedelta(minutes=1)
        records.append({
            "product": product, "vintage": name, "url": url, "bytes_listed": int(size),
            "published_at": pd.Timestamp(published_upper).isoformat(),
            "listing_url": address, "listing_sha256": listing_hash,
            "listing_publication_precision": "upper bound of publisher's displayed NEM minute",
        })
    return sorted(records, key=lambda row: row["published_at"])


def _select_downloads(records, origins, max_age_hours):
    """Keep files with a possible eligible origin without downloading every PASA hour."""
    selected = {}
    for record in records:
        published = pd.Timestamp(record["published_at"])
        loc = origins.searchsorted(published, side="left")
        if loc < len(origins) and origins[loc] - published <= pd.Timedelta(hours=max_age_hours):
            selected[record["vintage"]] = record
    return selected


def _cached_records(root):
    records = []
    for path in root.glob("PUBLIC_*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        name = record["vintage"]
        if (root / name).is_file():
            records.append(record)
    return records


def _capture(root, record):
    name = record["vintage"]
    path = root / name
    meta = path.with_suffix(".json")
    if meta.exists() and path.is_file():
        return json.loads(meta.read_text(encoding="utf-8"))
    with session() as client:
        for attempt in range(3):
            try:
                response = client.get(record["url"], timeout=(20, 90))
                response.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
    payload = response.content
    with ZipFile(io.BytesIO(payload)) as source:
        if len(source.infolist()) != 1 or source.testzip() is not None:
            raise ValueError(f"Invalid original format in {name}")
    if len(payload) != record["bytes_listed"]:
        raise ValueError(f"Publisher listed a different byte count for {name}")
    http_time = response.headers.get("Last-Modified")
    if not http_time:
        raise ValueError(f"No publisher Last-Modified timestamp for {name}")
    modified = parsedate_to_datetime(http_time).astimezone(NEM).replace(tzinfo=None)
    listed_upper = pd.Timestamp(record["published_at"])
    if not listed_upper - pd.Timedelta(minutes=1) <= modified < listed_upper:
        raise ValueError(f"Publisher listing and HTTP timestamp disagree for {name}")
    temporary = path.with_suffix(".partial")
    temporary.write_bytes(payload)
    temporary.replace(path)
    result = {
        **record, "http_last_modified": modified.isoformat(),
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    meta_temp = meta.with_suffix(".json.partial")
    meta_temp.write_text(json.dumps(result, indent=2), encoding="utf-8")
    meta_temp.replace(meta)
    return result


def acquire(root, start, end, workers=8):
    """Capture only current pre-dispatch/update and PASA/daily-compatible originals."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    existing = {row["vintage"]: row for row in _cached_records(root)}
    origins = schedule(start, end)
    # Initialise the platform CA bundle before concurrent downloads.
    with session():
        pass
    new = {}
    for product, name, max_age in (("predispatch", "updates", 1.5), ("stpasa", "daily_0800", 3)):
        new.update(_select_downloads(_listing(root, product), origins[name], max_age))
    pending = [row for name, row in new.items() if name not in existing]
    if pending:
        print(f"Capturing {len(pending)} original forecast vintages", flush=True)
        failures = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [(row["vintage"], pool.submit(_capture, root, row)) for row in pending]
            for index, (name, future) in enumerate(futures, start=1):
                try:
                    future.result()
                except (ValueError, requests.RequestException) as exc:
                    failures.append({"vintage": name, "error": str(exc)})
                if index % 100 == 0 or index == len(pending):
                    print(f"Checked {index}/{len(pending)} vintages ({len(failures)} failures)", flush=True)
        (root / "capture_failures.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")
        if failures:
            print(f"See {root / 'capture_failures.json'} for the source failures", flush=True)
    return _cached_records(root)


def _archive_record(root, url, archive):
    name = Path(urlparse(url).path).name
    path = root / name
    if not path.exists():
        with session() as client, client.get(url, stream=True, timeout=(20, 180)) as response:
            response.raise_for_status()
            temporary = path.with_suffix(".partial")
            with temporary.open("wb") as binary:
                for chunk in response.iter_content(1024 * 1024):
                    binary.write(chunk)
            with ZipFile(temporary) as container:
                if not container.infolist():
                    raise ValueError(f"Empty weekly forecast archive {url}")
            temporary.replace(path)
    with path.open("rb") as stored:
        digest = hashlib.file_digest(stored, "sha256").hexdigest()
    return path, {"url": url, "archive": archive, "archive_sha256": digest}


def acquire_proxy(root, start, end):
    """Acquire weekly original issues whose historic public release is unverified."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    index_url = urljoin(BASE, "ARCHIVE/PredispatchIS_Reports/")
    listing = get(index_url)
    weekly = []
    for _, _, href in LISTING_PATTERN.findall(listing.text):
        url = urljoin(index_url, href)
        archive = Path(urlparse(url).path).name
        dates = re.fullmatch(r"PUBLIC_PREDISPATCHIS_(\d{8})_(\d{8})\.zip", archive)
        if dates:
            first, last = (pd.Timestamp(item) for item in dates.groups())
            if first < end and last >= start:
                weekly.append((url, archive))
    with ThreadPoolExecutor(max_workers=4) as pool:
        files = list(pool.map(lambda pair: _archive_record(root, *pair), weekly))
    rows = []
    for path, info in files:
        with ZipFile(path) as container:
            for entry in container.infolist():
                if not FILE_PATTERN["predispatch"].fullmatch(entry.filename):
                    continue
                archive_timestamp = pd.Timestamp(datetime(*entry.date_time))
                proxy = archive_timestamp + pd.Timedelta(minutes=10)
                if not start <= proxy < end:
                    continue
                rows.append({
                    **info, "vintage": entry.filename, "product": "predispatch_proxy",
                    "archive_member_time": archive_timestamp.isoformat(),
                    "published_at": proxy.isoformat(),
                    "listing_publication_precision": "proxy from archive member mtime plus 10 minutes",
                })
    (root / "weekly_proxy_index.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"Indexed {len(rows)} explicitly unverified archival pre-dispatch vintages", flush=True)


def _read(raw, name, digest, product):
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"Forecast source hash changed for {name}")
    if product.startswith("predispatch"):
        prefix = "PREDISPATCH"
        names = ("REGION_SOLUTION", "INTERCONNECTOR_SOLN", "CONSTRAINT_SOLUTION")
    else:
        prefix = "STPASA"
        names = ("REGIONSOLUTION", "INTERCONNECTORSOLN", "CONSTRAINTSOLUTION")
    time_field = "DATETIME" if product.startswith("predispatch") else "INTERVAL_DATETIME"
    frames = {key: [] for key in names}
    vintages = set()
    with ZipFile(io.BytesIO(raw)) as source:
        lines = source.read(source.namelist()[0]).splitlines()
    header = next(csv.reader([lines[0].decode("utf-8-sig")]))
    selected = (names[1],) if product.endswith("_proxy") else names
    prefixes = tuple(f"{kind},{prefix},{key},".encode() for key in selected for kind in ("I", "D"))
    sections = {key: [] for key in selected}
    schemas = {}
    for line in lines[1:]:
        if line.startswith(prefixes):
            row_type, _, key, version, data = line.split(b",", 4)
            table = key.decode()
            if row_type == b"I":
                schemas[table, version] = data.decode().split(",")
            else:
                sections[table].append((version, data))

    setter_names = set()
    run_fields = ("RUN_DATETIME",) if product == "stpasa" else ("PREDISPATCHSEQNO", "RUNNO")
    setters = ("EXPORTLIMITCONSTRAINTID", "IMPORTLIMITCONSTRAINTID") if product == "stpasa" else (
        "EXPORTGENCONID", "IMPORTGENCONID",
    )
    limits = ("CALCULATEDEXPORTLIMIT", "CALCULATEDIMPORTLIMIT") if product == "stpasa" else (
        "EXPORTLIMIT", "IMPORTLIMIT",
    )
    demand = "DEMAND50" if product == "stpasa" else "TOTALDEMAND"
    rhs = "CAPACITYRHS" if product == "stpasa" else "RHS"
    marginal = "CAPACITYMARGINALVALUE" if product == "stpasa" else "MARGINALVALUE"
    columns = {
        names[0]: ("REGIONID", time_field, demand, "SS_WIND_UIGF", "SS_SOLAR_UIGF"),
        names[1]: (time_field, "STUDYREGIONID", *limits, *setters),
        names[2]: (time_field, "CONSTRAINTID", "STUDYREGIONID", rhs, marginal),
    }
    region_filter = {f",{region},".encode() for region in REGIONS}
    for table in selected:
        lookup = {version: {field: index for index, field in enumerate(schema)}
                  for (key, version), schema in schemas.items() if key == table}
        only = (columns[table], run_fields)
        for version, data in sections[table]:
            if table == names[0] and not any(region in data for region in region_filter):
                continue
            if table == names[1] and b",NSW1-SA1," not in data:
                continue
            index = lookup[version]
            if b'"' in data:
                fields = next(csv.reader([data.decode()]))
            else:
                fields = data.decode().split(",")
            if product == "stpasa":
                if fields[index["RUNTYPE"]] != "LOR":
                    continue
            elif fields[index["INTERVENTION"]] != "0":
                continue
            if table == names[2]:
                multiplier = fields[index[marginal]]
                if fields[index["CONSTRAINTID"]] not in setter_names and (
                    not multiplier or abs(float(multiplier)) <= 1e-6
                ):
                    continue
            vintages.add(tuple(fields[index[field]] for field in only[1]))
            item = {field: fields[index[field]] for field in only[0] if field in index}
            if table == names[1]:
                setter_names.update(item[field] for field in setters if item.get(field))
            frames[table].append(item)
    if header[:1] != ["C"] or header[2] != ("PREDISPATCHIS" if product.startswith("predispatch") else "STPASA"):
        raise ValueError(f"Unexpected source header in {name}")
    if len(vintages) > 1:
        raise ValueError(f"Mixed run keys in the original report {name}")
    issued_at = _timestamp(f"{header[5]} {header[6]}")
    market_run = "/".join(map(str, next(iter(vintages), ())))
    return issued_at, market_run, *(pd.DataFrame(frames[key]) for key in names)


def _num(frame, field):
    if field in frame:
        return pd.to_numeric(frame[field], errors="coerce")
    return pd.Series(float("nan"), index=frame.index)


def _coherent_regions(regions, time_field, product):
    if regions.empty:
        return pd.DataFrame(columns=VINTAGE_FEATURES, index=pd.DatetimeIndex([], name="time"))
    regional_fields = {
        "demand": "TOTALDEMAND" if product.startswith("predispatch") else "DEMAND50",
        "wind": "SS_WIND_UIGF", "solar": "SS_SOLAR_UIGF",
    }
    regional = regions[[time_field, "REGIONID"]].copy()
    regional["time"] = _timestamp(regional.pop(time_field))
    for field, source in regional_fields.items():
        regional[field] = _num(regions, source)
    regional = regional.drop_duplicates()
    conflict = regional.duplicated(["time", "REGIONID"], keep=False)
    regional = regional.loc[~regional["time"].isin(regional.loc[conflict, "time"])]
    wide = regional.pivot(index="time", columns="REGIONID", values=list(regional_fields))
    wide.columns = [f"{REGIONS[region]}_{field}_forecast" for field, region in wide.columns]
    return wide.reindex(columns=VINTAGE_FEATURES).sort_index()


def _direct_and_constraints(links, constraints, time_field, product):
    out = []
    for direction, (importer, side, sign) in DIRECTIONS.items():
        if links.empty:
            continue
        if product == "stpasa":
            relevant = links[links["STUDYREGIONID"].eq(importer)].copy()
            solution = (constraints[constraints["STUDYREGIONID"].eq(importer)]
                        if not constraints.empty else constraints)
            limit, setter, rhs, marginal = (
                f"CALCULATED{side}LIMIT", f"{side}LIMITCONSTRAINTID", "CAPACITYRHS", "CAPACITYMARGINALVALUE"
            )
        else:
            relevant = links.copy()
            solution = constraints
            limit, setter, rhs, marginal = f"{side}LIMIT", f"{side}GENCONID", "RHS", "MARGINALVALUE"
        forecast = relevant[[time_field]].rename(columns={time_field: "raw_delivery"})
        forecast[direction] = sign * _num(relevant, limit)
        forecast[f"predicted_{side.lower()}_setter"] = relevant[setter].replace("", None)
        forecast = forecast.drop_duplicates()
        forecast = forecast.drop_duplicates("raw_delivery", keep=False)
        forecast["time"] = _timestamp(forecast["raw_delivery"])
        forecast = forecast.set_index("time").drop(columns="raw_delivery")
        if not solution.empty:
            constraint = solution[[time_field, "CONSTRAINTID"]].copy()
            constraint["rhs"] = _num(solution, rhs)
            constraint["binding"] = _num(solution, marginal).abs().gt(1e-6).astype(float)
            constraint = constraint.drop_duplicates()
            binding = constraint.groupby(time_field)["binding"].sum().rename(f"{side.lower()}_n_binding")
            binding.index = _timestamp(binding.index.to_series()).to_numpy()
            constraint = constraint.drop_duplicates([time_field, "CONSTRAINTID"], keep=False)
            constraint["time"] = _timestamp(constraint.pop(time_field))
            forecast = forecast.reset_index().merge(
                constraint, left_on=["time", f"predicted_{side.lower()}_setter"],
                right_on=["time", "CONSTRAINTID"], how="left", validate="one_to_one",
            ).drop(columns="CONSTRAINTID").set_index("time")
            forecast = forecast.rename(columns={
                "rhs": f"forecast_{side.lower()}_rhs", "binding": f"forecast_{side.lower()}_binding"
            }).join(binding)
        out.append(forecast)
    if not out:
        return pd.DataFrame()
    wide = pd.concat(out, axis=1)
    binding_counts = wide.reindex(columns=["export_n_binding", "import_n_binding"])
    wide["forecast_n_binding"] = binding_counts.mean(axis=1)
    return wide.drop(columns=list(binding_counts), errors="ignore")


def parse_vintage(root, record, raw=None):
    """Convert a single hashed file to coherent regional and directional delivery rows."""
    product = record["product"]
    name = record["vintage"]
    raw = (Path(root) / name).read_bytes() if raw is None else raw
    issued, market_run, regions, links, constraints = _read(raw, name, record["sha256"], product)
    time_field = "DATETIME" if product.startswith("predispatch") else "INTERVAL_DATETIME"
    wide = _coherent_regions(regions, time_field, product)
    direct = _direct_and_constraints(links, constraints, time_field, product)
    if not direct.empty:
        wide = wide.join(direct, how="outer")
    wide = wide.reindex(columns=[*VINTAGE_FEATURES, *DIRECTIONS, *PRODUCT_FEATURES,
                                "predicted_export_setter", "predicted_import_setter"])
    wide["time"] = wide.index
    wide["product"] = product
    wide["issued_at"] = issued
    wide["market_run"] = market_run
    published_at = pd.Timestamp(record["published_at"])
    if issued > pd.Timestamp(record.get("http_last_modified", published_at)):
        raise ValueError(f"Original report issue is later than publisher modification for {record['vintage']}")
    wide["published_at"] = published_at
    wide["vintage"] = record["vintage"]
    wide["source_sha256"] = record["sha256"]
    return wide.reset_index(drop=True)


def _parse_batch(root, records, archive=None):
    """Normalize a disjoint group of originals for process-based parallel reads."""
    if archive is None:
        return pd.concat([parse_vintage(root, row) for row in records], ignore_index=True), records
    parts = []
    with ZipFile(root / archive) as container:
        for row in records:
            raw = container.read(row["vintage"])
            row["sha256"] = hashlib.sha256(raw).hexdigest()
            parts.append(parse_vintage(root, row, raw))
    return pd.concat(parts, ignore_index=True), records


def _catalog(root):
    records = sorted(_cached_records(root), key=lambda item: item["vintage"])
    archives = []
    proxy_path = root / "weekly_proxy_index.json"
    if proxy_path.exists():
        proxy = pd.DataFrame(json.loads(proxy_path.read_text(encoding="utf-8")))
        if not proxy.empty:
            archives = [(archive, group.to_dict("records")) for archive, group in proxy.groupby("archive")]
    return records, archives


def read_sources(root, workers=1):
    root = Path(root)
    records, archives = _catalog(root)
    if not records and not archives:
        return pd.DataFrame(), pd.DataFrame()
    parser = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    catalogo = json.dumps([records, archives], sort_keys=True).encode()
    version = hashlib.sha256(parser.encode() + catalogo).hexdigest()[:20]
    panel = root / f"forecast_rows_{version}.parquet"
    catalog = root / f"forecast_sources_{version}.parquet"
    if panel.exists() and catalog.exists():
        return pd.read_parquet(panel), pd.read_parquet(catalog)
    jobs = [(root, records[i:i + 25], None) for i in range(0, len(records), 25)]
    jobs.extend((root, group, archive) for archive, group in archives)
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = [pool.submit(_parse_batch, *job) for job in jobs]
            batches = []
            for index, result in enumerate(results, 1):
                batches.append(result.result())
                if index % 4 == 0 or index == len(results):
                    print(f"Normalized {index}/{len(results)} forecast batches", flush=True)
    else:
        batches = []
        for index, job in enumerate(jobs, 1):
            batches.append(_parse_batch(*job))
            if index % 4 == 0 or index == len(jobs):
                print(f"Normalized {index}/{len(jobs)} forecast batches", flush=True)
    parts = [part for part, _ in batches]
    sources = [entry for _, batch in batches for entry in batch]
    rows = pd.concat(parts, ignore_index=True)
    sources = pd.DataFrame(sources).merge(
        rows[["product", "vintage", "issued_at", "market_run"]].drop_duplicates(),
        on=["product", "vintage"], how="left", validate="one_to_one",
    )
    for frame, path in ((rows, panel), (sources, catalog)):
        temporary = path.with_suffix(".partial")
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)
    return rows, sources


def audit_archived_timestamps(root, sources):
    """Compare archived member timestamps with independently visible originals."""
    root = Path(root)
    proxy_index = root / "weekly_proxy_index.json"
    if not proxy_index.exists() or sources.empty:
        return pd.DataFrame()
    archived = pd.DataFrame(json.loads(proxy_index.read_text(encoding="utf-8")))
    if archived.empty:
        return pd.DataFrame()
    current = sources.loc[sources["product"].eq("predispatch"),
                          ["vintage", "http_last_modified", "sha256"]].set_index("vintage")
    matches = []
    for archive, record in archived.groupby("archive"):
        with ZipFile(root / archive) as container:
            for entry in container.infolist():
                if entry.filename not in current.index:
                    continue
                reference = current.loc[entry.filename]
                member_time = pd.Timestamp(datetime(*entry.date_time))
                publication = pd.Timestamp(reference["http_last_modified"])
                matches.append({
                    "archive": archive, "archive_sha256": record["archive_sha256"].iloc[0],
                    "vintage": entry.filename, "archive_member_time_nem": member_time,
                    "published_http_last_modified_nem": publication,
                    "publisher_lag_seconds": (publication - member_time).total_seconds(),
                    "same_archive_and_current_bytes": hashlib.sha256(container.read(entry)).hexdigest()
                    == reference["sha256"],
                })
    return pd.DataFrame(matches)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default=str(START.date()))
    parser.add_argument("--end", default=str(datetime.now(NEM).date()))
    parser.add_argument("--output", type=Path, default=DATA / "pec_limits_v1" / "issued")
    parser.add_argument("--archive-proxy-through", type=pd.Timestamp)
    parser.add_argument("--normalize-only", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.normalize_only:
        vintages, files = read_sources(args.output, workers=args.workers)
        print(f"Normalized {len(vintages)} delivery rows from {len(files)} vintages", flush=True)
    else:
        acquire(args.output, pd.Timestamp(args.start), pd.Timestamp(args.end))
        if args.archive_proxy_through is not None:
            acquire_proxy(args.output, pd.Timestamp(args.start), args.archive_proxy_through)
