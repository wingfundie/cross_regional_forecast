"""Cached-evidence Markdown and self-contained editorial HTML report."""
from __future__ import annotations

from base64 import b64encode
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
import csv
import json
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from nemic.experiments.core import ROOT, clean, digest
from scripts.report_theme.report_theme import (
    finding,
    figure_html,
    hero,
    matplotlib_style,
    metric,
    render_page,
)
from .config import code_manifest
from .protocol import holm_adjust


REPORT_DIR = ROOT / "reports/qni_vni_clustering_v1"


def _atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _collect(config: dict) -> dict:
    root = config["_run"]
    inventory = _load_json(root / "inventory.json")
    pilot = _load_json(root / "pilot/VNI/summary.json")
    point = []
    for path in sorted(root.glob("**/result.json")):
        payload = _load_json(path)
        if payload and "scores" in payload and "effects" in payload:
            point.append({"path": path, "payload": payload})
    state = []
    for path in sorted(root.glob("**/state_diagnostics.json")) + sorted(root.glob("state/*/*/result.json")):
        payload = _load_json(path)
        if payload:
            state.append({"path": path, "payload": payload})
    generator = []
    for path in sorted(root.glob("**/generator/result.json")):
        payload = _load_json(path)
        if payload:
            generator.append({"path": path, "payload": payload})
    risk = []
    for path in sorted(root.glob("risk/*/*/result.json")):
        payload = _load_json(path)
        if payload:
            risk.append({"path": path, "payload": payload})
    return {
        "inventory": inventory,
        "pilot": pilot,
        "point": point,
        "state": state,
        "generator": generator,
        "risk": risk,
    }


def _effect_rows(evidence: dict) -> list[dict]:
    rows = []
    for item in evidence["point"]:
        payload = item["payload"]
        for block, result in payload.get("effects", {}).items():
            if result.get("status") != "measured":
                continue
            rows.append({
                "connector": payload.get("connector"),
                "fold": payload.get("fold", {}).get("name"),
                "band": payload.get("band"),
                "target": payload.get("target"),
                "cluster_model": payload.get("cluster_winner"),
                "control_model": payload.get("control_winner"),
                "block_days": int(block),
                "effect_mae": result.get("effect_mae"),
                "effect_percent": result.get("effect_percent"),
                "ci_low": (result.get("effect_percent_ci95") or [None, None])[0],
                "ci_high": (result.get("effect_percent_ci95") or [None, None])[1],
                "p_value": result.get("p_value_two_sided"),
                "holm_p_value": None,
                "rows": result.get("rows"),
                "origins": result.get("origins"),
            })
    primary = [index for index, row in enumerate(rows) if row["block_days"] == 7]
    if primary:
        adjusted = holm_adjust([rows[index]["p_value"] for index in primary])
        for index, value in zip(primary, adjusted):
            rows[index]["holm_p_value"] = float(value) if np.isfinite(value) else None
    return rows


def _generator_effect_rows(evidence: dict) -> list[dict]:
    rows = []
    for item in evidence["generator"]:
        payload = item["payload"]
        for ablation in payload.get("ablations", []):
            if ablation.get("status") != "complete":
                continue
            effect = ablation.get("effects", {}).get("7", {})
            winner = ablation.get("winner", {})
            control = ablation.get("control", {})
            rows.append({
                "connector": payload.get("connector"),
                "fold": payload.get("fold", {}).get("name"),
                "target": ablation.get("target"),
                "band": ablation.get("band"),
                "representation": winner.get("representation"),
                "challenger_family": winner.get("family"),
                "control_family": control.get("family"),
                "effect_percent": effect.get("effect_percent"),
                "ci_low": (effect.get("effect_percent_ci95") or [None, None])[0],
                "ci_high": (effect.get("effect_percent_ci95") or [None, None])[1],
                "rows": ablation.get("rows"),
            })
    return rows


def _table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return '<div class="callout scope-note">No measured rows are available for this section yet.</div>'
    header = "".join(f"<th>{escape(label)}</th>" for key, label in columns)
    body = []
    for row in rows:
        cells = []
        for key, _ in columns:
            value = row.get(key)
            if value is None or (isinstance(value, float) and not np.isfinite(value)):
                text = "—"
            elif isinstance(value, float):
                text = f"{value:,.3f}"
            else:
                text = str(value)
            cells.append(f"<td>{escape(text)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="table-wrap" tabindex="0"><table><thead><tr>{header}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _png_data(fig) -> str:
    stream = BytesIO()
    fig.savefig(stream, format="png", bbox_inches="tight", dpi=160)
    plt.close(fig)
    return "data:image/png;base64," + b64encode(stream.getvalue()).decode("ascii")


def _effect_chart(rows: list[dict]) -> str | None:
    measured = [row for row in rows if row["block_days"] == 7]
    if not measured:
        return None
    with plt.rc_context(matplotlib_style()):
        fig, axis = plt.subplots(figsize=(10.5, max(3.8, len(measured) * 0.34 + 1.5)))
        labels = [f"{r['connector']} · {r['target']} · band {r['band']} · {r['fold']}" for r in measured]
        values = np.asarray([r["effect_percent"] for r in measured], dtype=float)
        low = np.asarray([r["ci_low"] for r in measured], dtype=float)
        high = np.asarray([r["ci_high"] for r in measured], dtype=float)
        y = np.arange(len(measured))
        axis.barh(y, values, color="#5696b9")
        finite = np.isfinite(low) & np.isfinite(high) & np.isfinite(values)
        axis.errorbar(values[finite], y[finite], xerr=[values[finite] - low[finite], high[finite] - values[finite]], fmt="none", ecolor="#282b30", capsize=3)
        axis.axvline(0, color="#66717e", linewidth=1)
        axis.set_yticks(y, labels)
        axis.invert_yaxis()
        axis.set_xlabel("MAE effect versus matched control (%) — positive favours clustering")
        axis.set_title("Held-out clustering effect estimates")
        return _png_data(fig)


def _state_rows(evidence: dict) -> list[dict]:
    rows = []
    for item in evidence["state"]:
        payload = item["payload"]
        for candidate in payload.get("candidates", []):
            rows.append({
                "connector": payload.get("connector", "VNI"),
                "fold": payload.get("fold", {}).get("name"),
                "method": candidate.get("method"),
                "k": candidate.get("k"),
                "seed_ari": candidate.get("seed_mean_ari"),
                "block_ari": candidate.get("block_mean_ari"),
                "recurring": candidate.get("recurring_regimes"),
            })
    return rows


def _write_downloads(evidence: dict, effects: list[dict], state_rows: list[dict]) -> list[Path]:
    downloads = REPORT_DIR / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    effect_path = downloads / "forecast_effects.csv"
    with effect_path.open("w", newline="", encoding="utf-8") as handle:
        fields = list(effects[0]) if effects else ["connector", "fold", "band", "target", "effect_percent"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(effects)
    state_path = downloads / "state_stability.csv"
    with state_path.open("w", newline="", encoding="utf-8") as handle:
        fields = list(state_rows[0]) if state_rows else ["connector", "fold", "method", "k", "seed_ari", "block_ari", "recurring"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(state_rows)
    compact_path = downloads / "compact_evidence.json"
    compact = {
        "pilot": evidence["pilot"],
        "forecast_effects": effects,
        "state_stability": state_rows,
        "generator_jobs": [item["payload"] for item in evidence["generator"]],
        "risk_jobs": [item["payload"] for item in evidence["risk"]],
    }
    _atomic_text(compact_path, json.dumps(clean(compact), indent=2, allow_nan=False))
    return [effect_path, state_path, compact_path]


def build_report(config: dict) -> dict:
    evidence = _collect(config)
    if evidence["inventory"] is None:
        raise ValueError("Run inventory before rendering the report")
    effects = _effect_rows(evidence)
    generator_effects = _generator_effect_rows(evidence)
    state_rows = _state_rows(evidence)
    downloads = _write_downloads(evidence, effects, state_rows)
    measured = [row for row in effects if row["block_days"] == 7]
    positive = sum((row.get("effect_percent") or 0) > 0 for row in measured)
    recurring = max([int(row.get("recurring") or 0) for row in state_rows] or [0])
    connectors = sorted({row.get("connector") for row in measured if row.get("connector")})
    pilot = evidence["pilot"] or {}
    status = "Pilot evidence available" if pilot else "Inventory complete; modelling pending"

    body = (
        "<style>html,body{overflow-x:hidden}"
        "@media(max-width:520px){.metrics{grid-template-columns:1fr}}</style>"
    )
    body += hero(
        "INTERFLOW · CLUSTERING RESEARCH",
        "Does clustering improve",
        "interconnector forecasts?",
        "A leakage-controlled comparison of clustered market states and generator sensitivities against matched QNI/VNI forecasting controls. Forecast effects and explanatory regimes are judged separately.",
        ["Retrospective development evidence", "VNI first · QNI replication", "Data cutoff 2026-09-01", "Not operational"],
    )
    body += (
        '<nav aria-label="Report sections"><a href="#answer">Answer</a><a href="#forecast">Forecast effects</a>'
        '<a href="#regimes">Regimes</a><a href="#generator">Generator groups</a>'
        '<a href="#risk">Contraction warnings</a><a href="#methods">Methods & limitations</a>'
        '<a href="#downloads">Downloads</a></nav>'
    )
    body += '<div class="metrics">' + "".join([
        metric("Campaign status", status, "Derived from cached artifacts"),
        metric("Forecast cells measured", len(measured), "Seven-day block comparison rows"),
        metric("Positive MAE effects", f"{positive}/{len(measured)}" if measured else "—", "Positive favours clustering; not a promotion gate"),
        metric("Recurring regimes", recurring if state_rows else "—", "Maximum per evaluated candidate under ARI/support rules"),
    ]) + "</div>"
    body += (
        '<div class="callout">The primary feature history uses retrospective network state and publication-time proxies. '
        'The results estimate historical development effects; they do not establish live issue-time performance.</div>'
    )
    body += '<section id="answer"><div class="section-kicker">DIRECT ANSWER</div><h2>What the experiment can say</h2><div class="findings">'
    body += finding(1, "Forecast value is measured, not assumed", f"{len(measured)} matched forecast comparisons are currently available. Every result uses the same finite evaluation rows for clustered and control predictions.")
    body += finding(2, "Explanation has an independent bar", f"The strongest evaluated candidate currently supports {recurring} recurring regimes under the predeclared stability and day-support convention.")
    body += finding(3, "A favourable pilot is not deployment evidence", "Historical inputs include publication proxies, prior modelling work touched the same era, and QNI replication plus later unseen-data confirmation remain separate gates.")
    body += "</div></section>"

    body += '<section id="forecast"><div class="section-kicker">01 · FORECAST EFFECTS</div><h2>Clustered models versus matched controls</h2>'
    chart = _effect_chart(effects)
    if chart:
        body += figure_html(f'<img src="{chart}" alt="Horizontal bars of clustering MAE effect estimates">', "Held-out MAE effect with 95% moving-block intervals", "Positive values favour the clustered challenger. Intervals reflect historical block resampling, not future-market uncertainty.", "downloads/forecast_effects.csv")
    body += _table(measured, [("connector", "Connector"), ("fold", "Fold"), ("target", "Target"), ("band", "Band"), ("cluster_model", "Cluster model"), ("control_model", "Matched control"), ("effect_percent", "MAE effect %"), ("ci_low", "CI low"), ("ci_high", "CI high"), ("p_value", "Raw p"), ("holm_p_value", "Holm p"), ("origins", "Origins")])
    body += "</section>"

    body += '<section id="regimes"><div class="section-kicker">02 · EXPLANATORY REGIMES</div><h2>Stability and independent-day support</h2>'
    body += _table(state_rows, [("connector", "Connector"), ("fold", "Fold"), ("method", "Method"), ("k", "K"), ("seed_ari", "Seed ARI"), ("block_ari", "Block ARI"), ("recurring", "Recurring regimes")])
    body += '<p class="note">Recurring means median ARI at least 0.70 plus at least 30 training days and 14 evaluation days for the regime. Calendar and missingness profiles remain required before physical interpretation.</p></section>'

    generator_rows = [{
        "connector": item["payload"].get("connector"), "fold": item["payload"].get("fold", {}).get("name"),
        "versions": item["payload"].get("matrix", {}).get("training_version_count"),
        "duids": item["payload"].get("matrix", {}).get("duid_count"),
        "representations": ", ".join(item["payload"].get("representations", [])),
    } for item in evidence["generator"]]
    body += '<section id="generator"><div class="section-kicker">03 · GENERATOR GROUPS</div><h2>Signed equation/DUID representations</h2>'
    body += _table(generator_rows, [("connector", "Connector"), ("fold", "Fold"), ("versions", "Training versions"), ("duids", "DUIDs"), ("representations", "Representations")])
    body += _table(generator_effects, [("connector", "Connector"), ("fold", "Fold"), ("target", "Target"), ("band", "Band"), ("representation", "Winning representation"), ("challenger_family", "Challenger family"), ("control_family", "Matched control family"), ("effect_percent", "MAE effect %"), ("ci_low", "CI low"), ("ci_high", "CI high"), ("rows", "Rows")])
    body += '<p class="note">Manual groups, K-means groups and signed SVD components are fitted inside each training fold. Tightening and relief remain separate; unsupported equation versions stay missing.</p></section>'

    risk_rows = []
    for item in evidence["risk"]:
        payload = item["payload"]
        for row in payload.get("results", []):
            event = row.get("events", {})
            paired = payload.get("paired_recall", {}).get(row.get("direction")) or {}
            risk_rows.append({
                "connector": payload.get("connector"), "fold": payload.get("fold", {}).get("name"),
                "model": row.get("model"), "direction": row.get("direction"),
                "incidents": event.get("incidents"), "recall": event.get("recall"),
                "precision": event.get("precision"), "false_alerts": event.get("false_alarms_per_day"),
                "recall_delta": paired.get("recall_difference") if row.get("model") == "cluster" else None,
                "delta_low": (paired.get("recall_difference_ci95") or [None, None])[0] if row.get("model") == "cluster" else None,
                "delta_high": (paired.get("recall_difference_ci95") or [None, None])[1] if row.get("model") == "cluster" else None,
            })
    body += '<section id="risk"><div class="section-kicker">04 · CONTRACTION WARNINGS</div><h2>Thirty-to-120-minute advance warnings</h2>'
    body += _table(risk_rows, [("connector", "Connector"), ("fold", "Fold"), ("model", "Model"), ("direction", "Direction"), ("incidents", "Incidents"), ("recall", "Recall"), ("precision", "Precision"), ("false_alerts", "False alerts/day"), ("recall_delta", "Cluster recall Δ"), ("delta_low", "Δ CI low"), ("delta_high", "Δ CI high")])
    body += "</section>"

    coverage = evidence["inventory"].get("coverage", [])
    coverage_rows = [{
        "connector": row.get("connector"), "rows": row.get("rows"), "origins": row.get("origins"),
        "origin_start": row.get("origin_start"), "origin_end": row.get("origin_end"),
        "columns": row.get("columns"), "provenance": ", ".join(row.get("provenance", [])),
    } for row in coverage]
    body += '<section id="methods"><div class="section-kicker">05 · METHODS & LIMITATIONS</div><h2>What was fitted and what remains uncertain</h2><div class="method">'
    body += '<p>Every preprocessing step, cluster solution, generator representation and model is fitted within an expanding chronological training partition. Selection, calibration, alert tuning and evaluation are disjoint; delivery plus 30 minutes must mature before a partition boundary. Origin-state clustering fits one row per origin.</p>'
    body += '<p>The core state candidates are K=1, K-means and diagonal Gaussian mixtures. Generator candidates are four study-informed groups, K-means at four/eight groups and signed SVD at four/eight components. Forecasts compare pooled probability features, regularised interactions and local experts with pooled OOD fallback.</p>'
    body += '<p>Reported interconnector limits are dispatch-solution outputs rather than maximum secure physical transfer capability. Existing history has informed earlier development, so this is not a wholly untouched final test. Weather is excluded from the primary PASA/coal track. Future realised inputs, if added, remain a separately labelled conditional diagnostic.</p></div>'
    body += _table(coverage_rows, [("connector", "Connector"), ("rows", "Rows"), ("origins", "Origins"), ("origin_start", "Origin start"), ("origin_end", "Origin end"), ("columns", "Columns"), ("provenance", "Provenance")])
    body += "</section>"

    body += '<section id="downloads"><div class="section-kicker">06 · DOWNLOADS & REPRODUCIBILITY</div><h2>Compact evidence</h2><ul>'
    for path in downloads:
        body += f'<li><a href="downloads/{escape(path.name, quote=True)}" download>{escape(path.name)}</a> · SHA-256 {digest(path)}</li>'
    body += '</ul><p class="note">Rebuild: <code>python -m nemic.experiments.clustering report</code>. The renderer reads cached results only and never trains models.</p></section>'
    body += '<footer>Generated ' + escape(datetime.now(timezone.utc).isoformat()) + ' · Campaign qni_vni_clustering_v1 · Research only</footer>'

    html_path = REPORT_DIR / "Clustering_Research.html"
    markdown_path = REPORT_DIR / "Clustering_Research.md"
    _atomic_text(html_path, render_page("QNI/VNI clustering research", body, plotly=False, accent="purple"))

    markdown = [
        "# QNI/VNI clustering research",
        "",
        "> Retrospective development evidence using publication-time proxies. Not operationally eligible.",
        "",
        "## Direct answer",
        "",
        f"The cached campaign currently contains {len(measured)} measured seven-day-block forecast comparisons. "
        f"Clustering has a positive point estimate in {positive} of them. This is an effect estimate, not a model-promotion decision.",
        "",
        f"The strongest evaluated explanatory candidate supports {recurring} recurring regimes under the predeclared ARI and independent-day convention.",
        "",
        "## Forecast effects",
        "",
    ]
    if measured:
        markdown += ["| Connector | Fold | Target | Band | Cluster model | Control | Effect % | 95% interval | Holm p |", "|---|---|---|---:|---|---|---:|---|---:|"]
        for row in measured:
            adjusted = "—" if row["holm_p_value"] is None else f"{row['holm_p_value']:.4f}"
            markdown.append(f"| {row['connector']} | {row['fold']} | {row['target']} | {row['band']} | {row['cluster_model']} | {row['control_model']} | {row['effect_percent']:.3f} | [{row['ci_low']:.3f}, {row['ci_high']:.3f}] | {adjusted} |")
    else:
        markdown.append("No forecast cell has completed yet.")
    markdown += [
        "", "## Generator grouping effects", "",
    ]
    if generator_effects:
        markdown += ["| Connector | Fold | Target | Band | Representation | Families | Effect % | 95% interval |", "|---|---|---|---:|---|---|---:|---|"]
        for row in generator_effects:
            markdown.append(f"| {row['connector']} | {row['fold']} | {row['target']} | {row['band']} | {row['representation']} | {row['challenger_family']} vs {row['control_family']} | {row['effect_percent']:.3f} | [{row['ci_low']:.3f}, {row['ci_high']:.3f}] |")
    else:
        markdown.append("No generator-group ablation has completed yet.")
    markdown += [
        "", "## Contraction warning comparison", "",
    ]
    clustered_risk = [row for row in risk_rows if row["model"] == "cluster"]
    if clustered_risk:
        markdown += ["| Connector | Fold | Direction | Recall | Precision | False alerts/day | Recall difference | 95% interval |", "|---|---|---|---:|---:|---:|---:|---|"]
        for row in clustered_risk:
            def format_metric(value):
                return "—" if value is None or not np.isfinite(value) else f"{value:.3f}"
            interval = f"[{format_metric(row['delta_low'])}, {format_metric(row['delta_high'])}]"
            markdown.append(f"| {row['connector']} | {row['fold']} | {row['direction']} | {format_metric(row['recall'])} | {format_metric(row['precision'])} | {format_metric(row['false_alerts'])} | {format_metric(row['recall_delta'])} | {interval} |")
    else:
        markdown.append("No contraction-warning comparison has completed yet.")
    markdown += [
        "", "## Methods and limitations", "",
        "Clustering, preprocessing and compression are fitted inside each chronological training partition. Selection, calibration, alert tuning and evaluation remain disjoint, and delivery maturity is purged at each boundary.",
        "",
        "The primary history is retrospective development evidence: PASA generated time is a publication proxy, coal metadata include retrospective elements, and earlier research touched the same historical era. Reported limits are dispatch-solution outputs, not physical transfer capability.",
        "",
        "## Reproduction", "",
        "- Inventory: `python -m nemic.experiments.clustering inventory`",
        "- VNI pilot: `python -m nemic.experiments.clustering pilot --connector VNI`",
        "- Cached report: `python -m nemic.experiments.clustering report`",
        "",
    ]
    _atomic_text(markdown_path, "\n".join(markdown))

    input_paths = [item["path"] for group in (evidence["point"], evidence["state"], evidence["generator"], evidence["risk"]) for item in group]
    if (config["_run"] / "inventory.json").exists():
        input_paths.append(config["_run"] / "inventory.json")
    manifest = {
        "campaign": config["campaign"],
        "built_at": datetime.now(timezone.utc).isoformat(),
        "data_cutoff": config["end"],
        "claim": config["claims"]["primary"],
        "rebuild": "python -m nemic.experiments.clustering report",
        "inputs": [{"path": str(path.relative_to(ROOT)), "sha256": digest(path)} for path in sorted(set(input_paths))],
        "code": code_manifest(),
        "outputs": [
            {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}
            for path in [html_path, markdown_path, *downloads]
        ],
    }
    manifest_path = REPORT_DIR / "manifest.json"
    _atomic_text(manifest_path, json.dumps(clean(manifest), indent=2, allow_nan=False))
    # Keep a content-addressed pointer under the ignored campaign root.
    pointer = config["_run"] / "report/manifest.json"
    _atomic_text(pointer, json.dumps({
        "report_manifest": str(manifest_path.relative_to(ROOT)),
        "report_manifest_sha256": digest(manifest_path),
        "html": str(html_path.relative_to(ROOT)),
        "html_sha256": digest(html_path),
    }, indent=2))
    return {"html": html_path, "markdown": markdown_path, "manifest": manifest_path, "forecast_cells": len(measured)}


def validate_report(config: dict) -> dict:
    manifest_path = REPORT_DIR / "manifest.json"
    manifest = _load_json(manifest_path)
    if manifest is None:
        raise FileNotFoundError("Build the clustering report first")
    errors = []
    for item in [*manifest.get("inputs", []), *manifest.get("outputs", [])]:
        path = ROOT / item["path"]
        if not path.exists():
            errors.append(f"missing output: {item['path']}")
        elif digest(path) != item["sha256"]:
            errors.append(f"hash mismatch: {item['path']}")
    html_path = REPORT_DIR / "Clustering_Research.html"
    html = html_path.read_text(encoding="utf-8")
    ids = re.findall(r'\bid="([^"]+)"', html)
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        errors.append(f"duplicate anchors: {duplicates}")
    anchors = set(ids)
    for href in re.findall(r'href="([^"]+)"', html):
        if href.startswith("#") and href[1:] not in anchors:
            errors.append(f"missing anchor: {href}")
        elif not href.startswith(("#", "http://", "https://", "data:")):
            target = (REPORT_DIR / href).resolve()
            if not target.exists():
                errors.append(f"missing local link: {href}")
    if re.search(r'<(?:script|link)[^>]+(?:src|href)="https?://', html):
        errors.append("external rendering dependency")
    return {
        "valid": not errors,
        "errors": errors,
        "html": html_path,
        "manifest": manifest_path,
        "visual_qa": "separate browser check required",
    }
