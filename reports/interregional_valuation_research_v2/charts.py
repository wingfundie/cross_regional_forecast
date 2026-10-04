"""New v2 exhibits (N1-N27), built from ./evidence only. Each returns a dict for the HTML builder:
{id, section, title, note, fig (plotly JSON), csv (evidence file offered as download)}."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

EV = Path(__file__).resolve().parent / 'evidence'
C = {'energy': '#83b6d9', 'scarcity': '#073c64', 'total': '#b08b42', 'teal': '#268a87', 'purple': '#7658c9', 'slate': '#66717e',
     'red': '#b44d5e', 'pale': '#d9e7f1', 'green': '#4f8a3a'}
DIRC = {'VICNSW': '#4c94df', 'NSWVIC': '#9cc3ea', 'QLDNSW': '#b08b42', 'NSWQLD': '#dcc28f', 'VICSA': '#7658c9', 'SAVIC': '#b9a9e6',
        'NSWSA': '#268a87', 'SANSW': '#8fcbc9', 'TASVIC': '#b44d5e', 'VICTAS': '#e0a3ad'}
PAIRC = {'NSW − VIC': '#4c94df', 'QLD − NSW': '#b08b42', 'SA − VIC': '#7658c9', 'VIC − TAS': '#b44d5e'}
MAIN6 = ['VICNSW', 'NSWVIC', 'QLDNSW', 'NSWQLD', 'VICSA', 'SAVIC']


def ev(n):
    return pd.read_csv(EV / n)


def base(fig, ytitle='', height=380, xtitle=''):
    fig.update_layout(height=height, margin=dict(l=70, r=24, t=40, b=56), paper_bgcolor='#fff', plot_bgcolor='#fff',
                      font=dict(family='Arial', size=12, color='#333'), legend=dict(orientation='h', x=0, y=1.12, font=dict(size=11)),
                      hovermode='closest')
    fig.update_xaxes(gridcolor='#edf0f2', automargin=True, title_text=xtitle, title_font_size=12)
    fig.update_yaxes(gridcolor='#e8edf1', zerolinecolor='#97a8b6', automargin=True, title_text=ytitle, title_font_size=12)
    return fig


def out(id_, section, title, note, fig, csv):
    return dict(id=id_, section=section, title=title, note=note, fig=json.loads(fig.to_json()), csv=csv)


def n1_reconciliation():
    r = ev('sra_reconciliation.csv'); r = r[r.coverage > .99]
    L = ev('sra_ledger_quarterly.csv'); L = L[L.complete]
    rows = []
    for d, (asset, exp) in {'VICNSW': ('VIC1-NSW1', 'VIC1'), 'QLDNSW': ('NSW1-QLD1', 'QLD1'), 'VICSA': ('V-SA', 'VIC1')}.items():
        g = L[L.direction == d].groupby('variant').residue_pos.sum() / 1e6
        rows.append(dict(direction=d, lossless=g['dispatch_lossless'], dispatch=g['dispatch_dated_share'], metered=g['metered_dated_share'], settled=g['settled']))
    df = pd.DataFrame(rows)
    fig = go.Figure()
    for col, name, colr in [('lossless', 'Lossless dispatch proxy (v1 style, pooled)', C['pale']), ('dispatch', '+ losses, dated loss share', C['energy']),
                            ('metered', '+ metered flow', C['teal']), ('settled', 'AEMO settled (SETIRSURPLUS)', C['scarcity'])]:
        fig.add_bar(name=name, x=df.direction, y=df[col], marker_color=colr, hovertemplate='%{x}<br>' + name + ': $%{y:,.1f}m<extra></extra>')
    base(fig, 'Positive directional residue, Oct 2021 – Jun 2026 · $m')
    return out('n1', 'ledger', 'Exhibit N1: From the flow × spread proxy to AEMO-settled residue',
               'Positive directional residue summed over 19 complete quarters. Each bar adds one correction; the last bar is the realised payoff pool actually distributed pre-loop.', fig, 'sra_ledger_quarterly.csv')


def n2_realised():
    L = ev('sra_ledger_quarterly.csv'); L = L[(L.variant == 'settled') & L.complete]
    fig = go.Figure()
    for d in MAIN6:
        g = L[L.direction == d]
        fig.add_scatter(x=g.quarter, y=g.per_unit, name=d, mode='lines+markers', line=dict(color=DIRC[d], width=2),
                        hovertemplate=d + ' %{x}<br>$%{y:,.0f} per unit<extra></extra>')
    base(fig, 'Realised payoff · $ per unit per quarter')
    return out('n2', 'ledger', 'Exhibit N2: Realised SRA payoff per unit, 2021 Q4 – 2026 Q2',
               'AEMO-settled positive residue × the unit proportion for the delivery quarter. Auction fees not deducted (zero in the MMS allocation table for most quarters).', fig, 'sra_ledger_quarterly.csv')


def n3_scatter():
    J = ev('auction_vs_realised.csv')
    fig = go.Figure()
    for d in MAIN6:
        g = J[J.direction == d]
        fig.add_scatter(x=g.CLEARINGPRICE, y=g.per_unit, mode='markers', name=d, marker=dict(color=DIRC[d], size=4 + g.quarters_ahead * .9, opacity=.7),
                        customdata=np.c_[g.delivery_quarter, g.tranche, g.quarters_ahead],
                        hovertemplate=d + ' %{customdata[0]} tranche %{customdata[1]}<br>%{customdata[2]} quarters ahead<br>price $%{x:,.0f}<br>realised $%{y:,.0f}<extra></extra>')
    m = float(max(J.CLEARINGPRICE.max(), J.per_unit.max()))
    fig.add_scatter(x=[0, m], y=[0, m], mode='lines', name='Realised = price', line=dict(color=C['slate'], dash='dot'))
    base(fig, 'Realised payoff · $ per unit', 460, 'Auction clearing price · $ per unit')
    return out('n3', 'auctions', 'Exhibit N3: Every delivered tranche, clearing price against realised payoff',
               'Points above the dotted line paid holders more than they paid. Marker size grows with quarters between auction and delivery.', fig, 'auction_vs_realised.csv')


def n4_horizon():
    S = ev('auction_premium_summary.csv')
    order = ['1-2 quarters', '3-4 quarters', '5-8 quarters', '9-12 quarters']
    fig = go.Figure()
    for d in ['all'] + MAIN6:
        g = S[(S.direction == d) & (S.horizon.isin(order))].set_index('horizon').reindex(order)
        vis = True if d == 'all' else 'legendonly'
        col = C['scarcity'] if d == 'all' else DIRC[d]
        fig.add_scatter(x=order, y=g.value_weighted_ratio, name='All directions' if d == 'all' else d, mode='lines+markers', visible=vis,
                        line=dict(color=col, width=3 if d == 'all' else 2),
                        error_y=dict(type='data', symmetric=False, array=g.ci_high - g.value_weighted_ratio, arrayminus=g.value_weighted_ratio - g.ci_low, color=col),
                        hovertemplate='%{x}<br>realised ÷ price %{y:.2f}<extra></extra>')
    fig.add_hline(y=1, line_dash='dot', line_color=C['slate'])
    base(fig, 'Value-weighted realised ÷ price', 400, 'Time from auction to delivery')
    return out('n4', 'auctions', 'Exhibit N4: The discount grows with time to delivery',
               'Ratio of realised payoff to price, weighted by units sold. Bars: 95% cluster-bootstrap interval resampling delivery quarters (2,000 replicates). Click legend entries to add directions.', fig, 'auction_premium_summary.csv')


def n5_heatmap():
    H = ev('auction_premium_heatmap.csv')
    z = H.pivot(index='direction', columns='delivery_quarter', values='ratio').reindex(MAIN6)
    fig = go.Figure(go.Heatmap(z=np.log2(z.values), x=list(z.columns), y=list(z.index), customdata=z.values,
                               colorscale=[[0, '#b44d5e'], [.5, '#ffffff'], [1, '#073c64']], zmid=0, zmin=-2, zmax=2,
                               colorbar=dict(title='log₂ ratio', thickness=12),
                               hovertemplate='%{y} %{x}<br>realised ÷ price %{customdata:.2f}<extra></extra>'))
    base(fig, '', 330)
    return out('n5', 'auctions', 'Exhibit N5: Realised ÷ price by direction and delivery quarter',
               'Blue: holders were paid more than they paid; red: less. Colour is log₂ of the value-weighted ratio across all tranches of the quarter.', fig, 'auction_premium_heatmap.csv')


def n6_n7_futures():
    st = json.loads((EV / 'futures_status.json').read_text())
    figs = []
    if st.get('observed') and (EV / 'futures_premia.csv').exists():
        P = ev('futures_paths.csv'); F = ev('futures_premia.csv')
        fig = go.Figure()
        for (r, q), g in P.groupby(['region', 'contract_quarter']):
            fig.add_scatter(x=g.date, y=g.price, mode='lines', name=f'{r} {q}', line=dict(width=1.5))
        base(fig, 'Base futures · $/MWh')
        figs.append(out('n6', 'futures', 'Exhibit N6: AER base-futures price paths', 'AER public chart exports.', fig, 'futures_paths.csv'))
        fig2 = go.Figure(go.Bar(x=F.region + ' ' + F.contract_quarter, y=F.ex_post_premium, marker_color=C['total']))
        base(fig2, 'Futures − realised · $/MWh')
        figs.append(out('n7', 'futures', 'Exhibit N7: Ex-post base-futures premia', 'Last observed pre-delivery AER price minus realised quarterly average.', fig2, 'futures_premia.csv'))
    else:
        for id_, t in [('n6', 'Exhibit N6: AER base-futures price paths'), ('n7', 'Exhibit N7: Ex-post base and spread premia')]:
            fig = go.Figure()
            fig.add_annotation(text='Not observed: AER chart exports not yet supplied (see data/external/README.md).<br>Run python -m nemic.valuation market after adding them.',
                               x=.5, y=.5, xref='paper', yref='paper', showarrow=False, font=dict(size=13, color=C['slate']))
            fig.update_xaxes(visible=False); fig.update_yaxes(visible=False)
            base(fig, '', 220)
            figs.append(out(id_, 'futures', t + ' — not observed', 'The AER site refuses automated retrieval. The loader, premium calculation and chart are built and run as soon as the files are present.', fig, 'futures_status.json'))
    return figs


def n8_loss():
    lc = ev('loss_congestion_quarterly.csv'); lc = lc[lc.complete & (lc.pair != 'VIC − TAS')]
    fig = make_subplots(rows=1, cols=3, subplot_titles=list(PAIRC)[:3], shared_yaxes=False)
    parts = [('energy_loss', 'Energy · loss', C['pale']), ('energy_congestion', 'Energy · congestion', C['energy']),
             ('scarcity_loss', 'Scarcity · loss', '#c9b27c'), ('scarcity_congestion', 'Scarcity · congestion', C['scarcity'])]
    for i, p in enumerate(list(PAIRC)[:3], 1):
        g = lc[lc.pair == p]
        for col, name, colr in parts:
            fig.add_bar(x=g.quarter, y=g[col], name=name, marker_color=colr, showlegend=i == 1, legendgroup=col, row=1, col=i,
                        hovertemplate=p + ' %{x}<br>' + name + ': $%{y:.2f}/MWh<extra></extra>')
        fig.add_scatter(x=g.quarter, y=g.spread, mode='markers', marker=dict(color=C['total'], size=6), name='Total spread', showlegend=i == 1, legendgroup='t', row=1, col=i)
    fig.update_layout(barmode='relative')
    base(fig, 'AUD/MWh', 430)
    return out('n8', 'loss', 'Exhibit N8: Energy/scarcity × loss/congestion, exactly additive',
               'Loss part = price at the loss-factor-coupled level minus origin price; congestion part = the remainder. Each is split again at $300. The four pieces sum to the quarterly spread.', fig, 'loss_congestion_quarterly.csv')


def n9_mlf():
    s = ev('mlf_flow_sample.csv'); fits = ev('loss_curve_fits.csv')
    names = {'VIC1-NSW1': 'VNI', 'NSW1-QLD1': 'QNI', 'V-SA': 'Heywood', 'T-V-MNSP1': 'Basslink'}
    fig = make_subplots(rows=1, cols=3, subplot_titles=['VNI', 'QNI', 'Heywood'])
    for i, a in enumerate(['VIC1-NSW1', 'NSW1-QLD1', 'V-SA'], 1):
        g = s[s.asset == a]
        fig.add_scatter(x=g.flow, y=g.mlf, mode='markers', marker=dict(size=3, opacity=.25, color=C['energy']), name='Dispatch intervals', showlegend=i == 1, row=1, col=i)
        f = fits[fits.asset == a].sort_values('fy').iloc[-1]
        x = np.linspace(g.flow.quantile(.01), g.flow.quantile(.99), 50)
        fig.add_scatter(x=x, y=f.intercept + f.slope_per_mw * x, mode='lines', line=dict(color=C['scarcity'], width=2), name='Linear fit, latest FY', showlegend=i == 1, row=1, col=i)
    base(fig, 'Marginal loss factor (to ÷ from price when coupled)', 380, 'Interconnector flow · MW (positive = from → to)')
    return out('n9', 'loss', 'Exhibit N9: The loss factor rises with flow',
               'Random sample of 4,000 dispatch intervals per interconnector. AEMO’s published equations add regional demand terms; the linear fit is a readable summary, not the settlement equation.', fig, 'mlf_flow_sample.csv')


def n10_hedge_points():
    P = ev('hedge_weekly_points.csv')
    fig = go.Figure()
    for i, d in enumerate(MAIN6):
        g = P[P.direction == d]
        vis = True if d in ('VICNSW',) else 'legendonly'
        fig.add_scatter(x=g.s, y=g.u, mode='markers', name=d, visible=vis, marker=dict(color=np.where(g.stress, C['red'], DIRC[d]), size=np.where(g.stress, 9, 5), opacity=.75),
                        customdata=g.w, hovertemplate=d + ' week %{customdata}<br>1 MW spread P&L $%{x:,.0f}<br>unit payoff $%{y:,.0f}<extra></extra>')
    base(fig, 'Unit payoff in the week · $', 440, '1 MW flat spread P&L in the week (long destination, short origin) · $')
    return out('n10', 'hedging', 'Exhibit N10: Weekly SRA unit payoff against a 1 MW futures-style spread',
               'Each point is one full week (Oct 2021 – Aug 2026). Red points are the ten weeks with the largest spread P&L. A firm hedge would line up along a straight ray; VNI northbound units flatten exactly in the red weeks.', fig, 'hedge_weekly_points.csv')


def n11_dumbbell():
    H = ev('hedge_effectiveness.csv')
    H = H[H.direction.isin(['VICNSW', 'QLDNSW', 'VICSA'])]
    fig = go.Figure()
    H = H.assign(mw=1 / H.units_min_variance_per_mw)
    for _, r in H.iterrows():
        fig.add_scatter(x=[r.ratio_top_spread_weeks, r.mw], y=[r.direction] * 2, mode='lines', line=dict(color='#c3ccd4', width=6), showlegend=False, hoverinfo='skip')
    fig.add_scatter(x=H.mw, y=H.direction, mode='markers', name='All weeks (regression, 1/n*)', marker=dict(color=C['scarcity'], size=13))
    fig.add_scatter(x=H.ratio_top_spread_weeks, y=H.direction, mode='markers', name='Ten highest-spread weeks', marker=dict(color=C['red'], size=13))
    base(fig, '', 300, 'Unit payoff ÷ 1 MW spread P&L (MW-equivalent of one unit)')
    return out('n11', 'hedging', 'Exhibit N11: What one unit hedges on average, and in stress',
               'All weeks: MW of flat spread best replicated by one unit, 1/n* from the minimum-variance regression. Stress: total unit payoff ÷ total 1 MW spread P&L over the ten highest-spread weeks.', fig, 'hedge_effectiveness.csv')


def n12_frontier():
    F = ev('hedge_cvar_frontier.csv')
    fig = go.Figure()
    for d in ['VICNSW', 'QLDNSW', 'VICSA']:
        g = F[F.direction == d]
        fig.add_scatter(x=g.cvar_weekly_loss, y=g.mean_weekly_pnl, mode='lines+markers', name=d, line=dict(color=DIRC[d]), customdata=g.units,
                        hovertemplate=d + '<br>%{customdata:.1f} units per MW<br>CVaR95 weekly loss $%{x:,.0f}<br>mean weekly P&L $%{y:,.0f}<extra></extra>')
    base(fig, 'Mean weekly P&L · $', 420, 'CVaR 95% of weekly loss · $ (lower is better)')
    return out('n12', 'hedging', 'Exhibit N12: Hedging a short 1 MW spread with SRA units — risk against cost',
               'Units bought at each quarter’s volume-weighted clearing price, spread evenly over 13 weeks. Moving along a curve adds units. A futures hedge would remove the spread risk at the (unobserved) futures premium.', fig, 'hedge_cvar_frontier.csv')


def n13_extended_heatmap():
    sp = ev('spread_decomposition.csv'); sp = sp[sp.complete]
    lab = {'VIC to NSW': 'NSW − VIC', 'NSW to QLD': 'QLD − NSW', 'VIC to SA': 'SA − VIC', 'TAS to VIC': 'VIC − TAS'}
    z = sp.pivot(index='direction', columns='quarter', values='spread').reindex(list(lab))
    m = float(np.nanmax(np.abs(z.values)))
    fig = go.Figure(go.Heatmap(z=z.values, x=list(z.columns), y=[lab[i] for i in z.index], colorscale=[[0, '#b44d5e'], [.5, '#fff'], [1, '#073c64']],
                               zmid=0, zmin=-m, zmax=m, texttemplate='%{z:.0f}', colorbar=dict(title='$/MWh', thickness=12),
                               hovertemplate='%{y} %{x}: $%{z:.2f}/MWh<extra></extra>'))
    base(fig, '', 320)
    return out('n13', 'evidence', 'Exhibit N13: Nineteen complete quarters, four region pairs',
               'Quarterly mean spread, destination minus origin. VIC − TAS is added for the Basslink units that exist from July 2026.', fig, 'spread_decomposition.csv')


def n14_forest():
    b = ev('bootstrap_quarterly.csv'); b = b[(b.block_days == 7) & (b.component == 'spread')]
    fig = make_subplots(rows=1, cols=4, subplot_titles=list(PAIRC), shared_yaxes=True)
    for i, p in enumerate(PAIRC, 1):
        g = b[b.pair == p]
        fig.add_scatter(x=g.estimate, y=g.quarter, mode='markers', marker=dict(color=PAIRC[p], size=7), showlegend=False,
                        error_x=dict(type='data', symmetric=False, array=g.ci_high - g.estimate, arrayminus=g.estimate - g.ci_low, color=PAIRC[p]),
                        hovertemplate=p + ' %{y}: $%{x:.2f} [%{customdata[0]:.2f}, %{customdata[1]:.2f}]<extra></extra>', customdata=np.c_[g.ci_low, g.ci_high], row=1, col=i)
        fig.add_vline(x=0, line_color='#97a8b6', row=1, col=i)
    base(fig, '', 560, 'Quarterly mean spread · $/MWh')
    fig.update_yaxes(autorange='reversed')
    return out('n14', 'uncertainty', 'Exhibit N14: How much of a quarter is one draw of weather and outages?',
               '95% moving-block bootstrap intervals (7-day blocks, 2,000 replicates) for each quarter’s mean spread. Wide bars mean the realised quarter is a noisy estimate of the conditions that produced it.', fig, 'bootstrap_quarterly.csv')


def n15_fragility():
    lo = ev('leave_one_day_out.csv')
    fig = make_subplots(rows=2, cols=2, subplot_titles=list(PAIRC), vertical_spacing=.16)
    for i, p in enumerate(PAIRC):
        g = lo[lo.pair == p]; r, c = i // 2 + 1, i % 2 + 1
        fig.add_bar(x=g.quarter, y=g.spread, name='All days', marker_color=C['energy'], showlegend=i == 0, legendgroup='a', row=r, col=c)
        fig.add_bar(x=g.quarter, y=g.without_top_day, name='Without the single most influential day', marker_color=C['scarcity'], showlegend=i == 0, legendgroup='b', row=r, col=c)
    fig.update_layout(barmode='group')
    base(fig, '$/MWh', 560)
    return out('n15', 'uncertainty', 'Exhibit N15: Remove one day and the quarter changes',
               'The most influential day is the calendar day with the largest absolute contribution to the quarter’s summed spread.', fig, 'leave_one_day_out.csv')


def n16_extremogram():
    e = ev('extremogram.csv')
    pairs = [('NSW1', 'VIC1'), ('VIC1', 'NSW1'), ('QLD1', 'NSW1'), ('SA1', 'VIC1'), ('VIC1', 'SA1'), ('NSW1', 'QLD1')]
    fig = go.Figure()
    for x, y in pairs:
        g = e[(e.conditioning == x) & (e.response == y)]
        fig.add_scatter(x=g.lag_hours, y=g.probability, mode='lines+markers', name=f'{y[:-1]} > $300 given {x[:-1]} > $300')
    base(fig, 'Probability', 400, 'Lag · hours')
    fig.update_xaxes(type='log')
    return out('n16', 'uncertainty', 'Exhibit N16: Cross-regional extremogram',
               'Pr(response region above $300 at t + h | conditioning region above $300 at t). Lag 0 measures common spikes; the decay shows how long scarcity persists and spreads.', fig, 'extremogram.csv')


def n17_counterprice():
    d = ev('counterprice_days.csv')
    fig = go.Figure()
    for code in ['NSWVIC', 'QLDNSW', 'VICSA', 'SAVIC', 'VICNSW']:
        g = d[d.direction == code]
        fig.add_bar(x=g.day, y=g.neg / 1e6, name=code, marker_color=DIRC.get(code, '#999'),
                    customdata=np.c_[g.forced / 1e6], hovertemplate=code + ' %{x|%d %b %Y}<br>negative residue $%{y:.2f}m<br>of which forced flow $%{customdata[0]:.2f}m<extra></extra>')
    fig.update_layout(barmode='relative')
    base(fig, 'Negative residue on the day · $m', 400)
    return out('n17', 'counterprice', 'Exhibit N17: Days with more than $0.1m of counter-price residue',
               'Settled negative residue by day and direction. Hover shows how much occurred while the interconnector was forced (a negative limit forcing flow toward the cheaper region).', fig, 'counterprice_days.csv')


def n18_attribution():
    a = ev('constraint_attribution.csv')
    nq = a.quarter.nunique()
    g = a[a.family != 'coupled/none'].groupby(['pair', 'family', 'network_state']).contribution.sum().div(nq).reset_index()
    fig = go.Figure()
    fams = ['thermal', 'voltage stability', 'transient stability', 'oscillatory', 'interconnector limit', 'negative residue management', 'manual/ramp', 'other', 'unreported']
    cols = ['#4c94df', '#7658c9', '#073c64', '#268a87', '#b08b42', '#b44d5e', '#999', '#ccc', '#eee']
    for fam, col in zip(fams, cols):
        for st, pat in [('system normal', ''), ('outage/other', '/')]:
            s = g[(g.family == fam) & (g.network_state == st)]
            if not len(s):
                continue
            fig.add_bar(x=s.pair, y=s.contribution, name=f'{fam} · {st}', marker=dict(color=col, pattern_shape=pat),
                        hovertemplate='%{x}<br>' + fam + ' · ' + st + ': $%{y:.2f}/MWh<extra></extra>')
    fig.update_layout(barmode='relative')
    base(fig, 'Average congestion contribution · $/MWh', 460)
    return out('n18', 'counterprice', 'Exhibit N18: Which constraints separate the regions?',
               'Congestion part of each pair’s spread, averaged over 19 quarters, attributed to the interconnector’s limit-setting constraint. Family from AEMO’s naming convention; hatched = not a “NIL” (system-normal) equation. A heuristic classification.', fig, 'constraint_attribution.csv')


def n19_outage():
    o = ev('outage_plan_predictive.csv')
    fig = go.Figure()
    for p in PAIRC:
        g = o[o.pair == p]
        fig.add_scatter(x=g.planned_set_hours, y=100 * g.separated_share, mode='markers+text', text=g.quarter, textposition='top center', textfont=dict(size=9),
                        name=p, marker=dict(color=PAIRC[p], size=8))
    base(fig, 'Share of intervals separated beyond losses · %', 460, 'Constraint-set hours already submitted to AEMO before the tranche-12 notification')
    return out('n19', 'counterprice', 'Exhibit N19: Were outage plans known before the auction informative?',
               'Each point is a delivery quarter from 2023 Q1 (mapping of outages to constraint sets starts September 2022). Only outage submissions timestamped before the as-of date are counted.', fig, 'outage_plan_predictive.csv')


def n20_loop():
    lq = ev('loop_counterfactual.csv'); lq = lq[lq.complete]
    t = lq.groupby('direction')[['status_quo', 'loop_rule']].sum() / 1e6
    order = ['VICNSW', 'NSWVIC', 'VICSA', 'SAVIC', 'NSWSA', 'SANSW']
    t = t.reindex(order)
    fig = go.Figure()
    fig.add_bar(x=t.index, y=t.status_quo, name='Existing rules (positive part per direction)', marker_color=C['energy'])
    fig.add_bar(x=t.index, y=t.loop_rule, name='AEMC net-trade rule, dispatch held fixed', marker_color=C['scarcity'])
    base(fig, 'Payout to unit holders, Oct 2021 – Jun 2026 · $m', 420)
    return out('n20', 'loop', 'Exhibit N20: The same history paid out under the loop rule',
               'Rule-only counterfactual: settled allocations and flows are held fixed and redistributed by net trade (AEMC ERC0386). The NSW–SA arm carries no physical flow before EnergyConnect but still receives net trade when VIC is a pass-through region.', fig, 'loop_counterfactual.csv')


def n21_mpc():
    m = ev('mpc_normalised.csv')
    p = m.pivot_table(index=['pair', 'quarter'], columns='basis', values='scarcity').reset_index()
    p = p[p.pair != 'VIC − TAS']
    fig = go.Figure()
    for pr in list(PAIRC)[:3]:
        g = p[p.pair == pr]
        fig.add_bar(x=g.quarter, y=g.normalised - g.raw, name=pr, marker_color=PAIRC[pr])
    fig.update_layout(barmode='group')
    base(fig, 'Change in scarcity component · $/MWh', 360)
    return out('n21', 'settings', 'Exhibit N21: Restating history at the FY2027 market price cap',
               'Intervals at the market price cap are rescaled to the 2026-27 cap from AEMO’s MARKET_PRICE_THRESHOLDS table; other prices unchanged. Shows how much of each quarter’s scarcity value is a function of the cap level.', fig, 'mpc_normalised.csv')


def n22_diurnal():
    d = ev('diurnal_profile.csv')
    seasons = ['Summer', 'Autumn', 'Winter', 'Spring']
    fig = make_subplots(rows=1, cols=3, subplot_titles=list(PAIRC)[:3], shared_yaxes=True)
    for i, p in enumerate(list(PAIRC)[:3], 1):
        g = d[d.pair == p]
        z = g.pivot(index='season', columns='hour', values='spread').reindex(seasons)
        fig.add_heatmap(z=z.values, x=list(z.columns), y=seasons, coloraxis='coloraxis', row=1, col=i,
                        hovertemplate=p + ' %{y} hour %{x}: $%{z:.1f}/MWh<extra></extra>')
    fig.update_layout(coloraxis=dict(colorscale=[[0, '#b44d5e'], [.5, '#fff'], [1, '#073c64']], cmid=0, colorbar=dict(title='$/MWh', thickness=12)))
    base(fig, '', 330, 'Hour of day (interval-ending, UTC+10)')
    return out('n22', 'settings', 'Exhibit N22: When in the day and year the spread is earned',
               'Mean spread by hour and season over the full window. The companion CSV also holds flow-direction shares and residue per hour.', fig, 'diurnal_profile.csv')


def n23_walkforward():
    S = ev('walk_forward_scores.csv')
    S = S.sort_values('mae')
    fig = make_subplots(rows=1, cols=2, subplot_titles=['Mean absolute error · $ per unit', 'Bias (forecast − realised) · $ per unit'])
    col = [C['scarcity'] if r == 'market_clearing_price' else C['energy'] for r in S.rule]
    fig.add_bar(x=S.mae, y=S.rule, orientation='h', marker_color=col, showlegend=False, row=1, col=1)
    fig.add_bar(x=S.bias, y=S.rule, orientation='h', marker_color=col, showlegend=False, row=1, col=2)
    base(fig, '', 340)
    return out('n23', 'valuation', 'Exhibit N23: Walk-forward forecasts of the per-unit payoff at each auction',
               'Every delivered tranche since 2021 scored against its realised payoff using only quarters settled before the auction date. The market price is the most accurate forecast but is biased low: the discount is a premium, not ignorance.', fig, 'walk_forward_scores.csv')


def n24_tornado():
    T = ev('scenario_sensitivity.csv')
    fig = make_subplots(rows=2, cols=3, subplot_titles=MAIN6, vertical_spacing=.2, horizontal_spacing=.12)
    for i, d in enumerate(MAIN6):
        g = T[T.direction == d]; r, c = i // 3 + 1, i % 3 + 1
        b0 = float(g.baseline.iloc[0])
        fig.add_bar(y=g.factor, x=g.high - b0, base=b0, orientation='h', marker_color=C['energy'], showlegend=False, row=r, col=c,
                    hovertemplate='%{y}<br>$%{x:,.0f} vs baseline<extra></extra>')
        fig.add_vline(x=b0, line_color=C['scarcity'], row=r, col=c)
    fig.update_yaxes(showticklabels=False)
    fig.update_yaxes(showticklabels=True, col=1)
    base(fig, '', 520, '$ per unit per quarter')
    return out('n24', 'valuation', 'Exhibit N24: Measured sensitivities of an eight-quarter baseline value',
               'Baseline (line) = mean settled payoff over the last eight complete quarters. Bars show the same quantity under each measured alternative: dispatch or metered flows, loss share 0 to 1, lossless residue and the loop net-trade rule.', fig, 'scenario_sensitivity.csv')


def n25_option():
    O = ev('option_benchmark.csv').dropna()
    fig = go.Figure()
    for d in MAIN6:
        g = O[O.direction == d]
        fig.add_scatter(x=g.realised_per_unit, y=g.option_value_per_unit, mode='markers', name=d, marker=dict(color=DIRC[d], size=8), text=g.quarter,
                        hovertemplate=d + ' %{text}<br>realised $%{x:,.0f}<br>option benchmark $%{y:,.0f}<extra></extra>')
    m = float(max(O.realised_per_unit.max(), O.option_value_per_unit.max()))
    fig.add_scatter(x=[0, m], y=[0, m], mode='lines', line=dict(dash='dot', color=C['slate']), name='Benchmark = realised')
    base(fig, 'Regime spread-option benchmark · $ per unit', 440, 'Realised payoff · $ per unit')
    return out('n25', 'valuation', 'Exhibit N25: A spread-option benchmark that assumes flow and spread are independent',
               'Bachelier calls on the spread within season × 4-hour × flow-direction regimes, times the regime’s mean flow, fitted on the previous four quarters. Its systematic overstatement measures the value lost to firmness.', fig, 'option_benchmark.csv')


def n26_bids():
    Cv = ev('auction_bid_curve_latest.csv')
    fig = go.Figure()
    for (c, d), g in Cv.groupby(['CONTRACTID', 'direction']):
        if d not in MAIN6:
            continue
        g = g.sort_values('cum_units')
        fig.add_scatter(x=g.cum_units, y=g.BIDPRICE, mode='lines', line_shape='hv', name=f'{d} {c}', visible=True if c.endswith('T12') else 'legendonly',
                        line=dict(color=DIRC[d]))
    base(fig, 'Bid price · $ per unit', 440, 'Cumulative units bid')
    return out('n26', 'microstructure', 'Exhibit N26: Aggregate demand curves in the latest auction',
               'Public bid stacks (MMS RESIDUE_PRICE_FUNDS_BID) with participant identities removed by AEMO. Tranche-12 contracts shown; others in the legend.', fig, 'auction_bid_curve_latest.csv')


def n27_strategic():
    p = EV / 'strategic_pilot.csv'
    fig = go.Figure()
    if p.exists() and p.stat().st_size > 50:
        S = ev('strategic_pilot.csv')
        for reg in sorted(S.importing_region.unique()):
            for b, col in [(False, C['energy']), (True, C['red'])]:
                g = S[(S.importing_region == reg) & (S.import_binding == b)]
                fig.add_box(y=g.steepness_per_mw.clip(upper=g.steepness_per_mw.quantile(.95)), name=f'{reg[:-1]} · {"import binding" if b else "not binding"}', marker_color=col, boxpoints=False)
        base(fig, '$/MWh per MW for the next 200 MW (95th pct clipped)', 380)
    else:
        fig.add_annotation(text='Pilot produced no rows', x=.5, y=.5, xref='paper', yref='paper', showarrow=False)
        base(fig, '', 200)
    return out('n27', 'strategic', 'Exhibit N27: Importing-region offer-curve steepness (pilot)',
               'Price increase needed to call 200 MW beyond the energy offered at or below the regional price, on the highest-separation days. Exploratory: a small sample of days, energy offers only, no causal claim.', fig, 'strategic_pilot.csv')


def all_charts() -> list[dict]:
    charts = [n1_reconciliation(), n2_realised(), n3_scatter(), n4_horizon(), n5_heatmap()] + n6_n7_futures() + \
             [n8_loss(), n9_mlf(), n10_hedge_points(), n11_dumbbell(), n12_frontier(), n13_extended_heatmap(), n14_forest(), n15_fragility(),
              n16_extremogram(), n17_counterprice(), n18_attribution(), n19_outage(), n20_loop(), n21_mpc(), n22_diurnal(), n23_walkforward(),
              n24_tornado(), n25_option(), n26_bids(), n27_strategic()]
    return charts


if __name__ == '__main__':
    c = all_charts()
    print(len(c), [x['id'] for x in c])
