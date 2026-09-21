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


def test_report_is_observational_not_modelled():
    source = (ROOT / "scripts" / "build_all_ic_regime_report.py").read_text(encoding="utf-8")
    assert "regime_scatter_sample.csv.gz" in source
    assert "HistGradientBoosting" not in source
    assert "adjusted_effects.csv" not in source


def test_all_six_constraint_adapters_declared():
    assert set(MODULE.CONSTRAINT_DIRS) == {
        "NSW1-QLD1", "N-Q-MNSP1", "VIC1-NSW1", "V-SA", "V-S-MNSP1", "T-V-MNSP1"}
