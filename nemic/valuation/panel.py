"""Five-minute price and interconnector panels for the full v2 window.

Prices: DISPATCHPRICE with INTERVENTION = 0 (the pricing run, whose RRP settles the market).
Flows: DISPATCHINTERCONNECTORRES physical run (INTERVENTION = 1 where present, else 0).
APCFLAG is decoded per the MMS data model: 1 APC/APF binding, 2 VoLL override,
4 MPC/MPF binding, 8 manual override, 16 IRLF price scaling.
"""
from __future__ import annotations

import glob

import numpy as np
import pandas as pd

from .config import ROOT, cfg, data, log, window

PRICE_COLS = ['SETTLEMENTDATE', 'REGIONID', 'INTERVENTION', 'RRP', 'ROP', 'APCFLAG', 'MARKETSUSPENDEDFLAG',
              'PRICE_STATUS', 'LASTCHANGED']
IC_COLS = ['SETTLEMENTDATE', 'INTERCONNECTORID', 'INTERVENTION', 'MWFLOW', 'METEREDMWFLOW', 'MWLOSSES',
           'MARGINALLOSS', 'EXPORTLIMIT', 'IMPORTLIMIT', 'EXPORTGENCONID', 'IMPORTGENCONID', 'LASTCHANGED']
APC_BITS = {1: 'apc_binding', 2: 'voll_override', 4: 'mpc_binding', 8: 'manual_override', 16: 'irlf_scaling'}


def _read(table: str, cols: list[str]) -> pd.DataFrame:
    frames = []
    for f in sorted(glob.glob(str(ROOT / f'data/tables/{table}/*.parquet'))):
        import pyarrow.parquet as pq
        have = set(pq.read_schema(f).names)
        frames.append(pd.read_parquet(f, columns=[c for c in cols if c in have]))
    x = pd.concat(frames, ignore_index=True)
    x['time'] = pd.to_datetime(x.SETTLEMENTDATE.astype(str).str.replace('/', '-'))
    x['INTERVENTION'] = pd.to_numeric(x.INTERVENTION, errors='coerce').fillna(0).astype(int)
    s, e = window()
    return x[(x.time > s) & (x.time <= e)].drop(columns='SETTLEMENTDATE')


def build_prices() -> pd.DataFrame:
    x = _read('DISPATCHPRICE', PRICE_COLS)
    x = x[x.INTERVENTION == 0]
    for c in ['RRP', 'ROP', 'APCFLAG', 'MARKETSUSPENDEDFLAG']:
        x[c] = pd.to_numeric(x[c], errors='coerce')
    x = x.sort_values(['time', 'REGIONID', 'LASTCHANGED'])
    conflicts = int(x.groupby(['time', 'REGIONID']).RRP.nunique().gt(1).sum())
    x = x.drop_duplicates(['time', 'REGIONID'], keep='last')
    x.attrs['conflicting_versions'] = conflicts
    return x


def build_ic() -> pd.DataFrame:
    x = _read('DISPATCHINTERCONNECTORRES', IC_COLS)
    for c in ['MWFLOW', 'METEREDMWFLOW', 'MWLOSSES', 'MARGINALLOSS', 'EXPORTLIMIT', 'IMPORTLIMIT']:
        x[c] = pd.to_numeric(x[c], errors='coerce')
    x = x.sort_values(['time', 'INTERCONNECTORID', 'INTERVENTION', 'LASTCHANGED'])
    return x.drop_duplicates(['time', 'INTERCONNECTORID'], keep='last')  # physical run where present


def run() -> dict:
    log('panel', 'started')
    p = build_prices()
    i = build_ic()
    s, e = window()
    expected = pd.date_range(s + pd.Timedelta(minutes=5), e, freq='5min')
    P = p.pivot(index='time', columns='REGIONID', values='RRP').reindex(expected)
    missing = {r: int(P[r].isna().sum()) for r in P}
    flags = p[['time', 'REGIONID', 'RRP', 'ROP', 'APCFLAG', 'MARKETSUSPENDEDFLAG', 'PRICE_STATUS']].copy()
    for bit, name in APC_BITS.items():
        flags[name] = (flags.APCFLAG.fillna(0).astype(int) & bit) > 0
    p_out = data('panel', 'prices.parquet')
    flags.to_parquet(p_out, index=False)
    i_out = data('panel', 'interconnectors.parquet')
    i.to_parquet(i_out, index=False)
    ic_missing = {k: int(len(expected) - g.time.isin(expected).sum()) for k, g in i.groupby('INTERCONNECTORID')}
    info = dict(intervals=len(expected), price_missing=missing, ic_missing=ic_missing,
                conflicting_price_versions=p.attrs['conflicting_versions'],
                not_firm=int((p.PRICE_STATUS != 'FIRM').sum()),
                physical_run_rows=int((i.INTERVENTION == 1).sum()))
    log('panel', 'completed', **info)
    return info


def prices(v1: bool = False, fill: bool = False) -> pd.DataFrame:
    """Wide RRP matrix indexed by interval-ending time."""
    f = pd.read_parquet(data('panel', 'prices.parquet'), columns=['time', 'REGIONID', 'RRP'])
    P = f.pivot(index='time', columns='REGIONID', values='RRP').sort_index()
    s, e = window(v1)
    P = P[(P.index > s) & (P.index <= e)]
    return P.ffill() if fill else P


def flags(v1: bool = False) -> pd.DataFrame:
    f = pd.read_parquet(data('panel', 'prices.parquet'))
    s, e = window(v1)
    return f[(f.time > s) & (f.time <= e)]


def ic(v1: bool = False) -> dict[str, pd.DataFrame]:
    x = pd.read_parquet(data('panel', 'interconnectors.parquet'))
    s, e = window(v1)
    x = x[(x.time > s) & (x.time <= e)]
    return {k: g.set_index('time').sort_index() for k, g in x.groupby('INTERCONNECTORID')}
