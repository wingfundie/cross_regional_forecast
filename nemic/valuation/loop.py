"""Loop settlement (net trade approach), AEMC ERC0386 final rule, 25 September 2025.

Implemented from the determination text (sections 3.2.1-3.2.3, appendix B):
  1. Allocation per arm = IRSR under AEMO's existing methodology (signed).
  2. Net loop IRSR = sum of allocations. If <= 0, nothing is paid to SRD units (recovered from CNSPs).
  3. Net regional export quantities; net trade on each arm linking a net exporting region to a net
     importing region. Two exporters: each arm carries its exporter's net export. Two importers:
     each arm carries its importer's net import. A zero-net-export region counts as exporting 0.
     Three exporters (losses): each arm carries its from-region's net export in the flow direction.
  4. Step 1 amount = net trade quantity x (P_importing - P_exporting).
     Step 2 provisional = net loop IRSR x amount / sum(amounts).
     Step 3 final (secondary netting) = net loop IRSR x max(provisional, 0) / sum(max(provisional, 0)).

Historical counterfactuals hold dispatch fixed. Before EnergyConnect there is no NSW-SA flow, so the
NSW-SA arm carries zero physical flow but can still receive net trade (e.g. NSW->VIC->SA pass-through).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ARMS = {'VN': ('VIC1', 'NSW1'), 'VS': ('VIC1', 'SA1'), 'NS': ('NSW1', 'SA1')}
CODES = {('VIC1', 'NSW1'): 'VICNSW', ('NSW1', 'VIC1'): 'NSWVIC', ('VIC1', 'SA1'): 'VICSA', ('SA1', 'VIC1'): 'SAVIC',
         ('NSW1', 'SA1'): 'NSWSA', ('SA1', 'NSW1'): 'SANSW'}
REGIONS = ['NSW1', 'VIC1', 'SA1']


def net_trade(prices: pd.DataFrame, flows: pd.DataFrame, allocations: pd.DataFrame) -> pd.DataFrame:
    """Vectorised net-trade payouts.

    prices: columns NSW1, VIC1, SA1.  flows: columns VN, VS, NS (positive = first region -> second).
    allocations: columns VN, VS, NS, signed IRSR per arm in the physical flow direction ($ per interval).
    Returns payout columns per directional code plus net_loop, status-quo positive parts and diagnostics.
    """
    idx = prices.index
    F = flows.reindex(columns=['VN', 'VS', 'NS']).fillna(0.0)
    A = allocations.reindex(columns=['VN', 'VS', 'NS']).fillna(0.0)
    net_loop = A.sum(axis=1)
    exp = pd.DataFrame({
        'NSW1': F.NS - F.VN,
        'VIC1': F.VN + F.VS,
        'SA1': -F.VS - F.NS,
    }, index=idx)
    out = pd.DataFrame(0.0, index=idx, columns=sorted(set(CODES.values())))
    amt_cols = {}
    E = exp.values
    Pm = prices[REGIONS].values
    n = len(idx)
    exporting = E >= 0  # zero counts as exporting
    n_exp = exporting.sum(axis=1)
    arm_list = list(ARMS.items())
    amounts = np.zeros((n, 3)); qty = np.zeros((n, 3)); direction = np.zeros((n, 3))  # +1 first->second, -1 reverse
    ri = {r: i for i, r in enumerate(REGIONS)}
    for k, (arm, (a, b)) in enumerate(arm_list):
        ia, ib = ri[a], ri[b]
        ea, eb = exporting[:, ia], exporting[:, ib]
        # arm links exporter -> importer
        a_to_b = ea & ~eb
        b_to_a = eb & ~ea
        two_exp = n_exp == 2
        one_exp = n_exp == 1
        q = np.zeros(n)
        q = np.where(a_to_b & two_exp, E[:, ia], q)
        q = np.where(b_to_a & two_exp, E[:, ib], q)
        q = np.where(a_to_b & one_exp, -E[:, ib], q)
        q = np.where(b_to_a & one_exp, -E[:, ia], q)
        d = np.where(a_to_b, 1.0, np.where(b_to_a, -1.0, 0.0))
        three = n_exp == 3
        fl = F[arm].values
        d = np.where(three, np.sign(fl), d)
        q = np.where(three & (fl > 0), E[:, ia], q)
        q = np.where(three & (fl < 0), E[:, ib], q)
        price_diff = np.where(d > 0, Pm[:, ib] - Pm[:, ia], Pm[:, ia] - Pm[:, ib])
        amounts[:, k] = np.where(d != 0, q * price_diff, 0.0)
        qty[:, k] = q; direction[:, k] = d
    s = amounts.sum(axis=1)
    NL = net_loop.values
    with np.errstate(divide='ignore', invalid='ignore'):
        prov = np.where(np.abs(s)[:, None] > 1e-9, NL[:, None] * amounts / s[:, None], 0.0)
        # degenerate: step-1 total not the same sign as net loop -> distribute on positive amounts
        bad = (np.abs(s) <= 1e-9) | (np.sign(s) != np.sign(NL))
        pos_amt = np.clip(amounts, 0, None)
        prov = np.where(bad[:, None] & (pos_amt.sum(1) > 0)[:, None], NL[:, None] * pos_amt / pos_amt.sum(1, keepdims=True), prov)
        pp = np.clip(prov, 0, None)
        final = np.where(pp.sum(1, keepdims=True) > 0, NL[:, None] * pp / pp.sum(1, keepdims=True), 0.0)
    final = np.where(NL[:, None] > 0, final, 0.0)
    for k, (arm, (a, b)) in enumerate(arm_list):
        fwd, rev = CODES[(a, b)], CODES[(b, a)]
        out[fwd] += np.where(direction[:, k] > 0, final[:, k], 0.0)
        out[rev] += np.where(direction[:, k] < 0, final[:, k], 0.0)
        amt_cols[f'amount_{arm}'] = amounts[:, k]
        amt_cols[f'provisional_{arm}'] = prov[:, k]
        amt_cols[f'net_trade_{arm}'] = qty[:, k] * direction[:, k]
    res = out.add_prefix('loop_')
    for arm, (a, b) in ARMS.items():
        al = A[arm]
        res[f'sq_{CODES[(a, b)]}'] = al.where(F[arm] > 0, 0).clip(lower=0)
        res[f'sq_{CODES[(b, a)]}'] = al.where(F[arm] < 0, 0).clip(lower=0)
    res['net_loop'] = net_loop
    res['n_exporting'] = n_exp
    for k, v in amt_cols.items():
        res[k] = v
    return res
