"""Headline numbers generator for interregional valuation research v3.

Builds every v2 headline key from `reports/interregional_valuation_research_v3/evidence/`
and adds all Tier A v3 analytical numbers (A1-A9) so zero numbers in the v3 prose are typed by hand.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import summary as v2_summary
from .config import ROOT

EV3 = ROOT / 'reports/interregional_valuation_research_v3/evidence'


def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(EV3 / name)


def f0(x):
    return f'{x:,.0f}'


def f1(x):
    return f'{x:,.1f}'


def f2(x):
    return f'{x:,.2f}'


def money(x, d=0):
    return ('−' if x < 0 else '') + '\\$' + f'{abs(x):,.{d}f}'


def mm(x):
    return ('−' if x < 0 else '') + '\\$' + f'{abs(x) / 1e6:,.1f}m'


def pct(x, d=0):
    return f'{100 * x:.{d}f}%'


def build() -> dict:
    # Reuse v2 summary builder pointed cleanly at EV3
    orig_ev = v2_summary.EV
    try:
        v2_summary.EV = EV3
        N = v2_summary.build()
    finally:
        v2_summary.EV = orig_ev

    # ---- A1. SRA dollar-payoff decomposition ($/unit, 19-quarter mean)
    a1 = _csv('sra_payoff_decomposition.csv')
    for d, g in a1.groupby('direction'):
        tot = g.settled_per_unit.mean()
        loss_u = g.state_coupled_loss_per_unit.mean()
        econg_u = g.state_energy_congestion_per_unit.mean()
        scarc_u = g.state_scarcity_total_per_unit.mean()
        clip_u = g.fixed_flow_clipped_energy_per_unit.mean()
        sinc_u = g.fixed_flow_scarcity_increment_per_unit.mean()
        N[f'sra_dec_tot_{d}'] = money(tot)
        N[f'sra_dec_loss_{d}'] = money(loss_u)
        N[f'sra_dec_econg_{d}'] = money(econg_u)
        N[f'sra_dec_scarc_{d}'] = money(scarc_u)
        N[f'sra_dec_loss_pct_{d}'] = pct(loss_u / tot) if tot > 0 else '0%'
        N[f'sra_dec_econg_pct_{d}'] = pct(econg_u / tot) if tot > 0 else '0%'
        N[f'sra_dec_scarc_pct_{d}'] = pct(scarc_u / tot) if tot > 0 else '0%'
        N[f'sra_dec_clip_{d}'] = money(clip_u)
        N[f'sra_dec_sinc_{d}'] = money(sinc_u)

    # ---- A2. Auction ex-2022 split, T1->T12 drift, credit-support carry
    reg = _csv('auction_regime_sensitivity.csv')
    for rname in ['full_19q', 'ex_2022_crisis', 'early_2021q4_2023q4', 'recent_2024q1_2026q2']:
        row = reg[(reg.regime == rname) & (reg.direction == 'all') & (reg.horizon == 'all')].iloc[0]
        N[f'auc_ratio_{rname}'] = f2(row.value_weighted_ratio)
        N[f'auc_lo_{rname}'] = f2(row.ci_low)
        N[f'auc_hi_{rname}'] = f2(row.ci_high)
        N[f'auc_tr_{rname}'] = f0(row.tranches)
    for h, hk in [('1-2 quarters', 'h12'), ('9-12 quarters', 'h912')]:
        row = reg[(reg.regime == 'ex_2022_crisis') & (reg.direction == 'all') & (reg.horizon == h)].iloc[0]
        N[f'auc_ex22_{hk}'] = f2(row.value_weighted_ratio)
        N[f'auc_ex22_{hk}_lo'] = f2(row.ci_low)
        N[f'auc_ex22_{hk}_hi'] = f2(row.ci_high)

    dr = _csv('auction_tranche_drift.csv')
    dr_all = dr[dr.direction == 'all'].set_index('tranche')
    N['drift_t1_vs_t12'] = pct(dr_all.loc[1, 'median_price_vs_t12'] - 1.0, 0) if 1 in dr_all.index else 'n/a'
    N['drift_t4_vs_t12'] = pct(dr_all.loc[4, 'median_price_vs_t12'] - 1.0, 0) if 4 in dr_all.index else 'n/a'
    N['drift_t1_ratio'] = f2(dr_all.loc[1, 'value_weighted_ratio']) if 1 in dr_all.index else 'n/a'
    N['drift_t12_ratio'] = f2(dr_all.loc[12, 'value_weighted_ratio']) if 12 in dr_all.index else 'n/a'

    cy = _csv('auction_carry_returns.csv').set_index('horizon')
    for h, hk in [('all', 'all'), ('1-2 quarters', 'h12'), ('3-4 quarters', 'h34'),
                  ('5-8 quarters', 'h58'), ('9-12 quarters', 'h912')]:
        r = cy.loc[h]
        N[f'carry_days_auc_{hk}'] = f0(r.median_days_auction_to_cash)
        N[f'carry_days_pay_{hk}'] = f0(r.median_days_payment_to_cash)
        N[f'carry_vwhpr_{hk}'] = pct(r.value_weighted_hpr, 0)
        N[f'carry_drag8_{hk}'] = pct(r.carry_drag_8pct, 1)
        N[f'carry_net8_{hk}'] = pct(r.net_excess_hpr_8pct, 0)
        N[f'carry_net12_{hk}'] = pct(r.net_excess_hpr_12pct, 0)

    # ---- A3. Loop 3-way waterfall, quarterly range, post-loop hedging, parametric PEC
    lw = _csv('loop_attribution_waterfall.csv')
    for d in ['VICNSW', 'NSWVIC', 'VICSA', 'SAVIC', 'NSWSA', 'SANSW']:
        g = lw[lw.direction == d]
        N[f'lw_sq_{d}'] = mm(g.status_quo.sum())
        N[f'lw_neg_{d}'] = mm(g.neg_netting_delta.sum())
        N[f'lw_pt_{d}'] = mm(g.passthrough_reallocation_delta.sum())
        N[f'lw_sec_{d}'] = mm(g.secondary_netting_delta.sum())
        N[f'lw_fin_{d}'] = mm(g.loop_rule.sum())
        N[f'lw_pu_sq_{d}'] = money(g.status_quo_per_unit.mean())
        N[f'lw_pu_fin_{d}'] = money(g.loop_per_unit.mean())
        if g['pct_change'].notna().any():
            N[f'lw_qmin_{d}'] = pct(g['pct_change'].min())
            N[f'lw_qmed_{d}'] = pct(g['pct_change'].median())
            N[f'lw_qmax_{d}'] = pct(g['pct_change'].max())

    lh = _csv('loop_hedge_effectiveness.csv')
    for d in ['VICNSW', 'VICSA', 'NSWSA', 'SANSW']:
        gl = lh[(lh.direction == d) & (lh.basis == 'loop_rule')]
        if len(gl):
            r = gl.iloc[0]
            N[f'loop_hr2_{d}'] = pct(r.weekly_r2)
            N[f'loop_hqr2_{d}'] = pct(r.quarterly_r2)
            N[f'loop_hnmv_{d}'] = f1(r.units_min_variance_per_mw)
            N[f'loop_hstress_{d}'] = f2(r.stress_mw_equivalent)

    pec = _csv('loop_parametric_pec.csv')
    for mw in [0, 150, 800]:
        for comp_p in [0, 20]:
            sub = pec[(pec.pec_mw == mw) & (pec.spread_compression_pct == comp_p)]
            if not len(sub):
                continue
            sm = sub.set_index('direction').total_payout_m
            for d in ['VICNSW', 'VICSA', 'NSWSA', 'SANSW']:
                N[f'pec_{mw}_{comp_p}_{d}'] = '\\$' + f'{sm[d]:,.1f}m'

    # ---- A4. Quarterly & component hedging + 2-instrument frontier
    hc = _csv('hedge_quarterly_and_components.csv')
    for d in ['VICNSW', 'QLDNSW', 'VICSA', 'NSWQLD', 'NSWVIC', 'SAVIC']:
        for t, tk in [('total_spread', 'tot'), ('capped_energy_spread', 'eng'), ('scarcity_cap_spread', 'cap')]:
            r = hc[(hc.direction == d) & (hc.target == t)].iloc[0]
            N[f'hc_wr2_{tk}_{d}'] = pct(r.weekly_r2)
            N[f'hc_qr2_{tk}_{d}'] = pct(r.quarterly_r2)

    tf = _csv('hedge_two_instrument_frontier.csv')
    for d in ['VICNSW', 'QLDNSW', 'VICSA']:
        g0 = tf[(tf.direction == d) & (tf.cap_mw == 0.0)]
        unhedged = g0[g0.sra_units == 0.0].iloc[0].cvar95_weekly_loss
        best_sra = g0.loc[g0.cvar95_weekly_loss.idxmin()]
        g1 = tf[(tf.direction == d) & (tf.cap_mw == 1.0)]
        best_mix = g1.loc[g1.cvar95_weekly_loss.idxmin()]
        N[f'cvar_unhedged_{d}'] = money(unhedged)
        N[f'cvar_sra_only_{d}'] = money(best_sra.cvar95_weekly_loss)
        N[f'cvar_sra_units_{d}'] = f1(best_sra.sra_units)
        N[f'cvar_sra_cap_{d}'] = money(best_mix.cvar95_weekly_loss)
        N[f'cvar_sra_cap_units_{d}'] = f1(best_mix.sra_units)
        N[f'cvar_reduction_mix_{d}'] = pct(1.0 - best_mix.cvar95_weekly_loss / unhedged)

    # ---- A5. Diurnal operating blocks & negative-price loss inversion
    drg = _csv('diurnal_regime_summary.csv')
    drg_all = drg[drg.season == 'All seasons']
    for d in ['VICNSW', 'QLDNSW', 'VICSA', 'NSWQLD', 'NSWVIC', 'SAVIC']:
        for bname, bk in [('Solar Midday (09:00-15:00)', 'midday'),
                          ('Evening Ramp (16:00-21:00)', 'evening'),
                          ('Overnight & Shoulder (22:00-08:00)', 'overnight')]:
            r = drg_all[(drg_all.direction == d) & (drg_all.block == bname)].iloc[0]
            N[f'diur_{bk}_{d}'] = pct(r.residue_share_pct / 100.0)

    neg = _csv('negative_price_mechanics.csv').set_index('pair')
    for p, pk in [('NSW − VIC', 'nsw_vic'), ('QLD − NSW', 'qld_nsw'), ('SA − VIC', 'sa_vic')]:
        r = neg.loc[p]
        N[f'neg_share_{pk}'] = pct(r.neg_from_share_pct / 100.0, 1)
        N[f'neg_spread_{pk}'] = '\\$' + f2(r.mean_spread_when_from_neg)
        N[f'neg_loss_{pk}'] = money(r.mean_loss_term_when_from_neg, 2)
        N[f'pos_loss_{pk}'] = money(r.mean_loss_term_when_from_nonneg, 2)
        N[f'neg_res_share_{pk}'] = pct(r.residue_share_during_neg_from_pct / 100.0, 1)

    # ---- A6. Disaggregated walk-forward + 3 smarter baselines
    wf3 = _csv('walk_forward_v3_scores.csv').set_index('rule')
    N['wf3_first_auction'] = str(wf3.loc['market_clearing_price', 'first_auction'])
    N['wf3_last_auction'] = str(wf3.loc['market_clearing_price', 'last_auction'])
    N['wf3_dropped'] = f0(int(N['auction_tranches'].replace(',', '')) - int(wf3.loc['market_clearing_price', 'n']))
    for r in ['market_clearing_price', 'debiased_clearing_price', 'trailing_4q', 'mpc_rescaled_trailing_4q',
              'trailing_8q', 'outage_adjusted_t12', 'market_clearing_price_matched_t12']:
        if r in wf3.index:
            N[f'wf3_mae_{r}'] = money(wf3.loc[r, 'mae'])
            N[f'wf3_bias_{r}'] = money(wf3.loc[r, 'bias'])
            N[f'wf3_n_{r}'] = f0(wf3.loc[r, 'n'])
            N[f'wf3_pct_{r}'] = pct(wf3.loc[r, 'mae_pct_of_mean'] / 100.0)

    wfd = _csv('walk_forward_by_direction.csv')
    for d in ['VICNSW', 'QLDNSW', 'VICSA', 'NSWQLD', 'NSWVIC', 'SAVIC']:
        rm = wfd[(wfd.direction == d) & (wfd.rule == 'market_clearing_price')].iloc[0]
        rd = wfd[(wfd.direction == d) & (wfd.rule == 'debiased_clearing_price')].iloc[0]
        N[f'wfd_mkt_mae_{d}'] = money(rm.mae)
        N[f'wfd_mkt_pct_{d}'] = pct(rm.mae_pct_of_mean / 100.0)
        N[f'wfd_deb_mae_{d}'] = money(rd.mae)
        N[f'wfd_mkt_bias_{d}'] = money(rm.bias)

    # ---- A7. QNI dilution, pro-forma Basslink, bid-stack slippage
    dil = _csv('qni_dilution_check.csv').set_index('direction')
    for d in ['NSWQLD', 'QLDNSW']:
        r = dil.loc[d]
        N[f'dil_pct_{d}'] = pct(r.mechanical_per_unit_dilution_pct / 100.0, 1)
        N[f'dil_pre_{d}'] = money(r.mean_price_pre_2026q2_2027q1) if np.isfinite(r.mean_price_pre_2026q2_2027q1) else 'n/a'
        N[f'dil_post_{d}'] = money(r.mean_price_post_2027q2_plus) if np.isfinite(r.mean_price_post_2027q2_plus) else 'n/a'

    bl = _csv('basslink_proforma_backcast.csv')
    for d in ['TASVIC', 'VICTAS']:
        g = bl[bl.direction == d]
        N[f'bl_mean_disp_{d}'] = money(g.proforma_per_unit_dispatch.mean())
        N[f'bl_med_disp_{d}'] = money(g.proforma_per_unit_dispatch.median())
        N[f'bl_tot_disp_{d}'] = mm(g.proforma_pos_residue_dispatch.sum())

    sl = _csv('bid_stack_slippage.csv')
    for d in ['VICNSW', 'QLDNSW', 'VICSA']:
        for sz in [25, 50, 100]:
            g = sl[(sl.direction == d) & (sl.order_units == sz)]
            if len(g):
                r = g.iloc[0]
                N[f'slip_{sz}_pct_{d}'] = pct(r.price_impact_pct / 100.0, 1)
                N[f'slip_{sz}_dol_{d}'] = money(r.price_impact_dollars)

    # ---- A8. MPC x CPT interaction
    mc = _csv('mpc_cpt_normalised.csv')
    N['cpt_target'] = money(mc.target_cpt.iloc[0])
    N['apc_fy27'] = money(mc.apc_cap.iloc[0])
    piv = mc.pivot_table(index=['pair', 'quarter'], columns='basis', values='scarcity').reset_index()
    piv['lin_diff'] = piv.linear_mpc_only - piv.raw
    piv['cpt_diff'] = piv.mpc_with_cpt_cap - piv.raw
    piv['cpt_trim'] = piv.linear_mpc_only - piv.mpc_with_cpt_cap
    N['cpt_max_trim'] = f2(piv.cpt_trim.abs().max())
    top_trim = piv.loc[piv.cpt_trim.abs().idxmax()]
    N['cpt_trim_pair'] = str(top_trim.pair)
    N['cpt_trim_quarter'] = str(top_trim.quarter).replace('Q', ' Q')
    N['cpt_trim_lin'] = f2(top_trim.linear_mpc_only)
    N['cpt_trim_cap'] = f2(top_trim.mpc_with_cpt_cap)
    # Count capped intervals across NSW/QLD/SA/VIC on the CPT-capped basis
    mc_cap = mc[mc['basis'] == 'mpc_with_cpt_cap']
    N['cpt_capped_nsw'] = f0(mc_cap[mc_cap['pair'] == 'NSW − VIC']['cpt_capped_intervals_dest'].sum())
    N['cpt_capped_qld'] = f0(mc_cap[mc_cap['pair'] == 'QLD − NSW']['cpt_capped_intervals_dest'].sum())
    N['cpt_capped_sa'] = f0(mc_cap[mc_cap['pair'] == 'SA − VIC']['cpt_capped_intervals_dest'].sum())

    # ---- A9. QNI south diagnostic & Ex-ante option fix
    qd = _csv('qni_south_reconciliation_diag.csv')
    q_main = qd[qd.asset == 'NSW1-QLD1']
    q_terr = qd[qd.asset == 'N-Q-MNSP1']
    N['qnis_main_bias'] = pct(q_main.computed_pos.sum() / q_main.settled_pos.sum() - 1.0, 0)
    N['qnis_terr_settled'] = mm(q_terr.settled_pos.sum())
    N['qnis_signflip_share'] = pct(q_main.sign_flip_share_of_computed_pct.mean() / 100.0, 1)
    N['qnis_smallflow_share'] = pct(q_main.small_flow_share_of_computed_pct.mean() / 100.0, 1)

    o3 = _csv('option_benchmark_v3.csv').dropna()
    N['opt_v3_exante_mult'] = f2(o3.ex_ante_option_per_unit.sum() / o3.realised_per_unit.sum())
    N['opt_v2_peek_mult'] = f2(o3.v2_realised_regime_option_per_unit.sum() / o3.realised_per_unit.sum())
    # Greeks for VICNSW & QLDNSW in 2026 Q2
    gr = _csv('option_sensitivity_v3.csv')
    for d in ['VICNSW', 'QLDNSW', 'VICSA']:
        gv = gr[(gr.direction == d) & (gr.factor.str.contains('volatility'))].set_index('multiplier').ex_ante_value_per_unit
        gf = gr[(gr.direction == d) & (gr.factor.str.contains('frequency'))].set_index('multiplier').ex_ante_value_per_unit
        N[f'greek_base_{d}'] = money(gv.loc[1.0])
        N[f'greek_vol2x_{d}'] = money(gv.loc[2.0])
        N[f'greek_vol_pct_{d}'] = pct(gv.loc[2.0] / gv.loc[1.0] - 1.0)
        N[f'greek_frq2x_{d}'] = money(gf.loc[2.0])
        N[f'greek_frq_pct_{d}'] = pct(gf.loc[2.0] / gf.loc[1.0] - 1.0)

    # Top constraint setters (for Ch. 6 prose)
    ts = _csv('constraint_top_setters.csv')
    vni_top = ts[ts.pair == 'NSW − VIC'].iloc[0]
    sa_top = ts[ts.pair == 'SA − VIC'].iloc[0]
    qld_top = ts[ts.pair == 'QLD − NSW'].iloc[0]
    N['top_set_vni_val'] = f2(vni_top.contribution)
    N['top_set_vni_int'] = f0(vni_top.intervals)
    N['top_set_sa_val'] = f2(sa_top.contribution)
    N['top_set_sa_int'] = f0(sa_top.intervals)
    N['top_set_qld_val'] = f2(qld_top.contribution)
    N['top_set_qld_int'] = f0(qld_top.intervals)

    # Strategic pilot honest scope
    st_st = json.loads((EV3 / 'strategic_pilot_status.json').read_text())
    days_ok = sum(len(v['days']) for v in st_st['regions'].values() if isinstance(v, dict))
    failed_months = sum(1 for v in st_st['regions'].values() if isinstance(v, str))
    N['strategic_days_total'] = str(days_ok)
    N['strategic_failed_months'] = str(failed_months)

    return N


def write() -> dict:
    N = build()
    (EV3 / 'headline_numbers.json').write_text(json.dumps(N, indent=1, ensure_ascii=False), encoding='utf-8')
    return N


if __name__ == '__main__':
    res = write()
    print(f'Wrote {len(res)} headline numbers to {EV3 / "headline_numbers.json"}')
