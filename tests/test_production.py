import json
import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from nemic.production.contracts import digest, write_json
from nemic.production.registry import Registry
from nemic.production.pipeline import forecast, hourly
from nemic.production.inputs import normalize, asof, scenario
from nemic.production.features import build
from nemic.production.training import folds
from nemic.production.constraints import candidates, equation_bound


def package(tmp_path, name="VNI", features=None, status="research", identity="test"):
    p = tmp_path / identity
    p.mkdir()
    features = features or ["lead"]
    model = DummyRegressor(strategy="constant", constant=-20).fit(pd.DataFrame([[1]*len(features)], columns=features), [-20])
    joblib.dump({"estimator": model, "adjustments": np.array([-10, -5, 0, 5, 10])}, p / "model.joblib")
    m = dict(id=identity, version="1", connectors=[name], target="export", lead_min=1, lead_max=48,
             resolution_minutes=30, adapter="sklearn", recipe="calendar-v1", features=features, status=status,
             artifacts={"model.joblib": digest(p / "model.joblib")}, training_cutoff=None, evaluation={}, dependencies={})
    write_json(p / "manifest.json", m)
    return p


def setup_registry(tmp_path, **kwargs):
    r = Registry(tmp_path / "registry")
    key = r.register(package(tmp_path, **kwargs))
    policy = {"version": "1", "routes": [dict(connector="VNI", target="export", lead_min=1, lead_max=48, models=[key])]}
    return r, key, policy


def test_route_status_horizons_and_negative_limits(tmp_path):
    r, key, policy = setup_registry(tmp_path)
    kwargs = dict(origin="2026-01-01T00:00:00+10:00", connectors=["VNI", "QNI"], days=2, targets=["export"])
    prod = forecast(r, policy, pd.DataFrame(), **kwargs)
    assert prod.status.eq("unavailable").all()
    research = forecast(r, policy, pd.DataFrame(), mode="research", **kwargs)
    assert research.status.eq("complete").sum() == 48
    assert research.loc[research.status == "complete", "forecast_mw"].eq(-20).all()
    assert research.loc[research.connector == "QNI", "reason"].eq("no route").all()
    assert hourly(research).interval_basis.str.contains("separate hourly").all()


def test_registry_immutable_hash_and_portable(tmp_path):
    r, key, policy = setup_registry(tmp_path)
    with pytest.raises(ValueError, match="already registered"):
        r.register(tmp_path / "test")
    r.export(key, tmp_path / "copy")
    other = Registry(tmp_path / "other")
    assert other.register(tmp_path / "copy") == key
    m, p = other.load(key)
    (p / "model.joblib").write_bytes(b"broken")
    with pytest.raises(ValueError, match="Hash mismatch"):
        other.load(key)


def test_cross_connector_and_overlap_rejected(tmp_path):
    r, key, policy = setup_registry(tmp_path)
    policy["routes"].append(dict(policy["routes"][0]))
    with pytest.raises(ValueError, match="Ambiguous"):
        r.validate_routes(policy)
    policy["routes"] = [dict(connector="QNI", target="export", lead_min=1, lead_max=48, models=[key])]
    with pytest.raises(ValueError, match="Cross-connector"):
        r.validate_routes(policy)


def test_validated_fallback(tmp_path):
    r, key, policy = setup_registry(tmp_path, features=["unavailable"], status="approved")
    fallback = r.register(package(tmp_path, identity="fallback", status="approved"))
    policy["routes"][0]["models"].append(fallback)
    out = forecast(r, policy, pd.DataFrame(), origin="2026-01-01T00:00:00+10:00", connectors=["VNI"], targets=["export"])
    assert out.selection.eq("fallback").all()
    assert out.reason.str.contains("Missing features").all()


def normalized():
    mapping = dict(columns={k:k for k in ("issue", "received", "delivery", "region", "variable", "value")},
                   timezone="Australia/Brisbane", interval_minutes=60, interval_label="end", units={"demand":"GW"}, source="test")
    frame = pd.DataFrame([dict(issue="2026-01-01 00:00", received="2026-01-01 00:05", delivery="2026-01-01 02:00", region="VIC1", variable="demand", value=5)])
    return normalize(frame, mapping), mapping, frame


def test_mapping_asof_and_scenarios():
    out, mapping, frame = normalized()
    assert out.value.iloc[0] == 5000
    assert asof(out, "2026-01-01T00:00:00+10:00", 24).empty
    assert len(asof(out, "2026-01-01T00:10:00+10:00", 24)) == 1
    with pytest.raises(ValueError, match="Duplicate"):
        normalize(pd.concat([frame, frame]), mapping)
    overrides = pd.DataFrame([dict(region="VIC1", variable="demand", delivery=out.delivery.iloc[0], value=6000)])
    changed = scenario(out, overrides, "higher-demand")
    assert changed.value.iloc[0] == 6000 and out.value.iloc[0] == 5000


def test_feature_contract_and_coarse_flag():
    out, _, _ = normalized()
    m = dict(recipe="regional-v1", features=["source_demand", "source_demand_coarse"], target="export")
    f = build(m, "2026-01-01T01:00:00+10:00", "2026-01-01T01:30:00+10:00", "VNI", out)
    assert f.source_demand.iloc[0] == 5000 and f.source_demand_coarse.iloc[0] == 1
    with pytest.raises(ValueError, match="Missing features"):
        build(m, "2026-01-01T02:00:00+10:00", "2026-01-01T02:30:00+10:00", "VNI", out)


def test_purged_splits():
    origins = pd.date_range("2026-01-01", periods=40, freq="D", tz="UTC")
    frame = pd.DataFrame(dict(origin=origins, delivery=origins + pd.Timedelta(days=2)))
    for train, test in folds(frame):
        assert frame.loc[train, "delivery"].max() < frame.loc[test, "origin"].min()


def test_outage_cancellation_and_missing_equation_inputs():
    origin = pd.Timestamp("2026-01-01", tz="UTC")
    outages = pd.DataFrame([dict(outage_id="a", equipment="line", issue=origin-pd.Timedelta(hours=2), received=origin-pd.Timedelta(hours=1), start=origin, end=origin+pd.Timedelta(days=1), status="planned"),
                           dict(outage_id="a", equipment="line", issue=origin, received=origin, start=origin, end=origin+pd.Timedelta(days=1), status="cancelled")])
    links = pd.DataFrame([dict(equipment="line", constraint_id="c", connector="VNI", effective_from=origin, effective_to=origin+pd.Timedelta(days=2), received=origin)])
    assert candidates(outages, links, origin, origin+pd.Timedelta(hours=1), "VNI").empty
    with pytest.raises(ValueError, match="missing"):
        equation_bound(100, {"VNI":1, "generator":2}, {}, "VNI")


def test_synthetic_end_to_end(tmp_path):
    from nemic.production.demo import run
    path = run(tmp_path / "demo")
    assert path.exists()
    result = pd.read_parquet(path.parent / "forecasts.parquet")
    assert result.status.eq("complete").sum() == 96
    assert result[result.connector == "Basslink"].status.eq("unavailable").all()


def test_hourly_calibration_is_separate_and_asof():
    from nemic.production.calibration import fit_hourly, apply_hourly
    delivery = pd.date_range("2025-01-01", periods=40, freq="h", tz="UTC")
    f = pd.DataFrame(dict(connector="VNI", target="export", actual=np.arange(40), forecast_mw=np.arange(40) - 5,
                         delivery=delivery, routing_version="r1"))
    calibration = fit_hourly(f, version="h1")
    out = pd.DataFrame([dict(connector="VNI", target="export", origin=pd.Timestamp("2025-02-01", tz="UTC"), status="complete", forecast_mw=100)])
    scored = apply_hourly(out, calibration, "r1")
    assert scored.p50_mw.iloc[0] == 105
    assert "p50_mw" not in apply_hourly(out, calibration, "wrong")


def test_constraint_ranker_oof_and_outage_effect_counts():
    from nemic.production.constraints import fit_setter_ranker, rank_effects
    origins = pd.date_range("2025-01-01", periods=40, freq="D", tz="UTC")
    frame = pd.DataFrame(dict(origin=origins, delivery=origins + pd.Timedelta(hours=1), pressure=np.arange(40) % 2, is_setter=np.arange(40) % 2))
    model, oof = fit_setter_ranker(frame, ["pressure"])
    assert oof.oof_probability.isna().sum() == 10
    assert oof.oof_probability.dropna().between(0, 1).all()
    effects = pd.DataFrame([dict(outage_id="a", event_id="one", connector="VNI", target="export", estimated_reduction_mw=100)]*100)
    summary = rank_effects(effects)
    assert summary["count"].iloc[0] == 1
    assert "exploratory" in summary.evidence.iloc[0]


def test_evaluation_preserves_missing_predictions():
    from nemic.production.evaluation import attach_actuals, scorecard
    origin = pd.Timestamp("2026-01-01", tz="UTC")
    f = pd.DataFrame([dict(connector="VNI", target="export", delivery=origin, lead=1, model="a", status="complete", forecast_mw=-10),
                      dict(connector="VNI", target="export", delivery=origin+pd.Timedelta(minutes=30), lead=2, model="a", status="unavailable", forecast_mw=np.nan)])
    actuals = f[["connector", "target", "delivery"]].assign(actual=[-20, 0])
    result = scorecard(attach_actuals(f, actuals))
    assert result.n.sum() == 1 and result.unscored.sum() == 1
    assert result.mae_mw.iloc[0] == 10


def test_legacy_import_and_generic_prediction_parity(tmp_path):
    from nemic.production.adapters import import_legacy
    from nemic.experiments.vni_forecast import VniBundleRepository
    final = tmp_path / "legacy" / "final"
    catalogue = []
    for band in range(4):
        for target in ("export", "import", "export_tight", "import_tight"):
            folder = final / f"band{band}" / target
            folder.mkdir(parents=True)
            bundle = dict(winner="persistence", models={}, input_columns=["lead", "own_anchor"], target=target, band=band,
                          quantiles=[.025, .1, .5, .9, .975], pooled_adjustments=np.array([-20,-10,0,10,20]),
                          period_adjustments={i:np.array([-20,-10,0,10,20]) for i in range(5)}, operationally_eligible=False)
            joblib.dump(bundle, folder / "model.joblib")
            catalogue.append(dict(target=target, band=band, path=str((folder / "model.joblib").relative_to(final.parent)), sha256=digest(folder / "model.joblib")))
    write_json(final / "catalogue.json", catalogue)
    registry = Registry(tmp_path / "registry")
    keys = import_legacy(final, registry, tmp_path / "staging")
    assert len(keys) == 16
    key = "vni-legacy-export-band0@1"
    policy = dict(version="legacy", routes=[dict(connector="VNI", target="export", lead_min=1, lead_max=12, models=[key])])
    origin = pd.Timestamp("2026-01-01", tz="Australia/Brisbane")
    prepared = pd.DataFrame(dict(connector="VNI", target="export", origin=origin, delivery=[origin+pd.Timedelta(minutes=30*i) for i in range(1,13)], lead=range(1,13), own_anchor=-50))
    old = VniBundleRepository(final).forecast(prepared, "export", allow_research=True)
    new = forecast(registry, policy, pd.DataFrame(), origin=origin, connectors=["VNI"], targets=["export"], mode="research", prepared=prepared)
    np.testing.assert_allclose(new.iloc[:12].forecast_mw, old.forecast_mw)
    np.testing.assert_allclose(new.iloc[:12].p10_mw, old.p10_mw)


def test_weather_cached_parser_requires_issue():
    from nemic.production.adapters import open_meteo_payload
    payload = {"hourly":{"time":["2026-01-01T01:00"], "temperature_2m":[25]}}
    with pytest.raises(ValueError, match="issue"):
        open_meteo_payload(payload, region="VIC1", received="2026-01-01T00:00Z")
    f = open_meteo_payload(payload, region="VIC1", received="2026-01-01T00:00Z", issue="2025-12-31T23:00Z")
    assert f.value.iloc[0] == 25
