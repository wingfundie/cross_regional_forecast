"""Build the V-SA two-year report with the shared longitudinal report generator."""
from pathlib import Path

from build_vni_two_year_report import build


if __name__ == "__main__":
    build(Path("configs/constraint_vsa_2y.json"))
