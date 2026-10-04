"""Phase 5 mechanisms and regimes.

* Counter-price and forced flow: negative settled residue by direction, split by whether the
  interconnector was forced (a negative export limit forces reverse flow; a positive import limit
  forces forward flow), whether NRM (negative residue management) was active (NEGATIVE_RESIDUE),
  and whether the exporting region was above $300.
* Constraint attribution: congestion part of each pair's spread, attributed to the limit-setting
  constraint ID reported in DISPATCHINTERCONNECTORRES, by constraint type (AEMO naming convention:
  '>>' thermal, '^^' voltage stability, '::' transient stability, '<<' oscillatory) and by system
  normal ('NIL' in the ID) versus outage/other. This is a naming heuristic, stated as such.
* Outage-plan predictive test: planned constraint-set hours submitted to AEMO before each delivery
  quarter (as-of the quarter's tranche-12 notification) vs realised separation.
* Loop counterfactual: AEMC net trade rule applied to settled allocations with dispatch held fixed.
* Scenario registry: dated structural changes and measured sensitivities of the historical baseline.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from . import loop, panel
from .acquire import load
from .config import ROOT, cfg, complete_quarter_intervals, data, log, quarter_of, write_csv
from .evidence import CANON, MAIN_ASSET

K = 300.0
NRM_ID = {'VICNSW': 'VIC1_NSW1', 'NSWVIC': 'NSW1_VIC1', 'NSWQLD': 'NSW1_QLD1', 'QLDNSW': 'QLD1_NSW1',
          'VICSA': 'VIC1_SA1', 'SAVIC': 'SA1_VIC1', 'TASVIC': 'TAS1_VIC1', 'VICTAS': 'VIC1_TAS1'}


def nrm_flags(index) -> pd.DataFrame:
    x = load('NEGATIVE_RESIDUE')
    x['time'] = pd.to_datetime(x.SETTLEMENTDATE.str.replace('/', '-'))
    x['flag'] = pd.to_numeric(x.NRM_ACTIVATED_FLAG, errors='coerce').fillna(0) > 0
    x = x.sort_values('NRM_DATETIME').drop_duplicates(['time', 'DIRECTIONAL_INTERCONNECTORID'], keep='last')
    w = x.pivot(index='time', columns='DIRECTIONAL_INTERCONNECTORID', values='flag').reindex(index)
    w.attrs['first'] = str(x.time.min())
    return w


def counterprice(P, ics, S) -> tuple[pd.DataFrame, pd.DataFrame]:
    q = quarter_of(P.index)
    nrm = nrm_flags(P.index)
    rows, daily = [], []
    for pr in cfg()['pairs']:
        a, b = pr['a'], pr['b']
        g = ics[MAIN_ASSET[pr['pair']]].reindex(P.index)
        fr, to = cfg()['asset_direction'][MAIN_ASSET[pr['pair']]]
        forced_fwd = g.IMPORTLIMIT > 0      # flow must exceed a positive floor: forced fr->to
        forced_rev = g.EXPORTLIMIT < 0      # flow must be below a negative ceiling: forced to->fr
        for code, o, d in [(pr['sra_ab'], a, b), (pr['sra_ba'], b, a)]:
            neg = S[f'{code}_neg']
            forced = forced_fwd if (o, d) == (fr, to) else forced_rev
            nr = nrm[NRM_ID[code]].astype('boolean') if NRM_ID[code] in nrm else pd.Series(pd.NA, index=P.index, dtype='boolean')
            df = pd.DataFrame({'q': q, 'neg': neg, 'forced': neg.where(forced, 0), 'exp_above': neg.where(P[o] > K, 0),
                               'nrm': neg.where(nr.fillna(False).astype(bool), 0), 'n_neg': neg < 0,
                               'nrm_active': nr.fillna(False).astype(bool), 'nrm_obs': nr.notna(), 'pos': S[f'{code}_pos']})
            t = df.groupby('q').sum()
            for quarter, r in t.iterrows():
                rows.append(dict(direction=code, quarter=str(quarter), negative_residue=r.neg, positive_residue=r.pos,
                                 negative_when_forced=r.forced, negative_when_exporter_above_300=r.exp_above,
                                 negative_while_nrm_active=r.nrm, negative_intervals=int(r.n_neg), nrm_active_intervals=int(r.nrm_active),
                                 nrm_observed_intervals=int(r.nrm_obs)))
            dd = df.groupby((P.index - pd.Timedelta('1ns')).normalize()).agg(neg=('neg', 'sum'), forced=('forced', 'sum'), exp_above=('exp_above', 'sum'))
            dd = dd[dd.neg < -1e5]
            daily.append(dd.reset_index().rename(columns={'index': 'day', 'time': 'day'}).assign(direction=code))
    return pd.DataFrame(rows), pd.concat(daily, ignore_index=True)


def constraint_family(cid: str) -> tuple[str, str]:
    c = str(cid or '')
    if not c or c == 'nan':
        return 'unreported', 'unreported'
    if c.upper().startswith('NRM'):
        return 'negative residue management', 'system normal'
    if c.startswith('#'):
        return 'manual/ramp', 'other'
    fam = 'thermal' if '>>' in c or '>' in c[:3] else 'voltage stability' if '^^' in c else 'transient stability' if '::' in c else \
        'oscillatory' if '<<' in c else 'interconnector limit' if re.match(r'^(V-|N-|Q-|S-|T-|I-)?[A-Z0-9]+[-_]', c) and not any(s in c for s in '>^:<') else 'other'
    state = 'system normal' if 'NIL' in c.upper() else 'outage/other'
    return fam, state


def attribution(P, ics) -> pd.DataFrame:
    q = quarter_of(P.index)
    rows = []
    for pr, (a, b, lab) in CANON.items():
        asset = MAIN_ASSET[pr]
        g = ics[asset].reindex(P.index)
        fr, to = cfg()['asset_direction'][asset]
        sgn = 1.0 if (fr, to) == (a, b) else -1.0
        cong = sgn * (P[to] - P[fr] * g.MARGINALLOSS)
        coupled = (P[to] - P[fr] * g.MARGINALLOSS).abs() <= np.maximum(0.01, 1e-4 * P[fr].abs())
        at_exp = g.MWFLOW >= g.EXPORTLIMIT - 1.0
        at_imp = g.MWFLOW <= g.IMPORTLIMIT + 1.0
        setter = pd.Series(np.where(at_exp, g.EXPORTGENCONID, np.where(at_imp, g.IMPORTGENCONID, None)), index=P.index)
        setter = setter.where(~coupled)
        fam = setter.map(lambda c: constraint_family(c)[0] if c is not None and c == c else 'coupled/none')
        st = setter.map(lambda c: constraint_family(c)[1] if c is not None and c == c else 'coupled/none')
        df = pd.DataFrame({'q': q, 'cong': cong, 'fam': fam, 'state': st, 'n': 1})
        n = df.groupby('q').n.transform('sum')
        df['contrib'] = df.cong / n
        t = df.groupby(['q', 'fam', 'state']).agg(contribution=('contrib', 'sum'), intervals=('n', 'sum')).reset_index()
        t.insert(0, 'pair', lab)
        rows.append(t)
    out = pd.concat(rows, ignore_index=True).rename(columns={'q': 'quarter', 'fam': 'family', 'state': 'network_state'})
    out['quarter'] = out.quarter.astype(str)
    return out


def top_setters(P, ics, n=12) -> pd.DataFrame:
    rows = []
    for pr, (a, b, lab) in CANON.items():
        asset = MAIN_ASSET[pr]
        g = ics[asset].reindex(P.index)
        fr, to = cfg()['asset_direction'][asset]
        sgn = 1.0 if (fr, to) == (a, b) else -1.0
        cong = sgn * (P[to] - P[fr] * g.MARGINALLOSS)
        at_exp = g.MWFLOW >= g.EXPORTLIMIT - 1.0; at_imp = g.MWFLOW <= g.IMPORTLIMIT + 1.0
        setter = pd.Series(np.where(at_exp, g.EXPORTGENCONID, np.where(at_imp, g.IMPORTGENCONID, 'none')), index=P.index)
        t = pd.DataFrame({'setter': setter, 'c': cong / len(P)}).groupby('setter').agg(contribution=('c', 'sum'), intervals=('c', 'size'))
        t = t.reindex(t.contribution.abs().sort_values(ascending=False).index).head(n).reset_index()
        t['family'] = [constraint_family(c)[0] for c in t.setter]; t['network_state'] = [constraint_family(c)[1] for c in t.setter]
        t.insert(0, 'pair', lab)
        rows.append(t)
    return pd.concat(rows, ignore_index=True)


def outage_predictive(P, S, attr: pd.DataFrame) -> pd.DataFrame:
    e = pd.read_parquet(ROOT / 'data/nos_regime_v1/episodes.parquet')[['OUTAGEID', 'submitted', 'status']]
    s = pd.read_parquet(ROOT / 'data/nos_regime_v1/episode_sets.parquet')
    j = s.merge(e, on='OUTAGEID')
    j['prefix'] = j.GENCONSETID.str.extract(r'^([A-Z])-')[0]
    rc = load('RESIDUE_CONTRACTS')
    rc['notify'] = pd.to_datetime(rc.NOTIFYDATE.str.replace('/', '-'), errors='coerce')
    rc['dq'] = rc.CONTRACTYEAR.astype(str) + 'Q' + rc.QUARTER.astype(str)
    rc['tranche'] = pd.to_numeric(rc.TRANCHE)
    asof = rc[rc.tranche == 12].groupby('dq').notify.min()
    rel = {'NSW − VIC': {'I', 'V', 'N'}, 'QLD − NSW': {'I', 'Q', 'N'}, 'SA − VIC': {'I', 'S', 'V'}, 'VIC − TAS': {'I', 'T', 'V'}}
    sep = attr[attr.family != 'coupled/none'].groupby(['pair', 'quarter']).intervals.sum() / \
          attr.groupby(['pair', 'quarter']).intervals.sum()
    rows = []
    for dq in sorted(set(attr.quarter)):
        if dq not in asof.index or pd.Period(dq, 'Q').start_time < pd.Timestamp('2023-01-01'):
            continue
        start, end = pd.Period(dq, 'Q').start_time, pd.Period(dq, 'Q').end_time
        known = j[(j.submitted <= asof[dq]) & (j.set_end > start) & (j.set_start < end)]
        for pair, prefixes in rel.items():
            k = known[known.prefix.isin(prefixes)]
            hours = ((k.set_end.clip(upper=end) - k.set_start.clip(lower=start)).dt.total_seconds() / 3600).sum()
            ih = k[k.prefix == 'I']
            ihours = ((ih.set_end.clip(upper=end) - ih.set_start.clip(lower=start)).dt.total_seconds() / 3600).sum()
            rows.append(dict(pair=pair, quarter=dq, asof=str(asof[dq].date()), planned_set_hours=hours, planned_interregional_set_hours=ihours,
                             planned_sets=int(k.GENCONSETID.nunique()), separated_share=float(sep.get((pair, dq), np.nan))))
    out = pd.DataFrame(rows)
    return out


def loop_counterfactual(P, units) -> tuple[pd.DataFrame, pd.DataFrame]:
    arms = pd.read_parquet(data('settlement', 'settled_arms_5min.parquet'))
    prices = P[['NSW1', 'VIC1', 'SA1']]
    flows = pd.DataFrame({'VN': arms['VIC-NSW_flow'], 'VS': arms['VIC-SA_flow'], 'NS': 0.0}, index=P.index)
    alloc = pd.DataFrame({'VN': arms['VIC-NSW_alloc'], 'VS': arms['VIC-SA_alloc'], 'NS': 0.0}, index=P.index)
    res = loop.net_trade(prices, flows, alloc)
    q = quarter_of(P.index)
    cols = [c for c in res if c.startswith('loop_') or c.startswith('sq_')]
    t = res[cols].groupby(q).sum()
    rows = []
    for quarter, r in t.iterrows():
        n = int((q == quarter).sum())
        for code in ['VICNSW', 'NSWVIC', 'VICSA', 'SAVIC', 'NSWSA', 'SANSW']:
            u = units[(units.quarter == str(quarter)) & (units.direction == code)]
            prop = float(u.PROPORTION.iloc[0]) / 100 if len(u) else (1 / cfg()['fallback_max_units'][code] if code in cfg()['fallback_max_units'] else np.nan)
            rows.append(dict(quarter=str(quarter), direction=code, complete=n == complete_quarter_intervals(quarter),
                             status_quo=r.get(f'sq_{code}', 0.0), loop_rule=r.get(f'loop_{code}', 0.0), proportion=prop,
                             status_quo_per_unit=r.get(f'sq_{code}', 0.0) * prop, loop_per_unit=r.get(f'loop_{code}', 0.0) * prop))
    diag = pd.DataFrame({'q': q.astype(str), 'net_loop_negative': res.net_loop < 0, 'pass_through': res.n_exporting == 2,
                         'secondary_netting': (res[[c for c in res if c.startswith('provisional_')]] < 0).any(axis=1)}).groupby('q').mean().reset_index()
    return pd.DataFrame(rows), diag


def scenario_registry(units: pd.DataFrame, ledger: pd.DataFrame, loopq: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    u = units.pivot_table(index='quarter', columns='direction', values='MAXIMUMUNITS', aggfunc='last').sort_index()
    changes = []
    for d in u.columns:
        s = u[d].dropna()
        ch = s[s.diff().fillna(0) != 0]
        for qq, v in ch.items():
            changes.append(dict(direction=d, effective_quarter=qq, max_units=int(v), previous=int(s.shift(1)[qq])))
    reg = {
        'status': 'Dated registry of structural changes that affect SRA and spread valuation. Dates marked "rule" or "data" are verified from primary text or AEMO tables; items marked "announced" are unverified project timelines and must be checked before use.',
        'items': [
            dict(item='Loop dispatch representation (EnergyConnect)', date='2026-10-01', basis='report S07 (AEMO May 2026 reference paper)', kind='announced'),
            dict(item='Loop settlement: AEMC net trade approach', date='2026-11-01', basis='AEMC ERC0386 final rule 25 Sep 2025; start date per report S07', kind='rule'),
            dict(item='Basslink regulated; VICTAS/TASVIC SRA units', date='2026-07-01', basis='report S10 (AEMO April 2026 final report)', kind='rule'),
            dict(item='Unit-count changes (all directions)', date='see unit_changes', basis='AUCTION_IC_ALLOCATIONS (MMSDM)', kind='data'),
            dict(item='Project EnergyConnect stage 2 full transfer capability', date='2027 (approx.)', basis='public project statements; not verified in this campaign', kind='announced'),
            dict(item='HumeLink', date='2026-2027 (approx.)', basis='public project statements; not verified', kind='announced'),
            dict(item='VNI West', date='after 2029 (approx.)', basis='ISP; not verified', kind='announced'),
            dict(item='Marinus Link stage 1', date='about 2030 (approx.)', basis='public project statements; not verified', kind='announced'),
        ],
        'unit_changes': changes,
    }
    # measured sensitivities of an 8-quarter trailing baseline (per unit), for the tornado chart
    L = ledger[ledger.complete]
    last8 = sorted(L.quarter.unique())[-8:]
    base = L[(L.variant == 'settled') & L.quarter.isin(last8)].groupby('direction').per_unit.mean()
    rows = []
    for d in ['VICNSW', 'NSWVIC', 'NSWQLD', 'QLDNSW', 'VICSA', 'SAVIC']:
        b0 = base.get(d, np.nan)
        def alt(variant):
            return L[(L.variant == variant) & L.quarter.isin(last8) & (L.direction == d)].per_unit.mean()
        lq = loopq[(loopq.direction == d) & loopq.quarter.isin(last8)]
        loop_ratio = lq.loop_rule.sum() / lq.status_quo.sum() if len(lq) and lq.status_quo.sum() else np.nan
        f = pd.read_csv(ROOT / cfg()['report_root'] / 'evidence/leave_one_day_out.csv')
        rows += [dict(direction=d, factor='Dispatch flows instead of settled', low=alt('dispatch_dated_share'), high=alt('dispatch_dated_share')),
                 dict(direction=d, factor='Metered flows, dated loss share', low=alt('metered_dated_share'), high=alt('metered_dated_share')),
                 dict(direction=d, factor='Loss share 0 to 1', low=min(alt('dispatch_share_0'), alt('dispatch_share_1')), high=max(alt('dispatch_share_0'), alt('dispatch_share_1'))),
                 dict(direction=d, factor='Lossless residue', low=alt('dispatch_lossless'), high=alt('dispatch_lossless'))]
        if np.isfinite(loop_ratio):
            rows.append(dict(direction=d, factor='Loop net-trade rule (dispatch fixed)', low=b0 * loop_ratio, high=b0 * loop_ratio))
    T = pd.DataFrame(rows)
    T['baseline'] = T.direction.map(base)
    return reg, T


def run() -> dict:
    log('mechanisms', 'started')
    P = panel.prices()
    ics = panel.ic()
    S = pd.read_parquet(data('settlement', 'directional_5min.parquet'))
    cp, daily = counterprice(P, ics, S)
    write_csv(cp, 'counterprice_quarterly.csv'); write_csv(daily, 'counterprice_days.csv')
    attr = attribution(P, ics)
    write_csv(attr, 'constraint_attribution.csv')
    write_csv(top_setters(P, ics), 'constraint_top_setters.csv')
    op = outage_predictive(P, S, attr)
    write_csv(op, 'outage_plan_predictive.csv')
    units = pd.read_csv(ROOT / cfg()['report_root'] / 'evidence/sra_unit_registry.csv')
    lq, diag = loop_counterfactual(P, units)
    write_csv(lq, 'loop_counterfactual.csv'); write_csv(diag, 'loop_diagnostics.csv')
    ledger = pd.read_csv(ROOT / cfg()['report_root'] / 'evidence/sra_ledger_quarterly.csv')
    reg, tornado = scenario_registry(units, ledger, lq)
    (ROOT / cfg()['report_root'] / 'evidence/scenario_registry.json').write_text(json.dumps(reg, indent=2))
    write_csv(tornado, 'scenario_sensitivity.csv')
    from scipy.stats import spearmanr
    rho = {p: float(spearmanr(g.planned_set_hours, g.separated_share, nan_policy='omit').statistic) for p, g in op.groupby('pair') if len(g) > 4}
    info = dict(counterprice_neg_total=float(cp.negative_residue.sum()), outage_spearman=rho,
                loop_totals={d: [float(g.status_quo.sum()), float(g.loop_rule.sum())] for d, g in lq[lq.complete].groupby('direction')})
    log('mechanisms', 'completed', **info)
    return info
