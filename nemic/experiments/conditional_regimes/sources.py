"""Bounded acquisition: required MMS tables, original daily reports and weather only."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import json
from pathlib import Path
import re
from urllib.parse import unquote, urljoin
import zipfile

import pandas as pd
from bs4 import BeautifulSoup

from nemic.common import session
from nemic.ingest import archive_dir
from .common import DATA, ROOT, config, digest, now, stage, write_json

IDENTITY = {("DISPATCH", "INTERCONNECTORRES"): "DISPATCHINTERCONNECTORRES",
            ("DISPATCH", "REGIONSUM"): "DISPATCHREGIONSUM",
            ("NETWORK", "OUTAGEDETAIL"): "NETWORK_OUTAGEDETAIL",
            ("NETWORK", "OUTAGECONSTRAINTSET"): "NETWORK_OUTAGECONSTRAINTSET"}


def listing(url):
    r = session().get(url, timeout=(10, config()["source_timeout_seconds"]))
    r.raise_for_status()
    return [urljoin(url, a["href"]) for a in BeautifulSoup(r.text, "html.parser").find_all("a", href=True)]


def download(url):
    p = DATA / "raw" / unquote(url.rsplit("/", 1)[-1])
    p.parent.mkdir(parents=True, exist_ok=True)
    meta = p.with_suffix(p.suffix + ".json")
    if p.exists() and meta.exists():
        old = json.loads(meta.read_text())
        if digest(p) == old["sha256"]:
            return p, old
    started = now()
    count = 0
    with session().get(url, stream=True, timeout=(15, 45)) as r:
        r.raise_for_status()
        tmp = p.with_suffix(".partial")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                count += len(chunk)
                if count > config()["download_max_mb"] * 1_000_000:
                    raise ValueError("Per-file download cap exceeded")
                f.write(chunk)
        with zipfile.ZipFile(tmp) as z:
            if not z.namelist():
                raise ValueError("Empty source archive")
        tmp.replace(p)
    record = {"url": url, "bytes": count, "sha256": digest(p), "retrieval_started": started,
              "receipt_completed": now(), "availability_evidence": "retrieved_today_not_historical_receipt"}
    write_json(meta, record)
    return p, record


def csv_members(path):
    with zipfile.ZipFile(path) as z:
        for member in z.infolist():
            if member.filename.lower().endswith(".zip"):
                yield from csv_members(io.BytesIO(z.read(member)))
            elif member.filename.lower().endswith(".csv"):
                yield z.read(member)


def parse_tables(path, wanted):
    frames = {t: [] for t in wanted}
    for content in csv_members(path):
        schemas, rows = {}, {}
        for row in csv.reader(io.StringIO(content.decode("utf-8-sig"))):
            if len(row) < 4 or row[0] not in {"I", "D"}:
                continue
            filename = str(getattr(path, "name", ""))
            declared = next((t for t in wanted if "#" + t + "#" in filename), None)
            table = declared or IDENTITY.get((row[1], row[2]), row[2] if row[2] in wanted else row[1] + "_" + row[2])
            if table not in wanted:
                continue
            key = (table, row[3])
            if row[0] == "I":
                schemas[key] = row[4:]
            elif key in schemas:
                n = len(schemas[key])
                values = row[4:]
                if len(values) != n:
                    raise ValueError(f"Malformed source row in {table}: {len(values)} != {n}")
                rows.setdefault(key, []).append(values)
        for key, records in rows.items():
            frames[key[0]].append(pd.DataFrame(records, columns=schemas[key]))
    return {table: pd.concat(parts, ignore_index=True) for table, parts in frames.items() if parts}


def inventory():
    import pyarrow.parquet as pq
    with stage("inventory") as artifacts:
        paths = [ROOT / x for x in ["data/processed/targets.parquet", "data/processed/drivers.parquet",
                 "data/nos_regime_v1/tables_panel_cache.parquet", "data/nos_regime_v1/family_coverage_30min.parquet",
                 "data/nos_regime_v1/episodes.parquet", "data/nos_regime_v1/episode_sets.parquet",
                 "data/nos_regime_v1/outage_keys.parquet", "data/nos_regime_v1/k5_electrical.parquet"]]
        rows = []
        for path in paths:
            if not path.exists():
                raise FileNotFoundError(path)
            rows.append({"path": str(path.relative_to(ROOT)), "rows": pq.ParquetFile(path).metadata.num_rows,
                         "bytes": path.stat().st_size, "sha256": digest(path)})
        report = {"as_of": config()["as_of"], "sources": rows, "requested_cutoff": config()["requested_data_end"],
                  "retained_detail_end": "2026-09-01T00:00:00+10:00", "running_owner": "exclusive current campaign process"}
        out = DATA / "inventory.json"
        write_json(out, report)
        artifacts.append(out)
        print("Inventory verified", len(rows), "retained artifacts", flush=True)


def acquire():
    """Extend to completed days; absent October invocation is unknown, never clear."""
    with stage("acquire", [DATA / "inventory.json"]) as artifacts:
        c = config()
        wanted = {"DISPATCHINTERCONNECTORRES", "DISPATCHREGIONSUM", "GENCONSETINVOKE",
                  "NETWORK_OUTAGEDETAIL", "NETWORK_OUTAGECONSTRAINTSET", "GENCONSET",
                  "SPDINTERCONNECTORCONSTRAINT"}
        urls, failures, records = [], [], []
        for month in (pd.Timestamp("2026-09-01"), pd.Timestamp("2026-10-01")):
            url = archive_dir(month)
            try:
                links = listing(url)
                urls.extend((link, wanted) for link in links if any("#" + t + "#" in unquote(link) for t in wanted))
            except Exception as exc:
                failures.append({"source": url, "reason": str(exc), "interpretation": "Monthly archive not available"})
        # Daily originals supply only the missing current month, not duplicate September.
        archived_days = set()
        for folder in ("Archive", "Current"):
            base = f"https://nemweb.com.au/Reports/{folder}/DispatchIS_Reports/"
            try:
                for link in listing(base):
                    m = re.search(r"PUBLIC_DISPATCHIS_(\d{8})(?:\d{4,6}.*)?\.zip$", link, re.I)
                    is_needed = m and "20261001" <= m[1] <= "20261025"
                    if is_needed and folder == "Current" and m[1] in archived_days:
                        continue
                    if is_needed and m[1] == "20261025" and not re.search(r"202610250000_", link):
                        continue
                    if is_needed:
                        urls.append((link, {"DISPATCHINTERCONNECTORRES", "DISPATCHREGIONSUM"}))
                        if folder == "Archive":
                            archived_days.add(m[1])
            except Exception as exc:
                failures.append({"source": base, "reason": str(exc)})
        # Current folder has many same-day dispatch files. Only requested complete day 24 is needed.
        unique = {}
        for url, tables in urls:
            name = unquote(url.rsplit("/", 1)[-1])
            if "PUBLIC_DISPATCHIS_20261025" in name and "202610250000_" not in name:
                continue
            unique[url] = tables
        def one(item):
            url, tables = item
            token = unquote(url.rsplit("/",1)[-1]).replace(".zip", "")
            checkpoint = DATA / "acquired" / (token + ".json")
            if checkpoint.exists():
                old = json.loads(checkpoint.read_text())
                if old["outputs"] and all((DATA / p).exists() and digest(DATA / p) == h for p,h in old["outputs"].items()):
                    return old
            path, record = download(url)
            frames = parse_tables(path, tables)
            outputs = {}
            for table, f in frames.items():
                out = DATA / "extension" / table / (token + ".parquet")
                out.parent.mkdir(parents=True, exist_ok=True)
                f.to_parquet(out, index=False)
                outputs[str(out.relative_to(DATA))] = digest(out)
            row = {**record, "tables": {k: len(v) for k,v in frames.items()}, "outputs": outputs}
            write_json(checkpoint, row)
            print("Acquired", token, row["tables"], flush=True)
            return row
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [(url, pool.submit(one, (url, tables))) for url,tables in unique.items()]
            for url, future in futures:
                try:
                    records.append(future.result())
                except Exception as exc:
                    failures.append({"source": url, "reason": str(exc)})
        out = DATA / "source_manifest.json"
        write_json(out, {"retrieved": now(), "records": records, "gaps": failures,
                         "claim": "Historical actuals extension, not issue-time replay"})
        artifacts.append(out)
        print("Source acquisition", len(records), "sources; gaps", len(failures), flush=True)
