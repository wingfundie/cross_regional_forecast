import numpy as np
import pandas as pd
import pytest

from nemic.experiments.clustering.state import (
    StateClusterer,
    assess_stability,
    support_summary,
)


def _states(rows=480):
    rng = np.random.default_rng(19)
    index = pd.date_range("2025-01-01", periods=rows, freq="h")
    regime = (np.arange(rows) % 48 >= 24).astype(float)
    room = regime * 8.0 + rng.normal(0, 0.35, rows)
    pressure = regime * -5.0 + rng.normal(0, 0.25, rows)
    sparse = np.full(rows, np.nan)
    sparse[: max(1, rows // 10)] = rng.normal(size=max(1, rows // 10))
    return pd.DataFrame(
        {
            "room": room,
            "room_copy": room,
            "flow_change": rng.normal(0, 1.0, rows),
            "pressure": pressure,
            "constant": 3.0,
            "sparse": sparse,
        },
        index=index,
    )


GROUPS = {
    "network": ["room", "room_copy", "flow_change", "constant"],
    "constraint": ["pressure", "sparse"],
}


def test_kmeans_preprocessing_is_train_only_group_balanced_and_schema_safe():
    train = _states()
    model = StateClusterer(
        n_clusters=2,
        method="kmeans",
        feature_groups=GROUPS,
        random_state=741,
    ).fit(train)

    assert model.dropped_features_["constant"]["reason"] == "constant"
    assert model.dropped_features_["sparse"]["reason"] == "too_missing"
    assert model.dropped_features_["room_copy"] == {
        "reason": "near_duplicate",
        "representative": "room",
    }
    assert model.group_weights_["network"] == pytest.approx(1 / np.sqrt(2))
    assert model.group_weights_["constraint"] == pytest.approx(1.0)

    expected = model.transform(train)
    reordered = train[["pressure", "constant", "room_copy", "flow_change", "room"]].copy()
    reordered["irrelevant_extra"] = 99.0
    actual = model.transform(reordered)
    np.testing.assert_array_equal(actual.labels, expected.labels)
    np.testing.assert_allclose(actual.probabilities, expected.probabilities)

    threshold = model.ood_threshold_
    centre = model.cluster_centers_.copy()
    evaluation = train.iloc[:2].copy()
    evaluation.loc[:, ["room", "room_copy", "pressure"]] = 1e12
    result = model.transform(evaluation)
    assert result.out_of_distribution.all()
    assert model.ood_threshold_ == threshold
    np.testing.assert_array_equal(model.cluster_centers_, centre)

    with pytest.raises(ValueError, match="missing fitted"):
        model.transform(train.drop(columns="pressure"))
    with pytest.raises(ValueError, match="maximum_missing_fraction"):
        StateClusterer(n_clusters=2, maximum_missing_fraction=1.0)


def test_gmm_probabilities_distances_and_augmentation_are_aligned():
    train = _states()
    model = StateClusterer(
        n_clusters=2,
        method="gmm",
        feature_groups=GROUPS,
        random_state=742,
    ).fit(train)
    result = model.transform(train)

    np.testing.assert_allclose(result.probabilities.sum(axis=1), 1.0)
    assert (result.distance >= 0).all()
    assert result.labels.index.equals(train.index)
    augmented = model.augment(train, include_label=True)
    expected = {
        "state_cluster__label",
        "state_cluster__probability_0",
        "state_cluster__probability_1",
        "state_cluster__distance",
        "state_cluster__ood",
    }
    assert expected.issubset(augmented.columns)
    assert augmented.index.equals(train.index)


def test_one_cluster_control_and_support_include_all_days():
    train = _states(240)
    model = StateClusterer(
        n_clusters=1,
        method="gmm",
        feature_groups=GROUPS,
    ).fit(train)
    result = model.transform(train)

    assert model.model_ is None
    assert (result.labels == 0).all()
    assert (result.probabilities.iloc[:, 0] == 1.0).all()
    summary = support_summary(result)
    assert summary.loc[0, "rows"] == len(train)
    assert summary.loc[0, "unique_days"] == train.index.normalize().nunique()
    assert summary.loc[0, "ood_fraction"] <= 0.01


def test_seed_and_day_block_stability_are_reproducible():
    train = _states(720)
    first = assess_stability(
        train,
        n_clusters=2,
        method="kmeans",
        feature_groups=GROUPS,
        seeds=(741, 742, 743),
        block_days=2,
    )
    second = assess_stability(
        train,
        n_clusters=2,
        method="kmeans",
        feature_groups=GROUPS,
        seeds=(741, 742, 743),
        block_days=2,
    )

    pd.testing.assert_frame_equal(first.seed_scores, second.seed_scores)
    pd.testing.assert_frame_equal(first.block_scores, second.block_scores)
    assert first.seed_mean_ari > 0.95
    assert first.block_mean_ari > 0.90
