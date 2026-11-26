"""Unit and regression tests for interregional valuation v3 analytics and report integrity."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nemic.valuation.config import ROOT

V3_REPORT = ROOT / 'reports/interregional_valuation_research_v3'
V3_EV = V3_REPORT / 'evidence'


def _skip_if_no_v3_evidence(filename: str) -> Path:
    p = V3_EV / filename
    if not p.exists():
        pytest.skip(f'v3 evidence not yet generated: {filename}')
    return p


def test_sra_payoff_state_attribution_closes_exactly():
    df = pd.read_csv(_skip_if_no_v3_evidence('sra_payoff_decomposition.csv'))
    parts = (
        df.state_coupled_loss_per_unit
        + df.state_energy_congestion_per_unit
        + df.state_scarcity_total_per_unit
    )
    assert np.allclose(parts, df.settled_per_unit, atol=1e-4)
    scarc = (
        df.state_scarcity_dest_only_per_unit
        + df.state_scarcity_orig_only_per_unit
        + df.state_scarcity_both_per_unit
    )
    assert np.allclose(scarc, df.state_scarcity_total_per_unit, atol=1e-4)
    fixed_parts = df.fixed_flow_clipped_energy_per_unit + df.fixed_flow_scarcity_increment_per_unit
    assert np.allclose(fixed_parts, df.metered_actual_per_unit, atol=1e-4)


def test_loop_three_way_waterfall_closes_exactly():
    df = pd.read_csv(_skip_if_no_v3_evidence('loop_attribution_waterfall.csv'))
    recon = (
        df.status_quo
        + df.neg_netting_delta
        + df.passthrough_reallocation_delta
        + df.secondary_netting_delta
    )
    assert np.allclose(recon, df.loop_rule, atol=1e-2)
    assert np.allclose(df.loop_rule - df.status_quo, df.total_delta, atol=1e-2)


def test_auction_ex2022_subset_strictly_smaller_than_full():
    df = pd.read_csv(_skip_if_no_v3_evidence('auction_regime_sensitivity.csv'))
    full = df[(df.regime == 'full_19q') & (df.direction == 'all') & (df.horizon == 'all')].iloc[0]
    ex22 = df[(df.regime == 'ex_2022_crisis') & (df.direction == 'all') & (df.horizon == 'all')].iloc[0]
    assert full.delivery_quarters == 19
    assert ex22.delivery_quarters == 17
    assert ex22.tranches < full.tranches


def test_bid_stack_slippage_is_monotone_in_order_size():
    df = pd.read_csv(_skip_if_no_v3_evidence('bid_stack_slippage.csv'))
    for (cid, d), g in df.groupby(['contract_id', 'direction']):
        g = g.sort_values('order_units')
        diffs = np.diff(g.price_impact_dollars.values)
        assert np.all(diffs >= -1e-6), f'Non-monotone slippage for {cid} {d}: {g.price_impact_dollars.tolist()}'


def test_mpc_cpt_truncation_never_exceeds_linear_mpc_on_dest_spikes():
    df = pd.read_csv(_skip_if_no_v3_evidence('mpc_cpt_normalised.csv'))
    assert set(df.basis.unique()) == {'raw', 'linear_mpc_only', 'mpc_with_cpt_cap'}
    assert (df.target_cpt > 0).all()


def test_option_benchmark_v3_has_ex_ante_and_peek_columns():
    df = pd.read_csv(_skip_if_no_v3_evidence('option_benchmark_v3.csv')).dropna()
    assert len(df) >= 60
    assert (df.ex_ante_option_per_unit >= 0).all()
    assert {'ex_ante_option_per_unit', 'v2_realised_regime_option_per_unit', 'realised_per_unit'} <= set(df.columns)


def test_v3_headline_numbers_and_manifest_if_built():
    hl_path = V3_EV / 'headline_numbers.json'
    if not hl_path.exists():
        pytest.skip('v3 headline numbers not built')
    numbers = json.loads(hl_path.read_text(encoding='utf-8'))
    assert len(numbers) >= 350
    md_path = V3_REPORT / 'research_report.md'
    if md_path.exists():
        md = md_path.read_text(encoding='utf-8')
        assert not re.findall(r'\{\{[a-zA-Z0-9_:]+\}\}', md)
