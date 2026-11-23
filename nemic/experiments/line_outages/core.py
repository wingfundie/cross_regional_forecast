"""Campaign ownership, content fingerprints and small temporal helpers."""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import psutil

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "configs/experiments/line_outage_risk_v1.json"
OLD = ROOT / "data/nos_regime_v1"
BIND = ROOT / "data/nos_binding_v1"
REGIONS = ["NSW1", "QLD1", "VIC1", "SA1", "TAS1"]
STUDIES = {"NSW1-QLD1": "qni", "N-Q-MNSP1": "directlink", "VIC1-NSW1": "vni",
           "V-SA": "vsa", "V-S-MNSP1": "murraylink", "T-V-MNSP1": "basslink"}
IC_REGIONS = {"NSW1-QLD1": ("NSW1", "QLD1"), "N-Q-MNSP1": ("NSW1", "QLD1"),
              "VIC1-NSW1": ("VIC1", "NSW1"), "V-SA": ("VIC1", "SA1"),
              "V-S-MNSP1": ("VIC1", "SA1"), "T-V-MNSP1": ("TAS1", "VIC1")}


def config(path=CONFIG):
    c = json.loads(Path(path).read_text(encoding="utf-8"))
    c["_config"] = Path(path)
    c["_data"] = ROOT / c["data_dir"]
    c["_execution"] = ROOT / "execution" / c["experiment_id"]
    c["_report"] = ROOT / c["report_dir"]
    return c


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def json_write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


def save(c, name, frame):
    p = c["_data"] / (name + ".parquet")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp.parquet")
    frame.to_parquet(tmp, index=False)
    tmp.replace(p)
    return p


def load(c, name):
    return pd.read_parquet(c["_data"] / (name + ".parquet"))


def grid(c):
    return pd.date_range(pd.Timestamp(c["window_start"]) + pd.Timedelta(minutes=5),
                         c["window_end"], freq="5min")


def interval_mask(times, windows, inclusive_start=False):
    """Equipment start is exclusive, restoration inclusive for interval-ending dispatch."""
    values = pd.DatetimeIndex(times).asi8
    out = np.zeros(len(values), dtype=bool)
    for row in windows.itertuples():
        s, e = pd.Timestamp(row.start).value, pd.Timestamp(row.end).value
        left = np.searchsorted(values, s, side="left" if inclusive_start else "right")
        right = np.searchsorted(values, e, side="right")
        out[left:right] = True
    return out


def merge_events(frame):
    """Collapse overlapping/adjacent administrative windows, retaining every source ID."""
    rows = []
    for asset, g in frame.sort_values(["asset", "start", "end"]).groupby("asset", sort=True):
        current = None
        for r in g.itertuples():
            if current and r.start <= current["end"] + pd.Timedelta(minutes=5):
                current["end"] = max(current["end"], r.end)
                current["outage_ids"].append(str(r.OUTAGEID))
            else:
                if current:
                    rows.append(current)
                current = {"asset": asset, "start": r.start, "end": r.end,
                           "outage_ids": [str(r.OUTAGEID)]}
        if current:
            rows.append(current)
    result = pd.DataFrame(rows, columns=["asset", "start", "end", "outage_ids"])
    if len(result):
        result["event_id"] = [hashlib.sha256((r.asset + str(r.start) + str(r.end)).encode()).hexdigest()[:16]
                              for r in result.itertuples()]
        result["outage_ids"] = result.outage_ids.map(lambda v: "|".join(sorted(set(v))))
    else:
        result["event_id"] = pd.Series(dtype=str)
    return result


def run_stage(c, stage, function, inputs, outputs, force=False):
    """Atomic ownership + dependency/output-hash checked resume; one healthy stage owner."""
    execution = c["_execution"]
    execution.mkdir(parents=True, exist_ok=True)
    module_file = Path(__import__(function.__module__,fromlist=["__file__"]).__file__)
    sources = [c["_config"], Path(__file__), module_file, *inputs]
    for p in sources:
        if not Path(p).is_file():
            raise FileNotFoundError(p)
    fingerprints = {str(Path(p).relative_to(ROOT)): sha(p) for p in dict.fromkeys(sources)}
    digest = hashlib.sha256(json.dumps(fingerprints, sort_keys=True).encode()).hexdigest()
    manifest = execution / "manifests" / (stage + ".json")
    db = sqlite3.connect(execution / "ledger.sqlite", timeout=30)
    db.execute("CREATE TABLE IF NOT EXISTS stages (stage TEXT PRIMARY KEY, state TEXT, pid INTEGER, process_start REAL, fingerprint TEXT, updated TEXT, detail TEXT)")
    db.execute("BEGIN IMMEDIATE")
    old = db.execute("SELECT state,pid,process_start FROM stages WHERE stage=?", (stage,)).fetchone()
    if old and old[0] == "active":
        try:
            live = psutil.Process(old[1])
            healthy = abs(live.create_time() - old[2]) < 0.01 and live.is_running()
        except psutil.Error:
            healthy = False
        if healthy:
            db.rollback(); db.close()
            raise RuntimeError(f"Stage {stage} already owned by healthy PID {old[1]}")
    if not force and manifest.exists():
        m = json.loads(manifest.read_text())
        if m.get("fingerprint") == digest and all(Path(p).is_file() and sha(p) == h for p, h in m["outputs"].items()):
            db.commit(); db.close()
            print(f"{stage}: verified cached outputs", flush=True)
            return m["summary"]
    db.execute("INSERT OR REPLACE INTO stages VALUES (?,?,?,?,?,?,?)",
               (stage, "active", os.getpid(), psutil.Process().create_time(), digest, pd.Timestamp.now(tz="UTC").isoformat(), ""))
    db.commit()
    print(f"{stage}: active", flush=True)
    try:
        c["_stage_fingerprint"] = digest
        summary = function(c)
        absent = [str(p) for p in outputs if not Path(p).is_file()]
        if absent:
            raise RuntimeError(f"Missing declared outputs: {absent}")
        extras = []
        if stage == "compare": extras = list((c["_data"] / "pairs").glob("*.parquet"))
        if stage == "events": extras = list((c["_data"] / "timelines").glob("*.parquet"))
        if stage == "report": extras = list((c["_report"] / "downloads").glob("*"))
        if stage == "supplement": extras = list((c["_data"] / "supplements").glob("*"))
        json_write(manifest, {"stage": stage, "fingerprint": digest, "inputs": fingerprints,
                              "outputs": {str(p): sha(p) for p in dict.fromkeys([*outputs,*extras])}, "summary": summary,
                              "completed_utc": pd.Timestamp.now(tz="UTC").isoformat()})
        db.execute("UPDATE stages SET state='complete',detail=?,updated=? WHERE stage=?",
                   (json.dumps(summary, default=str), pd.Timestamp.now(tz="UTC").isoformat(), stage))
        db.commit()
        print(f"{stage}: complete {json.dumps(summary, default=str)}", flush=True)
        return summary
    except Exception as exc:
        db.execute("UPDATE stages SET state='failed',detail=?,updated=? WHERE stage=?",
                   (repr(exc), pd.Timestamp.now(tz="UTC").isoformat(), stage))
        db.commit()
        raise
    finally:
        db.close()
