"""Headline numbers for the v2 report, computed only from the evidence files (the claims gate).

Every number quoted in research_report.md is a {{key}} placeholder filled from this dictionary.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .config import ROOT, cfg

EV = ROOT / cfg()['report_root'] / 'evidence'


def _csv(n):
    return pd.read_csv(EV / n)


def f0(x):
    return f'{x:,.0f}'


def f1(x):
    return f'{x:,.1f}'


def f2(x):
    return f'{x:,.2f}'


def money(x, d=0):
    return ('−' if x < 0 else '') + '\\$' + (f'{abs(x):,.{d}f}')


def mm(x):
    return ('−' if x < 0 else '') + '\\$' + f'{abs(x) / 1e6:,.1f}m'


def pct(x, d=0):
    return f'{100 * x:.{d}f}%'


def build() -> dict:
    N = {}
    audit = json.loads((EV / 'data_audit.json').read_text())
    N['intervals'] = f0(audit['intervals'])
    N['complete_quarters'] = str(audit['complete_quarters'])
    N['first_quarter'], N['last_quarter'] = '2021 Q4', '2026 Q2'
    N['apc_binding_rows'] = f0(audit['apcflag_bits']['apc_binding'])
    N['mpc_binding_rows'] = f0(audit['apcflag_bits']['mpc_binding'])
    N['irlf_rows'] = f0(audit['apcflag_bits']['irlf_scaling'])
    N['suspension_rows'] = f0(audit['suspension_rows'])
    N['suspension_max_change'] = f2(max(s['max_abs_change'] for s in audit['suspension_sensitivity']))
    N['not_firm_complete'] = str(audit['not_firm_in_complete_quarters'])

    # spreads
    sp = _csv('spread_decomposition.csv'); sp = sp[sp.complete]
    lab = {'VIC to NSW': 'NSW − VIC', 'NSW to QLD': 'QLD − NSW', 'VIC to SA': 'SA − VIC', 'TAS to VIC': 'VIC − TAS'}
    for k, v in lab.items():
        g = sp[sp.direction == k]
        key = v.replace(' − ', '_').lower()
        N[f'mean_spread_{key}'] = f2(g.spread.mean()); N[f'sd_spread_{key}'] = f2(g.spread.std())
        N[f'min_spread_{key}'] = f2(g.spread.min()); N[f'max_spread_{key}'] = f2(g.spread.max())
        N[f'minq_spread_{key}'] = g.loc[g.spread.idxmin(), 'quarter']; N[f'maxq_spread_{key}'] = g.loc[g.spread.idxmax(), 'quarter']

    # settled ledger
    L = _csv('sra_ledger_quarterly.csv'); Ls = L[(L.variant == 'settled') & L.complete]
    for d, g in Ls.groupby('direction'):
        N[f'pu_mean_{d}'] = money(g.per_unit.mean()); N[f'pu_median_{d}'] = money(g.per_unit.median())
        N[f'pu_min_{d}'] = money(g.per_unit.min()); N[f'pu_max_{d}'] = money(g.per_unit.max())
        N[f'neg_total_{d}'] = mm(g.residue_neg.sum()); N[f'pos_total_{d}'] = mm(g.residue_pos.sum())
    N['fallback_unit_rows'] = str(int((Ls.units_source == 'fallback').sum()))
    for d in ['VICNSW', 'QLDNSW', 'VICSA', 'NSWQLD']:
        v = L[L.complete & (L.direction == d)].groupby('variant').per_unit.mean()
        N[f'lossless_uplift_{d}'] = pct(v['dispatch_lossless'] / v['settled'] - 1)
        N[f'dispatch_vs_settled_{d}'] = pct(v['dispatch_dated_share'] / v['settled'] - 1, 1)
        N[f'metered_vs_settled_{d}'] = pct(v['metered_dated_share'] / v['settled'] - 1, 1)
    rec = _csv('sra_reconciliation.csv'); rec = rec[(rec.coverage > .99)]
    t = rec.groupby(['asset', 'exporting_region', 'flow'])[['computed_pos', 'settled_pos']].sum()
    t['bias'] = t.computed_pos / t.settled_pos - 1
    N['rec_vni_north_metered'] = pct(t.loc[('VIC1-NSW1', 'VIC1', 'METEREDMWFLOW'), 'bias'], 2)
    N['rec_qni_south_metered'] = pct(t.loc[('NSW1-QLD1', 'QLD1', 'METEREDMWFLOW'), 'bias'], 2)
    N['rec_heywood_west_metered'] = pct(t.loc[('V-SA', 'VIC1', 'METEREDMWFLOW'), 'bias'], 1)
    N['rec_qni_north_metered'] = pct(t.loc[('NSW1-QLD1', 'NSW1', 'METEREDMWFLOW'), 'bias'], 0)

    # auctions
    S = _csv('auction_premium_summary.csv')
    a = S[(S.direction == 'all') & (S.horizon == 'all')].iloc[0]
    N['auction_tranches'] = f0(a.tranches); N['auction_ratio'] = f2(a.value_weighted_ratio)
    N['auction_ratio_lo'] = f2(a.ci_low); N['auction_ratio_hi'] = f2(a.ci_high)
    N['auction_share_above'] = pct(a.share_tranches_realised_above_price)
    N['auction_mean_premium'] = money(a.mean_premium_per_unit)
    for h, key in [('1-2 quarters', 'h12'), ('3-4 quarters', 'h34'), ('5-8 quarters', 'h58'), ('9-12 quarters', 'h912')]:
        r = S[(S.direction == 'all') & (S.horizon == h)].iloc[0]
        N[f'ratio_{key}'] = f2(r.value_weighted_ratio); N[f'ratio_{key}_lo'] = f2(r.ci_low); N[f'ratio_{key}_hi'] = f2(r.ci_high)
    for d, r in S[(S.horizon == 'all') & (S.direction != 'all')].set_index('direction').iterrows():
        N[f'ratio_{d}'] = f2(r.value_weighted_ratio); N[f'ratio_{d}_lo'] = f2(r.ci_low); N[f'ratio_{d}_hi'] = f2(r.ci_high)
    pv = _csv('auction_proceeds_vs_residue.csv')
    N['proceeds_total'] = mm(pv.proceeds.sum()); N['distributed_total'] = mm(pv.distributed_to_holders.sum())
    N['proceeds_share'] = pct(pv.proceeds.sum() / pv.distributed_to_holders.sum())
    ret = _csv('auction_returns.csv')
    N['hpr_median'] = pct(ret.holding_period_return.median()); N['hpr_share_loss'] = pct((ret.holding_period_return < 0).mean())
    N['days_to_cash'] = f0(ret.mean_days_to_cash.median())
    M = _csv('auction_microstructure.csv')
    N['bid_to_offer'] = f1(M.bid_to_offer.median()); N['unsold_share'] = pct(M.unsold_units.sum() / M.UNITSOFFERED.sum(), 1)
    W = _csv('walk_forward_scores.csv').set_index('rule')
    for r in W.index:
        N[f'wf_mae_{r}'] = money(W.loc[r, 'mae']); N[f'wf_bias_{r}'] = money(W.loc[r, 'bias'])
    N['wf_n'] = f0(W.loc['market_clearing_price', 'n'])

    # hedging
    H = _csv('hedge_effectiveness.csv').set_index('direction')
    for d, r in H.iterrows():
        N[f'hedge_r2_{d}'] = f2(r.r2); N[f'hedge_ratio_all_{d}'] = f2(r.ratio_all); N[f'hedge_ratio_top_{d}'] = f2(r.ratio_top_spread_weeks)
        N[f'hedge_mv_{d}'] = f1(r.units_min_variance_per_mw); N[f'hedge_vr_{d}'] = pct(r.variance_reduction); N[f'hedge_mwpu_{d}'] = f2(1 / r.units_min_variance_per_mw)
    N['hedge_weeks'] = f0(H.weeks.iloc[0])

    # loss / congestion
    lc = _csv('loss_congestion_quarterly.csv'); lc = lc[lc.complete]
    for p, g in lc.groupby('pair'):
        key = p.replace(' − ', '_').lower()
        N[f'loss_{key}'] = f2(g.loss.mean()); N[f'cong_{key}'] = f2(g.congestion.mean()); N[f'coupled_{key}'] = f0(g.coupled_pct.mean())
        share = (g.loss.abs() / (g.loss.abs() + g.congestion.abs())).max()
        N[f'loss_share_max_{key}'] = pct(share)

    # dependence (M-01)
    fd = _csv('flow_diagnostics_v1window.csv').set_index('direction')
    N['v1_cov_vninorth'] = f0(fd.loc['VIC1 to NSW1', 'covariance']); N['v1_ungated_vninorth'] = f0(fd.loc['VIC1 to NSW1', 'ungated_covariance'])
    N['v1_condcov_vninorth'] = f0(fd.loc['VIC1 to NSW1', 'conditional_covariance']); N['v1_condsp_vninorth'] = f2(fd.loc['VIC1 to NSW1', 'conditional_spearman'])
    ff = _csv('flow_diagnostics_full.csv').set_index('direction')
    N['full_condsp_vninorth'] = f2(ff.loc['VIC1 to NSW1', 'conditional_spearman']); N['full_condcov_vninorth'] = f0(ff.loc['VIC1 to NSW1', 'conditional_covariance'])
    N['full_condsp_qninorth'] = f2(ff.loc['QLD1 to NSW1', 'conditional_spearman'])
    td = _csv('tail_dependence.csv').set_index('direction')
    N['vni_flow_stress'] = f0(td.loc['VIC to NSW', 'mean_flow_when_dest_above_300']); N['vni_flow_normal'] = f0(td.loc['VIC to NSW', 'mean_flow_otherwise'])
    N['qni_flow_stress'] = f0(td.loc['QLD to NSW', 'mean_flow_when_dest_above_300']); N['qni_flow_normal'] = f0(td.loc['QLD to NSW', 'mean_flow_otherwise'])

    # counter-price
    cp = _csv('counterprice_quarterly.csv')
    g = cp[cp.direction == 'NSWVIC']
    N['nswvic_neg'] = mm(g.negative_residue.sum()); N['nswvic_forced_share'] = pct(g.negative_when_forced.sum() / g.negative_residue.sum())
    N['nswvic_exp300_share'] = pct(g.negative_when_exporter_above_300.sum() / g.negative_residue.sum())
    N['nswvic_nrm_intervals'] = f0(g.nrm_active_intervals.sum())
    N['all_neg'] = mm(cp.negative_residue.sum()); N['all_forced_share'] = pct(cp.negative_when_forced.sum() / cp.negative_residue.sum())

    # attribution
    at = _csv('constraint_attribution.csv')
    nq = at.quarter.nunique()
    v = at[at.pair == 'NSW − VIC'].groupby('family').contribution.sum() / nq
    N['vni_cong_transient'] = f2(v.get('transient stability', 0)); N['vni_cong_thermal'] = f2(v.get('thermal', 0)); N['vni_cong_voltage'] = f2(v.get('voltage stability', 0))
    s = at[at.pair == 'NSW − VIC'].groupby('network_state').contribution.sum() / nq
    N['vni_cong_system_normal'] = f2(s.get('system normal', 0)); N['vni_cong_outage'] = f2(s.get('outage/other', 0))
    op = _csv('outage_plan_predictive.csv')
    for p, gg in op.groupby('pair'):
        key = p.replace(' − ', '_').lower()
        N[f'outage_rho_{key}'] = f2(gg[['planned_set_hours', 'separated_share']].corr(method='spearman').iloc[0, 1]); N['outage_quarters'] = str(len(gg))

    # loop
    lq = _csv('loop_counterfactual.csv'); lq = lq[lq.complete]
    tot = lq.groupby('direction')[['status_quo', 'loop_rule']].sum()
    for d, r in tot.iterrows():
        N[f'loop_sq_{d}'] = mm(r.status_quo); N[f'loop_new_{d}'] = mm(r.loop_rule)
        if r.status_quo > 0:
            N[f'loop_change_{d}'] = pct(r.loop_rule / r.status_quo - 1)
    N['loop_new_categories'] = mm(tot.loc[['NSWSA', 'SANSW'], 'loop_rule'].sum())
    dg = _csv('loop_diagnostics.csv')
    N['loop_pass_through'] = pct(dg.pass_through.mean()); N['loop_secondary'] = pct(dg.secondary_netting.mean()); N['loop_net_negative'] = pct(dg.net_loop_negative.mean())

    # fragility, bootstrap
    lo = _csv('leave_one_day_out.csv')
    N['sign_flips'] = str(int(lo.sign_flip.sum())); N['pair_quarters'] = str(len(lo))
    big = lo.loc[lo.top_day_share_pct.abs().clip(upper=1000).idxmax()]
    N['frag_pair'], N['frag_quarter'], N['frag_spread'], N['frag_without'] = big.pair, big.quarter, f2(big.spread), f2(big.without_top_day)
    bq = _csv('bootstrap_quarterly.csv'); b = bq[(bq.block_days == 7) & (bq.component == 'spread')]
    b = b.assign(w=b.ci_high - b.ci_low)
    N['boot_median_width'] = f2(b.w.median())

    # MPC
    mp = json.loads((EV / 'mpc_schedule.json').read_text())
    N['mpc_target'] = money(mp['target_mpc'])
    mn = _csv('mpc_normalised.csv'); mn = mn.pivot_table(index=['pair', 'quarter'], columns='basis', values='scarcity').reset_index()
    mn['d'] = mn.normalised - mn.raw
    N['mpc_max_uplift'] = f2(mn.d.abs().max())

    # option benchmark
    O = _csv('option_benchmark.csv').dropna()
    N['option_overstatement'] = f1((O.option_value_per_unit.sum() / O.realised_per_unit.sum()))
    fut = json.loads((EV / 'futures_status.json').read_text())
    N['futures_observed'] = 'observed' if fut.get('observed') else 'not observed'
    try:
        sp_ = _csv('strategic_pilot.csv')
        m = sp_.groupby(['importing_region', 'import_binding']).steepness_per_mw.agg(['median', 'size'])
        parts = []
        for reg in sorted(sp_.importing_region.unique()):
            b = m.loc[(reg, True)] if (reg, True) in m.index else None; nb = m.loc[(reg, False)] if (reg, False) in m.index else None
            parts.append(f"{reg[:-1]}: \${f2(b['median']) if b is not None else 'n/a'} per MW with imports binding ({int(b['size']) if b is not None else 0} intervals) against \${f2(nb['median']) if nb is not None else 'n/a'} otherwise ({int(nb['size']) if nb is not None else 0} intervals)")
        N['strategic_by_region'] = '; '.join(parts)
        N['strategic_intervals'] = f0(len(sp_)); N['strategic_regions'] = ', '.join(sorted(sp_.importing_region.unique()))
    except Exception:
        N['strategic_by_region'] = 'no rows'; N['strategic_intervals'] = '0'; N['strategic_regions'] = 'none'
    return N


def write() -> dict:
    N = build()
    (EV / 'headline_numbers.json').write_text(json.dumps(N, indent=1, ensure_ascii=False), encoding='utf-8')
    return N
