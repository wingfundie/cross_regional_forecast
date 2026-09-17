"""Build a navigable VNI report suite from the immutable full-run report.

The model runners keep their original artifact paths.  This module adds a human
facing catalogue and focused HTML views without copying or changing model data.
"""
from __future__ import annotations

import csv
import hashlib
import json
import argparse
from copy import copy
from pathlib import Path
import shutil
import sys

from bs4 import BeautifulSoup
import pandas as pd
from nemic.experiments.core import load_config


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.report_theme.report_theme import hero, metric, render_page

RUN = ROOT / "data/forecast_experiments/vni_diurnal_nos_v2"
REPORT = RUN / "report"
PAGES = REPORT / "pages"
FULL = REPORT / "full_run"
DOWNLOADS = REPORT / "downloads"
QA = REPORT / "qa"
CONNECTOR = {"name": "VNI", "id": "VIC1-NSW1"}
SLUG = "vni"
CONFIG_PATH = "configs/experiments/vni_diurnal_nos_v2.json"

PAGE_SPECS = (
    (
        "01_model_performance.html",
        "Model performance",
        "Rolling and fixed evaluation, delivery-period results, 336-step curves and the legacy bridge.",
        ("Model results", "Full 336-step finalist curves", "Corrected legacy-policy bridge"),
    ),
    (
        "02_model_explorer.html",
        "Model explorer",
        "Actual-versus-forecast charts, metrics, search histories, fitted parameters, uncertainty, feature importance and SHAP for every cell.",
        ("Models used", "Models, actual limits and explanations"),
    ),
    (
        "03_feature_fundamentals.html",
        "Features and fundamentals",
        "Grouped importance and the physical interpretation of calendar, observed-history, network-state and generator-pressure inputs.",
        ("Feature relevance to fundamentals",),
    ),
    (
        "04_nos_outages.html",
        "NOS outage modelling",
        "Coverage, mapping, matched outage assessment, outage-feature ablations, actual-versus-forecast charts, importance and SHAP.",
        ("NOS outage evidence",),
    ),
    (
        "05_risk_and_refinements.html",
        "Risk and refinements",
        "Contraction-warning models, bounded training-window and lead-pressure refinements, importance and SHAP.",
        ("Bounded refinements", "Contraction warnings"),
    ),
    (
        "06_model_handoff.html",
        "Model verdict and handoff",
        "Final model choice, statistical tests, exact trained-bundle parameters, reload parity and evidence limits.",
        ("Model-choice verdict", "Methods and limits of the evidence"),
    ),
)

ARTIFACT_AREAS = (
    ("diurnal", "Point models", "Rolling and fixed fold × target × horizon-band searches and explanations"),
    ("curves", "Forecast curves", "Frozen 336-step forecast curves and boundary audits"),
    ("bridge", "Legacy bridge", "Aligned sampling comparison against legacy policy families"),
    ("risk", "Contraction risk", "Base contraction-warning models and explanations"),
    ("nos", "NOS source analysis", "Archive, coverage, mapping, exposure and matched-impact evidence"),
    ("nos_models", "NOS point models", "Source-common outage-feature ablations and explanations"),
    ("nos_risk", "NOS risk", "Scheduled-outage contraction-risk challengers"),
    ("refinements", "Post-selection refinements", "Training-window and lead-conditioned pressure tests"),
    ("final", "Trained bundles", "Frozen research bundles, schemas, parameters and reload checks"),
    ("report", "Reports", "Human-facing HTML pages, downloads, manifests and QA evidence"),
)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _heading(node) -> str:
    heading = node.find(["h1", "h2"])
    return heading.get_text(" ", strip=True) if heading else ""


def _navigation(prefix: str = "") -> str:
    links = [f'<a href="{prefix}index.html">Report home</a>'] if prefix else []
    links.extend(
        f'<a href="{prefix}pages/{filename}">{title}</a>'
        for filename, title, _, _ in PAGE_SPECS
    )
    links.append(f'<a href="{prefix}full_run/{SLUG}_diurnal_nos_model_report.html">Full run</a>')
    return "<nav class=\"suite-nav\">" + " · ".join(links) + "</nav>"


def _focused_page(source: BeautifulSoup, filename: str, title: str, dek: str, headings: tuple[str, ...]) -> Path:
    source_main = source.find("main")
    selected = [node for node in source_main.find_all("section", recursive=False) if _heading(node) in headings]
    if len(selected) != len(headings):
        found = {_heading(node) for node in selected}
        raise ValueError(f"Missing report sections for {filename}: {set(headings) - found}")

    has_plots = any(node.select_one(".lazy-plot") for node in selected)
    document = BeautifulSoup("<!doctype html><html><head></head><body><main></main></body></html>", "html.parser")
    for node in source.head.find_all(recursive=False):
        if node.name == "script" and not has_plots:
            continue
        document.head.append(copy(node))
    document.title.string = f"{CONNECTOR['name']} · {title}"
    main = document.find("main")
    header = BeautifulSoup(
        hero(
            f"{CONNECTOR['name']} forecasting research",
            "Completed run",
            title,
            dek,
            [CONNECTOR['id'], "NEM time · UTC+10", "Outcomes through August 2026", "Historical development evidence"],
        ),
        "html.parser",
    )
    main.append(header)
    nav = BeautifulSoup(_navigation("../"), "html.parser")
    main.append(nav)
    for node in selected:
        main.append(copy(node))
    # The model explorer and all chart pages use the same lazy Plotly renderer.
    if has_plots:
        for script in source_main.find_all("script", recursive=False):
            main.append(copy(script))
    target = PAGES / filename
    target.write_text(str(document), encoding="utf-8")
    return target


def _artifact_catalog() -> list[dict]:
    rows = []
    for folder, label, purpose in ARTIFACT_AREAS:
        path = RUN / folder
        files = [p for p in path.rglob("*") if p.is_file()] if path.exists() else []
        rows.append(
            {
                "folder": folder,
                "label": label,
                "purpose": purpose,
                "file_count": len(files),
                "size_mb": round(sum(p.stat().st_size for p in files) / 1024**2, 2),
            }
        )
    return rows


def _write_catalog(rows: list[dict]) -> None:
    with (DOWNLOADS / "artifact_catalog.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        f"# {CONNECTOR['name']} diurnal and NOS run catalogue",
        "",
        "Start with `report/index.html`. Model artifacts remain in their original immutable folders so completed-run lineage and hashes stay valid.",
        "",
        "| Folder | Contents | Files | Size (MB) |",
        "|---|---|---:|---:|",
    ]
    lines.extend(f"| `{r['folder']}/` | {r['purpose']} | {r['file_count']} | {r['size_mb']:.2f} |" for r in rows)
    lines.extend(
        [
            "",
            "## Rebuild",
            "",
            "```powershell",
            "python scripts/build_qni_report_suite.py" if SLUG == "qni" else "python scripts/build_vni_report_suite.py",
            "```",
            "",
            "The rebuild reads cached run evidence. It does not retrain models.",
        ]
    )
    (RUN / "RUN_INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _index(rows: list[dict], pages: list[Path]) -> Path:
    cards = []
    for filename, title, description, _ in PAGE_SPECS:
        cards.append(
            '<article class="finding"><div class="finding-index">REPORT</div>'
            f'<h3><a href="pages/{filename}">{title}</a></h3><p>{description}</p></article>'
        )
    performance=pd.read_csv(DOWNLOADS/'research_performance.csv')
    export=performance.query("target == 'export_tight' and band == 0").iloc[0]
    imported=performance.query("target == 'import_tight' and band == 0").iloc[0]
    completed=len(list((RUN/'diurnal').glob('*/band*/*/result.json')))
    body = hero(
        f"{CONNECTOR['name']} forecasting research",
        "Run centre",
        "Models, evidence and reports",
        f"One landing page for the completed {CONNECTOR['name']} diurnal and NOS study. MAE drives selection; MAPE is assessment-only. All pages are offline and reproduce the completed cached run.",
        [CONNECTOR['id'], f"{completed} evaluated model cells", "16 frozen research bundles", "Outcomes through August 2026"],
    )
    body += _navigation()
    body += '<section class="metrics">'
    body += metric("Point-model policy", "Target × band", "Frozen MAE selection; see model handoff")
    body += metric("Export tight skill", f"{100*export.skill_persistence:.1f}%", "Band 0 versus persistence")
    body += metric("Import tight skill", f"{100*imported.skill_persistence:.1f}%", "Band 0 versus persistence")
    body += metric("NOS point verdict", "Challenger", "Source-common ablations reported separately")
    body += "</section>"
    body += '<section><h2>Choose a report</h2><div class="findings">' + "".join(cards) + "</div></section>"
    body += '<section><h2>Research paper</h2><div class="callout"><strong>Complete written study.</strong> '
    body += f'<a href="{SLUG}_research_paper.html">Read the full research paper</a> for the research question, methods, model and feature definitions, comparative results, explainability, NOS findings, selected specification and forward-forecasting guide.</div></section>'
    body += '<section><h2>Complete-run files</h2><div class="callout"><strong>Full report.</strong> '
    body += f'<a href="full_run/{SLUG}_diurnal_nos_model_report.html">Open the complete model report</a> or '
    body += '<a href="full_run/nos_outage_impact_analysis.html">open the matched NOS impact report</a>. '
    body += 'These retain every chart, table, search history, feature-importance result and SHAP decomposition.</div>'
    body += '<p>Downloads: <a href="downloads/model_results.csv">all model results</a> · '
    body += '<a href="downloads/artifact_catalog.csv">artifact catalogue</a> · '
    body += '<a href="downloads/source_build.json">source build manifest</a> · '
    body += '<a href="report_suite_manifest.json">report-suite manifest</a>.</p></section>'
    body += '<section><h2>Saved models</h2><div class="callout"><strong>Forecast-ready research bundles.</strong> '
    body += 'The <a href="../final/catalogue.json">saved-model catalogue</a> indexes all 16 target × lead-band bundles. '
    body += f'Use the <a href="../../../../docs/{CONNECTOR["name"]}_SAVED_MODEL_GUIDE.md">saved-model guide</a> for the hash-verified '
    body += '<code>forecast-model</code> command, Python API, input schema and deployment status.</div></section>'
    body += '<section><h2>Where the run artifacts live</h2><div class="table-wrap" tabindex="0"><table><thead><tr>'
    body += '<th>Folder</th><th>Area</th><th>Purpose</th><th>Files</th><th>MB</th></tr></thead><tbody>'
    for row in rows:
        body += f"<tr><td><code>{row['folder']}/</code></td><td>{row['label']}</td><td>{row['purpose']}</td><td>{row['file_count']}</td><td>{row['size_mb']:.2f}</td></tr>"
    body += "</tbody></table></div></section>"
    body += '<section><h2>Reading the evidence</h2><p>The point-model pages contain actual-versus-forecast charts and MAPE-first/MAE-second tables. The model explorer holds cell-level Optuna ranges, completed trials and parameters. The NOS page separates descriptive outage burden from supported matched effects. The handoff page identifies the selected trained bundles and preserves the historical-development limitation.</p></section>'
    target = REPORT / "index.html"
    target.write_text(render_page(f"{CONNECTOR['name']} model run centre", body, plotly=False), encoding="utf-8")
    return target


def _compatibility_page(title: str, target: str) -> str:
    body = hero(
        f"{CONNECTOR['name']} forecasting research",
        "Report moved",
        title,
        "The completed report now lives in the organised report suite. This compatibility page keeps the former path usable.",
        ["Offline report", "Completed cached run"],
    )
    body += f'<section><h2>Open report</h2><p><a href="{target}">Continue to {title}</a>.</p></section>'
    return render_page(f"{CONNECTOR['name']} · {title}", body, plotly=False)


def build_report_suite(config_path: str = CONFIG_PATH) -> Path:
    global RUN, REPORT, PAGES, FULL, DOWNLOADS, QA, CONNECTOR, SLUG, CONFIG_PATH
    config=load_config(config_path);RUN=config['_run'];REPORT=RUN/'report';PAGES=REPORT/'pages';FULL=REPORT/'full_run';DOWNLOADS=REPORT/'downloads';QA=REPORT/'qa'
    CONNECTOR=config['connectors'][0];SLUG=CONNECTOR['name'].lower();CONFIG_PATH=config_path
    PAGES.mkdir(parents=True, exist_ok=True)
    FULL.mkdir(parents=True, exist_ok=True)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    source_path = REPORT / f"{SLUG}_diurnal_nos_model_report.html"
    nos_path = REPORT / "nos_outage_impact_analysis.html"
    if not source_path.exists() or not nos_path.exists():
        raise FileNotFoundError(f"Build the full {CONNECTOR['name']} and NOS reports before building the suite")

    full_source = FULL / source_path.name
    full_nos = FULL / nos_path.name
    # After the first suite build the former root paths are lightweight
    # compatibility pages.  Direct suite-only rebuilds therefore read the
    # retained full reports instead of trying to split the compatibility page.
    report_source = source_path if source_path.stat().st_size > 1_000_000 else full_source
    nos_source = nos_path if nos_path.stat().st_size > 1_000_000 else full_nos
    if report_source != full_source:
        shutil.copy2(report_source, full_source)
    if nos_source != full_nos:
        shutil.copy2(nos_source, full_nos)
    for name, target_name in (("model_results.csv", "model_results.csv"), ("build.json", "source_build.json"), ("nos_impact_build.json", "nos_impact_build.json")):
        source = REPORT / name
        if source.exists():
            shutil.copy2(source, DOWNLOADS / target_name)

    source = BeautifulSoup(report_source.read_text(encoding="utf-8"), "html.parser")
    pages = [_focused_page(source, *spec) for spec in PAGE_SPECS]

    QA.mkdir(parents=True, exist_ok=True)
    for pattern in ("visual_qa*", "vni_report_*.png"):
        for path in REPORT.glob(pattern):
            path.replace(QA / path.name)

    rows = _artifact_catalog()
    _write_catalog(rows)
    index = _index(rows, pages)
    outputs = [index, *pages, full_source, full_nos]
    manifest = {
        "run": config['campaign'],
        "source_report": str(full_source.relative_to(ROOT)).replace("\\", "/"),
        "rebuild_command": f"python scripts/build_qni_report_suite.py" if SLUG=='qni' else "python scripts/build_vni_report_suite.py",
        "pages": [
            {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": _sha(path), "bytes": path.stat().st_size}
            for path in outputs
        ],
        "artifact_catalog": rows,
    }
    (REPORT / "report_suite_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    source_path.write_text(
        _compatibility_page("complete model report", "full_run/vni_diurnal_nos_model_report.html"),
        encoding="utf-8",
    )
    nos_path.write_text(
        _compatibility_page("matched NOS impact report", "full_run/nos_outage_impact_analysis.html"),
        encoding="utf-8",
    )
    for legacy_download in (REPORT / "model_results.csv", REPORT / "build.json", REPORT / "nos_impact_build.json"):
        if legacy_download.exists():
            legacy_download.unlink()
    return index


if __name__ == "__main__":
    parser=argparse.ArgumentParser();parser.add_argument('--config',default=CONFIG_PATH)
    print(build_report_suite(parser.parse_args().config))
