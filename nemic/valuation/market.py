"""Phase 4 market side: auction prices vs realised payoffs, auction microstructure and returns,
hedge effectiveness of SRA units against a flat futures-style spread, and AER base-futures premia.

Realised payoffs come from the pre-loop settlement ledger (dispatch flows, dated loss shares).
Per-unit payoff = PROPORTION x positive directional residue in the delivery quarter.
Premium (realised minus price) is the ex-post excess return to a unit buyer before funding.
Uncertainty uses a cluster bootstrap over delivery quarters, because every tranche of a quarter
shares the same realised outcome.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from . import aer, panel
from .acquire import load
from .config import ROOT, cfg, data, log, quarter_of, write_csv
from .settlement import SRA_KEY, DIRECTIONS

PAIR_OF = {'VICNSW': ('VIC1', 'NSW1'), 'NSWVIC': ('NSW1', 'VIC1'), 'NSWQLD': ('NSW1', 'QLD1'), 'QLDNSW': ('QLD1', 'NSW1'),
           'VICSA': ('VIC1', 'SA1'), 'SAVIC': ('SA1', 'VIC1'), 'TASVIC': ('TAS1', 'VIC1'), 'VICTAS': ('VIC1', 'TAS1')}


def _ts(s):
    return pd.to_datetime(s.astype(str).str.replace('/', '-'), errors='coerce')


def _latest(x: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if 'VERSIONNO' in x:
        x = x.assign(_v=pd.to_numeric(x.VERSIONNO, errors='coerce')).sort_values('_v')
    elif 'LASTCHANGED' in x:
        x = x.sort_values('LASTCHANGED')
    return x.drop_duplicates(keys, keep='last')


def auction_panel() -> pd.DataFrame:
    x = _latest(load('RESIDUE_PUBLIC_DATA'), ['CONTRACTID', 'INTERCONNECTORID', 'FROMREGIONID'])
    m = x.CONTRACTID.str.extract(r'C(\d{4})Q(\d)T(\d{2})')
    x['delivery_quarter'] = [f'{y}Q{q}' for y, q in zip(m[0], m[1])]
    x['tranche'] = pd.to_numeric(m[2])
    x['direction'] = [SRA_KEY.get((i, f)) for i, f in zip(x.INTERCONNECTORID, x.FROMREGIONID)]
    for c in ['UNITSOFFERED', 'UNITSSOLD', 'CLEARINGPRICE', 'RESERVEPRICE']:
        x[c] = pd.to_numeric(x[c], errors='coerce')
    rc = _latest(load('RESIDUE_CONTRACTS'), ['CONTRACTID'])[['CONTRACTID', 'AUCTIONDATE', 'AUCTIONID', 'STARTDATE']]
    x = x.merge(rc, on='CONTRACTID', how='left')
    at = _latest(load('AUCTION_TRANCHE'), ['CONTRACTYEAR', 'QUARTER', 'TRANCHE'])
    at['delivery_quarter'] = at.CONTRACTYEAR.astype(str) + 'Q' + at.QUARTER.astype(str)
    at['tranche'] = pd.to_numeric(at.TRANCHE)
    x = x.merge(at[['delivery_quarter', 'tranche', 'AUCTIONDATE']].rename(columns={'AUCTIONDATE': 'AUCTIONDATE_T'}), on=['delivery_quarter', 'tranche'], how='left')
    x['auction_date'] = _ts(x.AUCTIONDATE.fillna(x.AUCTIONDATE_T))
    x['delivery_start'] = [pd.Period(q, 'Q').start_time for q in x.delivery_quarter]
    x['days_ahead'] = (x.delivery_start - x.auction_date).dt.days
    x['quarters_ahead'] = 13 - x.tranche  # tranche 12 is sold in the quarter before delivery
    x['horizon'] = pd.cut(x.quarters_ahead, [0, 2, 4, 8, 12], labels=['1-2 quarters', '3-4 quarters', '5-8 quarters', '9-12 quarters'])
    cal = _latest(load('AUCTION_CALENDAR'), ['CONTRACTYEAR', 'QUARTER'])
    cal['delivery_quarter'] = cal.CONTRACTYEAR.astype(str) + 'Q' + cal.QUARTER.astype(str)
    cal['payment_date'] = _ts(cal.PAYMENTDATE)
    x = x.merge(cal[['delivery_quarter', 'payment_date']], on='delivery_quarter', how='left')
    x = x.dropna(subset=['direction'])
    return x[['CONTRACTID', 'AUCTIONID', 'auction_date', 'delivery_quarter', 'tranche', 'quarters_ahead', 'days_ahead', 'horizon',
              'direction', 'INTERCONNECTORID', 'FROMREGIONID', 'UNITSOFFERED', 'UNITSSOLD', 'CLEARINGPRICE', 'RESERVEPRICE', 'payment_date']]


def realised_per_unit(variant: str = 'settled') -> pd.DataFrame:
    L = pd.read_csv(ROOT / cfg()['report_root'] / 'evidence/sra_ledger_quarterly.csv')
    return L[(L.variant == variant) & L.complete][['quarter', 'direction', 'per_unit', 'per_unit_net_fee', 'residue_pos', 'residue_neg', 'proportion', 'max_units']]


def cluster_bootstrap(df: pd.DataFrame, stat, reps: int, seed: int) -> tuple[float, float]:
    qs = df.delivery_quarter.unique()
    if len(qs) < 3:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    groups = {q: df[df.delivery_quarter == q] for q in qs}
    vals = []
    for _ in range(reps):
        pick = rng.choice(qs, size=len(qs), replace=True)
        vals.append(stat(pd.concat([groups[q] for q in pick])))
    return tuple(np.nanpercentile(vals, [2.5, 97.5]))


def premium_tables(A: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    R = realised_per_unit()
    J = A.merge(R, left_on=['delivery_quarter', 'direction'], right_on=['quarter', 'direction'], how='inner')
    J = J[(J.UNITSSOLD > 0) & (J.CLEARINGPRICE > 0)].copy()
    J['premium'] = J.per_unit - J.CLEARINGPRICE
    J['ratio'] = J.per_unit / J.CLEARINGPRICE
    b = cfg()['bootstrap']
    vw = lambda d: (d.per_unit * d.UNITSSOLD).sum() / (d.CLEARINGPRICE * d.UNITSSOLD).sum()
    rows = []
    for keys, g in [(('all', 'all'), J)] + [((d, 'all'), g) for d, g in J.groupby('direction')] + \
                   [(('all', h), g) for h, g in J.groupby('horizon', observed=True)] + \
                   [((d, h), g) for (d, h), g in J.groupby(['direction', 'horizon'], observed=True)]:
        lo, hi = cluster_bootstrap(g, vw, b['replicates'], b['seed'])
        rows.append(dict(direction=keys[0], horizon=str(keys[1]), tranches=len(g), delivery_quarters=g.delivery_quarter.nunique(),
                         value_weighted_ratio=vw(g), ci_low=lo, ci_high=hi, median_ratio=g.ratio.median(),
                         share_tranches_realised_above_price=(g.ratio > 1).mean(), mean_premium_per_unit=g.premium.mean()))
    S = pd.DataFrame(rows)
    # heatmap: value-weighted ratio by direction x delivery quarter
    H = J.groupby(['direction', 'delivery_quarter']).apply(lambda d: pd.Series({'ratio': vw(d), 'units_sold': d.UNITSSOLD.sum(),
                                                                                 'avg_price': (d.CLEARINGPRICE * d.UNITSSOLD).sum() / d.UNITSSOLD.sum(),
                                                                                 'realised': d.per_unit.iloc[0]}), include_groups=False).reset_index()
    return J, S, H


def proceeds_vs_residue(A: pd.DataFrame) -> pd.DataFrame:
    """Consumer/TNSP view: auction proceeds vs the residue sold (units sold x proportion x residue)."""
    R = realised_per_unit()
    g = A[A.UNITSSOLD > 0].groupby(['delivery_quarter', 'direction']).apply(
        lambda d: pd.Series({'proceeds': (d.CLEARINGPRICE * d.UNITSSOLD).sum(), 'units_sold': d.UNITSSOLD.sum()}), include_groups=False).reset_index()
    g = g.merge(R, left_on=['delivery_quarter', 'direction'], right_on=['quarter', 'direction'])
    g['distributed_to_holders'] = g.per_unit * g.units_sold
    g['share_of_units_sold'] = g.units_sold / g.max_units
    return g.drop(columns='quarter')


def microstructure(A: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    B = load('RESIDUE_PRICE_FUNDS_BID')
    for c in ['UNITS', 'BIDPRICE']:
        B[c] = pd.to_numeric(B[c], errors='coerce')
    B = B.drop_duplicates(['CONTRACTID', 'INTERCONNECTORID', 'FROMREGIONID', 'LINKEDBIDFLAG', 'AUCTIONID', 'UNITS', 'BIDPRICE'])
    B['direction'] = [SRA_KEY.get((i, f)) for i, f in zip(B.INTERCONNECTORID, B.FROMREGIONID)]
    B = B.dropna(subset=['direction'])
    k = ['AUCTIONID', 'CONTRACTID', 'direction']
    agg = B.groupby(k).agg(bid_steps=('UNITS', 'size'), units_bid=('UNITS', 'sum'), max_bid=('BIDPRICE', 'max'),
                           median_bid=('BIDPRICE', 'median')).reset_index()
    agg = agg.merge(A[['CONTRACTID', 'direction', 'delivery_quarter', 'tranche', 'quarters_ahead', 'UNITSOFFERED', 'UNITSSOLD', 'CLEARINGPRICE', 'RESERVEPRICE', 'auction_date']],
                    on=['CONTRACTID', 'direction'], how='left')
    agg['bid_to_offer'] = agg.units_bid / agg.UNITSOFFERED
    agg['unsold_units'] = agg.UNITSOFFERED - agg.UNITSSOLD
    # bid curve for the latest auction (all contracts), for the chart
    latest = B.AUCTIONID.max()
    C = B[B.AUCTIONID == latest].sort_values('BIDPRICE', ascending=False)
    C['cum_units'] = C.groupby(['CONTRACTID', 'direction']).UNITS.cumsum()
    return agg, C[['AUCTIONID', 'CONTRACTID', 'direction', 'BIDPRICE', 'UNITS', 'cum_units']]


def returns(A: pd.DataFrame, series: pd.DataFrame) -> pd.DataFrame:
    """Holding-period and annualised return per delivered tranche: pay the clearing price on the
    calendar PAYMENTDATE; receive weekly distributions with an assumed 21-day settlement lag."""
    q = quarter_of(series.index)
    wk = (series.index - pd.Timedelta('1ns')).to_period('W').end_time.normalize()
    rows = []
    R = realised_per_unit()
    for (dq, d), g in A[(A.UNITSSOLD > 0) & (A.CLEARINGPRICE > 0)].groupby(['delivery_quarter', 'direction']):
        r = R[(R.quarter == dq) & (R.direction == d)]
        if not len(r):
            continue
        prop = float(r.proportion.iloc[0])
        m = (q == pd.Period(dq, 'Q'))
        weekly = series.loc[m, f'{d}_pos'].groupby(wk[m]).sum() * prop
        pay_dates = weekly.index + pd.Timedelta(days=21)
        tot = weekly.sum()
        for _, t in g.iterrows():
            pd0 = t.payment_date if pd.notna(t.payment_date) else pd.Period(dq, 'Q').start_time + pd.Timedelta(days=20)
            if tot > 0:
                mean_days = float(((pay_dates - pd0).days.values * weekly.values).sum() / tot)
            else:
                mean_days = float((pay_dates - pd0).days.values.mean())
            hpr = tot / t.CLEARINGPRICE - 1
            ann = (1 + hpr) ** (365 / max(mean_days, 1)) - 1 if hpr > -1 else -1.0
            rows.append(dict(delivery_quarter=dq, direction=d, tranche=t.tranche, quarters_ahead=t.quarters_ahead, price=t.CLEARINGPRICE,
                             realised=tot, holding_period_return=hpr, mean_days_to_cash=mean_days, annualised_return=ann))
    return pd.DataFrame(rows)


def hedging(series: pd.DataFrame, A: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Weekly unit payoff vs 1 MW flat long-destination/short-origin spread P&L."""
    P = panel.prices()
    q = quarter_of(P.index)
    wk = (P.index - pd.Timedelta('1ns')).to_period('W')
    R = realised_per_unit()
    units = pd.read_csv(ROOT / cfg()['report_root'] / 'evidence/sra_unit_registry.csv')
    stress_n = cfg()['stress']['top_weeks']; alpha = cfg()['stress']['cvar_alpha']
    rows, points, frontier = [], [], []
    avg_price = A[(A.UNITSSOLD > 0)].groupby(['delivery_quarter', 'direction']).apply(
        lambda d: (d.CLEARINGPRICE * d.UNITSSOLD).sum() / d.UNITSSOLD.sum(), include_groups=False)
    for d in DIRECTIONS:
        o, t = PAIR_OF[d]
        if d in ('TASVIC', 'VICTAS'):
            continue
        prop = pd.Series([float(units[(units.quarter == str(p)) & (units.direction == d)].PROPORTION.iloc[0]) / 100
                          if len(units[(units.quarter == str(p)) & (units.direction == d)]) else 1 / cfg()['fallback_max_units'][d] for p in q.unique()],
                         index=q.unique())
        u = series[f'{d}_pos'] * pd.Series(q, index=P.index).map(prop).values
        s = (P[t] - P[o]) / 12
        W = pd.DataFrame({'w': wk, 'u': u.values, 's': s.values, 'q': q}).groupby('w').agg(u=('u', 'sum'), s=('s', 'sum'), q=('q', 'first'), n=('u', 'size'))
        W = W[W.n == 2016]  # full weeks only
        beta = np.cov(W.u, W.s)[0, 1] / W.s.var()
        top = W.s.nlargest(stress_n).index
        n_mv = np.cov(W.u, W.s)[0, 1] / W.u.var()
        rows.append(dict(direction=d, weeks=len(W), beta_unit_on_spread=beta, r2=np.corrcoef(W.u, W.s)[0, 1] ** 2,
                         spearman=W.u.corr(W.s, method='spearman'), ratio_all=W.u.sum() / W.s.sum(),
                         ratio_top_spread_weeks=W.u[top].sum() / W.s[top].sum(), units_min_variance_per_mw=n_mv,
                         variance_reduction=1 - (W.s - n_mv * W.u).var() / W.s.var()))
        points.append(W.reset_index().assign(direction=d, stress=lambda x: x.w.isin(top)).assign(w=lambda x: x.w.astype(str), q=lambda x: x.q.astype(str)))
        # CVaR frontier for a desk short 1 MW of the flat spread, hedged with n units bought at the
        # quarter's volume-weighted clearing price (spread evenly over 13 weeks); futures leg not priced (AER only).
        cost = W.q.map(lambda p: avg_price.get((str(p), d), np.nan)) / 13
        cost = cost.fillna(cost.mean())
        for n in np.linspace(0, max(3 * n_mv, 1), 31):
            pnl = -W.s + n * (W.u - cost)
            loss = -pnl
            var = np.quantile(loss, alpha)
            cvar = loss[loss >= var].mean()
            frontier.append(dict(direction=d, units=n, mean_weekly_pnl=pnl.mean(), cvar_weekly_loss=cvar, sd=pnl.std()))
    return pd.DataFrame(rows), pd.concat(points, ignore_index=True), pd.DataFrame(frontier)


def futures() -> dict:
    F, status = aer.load()
    (ROOT / cfg()['report_root'] / 'evidence/futures_status.json').write_text(json.dumps(status, indent=2, default=str))
    if not len(F):
        return status
    reg = pd.read_csv(ROOT / cfg()['report_root'] / 'evidence/regional_decomposition.csv')
    reg = reg[reg.complete][['quarter', 'region', 'mean_price']]
    F['delivery_start'] = [pd.Period(q, 'Q').start_time for q in F.contract_quarter]
    pre = F[F.date < F.delivery_start]
    last = pre.sort_values('date').groupby(['region', 'contract_quarter']).tail(1)
    out = last.merge(reg, left_on=['contract_quarter', 'region'], right_on=['quarter', 'region'], how='inner')
    out['ex_post_premium'] = out.price - out.mean_price
    out['days_before_delivery'] = (out.delivery_start - out.date).dt.days
    write_csv(out.drop(columns=['quarter']), 'futures_premia.csv')
    write_csv(F, 'futures_paths.csv')
    sp = []
    for d, (o, t) in PAIR_OF.items():
        a = out[out.region == o].set_index('contract_quarter'); b = out[out.region == t].set_index('contract_quarter')
        common = a.index.intersection(b.index)
        for cq in common:
            sp.append(dict(direction=d, contract_quarter=cq, futures_spread=b.price[cq] - a.price[cq], realised_spread=b.mean_price[cq] - a.mean_price[cq]))
    S = pd.DataFrame(sp)
    if len(S):
        S['spread_premium'] = S.futures_spread - S.realised_spread
        write_csv(S, 'futures_spread_premia.csv')
    status.update(premia_rows=len(out), spread_rows=len(S))
    return status


def run() -> dict:
    log('market', 'started')
    A = auction_panel()
    write_csv(A, 'auction_panel.csv')
    J, S, H = premium_tables(A)
    write_csv(J, 'auction_vs_realised.csv'); write_csv(S, 'auction_premium_summary.csv'); write_csv(H, 'auction_premium_heatmap.csv')
    write_csv(proceeds_vs_residue(A), 'auction_proceeds_vs_residue.csv')
    agg, curve = microstructure(A)
    write_csv(agg, 'auction_microstructure.csv'); write_csv(curve, 'auction_bid_curve_latest.csv')
    series = pd.read_parquet(data('settlement', 'directional_5min.parquet'))
    write_csv(returns(A, series), 'auction_returns.csv')
    hs, pts, fr = hedging(series, A)
    write_csv(hs, 'hedge_effectiveness.csv'); write_csv(pts, 'hedge_weekly_points.csv'); write_csv(fr, 'hedge_cvar_frontier.csv')
    fut = futures()
    info = dict(auction_rows=len(A), joined_tranches=len(J), futures_observed=fut.get('observed'),
                overall_ratio=float(S[(S.direction == 'all') & (S.horizon == 'all')].value_weighted_ratio.iloc[0]))
    log('market', 'completed', **info)
    return info
