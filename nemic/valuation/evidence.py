"""Phase 3 evidence base: audit, loss/congestion, uncertainty, cap normalisation, diurnal, dependence.

Loss/congestion split (exact, per interval) using the interconnector's dispatch marginal loss
factor (MLF). With the coupled reference price P* = MLF * P_from:

    P_to - P_from = (P* - P_from) + (P_to - P*)          [loss part] + [congestion part]

Each part splits again into capped energy and scarcity with the same K = $300 operator, so the
2x2 table (energy/scarcity x loss/congestion) sums exactly to the spread.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from nemic.experiments.clustering.protocol import moving_block_indices
from . import panel
from .acquire import load
from .config import ROOT, cfg, complete_quarter_intervals, log, quarter_of, sha256, write_csv, data

K = 300.0
MAIN_ASSET = {'VIC-NSW': 'VIC1-NSW1', 'NSW-QLD': 'NSW1-QLD1', 'VIC-SA': 'V-SA', 'TAS-VIC': 'T-V-MNSP1'}
CANON = {'VIC-NSW': ('VIC1', 'NSW1', 'NSW − VIC'), 'NSW-QLD': ('NSW1', 'QLD1', 'QLD − NSW'),
         'VIC-SA': ('VIC1', 'SA1', 'SA − VIC'), 'TAS-VIC': ('TAS1', 'VIC1', 'VIC − TAS')}


def complete_mask(index) -> pd.Series:
    q = quarter_of(index)
    n = pd.Series(1, index=index).groupby(q).transform('size')
    need = pd.Series([complete_quarter_intervals(p) for p in q], index=index)
    return (n == need)


# ------------------------------------------------------------------ audit (Phase 1 gate)
def audit(P: pd.DataFrame, fl: pd.DataFrame) -> dict:
    q = quarter_of(P.index)
    comp = complete_mask(P.index)
    firm = fl.assign(q=quarter_of(pd.DatetimeIndex(fl.time)))
    nf = firm[firm.PRICE_STATUS != 'FIRM']
    flag_counts = {name: int(fl[name].sum()) for name in ['apc_binding', 'voll_override', 'mpc_binding', 'manual_override', 'irlf_scaling']}
    susp = fl[fl.MARKETSUSPENDEDFLAG.fillna(0) != 0]
    # sensitivity: quarterly spread with and without suspension-flag intervals
    S = fl.assign(s=fl.MARKETSUSPENDEDFLAG.fillna(0) != 0).pivot(index='time', columns='REGIONID', values='s').reindex(P.index).fillna(False)
    sens = []
    for pr, (a, b, lab) in CANON.items():
        x = P[b] - P[a]
        m = S[a] | S[b]
        g = pd.DataFrame({'q': q, 'all': x, 'excl': x.where(~m)}).groupby('q').mean()
        sens.append(dict(pair=lab, max_abs_change=float((g['all'] - g['excl']).abs().max())))
    inputs = {}
    for folder in ['DISPATCHPRICE', 'DISPATCHINTERCONNECTORRES']:
        files = sorted((ROOT / 'data/tables' / folder).glob('*.parquet'))
        inputs[folder] = dict(files=len(files), sha256_of_hashes=__import__('hashlib').sha256(''.join(sha256(f) for f in files).encode()).hexdigest())
    for folder in sorted((ROOT / cfg()['data_root'] / 'tables').glob('*')):
        files = sorted(folder.glob('*.parquet'))
        inputs[folder.name] = dict(files=len(files), sha256_of_hashes=__import__('hashlib').sha256(''.join(sha256(f) for f in files).encode()).hexdigest())
    return dict(intervals=len(P), complete_quarters=int(len(set(q[comp]))), first=str(P.index.min()), last=str(P.index.max()),
                not_firm_rows=int(len(nf)), not_firm_in_complete_quarters=int(nf.q.isin(set(q[comp])).sum()),
                apcflag_bits=flag_counts, suspension_rows=int(len(susp)),
                suspension_dates=sorted({str(t.date()) for t in pd.to_datetime(susp.time)}),
                suspension_sensitivity=sens, input_hashes=inputs)


# ------------------------------------------------------------------ loss / congestion
def loss_congestion(P: pd.DataFrame, ics: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    q = quarter_of(P.index)
    rows, fits = [], []
    for pr, (a, b, lab) in CANON.items():
        asset = MAIN_ASSET[pr]
        g = ics[asset].reindex(P.index)
        fr, to = cfg()['asset_direction'][asset]
        mlf = g.MARGINALLOSS
        # express in canonical sign (b - a)
        pstar = P[fr] * mlf
        loss_ft = pstar - P[fr]
        cong_ft = P[to] - pstar
        e_loss = pstar.clip(upper=K) - P[fr].clip(upper=K)
        e_cong = P[to].clip(upper=K) - pstar.clip(upper=K)
        sgn = 1.0 if (fr, to) == (a, b) else -1.0
        coupled = cong_ft.abs() <= np.maximum(0.01, 1e-4 * P[fr].abs())
        df = pd.DataFrame({'q': q, 'spread': sgn * (P[to] - P[fr]), 'loss': sgn * loss_ft, 'congestion': sgn * cong_ft,
                           'energy_loss': sgn * e_loss, 'scarcity_loss': sgn * (loss_ft - e_loss),
                           'energy_congestion': sgn * e_cong, 'scarcity_congestion': sgn * (cong_ft - e_cong),
                           'coupled': coupled, 'mlf_missing': mlf.isna()})
        t = df.groupby('q').mean()
        t['coupled_pct'] = 100 * t.pop('coupled')
        t['n'] = df.groupby('q').size()
        t['complete'] = [int(t.n[p]) == complete_quarter_intervals(p) for p in t.index]
        t.insert(0, 'pair', lab); t.insert(1, 'asset', asset)
        rows.append(t.reset_index().rename(columns={'q': 'quarter'}))
        # empirical loss curve MLF = c0 + c1*F by financial year (AEMO equations add regional demand terms)
        F = g.MWFLOW
        fy = [f'FY{(t.year + (1 if t.month >= 7 else 0)) % 100:02d}' for t in (P.index - pd.Timedelta('1ns'))]
        d = pd.DataFrame({'F': F, 'mlf': mlf, 'fy': fy}).dropna()
        for y, gg in d.groupby('fy'):
            c1, c0 = np.polyfit(gg.F, gg.mlf, 1)
            fits.append(dict(asset=asset, pair=lab, fy=y, intercept=c0, slope_per_mw=c1, r2=float(np.corrcoef(gg.F, gg.mlf)[0, 1] ** 2), n=len(gg)))
    out = pd.concat(rows, ignore_index=True)
    out['quarter'] = out.quarter.astype(str)
    return out, pd.DataFrame(fits)


def mlf_scatter_sample(P, ics, n=4000, seed=7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for pr, asset in MAIN_ASSET.items():
        g = ics[asset].reindex(P.index)[['MWFLOW', 'MARGINALLOSS']].dropna()
        idx = rng.choice(len(g), size=min(n, len(g)), replace=False)
        s = g.iloc[np.sort(idx)]
        rows.append(pd.DataFrame({'asset': asset, 'flow': s.MWFLOW.values, 'mlf': s.MARGINALLOSS.values}))
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------------------ uncertainty
def bootstrap_quarters(P: pd.DataFrame, replicates: int, block_days: int, seed: int) -> pd.DataFrame:
    """Moving day-block bootstrap of each complete quarter's mean spread, energy and scarcity."""
    q = quarter_of(P.index)
    day = (P.index - pd.Timedelta('1ns')).normalize()
    comp = complete_mask(P.index)
    rows = []
    for pr, (a, b, lab) in CANON.items():
        x = P[b] - P[a]; e = P[b].clip(upper=K) - P[a].clip(upper=K)
        D = pd.DataFrame({'q': q, 'day': day, 'x': x, 'e': e, 'c': x - e})[comp.values]
        for quarter, g in D.groupby('q'):
            daily = g.groupby('day')[['x', 'e', 'c']].mean()
            idx = moving_block_indices(len(daily), block_days, replicates, seed)
            vals = daily.values[idx].mean(axis=1)  # replicates x 3
            for j, comp_name in enumerate(['spread', 'energy', 'scarcity']):
                lo, hi = np.percentile(vals[:, j], [2.5, 97.5])
                rows.append(dict(pair=lab, quarter=str(quarter), component=comp_name, estimate=float(daily.values[:, j].mean()),
                                 ci_low=lo, ci_high=hi, block_days=block_days, replicates=replicates))
    return pd.DataFrame(rows)


def leave_one_day_out(P: pd.DataFrame) -> pd.DataFrame:
    q = quarter_of(P.index); day = (P.index - pd.Timedelta('1ns')).date
    comp = complete_mask(P.index)
    rows = []
    for pr, (a, b, lab) in CANON.items():
        x = P[b] - P[a]
        for quarter in sorted(set(q[comp.values])):
            m = (q == quarter)
            s = x[m]; dsum = s.groupby(day[m]).sum()
            order = dsum.abs().sort_values(ascending=False)
            top = order.index[0]
            rows.append(dict(pair=lab, quarter=str(quarter), spread=s.mean(), without_top_day=s[day[m] != top].mean(),
                             without_top3_days=s[~np.isin(day[m], order.index[:3])].mean(), top_day=str(top),
                             top_day_share_pct=100 * dsum[top] / s.sum() if s.sum() else np.nan,
                             sign_flip=bool(np.sign(s.mean()) != np.sign(s[day[m] != top].mean()))))
    return pd.DataFrame(rows)


def extremogram(P: pd.DataFrame, lags=(0, 1, 3, 6, 12, 24, 48, 96, 144, 288), u: float = K) -> pd.DataFrame:
    """Cross-regional extremogram: Pr(Y_{t+h} > u | X_t > u) for five-minute lags h."""
    regs = ['NSW1', 'QLD1', 'SA1', 'VIC1', 'TAS1']
    E = P[regs] > u
    rows = []
    for x in regs:
        base = E[x].values
        n = base.sum()
        for y in regs:
            for h in lags:
                yy = np.roll(E[y].values, -h)
                valid = np.ones(len(base), bool); valid[len(base) - h:] = False if h else True
                num = (base & yy & valid).sum(); den = (base & valid).sum()
                rows.append(dict(conditioning=x, response=y, lag_intervals=h, lag_hours=h / 12, probability=num / den if den else np.nan,
                                 unconditional=E[y].mean(), conditioning_events=int(n)))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ market price cap normalisation
def mpc_schedule(index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series, dict]:
    x = load('MARKET_PRICE_THRESHOLDS')
    x['eff'] = pd.to_datetime(x.EFFECTIVEDATE.str.replace('/', '-'))
    x['ver'] = pd.to_numeric(x.VERSIONNO)
    for c in ['VOLL', 'MARKETPRICEFLOOR', 'ADMINISTERED_PRICE_THRESHOLD']:
        x[c] = pd.to_numeric(x[c], errors='coerce')
    x = x.sort_values(['eff', 'ver']).drop_duplicates('eff', keep='last').set_index('eff')
    mpc = x.VOLL.reindex(x.index.union(index)).ffill().reindex(index)
    cpt = x.ADMINISTERED_PRICE_THRESHOLD.reindex(x.index.union(index)).ffill().reindex(index)
    table = {str(k.date()): dict(mpc=float(v.VOLL), floor=float(v.MARKETPRICEFLOOR),
                                 cpt=float(v.ADMINISTERED_PRICE_THRESHOLD) if np.isfinite(v.ADMINISTERED_PRICE_THRESHOLD) else None)
             for k, v in x[x.index >= pd.Timestamp('2020-07-01')].iterrows()}
    return mpc, cpt, table


def mpc_normalised(P: pd.DataFrame, fl: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    mpc, cpt, table = mpc_schedule(P.index)
    target = float(mpc.iloc[-1])
    fy27 = [v['mpc'] for k, v in table.items() if k >= '2026-07-01']
    if fy27:
        target = fy27[0]
    at_cap = P.ge(mpc.values[:, None] * 0.999)
    Pn = P.where(~at_cap, P.mul(target / mpc, axis=0))
    q = quarter_of(P.index)
    rows = []
    for pr, (a, b, lab) in CANON.items():
        for name, M in [('raw', P), ('normalised', Pn)]:
            c = (M[b] - K).clip(lower=0) - (M[a] - K).clip(lower=0)
            s = pd.DataFrame({'q': q, 'c': c, 'x': M[b] - M[a]}).groupby('q').mean()
            for quarter, r in s.iterrows():
                rows.append(dict(pair=lab, quarter=str(quarter), basis=name, scarcity=r.c, spread=r.x))
    cap_intervals = {r: int(at_cap[r].sum()) for r in P}
    return pd.DataFrame(rows), dict(target_mpc=target, schedule=table, intervals_at_cap=cap_intervals)


# ------------------------------------------------------------------ diurnal / seasonal profile
def diurnal(P: pd.DataFrame, residue: pd.DataFrame | None, ics: dict) -> pd.DataFrame:
    t = P.index - pd.Timedelta('1ns')
    season = pd.Series(t.month, index=P.index).map({12: 'Summer', 1: 'Summer', 2: 'Summer', 3: 'Autumn', 4: 'Autumn', 5: 'Autumn',
                                                    6: 'Winter', 7: 'Winter', 8: 'Winter', 9: 'Spring', 10: 'Spring', 11: 'Spring'})
    hour = pd.Series(t.hour, index=P.index)
    rows = []
    for pr, (a, b, lab) in CANON.items():
        x = P[b] - P[a]
        F = ics[MAIN_ASSET[pr]].MWFLOW.reindex(P.index)
        fr, to = cfg()['asset_direction'][MAIN_ASSET[pr]]
        toward_b = (F > 0) if (fr, to) == (a, b) else (F < 0)
        df = pd.DataFrame({'season': season, 'hour': hour, 'spread': x, 'toward_dest_pct': 100 * toward_b.astype(float),
                           'dest_above_300_pct': 100 * (P[b] > K), 'origin_above_300_pct': 100 * (P[a] > K),
                           'negative_either_pct': 100 * ((P[a] < 0) | (P[b] < 0))})
        if residue is not None:
            code_ab = next(p['sra_ab'] for p in cfg()['pairs'] if p['pair'] == pr)
            code_ba = next(p['sra_ba'] for p in cfg()['pairs'] if p['pair'] == pr)
            df['residue_ab_per_hour'] = residue[f'{code_ab}_pos'].reindex(P.index).values * 12
            df['residue_ba_per_hour'] = residue[f'{code_ba}_pos'].reindex(P.index).values * 12
        g = df.groupby(['season', 'hour']).mean().reset_index()
        g.insert(0, 'pair', lab)
        rows.append(g)
    return pd.concat(rows, ignore_index=True)


# ------------------------------------------------------------------ dependence (M-01 extension)
def tail_dependence(P: pd.DataFrame, ics: dict) -> pd.DataFrame:
    rows = []
    for pr, (a, b, lab) in CANON.items():
        asset = MAIN_ASSET[pr]
        f = ics[asset].MWFLOW.reindex(P.index)
        fr, to = cfg()['asset_direction'][asset]
        for o, d_, fl in [(fr, to, f), (to, fr, -f)]:
            d = P[d_] - P[o]; fp = fl.clip(lower=0); prod = fp * d.clip(lower=0)
            top = prod.nlargest(max(1, int(len(prod) * 0.01)))
            gate = d > 0
            stress = (P[d_] > K)
            rows.append(dict(direction=f'{o[:-1]} to {d_[:-1]}', share_of_product_top1pct=float(top.sum() / prod.sum()) if prod.sum() else np.nan,
                             spearman_given_gate=float(fp[gate].corr(d[gate], method='spearman')),
                             mean_flow_when_dest_above_300=float(fp[stress].mean()) if stress.any() else np.nan,
                             mean_flow_otherwise=float(fp[~stress].mean()),
                             dest_above_300_intervals=int(stress.sum())))
    return pd.DataFrame(rows)


def run() -> dict:
    log('evidence', 'started')
    P = panel.prices()
    fl = panel.flags()
    ics = panel.ic()
    b = cfg()['bootstrap']
    info = {}
    au = audit(P, fl)
    (ROOT / cfg()['report_root'] / 'evidence').mkdir(parents=True, exist_ok=True)
    (ROOT / cfg()['report_root'] / 'evidence' / 'data_audit.json').write_text(json.dumps(au, indent=2))
    info['audit'] = {k: au[k] for k in ['intervals', 'complete_quarters', 'not_firm_in_complete_quarters', 'apcflag_bits', 'suspension_rows']}
    lc, fits = loss_congestion(P, ics)
    write_csv(lc, 'loss_congestion_quarterly.csv'); write_csv(fits, 'loss_curve_fits.csv')
    write_csv(mlf_scatter_sample(P, ics), 'mlf_flow_sample.csv')
    boots = pd.concat([bootstrap_quarters(P, b['replicates'], bd, b['seed']) for bd in b['block_days']], ignore_index=True)
    write_csv(boots, 'bootstrap_quarterly.csv')
    write_csv(leave_one_day_out(P), 'leave_one_day_out.csv')
    write_csv(extremogram(P), 'extremogram.csv')
    mpcn, mpcinfo = mpc_normalised(P, fl)
    write_csv(mpcn, 'mpc_normalised.csv')
    (ROOT / cfg()['report_root'] / 'evidence' / 'mpc_schedule.json').write_text(json.dumps(mpcinfo, indent=2))
    res = None
    rp = data('settlement', 'directional_5min.parquet')
    if rp.exists():
        res = pd.read_parquet(rp)
    write_csv(diurnal(P, res, ics), 'diurnal_profile.csv')
    write_csv(tail_dependence(P, ics), 'tail_dependence.csv')
    info['mpc'] = {k: mpcinfo[k] for k in ['target_mpc', 'intervals_at_cap']}
    log('evidence', 'completed', **info)
    return info
