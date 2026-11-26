"""Unit & accounting-invariant tests for Wave 3 (Forecasting Verdict, Clustering & PEC v2)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "reports/ic_forecasting_and_pec_v2/evidence"


def test_wave3_evidence_files_exist():
    expected = [
        "pec_observed_configs.csv",
        "pec_southern_ring_coupling.csv",
        "pec_loop_settlement_bridge.csv",
        "pec_issue_time_forecast_scores.csv",
        "longrange_band_verdict.csv",
        "longrange_cell_decisions.csv",
        "clustering_vs_controls.csv",
        "clustering_stability_summary.csv",
        "model_stack_governance_register.csv",
        "headline_numbers.json",
    ]
    for name in expected:
        p = EV / name
        assert p.exists() and p.stat().st_size > 20, f"Missing or empty Wave 3 evidence: {name}"


def test_c10_loop_settlement_conservation():
    df = pd.read_csv(EV / "pec_loop_settlement_bridge.csv")
    assert len(df) == 4, "Expected 4 EnergyConnect loop capacity regimes"
    # AEMC ERC0386 invariant: sum of 6 directional loop payouts must equal positive net_loop_pos_m (within rounding)
    for _, r in df.iterrows():
        s6 = r["loop_VICNSW_m"] + r["loop_NSWVIC_m"] + r["loop_VICSA_m"] + r["loop_SAVIC_m"] + r["loop_NSWSA_m"] + r["loop_SANSW_m"]
        assert abs(s6 - r["loop_total_payout_m"]) < 1e-6
        assert r["loop_total_payout_m"] <= r["net_loop_pos_m"] + 1e-3
    # Higher PEC capacity must increase PEC arm share of loop payouts monotonically from 150 -> 350 -> 800 MW
    assert df.iloc[1]["pec_arm_share_of_loop_pct"] <= df.iloc[2]["pec_arm_share_of_loop_pct"] + 0.5
    assert df.iloc[2]["pec_arm_share_of_loop_pct"] <= df.iloc[3]["pec_arm_share_of_loop_pct"] + 0.5


def test_longrange_verdict_and_stack_separation():
    bm = pd.read_csv(EV / "longrange_band_verdict.csv")
    cr = pd.read_csv(EV / "longrange_cell_decisions.csv")
    reg = pd.read_csv(EV / "model_stack_governance_register.csv")
    assert len(bm) == 50, f"Expected 50 long-range bands, got {len(bm)}"
    assert len(cr) == 10, f"Expected 10 long-range cells, got {len(cr)}"
    assert (cr["decision"] == "retain_baseline").all(), "All 10 historical long-range cells retained baseline"
    stacks = set(reg["stack"])
    assert {"original", "experiments", "production"}.issubset(stacks), "All 3 repository stacks must stay distinct"


def test_pec_configs_sum_to_100_pct():
    cfg = pd.read_csv(EV / "pec_observed_configs.csv")
    assert abs(cfg["share_pct"].sum() - 100.0) < 0.05
    N = json.loads((EV / "headline_numbers.json").read_text(encoding="utf-8"))
    assert N["lr_retained_baseline"] == "10"
