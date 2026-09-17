"""Offline editorial reports generated only from supplied run/evaluation artifacts."""
from html import escape
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go

from scripts.report_theme.report_theme import hero, metric, figure_html, style_plotly, render_page
from .contracts import digest, write_json
from .training import metrics


def report(frame, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    links = []
    for name, rows in frame.groupby("connector"):
        body = hero("Interconnector forecast", name, "Limits and uncertainty", "Forecasts reflect the registered model and supplied inputs. Research and synthetic runs are not production evidence.",
                    [f"Origin: {rows.origin.iloc[0]}", f"Scenario: {rows.scenario.iloc[0]}", f"Routing: {rows.routing_version.iloc[0]}"])
        body += '<div class="metrics">' + metric("Requested intervals", len(rows), "All targets combined") + metric("Completed", int(rows.status.eq("complete").sum()), "Unavailable intervals remain explicit") + '</div>'
        body += '<section><h2>Forecast curves</h2>'
        for target, group in rows.groupby("target"):
            fig = go.Figure()
            if "forecast_mw" in group:
                fig.add_trace(go.Scatter(x=group.delivery, y=group.forecast_mw, name="Forecast"))
                for q in ("p10_mw", "p90_mw"):
                    if q in group:
                        fig.add_trace(go.Scatter(x=group.delivery, y=group[q], name=q, line=dict(dash="dot")))
            if "actual" in group:
                fig.add_trace(go.Scatter(x=group.delivery, y=group.actual, name="Actual"))
                if "forecast_mw" in group:
                    body += '<div class="table-wrap">' + pd.DataFrame([metrics(group.actual, group.forecast_mw)]).to_html(index=False) + '</div>'
            style_plotly(fig, target, height=450)
            fig.update_yaxes(title="Directional limit (MW)")
            body += figure_html(fig.to_html(full_html=False, include_plotlyjs=False), target,
                                "Half-hour limits. Days 8–30 are an outlook. Gaps mean unavailable forecasts.")
        body += '</section><section><h2>Model selection and coverage</h2><div style="overflow:auto">'
        cols = [c for c in ("target", "model", "recipe", "eligibility", "status", "selection", "reason") if c in rows]
        body += rows[cols].value_counts(dropna=False).reset_index(name="intervals").to_html(index=False, escape=True)
        body += '</div></section><section><h2>Method and limitations</h2><p>Routes select explicitly configured compatible models. Hourly bounds are withheld until independently calibrated. Outage associations are not causal estimates. Forecast weather interpolation does not increase source resolution.</p></section>'
        filename = f"{name.lower()}.html"
        (folder / filename).write_text(render_page(f"{name} forecast", body), encoding="utf-8")
        links.append(f'<li><a href="{filename}">{escape(name)}</a></li>')
    body = hero("Forecast run", "Interconnector models", "Run reports", "Connector reports include completed forecasts and explicit coverage gaps.", [])
    body += '<ul>' + ''.join(links) + '</ul>'
    (folder / "index.html").write_text(render_page("Forecast reports", body, plotly=False), encoding="utf-8")
    write_json(folder / "report_manifest.json", {"generator": "nemic.production.reports", "version": 1,
               "rows": len(frame), "files": {p.name: digest(p) for p in folder.glob("*.html")},
               "rebuild": "python -m nemic.production report --input forecasts.parquet --output REPORT_DIR"})
    return folder / "index.html"


def training_report(package):
    from .contracts import read_json
    path = Path(package)
    evaluation = read_json(path / "evaluation.json")
    explanations = read_json(path / "explanations.json")
    manifest = read_json(path / "manifest.json")
    body = hero("Model development", manifest["id"], "Chronological evaluation", "Selection uses rolling MAE. Calibration is held out from model fitting, but requires subsequent coverage validation.", [manifest["status"], manifest["family"]])
    body += '<section><h2>Models tested</h2><div class="table-wrap">' + pd.DataFrame(evaluation["models"]).to_html(index=False) + '</div></section>'
    pred = pd.read_csv(path / "validation_predictions.csv")
    for name, rows in pred.groupby("model"):
        fig = go.Figure()
        for column in ("actual", "forecast_mw"):
            fig.add_trace(go.Scatter(x=rows.delivery, y=rows[column], name=column))
        style_plotly(fig, name)
        body += figure_html(fig.to_html(full_html=False, include_plotlyjs=False), f"{name}: actual vs forecast", "Rolling held-out point predictions; repeated deliveries can have different origins.")
    body += '<section><h2>Selected model feature importance</h2><div class="table-wrap">' + pd.Series(explanations["permutation_mae_increase"], name="MAE increase (MW)").to_frame().to_html() + '</div></section>'
    body += '<section><h2>SHAP decomposition</h2><p>' + escape(explanations["method"]) + '</p>'
    body += '<div class="table-wrap">' + pd.DataFrame(explanations["shap_values"], columns=explanations["features"]).head(20).to_html(index=False) + '</div></section>'
    if (path / "all_explanations.json").exists():
        for family, explanation in read_json(path / "all_explanations.json").items():
            importance = explanation["permutation_mae_increase"]
            fig = go.Figure(go.Bar(x=list(importance.values()), y=list(importance), orientation="h"))
            style_plotly(fig, f"{family}: feature importance", height=max(420, len(importance) * 24))
            fig.update_xaxes(title="Held-out MAE increase (MW)")
            body += figure_html(fig.to_html(full_html=False, include_plotlyjs=False), f"{family}: feature relevance", "Permutation importance reflects predictive association, not causality.")
            body += '<section><h3>' + escape(family) + ' SHAP contributions</h3><div style="overflow:auto">'
            body += pd.DataFrame(explanation["shap_values"], columns=explanation["features"]).head(10).to_html(index=False) + '</div></section>'
    body += '<section><h2>Verdict and parameters</h2><p>Selected on ' + escape(evaluation["selection_metric"]) + ': ' + escape(evaluation["selection"]) + '. Research status; no automatic production promotion.</p><pre style="overflow:auto">' + escape(str(manifest["parameters"])) + '</pre></section>'
    (path / "research_report.html").write_text(render_page("Model development", body), encoding="utf-8")
    return path / "research_report.html"
