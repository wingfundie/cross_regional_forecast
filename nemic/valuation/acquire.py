"""Phase 1 acquisition: MMSDM back-fill and SRA/settlement/network tables.

Reuses the project's cached, hash-recorded NEMweb downloader (``nemic.ingest``).
``ingest.extract`` keeps only tables in its IDENTITY map, so settlement, auction and
network tables use ``extract_all`` below, which keeps every I/D record with its own
schema. Only the listed tables are downloaded.
"""
from __future__ import annotations

import csv
import io
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote

import pandas as pd

from nemic import ingest
from nemic.common import links, dump
from .config import cfg, data, log

TABLE_DIR = 'tables'


def months() -> list[pd.Timestamp]:
    s = pd.Timestamp(cfg()['start_exclusive']).normalize().replace(day=1)
    e = pd.Timestamp(cfg()['end_inclusive']) - pd.Timedelta(days=1)
    return list(pd.date_range(s, e.replace(day=1), freq='MS'))


def extract_all(path) -> dict[str, pd.DataFrame]:
    """Every I/D table record in an MMSDM archive, keyed by '<PACKAGE>_<TABLE>' short name."""
    buckets, schemas = {}, {}
    for content in ingest.members(path):
        text = content.decode('utf-8-sig', errors='replace')
        for row in csv.reader(io.StringIO(text)):
            if len(row) < 5 or row[0] not in ('I', 'D'):
                continue
            key = (row[1], row[2], row[3])
            if row[0] == 'I':
                schemas[key] = row[4:]
            elif key in schemas:
                buckets.setdefault(key, []).append(row[4:])
    out = {}
    for key, rows in buckets.items():
        cols = schemas[key]
        n = len(cols)
        df = pd.DataFrame([r[:n] + [''] * max(0, n - len(r)) for r in rows], columns=cols)
        out.setdefault(f'{key[0]}_{key[1]}', []).append(df)
    return {k: pd.concat(v, ignore_index=True) for k, v in out.items()}


def _save(table: str, tag: str, frames: dict) -> dict:
    info = {}
    for name, df in frames.items():
        p = data(TABLE_DIR, table, f'{tag}__{name}.parquet')
        df.to_parquet(p, index=False, compression='zstd')
        info[name] = len(df)
    return info


def fetch_table(url: str, table: str) -> dict:
    p = ingest.download(url)
    done = data(TABLE_DIR, table, f'{p.stem}.done.json')
    if done.exists():
        return json.loads(done.read_text())
    info = _save(table, p.stem, extract_all(p))
    done.write_text(json.dumps(info))
    return info


def plan() -> list[tuple[str, str]]:
    tables = cfg()['mmsdm_tables']
    small = tables['settlement_and_auction'] + tables['network_and_settings'] + ['NEGATIVE_RESIDUE']
    back_end = pd.Timestamp('2023-09-01')  # data/tables already holds Sep 2023 onward
    jobs, availability = [], []
    for m in months():
        try:
            found = links(ingest.archive_dir(m))
        except Exception as e:  # archive month not yet published
            availability.append({'month': str(m.date()), 'error': str(e)[:120]})
            continue
        row = {'month': str(m.date())}
        for t in small:
            sel = [u for u in found if ingest.is_table(u, t)]
            row[t] = len(sel)
            jobs += [(u, t) for u in sel]
        if m < back_end:
            for t in tables['backfill']:
                sel = [u for u in found if ingest.is_table(u, t)]
                row[t] = len(sel)
                jobs += [(u, '__dispatch__') for u in sel]
        availability.append(row)
    dump(data('availability.json'), availability)
    return jobs


def run() -> dict:
    log('acquire', 'started')
    jobs = plan()
    dump(data('download_plan.json'), jobs)
    failures, done = [], 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        fut = {}
        for url, t in jobs:
            if t == '__dispatch__':
                fut[pool.submit(ingest.process_url, url, ingest.TABLES[:3])] = (url, t)
            else:
                fut[pool.submit(fetch_table, url, t)] = (url, t)
        for f in as_completed(fut):
            try:
                f.result(); done += 1
            except Exception as e:
                failures.append({'url': fut[f][0], 'table': fut[f][1], 'error': str(e)[:300]})
                print('FAILED', unquote(fut[f][0].split('/')[-1]), str(e)[:200], flush=True)
    dump(data('download_failures.json'), failures)
    log('acquire', 'completed' if not failures else 'partial', jobs=len(jobs), done=done, failures=len(failures))
    return {'jobs': len(jobs), 'done': done, 'failures': len(failures)}


def load(table: str, name: str | None = None) -> pd.DataFrame:
    """Concatenate all extracted monthly parts of a table (optionally one sub-table name)."""
    root = data(TABLE_DIR, table, 'x').parent
    parts = sorted(root.glob('*.parquet'))
    frames = []
    for p in parts:
        sub = p.stem.split('__', 1)[-1]
        if name is None or sub == name:
            frames.append(pd.read_parquet(p))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True).drop_duplicates()
    return df
