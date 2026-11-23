import pandas as pd

from nemic.experiments.pec.forecast import TARGETS, _origins, _split, gate_vintages
from nemic.experiments.pec.issued import VINTAGE_FEATURES


def test_forecast_gate_rejects_late_receipt_without_mixing_regional_vintages():
    grid = pd.DataFrame({
        "origin": pd.to_datetime(["2026-11-21 08:00", "2026-11-21 08:30"]),
        "time": pd.to_datetime(["2026-11-21 09:00", "2026-11-21 09:00"]),
    })
    forecasts = pd.DataFrame({
        "product": ["predispatch", "predispatch"],
        "vintage": ["older", "newer"],
        "time": pd.to_datetime(["2026-11-21 09:00", "2026-11-21 09:00"]),
        "issued_at": pd.to_datetime(["2026-11-21 07:32", "2026-11-21 07:59"]),
        "published_at": pd.to_datetime(["2026-11-21 07:33", "2026-11-21 08:01"]).as_unit("s"),
        "source_sha256": ["olderhash", "newerhash"],
        **{column: [100.0, 200.0] for column in VINTAGE_FEATURES},
    })
    forecasts.loc[1, "sa_wind_forecast"] = float("nan")
    replay = gate_vintages(grid, forecasts, "predispatch")
    assert replay["vintage"].tolist() == ["older", "newer"]
    assert replay["sa_wind_forecast"].iloc[0] == 100
    assert pd.isna(replay["sa_wind_forecast"].iloc[1])
    assert replay["nsw_wind_forecast"].iloc[1] == 200


def test_forecast_purges_target_windows_between_partitions():
    origins = pd.date_range("2026-10-01 08:00", "2026-11-21 08:00", freq="D")
    left = pd.DataFrame({"origin": origins}).loc[lambda frame: frame.index.repeat(35)].reset_index(drop=True)
    left["origin_day"] = left["origin"].dt.normalize()
    left["time"] = left["origin"] + pd.Timedelta(hours=168)
    left["published_at"] = left["time"] + pd.Timedelta(minutes=5)
    start = pd.Timestamp("2026-11-22")
    train, selection, calibration = _split(left, start, 168)
    assert len(train) and len(selection) and len(calibration)
    assert train["published_at"].max() <= selection["origin"].min()
    assert selection["published_at"].max() <= calibration["origin"].min()
    assert calibration["published_at"].max() <= start


def test_persistence_uses_only_completed_available_targets():
    halfhour = pd.DataFrame({
        "time": pd.to_datetime(["2026-11-21 07:00", "2026-11-21 07:30", "2026-11-21 08:00"]),
        "published_at": pd.to_datetime(["2026-11-21 07:03", "2026-11-21 08:02", "2026-11-21 08:00"]),
        "configuration": ["booked", "booked", "switched"],
        **{column: [-10.0, 0.0, 99.0] for column in TARGETS},
    })
    grid, _ = _origins(halfhour, pd.Timestamp("2026-11-21"), pd.Timestamp("2026-11-22"))
    daily = grid[grid["schedule"].eq("daily_0800")]
    assert len(daily) == 336
    assert daily["anchor_time"].eq(pd.Timestamp("2026-11-21 07:00")).all()
    assert daily["known_nsw_sa_tight"].eq(-10).all()
    assert daily["time"].max() == pd.Timestamp("2026-11-28 08:00")
