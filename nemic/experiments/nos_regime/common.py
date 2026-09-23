"""Paths, window and small shared helpers for the NOS outage regime study."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "nos_regime_v1"
EXEC = ROOT / "execution" / "nos_outage_regime_v1"
START = pd.Timestamp("2024-09-01 00:00")
END = pd.Timestamp("2026-09-01 00:00")
YEAR2 = pd.Timestamp("2025-09-01 00:00")
MONTHS = pd.period_range("2024-09", "2026-08", freq="M")

# Connector id -> constraint study folder (data/constraint_<study>_2y)
STUDY = {"NSW1-QLD1": "qni", "N-Q-MNSP1": "directlink", "VIC1-NSW1": "vni",
         "V-SA": "vsa", "V-S-MNSP1": "murraylink", "T-V-MNSP1": "basslink"}
PILOT = ["VIC1-NSW1", "V-SA"]
NOS_WEEKS = ROOT / "data" / "forecast_experiments" / "vni_diurnal_nos_v2" / "nos" / "weeks"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_aemo_zip(blob: bytes) -> dict[str, pd.DataFrame]:
    """Parse an AEMO CSV (I/D record format) inside a zip; one frame per report table, all strings."""
    tables: dict[str, list] = {}
    headers: dict[str, list] = {}
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        for member in z.namelist():
            if not member.lower().endswith(".csv"):
                continue
            text = z.read(member).decode("utf-8-sig", errors="replace")
            for row in csv.reader(io.StringIO(text)):
                if len(row) < 4:
                    continue
                key = f"{row[1]}_{row[2]}"
                if row[0] == "I":
                    headers[key] = row[4:]
                elif row[0] == "D" and key in headers:
                    tables.setdefault(key, []).append(row[4:4 + len(headers[key])])
    return {k: pd.DataFrame(v, columns=headers[k]) for k, v in tables.items()}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")
    tmp.replace(path)


def write_parquet(path: Path, frame: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.parquet")
    frame.to_parquet(tmp, index=False)
    tmp.replace(path)
    return path


def nem_time(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", format="mixed")
