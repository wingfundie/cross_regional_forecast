"""Run the dependency-scoped VNI constraint-feature feasibility pilot."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    ["-m", "nemic.constraint_ingest", "all"],
    ["-m", "nemic.constraint_features"],
    ["-m", "nemic.vni_influence_study"],
    ["-m", "unittest", "tests.test_constraint_features", "-v"],
]

if __name__ == "__main__":
    for index, args in enumerate(STEPS, 1):
        print(f"CONSTRAINT PILOT {index}/{len(STEPS)} {' '.join(args)}", flush=True)
        subprocess.run([sys.executable, *args], cwd=ROOT, check=True)
