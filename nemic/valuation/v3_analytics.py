"""Tier A valuation analytics and bug fixes for interregional valuation research v3.

Reads the frozen five-minute price, interconnector, settlement, and auction archives produced by
the v2 campaign (`data/valuation_v2/` and `reports/interregional_valuation_research_v2/evidence/`)
and writes self-contained compact evidence tables into `reports/interregional_valuation_research_v3/evidence/`.

Tier A upgrades implemented here:
  A1. SRA dollar-payoff decomposition ($/unit): state attribution + fixed-flow clipped counterfactual.
  A2. Auction regime sensitivity (ex-2022 crisis & sub-periods), T1->T12 tranche drift, and
      auction-to-cash credit-support carry drag.
  A3. Three-way loop haircut waterfall, post-loop hedge effectiveness, and parametric EnergyConnect
      (0 / 150 / 800 MW) transfer sensitivity.
  A4. Quarterly hedge effectiveness, capped-energy vs. $300-cap replication, and two-instrument
      (SRA + destination $300 cap) CVaR frontier.
  A5. Diurnal operating-block residue shares (Solar Midday / Evening Ramp / Overnight) and
      negative-price loss-sign inversion diagnostics.
  A6. Disaggregated walk-forward scoring (by direction & horizon), explicit date-window disclosure,
      and three causal ex-ante baselines (debiased clearing price, MPC-rescaled trailing 4q,
      pre-auction outage-adjusted trailing 4q).
  A7. Live catalysts: 2027 Q2 QNI unit-count dilution check, caveated pro-forma regulated Basslink
      residue backcast, and bid-stack order-size slippage (25 / 50 / 100 units).
  A8. MPC x rolling 7-day Cumulative Price Threshold (CPT) interaction under FY2027 settings.
  A9. QNI southbound 42% metered reconciliation diagnostic and strictly ex-ante Bachelier option
      benchmark (fixing the v2 in-sample test-quarter flow-regime peek) + Vega/frequency Greeks.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

from . import loop, market, panel, settlement
from .config import ROOT, cfg as cfg_v2, complete_quarter_intervals, data, quarter_of
from .evidence import CANON, MAIN_ASSET, complete_mask, mpc_schedule
from .market import PAIR_OF, cluster_bootstrap

V3_CFG_PATH = ROOT / 'configs/valuation/interregional_valuation_v3.json'
MAIN6 = ['VICNSW', 'NSWVIC', 'QLDNSW', 'NSWQLD', 'VICSA', 'SAVIC']
LOOP6 = ['VICNSW', 'NSWVIC', 'VICSA', 'SAVIC', 'NSWSA', 'SANSW']
K = 300.0


def cfg_v3() -> dict:
    return json.loads(V3_CFG_PATH.read_text(encoding='utf-8'))


def v2_ev(name: str) -> Path:
    return ROOT / cfg_v3()['v2_report_root'] / 'evidence' / name


def v3_ev(name: str) -> Path:
    p = ROOT / cfg_v3()['report_root'] / 'evidence' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def write_v3_csv(df: pd.DataFrame, name: str) -> Path:
    p = v3_ev(name)
    df.to_csv(p, index=False, lineterminator='\n', float_format='%.10g')
    return p


def seed_v2_evidence() -> int:
    """Copy frozen v2 compact evidence files into v3 evidence/ so v3 is self-contained."""
    src_dir = ROOT / cfg_v3()['v2_report_root'] / 'evidence'
    dst_dir = ROOT / cfg_v3()['report_root'] / 'evidence'
    dst_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    for f in sorted(src_dir.iterdir()):
        if f.is_file() and f.name != 'headline_numbers.json':
            shutil.copy2(f, dst_dir / f.name)
            copied += 1
    return copied


def _unit_prop_map(units: pd.DataFrame, quarters: list[str], direction: str) -> dict[str, float]:
    fb = cfg_v2()['fallback_max_units']
    ind = cfg_v3()['indicative_loop_units']
    out = {}
    for q in quarters:
        u = units[(units.quarter == q) & (units.direction == direction)]
        if len(u):
            out[q] = float(u.PROPORTION.iloc[0]) / 100.0
        elif direction in fb:
            out[q] = 1.0 / float(fb[direction])
        elif direction in ind:
            out[q] = 1.0 / float(ind[direction])
        else:
            out[q] = np.nan
    return out


# ------------------------------------------------------------------ A1. SRA dollar-payoff decomposition
def sra_payoff_decomposition(P: pd.DataFrame, ics: dict, S: pd.DataFrame, shares: dict, units: pd.DataFrame) -> pd.DataFrame:
    """Decompose settled and metered SRA dollar payoffs ($/unit) into loss, energy, and scarcity."""
    q = quarter_of(P.index)
    q_str = q.astype(str)
    comp = complete_mask(P.index)
    quarters = sorted(set(q_str[comp.values]))
    P_clip = P.clip(upper=K)
    # Clipped-price metered residue (fixed-flow counterfactual)
    S_met_actual = settlement.directional_series(P, ics, shares, 'METEREDMWFLOW')
    S_met_clip = settlement.directional_series(P_clip, ics, shares, 'METEREDMWFLOW')

    rows = []
    for pr in cfg_v2()['pairs']:
        if pr['pair'] == 'TAS-VIC':
            continue
        a, b = pr['a'], pr['b']
        asset = MAIN_ASSET[pr['pair']]
        g = ics[asset].reindex(P.index)
        fr, to = cfg_v2()['asset_direction'][asset]
        coupled = (P[to] - P[fr] * g.MARGINALLOSS).abs() <= np.maximum(0.01, 1e-4 * P[fr].abs())

        for code, orig, dst in [(pr['sra_ab'], a, b), (pr['sra_ba'], b, a)]:
            pmap = _unit_prop_map(units, quarters, code)
            pos = S[f'{code}_pos'].reindex(P.index).fillna(0.0)
            met_act = S_met_actual[f'{code}_pos'].reindex(P.index).fillna(0.0)
            met_clp = S_met_clip[f'{code}_pos'].reindex(P.index).fillna(0.0)

            both_le = (P[orig] <= K) & (P[dst] <= K)
            dst_only = (P[dst] > K) & (P[orig] <= K)
            orig_only = (P[orig] > K) & (P[dst] <= K)
            both_gt = (P[dst] > K) & (P[orig] > K)

            df = pd.DataFrame({
                'q': q_str,
                'comp': comp.values,
                'settled': pos.values,
                'coupled_loss': pos.where(coupled, 0.0).values,
                'energy_cong': pos.where(~coupled & both_le, 0.0).values,
                'scarcity_dst': pos.where(~coupled & dst_only, 0.0).values,
                'scarcity_orig': pos.where(~coupled & orig_only, 0.0).values,
                'scarcity_both': pos.where(~coupled & both_gt, 0.0).values,
                'met_actual': met_act.values,
                'met_clipped': met_clp.values,
            })
            df = df[df.comp]
            agg = df.groupby('q').sum()
            for qq, r in agg.iterrows():
                prop = pmap[qq]
                tot_u = r.settled * prop
                rows.append(dict(
                    direction=code,
                    quarter=qq,
                    settled_per_unit=tot_u,
                    state_coupled_loss_per_unit=r.coupled_loss * prop,
                    state_energy_congestion_per_unit=r.energy_cong * prop,
                    state_scarcity_dest_only_per_unit=r.scarcity_dst * prop,
                    state_scarcity_orig_only_per_unit=r.scarcity_orig * prop,
                    state_scarcity_both_per_unit=r.scarcity_both * prop,
                    state_scarcity_total_per_unit=(r.scarcity_dst + r.scarcity_orig + r.scarcity_both) * prop,
                    metered_actual_per_unit=r.met_actual * prop,
                    fixed_flow_clipped_energy_per_unit=r.met_clipped * prop,
                    fixed_flow_scarcity_increment_per_unit=(r.met_actual - r.met_clipped) * prop,
                ))
    return pd.DataFrame(rows)


def _fast_cluster_bootstrap_ratio(df: pd.DataFrame, reps: int, seed: int) -> tuple[float, float]:
    """Exact vectorised quarter-cluster bootstrap of value-weighted realised/price ratio."""
    qagg = df.groupby('delivery_quarter', sort=False).apply(
        lambda x: pd.Series({
            'num': float((x.per_unit * x.UNITSSOLD).sum()),
            'den': float((x.CLEARINGPRICE * x.UNITSSOLD).sum()),
        }),
        include_groups=False,
    )
    if len(qagg) < 3:
        return np.nan, np.nan
    num = qagg['num'].to_numpy(dtype=float)
    den = qagg['den'].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(num), size=(reps, len(num)))
    ratios = num[idx].sum(axis=1) / den[idx].sum(axis=1)
    lo, hi = np.nanpercentile(ratios, [2.5, 97.5])
    return float(lo), float(hi)


# ------------------------------------------------------------------ A2. Ex-2022 split, T1->T12 drift, carry
def auction_deep_analysis() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    J = pd.read_csv(v2_ev('auction_vs_realised.csv'), parse_dates=['auction_date', 'payment_date'])
    ret = pd.read_csv(v2_ev('auction_returns.csv'))
    b = cfg_v3()['bootstrap']
    vw = lambda d: (d.per_unit * d.UNITSSOLD).sum() / (d.CLEARINGPRICE * d.UNITSSOLD).sum()

    regimes = {
        'full_19q': J,
        'ex_2022_crisis': J[~J.delivery_quarter.isin(['2022Q2', '2022Q3'])],
        'early_2021q4_2023q4': J[J.delivery_quarter <= '2023Q4'],
        'recent_2024q1_2026q2': J[J.delivery_quarter >= '2024Q1'],
    }
    reg_rows = []
    for rname, df in regimes.items():
        slices = [(('all', 'all'), df)] + [((d, 'all'), g) for d, g in df.groupby('direction')] + \
                 [(('all', h), g) for h, g in df.groupby('horizon')]
        for (d, h), g in slices:
            if not len(g):
                continue
            lo, hi = _fast_cluster_bootstrap_ratio(g, b['replicates'], b['seed'])
            reg_rows.append(dict(
                regime=rname, direction=d, horizon=str(h),
                tranches=len(g), delivery_quarters=int(g.delivery_quarter.nunique()),
                value_weighted_ratio=float(vw(g)), ci_low=float(lo), ci_high=float(hi),
                median_ratio=float(g.ratio.median()),
                share_above_price=float((g.ratio > 1).mean()),
                mean_premium_per_unit=float(g.premium.mean()),
            ))

    # T1 -> T12 tranche convergence / drift
    t12 = J[J.tranche == 12][['delivery_quarter', 'direction', 'CLEARINGPRICE']].rename(columns={'CLEARINGPRICE': 't12_price'})
    Jt = J.merge(t12, on=['delivery_quarter', 'direction'], how='left')
    Jt['price_vs_t12'] = Jt.CLEARINGPRICE / Jt.t12_price
    Jt['price_vs_realised'] = Jt.CLEARINGPRICE / Jt.per_unit
    drift_rows = []
    for scope, gdf in [('all', Jt)] + [(d, g) for d, g in Jt.groupby('direction')]:
        for tr, g in gdf.groupby('tranche'):
            drift_rows.append(dict(
                direction=scope, tranche=int(tr), quarters_ahead=int(13 - tr),
                n=len(g), mean_price=float(g.CLEARINGPRICE.mean()),
                mean_realised=float(g.per_unit.mean()),
                value_weighted_ratio=float(vw(g)),
                median_price_vs_realised=float(g.price_vs_realised.median()),
                median_price_vs_t12=float(g.price_vs_t12.median()),
            ))

    # Capital lockup / credit-support carry vs 49-day payment-to-cash lag
    M = J.merge(
        ret[['delivery_quarter', 'direction', 'tranche', 'holding_period_return', 'mean_days_to_cash']],
        on=['delivery_quarter', 'direction', 'tranche'], how='left'
    )
    M['days_auction_to_payment'] = (M.payment_date - M.auction_date).dt.days.clip(lower=0)
    M['days_auction_to_cash'] = M.days_auction_to_payment + M.mean_days_to_cash
    carry_rows = []
    order = ['1-2 quarters', '3-4 quarters', '5-8 quarters', '9-12 quarters']
    for h in ['all'] + order:
        g = M if h == 'all' else M[M.horizon == h]
        d_pay = float(g.mean_days_to_cash.median())
        d_auc = float(g.days_auction_to_cash.median())
        vwr = float(vw(g))
        vw_hpr = vwr - 1.0
        row = dict(
            horizon=h, tranches=len(g),
            median_days_payment_to_cash=d_pay,
            median_days_auction_to_payment=float(g.days_auction_to_payment.median()),
            median_days_auction_to_cash=d_auc,
            value_weighted_ratio=vwr,
            value_weighted_hpr=vw_hpr,
            median_hpr=float(g.holding_period_return.median()),
        )
        for rate in cfg_v3()['carry_rates_pa']:
            rtag = int(round(rate * 100))
            drag = rate * (d_auc / 365.0)
            row[f'carry_drag_{rtag}pct'] = drag
            row[f'net_excess_hpr_{rtag}pct'] = vw_hpr - drag
        carry_rows.append(row)

    return pd.DataFrame(reg_rows), pd.DataFrame(drift_rows), pd.DataFrame(carry_rows)


# ------------------------------------------------------------------ A3. Loop 3-way waterfall, loop hedging, parametric PEC
def loop_deep_analysis(P: pd.DataFrame, units: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    arms = pd.read_parquet(data('settlement', 'settled_arms_5min.parquet'))
    prices = P[['NSW1', 'VIC1', 'SA1']]
    flows = pd.DataFrame({'VN': arms['VIC-NSW_flow'], 'VS': arms['VIC-SA_flow'], 'NS': 0.0}, index=P.index)
    alloc = pd.DataFrame({'VN': arms['VIC-NSW_alloc'], 'VS': arms['VIC-SA_alloc'], 'NS': 0.0}, index=P.index)
    res = loop.net_trade(prices, flows, alloc)

    q = quarter_of(P.index)
    q_str = q.astype(str)
    comp = complete_mask(P.index)
    quarters = sorted(set(q_str[comp.values]))

    # Reconstruct exact provisional per directional code for 3-way attribution
    sq_total = res[['sq_VICNSW', 'sq_NSWVIC', 'sq_VICSA', 'sq_SAVIC']].sum(axis=1)
    nl_pos = res.net_loop.clip(lower=0.0)
    # Scaling factor from status-quo positive sum to available net-loop pool (captures negative-loop zeroing & counter-price drag)
    scale = np.where(sq_total > 1e-9, nl_pos / sq_total, 0.0)
    scale = np.minimum(scale, 1.0)  # net-loop pooling never exceeds sum of positive arms unless negative arm absent

    # Map provisional arm values into directional codes by sign of net_trade_<arm>
    prov_dir = pd.DataFrame(0.0, index=P.index, columns=LOOP6)
    arm_map = [('VN', 'VICNSW', 'NSWVIC'), ('VS', 'VICSA', 'SAVIC'), ('NS', 'NSWSA', 'SANSW')]
    for arm, fwd, rev in arm_map:
        nt = res[f'net_trade_{arm}'].values
        pr = np.where(res.net_loop.values > 0, res[f'provisional_{arm}'].values, 0.0)
        prov_dir[fwd] = np.where(nt > 0, pr, 0.0)
        prov_dir[rev] = np.where(nt < 0, pr, 0.0)

    wf_rows = []
    for qq in quarters:
        m = (q_str == qq)
        for code in LOOP6:
            sq = float(res.loc[m, f'sq_{code}'].sum()) if f'sq_{code}' in res else 0.0
            after_neg = float((res.loc[m, f'sq_{code}'].values * scale[m]).sum()) if f'sq_{code}' in res else 0.0
            prov = float(prov_dir.loc[m, code].sum())
            fin = float(res.loc[m, f'loop_{code}'].sum())
            prop = _unit_prop_map(units, [qq], code)[qq]
            wf_rows.append(dict(
                quarter=qq, direction=code,
                status_quo=sq,
                neg_netting_delta=after_neg - sq,
                passthrough_reallocation_delta=prov - after_neg,
                secondary_netting_delta=fin - prov,
                loop_rule=fin,
                total_delta=fin - sq,
                pct_change=(fin / sq - 1.0) if sq > 0 else np.nan,
                proportion=prop,
                status_quo_per_unit=sq * prop,
                loop_per_unit=fin * prop,
            ))

    # Post-loop hedge effectiveness (weekly & quarterly)
    wk = (P.index - pd.Timedelta('1ns')).to_period('W')
    pair_ext = {**PAIR_OF, 'NSWSA': ('NSW1', 'SA1'), 'SANSW': ('SA1', 'NSW1')}
    stress_n = cfg_v3()['stress']['top_weeks']
    lh_rows = []
    for code in LOOP6:
        o, t = pair_ext[code]
        pmap = _unit_prop_map(units, quarters, code)
        prop_s = pd.Series(q_str, index=P.index).map(pmap).fillna(0.0).values
        u_loop = res[f'loop_{code}'].values * prop_s
        u_sq = (res[f'sq_{code}'].values if f'sq_{code}' in res else np.zeros(len(P))) * prop_s
        s = (P[t] - P[o]).values / 12.0
        for basis, u_vec in [('loop_rule', u_loop), ('status_quo', u_sq)]:
            if u_vec.sum() <= 0:
                continue
            W = pd.DataFrame({'w': wk, 'u': u_vec, 's': s, 'n': 1}).groupby('w').agg(u=('u', 'sum'), s=('s', 'sum'), n=('n', 'sum'))
            W = W[W.n == 2016]
            top = W.s.nlargest(stress_n).index
            n_mv = float(np.cov(W.u, W.s)[0, 1] / W.u.var()) if W.u.var() > 0 else np.nan
            r2_w = float(np.corrcoef(W.u, W.s)[0, 1] ** 2) if W.u.std() > 0 else np.nan
            Q = pd.DataFrame({'q': q_str, 'u': u_vec, 's': s, 'c': comp.values})
            Q = Q[Q.c].groupby('q').agg(u=('u', 'sum'), s=('s', 'sum'))
            r2_q = float(np.corrcoef(Q.u, Q.s)[0, 1] ** 2) if Q.u.std() > 0 else np.nan
            lh_rows.append(dict(
                direction=code, basis=basis,
                unit_basis='dated_registry' if code not in ('NSWSA', 'SANSW') else 'indicative_800_units',
                weekly_r2=r2_w,
                quarterly_r2=r2_q,
                units_min_variance_per_mw=n_mv,
                mw_per_unit=1.0 / n_mv if np.isfinite(n_mv) and n_mv != 0 else np.nan,
                stress_mw_equivalent=float(W.u[top].sum() / W.s[top].sum()),
                mean_quarterly_per_unit=float(Q.u.mean()),
            ))

    # Parametric EnergyConnect physical transfer sensitivity (0 / 150 / 800 MW + spread compression)
    pec_rows = []
    p_diff_ns = (prices.SA1 - prices.NSW1).values  # positive => NSW -> SA
    loss_k = 0.00008  # stylized ~6.4% loss at 800 MW (L = k F^2)
    for cap_mw in cfg_v3()['pec_parametric_mw']:
        for comp_f in cfg_v3()['pec_compression_factors']:
            if cap_mw == 0 and comp_f > 0:
                continue
            # Stylized price compression on SA-NSW spread under physical PEC transfer
            p_sim = prices.copy()
            if comp_f > 0:
                mid = 0.5 * (prices.NSW1 + prices.SA1)
                p_sim['NSW1'] = mid + (1.0 - comp_f) * (prices.NSW1 - mid)
                p_sim['SA1'] = mid + (1.0 - comp_f) * (prices.SA1 - mid)
            spread_ns = (p_sim.SA1 - p_sim.NSW1).values
            f_ns = np.where(np.abs(spread_ns) > 5.0, np.sign(spread_ns) * float(cap_mw), 0.0)
            l_ns = loss_k * (f_ns ** 2)
            # Loss-adjusted interval residue on NS arm (s = 0.5)
            r_ns = (p_sim.SA1.values * (f_ns - 0.5 * l_ns) - p_sim.NSW1.values * (f_ns + 0.5 * l_ns)) / 12.0
            fl_sim = flows.assign(NS=f_ns)
            al_sim = alloc.assign(NS=r_ns)
            # When spread compresses, scale VN/VS allocations proportionally to compressed spreads
            if comp_f > 0:
                sp_vn_old = (prices.NSW1 - prices.VIC1).values
                sp_vn_new = (p_sim.NSW1 - p_sim.VIC1).values
                sp_vs_old = (prices.SA1 - prices.VIC1).values
                sp_vs_new = (p_sim.SA1 - p_sim.VIC1).values
                with np.errstate(divide='ignore', invalid='ignore'):
                    al_sim['VN'] = np.where(np.abs(sp_vn_old) > 1.0, alloc.VN.values * (sp_vn_new / sp_vn_old), alloc.VN.values)
                    al_sim['VS'] = np.where(np.abs(sp_vs_old) > 1.0, alloc.VS.values * (sp_vs_new / sp_vs_old), alloc.VS.values)
            r_out = loop.net_trade(p_sim, fl_sim, al_sim)
            r_comp = r_out[comp.values]
            for code in LOOP6:
                pec_rows.append(dict(
                    pec_mw=cap_mw, spread_compression_pct=int(round(comp_f * 100)),
                    direction=code,
                    total_payout_m=float(r_comp[f'loop_{code}'].sum() / 1e6),
                    status_quo_m=float(r_comp[f'sq_{code}'].sum() / 1e6) if f'sq_{code}' in r_comp else 0.0,
                ))

    return pd.DataFrame(wf_rows), pd.DataFrame(lh_rows), pd.DataFrame(pec_rows)


# ------------------------------------------------------------------ A4. Quarterly & component hedging + 2-instrument frontier
def hedge_deep_analysis(P: pd.DataFrame, S: pd.DataFrame, units: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    A = pd.read_csv(v2_ev('auction_panel.csv'))
    q = quarter_of(P.index)
    q_str = q.astype(str)
    comp = complete_mask(P.index)
    quarters = sorted(set(q_str[comp.values]))
    wk = (P.index - pd.Timedelta('1ns')).to_period('W')
    stress_n = cfg_v3()['stress']['top_weeks']
    alpha = cfg_v3()['stress']['cvar_alpha']

    avg_price = A[A.UNITSSOLD > 0].groupby(['delivery_quarter', 'direction']).apply(
        lambda d: (d.CLEARINGPRICE * d.UNITSSOLD).sum() / d.UNITSSOLD.sum(), include_groups=False
    )

    comp_rows = []
    two_rows = []
    for d in MAIN6:
        o, t = PAIR_OF[d]
        pmap = _unit_prop_map(units, quarters, d)
        prop_s = pd.Series(q_str, index=P.index).map(pmap).fillna(0.0).values
        u = S[f'{d}_pos'].reindex(P.index).fillna(0.0).values * prop_s
        s_tot = (P[t] - P[o]).values / 12.0
        s_eng = (P[t].clip(upper=K) - P[o].clip(upper=K)).values / 12.0
        s_cap = ((P[t] - K).clip(lower=0.0) - (P[o] - K).clip(lower=0.0)).values / 12.0
        cap_dst = (P[t] - K).clip(lower=0.0).values / 12.0

        df = pd.DataFrame({'w': wk, 'q': q_str, 'c': comp.values, 'u': u, 'tot': s_tot, 'eng': s_eng, 'cap': s_cap, 'cap_dst': cap_dst, 'n': 1})
        W = df.groupby('w').agg(u=('u', 'sum'), tot=('tot', 'sum'), eng=('eng', 'sum'), cap=('cap', 'sum'),
                                cap_dst=('cap_dst', 'sum'), q=('q', 'first'), n=('n', 'sum'))
        W = W[W.n == 2016]
        Q = df[df.c].groupby('q').agg(u=('u', 'sum'), tot=('tot', 'sum'), eng=('eng', 'sum'), cap=('cap', 'sum'))

        for target_name, col in [('total_spread', 'tot'), ('capped_energy_spread', 'eng'), ('scarcity_cap_spread', 'cap')]:
            r2_w = float(np.corrcoef(W.u, W[col])[0, 1] ** 2) if W[col].std() > 0 else np.nan
            r2_q = float(np.corrcoef(Q.u, Q[col])[0, 1] ** 2) if Q[col].std() > 0 else np.nan
            nmv_w = float(np.cov(W.u, W[col])[0, 1] / W.u.var()) if W.u.var() > 0 else np.nan
            nmv_q = float(np.cov(Q.u, Q[col])[0, 1] / Q.u.var()) if Q.u.var() > 0 else np.nan
            top = W[col].nlargest(stress_n).index
            comp_rows.append(dict(
                direction=d, target=target_name,
                weekly_r2=r2_w, quarterly_r2=r2_q,
                weekly_n_mv=nmv_w, quarterly_n_mv=nmv_q,
                weekly_mw_per_unit=1.0 / nmv_w if np.isfinite(nmv_w) and nmv_w != 0 else np.nan,
                stress_ratio_top10_weeks=float(W.u[top].sum() / W[col][top].sum()) if abs(W[col][top].sum()) > 1 else np.nan,
            ))

        # Two-instrument CVaR frontier (SRA units + Destination $300 Cap) for 3 main directions
        if d in ('VICNSW', 'QLDNSW', 'VICSA'):
            sra_cost_w = W.q.map(lambda p: avg_price.get((str(p), d), np.nan)) / 13.0
            sra_cost_w = sra_cost_w.fillna(sra_cost_w.mean())
            # Illustrative cap price = empirical mean destination cap payout x 1.15 risk loading
            cap_fair_w = float(W.cap_dst.mean())
            cap_price_w = cap_fair_w * 1.15
            n_mv = float(np.cov(W.u, W.tot)[0, 1] / W.u.var())
            for m_cap in [0.0, 0.25, 0.5, 0.75, 1.0]:
                for n_sra in np.linspace(0.0, max(2.5 * n_mv, 1.0), 21):
                    pnl = -W.tot + n_sra * (W.u - sra_cost_w) + m_cap * (W.cap_dst - cap_price_w)
                    loss = -pnl
                    var = np.quantile(loss, alpha)
                    cvar = float(loss[loss >= var].mean())
                    two_rows.append(dict(
                        direction=d, cap_mw=m_cap, sra_units=float(n_sra),
                        cap_loading_assumption=1.15,
                        mean_weekly_pnl=float(pnl.mean()),
                        cvar95_weekly_loss=cvar,
                        weekly_sd=float(pnl.std()),
                    ))

    return pd.DataFrame(comp_rows), pd.DataFrame(two_rows)


# ------------------------------------------------------------------ A5. Diurnal operating blocks & negative-price loss inversion
def diurnal_and_negative_analysis(P: pd.DataFrame, ics: dict, S: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    t = P.index - pd.Timedelta('1ns')
    hour = t.hour
    block = np.where((hour >= 9) & (hour <= 15), 'Solar Midday (09:00-15:00)',
                     np.where((hour >= 16) & (hour <= 21), 'Evening Ramp (16:00-21:00)',
                              'Overnight & Shoulder (22:00-08:00)'))
    season = pd.Series(t.month, index=P.index).map({
        12: 'Summer', 1: 'Summer', 2: 'Summer', 3: 'Autumn', 4: 'Autumn', 5: 'Autumn',
        6: 'Winter', 7: 'Winter', 8: 'Winter', 9: 'Spring', 10: 'Spring', 11: 'Spring'
    })
    comp = complete_mask(P.index)

    diur_rows = []
    for pr in cfg_v2()['pairs']:
        if pr['pair'] == 'TAS-VIC':
            continue
        a, b = pr['a'], pr['b']
        for code, orig, dst in [(pr['sra_ab'], a, b), (pr['sra_ba'], b, a)]:
            df = pd.DataFrame({
                'season': season.values, 'block': block, 'comp': comp.values,
                'residue': S[f'{code}_pos'].reindex(P.index).fillna(0.0).values,
                'spread': (P[dst] - P[orig]).values,
                'neg_orig': (P[orig] < 0).values.astype(float),
                'dst_gt300': (P[dst] > K).values.astype(float),
            })
            df = df[df.comp]
            tot_res = df.residue.sum()
            for scope, grp_cols in [('all_seasons', ['block']), ('by_season', ['season', 'block'])]:
                g = df.groupby(grp_cols).agg(
                    residue_m=('residue', lambda x: x.sum() / 1e6),
                    mean_spread=('spread', 'mean'),
                    neg_origin_pct=('neg_orig', lambda x: 100 * x.mean()),
                    dest_above300_pct=('dst_gt300', lambda x: 100 * x.mean()),
                    intervals=('residue', 'size'),
                ).reset_index()
                if scope == 'all_seasons':
                    g.insert(0, 'season', 'All seasons')
                g['residue_share_pct'] = np.where(tot_res > 0, 100.0 * (g.residue_m * 1e6) / tot_res, 0.0)
                g.insert(0, 'direction', code)
                diur_rows.append(g)

    # Negative-price loss-sign inversion
    neg_rows = []
    for pr, (a, b, lab) in CANON.items():
        if pr == 'TAS-VIC':
            continue
        asset = MAIN_ASSET[pr]
        g = ics[asset].reindex(P.index)
        fr, to = cfg_v2()['asset_direction'][asset]
        sgn = 1.0 if (fr, to) == (a, b) else -1.0
        p_from = P[fr]
        p_to = P[to]
        loss_term = sgn * (p_from * (g.MARGINALLOSS - 1.0))
        spread = sgn * (p_to - p_from)
        code_ab = next(x['sra_ab'] for x in cfg_v2()['pairs'] if x['pair'] == pr)
        res_ab = S[f'{code_ab}_pos'].reindex(P.index).fillna(0.0)
        m_comp = comp.values
        m_neg = (p_from < 0).values & m_comp
        m_pos = (p_from >= 0).values & m_comp
        m_solar_export = (p_from < 0).values & (p_to > 0).values & m_comp
        neg_rows.append(dict(
            pair=lab,
            from_region=fr,
            neg_from_intervals=int(m_neg.sum()),
            neg_from_share_pct=float(100.0 * m_neg.sum() / m_comp.sum()),
            solar_export_intervals=int(m_solar_export.sum()),
            mean_spread_when_from_neg=float(spread[m_neg].mean()),
            mean_loss_term_when_from_neg=float(loss_term[m_neg].mean()),
            mean_loss_term_when_from_nonneg=float(loss_term[m_pos].mean()),
            loss_inversion_share_pct=float(100.0 * (loss_term[m_neg] < 0).mean()) if m_neg.any() else np.nan,
            residue_share_during_neg_from_pct=float(100.0 * res_ab[m_neg].sum() / res_ab[m_comp].sum()) if res_ab[m_comp].sum() > 0 else 0.0,
        ))
    return pd.concat(diur_rows, ignore_index=True), pd.DataFrame(neg_rows)


# ------------------------------------------------------------------ A6. Disaggregated walk-forward + 3 smarter baselines
def walk_forward_v3() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    A = pd.read_csv(v2_ev('auction_panel.csv'), parse_dates=['auction_date'])
    R = market.realised_per_unit()
    R['end'] = [pd.Period(q, 'Q').end_time for q in R.quarter]
    R['qn'] = [pd.Period(q, 'Q').quarter for q in R.quarter]
    # Historical MPC per quarter (for MPC-rescaled baseline)
    mp = json.loads(v2_ev('mpc_schedule.json').read_text())['schedule']
    mp_dates = sorted((pd.Timestamp(k), v['mpc']) for k, v in mp.items())

    def mpc_for_quarter(q_str: str) -> float:
        ts = pd.Period(q_str, 'Q').start_time + pd.Timedelta(days=45)
        val = mp_dates[0][1]
        for dt, m in mp_dates:
            if dt <= ts:
                val = m
        return float(val)

    R['mpc'] = [mpc_for_quarter(q) for q in R.quarter]
    # Join settled tranches for strictly causal trailing ratio (debiased clearing price)
    J = pd.read_csv(v2_ev('auction_vs_realised.csv'), parse_dates=['auction_date'])
    J['end'] = [pd.Period(q, 'Q').end_time for q in J.delivery_quarter]

    # Outage hours (known before tranche 12) for 2023 Q1+ subset
    op = pd.read_csv(v2_ev('outage_plan_predictive.csv'))
    dir_to_pair = {'VICNSW': 'NSW − VIC', 'NSWVIC': 'NSW − VIC', 'QLDNSW': 'QLD − NSW',
                   'NSWQLD': 'QLD − NSW', 'VICSA': 'SA − VIC', 'SAVIC': 'SA − VIC'}
    op_map = {(r.pair, r.quarter): float(r.planned_set_hours) for _, r in op.iterrows()}

    rows = []
    for _, t in A[(A.UNITSSOLD > 0) & (A.CLEARINGPRICE > 0)].iterrows():
        actual = R[(R.quarter == t.delivery_quarter) & (R.direction == t.direction)]
        if not len(actual):
            continue
        y = float(actual.per_unit.iloc[0])
        cutoff = t.auction_date - pd.Timedelta(days=28)
        hist = R[(R.direction == t.direction) & (R.end < cutoff)].sort_values('end')
        if len(hist) < 4:
            continue
        dq = pd.Period(t.delivery_quarter, 'Q')
        v = hist.per_unit.values
        same = hist[hist.qn == dq.quarter].per_unit.values[-3:]

        # Strictly causal debiased clearing price (trailing vw ratio for same horizon settled before auction)
        j_hist = J[(J.end < cutoff) & (J.horizon == t.horizon)]
        if len(j_hist) < 12:
            j_hist = J[J.end < cutoff]
        if len(j_hist) >= 6:
            trail_ratio = float((j_hist.per_unit * j_hist.UNITSSOLD).sum() / (j_hist.CLEARINGPRICE * j_hist.UNITSSOLD).sum())
            trail_ratio = float(np.clip(trail_ratio, 0.7, 2.0))
        else:
            trail_ratio = 1.0

        # Strictly causal MPC-rescaled trailing 4q (apply 35% scarcity weight scaling)
        dq_mpc = mpc_for_quarter(t.delivery_quarter)
        h4_mpc = float(hist.mpc.values[-4:].mean())
        mpc_scale = 0.65 + 0.35 * (dq_mpc / h4_mpc) if h4_mpc > 0 else 1.0

        # Outage-adjusted trailing 4q (only for tranche 12 on 2023 Q1+ where as-of outage hours exist)
        outage_fc = np.nan
        pair_lab = dir_to_pair.get(t.direction)
        if int(t.tranche) == 12 and pair_lab and (pair_lab, t.delivery_quarter) in op_map:
            h_pairs = [(op_map.get((pair_lab, q0), np.nan), float(val)) for q0, val in zip(hist.quarter, hist.per_unit)]
            h_pairs = [(xh, yh) for xh, yh in h_pairs if np.isfinite(xh)]
            if len(h_pairs) >= 4:
                xs = np.array([p[0] for p in h_pairs])
                ys = np.array([p[1] for p in h_pairs])
                x_now = op_map[(pair_lab, t.delivery_quarter)]
                if xs.std() > 1e-6:
                    # Shrink slope toward zero (ridge shrinkage) to prevent small-sample blowup
                    slope = np.cov(xs, ys)[0, 1] / (xs.var() + xs.var())
                    outage_fc = float(max(0.0, ys.mean() + slope * (x_now - xs.mean())))

        f = {
            'market_clearing_price': float(t.CLEARINGPRICE),
            'debiased_clearing_price': float(t.CLEARINGPRICE * trail_ratio),
            'trailing_4q': float(v[-4:].mean()),
            'mpc_rescaled_trailing_4q': float(v[-4:].mean() * mpc_scale),
            'trailing_8q': float(v[-8:].mean()),
            'trailing_12q': float(v[-12:].mean()),
            'same_season': float(same.mean()) if len(same) else np.nan,
            'last_quarter': float(v[-1]),
            'outage_adjusted_t12': outage_fc,
        }
        for k, fc in f.items():
            rows.append(dict(
                direction=t.direction, delivery_quarter=t.delivery_quarter,
                tranche=int(t.tranche), quarters_ahead=int(t.quarters_ahead),
                horizon=str(t.horizon), auction_date=str(t.auction_date.date()),
                rule=k, forecast=fc, actual=y, history_quarters=len(hist),
            ))

    W = pd.DataFrame(rows)
    W['error'] = W.forecast - W.actual

    def _score(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
        g = df.dropna(subset=['forecast']).groupby(group_cols).agg(
            n=('error', 'size'),
            mean_actual=('actual', 'mean'),
            bias=('error', 'mean'),
            mae=('error', lambda e: e.abs().mean()),
            median_abs_error=('error', lambda e: e.abs().median()),
            first_auction=('auction_date', 'min'),
            last_auction=('auction_date', 'max'),
        ).reset_index()
        g['mae_pct_of_mean'] = 100.0 * g.mae / g.mean_actual
        return g

    overall = _score(W[W.rule != 'outage_adjusted_t12'], ['rule'])
    mkt_mae = float(overall.loc[overall.rule == 'market_clearing_price', 'mae'].iloc[0])
    overall['mae_skill_vs_market'] = 1.0 - overall.mae / mkt_mae

    # Matched subset score for outage_adjusted_t12 vs clearing price on identical rows
    out_keys = W[(W.rule == 'outage_adjusted_t12') & W.forecast.notna()][['direction', 'delivery_quarter', 'tranche']]
    if len(out_keys):
        sub = W.merge(out_keys, on=['direction', 'delivery_quarter', 'tranche'])
        sub = sub[sub.rule.isin(['outage_adjusted_t12', 'market_clearing_price', 'trailing_4q'])]
        sub_sc = _score(sub, ['rule'])
        sub_sc['rule'] = sub_sc.rule.map(lambda r: r if r == 'outage_adjusted_t12' else f'{r}_matched_t12')
        mkt_sub = float(sub_sc.loc[sub_sc.rule == 'market_clearing_price_matched_t12', 'mae'].iloc[0])
        sub_sc['mae_skill_vs_market'] = 1.0 - sub_sc.mae / mkt_sub
        overall = pd.concat([overall, sub_sc], ignore_index=True)

    by_dir = _score(W[W.rule.isin(['market_clearing_price', 'debiased_clearing_price', 'trailing_4q', 'mpc_rescaled_trailing_4q'])], ['direction', 'rule'])
    by_hor = _score(W[W.rule.isin(['market_clearing_price', 'debiased_clearing_price', 'trailing_4q'])], ['horizon', 'rule'])
    return W, overall, by_dir, by_hor


# ------------------------------------------------------------------ A7. QNI dilution, pro-forma Basslink, bid-stack slippage
def live_catalysts_analysis(P: pd.DataFrame, ics: dict, shares: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # 1. QNI 2027 Q2 dilution check
    A = pd.read_csv(v2_ev('auction_panel.csv'), parse_dates=['auction_date'])
    dil_rows = []
    for d, old_u, new_u in [('NSWQLD', 550, 750), ('QLDNSW', 1200, 1300)]:
        g = A[(A.direction == d) & (A.UNITSSOLD > 0) & (A.CLEARINGPRICE > 0)].copy()
        g['qn'] = g.delivery_quarter.str[-2:]
        pre = g[(g.delivery_quarter >= '2026Q2') & (g.delivery_quarter <= '2027Q1')]
        post = g[g.delivery_quarter >= '2027Q2']
        # Same-quarter matched (Q2 2026 vs Q2 2027/2028)
        pre_q2 = g[g.delivery_quarter == '2026Q2']
        post_q2 = g[g.delivery_quarter.isin(['2027Q2', '2028Q2'])]
        dil_rows.append(dict(
            direction=d,
            effective_quarter='2027Q2',
            previous_max_units=old_u,
            new_max_units=new_u,
            unit_increase_pct=100.0 * (new_u / old_u - 1.0),
            mechanical_per_unit_dilution_pct=100.0 * (old_u / new_u - 1.0),
            pre_tranches=len(pre),
            post_tranches=len(post),
            mean_price_pre_2026q2_2027q1=float(pre.CLEARINGPRICE.mean()) if len(pre) else np.nan,
            mean_price_post_2027q2_plus=float(post.CLEARINGPRICE.mean()) if len(post) else np.nan,
            mean_price_2026q2_only=float(pre_q2.CLEARINGPRICE.mean()) if len(pre_q2) else np.nan,
            mean_price_2027_2028q2=float(post_q2.CLEARINGPRICE.mean()) if len(post_q2) else np.nan,
        ))

    # 2. Pro-forma regulated Basslink residue backcast (explicitly caveated MNSP dispatch)
    q = quarter_of(P.index)
    q_str = q.astype(str)
    comp = complete_mask(P.index)
    g_tv = ics['T-V-MNSP1'].reindex(P.index)
    s_tv = shares.get('T-V-MNSP1', cfg_v2()['loss_share_default'])
    if isinstance(s_tv, pd.Series):
        s_tv = s_tv.fillna(cfg_v2()['loss_share_default'])
    r_tv_disp = settlement.asset_residue(P, g_tv, 'TAS1', 'VIC1', s_tv, 'MWFLOW').fillna(0.0)
    r_tv_met = settlement.asset_residue(P, g_tv, 'TAS1', 'VIC1', s_tv, 'METEREDMWFLOW').fillna(0.0)
    f_disp = g_tv.MWFLOW.fillna(0.0)
    f_met = g_tv.METEREDMWFLOW.fillna(0.0)

    bl_rows = []
    for qq in sorted(set(q_str[comp.values])):
        m = (q_str == qq)
        for code, mask_d, mask_m in [
            ('TASVIC', f_disp > 0, f_met > 0),
            ('VICTAS', f_disp < 0, f_met < 0),
        ]:
            pos_d = float(r_tv_disp[m & mask_d].clip(lower=0.0).sum())
            pos_m = float(r_tv_met[m & mask_m].clip(lower=0.0).sum())
            neg_d = float(r_tv_disp[m & mask_d].clip(upper=0.0).sum())
            bl_rows.append(dict(
                quarter=qq, direction=code, basis='pro_forma_mnsp_dispatch',
                max_units=500,
                proforma_pos_residue_dispatch=pos_d,
                proforma_pos_residue_metered=pos_m,
                proforma_neg_residue_dispatch=neg_d,
                proforma_per_unit_dispatch=pos_d / 500.0,
                proforma_per_unit_metered=pos_m / 500.0,
            ))

    # 3. Bid-stack order-size slippage on latest auction Tranche 12 contracts
    Cv = pd.read_csv(v2_ev('auction_bid_curve_latest.csv'))
    latest_aid = Cv.AUCTIONID.max()
    A_lat = A[A.AUCTIONID == latest_aid]
    slip_rows = []
    for (cid, d), g in Cv.groupby(['CONTRACTID', 'direction']):
        if d not in MAIN6 or not str(cid).endswith('T12'):
            continue
        meta = A_lat[(A_lat.CONTRACTID == cid) & (A_lat.direction == d)]
        if not len(meta):
            continue
        offered = float(meta.UNITSOFFERED.iloc[0])
        sold = float(meta.UNITSSOLD.iloc[0])
        clr = float(meta.CLEARINGPRICE.iloc[0])
        g = g.sort_values('BIDPRICE', ascending=False).copy()
        g['cum'] = g.UNITS.cumsum()
        # Marginal bid price needed to displace competing buyers for an extra Q units
        # (equivalently the price at cumulative competing demand = offered - Q)
        for q_ord in cfg_v3()['slippage_order_sizes']:
            rem = max(offered - q_ord, 1.0)
            hit = g[g.cum >= rem]
            new_clr = float(hit.BIDPRICE.iloc[0]) if len(hit) else float(g.BIDPRICE.max())
            slip_rows.append(dict(
                auction_id=str(latest_aid), contract_id=cid, direction=d,
                units_offered=offered, units_sold=sold,
                clearing_price=clr, order_units=q_ord,
                order_share_of_tranche_pct=100.0 * q_ord / offered if offered > 0 else np.nan,
                implied_new_clearing=max(new_clr, clr),
                price_impact_dollars=max(new_clr - clr, 0.0),
                price_impact_pct=100.0 * max(new_clr - clr, 0.0) / clr if clr > 0 else np.nan,
            ))

    return pd.DataFrame(dil_rows), pd.DataFrame(bl_rows), pd.DataFrame(slip_rows)


# ------------------------------------------------------------------ A8. MPC x rolling 7-day CPT interaction
def mpc_cpt_analysis(P: pd.DataFrame) -> pd.DataFrame:
    mpc, cpt, table = mpc_schedule(P.index)
    fy27_entries = [v for k, v in sorted(table.items()) if k >= '2026-07-01']
    target_mpc = float(fy27_entries[0]['mpc']) if fy27_entries else float(mpc.iloc[-1])
    target_cpt = float(fy27_entries[0]['cpt']) if fy27_entries and fy27_entries[0]['cpt'] else float(cpt.dropna().iloc[-1])
    apc_cap = float(cfg_v3()['apc_cap_fy27'])
    win = int(cfg_v3()['cpt_intervals'])

    at_cap = P.ge(mpc.values[:, None] * 0.999)
    P_lin = P.where(~at_cap, P.mul(target_mpc / mpc, axis=0))

    # Apply true sequential rolling 7-day CPT cap per region (fast skip when unconstrained sum <= CPT)
    P_cpt = P_lin.copy()
    cpt_breach_counts = {}
    for reg in P_lin.columns:
        vals = P_lin[reg].to_numpy(dtype=float, copy=True)
        # Fast exact check: if unconstrained rolling 7-day sum never exceeds CPT, zero breaches occur
        csum = np.cumsum(np.insert(vals, 0, 0.0))
        roll = csum[1:] - np.concatenate([np.zeros(win - 1), csum[:-win]])
        if not np.any(roll > target_cpt):
            cpt_breach_counts[reg] = 0
            continue
        out = vals.copy()
        buf = np.zeros(win, dtype=float)
        running = 0.0
        breaches = 0
        # Only run sequential loop from (first_breach - win) through last active window
        first_b = max(0, int(np.argmax(roll > target_cpt)) - win)
        if first_b > 0:
            # seed rolling buffer ending at first_b - 1
            seed_slice = out[max(0, first_b - win):first_b]
            for j, v in enumerate(seed_slice):
                buf[(max(0, first_b - win) + j) % win] = v
            running = float(seed_slice.sum())
        for i in range(first_b, len(vals)):
            idx = i % win
            old = buf[idx]
            cand = vals[i]
            if running - old + cand > target_cpt:
                applied = apc_cap if cand > apc_cap else cand
                breaches += 1
            else:
                applied = cand
            running = running - old + applied
            buf[idx] = applied
            out[i] = applied
        P_cpt[reg] = out
        cpt_breach_counts[reg] = breaches

    q = quarter_of(P.index)
    comp = complete_mask(P.index)
    rows = []
    for pr, (a, b, lab) in CANON.items():
        for basis, M in [('raw', P), ('linear_mpc_only', P_lin), ('mpc_with_cpt_cap', P_cpt)]:
            c = (M[b] - K).clip(lower=0.0) - (M[a] - K).clip(lower=0.0)
            df = pd.DataFrame({'q': q.astype(str), 'comp': comp.values, 'c': c.values, 's': (M[b] - M[a]).values})
            g = df[df.comp].groupby('q').agg(scarcity=('c', 'mean'), spread=('s', 'mean')).reset_index()
            for _, r in g.iterrows():
                rows.append(dict(
                    pair=lab, quarter=r.q, basis=basis,
                    scarcity=float(r.scarcity), spread=float(r.spread),
                    target_mpc=target_mpc, target_cpt=target_cpt, apc_cap=apc_cap,
                    cpt_capped_intervals_dest=cpt_breach_counts.get(b, 0),
                    cpt_capped_intervals_orig=cpt_breach_counts.get(a, 0),
                ))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ A9. QNI south diag + Ex-ante option fix + Greeks
def reconciliation_and_option_fix(P: pd.DataFrame, ics: dict, shares: dict, units: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # 1. QNI southbound (NSW->QLD) reconciliation diagnostic
    st = settlement.settled()
    st = st[st.time.isin(P.index)]
    q = quarter_of(P.index)
    q_str = q.astype(str)
    comp = complete_mask(P.index)
    diag_rows = []
    for asset, fr, to in [('NSW1-QLD1', 'NSW1', 'QLD1'), ('N-Q-MNSP1', 'NSW1', 'QLD1')]:
        g = ics[asset].reindex(P.index)
        s = shares.get(asset, cfg_v2()['loss_share_default'])
        if isinstance(s, pd.Series):
            s = s.fillna(cfg_v2()['loss_share_default'])
        r_met = settlement.asset_residue(P, g, fr, to, s, 'METEREDMWFLOW').fillna(0.0)
        f_met = g.METEREDMWFLOW.fillna(0.0)
        f_disp = g.MWFLOW.fillna(0.0)
        sq = st[(st.INTERCONNECTORID == asset) & (st.REGIONID == 'NSW1')].set_index('time').reindex(P.index)
        sv_pos = sq.SURPLUSVALUE.fillna(0.0).clip(lower=0.0)
        comp_pos = r_met.where(f_met > 0, 0.0).clip(lower=0.0)
        small_flow = (f_met > 0) & (f_met < 50.0)
        sign_flip = (f_met > 0) & (f_disp <= 0)
        df = pd.DataFrame({
            'q': q_str, 'comp': comp.values,
            'computed_pos': comp_pos.values,
            'settled_pos': sv_pos.values,
            'small_flow_pos': comp_pos.where(small_flow, 0.0).values,
            'sign_flip_pos': comp_pos.where(sign_flip, 0.0).values,
            'sign_flip_intervals': sign_flip.astype(int).values,
        })
        for qq, r in df[df.comp].groupby('q').sum().iterrows():
            diag_rows.append(dict(
                asset=asset, quarter=qq,
                computed_pos=float(r.computed_pos),
                settled_pos=float(r.settled_pos),
                diff_dollars=float(r.computed_pos - r.settled_pos),
                bias_pct=float(100.0 * (r.computed_pos / r.settled_pos - 1.0)) if r.settled_pos > 1e4 else np.nan,
                small_flow_share_of_computed_pct=float(100.0 * r.small_flow_pos / r.computed_pos) if r.computed_pos > 0 else 0.0,
                sign_flip_share_of_computed_pct=float(100.0 * r.sign_flip_pos / r.computed_pos) if r.computed_pos > 0 else 0.0,
                sign_flip_intervals=int(r.sign_flip_intervals),
            ))

    # 2. Strictly ex-ante Bachelier regime option benchmark (no test-quarter flow peek!) + Greeks
    t = P.index - pd.Timedelta('1ns')
    season = pd.Series((t.month % 12) // 3, index=P.index)
    block = pd.Series(t.hour // 4, index=P.index)
    R = market.realised_per_unit()
    quarters = sorted(set(q_str[comp.values]))
    main_map = {'VICNSW': 'VIC1-NSW1', 'NSWVIC': 'VIC1-NSW1', 'NSWQLD': 'NSW1-QLD1',
                'QLDNSW': 'NSW1-QLD1', 'VICSA': 'V-SA', 'SAVIC': 'V-SA'}

    def _bcall(mu, sd):
        sd = np.maximum(sd, 1e-9)
        z = mu / sd
        return sd * norm.pdf(z) + mu * norm.cdf(z)

    opt_rows, greek_rows = [], []
    for d, asset in main_map.items():
        o, dst = PAIR_OF[d]
        fr, to = cfg_v2()['asset_direction'][asset]
        F = ics[asset].MWFLOW.reindex(P.index)
        Fd = F if (o, dst) == (fr, to) else -F
        x = P[dst] - P[o]
        flowreg = pd.Series(np.where(F > 50, 2, np.where(F < -50, 0, 1)), index=P.index)
        reg = season * 100 + block * 10 + flowreg
        cal_key = season * 10 + block  # known ex-ante from calendar!
        df = pd.DataFrame({'q': q_str, 'cal': cal_key.values, 'reg': reg.values, 'x': x.values, 'f': Fd.clip(lower=0.0).values})

        for i, qq in enumerate(quarters):
            if i < 4:
                continue
            train = df[df.q.isin(quarters[i - 4:i])]
            test = df[df.q == qq]
            # Training stats by full regime (season x 4h block x flowreg)
            stats = train.groupby(['cal', 'reg']).agg(
                mu=('x', 'mean'), sd=('x', 'std'), f=('f', 'mean'), n=('x', 'size'),
                spike=('x', lambda s: (s > K).mean()),
                sev=('x', lambda s: s[s > K].mean() if (s > K).any() else 0.0),
            ).reset_index()
            stats['sd'] = stats.sd.fillna(1.0)
            # Ex-ante transition weights P(flowreg | calendar season x 4h block) from training only
            cal_tot = stats.groupby('cal').n.transform('sum')
            stats['w'] = stats.n / cal_tot
            stats['call'] = _bcall(stats.mu.values, stats.sd.values)
            stats['expected_hr_val'] = stats.w * stats.f * stats.call
            cal_val = stats.groupby('cal').expected_hr_val.sum()

            # Test quarter only uses its calendar (season x 4h block) counts — 100% ex-ante!
            prop = _unit_prop_map(units, [qq], d)[qq]
            ex_ante_val = prop * float(test.cal.map(cal_val).fillna(0.0).sum() / 12.0)

            # Also compute v2 realised-regime value side-by-side to quantify the peek
            st_map = stats.set_index('reg')
            v2_call = _bcall(test.reg.map(st_map.mu).fillna(0.0).values, test.reg.map(st_map.sd).fillna(1.0).values)
            v2_val = prop * float((test.reg.map(st_map.f).fillna(0.0).values * v2_call).sum() / 12.0)

            real = R[(R.quarter == qq) & (R.direction == d)]
            opt_rows.append(dict(
                direction=d, quarter=qq,
                ex_ante_option_per_unit=ex_ante_val,
                v2_realised_regime_option_per_unit=v2_val,
                realised_per_unit=float(real.per_unit.iloc[0]) if len(real) else np.nan,
            ))

            if qq == quarters[-1]:  # latest complete quarter (2026Q2) ex-ante Greeks
                for k in [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]:
                    c_vol = _bcall(stats.mu.values, k * stats.sd.values)
                    cv = stats.assign(v=stats.w * stats.f * c_vol).groupby('cal').v.sum()
                    greek_rows.append(dict(
                        direction=d, quarter=qq, factor='Spread volatility (severity) multiplier',
                        multiplier=k, ex_ante_value_per_unit=prop * float(test.cal.map(cv).fillna(0.0).sum() / 12.0),
                    ))
                    mu2 = stats.mu.values + (k - 1.0) * stats.spike.values * stats.sev.values
                    c_frq = _bcall(mu2, stats.sd.values)
                    cf = stats.assign(v=stats.w * stats.f * c_frq).groupby('cal').v.sum()
                    greek_rows.append(dict(
                        direction=d, quarter=qq, factor='Spike frequency multiplier',
                        multiplier=k, ex_ante_value_per_unit=prop * float(test.cal.map(cf).fillna(0.0).sum() / 12.0),
                    ))

    return pd.DataFrame(diag_rows), pd.DataFrame(opt_rows), pd.DataFrame(greek_rows)


def run(stages: list[str] | None = None) -> dict:
    wanted = set(stages) if stages else {'seed', 'a1', 'a2', 'a3', 'a4', 'a5', 'a6', 'a7', 'a8', 'a9'}
    info: dict[str, int] = {}
    if 'seed' in wanted:
        info['v2_files_seeded'] = seed_v2_evidence()
    need_panel = bool(wanted & {'a1', 'a3', 'a4', 'a5', 'a7', 'a8', 'a9'})
    P = panel.prices() if need_panel else None
    ics = panel.ic() if bool(wanted & {'a1', 'a5', 'a7', 'a9'}) else None
    shares = settlement.loss_shares(P.index) if bool(wanted & {'a1', 'a7', 'a9'}) else None
    S = pd.read_parquet(data('settlement', 'directional_5min.parquet')) if bool(wanted & {'a1', 'a4', 'a5'}) else None
    units = pd.read_csv(v2_ev('sra_unit_registry.csv')) if bool(wanted & {'a1', 'a3', 'a4', 'a9'}) else None

    if 'a1' in wanted:
        a1 = sra_payoff_decomposition(P, ics, S, shares, units)
        write_v3_csv(a1, 'sra_payoff_decomposition.csv')
        info['a1_rows'] = len(a1)
    if 'a2' in wanted:
        a2_reg, a2_drift, a2_carry = auction_deep_analysis()
        write_v3_csv(a2_reg, 'auction_regime_sensitivity.csv')
        write_v3_csv(a2_drift, 'auction_tranche_drift.csv')
        write_v3_csv(a2_carry, 'auction_carry_returns.csv')
        info['a2_regime_rows'] = len(a2_reg)
    if 'a3' in wanted:
        a3_wf, a3_lh, a3_pec = loop_deep_analysis(P, units)
        write_v3_csv(a3_wf, 'loop_attribution_waterfall.csv')
        write_v3_csv(a3_lh, 'loop_hedge_effectiveness.csv')
        write_v3_csv(a3_pec, 'loop_parametric_pec.csv')
        info['a3_waterfall_rows'] = len(a3_wf)
    if 'a4' in wanted:
        a4_comp, a4_two = hedge_deep_analysis(P, S, units)
        write_v3_csv(a4_comp, 'hedge_quarterly_and_components.csv')
        write_v3_csv(a4_two, 'hedge_two_instrument_frontier.csv')
        info['a4_two_inst_rows'] = len(a4_two)
    if 'a5' in wanted:
        a5_diur, a5_neg = diurnal_and_negative_analysis(P, ics, S)
        write_v3_csv(a5_diur, 'diurnal_regime_summary.csv')
        write_v3_csv(a5_neg, 'negative_price_mechanics.csv')
        info['a5_diurnal_rows'] = len(a5_diur)
    if 'a6' in wanted:
        a6_w, a6_all, a6_dir, a6_hor = walk_forward_v3()
        write_v3_csv(a6_w, 'walk_forward_v3_forecasts.csv')
        write_v3_csv(a6_all, 'walk_forward_v3_scores.csv')
        write_v3_csv(a6_dir, 'walk_forward_by_direction.csv')
        write_v3_csv(a6_hor, 'walk_forward_by_horizon.csv')
        info['a6_scores_rows'] = len(a6_all)
    if 'a7' in wanted:
        a7_dil, a7_bl, a7_slip = live_catalysts_analysis(P, ics, shares)
        write_v3_csv(a7_dil, 'qni_dilution_check.csv')
        write_v3_csv(a7_bl, 'basslink_proforma_backcast.csv')
        write_v3_csv(a7_slip, 'bid_stack_slippage.csv')
        info['a7_basslink_rows'] = len(a7_bl)
    if 'a8' in wanted:
        a8 = mpc_cpt_analysis(P)
        write_v3_csv(a8, 'mpc_cpt_normalised.csv')
        info['a8_cpt_rows'] = len(a8)
    if 'a9' in wanted:
        a9_diag, a9_opt, a9_grk = reconciliation_and_option_fix(P, ics, shares, units)
        write_v3_csv(a9_diag, 'qni_south_reconciliation_diag.csv')
        write_v3_csv(a9_opt, 'option_benchmark_v3.csv')
        write_v3_csv(a9_grk, 'option_sensitivity_v3.csv')
        info['a9_option_rows'] = len(a9_opt)
    return info


if __name__ == '__main__':
    import sys
    st = sys.argv[1:] or None
    print(json.dumps(run(st), indent=2))
