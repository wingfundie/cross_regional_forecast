"""Acquire and date the outage and market records behind PEC configurations."""

import csv
import hashlib
import io
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from nemic.event_supplement import RangeReader

from .sources import DATA_DIR, START, Source, last_closed_day, listing, members, retain

NETWORK_PRODUCT = "Network"
NOTICE_IDS = {"146007", "146031", "146032", "146094", "146187"}
MATCH_EQUIPMENT = r"BUNDEY|BUNDAY|BURONGA|DINAWAN|WENTWORTH|WAGGA|(?:^|[^0-9A-Z])6[CFGHI](?:[^0-9A-Z]|$)"


def network_timestamp(name):
    match = re.search(r"PUBLIC_NETWORK_(\d{14})_\d+\.zip$", name, re.I)
    return pd.to_datetime(match[1], format="%Y%m%d%H%M%S") if match else None


def read_network(data, snapshot, snapshot_name):
    rows = {"OUTAGEDETAIL": [], "OUTAGECONSTRAINTSET": []}
    for _, blob in members(data):
        layouts = {}
        for line in csv.reader(io.StringIO(blob.decode("utf-8-sig", errors="replace"))):
            if len(line) < 4 or line[1] != "NETWORK" or line[2] not in rows:
                continue
            table = line[2]
            if line[0] == "I":
                layouts[table] = line[4:]
            elif line[0] == "D":
                row = dict(zip(layouts[table], line[4:]))
                row.update(snapshot=snapshot, network_source=snapshot_name)
                rows[table].append(row)
    return {table: pd.DataFrame(records) for table, records in rows.items()}


def stage_archive(url, end_day, data_dir):
    parent = url.rsplit("/", 1)[-1]
    path = data_dir / "raw" / "network" / Path(parent).stem
    path.mkdir(parents=True, exist_ok=True)
    manifest = path / "members.csv"
    if manifest.exists():
        return pd.read_csv(manifest, keep_default_na=False).to_dict("records")
    range_config = dict(root=data_dir, base_study_dir="pec_limits_no_base", disk_cap_bytes=18 * 10**9,
                        min_free_bytes=5 * 10**9)
    selected = {}
    reader = RangeReader(url, range_config)
    with zipfile.ZipFile(reader) as archive:
        for name in sorted(archive.namelist()):
            snapshot = network_timestamp(name)
            if snapshot is not None and START <= snapshot.normalize() <= end_day:
                selected[snapshot.normalize()] = (name, snapshot)
        records = []
        for name, snapshot in selected.values():
            child = path / Path(name).name
            if not child.is_file():
                content = archive.read(name)
                child.write_bytes(content)
            records.append(dict(product="NOS archive member", archive=child.name, container=parent,
                                source_url=url, file=str(child), snapshot=str(snapshot), status="available",
                                bytes=child.stat().st_size, sha256=hashlib.sha256(child.read_bytes()).hexdigest()))
    if records:
        pd.DataFrame(records).to_csv(manifest, index=False)
    return records


def acquire_network(data_dir=DATA_DIR, end_day=None):
    end_day = last_closed_day() if end_day is None else pd.Timestamp(end_day).normalize()
    archive_urls = sorted(url for url in listing("Archive", NETWORK_PRODUCT)
                          if (match := re.search(r"PUBLIC_NETWORK_(\d{8})\.zip$", url))
                          and START - pd.Timedelta(days=7) < pd.Timestamp(match[1]) <= end_day)
    current = {}
    for url in sorted(listing("Current", NETWORK_PRODUCT)):
        snapshot = network_timestamp(url)
        if snapshot is not None and START <= snapshot.normalize() <= end_day:
            current[snapshot.normalize()] = (url, snapshot)
    notice_urls = [url for url in listing("Current", "Market_Notice")
                   if (match := re.search(r"MKTNOTICE_(\d{8})\.R(\d+)$", url, re.I))
                   and (match[1] == "20261001" or match[2] in NOTICE_IDS)]
    requests = [Source("NOS original", url, data_dir / "raw" / "network" / url.rsplit("/", 1)[-1])
                for url, _ in current.values()]
    requests.extend(Source("AEMO market notice", url, data_dir / "raw" / "notices" / url.rsplit("/", 1)[-1])
                    for url in notice_urls)
    with ThreadPoolExecutor(max_workers=7) as pool:
        archive_records = pool.map(lambda url: stage_archive(url, end_day, data_dir), archive_urls)
        direct_records = list(pool.map(retain, requests))
        records = [record for batch in archive_records for record in batch]
    for source, record in zip(requests, direct_records):
        record["file"] = str(source.path)
        if source.product == "NOS original":
            record["snapshot"] = str(network_timestamp(source.path.name))
    records.extend(direct_records)
    records = pd.DataFrame(records)
    records.to_csv(data_dir / "network_sources.csv", index=False)
    print(f"Retained {records.snapshot.notna().sum()} NOS snapshots and {len(notice_urls)} primary notices", flush=True)


def outage_records(source_manifest):
    details, sets = [], []
    for source in source_manifest.dropna(subset=["snapshot"]).itertuples(index=False):
        tables = read_network(Path(source.file).read_bytes(), pd.Timestamp(source.snapshot), source.archive)
        detail = tables["OUTAGEDETAIL"]
        if not detail.empty:
            details.append(detail)
        links = tables["OUTAGECONSTRAINTSET"]
        if not links.empty:
            sets.append(links)
    if not details or not sets:
        raise ValueError("No NOS outage and constraint-set records were decoded")
    details = pd.concat(details, ignore_index=True).sort_values("snapshot")
    highlight = details[["SUBSTATIONID", "EQUIPMENTID", "ELEMENTID"]].fillna("").agg(" ".join, axis=1)
    details["pec_equipment_hint"] = highlight.str.upper().str.contains(MATCH_EQUIPMENT, regex=True)
    details["actual_start"] = pd.to_datetime(details.ACTUAL_STARTTIME, errors="coerce")
    details["actual_end"] = pd.to_datetime(details.ACTUAL_ENDTIME, errors="coerce")
    # Prefer documented actual start/end from the same snapshot. Planned times are retained for audit.
    details = details.sort_values(["OUTAGEID", "snapshot"]).drop_duplicates("OUTAGEID", keep="last")
    link_rows = pd.concat(sets, ignore_index=True).sort_values("snapshot").drop_duplicates(
        ["OUTAGEID", "GENCONSETID"], keep="last")
    combined = details.merge(link_rows, on="OUTAGEID", how="left", suffixes=("", "_set"))
    combined["set_start"] = pd.to_datetime(combined.STARTINTERVAL, errors="coerce")
    combined["set_end"] = pd.to_datetime(combined.ENDINTERVAL, errors="coerce")
    return combined


def notice_records(source_manifest):
    records = []
    for source in source_manifest[source_manifest["product"].eq("AEMO market notice")].itertuples(index=False):
        body = Path(source.file).read_bytes().decode("cp1252", errors="replace")
        date = re.search(r"Creation Date\s*:\s*(\d\d/\d\d/\d{4})\s+(\d\d:\d\d:\d\d)", body)
        reference = re.search(r"External Reference\s*:\s*(.+)", body)
        records.append(dict(notice_id=source.archive.rsplit(".R", 1)[-1],
                            published_at=pd.to_datetime(" ".join(date.groups()), format="%d/%m/%Y %H:%M:%S"),
                            subject=reference[1].strip() if reference else "", source_url=source.source_url,
                            sha256=source.sha256, pec_related=bool(re.search(r"NSW1[-_]SA1|BUNDEY|BUNDAY|BURONGA|ENERGYCONNECT|PEC STAGE", body, re.I))))
    return pd.DataFrame(records)


def observed_outages(five, active, outages):
    active_sets = set(active.GENCONSETID.dropna())
    eligible = outages[outages.actual_start.notna() & (outages.pec_equipment_hint | outages.GENCONSETID.isin(active_sets))]
    matches = []
    for outage in eligible.itertuples(index=False):
        # Actual times may precede the first dispatch solution. Require a complete known actual
        # window or a snapshot recording the already-started outage, and avoid projecting forward.
        last_known = outage.actual_end if pd.notna(outage.actual_end) else outage.snapshot
        times = five.loc[five.time.gt(outage.actual_start) & five.time.le(last_known), "time"]
        if pd.notna(outage.set_start):
            times = times[times.ge(outage.set_start)]
        if pd.notna(outage.set_end):
            times = times[times.le(outage.set_end)]
        grid = pd.DataFrame({"time": times, "outage_id": outage.OUTAGEID, "outage_set": outage.GENCONSETID,
                             "equipment": outage.EQUIPMENTID, "pec_equipment_hint": outage.pec_equipment_hint})
        if not outage.pec_equipment_hint:
            set_times = active.loc[active.GENCONSETID.eq(outage.GENCONSETID), "time"]
            grid = grid[grid.time.isin(set_times)]
        if not grid.empty:
            matches.append(grid)
    columns = ["time", "outage_id", "outage_set", "equipment", "pec_equipment_hint"]
    return pd.concat(matches, ignore_index=True).drop_duplicates() if matches else pd.DataFrame(columns=columns)
