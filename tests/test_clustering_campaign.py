import numpy as np
import pandas as pd

from nemic.experiments.clustering import generator_campaign
from nemic.experiments.clustering.campaign import _folds
from nemic.experiments.clustering.config import load_config
from nemic.experiments.clustering.data import equal_origin_training_rows, unique_origin_rows
from nemic.experiments.clustering.models import (
    LocalExpertModel,
    ResidualIntervals,
    append_cluster_interactions,
    select_correction_model,
)


def test_clustering_config_freezes_connector_order_and_horizon():
    config = load_config()
    assert [item["name"] for item in config["connectors"]] == ["VNI", "QNI"]
    assert config["targets"] == ["flow", "export_tight", "import_tight"]
    assert max(config["leads"]) == 336
    assert not config["claims"]["operationally_eligible"]


def test_origin_state_collapse_rejects_lead_dependent_state():
    frame = pd.DataFrame({
        "origin": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02"]),
        "lead": [1, 2, 1],
        "room": [4.0, 4.0, 5.0],
    })
    collapsed = unique_origin_rows(frame, ["room"])
    assert len(collapsed) == 2
    changed = frame.copy()
    changed.loc[1, "room"] = 99
    try:
        unique_origin_rows(changed, ["room"])
    except ValueError as exc:
        assert "vary across leads" in str(exc)
    else:
        raise AssertionError("lead-dependent origin state was accepted")


def test_equal_origin_training_sample_is_deterministic_and_balanced():
    frame = pd.DataFrame({
        "origin": np.repeat(pd.date_range("2025-01-01", periods=10, freq="30min"), 3),
        "lead": np.tile([1, 2, 4], 10),
        "x": np.arange(30),
    })
    first = equal_origin_training_rows(frame, 741)
    second = equal_origin_training_rows(frame, 741)
    pd.testing.assert_frame_equal(first, second)
    assert len(first) == frame.origin.nunique()
    assert first.groupby("origin").size().eq(1).all()


def test_cluster_models_do_not_refit_preprocessing_on_evaluation():
    rng = np.random.default_rng(31)
    train_x = pd.DataFrame({"x": rng.normal(size=500), "z": rng.normal(size=500)})
    select_x = pd.DataFrame({"x": rng.normal(size=150), "z": rng.normal(size=150)})
    train_anchor = np.zeros(500)
    select_anchor = np.zeros(150)
    train_y = 3 * train_x.x.to_numpy() + rng.normal(scale=0.1, size=500)
    select_y = 3 * select_x.x.to_numpy() + rng.normal(scale=0.1, size=150)
    config = load_config()
    model, _ = select_correction_model(
        "ridge", train_x, train_y, train_anchor, select_x, select_y, select_anchor,
        config, seed=741,
    )
    before = model.transform.scaler.mean_.copy()
    model.predict(pd.DataFrame({"x": [1e12], "z": [-1e12]}), [0])
    np.testing.assert_array_equal(before, model.transform.scaler.mean_)


def test_cluster_interactions_local_fallback_and_intervals():
    frame = pd.DataFrame({"x": np.arange(600, dtype=float), "room": np.linspace(-1, 1, 600)})
    probabilities = np.column_stack([np.arange(600) < 300, np.arange(600) >= 300]).astype(float)
    augmented = append_cluster_interactions(frame, probabilities, ["room"])
    assert {"cluster_0__x__room", "cluster_1__x__room"}.issubset(augmented.columns)

    actual = frame.x.to_numpy() + np.where(np.arange(600) < 300, -2.0, 2.0)
    anchor = frame.x.to_numpy()
    labels = probabilities.argmax(axis=1)
    local = LocalExpertModel(alpha=10, shrinkage=1, minimum_rows=200).fit(frame, actual, anchor, labels)
    pooled = local.pooled.predict(frame, anchor)
    prediction = local.predict(frame, anchor, labels, ood=np.ones(600, dtype=bool))
    np.testing.assert_allclose(prediction, pooled)

    intervals = ResidualIntervals.fit(actual, anchor, [0.025, 0.5, 0.975])
    predicted = intervals.predict(anchor[:5])
    assert predicted.shape == (5, 3)
    assert np.all(np.diff(predicted, axis=1) >= 0)


def test_generator_ablation_uses_strongest_matched_model_family(monkeypatch):
    config = load_config()
    origins = pd.date_range("2025-08-01 00:30", "2025-12-08 23:30", freq="30min")
    source = pd.DataFrame({
        "origin": origins,
        "delivery": origins + pd.Timedelta(minutes=30),
        "lead": 1,
        "actual_flow": 1.0,
        "anchor_flow": 0.0,
        "x": np.linspace(0, 1, len(origins)),
    })
    fold = _folds(config, source)[0]
    generator_features = {
        "manual": pd.DataFrame({"origin": origins, "manual__group": 1.0})
    }

    class FakeModel:
        def __init__(self, correction):
            self.correction = correction

        def predict(self, frame, anchor):
            return np.asarray(anchor, dtype=float) + self.correction

    def fake_select(family, *args, **kwargs):
        correction = 1.0 if family == "boost" else 0.25
        return FakeModel(correction), [{"settings": {"family": family}, "selection_mae": 0.0}]

    monkeypatch.setattr(
        generator_campaign,
        "feature_contract",
        lambda *_: {"network_model": ["x"]},
    )
    monkeypatch.setattr(generator_campaign, "select_correction_model", fake_select)
    result = generator_campaign._evaluate_ablation(
        config, "VNI", fold, source, generator_features, pilot_mode=True
    )[0]
    assert result["status"] == "complete"
    assert result["winner"]["family"] == "boost"
    assert result["control"]["family"] == "boost"
    assert result["control_score"]["mae"] == 0
