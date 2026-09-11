"""Run a dependency-scoped interconnector constraint-feature study."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/constraint_vni_pilot.json")
    args = parser.parse_args()
    steps = [
        ["-m", "nemic.constraint_ingest", "all", "--config", args.config],
        ["-m", "nemic.constraint_features", "--config", args.config],
        ["-m", "nemic.vni_influence_study", "--config", args.config],
        ["-m", "unittest", "tests.test_constraint_features", "-v"],
    ]
    for index, command in enumerate(steps, 1):
        print(f"CONSTRAINT PILOT {index}/{len(steps)} {' '.join(command)}", flush=True)
        subprocess.run([sys.executable, *command], cwd=ROOT, check=True)
