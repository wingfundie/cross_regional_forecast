"""Unit and algebraic invariant tests for Wave 1 (C1-C6 & Compressed Event Atlases v2)."""
from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nemic.experiments import constraint_pressure_v2 as cp2
from nemic.experiments import event_atlas_v2 as ea2

ROOT = Path(__file__).resolve().parents[1]
EV1 = ROOT / "reports/constraint_pressure_atlas_v2/evidence"
EA_DIR = ROOT / "reports/event_atlases_v2"


def test_duid_technology_classifier_separates_bess_and_hydro():
    assert cp2.classify_duid("VBB1", {}) == "BESS"
    assert cp2.classify_duid("KESSB1", {}) == "BESS"
    assert cp2.classify_duid("BLYTHB1", {}) == "BESS"
    assert cp2.classify_duid("LDBESS1", {}) == "BESS"
    assert cp2.classify_duid("TUMUT3", {}) == "Hydro"
    assert cp2.classify_duid("MURRAY", {}) == "Hydro"
    assert cp2.classify_duid("LIMOSF11", {}) == "Solar"
    assert cp2.classify_duid("MUWAWF1", {}) == "Wind"
    assert cp2.classify_duid("BW01", {}) == "Coal"


def test_columnar_gzip_roundtrip_preserves_event_bundles():
    sample = [
        {
            "event": {"event_id": "VNI-upper-test", "drop_mw": 412.3456, "unresolved_mw": -1e-12},
            "series": [{"time": "2025-01-01T00:05:00", "flow": 500.123, "export": 700.0}],
            "units": [{"time": "2025-01-01T00:05:00", "DUID": "TUMUT3", "TOTALCLEARED": 350.0}],
            "constraints": [],
            "rankings": [{"DUID": "TUMUT3", "net_tightening_mw": 120.456}],
            "equations": [],
            "sets": [],
            "invocations": [],
            "coal": [],
            "weather": [],
            "rooftop": [],
            "conditions": [],
            "external": None,
        }
    ]
    b64 = ea2.compress_bundles(sample)
    decoded = json.loads(gzip.decompress(base64.b64decode(b64)).decode("utf-8"))
    assert len(decoded) == 1
    assert decoded[0]["e"]["event_id"] == "VNI-upper-test"
    assert decoded[0]["e"]["drop_mw"] == 412.35
    assert decoded[0]["e"]["unresolved_mw"] == 0.0
    assert decoded[0]["s"]["c"] == ["time", "flow", "export"]
    assert decoded[0]["s"]["r"][0][1] == 500.12


@pytest.mark.skipif(not (EV1 / "six_link_parity_summary.csv").exists(), reason="Wave 1 evidence not built yet")
def test_wave1_six_link_parity_and_invariants():
    parity = pd.read_csv(EV1 / "six_link_parity_summary.csv")
    assert set(parity["link"]) == {"VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"}
    assert len(parity) == 12
    assert (parity["intervals"] > 200_000).all()

    lhs = pd.read_csv(EV1 / "contraction_lhs_rhs_switch.csv")
    assert len(lhs) == 12
    # Switch + LHS + RHS shares sum cleanly to 100%
    tot_share = lhs["switch_drop_share_pct"] + lhs["lhs_gen_drop_share_pct"] + lhs["rhs_z_drop_share_pct"]
    assert np.allclose(tot_share, 100.0, atol=0.25)

    casc = pd.read_csv(EV1 / "cross_link_cascades.csv")
    assert len(casc) == 36
    assert ((casc["cond_prob_pct"] >= 0.0) & (casc["cond_prob_pct"] <= 100.0)).all()
    diag = casc[casc["source_link"] == casc["target_link"]]
    assert np.allclose(diag["cond_prob_pct"], 100.0)

    duid = pd.read_csv(EV1 / "duid_economic_influence.csv")
    assert set(duid["link"]) == {"VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"}
    assert (duid["tight_abs_mw_obs"] <= duid["all_abs_mw_obs"] + 1e-3).all()


@pytest.mark.skipif(not (EA_DIR / "event_atlases_manifest.json").exists(), reason="Event Atlases v2 not built yet")
def test_compressed_event_atlases_shrink_by_more_than_half():
    mf = json.loads((EA_DIR / "event_atlases_manifest.json").read_text(encoding="utf-8"))
    assert len(mf["atlases"]) == 3
    for a in mf["atlases"]:
        assert a["new_mb"] < 8.0
        assert a["reduction_pct"] > 55.0
        md_txt = (EA_DIR / a["md"]).read_text(encoding="utf-8")
        assert "\u2014" not in md_txt
        assert "e-14" not in md_txt
        assert "net_mw" not in md_txt
