"""Reproduce the saved rolling diurnal comparison; does not train any model."""
from pathlib import Path
import hashlib
import json

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main():
    trial_root = ROOT / "data/forecast_experiments/vni_qni_202409_202608_v1/trials"
    frames, sources = [], []
    for path in sorted(trial_root.glob("*/20*/band0/*tight_predictions.parquet")):
        frame = pd.read_parquet(path)
        frame = frame[frame.protocol.eq("rolling")].copy()
        if frame.empty:
            continue
        delivery = pd.to_datetime(frame.delivery)
        hour = delivery.dt.hour + delivery.dt.minute / 60
        frame["period"] = pd.cut(
            hour, [0, 6, 10, 16, 21, 24], right=False,
            labels=["overnight", "morning", "solar", "evening", "late"],
        )
        frame["ae"] = (frame.prediction - frame.actual).abs()
        frame["pe"] = (frame.persistence - frame.actual).abs()
        frames.append(frame)
        sources.append({"path": path.relative_to(ROOT).as_posix(),
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    if not frames:
        raise ValueError("No saved rolling minimum-limit predictions available")
    combined = pd.concat(frames, ignore_index=True)
    keys = ["ic", "target", "origin", "lead", "fold", "protocol"]
    if combined.duplicated(keys).any():
        raise ValueError("Duplicate forecast keys in rolling evidence")
    if combined[["actual", "prediction", "persistence"]].isna().any().any():
        raise ValueError("Unmatched observations require an explicit eligibility policy")
    rows = combined.groupby(["ic", "target", "period"], observed=True).agg(
        n=("ae", "size"), mae=("ae", "mean"), persistence_mae=("pe", "mean")
    ).reset_index()
    rows["skill_vs_persistence"] = 1 - rows.mae / rows.persistence_mae
    output = {
        "claim": "Existing rolling development predictions; no new-model results",
        "protocol": "rolling", "band": 0,
        "lead_halfhours": sorted(int(v) for v in combined.lead.unique()),
        "period_basis": "NEM delivery interval end; left-closed buckets 0,6,10,16,21,24",
        "rows": json.loads(rows.to_json(orient="records")),
        "source_files": sources,
        "extractor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    destination = ROOT / "docs/data/qni_vni_diurnal_nos_evidence.json"
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Reproduced {len(rows)} period cells from {len(sources)} source files")
    print(rows.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
