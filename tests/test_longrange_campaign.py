import json
import numpy as np
import pandas as pd

import nemic.longrange_campaign as campaign


def test_longrange_campaign_freezes_chronology_and_retains_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "DATA", tmp_path / "run")
    config = {
        "campaign": "test", "claim": "test only", "connectors": ["VNI"], "targets": ["export_tight"],
        "leads_half_hours": [1, 336, 480, 672], "daily_issue_hour_nem": 8, "minimum_train_origins": 12,
        "selection_origins": 14, "calibration_origins": 14, "evaluation_origins": 8,
        "point_improvement_threshold": .02, "interval_minimum_coverage": {"80": .77, "95": .92},
        "runtime": {"numerical_threads": 1},
    }
    config_path = tmp_path / "config.json"; config_path.write_text(json.dumps(config))
    origins = pd.date_range("2025-01-01 08:00", periods=48, freq="D", tz="Australia/Brisbane")
    rows = []
    for origin in origins:
        for lead in config["leads_half_hours"]:
            delivery = origin + pd.Timedelta(minutes=30*lead)
            value = 500 + 50*np.sin(2*np.pi*delivery.hour/24)
            rows.append(dict(origin=origin, delivery=delivery, mt_run=origin-pd.Timedelta(hours=12), lead=lead,
                             connector="VNI", target="export_tight", actual=value, own_anchor=value, hour_sin=np.sin(2*np.pi*delivery.hour/24),
                             hour_cos=np.cos(2*np.pi*delivery.hour/24), year_sin=np.sin(2*np.pi*delivery.dayofyear/365.25),
                             year_cos=np.cos(2*np.pi*delivery.dayofyear/365.25), weekend=float(delivery.dayofweek>=5),
                             log_lead=np.log1p(lead), mt_age_hours=12., source_capacity_mw=1000., sink_capacity_mw=900.,
                             source_unit_count=10., sink_unit_count=9., source_positive_capacity_fraction=.9,
                             sink_positive_capacity_fraction=.9, source_mean_recall_hours=1., sink_mean_recall_hours=1.,
                             capacity_difference=100., positive_capacity_fraction_difference=0.))
    campaign.DATA.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(campaign.DATA / "features.parquet", index=False)
    result_path = campaign.run("VNI", config_path)
    result = json.loads(result_path.read_text())
    assert result["promotion"] is False
    cell = result["cells"][0]
    assert cell["partitions"]["select_start"] < cell["partitions"]["calibration_start"] < cell["partitions"]["evaluation_start"]
    assert cell["decision"] in {"retain_baseline", "improvement_demonstrated"}
    shadow_origin = origins[-1] + pd.Timedelta(days=1)
    mt_rows = []
    for lead in config["leads_half_hours"]:
        day = (shadow_origin + pd.Timedelta(minutes=30*lead)).tz_localize(None).normalize()
        for region in ("VIC1", "NSW1"):
            mt_rows.append(dict(available_at=shadow_origin-pd.Timedelta(hours=1), day=day, region=region,
                                capacity_mw=1000., unit_count=10., positive_capacity_fraction=.9,
                                mean_recall_hours=1., source_hash="test",
                                receipt_completed_at=shadow_origin-pd.Timedelta(hours=1),
                                availability_evidence="measured_receipt"))
    monkeypatch.setattr(campaign, "_load_mt", lambda: pd.DataFrame(mt_rows))
    forecast_path = campaign.shadow(shadow_origin, "VNI", tmp_path / "shadow", config_path)
    forecast = pd.read_parquet(forecast_path)
    assert forecast.status.eq("complete").all()
    assert not forecast.promotion.any()
