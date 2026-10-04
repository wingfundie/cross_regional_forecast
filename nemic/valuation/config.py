"""Configuration, paths and the stage ledger for the interregional valuation v2 campaign."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'configs/valuation/interregional_valuation_v2.json'


@lru_cache(maxsize=1)
def cfg() -> dict:
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def path(key: str) -> Path:
    p = ROOT / cfg()[key]
    p.mkdir(parents=True, exist_ok=True)
    return p


def data(*parts: str) -> Path:
    p = path('data_root').joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def evidence(name: str) -> Path:
    """Compact, committable evidence written into the v2 report folder."""
    p = path('report_root') / 'evidence' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def window(v1: bool = False) -> tuple[pd.Timestamp, pd.Timestamp]:
    w = cfg()['v1_window'] if v1 else cfg()
    return pd.Timestamp(w['start_exclusive']), pd.Timestamp(w['end_inclusive'])


def quarter_of(index: pd.DatetimeIndex) -> pd.PeriodIndex:
    """Interval-ending convention: assign by the instant just before the timestamp."""
    return (index - pd.Timedelta(nanoseconds=1)).to_period('Q')


def complete_quarter_intervals(q: pd.Period) -> int:
    return int(((q + 1).start_time - q.start_time).total_seconds() / 300)


def sha256(p: Path) -> str:
    """Line-ending-normalised hash for text, raw hash for binary files."""
    b = Path(p).read_bytes()
    if Path(p).suffix.lower() in {'.py', '.md', '.json', '.csv', '.js', '.mjs', '.cjs', '.css', '.txt', '.html'}:
        b = b.replace(b'\r\n', b'\n')
    return hashlib.sha256(b).hexdigest()


def log(stage: str, status: str, **info) -> None:
    """Append-only stage ledger (git-ignored events.jsonl) plus status.json snapshot."""
    root = path('tracking_root')
    rec = dict(time=datetime.now(timezone.utc).isoformat(timespec='seconds'), stage=stage, status=status, **info)
    with (root / 'events.jsonl').open('a', encoding='utf-8') as f:
        f.write(json.dumps(rec, default=str) + '\n')
    sp = root / 'status.json'
    st = json.loads(sp.read_text()) if sp.exists() else {}
    st[stage] = rec
    sp.write_text(json.dumps(st, indent=2, default=str))


def write_csv(df: pd.DataFrame, name: str, index: bool = False) -> Path:
    p = evidence(name)
    df.to_csv(p, index=index, lineterminator='\n', float_format='%.10g')
    return p
