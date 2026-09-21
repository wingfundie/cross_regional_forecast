import importlib.util
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "all_ic_report", ROOT / "scripts" / "build_all_ic_regime_report.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_australian_season_blocks_cross_year_correctly():
    time = pd.Series(pd.to_datetime(["2023-12-01", "2024-01-01", "2024-02-29", "2024-03-01"]))
    assert MODULE.australian_season(time).tolist() == ["Summer", "Summer", "Summer", "Autumn"]
    assert MODULE.season_block(time).tolist() == [
        "Summer 2023–24", "Summer 2023–24", "Summer 2023–24", "Autumn 2024"]


def test_calendar_quarter_completeness_excludes_boundary_fragments():
    time = pd.Series(pd.to_datetime(["2023-09-30", "2023-10-01", "2026-06-30", "2026-07-01"]))
    complete = MODULE.complete_calendar_quarter(
        time, pd.Timestamp("2023-09-01"), pd.Timestamp("2026-08-31 23:55"))
    assert complete.tolist() == [False, True, True, False]


def test_daily_periods_cover_the_full_day_without_gaps():
    time = pd.Series(pd.to_datetime([
        "2026-01-01 02:00", "2026-01-01 07:00", "2026-01-01 12:00",
        "2026-01-01 18:00", "2026-01-01 22:00"]))
    assert MODULE.daily_period(time).tolist() == [
        "Overnight", "Morning peak", "Solar period", "Evening peak", "Overnight"]


def test_seasonal_limit_summaries_keep_pooled_and_exact_blocks():
    panel = pd.DataFrame({
        "time": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-07-01", "2025-07-02"]),
        "ic": ["NSW1-QLD1"] * 4,
        "name": ["QNI"] * 4,
        "direction": ["forward"] * 4,
        "direction_label": ["NSW → QLD"] * 4,
        "season": ["Summer", "Summer", "Winter", "Winter"],
        "season_block": ["Summer 2024–25", "Summer 2024–25", "Winter 2025", "Winter 2025"],
        "directional_flow": [10.0, 20.0, 30.0, 40.0],
        "capacity": [100.0, 200.0, 300.0, 400.0],
        "headroom": [90.0, 180.0, 270.0, 360.0],
        "restricted": [True, False, False, False],
        "forced_direction": [False, False, False, False],
    })
    pooled, blocks = MODULE.seasonal_limit_summaries(panel)
    assert set(pooled.season) == {"Summer", "Winter"}
    assert set(blocks.season_block) == {"Summer 2024–25", "Winter 2025"}
    summer = pooled[pooled.season.eq("Summer")].iloc[0]
    assert summer.capacity_median == 150.0
    assert summer.capacity_p10 == 110.0
    assert summer.capacity_p90 == 190.0
    assert summer.restricted_rate == 0.5


def test_report_is_observational_not_modelled():
    source = (ROOT / "scripts" / "build_all_ic_regime_report.py").read_text(encoding="utf-8")
    assert "regime_scatter_sample.csv.gz" in source
    assert "HistGradientBoosting" not in source
    assert "adjusted_effects.csv" not in source


def test_enso_uses_five_overlapping_season_episode_rule():
    panel = pd.DataFrame({
        "time": pd.to_datetime(["2023-09-15", "2024-05-15", "2025-11-15", "2026-07-15"]),
        "ic": ["NSW1-QLD1"] * 4,
        "name": ["QNI"] * 4,
        "direction": ["forward"] * 4,
        "direction_label": ["NSW → QLD"] * 4,
        "directional_flow": [1.0] * 4,
        "capacity": [2.0] * 4,
        "headroom": [1.0] * 4,
        "restricted": [False] * 4,
        "forced_direction": [False] * 4,
    })
    monthly, summary = MODULE.enso_tables(panel)
    states = monthly.set_index("center_month").enso_state
    assert states.loc[pd.Timestamp("2023-09-01")] == "El Niño"
    assert states.loc[pd.Timestamp("2025-11-01")] == "Neutral"
    assert states.loc[pd.Timestamp("2026-07-01")] == "Neutral"
    assert set(summary.enso_state) == {"El Niño", "Neutral"}


def test_all_six_constraint_adapters_declared():
    assert set(MODULE.CONSTRAINT_DIRS) == {
        "NSW1-QLD1", "N-Q-MNSP1", "VIC1-NSW1", "V-SA", "V-S-MNSP1", "T-V-MNSP1"}
