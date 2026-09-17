"""Execute the complete QNI v2 campaign with resumable, stage-level logging.

Every modelling command retains its own hash/cache checks.  This driver only
orders the same stages used by the VNI campaign and records their exit status.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CONFIG = "configs/experiments/qni_diurnal_nos_v2.json"
FIXED = "configs/experiments/qni_diurnal_nos_v2_fixed.json"
RUN = ROOT / "data/forecast_experiments/qni_diurnal_nos_v2"


def experiment(command: str, config: str = CONFIG, *extra: str) -> list[str]:
    return [sys.executable, "-m", "nemic.experiments", command, "--config", config, *extra]


STAGES: list[tuple[str, list[str]]] = [
    ("primary", experiment("run-diurnal", CONFIG, "--stage", "primary")),
    ("nos_inventory", experiment("inventory-nos")),
    ("nos_recovery", experiment("recover-nos")),
    ("nos_audit", experiment("audit-nos")),
    ("nos_impacts", experiment("analyse-nos-impacts")),
    ("nos_feasibility", experiment("audit-nos-feasibility")),
    ("fixed_primary", experiment("run-diurnal-fixed", FIXED)),
    ("fixed_extensions", experiment("run-diurnal-extensions", FIXED)),
    ("rolling_extensions", experiment("run-diurnal-extensions")),
    ("rolling_risk", experiment("run-diurnal-risk")),
    ("fixed_risk", experiment("run-diurnal-risk", FIXED)),
    ("statistics", experiment("diurnal-statistics")),
    ("rolling_curves", experiment("run-diurnal-curves")),
    ("fixed_curves", experiment("run-diurnal-curves", FIXED)),
    ("bridge", experiment("run-diurnal-bridge")),
    ("refit", experiment("refit-diurnal")),
    ("explain_rolling", experiment("explain-diurnal")),
    ("explain_fixed", experiment("explain-diurnal", FIXED)),
    ("nos_models", experiment("run-nos-models")),
    ("refinements", experiment("run-diurnal-refinements")),
    ("nos_risk", experiment("run-nos-risk")),
    ("explain_nos", experiment("explain-nos")),
    ("reports", [sys.executable, "scripts/build_qni_report_suite.py"]),
    ("tests", [sys.executable, "-m", "pytest", "-q"]),
]


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-stage", choices=[name for name, _ in STAGES])
    args = parser.parse_args()
    RUN.mkdir(parents=True, exist_ok=True)
    start = 0 if args.from_stage is None else [name for name, _ in STAGES].index(args.from_stage)
    status_path = RUN / "campaign_status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {"campaign": "qni_diurnal_nos_v2", "stages": {}}
    for name, command in STAGES[start:]:
        log_path = RUN / f"campaign_{name}.log"
        status["stages"][name] = {"status": "running", "started": stamp(), "command": command, "log": log_path.name}
        status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{stamp()}] START {' '.join(command)}\n")
            log.flush()
            completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, text=True)
            log.write(f"[{stamp()}] EXIT {completed.returncode}\n")
        status["stages"][name].update(status="complete" if completed.returncode == 0 else "failed", finished=stamp(), exit_code=completed.returncode)
        status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
        if completed.returncode:
            raise SystemExit(f"QNI campaign stopped at {name}; inspect {log_path}")
    status["status"] = "complete"
    status["finished"] = stamp()
    status_path.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
