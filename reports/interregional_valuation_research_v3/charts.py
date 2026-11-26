"""Curated v3 exhibits built exclusively from ./evidence on a pure white #ffffff canvas.

Retires duplicate static Figure 1 and duplicate heatmap N13, converts unobserved AER N6-N7
to conditional rendering (auto-enabled once AER exports exist), upgrades N4/N11/N12/N21/N23/N25
with Tier A analytics and clean English labels, and adds four new Tier A exhibits (V1-V4).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

EV = Path(__file__).resolve().parent / 'evidence'
C = {
    'energy': '#83b6d9', 'scarcity': '#073c64', 'total': '#b08b42', 'teal': '#268a87',
    'purple': '#7658c9', 'slate': '#66717e', 'red': '#b44d5e', 'pale': '#d9e7f1', 'green': '#4f8a3a',
}
DIRC = {
    'VICNSW': '#4c94df', 'NSWVIC': '#9cc3ea', 'QLDNSW': '#b08b42', 'NSWQLD': '#dcc28f',
    'VICSA': '#7658c9', 'SAVIC': '#b9a9e6', 'NSWSA': '#268a87', 'SANSW': '#8fcbc9',
    'TASVIC': '#b44d5e', 'VICTAS': '#e0a3ad',
}
PAIRC = {'NSW − VIC': '#4c94df', 'QLD − NSW': '#b08b42', 'SA − VIC': '#7658c9', 'VIC − TAS': '#b44d5e'}
MAIN6 = ['VICNSW', 'NSWVIC', 'QLDNSW', 'NSWQLD', 'VICSA', 'SAVIC']

RULE_LABELS = {
    'market_clearing_price': 'Auction clearing price',
    'debiased_clearing_price': 'Debiased clearing price (ex-ante)',
    'trailing_4q': 'Trailing 4 quarters',
    'mpc_rescaled_trailing_4q': 'MPC-rescaled trailing 4 quarters',
    'trailing_8q': 'Trailing 8 quarters',
    'trailing_12q': 'Trailing 12 quarters',
    'same_season': 'Trailing same-season mean',
    'last_quarter': 'Prior settled quarter',
}


def ev(name: str) -> pd.DataFrame:
    return pd.read_csv(EV / name)


def fmt_q(series) -> list[str]:
    return [str(q).replace('Q', ' Q') for q in series]


def base(fig, ytitle='', height=380, xtitle=''):
    fig.update_layout(
        height=height, margin=dict(l=72, r=24, t=46, b=56),
        paper_bgcolor='#ffffff', plot_bgcolor='#ffffff',
        font=dict(family='Segoe UI, Arial, sans-serif', size=12, color='#30343a'),
        legend=dict(orientation='h', x=0, y=1.13, font=dict(size=11)),
        hovermode='closest',
    )
    fig.update_xaxes(gridcolor='#edf0f2', automargin=True, title_text=xtitle, title_font_size=12)
    fig.update_yaxes(gridcolor='#e8edf1', zerolinecolor='#97a8b6', automargin=True, title_text=ytitle, title_font_size=12)
    return fig


def out(id_, title, subtitle, note, fig, csv_name):
    return dict(id=id_, title=title, subtitle=subtitle, note=note, fig=json.loads(fig.to_json()), csv=csv_name)


# ---- Ch. 2: Pre-loop settlement ledger & SRA $/unit decomposition
def n1_reconciliation():
    L = ev('sra_ledger_quarterly.csv')
    L = L[L.complete]
    rows = []
    for d in ['VICNSW', 'QLDNSW', 'VICSA', 'NSWQLD']:
        g = L[L.direction == d].groupby('variant').residue_pos.sum() / 1e6
        rows.append(dict(direction=d, lossless=g['dispatch_lossless'], dispatch=g['dispatch_dated_share'],
                         metered=g['metered_dated_share'], settled=g['settled']))
    df = pd.DataFrame(rows)
    fig = go.Figure()
    for col, name, colr in [
        ('lossless', 'Lossless dispatch proxy', C['pale']),
        ('dispatch', 'Loss-adjusted dispatch', C['energy']),
        ('metered', 'Loss-adjusted metered', C['teal']),
        ('settled', 'AEMO settled surplus', C['scarcity']),
    ]:
        fig.add_bar(name=name, x=df.direction, y=df[col], marker_color=colr,
                    hovertemplate='%{x}<br>' + name + ': $%{y:,.1f}m<extra></extra>')
    base(fig, 'Positive directional residue ($m)', 370)
    return out('n1', 'Exhibit 2.1: From lossless flow-times-spread to AEMO-settled residue',
               'AUD millions · October 2021–June 2026 (19 complete quarters)',
               'Each bar adds one settlement correction; the final bar is the realised pre-loop pool distributed to SRA holders.',
               fig, 'sra_ledger_quarterly.csv')


def n2_realised():
    L = ev('sra_ledger_quarterly.csv')
    L = L[(L.variant == 'settled') & L.complete]
    fig = go.Figure()
    for d in MAIN6:
        g = L[L.direction == d]
        fig.add_scatter(x=fmt_q(g.quarter), y=g.per_unit, name=d, mode='lines+markers',
                        line=dict(color=DIRC[d], width=2),
                        hovertemplate=d + ' %{x}<br>$%{y:,.0f} per unit<extra></extra>')
    base(fig, 'Settled payoff ($ per unit)', 380)
    return out('n2', 'Exhibit 2.2: Quarterly settled SRA payoffs per unit across six directions',
               'AUD per unit per quarter · October 2021–June 2026',
               'AEMO-settled positive residue multiplied by the dated quarterly unit proportion. Auction fees are zero in the allocation register for most quarters.',
               fig, 'sra_ledger_quarterly.csv')


def v1_sra_payoff_decomp():
    df = ev('sra_payoff_decomposition.csv')
    g = df.groupby('direction')[[
        'state_coupled_loss_per_unit', 'state_energy_congestion_per_unit',
        'state_scarcity_dest_only_per_unit', 'state_scarcity_orig_only_per_unit',
        'state_scarcity_both_per_unit', 'settled_per_unit',
    ]].mean().reindex(MAIN6)
    fig = go.Figure()
    fig.add_bar(x=g.index, y=g.state_coupled_loss_per_unit, name='Coupled loss surplus', marker_color=C['pale'],
                hovertemplate='%{x}<br>Coupled loss surplus: $%{y:,.0f}/unit<extra></extra>')
    fig.add_bar(x=g.index, y=g.state_energy_congestion_per_unit, name='Sub-$300 energy congestion', marker_color=C['energy'],
                hovertemplate='%{x}<br>Sub-$300 energy congestion: $%{y:,.0f}/unit<extra></extra>')
    fig.add_bar(x=g.index, y=g.state_scarcity_dest_only_per_unit, name='Scarcity (destination >$300)', marker_color=C['scarcity'],
                hovertemplate='%{x}<br>Destination scarcity: $%{y:,.0f}/unit<extra></extra>')
    fig.add_bar(x=g.index, y=g.state_scarcity_orig_only_per_unit + g.state_scarcity_both_per_unit,
                name='Scarcity (origin or both >$300)', marker_color=C['total'],
                hovertemplate='%{x}<br>Origin or common scarcity: $%{y:,.0f}/unit<extra></extra>')
    fig.update_layout(barmode='stack')
    base(fig, 'Mean quarterly payoff ($ per unit)', 390)
    return out('v1', 'Exhibit 2.3: Exact dollar decomposition of settled SRA unit payoffs',
               'AUD per unit per quarter · October 2021–June 2026 (state attribution)',
               'Interval-level attribution of settled positive residue into coupled loss surplus, separated sub-$300 energy congestion, and separated scarcity states. Bars sum exactly to the 19-quarter mean payoff per unit.',
               fig, 'sra_payoff_decomposition.csv')


# ---- Ch. 3: Loop regime & 3-way waterfall
def n20_loop():
    lq = ev('loop_counterfactual.csv')
    lq = lq[lq.complete]
    order = ['VICNSW', 'NSWVIC', 'VICSA', 'SAVIC', 'NSWSA', 'SANSW']
    t = lq.groupby('direction')[['status_quo', 'loop_rule']].sum().reindex(order) / 1e6
    fig = go.Figure()
    fig.add_bar(x=t.index, y=t.status_quo, name='Pre-loop rules (positive part per direction)', marker_color=C['energy'],
                hovertemplate='%{x}<br>Pre-loop: $%{y:,.1f}m<extra></extra>')
    fig.add_bar(x=t.index, y=t.loop_rule, name='AEMC net-trade rule (dispatch held fixed)', marker_color=C['scarcity'],
                hovertemplate='%{x}<br>Net-trade loop rule: $%{y:,.1f}m<extra></extra>')
    base(fig, 'Cumulative payout pool ($m)', 390)
    return out('n20', 'Exhibit 3.1: Settled history redistributed under the AEMC net-trade loop rule',
               'AUD millions · October 2021–June 2026 (fixed-dispatch rule counterfactual)',
               'Settled arm allocations and flows are held fixed and redistributed by net regional trade under AEMC ERC0386. NSWSA and SANSW receive net-trade payouts whenever Victoria acts as a pass-through region.',
               fig, 'loop_counterfactual.csv')


def v2_loop_waterfall():
    lw = ev('loop_attribution_waterfall.csv')
    order = ['VICNSW', 'NSWVIC', 'VICSA', 'SAVIC', 'NSWSA', 'SANSW']
    g = lw.groupby('direction')[['neg_netting_delta', 'passthrough_reallocation_delta', 'secondary_netting_delta']].sum().reindex(order) / 1e6
    fig = go.Figure()
    fig.add_bar(x=g.index, y=g.neg_netting_delta, name='Negative-loop netting drag', marker_color=C['red'],
                hovertemplate='%{x}<br>Negative-loop netting: $%{y:,.1f}m<extra></extra>')
    fig.add_bar(x=g.index, y=g.passthrough_reallocation_delta, name='Pass-through net-trade reallocation', marker_color=C['teal'],
                hovertemplate='%{x}<br>Pass-through reallocation: $%{y:,.1f}m<extra></extra>')
    fig.add_bar(x=g.index, y=g.secondary_netting_delta, name='Secondary netting adjustment', marker_color=C['total'],
                hovertemplate='%{x}<br>Secondary netting: $%{y:,.1f}m<extra></extra>')
    fig.update_layout(barmode='relative')
    base(fig, 'Change vs. pre-loop pool ($m)', 390)
    return out('v2', 'Exhibit 3.2: Three-way decomposition of the loop-rule pool redistribution',
               'AUD millions · October 2021–June 2026 (additive delta vs. status quo)',
               'Separates the total rule-only change into (1) whole-loop negative-residue netting, (2) Victoria pass-through net-trade reallocation, and (3) secondary netting of provisional negative arms.',
               fig, 'loop_attribution_waterfall.csv')


# ---- Ch. 4: Uncertainty, CPT, Diurnal
def n14_forest():
    b = ev('bootstrap_quarterly.csv')
    b = b[(b.block_days == 7) & (b.component == 'spread')]
    fig = make_subplots(rows=1, cols=4, subplot_titles=list(PAIRC), shared_yaxes=True)
    for i, p in enumerate(PAIRC, 1):
        g = b[b.pair == p]
        qlabs = fmt_q(g.quarter)
        fig.add_scatter(x=g.estimate, y=qlabs, mode='markers', marker=dict(color=PAIRC[p], size=7), showlegend=False,
                        error_x=dict(type='data', symmetric=False, array=g.ci_high - g.estimate,
                                     arrayminus=g.estimate - g.ci_low, color=PAIRC[p]),
                        customdata=np.c_[g.ci_low, g.ci_high],
                        hovertemplate=p + ' %{y}: $%{x:.2f} [$%{customdata[0]:.2f}, $%{customdata[1]:.2f}]<extra></extra>',
                        row=1, col=i)
        fig.add_vline(x=0, line_color='#97a8b6', row=1, col=i)
    base(fig, '', 540, 'Quarterly mean spread (AUD/MWh)')
    fig.update_yaxes(autorange='reversed')
    return out('n14', 'Exhibit 4.1: Moving-block bootstrap uncertainty around quarterly spreads',
               'AUD/MWh · October 2021–June 2026 (7-day blocks, 2,000 replicates)',
               'Horizontal bars show 95% confidence intervals resampling contiguous 7-day blocks within each quarter. Wide intervals reflect how heavily a single weather or outage sequence drives a quarter mean.',
               fig, 'bootstrap_quarterly.csv')


def n15_fragility():
    lo = ev('leave_one_day_out.csv')
    fig = make_subplots(rows=2, cols=2, subplot_titles=list(PAIRC), vertical_spacing=.18)
    for i, p in enumerate(PAIRC):
        g = lo[lo.pair == p]
        r, c = i // 2 + 1, i % 2 + 1
        ql = fmt_q(g.quarter)
        fig.add_bar(x=ql, y=g.spread, name='All days', marker_color=C['energy'], showlegend=i == 0, legendgroup='a', row=r, col=c)
        fig.add_bar(x=ql, y=g.without_top_day, name='Excluding single most influential day', marker_color=C['scarcity'],
                    showlegend=i == 0, legendgroup='b', row=r, col=c)
    fig.update_layout(barmode='group')
    base(fig, 'AUD/MWh', 540)
    return out('n15', 'Exhibit 4.2: Single-day fragility of realised quarterly spreads',
               'AUD/MWh · October 2021–June 2026 (leave-one-day-out sensitivity)',
               'Compares each realised quarter against the same quarter with its single highest-impact calendar day removed. Three of 76 pair-quarters reverse sign.',
               fig, 'leave_one_day_out.csv')


def n16_extremogram():
    e = ev('extremogram.csv')
    pairs = [('NSW1', 'VIC1'), ('VIC1', 'NSW1'), ('QLD1', 'NSW1'), ('SA1', 'VIC1'), ('VIC1', 'SA1'), ('NSW1', 'QLD1')]
    fig = go.Figure()
    for x, y in pairs:
        g = e[(e.conditioning == x) & (e.response == y)]
        fig.add_scatter(x=g.lag_hours, y=g.probability, mode='lines+markers',
                        name=f'{y[:-1]} > $300 given {x[:-1]} > $300')
    base(fig, 'Conditional probability', 380, 'Lag (hours, log scale)')
    fig.update_xaxes(type='log')
    return out('n16', 'Exhibit 4.3: Cross-regional scarcity persistence and transmission',
               'Probability · October 2021–June 2026 (extremogram above $300/MWh)',
               'Estimated Pr(response region above $300 at t + h | conditioning region above $300 at t). Lag 0 measures simultaneous spikes; decay captures multi-hour persistence.',
               fig, 'extremogram.csv')


def n21_mpc_cpt():
    mc = ev('mpc_cpt_normalised.csv')
    p = mc.pivot_table(index=['pair', 'quarter'], columns='basis', values='scarcity').reset_index()
    p = p[p.pair == 'NSW − VIC'].sort_values('quarter')
    ql = fmt_q(p.quarter)
    fig = go.Figure()
    fig.add_bar(x=ql, y=p.linear_mpc_only - p.raw, name='Linear FY2027 MPC rescaling (no CPT cap)', marker_color=C['energy'])
    fig.add_bar(x=ql, y=p.mpc_with_cpt_cap - p.raw, name='FY2027 MPC with rolling 7-day CPT truncation', marker_color=C['scarcity'])
    fig.update_layout(barmode='group')
    base(fig, 'Change in NSW − VIC scarcity (AUD/MWh)', 360)
    return out('n21', 'Exhibit 4.4: Restating history at the FY2027 market price cap with CPT truncation',
               'AUD/MWh · October 2021–June 2026 (NSW minus VIC scarcity delta)',
               'Compares naive linear rescaling to the $23,200/MWh FY2027 cap against sequential simulation of the rolling 7-day Cumulative Price Threshold and $600/MWh administered price cap.',
               fig, 'mpc_cpt_normalised.csv')


def n22_diurnal():
    d = ev('diurnal_profile.csv')
    seasons = ['Winter', 'Spring', 'Summer', 'Autumn']
    fig = make_subplots(rows=1, cols=3, subplot_titles=list(PAIRC)[:3], shared_yaxes=True)
    for i, p in enumerate(list(PAIRC)[:3], 1):
        g = d[d.pair == p]
        z = g.pivot(index='season', columns='hour', values='spread').reindex(seasons)
        fig.add_heatmap(z=z.values, x=list(z.columns), y=seasons, coloraxis='coloraxis', row=1, col=i,
                        hovertemplate=p + ' %{y} hour %{x}: $%{z:.1f}/MWh<extra></extra>')
    fig.update_layout(coloraxis=dict(colorscale=[[0, '#b44d5e'], [.5, '#ffffff'], [1, '#073c64']], cmid=0,
                                     colorbar=dict(title='AUD/MWh', thickness=12)))
    base(fig, '', 330, 'Hour of day (interval-ending, UTC+10)')
    return out('n22', 'Exhibit 4.5: Diurnal and seasonal structure of regional price spreads',
               'AUD/MWh · October 2021–June 2026 (chronological seasonal order)',
               'Mean five-minute spread by hour and season, separating midday solar-export congestion from evening-ramp scarcity.',
               fig, 'diurnal_profile.csv')


# ---- Ch. 5: Loss vs. Congestion
def n8_loss():
    lc = ev('loss_congestion_quarterly.csv')
    lc = lc[lc.complete & (lc.pair != 'VIC − TAS')]
    fig = make_subplots(rows=1, cols=3, subplot_titles=list(PAIRC)[:3], shared_yaxes=False)
    parts = [('energy_loss', 'Energy · loss', C['pale']), ('energy_congestion', 'Energy · congestion', C['energy']),
             ('scarcity_loss', 'Scarcity · loss', '#c9b27c'), ('scarcity_congestion', 'Scarcity · congestion', C['scarcity'])]
    for i, p in enumerate(list(PAIRC)[:3], 1):
        g = lc[lc.pair == p]
        ql = fmt_q(g.quarter)
        for col, name, colr in parts:
            fig.add_bar(x=ql, y=g[col], name=name, marker_color=colr, showlegend=i == 1, legendgroup=col, row=1, col=i,
                        hovertemplate=p + ' %{x}<br>' + name + ': $%{y:.2f}/MWh<extra></extra>')
        fig.add_scatter(x=ql, y=g.spread, mode='markers', marker=dict(color=C['total'], size=6), name='Total spread',
                        showlegend=i == 1, legendgroup='t', row=1, col=i)
    fig.update_layout(barmode='relative')
    base(fig, 'AUD/MWh', 430)
    return out('n8', 'Exhibit 5.1: Exact 2×2 decomposition into loss vs. congestion and energy vs. scarcity',
               'AUD/MWh · October 2021–June 2026 (three mainland interconnectors)',
               'The four additive pieces sum identically to the quarterly mean spread. Futures carry 100% of the loss terms; SRA units earn roughly half of the coupled loss term as quadratic loss surplus.',
               fig, 'loss_congestion_quarterly.csv')


def n9_mlf():
    s = ev('mlf_flow_sample.csv')
    fits = ev('loss_curve_fits.csv')
    fig = make_subplots(rows=1, cols=3, subplot_titles=['VNI', 'QNI', 'Heywood'])
    for i, a in enumerate(['VIC1-NSW1', 'NSW1-QLD1', 'V-SA'], 1):
        g = s[s.asset == a]
        fig.add_scatter(x=g.flow, y=g.mlf, mode='markers', marker=dict(size=3, opacity=.25, color=C['energy']),
                        name='Dispatch intervals', showlegend=i == 1, row=1, col=i)
        f = fits[fits.asset == a].sort_values('fy').iloc[-1]
        x = np.linspace(g.flow.quantile(.01), g.flow.quantile(.99), 50)
        fig.add_scatter(x=x, y=f.intercept + f.slope_per_mw * x, mode='lines',
                        line=dict(color=C['scarcity'], width=2), name='Linear fit (latest FY)', showlegend=i == 1, row=1, col=i)
    base(fig, 'Marginal loss factor (ratio)', 370, 'Interconnector flow (MW, positive = from to to)')
    return out('n9', 'Exhibit 5.2: Marginal loss factor as an increasing function of transfer flow',
               'Dimensionless ratio · 4,000 sampled dispatch intervals per link',
               'AEMO inter-regional loss equations also include regional demand terms; the linear fit summarises the primary flow dependence.',
               fig, 'mlf_flow_sample.csv')


# ---- Ch. 6: Counter-price, Constraints, Outage plans, Pilot
def n17_counterprice():
    d = ev('counterprice_days.csv')
    fig = go.Figure()
    for code in ['NSWVIC', 'QLDNSW', 'VICSA', 'SAVIC', 'VICNSW']:
        g = d[d.direction == code]
        fig.add_bar(x=g.day, y=g.neg / 1e6, name=code, marker_color=DIRC.get(code, '#999'),
                    customdata=np.c_[g.forced / 1e6],
                    hovertemplate=code + ' %{x|%d %b %Y}<br>Negative residue: $%{y:.2f}m<br>Forced-flow share: $%{customdata[0]:.2f}m<extra></extra>')
    fig.update_layout(barmode='relative')
    base(fig, 'Daily negative residue ($m)', 380)
    return out('n17', 'Exhibit 6.1: Days exceeding $0.1m in settled counter-price residue',
               'AUD millions per day · October 2021–June 2026',
               'Settled negative residue concentrated heavily on NSW to VIC during forced southward flows while NSW exceeded $300/MWh.',
               fig, 'counterprice_days.csv')


def n18_attribution():
    a = ev('constraint_attribution.csv')
    nq = a.quarter.nunique()
    g = a[a.family != 'coupled/none'].groupby(['pair', 'family', 'network_state']).contribution.sum().div(nq).reset_index()
    fig = go.Figure()
    fams = ['thermal', 'voltage stability', 'transient stability', 'oscillatory', 'interconnector limit',
            'negative residue management', 'manual/ramp', 'other', 'unreported']
    cols = ['#4c94df', '#7658c9', '#073c64', '#268a87', '#b08b42', '#b44d5e', '#999999', '#cccccc', '#eeeeee']
    for fam, col in zip(fams, cols):
        for st, pat in [('system normal', ''), ('outage/other', '/')]:
            s = g[(g.family == fam) & (g.network_state == st)]
            if not len(s):
                continue
            fig.add_bar(x=s.pair, y=s.contribution, name=f'{fam} ({st})', marker=dict(color=col, pattern_shape=pat),
                        hovertemplate='%{x}<br>' + fam + ' (' + st + '): $%{y:.2f}/MWh<extra></extra>')
    fig.update_layout(barmode='relative')
    base(fig, 'Mean congestion contribution (AUD/MWh)', 440)
    return out('n18', 'Exhibit 6.2: Congestion spread attribution by binding constraint family and network state',
               'AUD/MWh · October 2021–June 2026 (19-quarter average)',
               'Hatched segments denote outage or non-system-normal equations; solid segments denote system-normal equations. Naming heuristic companion to equation-coefficient studies.',
               fig, 'constraint_attribution.csv')


def n19_outage():
    o = ev('outage_plan_predictive.csv')
    fig = go.Figure()
    for p in PAIRC:
        g = o[o.pair == p]
        fig.add_scatter(x=g.planned_set_hours, y=100 * g.separated_share, mode='markers+text',
                        text=fmt_q(g.quarter), textposition='top center', textfont=dict(size=9),
                        name=p, marker=dict(color=PAIRC[p], size=8))
    base(fig, 'Separated intervals beyond losses (%)', 420, 'Pre-auction submitted constraint-set hours (as-of Tranche 12 notice)')
    return out('n19', 'Exhibit 6.3: Pre-auction planned outage hours against realised price separation',
               'Percent vs. hours · 2023 Q1–2026 Q2 (15 quarters)',
               'Counts only outage-to-constraint-set hours timestamped prior to each quarter Tranche 12 notification date.',
               fig, 'outage_plan_predictive.csv')


def n27_strategic():
    p = EV / 'strategic_pilot.csv'
    fig = go.Figure()
    if p.exists() and p.stat().st_size > 50:
        S = ev('strategic_pilot.csv')
        for reg in sorted(S.importing_region.unique()):
            for b, col in [(False, C['energy']), (True, C['red'])]:
                g = S[(S.importing_region == reg) & (S.import_binding == b)]
                fig.add_box(y=g.steepness_per_mw.clip(upper=g.steepness_per_mw.quantile(.95)),
                            name=f'{reg[:-1]} ({"import binding" if b else "not binding"})',
                            marker_color=col, boxpoints=False)
        base(fig, 'AUD/MWh per MW for next 200 MW (95th pct clipped)', 350)
    return out('n27', 'Exhibit 6.4: Exploratory offer-curve steepness diagnostic (four calendar days)',
               'AUD/MWh per MW · Two NSW days (Nov 2024) and two SA days (Jan 2026)',
               'Exploratory diagnostic only: four of six targeted archive months lacked bid-per-offer files, leaving zero Queensland coverage. Measures energy-offer slope without inferring intent.',
               fig, 'strategic_pilot.csv')


# ---- Ch. 7: Auctions, Term Structure, T1->T12 Drift, Bid Curves
def n3_scatter():
    J = ev('auction_vs_realised.csv')
    fig = go.Figure()
    for d in MAIN6:
        g = J[J.direction == d]
        fig.add_scatter(x=g.CLEARINGPRICE, y=g.per_unit, mode='markers', name=d,
                        marker=dict(color=DIRC[d], size=4 + g.quarters_ahead * .85, opacity=.72),
                        customdata=np.c_[fmt_q(g.delivery_quarter), g.tranche, g.quarters_ahead],
                        hovertemplate=d + ' %{customdata[0]} Tranche %{customdata[1]}<br>%{customdata[2]} quarters ahead<br>Clearing price: $%{x:,.0f}<br>Realised payoff: $%{y:,.0f}<extra></extra>')
    m = float(max(J.CLEARINGPRICE.max(), J.per_unit.max()))
    fig.add_scatter(x=[0, m], y=[0, m], mode='lines', name='Realised equals price', line=dict(color=C['slate'], dash='dot'))
    base(fig, 'Realised payoff ($ per unit)', 430, 'Auction clearing price ($ per unit)')
    return out('n3', 'Exhibit 7.1: Clearing price against realised payoff across 1,332 delivered tranches',
               'AUD per unit · October 2021–June 2026 delivery quarters',
               'Points above the dotted diagonal paid holders more than the clearing price (63% of tranches). Marker size scales with quarters between auction and delivery.',
               fig, 'auction_vs_realised.csv')


def n4_horizon():
    S = ev('auction_regime_sensitivity.csv')
    order = ['1-2 quarters', '3-4 quarters', '5-8 quarters', '9-12 quarters']
    fig = go.Figure()
    for rname, label, col, dash in [
        ('full_19q', 'Full sample (19 quarters)', C['scarcity'], 'solid'),
        ('ex_2022_crisis', 'Excluding 2022 crisis (17 quarters)', C['teal'], 'dash'),
        ('recent_2024q1_2026q2', 'Recent window (2024 Q1–2026 Q2)', C['total'], 'dot'),
    ]:
        g = S[(S.regime == rname) & (S.direction == 'all') & (S.horizon.isin(order))].set_index('horizon').reindex(order)
        fig.add_scatter(
            x=order, y=g.value_weighted_ratio, name=label, mode='lines+markers',
            line=dict(color=col, width=2.8 if rname == 'full_19q' else 2.2, dash=dash),
            error_y=dict(type='data', symmetric=False, array=g.ci_high - g.value_weighted_ratio,
                         arrayminus=g.value_weighted_ratio - g.ci_low, color=col) if rname in ('full_19q', 'ex_2022_crisis') else None,
            hovertemplate=label + '<br>%{x}: %{y:.2f}×<extra></extra>',
        )
    fig.add_hline(y=1.0, line_dash='dot', line_color=C['slate'])
    base(fig, 'Value-weighted realised / price', 400, 'Horizon from auction to delivery')
    return out('n4', 'Exhibit 7.2: Auction discount term structure across full, ex-2022, and recent samples',
               'Ratio (realised ÷ price) · 95% quarter-cluster bootstrap intervals',
               'Compares the full 19-quarter horizon gradient against the 17-quarter ex-2022-crisis sample and the 10-quarter post-2024 window to test whether the term discount persists outside the 2022 shock.',
               fig, 'auction_regime_sensitivity.csv')


def v3_tranche_drift():
    dr = ev('auction_tranche_drift.csv')
    cy = ev('auction_carry_returns.csv')
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Median price vs. Tranche 12 clearing price', 'Excess return after 8% p.a. credit-support carry'])
    da = dr[dr.direction == 'all'].sort_values('tranche')
    fig.add_scatter(x=da.tranche, y=100 * da.median_price_vs_t12, mode='lines+markers', name='Price / T12 (%)',
                    line=dict(color=C['scarcity'], width=2.5), showlegend=False, row=1, col=1,
                    hovertemplate='Tranche %{x} (%{customdata}q ahead)<br>%{y:.1f}% of T12 price<extra></extra>',
                    customdata=da.quarters_ahead)
    fig.add_hline(y=100, line_dash='dot', line_color=C['slate'], row=1, col=1)
    order = ['1-2 quarters', '3-4 quarters', '5-8 quarters', '9-12 quarters']
    c = cy.set_index('horizon').reindex(order)
    fig.add_bar(x=order, y=100 * c.value_weighted_hpr, name='Gross value-weighted HPR', marker_color=C['energy'], row=1, col=2)
    fig.add_bar(x=order, y=100 * c.net_excess_hpr_8pct, name='Net of 8% p.a. auction-to-cash carry', marker_color=C['teal'], row=1, col=2)
    fig.update_layout(barmode='group')
    fig.update_xaxes(title_text='Auction tranche (T1 farthest → T12 nearest)', row=1, col=1)
    fig.update_yaxes(title_text='% of Tranche 12 price', row=1, col=1)
    fig.update_yaxes(title_text='Return per tranche (%)', row=1, col=2)
    base(fig, '', 380)
    return out('v3', 'Exhibit 7.3: Tranche-to-tranche price convergence and credit-support carry drag',
               'Percent · October 2021–June 2026 delivered tranches',
               'Left: clearing price normalized by the same quarter final Tranche 12 price, isolating intra-quarter term drift. Right: gross value-weighted holding-period return vs. return net of an illustrative 8% p.a. credit-support charge over the full auction-to-cash window.',
               fig, 'auction_carry_returns.csv')


def n5_heatmap():
    H = ev('auction_premium_heatmap.csv')
    z = H.pivot(index='direction', columns='delivery_quarter', values='ratio').reindex(MAIN6)
    fig = go.Figure(go.Heatmap(
        z=np.log2(z.values), x=fmt_q(z.columns), y=list(z.index), customdata=z.values,
        colorscale=[[0, '#b44d5e'], [.5, '#ffffff'], [1, '#073c64']], zmid=0, zmin=-2, zmax=2,
        colorbar=dict(title='log₂ ratio', thickness=12),
        hovertemplate='%{y} %{x}<br>Realised ÷ price: %{customdata:.2f}×<extra></extra>',
    ))
    base(fig, '', 330)
    return out('n5', 'Exhibit 7.4: Realised-to-price ratio by direction and delivery quarter',
               'log₂(realised ÷ price) · October 2021–June 2026',
               'Blue cells indicate quarters where settled payoffs exceeded value-weighted clearing prices; crimson cells indicate buyer losses.',
               fig, 'auction_premium_heatmap.csv')


def n26_bids():
    Cv = ev('auction_bid_curve_latest.csv')
    fig = go.Figure()
    for (c, d), g in Cv.groupby(['CONTRACTID', 'direction']):
        if d not in MAIN6:
            continue
        g = g.sort_values('cum_units')
        fig.add_scatter(x=g.cum_units, y=g.BIDPRICE, mode='lines', line_shape='hv', name=f'{d} ({c})',
                        visible=True if str(c).endswith('T12') else 'legendonly', line=dict(color=DIRC[d]))
    base(fig, 'Bid price ($ per unit)', 400, 'Cumulative units bid')
    return out('n26', 'Exhibit 7.5: Public aggregate demand curves in the latest auction',
               'AUD per unit · Latest public auction tranche-12 contracts (others in legend)',
               'Anonymised public bid stacks used to estimate order-size clearing slippage for 25, 50, and 100 unit desk allocations.',
               fig, 'auction_bid_curve_latest.csv')


# ---- Ch. 8: Hedging, Post-loop Firmness, Two-Instrument SRA+Cap Frontier
def n10_hedge_points():
    P = ev('hedge_weekly_points.csv')
    fig = go.Figure()
    for d in MAIN6:
        g = P[P.direction == d]
        vis = True if d == 'VICNSW' else 'legendonly'
        fig.add_scatter(x=g.s, y=g.u, mode='markers', name=d, visible=vis,
                        marker=dict(color=np.where(g.stress, C['red'], DIRC[d]), size=np.where(g.stress, 9, 5), opacity=.76),
                        customdata=g.w,
                        hovertemplate=d + ' week %{customdata}<br>1 MW spread P&L: $%{x:,.0f}<br>Unit payoff: $%{y:,.0f}<extra></extra>')
    base(fig, 'Weekly SRA unit payoff ($)', 410, 'Weekly 1 MW flat spread P&L ($)')
    return out('n10', 'Exhibit 8.1: Weekly SRA unit payoff against a 1 MW flat spread',
               'AUD per week · 256 full weeks (October 2021–August 2026)',
               'Crimson markers identify the ten highest-spread weeks. A firm hedge follows a straight ray through the origin; VICNSW payoffs flatten precisely in stress weeks.',
               fig, 'hedge_weekly_points.csv')


def n11_dumbbell():
    H = ev('hedge_effectiveness.csv')
    LH = ev('loop_hedge_effectiveness.csv')
    H = H[H.direction.isin(['VICNSW', 'QLDNSW', 'VICSA'])].assign(mw=1 / H.units_min_variance_per_mw)
    fig = go.Figure()
    for _, r in H.iterrows():
        fig.add_scatter(x=[r.ratio_top_spread_weeks, r.mw], y=[r.direction] * 2, mode='lines',
                        line=dict(color='#c3ccd4', width=6), showlegend=False, hoverinfo='skip')
    fig.add_scatter(x=H.mw, y=H.direction, mode='markers', name='Pre-loop all weeks (1/n*)', marker=dict(color=C['scarcity'], size=12))
    fig.add_scatter(x=H.ratio_top_spread_weeks, y=H.direction, mode='markers', name='Pre-loop 10 stress weeks', marker=dict(color=C['red'], size=12))
    Lsub = LH[(LH.basis == 'loop_rule') & (LH.direction.isin(['VICNSW', 'VICSA']))]
    if len(Lsub):
        fig.add_scatter(x=Lsub.stress_mw_equivalent, y=Lsub.direction, mode='markers',
                        name='Post-loop 10 stress weeks', marker=dict(color=C['teal'], size=12, symbol='diamond'))
    base(fig, '', 310, 'MW-equivalent of one SRA unit')
    return out('n11', 'Exhibit 8.2: Directional hedge equivalence on average, in stress, and under the loop rule',
               'MW-equivalent per unit · 256 full weeks (October 2021–August 2026)',
               'Compares all-week regression MW-equivalence against the ten highest-spread weeks under pre-loop settlement and under the fixed-dispatch AEMC loop rule.',
               fig, 'loop_hedge_effectiveness.csv')


def n12_two_inst_frontier():
    F = ev('hedge_two_instrument_frontier.csv')
    fig = make_subplots(rows=1, cols=3, subplot_titles=['VICNSW (NSW − VIC)', 'QLDNSW (NSW − QLD)', 'VICSA (SA − VIC)'], shared_yaxes=False)
    styles = [(0.0, 'SRA units only (0 MW cap)', C['energy'], 'solid'),
              (0.5, 'SRA + 0.5 MW dest. $300 cap', C['teal'], 'dash'),
              (1.0, 'SRA + 1.0 MW dest. $300 cap', C['scarcity'], 'solid')]
    for i, d in enumerate(['VICNSW', 'QLDNSW', 'VICSA'], 1):
        for cap_mw, label, col, dash in styles:
            g = F[(F.direction == d) & (F.cap_mw == cap_mw)]
            fig.add_scatter(x=g.cvar95_weekly_loss, y=g.mean_weekly_pnl, mode='lines+markers', name=label,
                            line=dict(color=col, dash=dash, width=2), marker=dict(size=4),
                            customdata=g.sra_units, showlegend=i == 1, legendgroup=label, row=1, col=i,
                            hovertemplate=d + '<br>%{customdata:.1f} SRA units + ' + f'{cap_mw:.1f} MW cap<br>CVaR95 loss: $%{{x:,.0f}}<br>Mean weekly P&L: $%{{y:,.0f}}<extra></extra>')
    base(fig, 'Mean weekly P&L ($)', 415, 'CVaR 95% of weekly loss ($, lower is safer)')
    fig.update_layout(margin=dict(l=72, r=24, t=72, b=56), legend=dict(orientation='h', x=0, y=1.18, font=dict(size=11)))
    return out('n12', 'Exhibit 8.3: Single-instrument SRA vs. combined SRA plus destination $300 cap frontier',
               'AUD per week · Illustrative cap pricing at 1.15× historical mean (pending ASX quotes)',
               'Moving along each curve increases SRA units held against a short 1 MW flat spread. Adding a destination $300 cap shifts the tail-risk frontier sharply inward on VICNSW, where SRA firmness breaks during NSW spikes.',
               fig, 'hedge_two_instrument_frontier.csv')


# ---- Ch. 9: Walk-Forward, Sensitivities, Fixed Ex-Ante Option Benchmark & Greeks
def n23_walkforward():
    S = ev('walk_forward_v3_scores.csv')
    S = S[S.rule.isin(RULE_LABELS)].copy()
    S['label'] = S.rule.map(RULE_LABELS)
    S = S.sort_values('mae')
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Mean absolute error ($ per unit)', 'Mean bias: forecast minus realised ($ per unit)'])
    cols = [C['scarcity'] if 'clearing_price' in r else (C['teal'] if 'mpc' in r else C['energy']) for r in S.rule]
    fig.add_bar(x=S.mae, y=S.label, orientation='h', marker_color=cols, showlegend=False, row=1, col=1,
                hovertemplate='%{y}<br>MAE: $%{x:,.0f}/unit<extra></extra>')
    fig.add_bar(x=S.bias, y=S.label, orientation='h', marker_color=cols, showlegend=False, row=1, col=2,
                hovertemplate='%{y}<br>Bias: $%{x:,.0f}/unit<extra></extra>')
    fig.update_yaxes(showticklabels=False, row=1, col=2)
    base(fig, '', 380)
    return out('n23', 'Exhibit 9.1: Walk-forward accuracy and bias at historical auction dates',
               'AUD per unit · 612 scored tranches with at least four prior settled quarters',
               'Every rule uses only information settled at least 28 days before each auction date. Debiased clearing price scales the clearing price by the strictly causal trailing horizon ratio.',
               fig, 'walk_forward_v3_scores.csv')


def n24_tornado():
    T = ev('scenario_sensitivity.csv')
    fig = make_subplots(rows=2, cols=3, subplot_titles=MAIN6, vertical_spacing=.22, horizontal_spacing=.12)
    for i, d in enumerate(MAIN6):
        g = T[T.direction == d]
        r, c = i // 3 + 1, i % 3 + 1
        b0 = float(g.baseline.iloc[0])
        fig.add_bar(y=g.factor, x=g.high - b0, base=b0, orientation='h', marker_color=C['energy'],
                    showlegend=False, row=r, col=c, hovertemplate='%{y}<br>$%{x:,.0f} vs. baseline<extra></extra>')
        fig.add_vline(x=b0, line_color=C['scarcity'], row=r, col=c)
    fig.update_yaxes(showticklabels=False)
    fig.update_yaxes(showticklabels=True, col=1)
    base(fig, '', 500, 'AUD per unit per quarter')
    return out('n24', 'Exhibit 9.2: Measured settlement sensitivities around the trailing eight-quarter baseline',
               'AUD per unit per quarter · Last eight complete quarters (2024 Q3–2026 Q2)',
               'Vertical navy line marks mean settled payoff. Horizontal bars measure the shift under dispatch flow, metered reconstruction, loss-share bounds, lossless proxy, and the AEMC loop rule.',
               fig, 'scenario_sensitivity.csv')


def n25_option():
    O = ev('option_benchmark_v3.csv').dropna()
    fig = go.Figure()
    for d in MAIN6:
        g = O[O.direction == d]
        fig.add_scatter(x=g.realised_per_unit, y=g.ex_ante_option_per_unit, mode='markers', name=d,
                        marker=dict(color=DIRC[d], size=8), text=fmt_q(g.quarter),
                        customdata=g.v2_realised_regime_option_per_unit,
                        hovertemplate=d + ' %{text}<br>Realised: $%{x:,.0f}<br>Ex-ante Bachelier: $%{y:,.0f}<br>v2 realised-regime: $%{customdata:,.0f}<extra></extra>')
    m = float(max(O.realised_per_unit.max(), O.ex_ante_option_per_unit.max()))
    fig.add_scatter(x=[0, m], y=[0, m], mode='lines', line=dict(dash='dot', color=C['slate']), name='Benchmark equals realised')
    base(fig, 'Ex-ante Bachelier benchmark ($ per unit)', 410, 'Realised settled payoff ($ per unit)')
    return out('n25', 'Exhibit 9.3: Strictly ex-ante spread-option benchmark assuming flow–spread independence',
               'AUD per unit · 2022 Q4–2026 Q2 (rolling four-quarter prior regime weights)',
               'Corrects version 2 by replacing realised test-quarter flow regimes with ex-ante calendar-conditioned training frequencies. Systematic overstatement isolates the cost of ignoring within-regime firmness collapse.',
               fig, 'option_benchmark_v3.csv')


def v4_option_greeks():
    G = ev('option_sensitivity_v3.csv')
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Spread volatility (severity) multiplier', 'Spike frequency multiplier'])
    for d in ['VICNSW', 'QLDNSW', 'VICSA', 'NSWQLD']:
        gv = G[(G.direction == d) & (G.factor.str.contains('volatility'))].sort_values('multiplier')
        gf = G[(G.direction == d) & (G.factor.str.contains('frequency'))].sort_values('multiplier')
        fig.add_scatter(x=gv.multiplier, y=gv.ex_ante_value_per_unit, mode='lines+markers', name=d,
                        line=dict(color=DIRC[d], width=2.2), legendgroup=d, row=1, col=1,
                        hovertemplate=d + ' %{x:.2f}× vol: $%{y:,.0f}/unit<extra></extra>')
        fig.add_scatter(x=gf.multiplier, y=gf.ex_ante_value_per_unit, mode='lines+markers', name=d,
                        line=dict(color=DIRC[d], width=2.2), legendgroup=d, showlegend=False, row=1, col=2,
                        hovertemplate=d + ' %{x:.2f}× freq: $%{y:,.0f}/unit<extra></extra>')
    fig.add_vline(x=1.0, line_dash='dot', line_color=C['slate'], row=1, col=1)
    fig.add_vline(x=1.0, line_dash='dot', line_color=C['slate'], row=1, col=2)
    base(fig, 'Ex-ante benchmark value ($ per unit)', 395, 'Stress multiplier relative to trailing 4-quarter baseline')
    fig.update_layout(margin=dict(l=72, r=24, t=70, b=56), legend=dict(orientation='h', x=0, y=1.18, font=dict(size=11)))
    return out('v4', 'Exhibit 9.4: Ex-ante sensitivity of unit value to spread volatility and spike frequency',
               'AUD per unit · 2026 Q2 ex-ante Bachelier Greeks across four major links',
               'Quantifies relative Vega (severity) versus arrival-rate (frequency) curvature. Volatility scaling moves value far more sharply than arrival-rate scaling in this reduced-form option proxy.',
               fig, 'option_sensitivity_v3.csv')


def all_charts() -> dict[str, dict]:
    items = [
        n1_reconciliation(), n2_realised(), v1_sra_payoff_decomp(),
        n20_loop(), v2_loop_waterfall(),
        n14_forest(), n15_fragility(), n16_extremogram(), n21_mpc_cpt(), n22_diurnal(),
        n8_loss(), n9_mlf(),
        n17_counterprice(), n18_attribution(), n19_outage(), n27_strategic(),
        n3_scatter(), n4_horizon(), v3_tranche_drift(), n5_heatmap(), n26_bids(),
        n10_hedge_points(), n11_dumbbell(), n12_two_inst_frontier(),
        n23_walkforward(), n24_tornado(), n25_option(), v4_option_greeks(),
    ]
    return {c['id']: c for c in items}
