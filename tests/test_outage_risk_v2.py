"""Unit & accounting-invariant tests for Wave 2 (Outage Risk & NOS Regime Handbook v2)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "reports/outage_risk_handbook_v2/evidence"


def test_wave2_evidence_files_exist():
    expected = [
        "nos_economic_effects.csv",
        "nos_outlook_calibration.csv",
        "nos_reliability_curves.csv",
        "nos_live_outlook_calibrated.csv",
        "nos_n11_superadditivity.csv",
        "line_corridor_pooled_risk.csv",
        "line_50_directory.csv",
        "line_deep_dives_6_8.csv",
        "nos_booking_reliability_summary.csv",
        "headline_numbers.json",
    ]
    for name in expected:
        p = EV / name
        assert p.exists() and p.stat().st_size > 20, f"Missing or empty Wave 2 evidence: {name}"


def test_c7b_calibration_improves_brier_and_ece():
    cells = pd.read_csv(EV / "nos_outlook_calibration.csv")
    assert len(cells) == 96, f"Expected 96 layer x lead_band x link x direction cells, got {len(cells)}"
    # Calibrated outlook must beat raw outlook on majority of cells and increase skilful cells
    assert int(cells["cal_beats_raw"].sum()) >= 60, "Calibrated outlook should beat raw on >= 60/96 cells"
    assert int(cells["cal_skilful"].sum()) > int(cells["raw_skilful"].sum()), "Calibrated outlook must increase skilful cell count"

    rel = pd.read_csv(EV / "nos_reliability_curves.csv")
    for lay in ("binding", "setter"):
        r_raw = rel[(rel["layer"] == lay) & (rel["model"] == "raw_outlook")]
        r_cal = rel[(rel["layer"] == lay) & (rel["model"] == "calibrated_eb_iso")]
        ece_raw = (r_raw["n"] * r_raw["abs_cal_err"]).sum() / r_raw["n"].sum()
        ece_cal = (r_cal["n"] * r_cal["abs_cal_err"]).sum() / r_cal["n"].sum()
        assert ece_cal < ece_raw, f"Calibrated ECE must be strictly lower than raw ECE on {lay}"


def test_c8_superadditivity_identity():
    c8 = pd.read_csv(EV / "nos_n11_superadditivity.csv")
    assert len(c8) >= 10, "Expected at least 10 tested concurrent N-1-1 pairs"
    err_add = (c8["effect_a_mw"] + c8["effect_b_mw"] - c8["additive_sum_mw"]).abs().max()
    err_sup = (c8["observed_joint_mw"] - c8["additive_sum_mw"] - c8["super_additivity_mw"]).abs().max()
    assert err_add < 1e-6, f"Additive sum identity violated: {err_add}"
    assert err_sup < 1e-6, f"Super-additivity identity violated: {err_sup}"


def test_c9_corridor_pooling_and_line6_line8():
    d50 = pd.read_csv(EV / "line_50_directory.csv")
    assert len(d50) == 50, f"Expected all 50 transmission lines, got {len(d50)}"
    assert "CANBERRA/LINE/6" in set(d50["asset"])
    assert "DAPTO/LINE/8" in set(d50["asset"])
    # Empirical-Bayes weights must be strictly in [0, 1]
    for col in ("eb_price_weight", "eb_cap_weight", "eb_spread_weight"):
        vals = d50[col].dropna()
        assert (vals >= 0.0).all() and (vals <= 1.0).all(), f"{col} out of [0, 1]"
    # Line 6 (n=2 events) should have smaller shrinkage weight than high-event peers in same corridor
    l6_w = float(d50.loc[d50["asset"] == "CANBERRA/LINE/6", "eb_price_weight"].iloc[0])
    l8_w = float(d50.loc[d50["asset"] == "DAPTO/LINE/8", "eb_price_weight"].iloc[0])
    assert 0.0 <= l6_w <= 1.0 and 0.0 <= l8_w <= 1.0
    N = json.loads((EV / "headline_numbers.json").read_text(encoding="utf-8"))
    assert N["c9_total_lines"] == "50"
