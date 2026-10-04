import numpy as np
import pandas as pd
import pytest

from nemic.experiments.clustering.protocol import (
    CHECKPOINT_LEADS,
    ProtocolConfig,
    expanding_folds,
    holm_adjust,
    interval_metrics,
    lead_band,
    limited_support_flags,
    moving_block_indices,
    one_row_per_origin,
    origin_balanced_weights,
    paired_effect_intervals,
    partition_masks,
    recurring_regime_screen,
    regime_stability,
    regression_metrics,
)


def test_expanding_folds_have_frozen_disjoint_durations():
    folds = expanding_folds("2025-08-01", "2026-09-01")
    assert len(folds) == 10
    first, second = folds[:2]
    assert first.train_end - first.train_start == pd.Timedelta(days=60)
    assert first.select_end - first.train_end == pd.Timedelta(days=14)
    assert first.calibrate_end - first.select_end == pd.Timedelta(days=14)
    assert first.alert_end - first.calibrate_end == pd.Timedelta(days=14)
    assert first.evaluate_end - first.alert_end == pd.Timedelta(days=28)
    assert second.train_start == first.train_start
    assert second.train_end - first.train_end == pd.Timedelta(days=28)


def test_partition_masks_purge_delivery_maturity_at_boundary():
    fold = expanding_folds("2025-01-01", "2025-06-01")[0]
    boundary = fold.train_end
    origin = pd.DatetimeIndex([
        boundary - pd.Timedelta(hours=2),
        boundary - pd.Timedelta(hours=2),
        boundary,
    ])
    delivery = pd.DatetimeIndex([
        boundary - pd.Timedelta(minutes=31),
        boundary - pd.Timedelta(minutes=30),
        boundary + pd.Timedelta(minutes=30),
    ])
    masks = partition_masks(origin, delivery, fold)
    assert masks["train"].tolist() == [True, False, False]
    assert masks["select"].tolist() == [False, False, True]
    assert np.vstack(tuple(masks.values())).sum(axis=0).max() == 1


def test_origin_collapse_and_weights_do_not_overweight_repeated_leads():
    frame = pd.DataFrame({
        "origin": ["a", "a", "a", "b"],
        "state": [1, 1, 1, 2],
        "lead": [1, 2, 3, 1],
    })
    collapsed = one_row_per_origin(frame, constant_columns=["state"])
    assert collapsed.origin.tolist() == ["a", "b"]
    weights = origin_balanced_weights(frame.origin)
    np.testing.assert_allclose(weights, [1 / 3, 1 / 3, 1 / 3, 1])
    np.testing.assert_allclose(pd.Series(weights).groupby(frame.origin).sum(), [1, 1])
    with pytest.raises(ValueError):
        one_row_per_origin(frame.assign(state=[1, 2, 1, 2]), constant_columns=["state"])


def test_lead_bands_and_literal_checkpoints_end_at_168_hours():
    assert lead_band(1).name == "0.5-6h"
    assert lead_band(48).name == "6.5-24h"
    assert lead_band(144).name == "24.5-72h"
    assert lead_band(336).last_hours == 168
    assert CHECKPOINT_LEADS == {24: 48, 48: 96, 168: 336}
    with pytest.raises(ValueError):
        lead_band(337)


def test_regression_and_interval_metrics_are_matched_and_complete():
    point = regression_metrics([0, 1, 2, 3], [0, 2, 2, 5])
    assert point["mae"] == pytest.approx(0.75)
    assert point["rmse"] == pytest.approx(np.sqrt(1.25))
    assert point["bias"] == pytest.approx(0.75)
    assert point["positive_overstatement"] == pytest.approx(0.75)
    assert point["overstatement_100_rate"] == 0
    assert set(point) >= {"p90_absolute_error", "p95_absolute_error", "p99_absolute_error"}

    intervals = interval_metrics(
        actual=[0, 1], median=[0, 1],
        lower80=[-1, 0], upper80=[1, 2],
        lower95=[-2, -1], upper95=[2, 3],
    )
    assert intervals["coverage_80"] == 1
    assert intervals["coverage_95"] == 1
    assert intervals["width_80"] == 2
    assert intervals["width_95"] == 4
    assert intervals["wis"] == pytest.approx(0.12)
    with pytest.raises(ValueError):
        regression_metrics([1, np.nan], [1, 2])


def test_paired_bootstrap_is_origin_balanced_deterministic_and_positive():
    origins = pd.date_range("2025-01-01", periods=70, freq="D").repeat(2)
    actual = np.zeros(len(origins))
    control = np.full(len(origins), 2.0)
    challenger = np.tile([0.5, 1.5], 70)
    first = paired_effect_intervals(actual, challenger, control, origins, replicates=100)
    second = paired_effect_intervals(actual, challenger, control, origins, replicates=100)
    assert first == second
    assert first["7"]["effect_mae"] == pytest.approx(1.0)
    assert first["14"]["effect_percent"] == pytest.approx(50.0)
    assert first["7"]["origins"] == 70
    assert 0 <= first["7"]["p_value_two_sided"] <= 1


def test_moving_blocks_are_contiguous_and_holm_preserves_missing():
    sampled = moving_block_indices(28, 7, replicates=20)
    assert sampled.shape == (20, 28)
    for draw in sampled:
        for block in draw.reshape(-1, 7):
            assert np.all(np.diff(block) == 1)
    adjusted = holm_adjust([0.01, 0.04, np.nan, 0.03])
    np.testing.assert_allclose(adjusted[[0, 1, 3]], [0.03, 0.06, 0.06])
    assert np.isnan(adjusted[2])


def test_regime_and_result_support_screens_follow_declared_conventions():
    stability = regime_stability([[0, 0, 1, 1], [1, 1, 0, 0], [0, 0, 1, 1]])
    assert stability["median_ari"] == 1
    screen = recurring_regime_screen(stability["ari"], training_days=30, evaluation_days=14)
    assert screen["recurring"]
    assert not recurring_regime_screen([0.69], 30, 14)["recurring"]
    assert limited_support_flags(55, 30)["limited_support"]
    assert limited_support_flags(56, 29)["flags"]["incidents"]
    assert not limited_support_flags(pd.date_range("2025-01-01", periods=56), 30)["limited_support"]


def test_protocol_rejects_invalid_duration_configuration():
    mapped = ProtocolConfig.from_mapping({"step_days": 7, "maturity_minutes": 45})
    assert mapped.advance_days == 7
    assert mapped.maturity_delay_minutes == 45
    with pytest.raises(ValueError):
        ProtocolConfig(select_days=0)
