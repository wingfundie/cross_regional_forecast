"""Bounded preparation of retained long-horizon source evidence."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
import re
import zipfile
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup

from nemic.common import session
from nemic.experiments.core import ROOT, digest
from nemic.fundamentals.sources import _members, nem_time, read_mms


DEFAULT_ROOT = ROOT / "data" / "forecast_experiments" / "qni_vni_fundamentals_v3"
CURRENT_ROOT = ROOT / "data" / "forecast_inputs" / "qni_vni_longrange"


def _parse_mt(raw, source_hash, retrieved_at, horizon_days):
    rows=[];last_generated=None;day_limit=None
    for dataset,table,version,row,generated in read_mms(raw):
        if dataset!='MTPASA' or table!='DUIDAVAILABILITY':continue
        if generated is None:raise ValueError('Missing original MT PASA report timestamp')
        if generated!=last_generated:
            last_generated=generated;day_limit=(generated+pd.Timedelta(days=int(horizon_days))).strftime('%Y-%m-%d')
        if row['DAY'][:10].replace('/','-') > day_limit:continue
        rows.append(dict(product='mtpasa',run_id=row['PUBLISH_DATETIME'],available_at=generated,
            retrieved_at=pd.Timestamp(retrieved_at),day=nem_time(row['DAY']),region=row['REGIONID'],duid=row['DUID'],
            capacity_mw=pd.to_numeric(row.get('PASAAVAILABILITY'),errors='coerce'),
            unit_state=row.get('PASAUNITSTATE'),recall_hours=pd.to_numeric(row.get('PASARECALLTIME'),errors='coerce'),
            source_hash=source_hash,provenance='report_generated_proxy',schema_version=version))
    return pd.DataFrame(rows)


def _daily_members(zipped, expanded_bytes):
    """Read the 18:00 reports used by the following day's 08:00 origin."""
    members = zipped.infolist()
    selected = [member for member in members if re.search(r"_\d{8}1800_", member.filename)]
    if not selected:
        yield from _members(zipped, int(expanded_bytes))
        return
    if sum(member.file_size for member in selected) > int(expanded_bytes):
        raise RuntimeError("Selected expanded archive exceeds configured cap")
    for member in selected:
        if member.filename.lower().endswith(".csv"):
            with zipped.open(member) as raw:
                yield member.filename, raw
        elif member.filename.lower().endswith(".zip"):
            with zipped.open(member) as nested:
                import io
                with zipfile.ZipFile(io.BytesIO(nested.read())) as child:
                    yield from _members(child, int(expanded_bytes), 1)


def _extract_archive(archive, source_root, horizon_days, expanded_bytes):
    """Parse one archive; callers isolate this function so memory returns to the OS."""
    archive = Path(archive)
    source_root = Path(source_root)
    output_root = source_root / f"sources/mtpasa_{int(horizon_days)}d"
    output_root.mkdir(parents=True, exist_ok=True)
    identity = archive.stem
    output = output_root / f"{identity}.parquet"
    metadata = output.with_suffix(".json")
    if output.exists() and metadata.exists():
        cached = json.loads(metadata.read_text(encoding="utf-8"))
        if cached.get("raw_sha256") == digest(archive) and cached.get("horizon_days") == int(horizon_days) \
                and cached.get("aggregation") == "regional-v2" and cached.get("parsed_sha256") == digest(output):
            return cached
    source_meta = source_root / "sources" / "mtpasa" / f"{identity}.json"
    receipt = None
    if source_meta.exists():
        source_payload = json.loads(source_meta.read_text(encoding="utf-8"))
        receipt = source_payload.get("receipt_completed_at") or source_payload.get("retrieved_at")
    receipt = receipt or pd.Timestamp.fromtimestamp(archive.stat().st_mtime, tz="UTC").isoformat()
    frames = []
    sha = digest(archive)
    with zipfile.ZipFile(archive) as zipped:
        for _, raw in _daily_members(zipped, int(expanded_bytes)):
            frame = _parse_mt(raw, sha, receipt, horizon_days=horizon_days)
            if len(frame):
                frames.append(frame)
    if not frames:
        raise ValueError(f"No eligible MT PASA rows in {archive}")
    combined = pd.concat(frames, ignore_index=True).drop_duplicates(
        ["available_at", "day", "region", "duid"], keep="last")
    combined["positive_capacity"] = combined.capacity_mw.gt(0).astype(float)
    combined = (combined.groupby(["available_at", "day", "region"], observed=True)
                .agg(capacity_mw=("capacity_mw", "sum"), unit_count=("duid", "nunique"),
                     positive_capacity_fraction=("positive_capacity", "mean"),
                     mean_recall_hours=("recall_hours", "mean"), source_hash=("source_hash", "first"),
                     receipt_completed_at=("retrieved_at", "first"))
                .reset_index())
    temporary_output = output.with_suffix(output.suffix + ".tmp")
    combined.to_parquet(temporary_output, compression="zstd", index=False)
    temporary_output.replace(output)
    display_root = ROOT if archive.resolve().is_relative_to(ROOT.resolve()) else source_root
    payload = {
        "raw": str(archive.relative_to(display_root)), "raw_sha256": sha,
        "output": str(output.relative_to(display_root)), "parsed_sha256": digest(output),
        "horizon_days": int(horizon_days), "rows": int(len(combined)),
        "aggregation": "regional-v2",
        "run_selection": "daily_1800_for_0800_origin",
        "generated_min": str(combined.available_at.min()), "generated_max": str(combined.available_at.max()),
        "delivery_min": str(combined.day.min()), "delivery_max": str(combined.day.max()),
        "receipt_completed_at": receipt,
        "availability_evidence": "historical_report_generation_proxy",
    }
    temporary_metadata = metadata.with_suffix(metadata.suffix + ".tmp")
    temporary_metadata.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary_metadata.replace(metadata)
    return payload


def _generation_start(source_root, archive):
    metadata = Path(source_root) / "sources" / "mtpasa" / f"{Path(archive).stem}.json"
    if metadata.exists():
        value = json.loads(metadata.read_text(encoding="utf-8")).get("available_min")
        if value:
            return pd.Timestamp(value)
    return pd.Timestamp.fromtimestamp(Path(archive).stat().st_mtime, tz="UTC")


def extract_mtpasa(source_root=DEFAULT_ROOT, horizon_days=90, expanded_bytes=20 * 1024**3,
                   latest_generation=None):
    """Reparse retained original MT PASA ZIPs into an isolated horizon cache."""
    source_root = Path(source_root)
    raw_root = source_root / "raw" / "mtpasa"
    all_archives = sorted(raw_root.glob("*.zip"), key=lambda path: _generation_start(source_root, path))
    cutoff = pd.Timestamp(latest_generation) if latest_generation is not None else None
    if cutoff is not None and cutoff.tzinfo is None:
        raise ValueError("Latest generation cutoff must be timezone aware")
    archives = [path for path in all_archives if cutoff is None or _generation_start(source_root, path) <= cutoff]
    skipped = [{"raw": str(path), "generated_min": str(_generation_start(source_root, path)),
                "reason": "generation after mature-origin cutoff"} for path in all_archives if path not in archives]
    records = []
    # MT PASA XML parsing temporarily allocates gigabytes. A fresh process per
    # archive makes the one-worker memory contract effective on Windows.
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=1, mp_context=context, max_tasks_per_child=1) as pool:
        for archive in archives:
            records.append(pool.submit(_extract_archive, archive, source_root, horizon_days, expanded_bytes).result())
            print(f"completed {len(records)}/{len(archives)}: {records[-1]['generated_min']}", flush=True)
    if not records:
        raise FileNotFoundError(f"No retained MT PASA archives found under {raw_root}")
    output_root = source_root / f"sources/mtpasa_{int(horizon_days)}d"
    manifest = output_root / "manifest.json"
    temporary_manifest = manifest.with_suffix(manifest.suffix + ".tmp")
    temporary_manifest.write_text(json.dumps({"schema": 2, "horizon_days": int(horizon_days),
                                              "latest_generation": str(cutoff) if cutoff is not None else None,
                                              "archives": records, "skipped": skipped}, indent=2), encoding="utf-8")
    temporary_manifest.replace(manifest)
    return manifest


def collect_current(origin, output_root=CURRENT_ROOT, horizon_days=90):
    """Acquire the latest public MT PASA run available at a daily issue time."""
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None:
        raise ValueError("Collection origin must be timezone aware")
    directory = "https://www.nemweb.com.au/Reports/CURRENT/MTPASA_DUIDAvailability/"
    response = session().get(directory, timeout=(15, 60)); response.raise_for_status()
    urls = sorted(set(urljoin(directory, tag["href"]) for tag in BeautifulSoup(response.text, "html.parser").find_all("a", href=True)
                      if tag["href"].lower().endswith(".zip")))
    eligible = []
    for url in urls:
        match = re.search(r"_(\d{12})_", url)
        if match:
            issued = pd.to_datetime(match.group(1), format="%Y%m%d%H%M").tz_localize("Australia/Brisbane")
            if issued <= origin.tz_convert("Australia/Brisbane"):
                eligible.append((issued, url))
    if not eligible:
        raise RuntimeError("No current MT PASA file is available at the requested origin")
    issued, url = max(eligible)
    identity = hashlib.sha256(url.encode()).hexdigest()
    output_root = Path(output_root); raw_root = output_root / "raw/mtpasa"; raw_root.mkdir(parents=True, exist_ok=True)
    archive = raw_root / f"{identity}.zip"; source_meta = output_root / "sources/mtpasa" / f"{identity}.json"
    previous = json.loads(source_meta.read_text(encoding="utf-8")) if source_meta.exists() else {}
    started = pd.Timestamp(previous.get("retrieval_started_at", pd.Timestamp.now(tz="UTC")))
    if not archive.exists():
        download = session().get(url, stream=True, timeout=(20, 120)); download.raise_for_status()
        temporary = archive.with_suffix(".part"); size = 0
        with temporary.open("wb") as handle:
            for chunk in download.iter_content(1024*1024):
                size += len(chunk)
                if size > 600*1024**2:
                    raise RuntimeError("Current MT PASA archive exceeds the 600 MiB cap")
                handle.write(chunk)
        temporary.replace(archive)
        completed = pd.Timestamp.now(tz="UTC")
    else:
        completed = pd.Timestamp(previous.get("receipt_completed_at", pd.Timestamp.fromtimestamp(archive.stat().st_mtime, tz="UTC")))
    source_meta.parent.mkdir(parents=True, exist_ok=True)
    temporary_meta = source_meta.with_suffix(".json.tmp")
    temporary_meta.write_text(json.dumps({"url":url,"issue":str(issued),"retrieval_started_at":str(started),
                                          "receipt_completed_at":str(completed),"raw_sha256":digest(archive)},indent=2),encoding="utf-8")
    temporary_meta.replace(source_meta)
    payload = _extract_archive(archive, output_root, horizon_days, 20*1024**3)
    manifest = output_root / f"sources/mtpasa_{int(horizon_days)}d/manifest.json"
    manifest.write_text(json.dumps({"schema":1,"origin":str(origin),"archive":payload},indent=2),encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract-mtpasa")
    extract.add_argument("--source-root", default=str(DEFAULT_ROOT))
    extract.add_argument("--horizon-days", type=int, default=90)
    extract.add_argument("--latest-generation")
    current = sub.add_parser("collect-current")
    current.add_argument("--origin", required=True); current.add_argument("--output-root", default=str(CURRENT_ROOT))
    current.add_argument("--horizon-days", type=int, default=90)
    args = parser.parse_args()
    if args.command == "extract-mtpasa":
        print(extract_mtpasa(args.source_root, args.horizon_days, latest_generation=args.latest_generation))
    elif args.command == "collect-current":
        print(collect_current(args.origin, args.output_root, args.horizon_days))


if __name__ == "__main__":
    main()
