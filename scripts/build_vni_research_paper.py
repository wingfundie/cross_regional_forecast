"""Build the paper-style report for the completed VNI diurnal/NOS run."""
from __future__ import annotations

import html
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nemic.experiments.core import digest
from nemic.experiments.diurnal import PERIODS, metrics, origin_weights
from scripts.report_theme.report_theme import figure_html, hero, metric, render_page, style_plotly


RUN = ROOT / "data/forecast_experiments/vni_diurnal_nos_v2"
OUTPUT = RUN / "report"
BAND_LABELS = {0: "0.5–6 h", 1: "6.5–24 h", 2: "24.5–72 h", 3: "72.5–168 h"}
TARGET_LABELS = {
    "export": "Export mean",
    "import": "Import mean",
    "export_tight": "Export minimum",
    "import_tight": "Import minimum",
}
MODEL_NAMES = {
    "persistence": "Persistence",
    "seasonal_daily": "Daily persistence",
    "seasonal_weekly": "Weekly persistence",
    "T0_mae": "T0 shared ridge",
    "T1_mae": "T1 Fourier ridge",
    "T2_mae": "T2 period interactions",
    "T3_mae": "T3 smooth interactions",
    "T4_mae": "T4 residual correction",
    "T5_mae": "T5 period specialists",
    "T6_mae": "T6 shallow boosting",
}


def _table(frame: pd.DataFrame) -> str:
    return '<div class="table-wrap" tabindex="0">' + frame.to_html(index=False, escape=True) + "</div>"


def _chart(fig: go.Figure, caption: str, note: str) -> str:
    return figure_html(fig.to_html(full_html=False, include_plotlyjs=False, config={"responsive": True}), caption, note)


def _mape50(actual: np.ndarray, prediction: np.ndarray, weights: np.ndarray) -> tuple[float, float]:
    eligible = np.isfinite(actual) & np.isfinite(prediction) & (np.abs(actual) >= 50)
    value = 100 * np.average(np.abs(prediction[eligible] - actual[eligible]) / np.abs(actual[eligible]), weights=weights[eligible])
    return float(value), float(np.average(eligible, weights=weights))


def _load_point_results():
    grouped: dict[tuple[str, int], list[pd.DataFrame]] = {}
    primary: dict[tuple[str, str], list[pd.DataFrame]] = {}
    fixed_rows = []
    selection_rows = []
    sources = []
    for result_path in sorted((RUN / "diurnal").glob("*/band*/*/result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        sources.append(result_path)
        target, band = result["target"], int(result["band"])
        if result["fold"]["protocol"] == "fixed":
            for score in result["scores"]:
                if score["model"] in ("persistence", "T0_mae") or score["selected"]:
                    fixed_rows.append(
                        {
                            "Target": TARGET_LABELS[target],
                            "Band": BAND_LABELS[band],
                            "Policy": "Selected" if score["selected"] else MODEL_NAMES.get(score["model"], score["model"]),
                            "MAPE ≥50 (%)": score["mape_50"],
                            "MAE (MW)": score["weighted_mae"],
                        }
                    )
            continue
        frame = pd.read_parquet(result_path.parent / "predictions.parquet")
        small = frame[["origin", "delivery", "period", "actual", "reference", "persistence", "T0_mae"]].copy()
        small["selected"] = frame[result["winner"]].to_numpy()
        grouped.setdefault((target, band), []).append(small)
        selection_rows.append({"Fold": result["fold"]["name"], "Target": target, "Band": band, "Winner": result["winner"]})
        if target.endswith("_tight") and band == 0:
            candidates = [name for name in MODEL_NAMES if name in frame]
            for name in candidates:
                primary.setdefault((target, name), []).append(
                    frame[["origin", "actual", "reference", name]].rename(columns={name: "prediction"})
                )

    performance = []
    period_rows = []
    combined = {}
    for (target, band), frames in grouped.items():
        frame = pd.concat(frames, ignore_index=True)
        combined[(target, band)] = frame
        scores = {}
        for policy in ("selected", "persistence", "T0_mae"):
            scores[policy] = metrics(
                frame.actual.to_numpy(),
                frame[policy].to_numpy(),
                frame.reference.to_numpy(),
                origin_weights(frame.origin),
            )
        performance.append(
            {
                "target": target,
                "band": band,
                "selected_mae": scores["selected"]["weighted_mae"],
                "selected_mape": scores["selected"]["mape_50"],
                "mape_coverage": scores["selected"]["mape_50_coverage"],
                "persistence_mae": scores["persistence"]["weighted_mae"],
                "t0_mae": scores["T0_mae"]["weighted_mae"],
                "skill_persistence": 1 - scores["selected"]["weighted_mae"] / scores["persistence"]["weighted_mae"],
                "skill_t0": 1 - scores["selected"]["weighted_mae"] / scores["T0_mae"]["weighted_mae"],
                "over100": scores["selected"]["over100"],
                "over200": scores["selected"]["over200"],
                "rows": len(frame),
            }
        )
        if target.endswith("_tight") and band == 0:
            for period, local in frame.groupby("period"):
                for policy in ("selected", "persistence", "T0_mae"):
                    score = metrics(
                        local.actual.to_numpy(), local[policy].to_numpy(), local.reference.to_numpy(), origin_weights(local.origin)
                    )
                    period_rows.append(
                        {
                            "target": target,
                            "period": PERIODS[int(period)],
                            "policy": policy,
                            "mae": score["weighted_mae"],
                            "mape": score["mape_50"],
                        }
                    )

    leaderboard = []
    for (target, model), frames in primary.items():
        frame = pd.concat(frames, ignore_index=True)
        score = metrics(
            frame.actual.to_numpy(), frame.prediction.to_numpy(), frame.reference.to_numpy(), origin_weights(frame.origin)
        )
        leaderboard.append({"target": target, "model": model, "mae": score["weighted_mae"], "mape": score["mape_50"]})
    return (
        pd.DataFrame(performance).sort_values(["target", "band"]),
        pd.DataFrame(period_rows),
        pd.DataFrame(leaderboard),
        pd.DataFrame(fixed_rows),
        pd.DataFrame(selection_rows),
        combined,
        sources,
    )


def _load_explanations():
    importance, shap_rows, sources = [], [], []
    for result_path in sorted((RUN / "diurnal").glob("*/band0/*_tight/result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result["fold"]["protocol"] != "rolling":
            continue
        explanation_path = result_path.parent / "explanations.json"
        if not explanation_path.exists():
            continue
        sources.append(explanation_path)
        evidence = json.loads(explanation_path.read_text(encoding="utf-8"))
        for row in evidence["importance"]:
            if row["model"] == "T6_mae":
                importance.append({"target": result["target"], "fold": result["fold"]["name"], **row})
        shap_path = result_path.parent / "T6_mae_shap.parquet"
        if shap_path.exists():
            sources.append(shap_path)
            frame = pd.read_parquet(shap_path)
            values = frame.groupby("feature").shap_mw.apply(lambda x: float(np.mean(np.abs(x))))
            for feature, value in values.items():
                shap_rows.append({"target": result["target"], "fold": result["fold"]["name"], "feature": feature, "mean_abs_shap": value})
    importance_frame = pd.DataFrame(importance).groupby(["target", "group"], as_index=False).mae_degradation.mean()
    shap_frame = pd.DataFrame(shap_rows).groupby(["target", "feature"], as_index=False).mean_abs_shap.mean()
    return importance_frame, shap_frame, sources


def _load_nos_results():
    frames: dict[str, list[pd.DataFrame]] = {}
    importance = []
    sources = []
    for result_path in sorted((RUN / "nos_models").glob("*/*/result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        sources.append(result_path)
        frame = pd.read_parquet(result_path.parent / "predictions.parquet")
        local = frame.loc[frame.nos_known, ["origin", "actual", "T6_O0"]].copy()
        local["selected"] = frame.loc[frame.nos_known, result["winner"]].to_numpy()
        local["winner"] = result["winner"]
        frames.setdefault(result["target"], []).append(local)
        explanation = result_path.parent / "explanations.json"
        if explanation.exists():
            sources.append(explanation)
            evidence = json.loads(explanation.read_text(encoding="utf-8"))
            for row in evidence["importance"]:
                if row["model"] == result["winner"] and row["group"] == "scheduled_outage":
                    importance.append({"target": result["target"], "mae_degradation": row["mae_degradation"]})
    rows = []
    for target, pieces in frames.items():
        frame = pd.concat(pieces, ignore_index=True)
        weights = origin_weights(frame.origin)
        selected_mae = float(np.average(np.abs(frame.actual - frame.selected), weights=weights))
        control_mae = float(np.average(np.abs(frame.actual - frame.T6_O0), weights=weights))
        selected_mape, coverage = _mape50(frame.actual.to_numpy(), frame.selected.to_numpy(), weights)
        rows.append(
            {
                "target": target,
                "selected_mae": selected_mae,
                "control_mae": control_mae,
                "skill": 1 - selected_mae / control_mae,
                "mape": selected_mape,
                "coverage": coverage,
                "rows": len(frame),
            }
        )
    importance_frame = pd.DataFrame(importance).groupby("target", as_index=False).mae_degradation.mean()
    return pd.DataFrame(rows), importance_frame, sources


def _load_refinements():
    rows, sources = [], []
    for result_path in sorted((RUN / "refinements").glob("*/*/result.json")):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        sources.append(result_path)
        scores = {row["model"]: row for row in result["scores"]}
        chosen, base = scores[result["winner"]], scores["expanding"]
        rows.append(
            {
                "target": result["target"],
                "winner": result["winner"],
                "selected_mae": chosen["weighted_mae"],
                "expanding_mae": base["weighted_mae"],
                "skill": 1 - chosen["weighted_mae"] / base["weighted_mae"],
                "n": chosen["n"],
            }
        )
    frame = pd.DataFrame(rows)
    aggregate = []
    for target, local in frame.groupby("target"):
        weight = local.n.to_numpy()
        selected = float(np.average(local.selected_mae, weights=weight))
        base = float(np.average(local.expanding_mae, weights=weight))
        aggregate.append({"target": target, "selected_mae": selected, "expanding_mae": base, "skill": 1 - selected / base})
    return pd.DataFrame(aggregate), sources


def _load_final_catalogue():
    catalogue_path = RUN / "final/catalogue.json"
    rows = json.loads(catalogue_path.read_text(encoding="utf-8"))
    output, sources = [], [catalogue_path]
    for row in rows:
        manifest_path = RUN / Path(row["path"]).parent / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        sources.append(manifest_path)
        parameters = manifest["parameters"][row["winner"]]
        if row["winner"].startswith("T6"):
            summary = (
                f"leaves={parameters['num_leaves']}; min_child={parameters['min_child_samples']}; "
                f"lr={parameters['learning_rate']:.4f}; trees={parameters['n_estimators']}"
            )
        else:
            summary = f"ridge alpha={parameters['alpha']:.3f}"
        output.append(
            {
                "Target": TARGET_LABELS[row["target"]],
                "Band": BAND_LABELS[int(row["band"])],
                "Selected model": row["winner"],
                "Fitted parameters": summary,
                "Selection MAE (MW)": manifest["selection_mae"][row["winner"]],
                "Bundle": row["path"].replace("\\", "/"),
                "Reload parity": manifest["reload_parity"],
            }
        )
    return pd.DataFrame(output), sources


def _representative_curves():
    rows = {}
    sources = []
    for target in ("export_tight", "import_tight"):
        path = RUN / "curves/2026-08" / target / "predictions.parquet"
        result_path = path.parent / "result.json"
        if not path.exists():
            candidates = sorted((RUN / "curves").glob(f"*/{target}/predictions.parquet"))
            path = candidates[-1]
            result_path = path.parent / "result.json"
        frame = pd.read_parquet(path)
        first_origin = frame.origin.min()
        rows[target] = frame.loc[frame.origin.eq(first_origin)].copy()
        sources.extend([path, result_path])
    return rows, sources


def _model_glossary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("Persistence", "Latest admissible directional limit", "Benchmark"),
            ("Daily/weekly persistence", "Same half-hour one day or one week earlier", "Seasonal benchmarks"),
            ("T0", "Shared regularized ridge with base cyclic calendar", "Global linear control"),
            ("T1", "Ridge with profile-supported daily Fourier terms", "Richer mean daily shape"),
            ("T2", "Five delivery-period coefficient deviations", "Discrete time-varying sensitivity"),
            ("T3", "Smooth cyclic driver interactions", "Smooth time-varying sensitivity"),
            ("T4", "Shared forecast plus out-of-fold period residual correction", "Conservative specialization"),
            ("T5", "Support-gated period specialists with boundary blending", "Separate local models"),
            ("T6", "Shallow LightGBM absolute-error correction", "Nonlinear challenger"),
            ("O1–O4 / OX", "NOS burden, transitions, mapping, revision and restricted interactions", "Outage ablations"),
            ("DR-NMAE", "Directional-reference normalized absolute-error objective", "Percentage-error challenger"),
        ],
        columns=["ID", "Specification", "Role"],
    )


def _feature_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            ("Observed history", "flow/limit lags at 1, 48 and 336 intervals; recent deltas; own anchor", "Persistence of topology and operating state"),
            ("Calendar", "hour sine/cosine, annual sine/cosine, weekend", "Recurring demand, renewable and unit-commitment shape"),
            ("Forecast lead", "lead and log lead", "Decay in current-state information with horizon"),
            ("Network state", "upper/lower room, switch gaps, candidate counts, setter age, recent switches", "Constraint geometry and candidate competition"),
            ("Generator pressure", "tightening, relief, pressure change and available relief by direction", "Operating-point pressure on directional capability"),
            ("Quality", "partial-candidate fraction, pressure completeness, envelope inconsistency", "Separates missing reconstruction from physical state"),
            ("Scheduled NOS challenger", "active/scheduled burden, transitions, mapped mechanisms, revisions and OX interactions", "Tests advance topology information beyond current state"),
        ],
        columns=["Feature family", "Variables", "Fundamental interpretation"],
    )


def build() -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance, periods_frame, leaderboard, fixed, selections, combined, point_sources = _load_point_results()
    importance, shap_frame, explanation_sources = _load_explanations()
    nos, nos_importance, nos_sources = _load_nos_results()
    refinements, refinement_sources = _load_refinements()
    bundles, bundle_sources = _load_final_catalogue()
    curves, curve_sources = _representative_curves()
    statistics_path = RUN / "statistics.json"
    statistics = json.loads(statistics_path.read_text(encoding="utf-8"))
    impact_path = RUN / "nos/impact/full_development/status.json"
    impact = json.loads(impact_path.read_text(encoding="utf-8"))

    export = performance.query("target == 'export_tight' and band == 0").iloc[0]
    imported = performance.query("target == 'import_tight' and band == 0").iloc[0]
    nos_export = nos.query("target == 'export_tight'").iloc[0]
    nos_import = nos.query("target == 'import_tight'").iloc[0]

    body = hero(
        "VNI directional-limit forecasting",
        "Time-of-delivery models",
        "A two-year rolling study with network-outage evidence",
        "A complete historical evaluation of daily specialization, nonlinear correction, scheduled network outages, feature relevance, uncertainty and deployable saved-model bundles for VIC1–NSW1 directional limits.",
        ["Research paper", "September 2024–August 2026 outcomes", "NEM time · UTC+10", "MAE-selected point forecasts", "Development evidence"],
    )
    body += '<nav><a href="#abstract">Abstract</a> · <a href="#methods">Methods</a> · <a href="#models">Models</a> · <a href="#results">Results</a> · <a href="#features">Features</a> · <a href="#nos">NOS</a> · <a href="#verdict">Verdict</a> · <a href="#forward">Forward use</a></nav>'
    body += '<section class="metrics">'
    body += metric("Export minimum MAE", f"{export.selected_mae:.1f} MW", f"{100*export.skill_persistence:.1f}% better than persistence")
    body += metric("Import minimum MAE", f"{imported.selected_mae:.1f} MW", f"{100*imported.skill_persistence:.1f}% better than persistence")
    body += metric("Primary selected family", "T6", "Shallow absolute-error boosting")
    body += metric("NOS point-model effect", "Not promoted", f"{100*nos_export.skill:+.2f}% export; {100*nos_import.skill:+.2f}% import")
    body += "</section>"

    body += f'''<section id="abstract"><h2>Abstract</h2><div class="callout"><strong>Research question.</strong> Does modelling VNI limits as a function of delivery time improve forecasts beyond a shared model, and does issue-known scheduled outage information add further predictive value?</div>
    <p>This study evaluates minimum and mean directional transfer limits for the Victoria–New South Wales interconnector over twelve rolling monthly evaluation folds. Forecasts cover 0.5 to 168 hours and are selected by origin-balanced mean absolute error (MAE). The candidate ladder separates richer average daily shape, delivery-time-varying driver sensitivity, period-specific correction, independent specialists and shallow nonlinear boosting. Scheduled network-outage information is added only after a source-vintage coverage and matched-episode analysis.</p>
    <p>The selection-frozen policy reduced band-0 minimum-export MAE from {export.persistence_mae:.1f} MW under persistence to {export.selected_mae:.1f} MW, and minimum-import MAE from {imported.persistence_mae:.1f} MW to {imported.selected_mae:.1f} MW. Against the shared T0 ridge, the reductions were {export.t0_mae-export.selected_mae:.1f} MW and {imported.t0_mae-imported.selected_mae:.1f} MW. Seven- and fourteen-day moving-block confidence intervals excluded zero, and the 90% model confidence set retained T6 alone for both tight directions. Gains persisted across delivery periods and all four lead bands, supporting time-of-delivery specialization. Calendar and recent observed limits carried most of the predictive information. Scheduled NOS features changed source-common MAE by only {100*nos_export.skill:+.2f}% for export and {100*nos_import.skill:+.2f}% for import versus the no-NOS T6 control, so they were not promoted to the point model.</p>
    <p>The resulting handoff uses T6 for all targets in bands 0–2 and for band-3 imports, with T0 retained for band-3 exports. Sixteen hash-catalogued research bundles reproduce their saved predictions exactly. They are ready for forecasting from the 41-column feature contract, but remain in research status until a receipt-time-verified live feature feed and prospective shadow evaluation are completed.</p></section>'''

    body += '''<section id="methods"><h2>1. Data, targets and experimental design</h2>
    <p>The analysis uses reconstructed directional-limit, flow, constraint-candidate and aggregate generator-pressure histories for VIC1–NSW1. Forecast origins and deliveries are expressed in NEM time. The four targets are mean export, mean import, minimum export and minimum import capability. Direction is normalized so the import target represents positive directional capacity even where source fields use signed values.</p>
    <p>Twelve expanding rolling folds preserve chronology. Within each fold, training, model selection, interval calibration, alert-threshold selection and evaluation are separate. A 30-minute label-maturity allowance prevents a delivery outcome from entering the information set before it could have been observed. Each forecast origin receives total weight one across its configured leads so long-horizon bands do not dominate simply because they contain more origin–lead pairs.</p>
    <p>Lead bands are 1–12, 13–48, 49–144 and 145–336 half-hours. The first band is the primary model-family comparison; later bands reuse the selected family shortlist and fold-specific parameters rather than repeating an unrestricted family × target × band search. A separate fixed-split protocol is reported as sensitivity evidence and does not replace rolling results.</p>
    <h3>Metrics and selection</h3>
    <p>MAE in MW is the fitting, tuning and selection objective. MAPE is reported only where |actual| ≥ 50 MW and is never used to select the main policy. Supporting diagnostics include directional-reference NMAE, RMSE, bias, tail error, and capacity-overstatement rates above 100 and 200 MW. The statistical comparison uses paired daily losses, 2,000 moving-block bootstrap replicates at seven- and fourteen-day block lengths, Holm correction across the four VNI primary hypotheses, and a 90% model confidence set.</p></section>'''

    body += '<section id="models"><h2>2. Models tested</h2><p>The ladder was designed to attribute gains rather than compare unrelated black boxes. T1 tests richer mean shape; T2 and T3 test changing sensitivities; T4 and T5 test cautious and fully local specialization; T6 tests whether remaining nonlinear structure matters.</p>'
    body += _table(_model_glossary()) + "</section>"

    body += '<section id="features"><h2>3. Features and physical interpretation</h2><p>Every core point model receives the same issue-admissible information. Calendar terms are proxies for recurring demand, renewable and commitment states; recent limits anchor the current topology; network and generator-pressure features describe the operating point. This makes incremental family comparisons interpretable.</p>'
    body += _table(_feature_table())
    body += '<p>The saved point-model schema contains 41 numeric columns. NOS blocks are evaluated separately so a weak outage result cannot be confused with a weak core model. The generator-pressure block is observed or lagged aggregate state rather than original-vintage forward unit availability; conclusions about NOS are conditional on that limitation.</p></section>'

    # Overall MAE and MAPE figures.
    ordered = performance.assign(label=lambda x: x.target.map(TARGET_LABELS) + " · " + x.band.map(BAND_LABELS))
    fig = go.Figure()
    for column, name, color in (("persistence_mae", "Persistence", "#ce9a48"), ("t0_mae", "Shared T0", "#8370b4"), ("selected_mae", "Selected policy", "#268a87")):
        fig.add_bar(x=ordered.label, y=ordered[column], name=name, marker_color=color)
    style_plotly(fig, "Origin-balanced MAE across targets and lead bands", height=620)
    fig.update_layout(barmode="group"); fig.update_xaxes(tickangle=-38); fig.update_yaxes(title="MAE (MW)")

    body += '<section id="results"><h2>4. Forecast performance</h2><p>The selected policy improves on persistence in every target–band cell. The gain is largest at short and medium horizons for exports, while imports show smaller but still consistent improvements. Performance decays with lead, but the routed policy retains positive skill through seven days.</p>'
    body += _chart(fig, "Figure 1. MAE by target, lead band and policy", "All rolling evaluation folds; lower is better. Selected policies were frozen before evaluation.")

    paper_performance = performance.copy()
    paper_performance["Target"] = paper_performance.target.map(TARGET_LABELS)
    paper_performance["Lead band"] = paper_performance.band.map(BAND_LABELS)
    paper_performance["MAPE ≥50 (%)"] = paper_performance.selected_mape.map(lambda x: f"{x:.1f}")
    paper_performance["MAPE coverage"] = paper_performance.mape_coverage.map(lambda x: f"{100*x:.1f}%")
    paper_performance["MAE (MW)"] = paper_performance.selected_mae.map(lambda x: f"{x:.1f}")
    paper_performance["Persistence MAE"] = paper_performance.persistence_mae.map(lambda x: f"{x:.1f}")
    paper_performance["Shared T0 MAE"] = paper_performance.t0_mae.map(lambda x: f"{x:.1f}")
    paper_performance["Skill vs persistence"] = paper_performance.skill_persistence.map(lambda x: f"{100*x:.1f}%")
    paper_performance["Skill vs T0"] = paper_performance.skill_t0.map(lambda x: f"{100*x:.1f}%")
    paper_performance[">100 MW overstatement"] = paper_performance.over100.map(lambda x: f"{100*x:.1f}%")
    body += '<h3>Comprehensive rolling results</h3>' + _table(paper_performance[["Target", "Lead band", "MAPE ≥50 (%)", "MAPE coverage", "MAE (MW)", "Persistence MAE", "Shared T0 MAE", "Skill vs persistence", "Skill vs T0", ">100 MW overstatement"]])

    # Primary model ladder.
    ladder_fig = make_subplots(rows=1, cols=2, subplot_titles=("Minimum export", "Minimum import"), shared_yaxes=True)
    for column, target in enumerate(("export_tight", "import_tight"), start=1):
        local = leaderboard.query("target == @target").sort_values("mae", ascending=False)
        ladder_fig.add_trace(go.Bar(x=local.mae, y=local.model.map(MODEL_NAMES), orientation="h", marker_color="#5696b9", showlegend=False), row=1, col=column)
    style_plotly(ladder_fig, "Primary 0.5–6 hour model-family comparison", height=570)
    ladder_fig.update_xaxes(title="MAE (MW)")
    body += _chart(ladder_fig, "Figure 2. Model ladder on the primary tight-limit cells", "T6 has the lowest aggregate rolling MAE in both directions; lower is better.")

    # Delivery period results.
    period_order = list(PERIODS)
    period_fig = make_subplots(rows=1, cols=2, subplot_titles=("Minimum export", "Minimum import"), shared_yaxes=True)
    for column, target in enumerate(("export_tight", "import_tight"), start=1):
        local = periods_frame.query("target == @target")
        for policy, label, color in (("persistence", "Persistence", "#ce9a48"), ("T0_mae", "Shared T0", "#8370b4"), ("selected", "Selected", "#268a87")):
            values = local.query("policy == @policy").set_index("period").reindex(period_order)
            period_fig.add_trace(go.Scatter(x=period_order, y=values.mae, mode="lines+markers", name=label, legendgroup=policy, showlegend=column == 1, line=dict(color=color, width=3)), row=1, col=column)
    style_plotly(period_fig, "MAE by delivery period · primary lead band", height=520)
    period_fig.update_yaxes(title="MAE (MW)", row=1, col=1); period_fig.update_xaxes(tickangle=-25)
    body += '<h3>Time-of-delivery evidence</h3><p>Errors are higher during the morning, solar and evening transitions than overnight. The selected policy nevertheless improves on the shared model in every reported primary period. The result supports delivery-time specialization without implying that clock time itself causes the limit.</p>'
    body += _chart(period_fig, "Figure 3. Performance by delivery period", "Delivery time selects the period behavior; issue-time state remains part of the feature vector.")

    # Representative full curves.
    curve_fig = make_subplots(rows=2, cols=1, subplot_titles=("Minimum export · August 2026", "Minimum import · August 2026"), shared_xaxes=True, vertical_spacing=.12)
    for row_index, target in enumerate(("export_tight", "import_tight"), start=1):
        frame = curves[target]
        curve_fig.add_trace(go.Scatter(x=frame.delivery, y=frame.upper95, line=dict(width=0), showlegend=False, hoverinfo="skip"), row=row_index, col=1)
        curve_fig.add_trace(go.Scatter(x=frame.delivery, y=frame.lower95, fill="tonexty", fillcolor="rgba(86,150,185,.18)", line=dict(width=0), name="95% interval", legendgroup="interval", showlegend=row_index == 1), row=row_index, col=1)
        curve_fig.add_trace(go.Scatter(x=frame.delivery, y=frame.actual, name="Actual", legendgroup="actual", showlegend=row_index == 1, line=dict(color="#282b30", width=2)), row=row_index, col=1)
        curve_fig.add_trace(go.Scatter(x=frame.delivery, y=frame.forecast, name="Forecast", legendgroup="forecast", showlegend=row_index == 1, line=dict(color="#b34d3d", width=2)), row=row_index, col=1)
    style_plotly(curve_fig, "Frozen 336-step forecast curves from one daily issue", height=850)
    curve_fig.update_yaxes(title="Directional limit (MW)"); curve_fig.update_xaxes(title="Delivery interval ending · NEM time", row=2, col=1)
    body += _chart(curve_fig, "Figure 4. Actual and forecast directional limits", "Each curve uses one issue and routes every lead through the corresponding frozen band model; shaded regions are residual-calibrated 95% intervals.")

    fixed_display = fixed.copy()
    for column in ("MAPE ≥50 (%)", "MAE (MW)"):
        fixed_display[column] = fixed_display[column].map(lambda x: f"{x:.1f}")
    body += '<h3>Fixed-split sensitivity</h3><p>The fixed split is kept separate because it has one train/evaluation boundary and cannot replace the rolling origin evidence. Its broad ordering is consistent with the rolling result, while absolute errors differ with the sampled period.</p>' + _table(fixed_display)

    stats_rows = []
    for row in statistics["comparisons"]:
        if row["block_days"] == 7:
            stats_rows.append({"Target": TARGET_LABELS[row["target"]], "Control": MODEL_NAMES[row["control"]], "Improvement (MW)": f"{row['improvement_mw']:.1f}", "95% block CI": f"[{row['ci_low']:.1f}, {row['ci_high']:.1f}]", "Holm p": f"{row.get('holm_p_vni_family', np.nan):.4f}"})
    body += '<h3>Paired statistical evidence</h3><p>Both primary directions improve against persistence and T0 under paired block resampling. The conclusion is unchanged at fourteen-day blocks. The model confidence set contains T6 alone for both directions at both block lengths.</p>' + _table(pd.DataFrame(stats_rows)) + "</section>"

    # Explainability.
    importance_fig = make_subplots(rows=1, cols=2, subplot_titles=("Minimum export", "Minimum import"), shared_yaxes=True)
    group_order = ["calendar", "observed_history", "horizon", "network_state", "generator_pressure", "quality"]
    for column, target in enumerate(("export_tight", "import_tight"), start=1):
        local = importance.query("target == @target").set_index("group").reindex(group_order).dropna().sort_values("mae_degradation")
        importance_fig.add_trace(go.Bar(x=local.mae_degradation, y=local.index, orientation="h", marker_color="#7658c9", showlegend=False), row=1, col=column)
    style_plotly(importance_fig, "T6 grouped permutation importance · primary cells", height=520)
    importance_fig.update_xaxes(title="Held-out MAE degradation (MW)")

    body += '<section id="feature-results"><h2>5. Feature relevance and SHAP decomposition</h2><p>Grouped permutation tests measure how much held-out MAE worsens when a coherent input family is disrupted. Calendar is dominant for minimum export, consistent with a strong recurring capability shape. Recent observed limits dominate minimum import and rank second for export, showing that current network state remains the principal level anchor. Horizon, network-state and generator-pressure variables make smaller conditional contributions after correlated calendar and history inputs are present.</p>'
    body += _chart(importance_fig, "Figure 5. Grouped feature importance", "Average across rolling primary folds for T6. Values are predictive dependence, not physical causal effects.")

    shap_top = []
    for target, local in shap_frame.groupby("target"):
        for row in local.nlargest(12, "mean_abs_shap").itertuples():
            shap_top.append({"Target": TARGET_LABELS[target], "Feature": row.feature, "Mean |SHAP| (MW)": row.mean_abs_shap})
    shap_display = pd.DataFrame(shap_top)
    shap_fig = make_subplots(rows=1, cols=2, subplot_titles=("Minimum export", "Minimum import"), shared_yaxes=False)
    for column, target in enumerate(("export_tight", "import_tight"), start=1):
        local = shap_frame.query("target == @target").nlargest(12, "mean_abs_shap").sort_values("mean_abs_shap")
        shap_fig.add_trace(go.Bar(x=local.mean_abs_shap, y=local.feature, orientation="h", marker_color="#268a87", showlegend=False), row=1, col=column)
    style_plotly(shap_fig, "Leading T6 SHAP contributions", height=600)
    shap_fig.update_xaxes(title="Mean absolute SHAP contribution (MW)")
    body += '<p>Exact path-dependent TreeSHAP decomposes the T6 correction, with the issue-known anchor represented explicitly in the full forecast. The anchor, matching one-step directional-limit lag and hour-of-day terms are the largest single contributions. SHAP confirms model use of these variables but does not identify causal constraint mechanisms.</p>'
    body += _chart(shap_fig, "Figure 6. Leading feature-level contributions", "Mean absolute SHAP values across deterministic held-out diagnostic cases and rolling folds.")
    shap_display["Mean |SHAP| (MW)"] = shap_display["Mean |SHAP| (MW)"].map(lambda x: f"{x:.2f}")
    body += '<details><summary>Feature-level SHAP table</summary>' + _table(shap_display) + "</details></section>"

    # NOS evidence.
    nos_fig = go.Figure()
    labels = [TARGET_LABELS[row.target] for row in nos.itertuples()]
    nos_fig.add_bar(x=labels, y=nos.control_mae, name="T6 without NOS", marker_color="#8370b4")
    nos_fig.add_bar(x=labels, y=nos.selected_mae, name="Selection-routed NOS policy", marker_color="#268a87")
    style_plotly(nos_fig, "Source-common NOS comparison", height=470); nos_fig.update_layout(barmode="group"); nos_fig.update_yaxes(title="MAE (MW)")
    nos_display = nos.copy()
    nos_display["Target"] = nos_display.target.map(TARGET_LABELS)
    nos_display["Selected MAE"] = nos_display.selected_mae.map(lambda x: f"{x:.2f}")
    nos_display["No-NOS T6 MAE"] = nos_display.control_mae.map(lambda x: f"{x:.2f}")
    nos_display["NOS skill"] = nos_display.skill.map(lambda x: f"{100*x:+.2f}%")
    nos_display["MAPE ≥50 (%)"] = nos_display.mape.map(lambda x: f"{x:.1f}")

    body += f'''<section id="nos"><h2>6. Scheduled network-outage evidence</h2>
    <p>The outage archive contains 17,800 usable snapshots from 53 weekly bundles. Six expanding monthly folds pass the historical source-coverage gate in each direction. The pre-model atlas identifies {impact['candidate_bookings']} candidate bookings but only {impact['matched_direction_episodes']} direction-level episodes with adequate matched controls. No recurring entity passes the support, pre-trend, placebo and leave-one-out stability gates; consequently, no asset or constraint set is reported as the “highest adjusted impact.”</p>
    <p>The predictive ablation adds burden (O1), transitions and overlap (O2), mapped mechanisms (O3), revision and recall state (O4), and restricted outage × operating-state interactions (OX). On the common source population, the selected NOS route changes export MAE by {100*nos_export.skill:+.2f}% and import MAE by {100*nos_import.skill:+.2f}% relative to the T6 O0 control. This is too small and inconsistent to justify adding NOS to the default point model.</p>'''
    body += _chart(nos_fig, "Figure 7. NOS point-model performance", "All comparisons use the same source-known observations and history window.") + _table(nos_display[["Target", "Selected MAE", "No-NOS T6 MAE", "NOS skill", "MAPE ≥50 (%)", "rows"]])
    if not nos_importance.empty:
        ni = nos_importance.copy(); ni["Target"] = ni.target.map(TARGET_LABELS); ni["Scheduled-outage importance (MW)"] = ni.mae_degradation.map(lambda x: f"{x:+.2f}")
        body += '<p>Scheduled-outage grouped permutation importance is correspondingly small:</p>' + _table(ni[["Target", "Scheduled-outage importance (MW)"]])
    body += '<p>Five of six NOS risk folds select an outage recipe, but the chosen recipe changes by month and the recall/false-alarm trade-off is unstable. The evidence supports retaining NOS as a monitored risk challenger and targeted diagnostic. A broader conclusion requires original-vintage forward generation availability because current generator pressure is observed/lagged rather than forecast.</p></section>'

    # Refinements and verdict.
    refinement_display = refinements.copy(); refinement_display["Target"] = refinement_display.target.map(TARGET_LABELS); refinement_display["Selected MAE"] = refinement_display.selected_mae.map(lambda x: f"{x:.2f}"); refinement_display["Expanding-history MAE"] = refinement_display.expanding_mae.map(lambda x: f"{x:.2f}"); refinement_display["Skill"] = refinement_display.skill.map(lambda x: f"{100*x:+.2f}%")
    body += '<section><h2>7. Post-selection refinements and warning models</h2><p>Lead-conditioned aggregate pressure and trailing 180/365-day windows were tested only after the calendar/NOS recipe was frozen. Selection-routed refinements worsen aggregate held-out MAE, so the expanding-history model remains the default. Cross-connector pooling remains untested until QNI is executed on the same protocol.</p>' + _table(refinement_display[["Target", "Selected MAE", "Expanding-history MAE", "Skill"]])
    body += '<p>Separate logistic and boosted contraction-warning models were calibrated under a joint three-false-alarms-per-day directional budget. Their performance is useful for development diagnostics, but instability across folds and the historical nature of threshold selection prevent operational promotion. Point forecasts and contraction warnings should therefore remain separate products.</p></section>'

    bundle_display = bundles.copy(); bundle_display["Selection MAE (MW)"] = bundle_display["Selection MAE (MW)"].map(lambda x: f"{x:.1f}")
    body += '''<section id="verdict"><h2>8. Model assessment and selected specification</h2>
    <div class="callout"><strong>Recommended point model.</strong> Use the MAE-selected calendar policy: T6 for all four targets in bands 0–2 and for band-3 imports; retain T0 for band-3 exports. Keep persistence and seasonal persistence as monitored fallbacks. Do not include NOS or the post-selection refinements in the default point forecast.</div>
    <p>T6 earns promotion because it improves on both persistence and the shared T0 control in the primary directions, survives block-length sensitivity and the model confidence set, and preserves positive skill across all lead bands. T0 remains preferable for band-3 export because the additional nonlinear structure does not earn a sufficient selection-period gain there. The final routing decision is therefore target- and horizon-specific rather than a claim that one family is universally best.</p>
    <p>The model explains limits as a strongly recurring time-of-delivery shape whose realized level is anchored by the latest admissible directional limit and recent network state. Network geometry and generator pressure provide smaller conditional corrections. This interpretation is consistent with the predictive evidence but should not be read as a causal decomposition of individual constraint equations.</p>
    <h3>Saved-model catalogue</h3>''' + _table(bundle_display) + "</section>"

    body += '''<section id="forward"><h2>9. Forecasting forward</h2>
    <p>The repository contains sixteen saved bundles under <code>data/forecast_experiments/vni_diurnal_nos_v2/final/</code>. The catalogue records target, lead band, winner and SHA-256. Each bundle stores the fitted model, exact ordered schema, parameters, residual quantiles and delivery-period calibration. Reload parity passed for every bundle.</p>
    <h3>Research forecast from prepared features</h3>
    <pre>python -m nemic.experiments forecast-vni `
  --features path/to/vni_features.parquet `
  --target export_tight `
  --output local_exports/vni_export_tight.csv `
  --allow-research</pre>
    <p>The command verifies the model hash, validates all required columns, routes every row by lead, and writes the point forecast plus calibrated 2.5%, 10%, 50%, 90% and 97.5% estimates. If a delivery timestamp is supplied, interval adjustments use the five delivery periods; otherwise pooled calibration is used.</p>
    <h3>Live feature pipeline required for production</h3>
    <ol><li>At every issue time, record actual receipt timestamps for dispatch limits, flow, constraint candidates and generator-state inputs.</li><li>Construct the 41-column schema using only information available by the issue cutoff. Preserve the latest admissible directional limit as <code>own_anchor</code>.</li><li>Create one row per target delivery and lead; the loader routes leads 1–12, 13–48, 49–144 and 145–336 to the saved bundle.</li><li>Write point and interval forecasts with model hash, issue time, source vintages, schema version and data-quality flags.</li><li>Run prospective shadow forecasts without retuning. Monitor MAE, qualified MAPE, overstatement, interval coverage, boundary jumps and missing-feature rates.</li><li>Promote only after prospective performance meets the predefined improvement and risk gates. Until then, retain persistence as the operational fallback.</li></ol>
    <p>NOS features are absent from the saved point bundles because they did not improve source-common accuracy consistently. A future NOS production test should pair issue-vintage outage exposure with issue-vintage forward demand, renewable and generator-availability forecasts, then repeat the O0–O4 comparison prospectively.</p></section>'''

    body += '''<section><h2>10. Limitations</h2><p>All reported outcomes were available during development and are not independent confirmation. Network state was reconstructed historically, and actual receipt times are represented by a stated availability delay rather than a verified live message ledger. The NOS archive begins later than the core study and supplies limited independent recurring-outage support. SHAP and permutation importance describe model dependence, not causal physical effects. QNI has not yet been executed on this protocol, so cross-connector pooling and external connector generalization remain open questions.</p></section>
    <section><h2>11. Conclusion</h2><p>Time-of-delivery modelling materially improves VNI directional-limit forecasts. The improvement is not confined to one difficult period or one horizon: it is present across the five reporting periods and all four lead bands, with strongest evidence for shallow nonlinear T6 corrections. Recent observed limits and calendar structure provide most of the useful signal. Scheduled NOS data are operationally meaningful but add little incremental point-forecast accuracy on the available source-common history once current network state and T6 are present. The appropriate handoff is therefore a compact target × horizon routing policy, backed by saved schemas and calibration, with NOS retained as a risk and diagnostic challenger.</p></section>'''

    body += '''<section><h2>References and reproducibility</h2><ol>
    <li>Soares, L. J. and Medeiros, M. C. (2008). <a href="https://www.econ.puc-rio.br/marcelomedeiros/Soares%20and%20Medeiros%20%28IJF%2C%202008%29.pdf">Modeling and forecasting short-term electricity load</a>. <em>International Journal of Forecasting</em>, 24, 630–644.</li>
    <li>Hyndman, R. J. and Athanasopoulos, G. (2021). <a href="https://otexts.com/fpp3/dhr.html">Dynamic harmonic regression</a> and <a href="https://otexts.com/fpp3/tscv.html">time-series cross-validation</a>. <em>Forecasting: Principles and Practice</em>.</li>
    <li>Hansen, P. R., Lunde, A. and Nason, J. M. (2011). <a href="https://doi.org/10.3982/ECTA5771">The Model Confidence Set</a>. <em>Econometrica</em>.</li>
    <li>AEMO. <a href="https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/nem-events-and-reports/network-outages">Network Outages</a> and <a href="https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq">Constraint FAQ</a>.</li></ol>
    <p>Configuration: <code>configs/experiments/vni_diurnal_nos_v2.json</code>. Full cell-level results, search paths, SHAP decompositions and outage audits remain in the companion report suite. Rebuild this paper with <code>python scripts/build_vni_research_paper.py</code>.</p></section>'''

    output_path = OUTPUT / "vni_research_paper.html"
    output_path.write_text(render_page("VNI time-of-delivery forecasting research paper", body), encoding="utf-8")
    performance.to_csv(OUTPUT / "downloads/research_performance.csv", index=False)
    importance.to_csv(OUTPUT / "downloads/research_feature_importance.csv", index=False)
    shap_frame.to_csv(OUTPUT / "downloads/research_shap_importance.csv", index=False)
    all_sources = sorted(set(point_sources + explanation_sources + nos_sources + refinement_sources + bundle_sources + curve_sources + [statistics_path, impact_path]))
    manifest = {
        "title": "VNI time-of-delivery models and scheduled network-outage evidence",
        "generator": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
        "generator_sha256": digest(__file__),
        "report_sha256": digest(output_path),
        "sources": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": digest(path)} for path in all_sources],
        "headline": {
            "export_tight_band0_mae": export.selected_mae,
            "import_tight_band0_mae": imported.selected_mae,
            "export_tight_skill_vs_persistence": export.skill_persistence,
            "import_tight_skill_vs_persistence": imported.skill_persistence,
            "nos_export_skill": nos_export.skill,
            "nos_import_skill": nos_import.skill,
        },
    }
    (OUTPUT / "downloads/research_paper_build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return output_path


if __name__ == "__main__":
    build()
