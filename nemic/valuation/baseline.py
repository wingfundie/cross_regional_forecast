"""Port of the v1 descriptive decomposition (analyse_history.py), generalised to any window.

``v1_regression`` rebuilds the v1 CSVs from the v1 inputs and checks they match the
committed files exactly. ``run`` applies the same definitions to the full v2 window,
all four region pairs and TAS.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ROOT, cfg, complete_quarter_intervals, log, quarter_of, write_csv

K = 300.0
V1_PAIRS = [('VIC to NSW', 'VIC1', 'NSW1', 'vni'), ('NSW to QLD', 'NSW1', 'QLD1', 'qni'), ('VIC to SA', 'VIC1', 'SA1', 'vsa')]
V2_PAIRS = V1_PAIRS + [('TAS to VIC', 'TAS1', 'VIC1', 'bass')]


def regional(P: pd.DataFrame, k: float = K) -> pd.DataFrame:
    quarter = quarter_of(P.index)
    rows = []
    for region in P:
        for q, s in P[region].groupby(quarter):
            hit = s.gt(k); cap = (s - k).clip(lower=0)
            episodes = int((hit & ~hit.shift(1, fill_value=False)).sum())
            daily = cap.groupby((s.index - pd.Timedelta(nanoseconds=1)).date).sum()
            h30 = s.resample('30min', closed='right', label='right').mean()
            expected_n = complete_quarter_intervals(q)
            rows.append(dict(quarter=str(q), region=region, complete=len(s) == expected_n, intervals=len(s), hours=len(s) / 12,
                             mean_price=s.mean(), capped_energy=s.clip(upper=k).mean(), cap_excess=cap.mean(),
                             above300_hours=hit.sum() / 12, above300_pct=100 * hit.mean(), episodes=episodes,
                             excess_when_above=cap[hit].mean() if hit.any() else 0,
                             negative_pct=100 * s.lt(0).mean(), cap_from_halfhour=(h30 - k).clip(lower=0).mean(),
                             top5days_cap_pct=100 * daily.nlargest(5).sum() / daily.sum() if daily.sum() else 0))
    return pd.DataFrame(rows)


def spreads_and_states(P: pd.DataFrame, pairs, k: float = K) -> tuple[pd.DataFrame, pd.DataFrame]:
    quarter = quarter_of(P.index)
    spread_rows, states = [], []
    for name, a, b, _ in pairs:
        x = P[b] - P[a]; e = P[b].clip(upper=k) - P[a].clip(upper=k)
        c = (P[b] - k).clip(lower=0) - (P[a] - k).clip(lower=0)
        assert np.allclose(x, e + c)
        state = np.select([(P[a] <= k) & (P[b] <= k), (P[a] <= k) & (P[b] > k), (P[a] > k) & (P[b] <= k)],
                          ['neither', 'destination_only', 'origin_only'], default='both')
        for q in quarter.unique():
            mask = quarter == q
            expected_n = complete_quarter_intervals(q)
            spread_rows.append(dict(quarter=str(q), direction=name, complete=mask.sum() == expected_n, spread=x[mask].mean(),
                                    energy=e[mask].mean(), scarcity=c[mask].mean(), hours=mask.sum() / 12))
            for st in ['neither', 'destination_only', 'origin_only', 'both']:
                sel = mask & (state == st)
                states.append(dict(quarter=str(q), direction=name, state=st, hours=sel.sum() / 12, frequency_pct=sel.sum() / mask.sum() * 100,
                                   spread_contribution=x[sel].sum() / mask.sum(), energy_contribution=e[sel].sum() / mask.sum(),
                                   scarcity_contribution=c[sel].sum() / mask.sum()))
    return pd.DataFrame(spread_rows), pd.DataFrame(states)


def flow_diagnostics(P: pd.DataFrame, flows: dict[str, pd.Series], pairs) -> pd.DataFrame:
    """v1 gated diagnostic (kept for comparability) plus corrected ungated and gate-conditional terms (M-01)."""
    rows = []
    for name, a, b, key in pairs:
        f = flows[key].reindex(P.index)
        for origin, dest, fl in [(a, b, f), (b, a, -f)]:
            d = P[dest] - P[origin]; fl = fl.clip(lower=0)
            gate = d.gt(0); eff = fl.where(gate, 0); pos = d.clip(lower=0)
            actual = (eff * pos).mean(); naive = eff.mean() * pos.mean()
            tail_pct = 100 * (eff * pos).where((P[origin] > K) | (P[dest] > K), 0).sum() / (eff * pos).sum()
            ungated = fl.mean() * pos.mean()
            g_f, g_d = fl[gate], d[gate]
            rows.append(dict(direction=f'{origin} to {dest}', hours=len(P) / 12, positive_gross_proxy_dollars=(eff * pos).sum() / 12,
                             mean_effective_flow=eff.mean(), mean_positive_spread=pos.mean(), mean_product=actual, product_means=naive,
                             covariance=actual - naive, tail_proxy_pct=tail_pct,
                             ungated_mean_flow=fl.mean(), ungated_product_means=ungated, ungated_covariance=actual - ungated,
                             gate_probability=gate.mean(),
                             conditional_covariance=(g_f * g_d).mean() - g_f.mean() * g_d.mean() if gate.any() else np.nan,
                             conditional_pearson=g_f.corr(g_d) if gate.sum() > 2 else np.nan,
                             conditional_spearman=g_f.corr(g_d, method='spearman') if gate.sum() > 2 else np.nan))
    return pd.DataFrame(rows)


V1_FLOW_COLS = ['direction', 'hours', 'positive_gross_proxy_dollars', 'mean_effective_flow', 'mean_positive_spread',
                'mean_product', 'product_means', 'covariance', 'tail_proxy_pct']


def v1_inputs():
    start, end = pd.Timestamp('2024-09-01'), pd.Timestamp('2026-09-01')
    paths = [ROOT / f'data/event_{ic}_2y/prices_5min.parquet' for ic in ('vni', 'qni', 'vsa')]
    raw = pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)
    raw = raw[(raw.time > start) & (raw.time <= end) & (raw.INTERVENTION == 0)]
    raw = raw.drop_duplicates(['time', 'REGIONID']).sort_values(['time', 'REGIONID'])
    P = raw.pivot(index='time', columns='REGIONID', values='RRP').sort_index()
    flows = {k: pd.read_parquet(ROOT / f'data/event_{k}_2y/screen_timeseries.parquet').set_index('time').MWFLOW for _, _, _, k in V1_PAIRS}
    return P, flows


def v1_regression() -> dict:
    """Recompute the v1 CSVs and compare with the committed baseline files."""
    base = ROOT / cfg()['baseline_report']
    P, flows = v1_inputs()
    reg = regional(P)
    sp, st = spreads_and_states(P, V1_PAIRS)
    fd = flow_diagnostics(P, flows, V1_PAIRS)[V1_FLOW_COLS]
    out = {}
    for name, df in [('historical_regional_decomposition.csv', reg), ('historical_spread_decomposition.csv', sp),
                     ('historical_joint_regimes.csv', st), ('historical_flow_diagnostics.csv', fd)]:
        ref = pd.read_csv(base / name)
        new = pd.read_csv(pd.io.common.StringIO(df.to_csv(index=False)))
        num = ref.select_dtypes('number').columns
        out[name] = dict(shape_equal=ref.shape == new.shape,
                         max_abs_diff=float((ref[num] - new[num]).abs().max().max()),
                         labels_equal=bool(ref.drop(columns=num).equals(new.drop(columns=num))))
    return out


def run() -> dict:
    from . import panel
    log('baseline', 'started')
    reg_check = v1_regression()
    assert all(v['shape_equal'] and v['labels_equal'] and v['max_abs_diff'] < 1e-9 for v in reg_check.values()), reg_check
    P = panel.prices()
    assert not P.isna().any().any(), 'price panel has gaps'
    ics = panel.ic()
    flows = {'vni': ics['VIC1-NSW1'].MWFLOW, 'qni': ics['NSW1-QLD1'].MWFLOW, 'vsa': ics['V-SA'].MWFLOW, 'bass': ics['T-V-MNSP1'].MWFLOW}
    reg = regional(P)
    sp, st = spreads_and_states(P, V2_PAIRS)
    fd = flow_diagnostics(P, flows, V2_PAIRS)
    fd_v1 = flow_diagnostics(P[P.index > pd.Timestamp('2024-09-01')], flows, V2_PAIRS)
    write_csv(reg, 'regional_decomposition.csv')
    write_csv(sp, 'spread_decomposition.csv')
    write_csv(st, 'joint_regimes.csv')
    write_csv(fd, 'flow_diagnostics_full.csv')
    write_csv(fd_v1, 'flow_diagnostics_v1window.csv')
    info = dict(v1_regression=reg_check, quarters_complete=int(sp[sp.direction == 'VIC to NSW'].complete.sum()))
    log('baseline', 'completed', **info)
    return info
