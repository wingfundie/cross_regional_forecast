"""S0/S-1 acquisition: MMSDM monthly NETWORK tables. Only the required tables are downloaded."""
from __future__ import annotations

import time

import pandas as pd

from nemic.common import session

from .common import DATA, EXEC, MONTHS, read_aemo_zip, sha256, write_json, write_parquet

BASE = ("https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/{y}/MMSDM_{y}_{m:02d}/"
        "MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_ARCHIVE%23{table}%23FILE01%23{y}{m:02d}010000.zip")
OUTAGE_TABLES = ["NETWORK_OUTAGEDETAIL", "NETWORK_OUTAGECONSTRAINTSET"]
STANDING_TABLES = ["NETWORK_EQUIPMENTDETAIL", "NETWORK_SUBSTATIONDETAIL"]


def _fetch(table: str, month: pd.Period) -> dict:
    raw_dir = DATA / "raw" / "mmsdm"
    out = raw_dir / f"{table}_{month.strftime('%Y%m')}.parquet"
    url = BASE.format(y=month.year, m=month.month, table=table)
    if out.exists():
        return {"table": table, "month": str(month), "url": url, "path": str(out.relative_to(DATA)),
                "sha256": sha256(out), "status": "cached"}
    for attempt in range(4):
        try:
            response = session().get(url, timeout=(20, 300))
            if response.status_code == 404:
                return {"table": table, "month": str(month), "url": url, "status": "missing"}
            response.raise_for_status()
            break
        except Exception as exc:  # network retry
            if attempt == 3:
                return {"table": table, "month": str(month), "url": url, "status": "failed", "error": str(exc)}
            time.sleep(5 * (attempt + 1))
    zip_sha = __import__("hashlib").sha256(response.content).hexdigest()
    frames = read_aemo_zip(response.content)
    frame = pd.concat(frames.values(), ignore_index=True) if frames else pd.DataFrame()
    frame["source_month"] = str(month)
    write_parquet(out, frame)
    return {"table": table, "month": str(month), "url": url, "path": str(out.relative_to(DATA)), "rows": len(frame),
            "zip_bytes": len(response.content), "zip_sha256": zip_sha, "sha256": sha256(out), "status": "downloaded"}


def acquire_mmsdm() -> dict:
    records = []
    for month in MONTHS:
        for table in OUTAGE_TABLES:
            records.append(_fetch(table, month))
            print(records[-1]["table"], records[-1]["month"], records[-1]["status"], records[-1].get("rows"), flush=True)
    latest = MONTHS[-1]
    for table in STANDING_TABLES:
        records.append(_fetch(table, latest))
        print(records[-1]["table"], records[-1]["month"], records[-1]["status"], records[-1].get("rows"), flush=True)
    result = {"retrieved": pd.Timestamp.now(tz="UTC").isoformat(), "records": records,
              "missing": [r for r in records if r["status"] in {"missing", "failed"}]}
    write_json(DATA / "raw" / "mmsdm_sources.json", result)
    write_json(EXEC / "sources.json", {"mmsdm": [{k: r.get(k) for k in ("table", "month", "url", "status", "rows", "zip_sha256", "sha256")}
                                                 for r in records]})
    return result
