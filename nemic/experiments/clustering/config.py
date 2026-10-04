"""Configuration and content lineage for the clustering campaign."""
from __future__ import annotations

from pathlib import Path
import json

from nemic.experiments.core import ROOT, Store, digest, fingerprint

DEFAULT_CONFIG = ROOT / "configs/experiments/qni_vni_clustering_v1.json"


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict:
    path = Path(path).resolve()
    value = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "campaign", "root", "tracking_root", "source_campaign", "connectors",
        "targets", "leads", "bands", "folds", "clustering", "generator",
        "limits", "claims",
    }
    missing = sorted(required - value.keys())
    if missing:
        raise ValueError(f"Missing clustering configuration fields: {missing}")
    if value["campaign"] != "qni_vni_clustering_v1":
        raise ValueError("Unexpected clustering campaign identity")
    if [item["name"] for item in value["connectors"]] != ["VNI", "QNI"]:
        raise ValueError("Connector execution order must be VNI then QNI")
    if value["targets"] != ["flow", "export_tight", "import_tight"]:
        raise ValueError("Clustering v1 target contract changed")
    if max(value["leads"]) > 336:
        raise ValueError("Clustering v1 stops at 168 hours (lead 336)")
    if value["limits"]["workers"] > 2 or value["limits"]["threads"] > 2:
        raise ValueError("Campaign resource ceiling is two workers/two threads")
    run = (ROOT / value["root"] / value["campaign"]).resolve()
    allowed = (ROOT / "data/forecast_experiments").resolve()
    if not run.is_relative_to(allowed) or run == allowed:
        raise ValueError("Run root must be a child of data/forecast_experiments")
    source = (ROOT / value["source_campaign"]).resolve()
    if not source.is_relative_to(allowed) or source == run:
        raise ValueError("Source campaign must be a distinct retained campaign")
    tracking = (ROOT / value["tracking_root"]).resolve()
    if not tracking.is_relative_to(ROOT):
        raise ValueError("Tracking directory outside workspace")
    value["_path"] = path
    value["_run"] = run
    value["_source"] = source
    value["_tracking"] = tracking
    return value


def code_manifest() -> list[dict]:
    package = Path(__file__).resolve().parent
    paths = sorted(package.glob("*.py"))
    # These shared helpers are imported by the campaign and therefore belong in
    # its lineage. Existing campaigns keep their original manifest rules.
    paths += [
        ROOT / "nemic/experiments/core.py",
        ROOT / "nemic/experiments/events.py",
    ]
    return [
        {"path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)}
        for path in paths if path.exists()
    ]


def campaign_fingerprint(config: dict, sources: list[dict]) -> str:
    public = {key: value for key, value in config.items() if not key.startswith("_")}
    modelling_code = [
        item for item in code_manifest()
        if Path(item["path"]).name not in {"report.py", "__main__.py"}
    ]
    return fingerprint({"configuration": public, "sources": sources, "code": modelling_code})


def store(config: dict) -> Store:
    return Store(config)
