"""Effective-dated pre-loop SRA settlement engine and reconciliation to AEMO settled residues.

Asset residue for one five-minute interval, from-region loss share s:

    r_t = P_to,t * (F_t - (1 - s) L_t) - P_from,t * (F_t + s L_t)     [$ per MW-hour] / 12

A directional interconnector pools its regulated assets (VNI; QNI + Terranora; Heywood +
Murraylink; Basslink from July 2026). Pre-loop, unit holders receive the positive part per
interval; negative residue is recovered from the importing-region TNSP (NER 3.6.5(a)(4)) and
is kept in a separate ledger. A unit's share is PROPORTION% of the directional residue, with
PROPORTION and MAXIMUMUNITS from AUCTION_IC_ALLOCATIONS for the delivery quarter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import panel
from .acquire import load
from .config import cfg, data, log, quarter_of, write_csv, complete_quarter_intervals

SRA_KEY = {  # (INTERCONNECTORID in SRA tables, FROMREGIONID) -> directional code
    ('VIC1-NSW1', 'VIC1'): 'VICNSW', ('VIC1-NSW1', 'NSW1'): 'NSWVIC',
    ('NSW1-QLD1', 'NSW1'): 'NSWQLD', ('NSW1-QLD1', 'QLD1'): 'QLDNSW',
    ('V-SA', 'VIC1'): 'VICSA', ('V-SA', 'SA1'): 'SAVIC',
    ('T-V-MNSP1', 'TAS1'): 'TASVIC', ('T-V-MNSP1', 'VIC1'): 'VICTAS',
}
DIRECTIONS = ['VICNSW', 'NSWVIC', 'NSWQLD', 'QLDNSW', 'VICSA', 'SAVIC', 'TASVIC', 'VICTAS']


def _ts(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str).str.replace('/', '-'), errors='coerce')


def loss_shares(index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    """Effective-dated FROMREGIONLOSSSHARE per interconnector, aligned to ``index``."""
    x = load('INTERCONNECTORCONSTRAINT')
    x = x[x.FROMREGIONLOSSSHARE.astype(str).str.strip() != ''].copy()
    x['eff'] = _ts(x.EFFECTIVEDATE)
    x['ver'] = pd.to_numeric(x.VERSIONNO)
    x['s'] = pd.to_numeric(x.FROMREGIONLOSSSHARE)
    out = {}
    for ic, g in x.sort_values(['eff', 'ver']).groupby('INTERCONNECTORID'):
        g = g.drop_duplicates('eff', keep='last').set_index('eff').s
        out[ic] = g.reindex(g.index.union(index)).ffill().reindex(index)
    return out


def asset_residue(P: pd.DataFrame, g: pd.DataFrame, fr: str, to: str, s: pd.Series | float, flow: str = 'MWFLOW') -> pd.Series:
    F = g[flow].reindex(P.index)
    L = g['MWLOSSES'].reindex(P.index)
    return (P[to] * (F - (1 - s) * L) - P[fr] * (F + s * L)) / 12


def unit_registry() -> pd.DataFrame:
    x = load('AUCTION_IC_ALLOCATIONS')
    x = x.assign(year=pd.to_numeric(x.CONTRACTYEAR), q=pd.to_numeric(x.QUARTER), ver=pd.to_numeric(x.VERSIONNO))
    x = x.sort_values(['year', 'q', 'INTERCONNECTORID', 'FROMREGIONID', 'ver']).drop_duplicates(['year', 'q', 'INTERCONNECTORID', 'FROMREGIONID'], keep='last')
    x['direction'] = [SRA_KEY.get((i, f)) for i, f in zip(x.INTERCONNECTORID, x.FROMREGIONID)]
    x['quarter'] = [str(pd.Period(year=int(y), quarter=int(q), freq='Q')) for y, q in zip(x.year, x.q)]
    for c in ['MAXIMUMUNITS', 'PROPORTION', 'AUCTIONFEE', 'AUCTIONFEE_SALES']:
        x[c] = pd.to_numeric(x[c], errors='coerce')
    return x[['quarter', 'direction', 'INTERCONNECTORID', 'FROMREGIONID', 'MAXIMUMUNITS', 'PROPORTION', 'AUCTIONFEE', 'AUCTIONFEE_SALES', 'ver']].dropna(subset=['direction'])


def directional_series(P, ics, shares, flow: str = 'MWFLOW', share_override: float | None = None, lossless: bool = False) -> pd.DataFrame:
    """Per-interval pooled residue for every direction (positive and negative parts kept separately)."""
    out = {}
    for pr in cfg()['pairs']:
        a, b, assets = pr['a'], pr['b'], pr['assets']
        R = pd.Series(0.0, index=P.index); N = pd.Series(0.0, index=P.index)
        for asset in assets:
            fr, to = cfg()['asset_direction'][asset]
            g = ics[asset]
            s = share_override if share_override is not None else shares.get(asset, cfg()['loss_share_default'])
            if isinstance(s, pd.Series):
                s = s.fillna(cfg()['loss_share_default'])
            if lossless:
                g = g.assign(MWLOSSES=0.0)
            r = asset_residue(P, g, fr, to, s, flow).fillna(0)
            sign = 1.0 if (fr, to) == (a, b) else -1.0
            R += r; N += sign * g[flow].reindex(P.index).fillna(0)
        for code, mask in [(pr['sra_ab'], N > 0), (pr['sra_ba'], N < 0)]:
            out[f'{code}_pos'] = R.where(mask, 0).clip(lower=0)
            out[f'{code}_neg'] = R.where(mask, 0).clip(upper=0)
        out[f'{pr["pair"]}_netflow'] = N
    return pd.DataFrame(out, index=P.index)


def quarterly(series: pd.DataFrame, units: pd.DataFrame, variant: str) -> pd.DataFrame:
    q = quarter_of(series.index)
    g = series.groupby(q).sum()
    n = series.groupby(q).size()
    rows = []
    for quarter, r in g.iterrows():
        for d in DIRECTIONS:
            u = units[(units.quarter == str(quarter)) & (units.direction == d)]
            prop = float(u.PROPORTION.iloc[0]) / 100 if len(u) else 1 / cfg()['fallback_max_units'][d]
            maxu = float(u.MAXIMUMUNITS.iloc[0]) if len(u) else cfg()['fallback_max_units'][d]
            fee = float(u.AUCTIONFEE.iloc[0]) if len(u) and np.isfinite(u.AUCTIONFEE.iloc[0]) else 0.0
            rows.append(dict(quarter=str(quarter), direction=d, variant=variant,
                             complete=int(n[quarter]) == complete_quarter_intervals(quarter),
                             residue_pos=r[f'{d}_pos'], residue_neg=r[f'{d}_neg'],
                             proportion=prop, max_units=maxu, units_source='AUCTION_IC_ALLOCATIONS' if len(u) else 'fallback',
                             auction_fee=fee, per_unit=r[f'{d}_pos'] * prop, per_unit_net_fee=r[f'{d}_pos'] * prop - fee))
    return pd.DataFrame(rows)


def settled() -> pd.DataFrame:
    """AEMO settled IRSR (SETIRSURPLUS), latest settlement run per date, five-minute periods.

    Parts are read column-subset and converted to numbers one monthly file at a time, then cached.
    """
    cache = data('settlement', 'settled_compact.parquet')
    parts = sorted(data('tables', 'SETIRSURPLUS', 'x').parent.glob('*.parquet'))
    stamp = str(len(parts)) + '|' + '|'.join(p.name for p in parts[-3:])
    if cache.exists():
        c = pd.read_parquet(cache)
        if c.attrs.get('stamp', None) == stamp or (cache.with_suffix('.stamp').exists() and cache.with_suffix('.stamp').read_text() == stamp):
            return c
    cols = ['SETTLEMENTDATE', 'SETTLEMENTRUNNO', 'PERIODID', 'INTERCONNECTORID', 'REGIONID', 'MWFLOW', 'LOSSFACTOR', 'SURPLUSVALUE']
    frames = []
    for f in parts:
        x = pd.read_parquet(f, columns=cols)
        x['date'] = _ts(x.SETTLEMENTDATE)
        x = x[x.date >= pd.Timestamp('2021-10-01')].drop(columns='SETTLEMENTDATE')
        for c in ['SETTLEMENTRUNNO', 'PERIODID', 'MWFLOW', 'LOSSFACTOR', 'SURPLUSVALUE']:
            x[c] = pd.to_numeric(x[c], errors='coerce').astype('float32' if c in ('MWFLOW', 'LOSSFACTOR') else 'float64')
        x['INTERCONNECTORID'] = x.INTERCONNECTORID.astype('category'); x['REGIONID'] = x.REGIONID.astype('category')
        frames.append(x)
    x = pd.concat(frames, ignore_index=True)
    for c in ['INTERCONNECTORID', 'REGIONID']:
        x[c] = x[c].astype(str)
    last = x.groupby('date').SETTLEMENTRUNNO.transform('max')
    x = x[x.SETTLEMENTRUNNO == last].drop_duplicates(['date', 'PERIODID', 'INTERCONNECTORID', 'REGIONID'], keep='last')
    x['time'] = x.date + pd.to_timedelta(x.PERIODID * 5, unit='min')
    x = x.reset_index(drop=True)
    x.to_parquet(cache)
    cache.with_suffix('.stamp').write_text(stamp)
    return x


def settled_directional(P: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Realised directional residue from AEMO settlement (SETIRSURPLUS, latest run).

    Each asset row carries the residue in its exporting region's row. The directional interconnector
    A->B pools the exporting-region-A rows of its assets; unit holders receive the positive part per
    interval (pre-loop). Also returns per-arm signed allocations and settled energy flows (MW) for the
    loop counterfactual.
    """
    st = settled()
    st = st[st.time.isin(P.index)]
    out = {}
    arms = {}
    for pr in cfg()['pairs']:
        a, b = pr['a'], pr['b']
        Rab = pd.Series(0.0, index=P.index); Rba = pd.Series(0.0, index=P.index)
        Fab = pd.Series(0.0, index=P.index)
        for asset in pr['assets']:
            g = st[st.INTERCONNECTORID == asset]
            sv = g.pivot_table(index='time', columns='REGIONID', values='SURPLUSVALUE', aggfunc='sum').reindex(P.index).fillna(0)
            mw = g.pivot_table(index='time', columns='REGIONID', values='MWFLOW', aggfunc='sum').reindex(P.index).fillna(0)
            Rab += sv.get(a, 0.0); Rba += sv.get(b, 0.0)
            Fab += mw.get(b, 0.0) * 12  # MWh imported into b per interval -> MW (positive = a -> b)
        out[f'{pr["sra_ab"]}_pos'] = Rab.clip(lower=0); out[f'{pr["sra_ab"]}_neg'] = Rab.clip(upper=0)
        out[f'{pr["sra_ba"]}_pos'] = Rba.clip(lower=0); out[f'{pr["sra_ba"]}_neg'] = Rba.clip(upper=0)
        out[f'{pr["pair"]}_netflow'] = Fab
        arms[pr['pair']] = pd.DataFrame({'alloc': Rab + Rba, 'flow': Fab})
    cov = st.groupby('INTERCONNECTORID').time.nunique() / len(P.index)
    series = pd.DataFrame(out, index=P.index)
    series.attrs['coverage'] = cov.to_dict()
    A = pd.concat({k: v for k, v in arms.items()}, axis=1)
    A.columns = ['_'.join(c) for c in A.columns]
    return series, A


def run() -> dict:
    log('settlement', 'started')
    P = panel.prices()
    ics = panel.ic()
    shares = loss_shares(P.index)
    units = unit_registry()
    write_csv(units, 'sra_unit_registry.csv')
    settled_series, arms = settled_directional(P)
    arms.to_parquet(data('settlement', 'settled_arms_5min.parquet'))
    variants = {
        'settled': settled_series,
        'dispatch_dated_share': directional_series(P, ics, shares, 'MWFLOW'),
        'metered_dated_share': directional_series(P, ics, shares, 'METEREDMWFLOW'),
        'dispatch_share_0': directional_series(P, ics, shares, 'MWFLOW', share_override=0.0),
        'dispatch_share_1': directional_series(P, ics, shares, 'MWFLOW', share_override=1.0),
        'dispatch_lossless': directional_series(P, ics, shares, 'MWFLOW', lossless=True),
    }
    variants['settled'].to_parquet(data('settlement', 'directional_5min.parquet'))
    variants['dispatch_dated_share'].to_parquet(data('settlement', 'directional_5min_dispatch.parquet'))
    ledger = pd.concat([quarterly(v, units, k) for k, v in variants.items()], ignore_index=True)
    write_csv(ledger, 'sra_ledger_quarterly.csv')
    rec = reconcile(P, ics, shares)
    info = dict(units_rows=len(units), ledger_rows=len(ledger), settled_coverage=settled_series.attrs['coverage'], reconciliation=rec)
    log('settlement', 'completed', **{k: v for k, v in info.items() if k != 'reconciliation'})
    return info


def reconcile(P, ics, shares) -> dict:
    """Asset-level computed residue vs SETIRSURPLUS, by quarter and direction (surplus row = exporting region)."""
    st = settled()
    st = st[st.time.isin(P.index)]
    rows = []
    for asset, (fr, to) in cfg()['asset_direction'].items():
        if asset not in ics:
            continue
        g = ics[asset]
        s = shares.get(asset, cfg()['loss_share_default'])
        s = s.fillna(cfg()['loss_share_default']) if isinstance(s, pd.Series) else s
        for flow in ['MWFLOW', 'METEREDMWFLOW']:
            r = asset_residue(P, g, fr, to, s, flow)
            F = g[flow].reindex(P.index)
            for exp, mask in [(fr, F > 0), (to, F < 0)]:
                comp = r.where(mask, 0)
                q = quarter_of(P.index)
                cq = pd.DataFrame({'q': q, 'pos': comp.clip(lower=0), 'signed': comp}).groupby('q').sum()
                sq = st[(st.INTERCONNECTORID == asset) & (st.REGIONID == exp)].set_index('time')
                sq = sq.reindex(P.index)
                sv = pd.DataFrame({'q': q, 'settled': sq.SURPLUSVALUE.fillna(0), 'settled_pos': sq.SURPLUSVALUE.fillna(0).clip(lower=0),
                                   'covered': sq.SURPLUSVALUE.notna()}).groupby('q').agg(settled=('settled', 'sum'), settled_pos=('settled_pos', 'sum'), covered=('covered', 'mean'))
                for quarter in cq.index:
                    rows.append(dict(asset=asset, exporting_region=exp, flow=flow, quarter=str(quarter),
                                     computed_pos=cq.loc[quarter, 'pos'], computed_signed=cq.loc[quarter, 'signed'],
                                     settled=sv.loc[quarter, 'settled'], settled_pos=sv.loc[quarter, 'settled_pos'], coverage=sv.loc[quarter, 'covered']))
    R = pd.DataFrame(rows)
    R['bias_pct'] = 100 * (R.computed_signed - R.settled) / R.settled.abs().where(R.settled.abs() > 1e5)
    write_csv(R, 'sra_reconciliation.csv')
    ok = R[(R.flow == 'MWFLOW') & (R.coverage > .99)]
    tot = ok.groupby(['asset', 'exporting_region'])[['computed_signed', 'settled']].sum()
    tot['bias_pct'] = 100 * (tot.computed_signed - tot.settled) / tot.settled.abs()
    return {f'{a}|{e}': round(float(v), 2) for (a, e), v in tot.bias_pct.items()}
