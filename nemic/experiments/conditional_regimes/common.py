"""Campaign-owned paths, atomic artifacts and crash-safe single-stage ownership."""
from __future__ import annotations
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

import psutil

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data/forecast_experiments/conditional_regimes_v1"
REPORT = ROOT / "reports/conditional_regimes_v1"
EXECUTION = ROOT / "execution/conditional_regimes_v1"
CONFIG = ROOT / "configs/experiments/conditional_regimes_v1.json"
PACKAGE = ROOT / "packages/nemic-regimes"


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(obj, indent=2, default=str, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def config():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def code_signature():
    paths = sorted(Path(__file__).parent.glob("*.py")) + sorted((PACKAGE / "src/nemic_regimes").rglob("*.py"))
    paths += [CONFIG, EXECUTION / "METHODOLOGY.md", EXECUTION / "event_catalogue.json"]
    return hashlib.sha256("".join(str(p.relative_to(ROOT)) + digest(p) for p in paths if p.exists()).encode()).hexdigest()


def stage_signature(inputs=()):
    return hashlib.sha256((code_signature() + "".join(digest(p) for p in inputs if Path(p).exists())).encode()).hexdigest()


def dependency_snapshot(name, inputs=()):
    """Declared source/input dependencies; outputs are checked separately."""
    here=Path(__file__).parent
    modules={"inventory":["sources"],"acquire":["sources"],"events":["events"],"prepare":["data","sources"],
             "pilot":["research","metrics"],"evaluate":["research","metrics"],"assess":["assessment","metrics"],
             "bundle":["packaging","research"],"report":["reports"],"validate":["verify"]}
    paths=[CONFIG,Path(__file__),*(here/(module+".py") for module in modules.get(name,[])),*map(Path,inputs)]
    if name in {"prepare","pilot","evaluate","bundle","validate"}:
        paths += [PACKAGE/"src/nemic_regimes/core.py",PACKAGE/"src/nemic_regimes/models.py",EXECUTION/"METHODOLOGY.md"]
    if name in {"bundle","report","validate"}:
        paths += list((PACKAGE/"src/nemic_regimes").rglob("*.py"))
    if name=="inventory" and (DATA/"inventory.json").exists():
        paths += [ROOT/row["path"] for row in json.loads((DATA/"inventory.json").read_text(encoding="utf-8"))["sources"]]
    if name in {"prepare","bundle"}:
        paths += list((DATA/"extension").rglob("*.parquet"))
        paths += list((ROOT/"data/nos_binding_v1/standing").glob("*.parquet"))
        paths += list((ROOT/"data/nos_binding_v1/dispatchload").glob("*.parquet")) if name=="prepare" else []
        paths += [ROOT/"data/nos_regime_v1"/x for x in ("tables_panel_cache.parquet","episodes.parquet","episode_sets.parquet","outage_keys.parquet","invocation_spells.parquet")]
    if name=="events":
        paths += [EXECUTION/"event_catalogue.json",*DATA.glob("web_evidence_*.json"),*DATA.glob("web_search_*.json")]
    if name=="evaluate":paths += list((DATA/"tuning").glob("*.json"))
    if name=="report":
        paths += list(EXECUTION.glob("*.md"))+list((PACKAGE/"dist").glob("*.whl"))
        paths += [ROOT/"scripts/report_theme/report_theme.py",ROOT/"scripts/report_theme/report.css",
                  ROOT/"outputs/conditional_regimes_v1_20261025/conditional_limits.xlsx"]
        paths += [DATA/x for x in ("quarterly_catalogue.csv","assessed_scores.csv","assessed_paired_comparisons.csv","assessed_method_gates.csv",
                  "coverage.csv","feature_coverage.csv","family_mapping.csv","electrical_groups.csv","evaluation_availability.csv",
                  "example_profile.csv","example_profile.json","asof_scorecard.json","data_audit.json","source_manifest.json","event_review.json","nemic_regimes_bundle_v1.zip")]
    if name=="report":paths += [DATA/"canonical_partition_audit.json",PACKAGE/"examples/integration.py"]
    if name=="validate":paths += [DATA/x for x in ("visual_qa.json","package_smoke.json","test_results.json","canonical_partition_audit.json")]
    dependencies={str(p.resolve().relative_to(ROOT.resolve())):digest(p) if p.exists() else None for p in set(paths)}
    import importlib.metadata
    for package in ("numpy","pandas","pyarrow","scikit-learn","lightgbm","scipy"):
        dependencies["@runtime/"+package]=importlib.metadata.version(package)
    return dependencies


@contextmanager
def stage(name, inputs=()):
    DATA.mkdir(parents=True, exist_ok=True)
    lock = DATA / "owner.json"
    if lock.exists():
        prior = json.loads(lock.read_text())
        if psutil.pid_exists(prior["pid"]):
            process = psutil.Process(prior["pid"])
            if abs(process.create_time() - prior.get("process_started", 0)) < 1:
                raise RuntimeError(f"Healthy stage owner exists: {prior}")
        for worker in (DATA / "worker_owners").glob("*.json"):
            info=json.loads(worker.read_text())
            if psutil.pid_exists(info["pid"]) and abs(psutil.Process(info["pid"]).create_time()-info["process_started"])<1:
                raise RuntimeError(f"Healthy orphan worker still owns the stage: {info}")
        lock.unlink()
    # Exclusive create prevents two contenders acquiring a stage simultaneously.
    with lock.open("x", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "process_started": psutil.Process().create_time(), "stage": name, "started": now()}, f)
    started = time.monotonic()
    ledger_path = DATA / "ledger.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    entry = {"status": "active", "started": now(), "pid": os.getpid(), "signature": stage_signature(inputs),
             "input_paths":[str(Path(p).resolve().relative_to(ROOT.resolve())) for p in inputs],
             "dependencies":dependency_snapshot(name,inputs)}
    ledger[name] = entry
    write_json(ledger_path, ledger)
    artifacts = []
    try:
        yield artifacts
        missing = [str(p) for p in artifacts if not Path(p).exists()]
        if missing:
            raise RuntimeError(f"Missing stage artifacts: {missing}")
        entry.update(status="completed", finished=now(), seconds=round(time.monotonic()-started, 2),
                     artifacts={str(Path(p).relative_to(ROOT)): digest(p) for p in artifacts})
    except BaseException as exc:
        entry.update(status="failed", finished=now(), error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        ledger[name] = entry
        write_json(ledger_path, ledger)
        with (DATA / "events.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"stage": name, **entry}) + "\n")
        if lock.exists():
            lock.unlink()


def verified_stage(name):
    p = DATA / "ledger.json"
    if not p.exists():
        return False
    row = json.loads(p.read_text()).get(name, {})
    if row.get("status")!="completed" or not row.get("dependencies"):
        return False
    if not all((ROOT/k).exists() and digest(ROOT/k)==v for k,v in row.get("artifacts",{}).items()):
        return False
    inputs=[ROOT/p for p in row.get("input_paths",[])]
    return row["dependencies"]==dependency_snapshot(name,inputs)
