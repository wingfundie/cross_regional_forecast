"""Explicit routing, adapter execution and complete segment-level outcomes."""
from pathlib import Path
import joblib
import numpy as np
import pandas as pd

from .contracts import CONNECTORS, QCOLS, TARGETS, connector, safe_path, write_json
from .features import build


def predict(manifest, folder, features, delivery, bundle=None):
    if bundle is None:
        bundle = joblib.load(safe_path(folder, "model.joblib"))
    if manifest["adapter"] == "legacy-vni":
        from nemic.experiments.diurnal_export import predict_bundle
        from nemic.experiments.diurnal import periods
        point = np.asarray(predict_bundle(bundle, features), dtype=float)
        group = int(periods(pd.DatetimeIndex([delivery]))[0])
        adjustments = np.asarray(bundle["period_adjustments"][group])
    elif manifest["adapter"] == "sklearn":
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            point = np.asarray(bundle["estimator"].predict(features), dtype=float)
        adjustments = np.asarray(bundle["adjustments"])
    else:
        raise ValueError(f"Unsupported prediction adapter: {manifest['adapter']}")
    quantiles = point[:, None] + adjustments
    if not np.isfinite(point).all() or not np.isfinite(quantiles).all() or (np.diff(quantiles, axis=1) < 0).any():
        raise ValueError("Invalid point/quantile prediction")
    return point, quantiles


def forecast(registry, policy, inputs, *, origin, connectors, days=1, targets=TARGETS,
             mode="production", scenario="baseline", history=None, prepared=None, preview=False, context=None):
    registry.validate_routes(policy)
    if mode not in {"production", "research", "shadow"}:
        raise ValueError("Unknown execution mode")
    origin = pd.Timestamp(origin)
    if origin.tzinfo is None or origin.minute % 30 or origin.second or origin.microsecond:
        raise ValueError("Origin must be timezone-aware and aligned to half an hour")
    origin = origin.tz_convert("Australia/Brisbane")
    if not 1 <= days <= 30 or int(days) != days:
        raise ValueError("Days must be an integer between 1 and 30")
    if not set(targets) <= set(TARGETS):
        raise ValueError("Unknown limit target")
    rows = []
    loaded, bundles = {}, {}
    for name in dict.fromkeys(connector(c) for c in connectors):
        for target in dict.fromkeys(targets):
            for lead in range(1, int(days) * 48 + 1):
                delivery = origin + pd.Timedelta(minutes=30 * lead)
                row = dict(connector=name, target=target, origin=origin, delivery=delivery, lead=lead,
                           scenario=scenario, routing_version=policy["version"], status="unavailable",
                           product="outlook" if lead > 336 else "forecast", model=None, recipe=None,
                           eligibility=None, selection=None, forecast_mw=np.nan,
                           **{column: np.nan for column in QCOLS})
                source, sink = CONNECTORS[name][1:]
                row["direction"] = f"{source} → {sink}" if target.startswith("export") else f"{sink} → {source}"
                failures = []
                for rank, key in enumerate(registry.candidates(policy, name, target, lead)):
                    try:
                        if key not in loaded:
                            loaded[key] = registry.load(key)
                        m, folder = loaded[key]
                        allowed = {"production": {"approved"}, "shadow": {"approved", "shadow"}, "research": {"approved", "shadow", "research"}}
                        if m["status"] not in allowed[mode]:
                            raise ValueError(f"Model status {m['status']} is ineligible for {mode}")
                        cutoff = m.get("calibration_end") or m.get("training_cutoff")
                        if cutoff and origin <= pd.Timestamp(cutoff):
                            raise ValueError("Model/calibration contains outcomes at or after forecast origin")
                        if m["recipe"] == "legacy-vni-v1":
                            if prepared is None:
                                raise ValueError("Prepared legacy features required")
                            f = prepared[(prepared.connector == name) & (prepared.target == target)
                                         & (prepared.origin == origin) & (prepared.delivery == delivery)]
                            if len(f) != 1:
                                raise ValueError("Exactly one target-specific prepared row required")
                            f = f[m["features"]].astype(float)
                            if not np.isfinite(f.to_numpy()).all():
                                raise ValueError("Non-finite prepared features")
                        else:
                            f = build(m, origin, delivery, name, inputs, history, context=context)
                        row.update(model=key, recipe=m["recipe"], eligibility=m["status"],
                                   calibration_version=m.get("calibration_version", "bundle-v1"),
                                   artifact_sha256=m["artifacts"].get("model.joblib"),
                                   status="ready" if preview else "complete", selection="primary" if rank == 0 else "fallback")
                        if not preview:
                            if key not in bundles:
                                bundles[key] = joblib.load(safe_path(folder, "model.joblib"))
                            point, quantiles = predict(m, folder, f, delivery, bundles[key])
                            row.update(forecast_mw=float(point[0]), **dict(zip(QCOLS, quantiles[0])))
                        break
                    except (ValueError, KeyError, FileNotFoundError) as exc:
                        row["status"] = "unavailable"
                        failures.append(f"{key}: {exc}")
                row["reason"] = "; ".join(failures) if failures else ("configured primary" if row["status"] != "unavailable" else "no route")
                rows.append(row)
    return pd.DataFrame(rows)


def hourly(frame):
    """Point aggregation only; never combine half-hour quantile bounds."""
    f = frame.copy()
    f["delivery"] = pd.to_datetime(f.delivery).dt.ceil("h")
    result = []
    keys = ["connector", "target", "origin", "scenario", "delivery"]
    for group, rows in f.groupby(keys, dropna=False):
        row = dict(zip(keys, group))
        valid = len(rows) == 2 and rows.status.eq("complete").all()
        row["status"] = "complete" if valid else "unavailable"
        row["forecast_mw"] = (rows.forecast_mw.min() if str(row["target"]).endswith("tight") else rows.forecast_mw.mean()) if valid else np.nan
        row["interval_basis"] = "unavailable: separate hourly calibration required"
        result.append(row)
    return pd.DataFrame(result)


def save_run(frame, folder, metadata=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=False)
    frame.to_parquet(folder / "forecasts.parquet", index=False)
    frame.to_csv(folder / "forecasts.csv", index=False)
    hourly(frame).to_csv(folder / "hourly.csv", index=False)
    from .contracts import digest
    write_json(folder / "run.json", {"metadata": metadata or {}, "rows": len(frame),
               "status_counts": frame.status.value_counts().to_dict(),
               "sha256": digest(folder / "forecasts.parquet")})
    from .reports import report
    report(frame, folder)
    return folder
