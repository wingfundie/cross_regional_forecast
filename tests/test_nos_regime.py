import json

import numpy as np
import pandas as pd
import pytest

from nemic.experiments.nos_regime import compare, keys, lookup, state
from nemic.experiments.nos_regime.state import GRID30


def test_norm_strips_voltage_and_station_words():
    assert keys.norm("Wetherill Park 132kV") == "wetherill park"
    assert keys.norm("Wetherill Park Transmission Station") == "wetherill park"
    assert keys.norm("Braemar Power Station (H47)") == "braemar"


def test_area_label_uses_octant_and_distance():
    label, area, region, d = keys.nearest_place(-33.60, 150.90)   # north-west of Sydney
    assert region == "NSW1" and "Sydney" in label and "north" in label
    label, area, *_ = keys.nearest_place(-33.87, 151.21)
    assert label == "central Sydney" and area == "NSW1:Sydney"


def test_merge_and_cover_inclusive_interval_endings():
    t0 = pd.Timestamp("2025-01-01 00:05")
    spells = pd.DataFrame({"GENCONSETID": ["A", "A", "A"],
                           "start": [t0, t0 + pd.Timedelta("10min"), t0 + pd.Timedelta("2h")],
                           "end": [t0 + pd.Timedelta("5min"), t0 + pd.Timedelta("30min"), t0 + pd.Timedelta("2h")]})
    merged = state.merge_spells(spells)
    assert len(merged) == 2                                    # first two are adjacent -> merged
    times = pd.date_range(t0, periods=30, freq="5min").to_numpy()
    cov = state.covered(merged.reset_index(drop=True), times)
    assert cov[:7].all() and not cov[7] and cov[24]          # 00:05..00:35 inclusive, then 02:05


def test_boot_ci_is_deterministic_and_brackets_median():
    rng = np.random.default_rng(0)
    diffs = rng.normal(-50, 20, 400)
    days = np.repeat(np.arange(40), 10)
    a = compare.boot_ci(diffs, days)
    b = compare.boot_ci(diffs, days)
    assert a == b and a[0] < np.median(diffs) < a[1]


@pytest.mark.parametrize("row,expected", [
    ({"episodes": 6, "treated_hours": 30, "match_rate": .8, "placebo_clean": True}, "supported"),
    ({"episodes": 6, "treated_hours": 30, "match_rate": .8, "placebo_clean": np.nan}, "unsupported"),
    ({"episodes": 6, "treated_hours": 10, "match_rate": .8, "placebo_clean": True}, "indicative"),
    ({"episodes": 3, "treated_hours": 5, "match_rate": .2, "placebo_clean": False, "n_matched": 1}, "indicative"),
    ({"episodes": 2, "treated_hours": 50, "match_rate": .9, "placebo_clean": True}, "unsupported"),
])
def test_tier_rules(row, expected):
    assert compare.tier(row) == expected


def test_backoff_prefers_most_specific_supported_level():
    effects = pd.DataFrame([
        {"ic": "X", "direction": "forward", "level": "K3", "key": "SUB", "tier": "supported", "effect_capacity": -10},
        {"ic": "X", "direction": "forward", "level": "K2", "key": "F1", "tier": "supported", "effect_capacity": -80},
        {"ic": "X", "direction": "forward", "level": "K1", "key": "SUB/LINE/1", "tier": "indicative", "effect_capacity": -99},
    ])
    row = {"ic": "X", "direction": "forward", "asset": "SUB/LINE/1", "substation": "SUB", "area_key": "A", "families": {"F1"}}
    best = lookup.backoff(row, effects)
    assert best["published_level"] == "K2" and best["key"] == "F1"
    effects.loc[2, "tier"] = "supported"
    assert lookup.backoff(row, effects)["published_level"] == "K1"
    assert lookup.backoff({**row, "families": set(), "substation": "none"}, effects.iloc[[0]]) is None


def _toy_context(n_days=60):
    """Minimal Context with one connector direction and two families on the real GRID30 grid."""
    ctx = object.__new__(compare.Context)
    T = len(GRID30)
    ctx.ic, ctx.families = "X", ["F", "G"]
    ctx.fidx = {"F": 0, "G": 1}
    full = np.zeros((T, 2), bool)
    full[1000:1100, 0] = True          # F invoked
    full[5000:5100, 1] = True
    ctx.full = full
    ctx.w = np.array([11, 13], dtype=np.uint64)
    ctx.sig = (full.astype(np.uint64) * ctx.w).sum(axis=1, dtype=np.uint64)
    ctx.count = full.sum(axis=1)
    hh = (np.arange(T) + 1) % 48
    p = pd.DataFrame(index=GRID30)
    p["capacity"] = np.where(full[:, 0], 400.0, 500.0) + (hh % 3)
    for m in compare.METRICS:
        if m != "capacity":
            p[m] = 0.0
    p["complete"] = True
    p["key"] = 1; p["ckey"] = 1; p["hh"] = hh
    p["half_hour"] = hh; p["season"] = "Summer"; p["day_period"] = "Overnight"
    for c in ["tbin", "vbin", "rbin"]:
        p[c] = 1
    for c in ["temperature_mean", "vre_difference", "residual_difference"]:
        p[c] = 1.0
    p["season_reference"] = 500.0
    p["nem_date"] = GRID30.normalize()
    p["study_year"] = 1
    ctx.dirs = {"forward": {"p": p, "lead": np.zeros((T, 2), bool), "lead_count": np.zeros(T, int)}}
    ctx.t_ns = GRID30.asi8
    return ctx, full


def test_matching_is_deterministic_and_recovers_known_effect():
    ctx, full = _toy_context()
    off = ~full[:, 0]
    u1 = ctx.match("forward", full[:, 0], ["F"], off)
    u2 = ctx.match("forward", full[:, 0], ["F"], off)
    pd.testing.assert_frame_equal(u1.drop(columns=[]), u2)
    s = compare.summarize(u1)
    assert s["match_rate"] == 1.0
    assert abs(s["effect_capacity"] + 100) <= 2          # built-in -100 MW effect (± half-hour jitter)


def test_placebo_on_toy_context_is_clean():
    ctx, full = _toy_context()
    units, s = compare.run_effect(ctx, "forward", full[:, 0], ["F"], ~full[:, 0])
    assert s["placebo_clean"] and abs(s["placebo_effect_capacity"]) <= 2


def test_log_helper_refuses_double_start(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("nos_log", "scripts/nos_regime_log.py")
    log = importlib.util.module_from_spec(spec); spec.loader.exec_module(log)
    monkeypatch.setattr(log, "JSONL", tmp_path / "x.jsonl"); monkeypatch.setattr(log, "MARKDOWN", tmp_path / "x.md")
    assert log.main(["start", "--stage", "S", "--command", "c"]) == 0
    assert log.main(["start", "--stage", "S", "--command", "c"]) == 2
    assert log.main(["finish", "E001", "--status", "completed"]) == 0
    assert log.main(["check", "--stage", "S", "--note", "n"]) == 0
    events = [json.loads(x) for x in (tmp_path / "x.jsonl").read_text().splitlines()]
    assert [e["kind"] for e in events] == ["start", "finish", "check"]
