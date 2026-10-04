"""Phase 6 valuation tests.

Walk-forward baselines (extension 12): at every historical auction tranche whose delivery quarter
has settled, forecast the per-unit payoff using only quarters fully settled before the auction date.
Rules are frozen here, before scoring: last quarter; trailing 4, 8 and 12 quarters; same-season mean
(last three same-quarter-of-year observations); the ensemble of trailing-8 values for CRPS; and the
market (clearing price itself). Futures-scaled rule only if AER data are present.

Spread-option benchmark (extension 14): per-interval Bachelier (normal) call on the destination-minus-
origin spread, conditioned on regime (season x 4-hour block x flow-direction regime), with regime
means/variances and mean positive-direction flow estimated on the previous four settled quarters.
Value per unit = proportion x sum over intervals of E[flow+] x E[(spread)+]. Negative prices make a
lognormal (Margrabe/Kirk) model inappropriate; Margrabe is reported for positive-price intervals only
as a reference. Sensitivities scale spike frequency and severity in the regime distributions.

Strategic pilot (extension 16): importing-region offer-curve steepness when imports bind vs not.
"""
from __future__ import annotations

import io
import json
import zipfile
from urllib.parse import unquote

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import panel
from .config import ROOT, cfg, data, log, quarter_of, write_csv
from .market import PAIR_OF, realised_per_unit

EV = lambda n: ROOT / cfg()['report_root'] / 'evidence' / n


def crps_ensemble(members: np.ndarray, y: float) -> float:
    m = np.asarray(members, float)
    return float(np.mean(np.abs(m - y)) - 0.5 * np.mean(np.abs(m[:, None] - m[None, :])))


def walk_forward() -> tuple[pd.DataFrame, pd.DataFrame]:
    A = pd.read_csv(EV('auction_panel.csv'), parse_dates=['auction_date'])
    R = realised_per_unit()
    R['end'] = [pd.Period(q, 'Q').end_time for q in R.quarter]
    R['qn'] = [pd.Period(q, 'Q').quarter for q in R.quarter]
    rows = []
    for _, t in A[(A.UNITSSOLD > 0) & (A.CLEARINGPRICE > 0)].iterrows():
        actual = R[(R.quarter == t.delivery_quarter) & (R.direction == t.direction)]
        if not len(actual):
            continue
        y = float(actual.per_unit.iloc[0])
        hist = R[(R.direction == t.direction) & (R.end + pd.Timedelta(days=28) < t.auction_date)].sort_values('end')  # settled before auction
        if len(hist) < 4:
            continue
        dq = pd.Period(t.delivery_quarter, 'Q')
        v = hist.per_unit.values
        same = hist[hist.qn == dq.quarter].per_unit.values[-3:]
        f = {'last_quarter': v[-1], 'trailing_4q': v[-4:].mean(), 'trailing_8q': v[-8:].mean(), 'trailing_12q': v[-12:].mean(),
             'same_season': same.mean() if len(same) else np.nan, 'market_clearing_price': t.CLEARINGPRICE}
        for k, fc in f.items():
            rows.append(dict(direction=t.direction, delivery_quarter=t.delivery_quarter, tranche=t.tranche, quarters_ahead=t.quarters_ahead,
                             auction_date=t.auction_date.date(), rule=k, forecast=fc, actual=y, history_quarters=len(hist),
                             crps=crps_ensemble(v[-8:], y) if k == 'trailing_8q' else np.nan))
    W = pd.DataFrame(rows)
    W['error'] = W.forecast - W.actual
    S = W.dropna(subset=['forecast']).groupby('rule').agg(n=('error', 'size'), bias=('error', 'mean'), mae=('error', lambda e: e.abs().mean()),
                                                          median_abs_error=('error', lambda e: e.abs().median()), crps=('crps', 'mean')).reset_index()
    S['mae_skill_vs_market'] = 1 - S.mae / float(S[S.rule == 'market_clearing_price'].mae.iloc[0])
    return W, S


def _regimes(P: pd.DataFrame, F: pd.Series) -> pd.Series:
    t = P.index - pd.Timedelta('1ns')
    season = pd.Series(((t.month % 12) // 3), index=P.index)  # 0 summer, 1 autumn, 2 winter, 3 spring
    block = pd.Series(t.hour // 4, index=P.index)
    flowreg = pd.Series(np.where(F > 50, 2, np.where(F < -50, 0, 1)), index=P.index)
    return season * 100 + block * 10 + flowreg


def bachelier_call(mu, sd):
    sd = np.maximum(sd, 1e-9)
    z = mu / sd
    return sd * norm.pdf(z) + mu * norm.cdf(z)


def option_benchmark() -> tuple[pd.DataFrame, pd.DataFrame]:
    P = panel.prices()
    ics = panel.ic()
    q = quarter_of(P.index)
    R = realised_per_unit()
    units = pd.read_csv(EV('sra_unit_registry.csv'))
    quarters = sorted(set(q.astype(str)))
    rows, sens = [], []
    main = {'VICNSW': 'VIC1-NSW1', 'NSWVIC': 'VIC1-NSW1', 'NSWQLD': 'NSW1-QLD1', 'QLDNSW': 'NSW1-QLD1', 'VICSA': 'V-SA', 'SAVIC': 'V-SA'}
    for d, asset in main.items():
        o, dst = PAIR_OF[d]
        fr, to = cfg()['asset_direction'][asset]
        F = ics[asset].MWFLOW.reindex(P.index)
        Fd = F if (o, dst) == (fr, to) else -F
        x = P[dst] - P[o]
        reg = _regimes(P, F)
        df = pd.DataFrame({'q': q.astype(str), 'reg': reg, 'x': x, 'f': Fd.clip(lower=0)})
        for i, qq in enumerate(quarters):
            if i < 4:
                continue
            train = df[df.q.isin(quarters[i - 4:i])]
            test = df[df.q == qq]
            stats = train.groupby('reg').agg(mu=('x', 'mean'), sd=('x', 'std'), f=('f', 'mean'),
                                             spike=('x', lambda s: (s > 300).mean()), sev=('x', lambda s: s[s > 300].mean() if (s > 300).any() else 0.0))
            tr = test.reg.map(stats.mu), test.reg.map(stats.sd), test.reg.map(stats.f)
            call = bachelier_call(tr[0].fillna(0).values, tr[1].fillna(1).values)
            u = units[(units.quarter == qq) & (units.direction == d)]
            prop = float(u.PROPORTION.iloc[0]) / 100 if len(u) else 1 / cfg()['fallback_max_units'][d]
            # regime-product value (ignores within-regime flow/spread covariance)
            value = prop * float((tr[2].fillna(0).values * call).sum() / 12)
            real = R[(R.quarter == qq) & (R.direction == d)]
            rows.append(dict(direction=d, quarter=qq, option_value_per_unit=value, realised_per_unit=float(real.per_unit.iloc[0]) if len(real) else np.nan))
            if qq == quarters[-2]:
                # sensitivities: scale regime sd (severity proxy) and add spike mass (frequency) around the training estimates
                for k in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
                    c2 = bachelier_call(tr[0].fillna(0).values, k * tr[1].fillna(1).values)
                    sens.append(dict(direction=d, quarter=qq, factor='volatility (severity) multiplier', multiplier=k,
                                     value_per_unit=prop * float((tr[2].fillna(0).values * c2).sum() / 12)))
                    mu2 = tr[0].fillna(0).values + (k - 1) * test.reg.map(stats.spike).fillna(0).values * test.reg.map(stats.sev).fillna(0).values
                    c3 = bachelier_call(mu2, tr[1].fillna(1).values)
                    sens.append(dict(direction=d, quarter=qq, factor='spike frequency multiplier', multiplier=k,
                                     value_per_unit=prop * float((tr[2].fillna(0).values * c3).sum() / 12)))
    return pd.DataFrame(rows), pd.DataFrame(sens)


# ------------------------------------------------------------------ strategic-behaviour pilot
def _stream_bids(url: str, days: set, duids: set) -> pd.DataFrame:
    from nemic import ingest
    p = ingest.download(url)
    keep = []

    def streams(z):
        for name in z.namelist():
            if name.lower().endswith('.zip'):
                with z.open(name) as f:
                    yield from streams(zipfile.ZipFile(io.BytesIO(f.read())))
            elif name.lower().endswith('.csv'):
                yield z.open(name)

    with zipfile.ZipFile(p) as z:
        for inner in streams(z):
            header = None
            for raw in io.TextIOWrapper(inner, encoding='utf-8', errors='replace'):
                if raw.startswith('I,'):
                    header = raw.rstrip().split(',')[4:]
                    continue
                if not raw.startswith('D,') or header is None:
                    continue
                parts = raw.rstrip().split(',')[4:]
                row = dict(zip(header, parts))
                if row.get('BIDTYPE', 'ENERGY').strip('"') != 'ENERGY' or row.get('DUID', '').strip('"') not in duids:
                    continue
                ts = (row.get('INTERVAL_DATETIME') or row.get('SETTLEMENTDATE', '')).strip('"')
                if ts[:10].replace('/', '-') in days:
                    keep.append({k: v.strip('"') for k, v in row.items()})
    return pd.DataFrame(keep)


def strategic_pilot(n_days: int = 6) -> tuple[pd.DataFrame, dict]:
    """Offer-curve steepness in the importing region: price increase needed to call 200 MW more
    energy above the cleared regional stack, binding-import vs non-binding intervals on the same days."""
    from nemic.common import links
    from nemic import ingest
    P = panel.prices()
    ics = panel.ic()
    duid = pd.read_parquet(ROOT / 'data/nos_binding_v1/standing/DUDETAILSUMMARY.parquet')
    duid = duid.sort_values('START_DATE' if 'START_DATE' in duid else duid.columns[0]).drop_duplicates('DUID', keep='last')
    region_of = dict(zip(duid.DUID, duid.REGIONID))
    status = {'method': 'pilot: 10 highest-separation days per importing region (Sep 2023 - Jun 2026), at most 2 archive months each, energy offers only', 'regions': {}}
    rows = []
    jobs = []
    for d, asset, dst in [('VICNSW', 'VIC1-NSW1', 'NSW1'), ('VICSA', 'V-SA', 'SA1'), ('NSWQLD', 'NSW1-QLD1', 'QLD1')]:
        o = PAIR_OF[d][0]
        x = (P[dst] - P[o]).clip(lower=0)
        day = (P.index - pd.Timedelta('1ns')).normalize()
        top = x.groupby(day).mean().sort_values(ascending=False)
        top = top[(top.index >= pd.Timestamp('2023-09-01')) & (top.index < pd.Timestamp('2026-07-01'))].head(10)
        months = top.groupby(top.index.to_period('M')).size().sort_values(ascending=False).index[:2]
        for month in months:
            days = {str(t.date()) for t in top.index if t.to_period('M') == month}
            jobs.append((d, asset, dst, month, days))
    for d, asset, dst, month, days in jobs:
        folder = ingest.archive_dir(month.to_timestamp())
        try:
            url = next(u for u in links(folder) if ingest.is_table(u, 'BIDPEROFFER_D'))
        except StopIteration:
            status['regions'][f'{dst}|{month}'] = 'BIDPEROFFER_D not found'
            continue
        duids = {k for k, v in region_of.items() if v == dst}
        B = _stream_bids(url, days, duids)
        status['regions'][f'{dst}|{month}'] = dict(direction=d, days=sorted(days), rows=len(B))
        if not len(B):
            continue
        bd_url = next((u for u in links(folder) if ingest.is_table(u, 'BIDDAYOFFER_D')), None)
        prices = None
        if bd_url:
            from .acquire import extract_all
            bd = extract_all(ingest.download(bd_url))
            bdf = next(iter(bd.values()))
            bdf = bdf[(bdf.get('BIDTYPE', 'ENERGY') == 'ENERGY') & bdf.DUID.isin(duids)]
            bdf['day'] = pd.to_datetime(bdf.SETTLEMENTDATE.str.replace('/', '-')).dt.strftime('%Y-%m-%d')
            prices = bdf[bdf.day.isin(days)]
        if prices is None or not len(prices):
            continue
        band_cols = [f'PRICEBAND{i}' for i in range(1, 11)]
        avail_cols = [f'BANDAVAIL{i}' for i in range(1, 11)]
        B['time'] = pd.to_datetime((B.get('INTERVAL_DATETIME') if 'INTERVAL_DATETIME' in B else B.SETTLEMENTDATE).str.replace('/', '-'))
        B['day'] = B.time.dt.normalize().dt.strftime('%Y-%m-%d')
        pb = prices.sort_values('OFFERDATE' if 'OFFERDATE' in prices else 'SETTLEMENTDATE').drop_duplicates(['DUID', 'day'], keep='last')[['DUID', 'day'] + band_cols]
        M = B.merge(pb, on=['DUID', 'day'])
        for c in band_cols + avail_cols + ['MAXAVAIL']:
            if c in M:
                M[c] = pd.to_numeric(M[c], errors='coerce')
        g = ics[asset].reindex(P.index)
        fr, to = cfg()['asset_direction'][asset]
        binding = (g.MWFLOW >= g.EXPORTLIMIT - 1) if to == dst else (g.MWFLOW <= g.IMPORTLIMIT + 1)
        for t, s in M.groupby('time'):
            steps = pd.DataFrame({'p': s[band_cols].values.ravel(), 'q': s[avail_cols].values.ravel()}).dropna()
            steps = steps[steps.q > 0].sort_values('p')
            if not len(steps) or t not in P.index:
                continue
            steps['cum'] = steps.q.cumsum()
            rrp = P.at[t, dst]
            cleared = steps[steps.p <= rrp].q.sum()
            above = steps[steps.cum >= cleared + 200]
            p200 = float(above.p.iloc[0]) if len(above) else np.nan
            rows.append(dict(importing_region=dst, direction=d, time=t, rrp=rrp, cleared_mw_at_or_below_rrp=cleared,
                             price_for_next_200mw=p200, steepness_per_mw=(p200 - rrp) / 200 if np.isfinite(p200) else np.nan,
                             import_binding=bool(binding.get(t, False))))
    return pd.DataFrame(rows), status


def run() -> dict:
    log('valuation', 'started')
    W, S = walk_forward()
    write_csv(W, 'walk_forward_forecasts.csv'); write_csv(S, 'walk_forward_scores.csv')
    O, sens = option_benchmark()
    write_csv(O, 'option_benchmark.csv'); write_csv(sens, 'option_sensitivity.csv')
    info = dict(walk_forward_rows=len(W), scores=S.set_index('rule').mae.round(0).to_dict())
    try:
        SP, st = strategic_pilot()
        write_csv(SP, 'strategic_pilot.csv')
        (EV('strategic_pilot_status.json')).write_text(json.dumps(st, indent=2, default=str))
        if len(SP):
            info['strategic'] = {f'{k[0]}|binding={k[1]}': v for k, v in SP.groupby(['importing_region', 'import_binding']).steepness_per_mw.median().round(3).items()}
    except Exception as e:  # pilot is exploratory; record failure without blocking the campaign
        EV('strategic_pilot_status.json').write_text(json.dumps({'error': str(e)[:500]}, indent=2))
        info['strategic_error'] = str(e)[:200]
    log('valuation', 'completed', **{k: str(v) for k, v in info.items()})
    return info
