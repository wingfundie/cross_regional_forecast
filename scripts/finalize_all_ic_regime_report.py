"""Wait for the three new longitudinal studies, then rebuild and validate the report."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = [
    ROOT / "configs/constraint_directlink_2y.json",
    ROOT / "configs/constraint_murraylink_2y.json",
    ROOT / "configs/constraint_basslink_2y.json",
]
VALIDATOR = Path.home() / ".codex/skills/editorial-html-report/scripts/validate_report.py"
REPORT = ROOT / "reports/all_interconnector_regime_research_20260921/index.html"
STATUS = ROOT / "reports/all_interconnector_regime_research_20260921/finalization_status.json"


def counts(config_path: Path):
    config = json.loads(config_path.read_text(encoding="utf-8"))
    ledger = ROOT / "data" / config["output_dir"] / "ledger.sqlite"
    if not ledger.exists():
        return 0, 0, 0
    with sqlite3.connect(ledger) as db:
        rows = dict(db.execute("select status,count(1) from months group by status").fetchall())
    return rows.get("complete", 0), rows.get("running", 0), rows.get("failed", 0)


def write_status(state, detail):
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({"state": state, "detail": detail, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2), encoding="utf-8")


def main():
    write_status("waiting", {str(path.name): counts(path) for path in CONFIGS})
    while True:
        state = {str(path.name): counts(path) for path in CONFIGS}
        if all(complete == 24 for complete, _, _ in state.values()):
            break
        if not any(running for _, running, _ in state.values()):
            for config in CONFIGS:
                if counts(config)[0] < 24:
                    write_status("resuming", {str(path.name): counts(path) for path in CONFIGS})
                    subprocess.run([sys.executable, "-m", "nemic.constraint_longitudinal", "run", "--config", str(config)],
                                   cwd=ROOT, check=True)
        write_status("waiting", state)
        time.sleep(60)
    write_status("building", state)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_all_ic_regime_report.py")], cwd=ROOT, check=True)
    subprocess.run([sys.executable, str(VALIDATOR), str(REPORT)], cwd=ROOT, check=True)
    write_status("complete", {str(path.name): counts(path) for path in CONFIGS})


if __name__ == "__main__":
    main()
