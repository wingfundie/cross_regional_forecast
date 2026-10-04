import numpy as np
import pandas as pd
import pytest

from nemic.valuation.loop import net_trade
from nemic.valuation.settlement import asset_residue


def _frame(**cols):
    return pd.DataFrame({k: [v] for k, v in cols.items()}, index=pd.DatetimeIndex(['2026-11-01 00:05']))


def test_cepa_worked_example_residue():
    # CEPA (2024) table 3.2: metered 76 MW, losses 10 MW, 60% of losses on the importing side (s = 0.4),
    # RRN flows 70 MW (importing) and 80 MW (exporting); importing price $15, exporting price $10 -> $250/h.
    P = _frame(EXP=10.0, IMP=15.0)
    g = pd.DataFrame({'MWFLOW': [76.0], 'MWLOSSES': [10.0]}, index=P.index)
    r = asset_residue(P, g, 'EXP', 'IMP', s=0.4)
    assert r.iloc[0] * 12 == pytest.approx(250.0)


def test_lossless_residue_is_flow_times_spread_and_counter_price_is_negative():
    P = _frame(A=50.0, B=80.0)
    g = pd.DataFrame({'MWFLOW': [100.0], 'MWLOSSES': [0.0]}, index=P.index)
    assert asset_residue(P, g, 'A', 'B', 0.5).iloc[0] * 12 == pytest.approx(3000.0)
    g2 = g.assign(MWFLOW=-100.0)
    assert asset_residue(P, g2, 'A', 'B', 0.5).iloc[0] * 12 == pytest.approx(-3000.0)


def test_aemc_figure_3_1_net_trade():
    # NSW and VIC each export 150 MW, SA imports 300 MW; SA $50, NSW $30, VIC $40 (1-hour interval).
    # Physical flows chosen so VIC->NSW allocation is negative: allocations NSW-SA 4000, VIC-SA 1000, VIC-NSW -500.
    prices = _frame(NSW1=30.0, VIC1=40.0, SA1=50.0)
    flows = _frame(VN=50.0, VS=100.0, NS=200.0)
    alloc = _frame(VN=-500.0, VS=1000.0, NS=4000.0)
    out = net_trade(prices, flows, alloc)
    assert out.net_loop.iloc[0] == pytest.approx(4500.0)
    assert out.loop_NSWSA.iloc[0] == pytest.approx(3000.0)
    assert out.loop_VICSA.iloc[0] == pytest.approx(1500.0)
    assert out[[c for c in out if c.startswith('loop_')]].sum(axis=1).iloc[0] == pytest.approx(4500.0)
    assert out.loop_VICNSW.iloc[0] == 0 and out.loop_NSWVIC.iloc[0] == 0


def test_aemc_example_4_secondary_netting():
    # VIC exports 120 MW, NSW exports 30 MW, SA imports 150 MW; VIC $10, SA $40, NSW $55.
    # Step 1: VIC-SA 120 x 30 = 3600; NSW-SA 30 x (40 - 55) = -450; net loop IRSR 3150 -> all to VIC-SA.
    prices = _frame(NSW1=55.0, VIC1=10.0, SA1=40.0)
    # net exports: NSW = NS - VN = 30, VIC = VN + VS = 120, SA = -(VS + NS) = -150
    flows = _frame(VN=10.0, VS=110.0, NS=40.0)
    alloc = _frame(VN=450.0, VS=3300.0, NS=-600.0)  # sums to 3150
    out = net_trade(prices, flows, alloc)
    assert out.net_trade_VS.iloc[0] == pytest.approx(120.0)
    assert out.net_trade_NS.iloc[0] == pytest.approx(30.0)
    assert out.amount_VS.iloc[0] == pytest.approx(3600.0)
    assert out.amount_NS.iloc[0] == pytest.approx(-450.0)
    assert out.loop_VICSA.iloc[0] == pytest.approx(3150.0)
    assert out.loop_NSWSA.iloc[0] == pytest.approx(0.0)


def test_net_negative_loop_pays_nothing():
    prices = _frame(NSW1=55.0, VIC1=10.0, SA1=40.0)
    flows = _frame(VN=10.0, VS=110.0, NS=40.0)
    alloc = _frame(VN=-450.0, VS=100.0, NS=-600.0)
    out = net_trade(prices, flows, alloc)
    assert out[[c for c in out if c.startswith('loop_')]].to_numpy().sum() == 0


def test_pass_through_is_paid_to_nsw_sa():
    # NSW -> VIC -> SA with no NSW-SA flow: VIC net export 0 -> all net trade on NSW-SA.
    prices = _frame(NSW1=30.0, VIC1=35.0, SA1=60.0)
    flows = _frame(VN=-200.0, VS=200.0, NS=0.0)
    alloc = _frame(VN=1000.0, VS=5000.0, NS=0.0)
    out = net_trade(prices, flows, alloc)
    assert out.loop_NSWSA.iloc[0] == pytest.approx(6000.0)
    assert out.loop_NSWVIC.iloc[0] == 0 and out.loop_VICSA.iloc[0] == 0
    assert out.sq_NSWVIC.iloc[0] == pytest.approx(1000.0) and out.sq_VICSA.iloc[0] == pytest.approx(5000.0)
