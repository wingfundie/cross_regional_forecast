"""Reproducible throughput and golden-parity acceptance benchmark."""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .modelling import build_table,build_tables_parallel
from .tracking import atomic


def _golden(ledger,optimized,days=7):
    candidates=list((ledger.data/'features/QNI/partitions').glob('*/*.parquet'))
    legacy=[]
    for p in candidates:
        meta=p.with_suffix('.json')
        try:backend=json.loads(meta.read_text()).get('backend','legacy-scalar')
        except (FileNotFoundError,json.JSONDecodeError):backend='legacy-scalar'
        if backend!='vectorized-indexed-v2':legacy.append(p)
    new=pd.read_parquet(optimized)
    selected=sorted(set(new.origin.dt.strftime('%Y-%m-%d')))[:days]
    old_paths=[p for p in legacy if p.stem in selected]
    if len(old_paths)<days:return dict(status='insufficient_legacy_overlap',days=len(old_paths))
    old=pd.concat([pd.read_parquet(p) for p in old_paths],ignore_index=True)
    new=new[new.origin.dt.strftime('%Y-%m-%d').isin(selected)]
    keys=['connector','origin','delivery','lead'];common=[c for c in old if c in new]
    a=old[common].sort_values(keys).reset_index(drop=True);b=new[common].sort_values(keys).reset_index(drop=True)
    if not a[keys].equals(b[keys]):return dict(status='failed_keys',days=days)
    categorical=[c for c in common if not pd.api.types.is_numeric_dtype(a[c])]
    numeric=[c for c in common if c not in categorical and c not in keys]
    missing_equal=all(a[c].isna().equals(b[c].isna()) for c in common)
    exact=all(a[c].equals(b[c]) for c in categorical)
    close=all(np.allclose(a[c],b[c],rtol=1e-5,atol=1e-5,equal_nan=True) for c in numeric)
    return dict(status='passed' if missing_equal and exact and close else 'failed_values',days=days,rows=len(a),
                keys=True,categorical=exact,numeric=close,missingness=missing_equal)


def benchmark(ledger,workers=2):
    baseline_path=ledger.root/'benchmarks/scalar_baseline.json'
    baseline=json.loads(baseline_path.read_text())
    t=time.monotonic();single=build_table(ledger,'QNI',672);single_seconds=time.monotonic()-t
    single_rows=len(pd.read_parquet(single));single_rps=single_rows/single_seconds
    t=time.monotonic();paths=build_tables_parallel(ledger.c,('QNI','VNI'),720,min(2,workers));two_seconds=time.monotonic()-t
    aggregate_rows=sum(len(pd.read_parquet(p)) for p in paths);two_rps=aggregate_rows/two_seconds
    disk=shutil.disk_usage(ledger.data)
    result=dict(baseline_rows_per_second=baseline['attempted_rows_per_second'],single_worker=dict(rows=single_rows,seconds=single_seconds,rows_per_second=single_rps,
                speedup=single_rps/baseline['attempted_rows_per_second']),two_workers=dict(rows=aggregate_rows,seconds=two_seconds,rows_per_second=two_rps,
                speedup=two_rps/baseline['attempted_rows_per_second']),disk_free_bytes=disk.free,
                gates=dict(single_5x=single_rps>=5*baseline['attempted_rows_per_second'],two_7x=two_rps>=7*baseline['attempted_rows_per_second'],disk_20gb=disk.free>=20_000_000_000),
                golden=_golden(ledger,single))
    out=ledger.root/'benchmarks/vectorized_benchmark.json';atomic(out,json.dumps(result,indent=2))
    ledger.record('engineering/benchmark','completed' if all(result['gates'].values()) and result['golden']['status']=='passed' else 'ready',
                  'Measured vectorized throughput and parity acceptance', [out] if all(result['gates'].values()) and result['golden']['status']=='passed' else [])
    return out
