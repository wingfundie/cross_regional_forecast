"""Rebuild all QNI HTML reports from cached completed-run artifacts."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_vni_diurnal_report import build as build_full_report
from scripts.build_vni_nos_impact_report import build as build_nos_report
from scripts.build_vni_research_paper import build as build_research_paper
from scripts.reports.vni.build_suite import build_report_suite
from scripts.build_qni_results_summary import build as build_results_summary
from scripts.publish_vni_reports import publish


CONFIG = "configs/experiments/qni_diurnal_nos_v2.json"


if __name__ == "__main__":
    build_full_report(CONFIG)
    build_nos_report(CONFIG)
    build_research_paper(CONFIG)
    print(build_report_suite(CONFIG))
    print(build_results_summary())
    print(publish('QNI', 'qni_diurnal_nos_v2', 'build_qni_report_suite.py', 'publish_qni_reports.py'))
