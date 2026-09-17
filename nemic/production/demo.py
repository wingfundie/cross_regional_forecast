"""Deterministic offline demonstration. No downloaded or real training data."""
from pathlib import Path
import numpy as np
import pandas as pd

from .contracts import write_json
from .registry import Registry
from .training import train
from .pipeline import forecast, save_run


def run(folder):
    root = Path(folder)
    root.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(17)
    origins = pd.date_range("2025-01-01", periods=60, freq="D", tz="Australia/Brisbane")
    records = []
    for origin in origins:
        for lead in (1, 12, 24, 48):
            delivery = origin + pd.Timedelta(minutes=lead * 30)
            hour = delivery.hour + delivery.minute / 60
            records.append(dict(origin=origin, delivery=delivery, connector="VNI", lead=lead,
                                hour_sin=np.sin(2 * np.pi * hour / 24), hour_cos=np.cos(2 * np.pi * hour / 24),
                                actual=450 + 100 * np.sin(2 * np.pi * hour / 24) + rng.normal(0, 15)))
    frame = pd.DataFrame(records)
    frame.to_parquet(root / "synthetic_training.parquet", index=False)
    registry = Registry(root / "registry")
    routes = []
    for name in ("VNI", "QNI"):
        manifest = {"id": f"synthetic-{name.lower()}", "version": "1", "connectors": [name],
                    "target": "export", "lead_min": 1, "lead_max": 48, "resolution_minutes": 30,
                    "recipe": "calendar-v1", "features": ["lead", "hour_sin", "hour_cos"], "synthetic": True}
        package = root / f"package-{name.lower()}"
        local = frame.assign(connector=name)
        train(local, manifest, package, budget_seconds=2, max_trials=1)
        from .reports import training_report
        training_report(package)
        key = registry.register(package)
        routes.append(dict(connector=name, target="export", lead_min=1, lead_max=48, models=[key]))
    policy = {"version": "synthetic-demo-1", "routes": routes}
    write_json(root / "routes.json", policy)
    result = forecast(registry, policy, pd.DataFrame(), origin="2025-04-01T00:00:00+10:00",
                      connectors=["VNI", "QNI", "Basslink"], days=1, targets=["export"], mode="research", scenario="synthetic-demo")
    save_run(result, root / "run", {"synthetic": True, "warning": "No production performance evidence"})
    return root / "run" / "index.html"
