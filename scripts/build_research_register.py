"""Build the compact register of evidence, claims and unresolved gates."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _entry(name, stack, evidence, claim, status, unresolved, command):
    path = ROOT / evidence
    return dict(name=name, stack=stack, evidence=evidence, evidence_exists=path.exists(),
                evidence_sha256=_sha(path), claim=claim, status=status,
                unresolved=unresolved, reproduce=command)


def build():
    rows = [
        _entry("Six-link conditional backtest", "original", "BACKTEST_REPORT.md",
               "Conditional performance using realised future fundamentals", "completed",
               ["Live issue-time evaluation", "Interval calibration"], "python run_pipeline.py"),
        _entry("VNI diurnal/NOS v2", "experiments", "docs/VNI_DIURNAL_NOS_RESULTS.md",
               "Retrospective rolling development evidence", "completed_research",
               ["Receipt-time feed", "Prospective confirmation", "Interval calibration"], "python scripts/run_vni_diurnal_nos_campaign.py"),
        _entry("QNI diurnal/NOS v2", "experiments", "docs/QNI_DIURNAL_NOS_RESULTS.md",
               "Retrospective rolling development evidence", "completed_research",
               ["Mixed cell skill", "Prospective confirmation", "Interval calibration"], "python scripts/run_qni_diurnal_nos_campaign.py"),
        _entry("QNI/VNI fundamentals v3", "experiments", "reports/qni_vni_fundamentals_v3/index.html",
               "Preserved historical report using publication proxies", "report_preserved_ledger_revalidation_required",
               ["Ledger stage revalidation", "Measured receipt", "Risk gates", "Full lead coverage"], "python -m nemic.fundamentals status"),
        _entry("QNI/VNI clustering v1", "experiments", "reports/qni_vni_clustering_v1/Clustering_Research.html",
               "Historical development using publication proxies", "completed_report_validated",
               ["Representative browser layout review", "Prospective confirmation"], "python -m nemic.experiments.clustering report"),
        _entry("NOS outage regimes", "experiments", "execution/nos_outage_regime_v1/RESULTS_SUMMARY.md",
               "Retrospective matched historical associations", "completed_research",
               ["Measured receipt replay", "Forward incident confirmation"], "python scripts/run_nos_regime.py --stage compare --tag full"),
        _entry("NOS mechanics/outlook", "experiments", "execution/nos_constraint_binding_v1/RESULTS_SUMMARY.md",
               "Retrospective mechanics and historical research outlook", "completed_research",
               ["Forward booking reliability", "Unsupported-cell calibration"], "python scripts/run_nos_binding.py --stage D2"),
        _entry("Interregional valuation v2", "valuation", "reports/interregional_valuation_research_v2/README.md",
               "Historical settlement, auction and hedge research", "completed_research",
               ["Issue-time flow regimes", "Automatic futures history", "Prospective valuation"], "python -m nemic.valuation all"),
        _entry("QNI/VNI long-range v1", "experiments", "reports/qni_vni_longrange_v1/Long_Range_Research.html",
               "Original-vintage historical development found no promotable challenger", "completed_research_no_promotion",
               ["Prospective outcomes and scorecard"], "python -m nemic.longrange_campaign status"),
        _entry("Production scaffold", "production", "docs/PRODUCTION_PIPELINE_GUIDE.md",
               "Offline provider-neutral routing scaffold", "research_shadow_schedule_active",
               ["Prospective scorecard", "Explicit model promotion review"], "python -m nemic.production --help"),
    ]
    json_path = ROOT / "docs/RESEARCH_REGISTER.json"
    json_path.write_text(json.dumps({"schema": 1, "entries": rows}, indent=2), encoding="utf-8")
    lines = ["# Research evidence register", "", "This register separates completed computation from demonstrated forecast improvement and prospective confirmation.", "",
             "| Research stream | Stack | Status | Permitted claim | Evidence |", "|---|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['name']} | {row['stack']} | {row['status']} | {row['claim']} | `{row['evidence']}` |")
    lines += ["", "## Unresolved gates", ""]
    for row in rows:
        lines.append(f"- **{row['name']}:** " + "; ".join(row["unresolved"]))
    lines += ["", "Raw archives, fitted models and large predictions remain local. A completed experiment does not change production routing.", ""]
    md_path = ROOT / "docs/RESEARCH_REGISTER.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


if __name__ == "__main__":
    print(build())
