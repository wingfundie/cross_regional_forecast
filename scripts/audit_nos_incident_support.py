"""Audit saved March-August event evidence; no NOS coverage or power claim."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nemic.experiments.events import match


def main():
    rows, sources = [], []
    base = ROOT / "data/forecast_experiments/vni_qni_202409_202608_v1/trials"
    for connector in ("VNI", "QNI"):
        for direction in ("export", "import"):
            unique_events = set()
            for month in range(3, 9):
                fold = f"2026-{month:02d}"
                directory = base / connector / fold / "events"
                paths = [directory / f"{direction}_{kind}.parquet"
                         for kind in ("predictions", "incidents")]
                predictions, events = [pd.read_parquet(path) for path in paths]
                for path in paths:
                    sources.append({"path": path.relative_to(ROOT).as_posix(),
                                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
                predictions = predictions.sort_values("origin")
                assert not predictions.origin.duplicated().any()
                assert predictions.threshold.nunique() == 1
                predictions = predictions[np.isfinite(predictions.actual_window)]
                origins = pd.DatetimeIndex(predictions.origin)
                result = match(origins, predictions.probability.to_numpy(),
                               float(predictions.threshold.iloc[0]), events)
                times = pd.DatetimeIndex(events.time)
                lower = times.asi8 - pd.Timedelta(minutes=120).value
                upper = times.asi8 - pd.Timedelta(minutes=30).value
                eligible = (np.searchsorted(origins.asi8, upper, side="right") >
                            np.searchsorted(origins.asi8, lower, side="left"))
                assert int(eligible.sum()) == result["incidents"]
                unique_events.update(times[eligible].astype(str))
                rows.append({"connector": connector, "direction": direction, "fold": fold,
                             "origins": len(origins), "exposure_days": len(origins) / 48,
                             "incidents": result["incidents"], "tp": result["tp"],
                             "fp": result["fp"]})
            selected = [r for r in rows if r["connector"] == connector and r["direction"] == direction]
            total = {key: sum(r[key] for r in selected)
                     for key in ("origins", "exposure_days", "incidents", "tp", "fp")}
            total.update(connector=connector, direction=direction,
                         distinct_onset_timestamps=len(unique_events))
            print(json.dumps(total))
    output = {"claim": "Provisional saved-policy development audit, before NOS coverage and v2 label audit; not power or new-model results",
              "warning": "Incident counts are independent of the alarm budget. Fold totals may repeat boundary incidents; distinct timestamps do not establish independent outage episodes.",
              "rows": rows, "sources": sources}
    destination = ROOT / "docs/data/qni_vni_nos_incident_support.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
