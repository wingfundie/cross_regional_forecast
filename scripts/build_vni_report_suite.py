"""Rebuild all VNI HTML reports from cached completed-run artifacts."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_vni_diurnal_report import build as build_full_report
from scripts.build_vni_nos_impact_report import build as build_nos_report
from scripts.reports.vni.build_suite import build_report_suite


if __name__ == "__main__":
    build_full_report()
    build_nos_report()
    print(build_report_suite())
