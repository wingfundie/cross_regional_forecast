"""Ten curated inline Plotly exhibits for Flagship C (Forecasting Verdict, Clustering & PEC v2)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nemic.experiments.vb_report_kit import (
    PALETTE as C,
    chart_spec,
    style_plotly_white,
)

EV = Path(__file__).resolve().parent / "evidence"


def ev(name: str) -> pd.DataFrame:
    return pd.read_csv(EV / name)


def c1_pec_observed_configs():
    df = ev("pec_observed_configs.csv")
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.14, subplot_titles=["Observed share of commissioning hours (%)", "Median & P95 directional tight limits (MW)"])
    fig.add_bar(x=df["regime"], y=df["share_pct"], marker_color=C["deep"], showlegend=False, row=1, col=1,
                hovertemplate="%{x}<br>Share: %{y:.1f}%<extra></extra>")
    fig.add_bar(name="NSW→SA median", x=df["regime"], y=df["fwd_tight_med_mw"], marker_color=C["blue"], row=1, col=2)
    fig.add_bar(name="SA→NSW median", x=df["regime"], y=df["rev_tight_med_mw"], marker_color=C["teal"], row=1, col=2)
    fig.add_bar(name="NSW→SA P95", x=df["regime"], y=df["fwd_tight_p95_mw"], marker_color=C["gold"], row=1, col=2)
    style_plotly_white(fig, "", 390, "", margin_t=66, legend_y=1.18)
    fig.update_yaxes(title_text="% of half-hours", row=1, col=1)
    fig.update_yaxes(title_text="MW", row=1, col=2)
    fig.update_xaxes(tickangle=-18)
    return chart_spec("c1", "Exhibit 1.1: Observed Project EnergyConnect commissioning regimes and tight directional limits",
                      "NSW1-SA1 half-hourly commissioning record (1 October to 23 November 2026, 2,544 half-hours)",
                      "Shows the exact distribution across 150 MW commissioning, 350 MW testing, and zero-transfer lockout phases rather than assuming instantaneous 800 MW nameplate availability.",
                      fig, "pec_observed_configs.csv")


def c2_pec_southern_ring_coupling():
    df = ev("pec_southern_ring_coupling.csv")
    cats = sorted(df["ring_category"].unique())
    dirs = ["NSW -> SA (forward)", "SA -> NSW (reverse)"]
    pal = [C["deep"], C["blue"], C["teal"], C["gold"], C["red"], C["purple"], C["slate"]]
    fig = go.Figure()
    for i, cat in enumerate(cats):
        vals = []
        for d in dirs:
            s = df[(df["direction"] == d) & (df["ring_category"] == cat)]["share_pct"].sum()
            vals.append(s)
        fig.add_bar(name=cat, x=dirs, y=vals, marker_color=pal[i % len(pal)],
                    hovertemplate="%{x}<br>" + cat + ": %{y:.1f}% of 5-min intervals<extra></extra>")
    fig.update_layout(barmode="stack")
    style_plotly_white(fig, "Share of 5-minute dispatch intervals (%)", 395)
    return chart_spec("c2", "Exhibit 1.2: Southern-ring constraint-setter taxonomy on EnergyConnect (NSW1-SA1)",
                      "15,264 five-minute dispatch intervals classified by reported export and import setter equations",
                      "Demonstrates that EnergyConnect is governed not only by its own 150/350 MW commissioning caps, but heavily by shared VNI thermal/voltage limits (N>>NIL_060_051) and Heywood/SA UFLS bounds.",
                      fig, "pec_southern_ring_coupling.csv")


def c3_loop_settlement_bridge():
    df = ev("pec_loop_settlement_bridge.csv")
    arms = [
        ("loop_VICNSW_m", "VIC → NSW (VNI)", C["deep"]),
        ("loop_NSWVIC_m", "NSW → VIC (VNI)", C["sky"]),
        ("loop_VICSA_m", "VIC → SA (Heywood+ML)", C["teal"]),
        ("loop_SAVIC_m", "SA → VIC (Heywood+ML)", "#7bc4b4"),
        ("loop_NSWSA_m", "NSW → SA (PEC)", C["gold"]),
        ("loop_SANSW_m", "SA → NSW (PEC)", C["red"]),
    ]
    fig = go.Figure()
    for col, lbl, clr in arms:
        fig.add_bar(name=lbl, x=df["regime"], y=df[col], marker_color=clr,
                    hovertemplate="%{x}<br>" + lbl + ": $%{y:.1f}m (24m)<extra></extra>")
    fig.update_layout(barmode="stack")
    style_plotly_white(fig, "24-month AEMC ERC0386 loop payouts ($ millions)", 405)
    fig.update_xaxes(tickangle=-12)
    return chart_spec("c3", "Exhibit 2.1: AEMC ERC0386 loop settlement payouts across four observed EnergyConnect capacity regimes",
                      "24-month historical-price counterfactual (Sep 2024 to Aug 2026, holding regional prices fixed; AEMC ERC0386 net-trade engine)",
                      "Tracks how escalating EnergyConnect limits from 0 MW to observed 150 MW commissioning, 350 MW testing, and 800 MW Stage 2 reallocates net-trade SRA payouts across all six southern-ring buckets.",
                      fig, "pec_loop_settlement_bridge.csv")


def c4_loop_share_and_dilution():
    df = ev("pec_loop_settlement_bridge.csv")
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.14, subplot_titles=["Status-quo IRSR vs ERC0386 loop payout ($m)", "EnergyConnect arm share of loop payout (%)"])
    fig.add_bar(name="Status-quo positive IRSR", x=df["regime"], y=df["sq_total_pos_m"], marker_color=C["sky"], row=1, col=1)
    fig.add_bar(name="ERC0386 net-trade payout", x=df["regime"], y=df["loop_total_payout_m"], marker_color=C["deep"], row=1, col=1)
    fig.add_scatter(x=df["regime"], y=df["pec_arm_share_of_loop_pct"], mode="lines+markers+text",
                    text=[f"{v:.1f}%" for v in df["pec_arm_share_of_loop_pct"]], textposition="top center",
                    line=dict(color=C["gold"], width=2.8), marker=dict(size=9), showlegend=False, row=1, col=2)
    style_plotly_white(fig, "", 390, "", margin_t=66, legend_y=1.18)
    fig.update_yaxes(title_text="AUD millions (24m)", row=1, col=1)
    fig.update_yaxes(title_text="% of total loop payout", row=1, col=2)
    fig.update_xaxes(tickangle=-15)
    return chart_spec("c4", "Exhibit 2.2: Net-loop payout conservation and EnergyConnect's rising share of southern-ring settlement",
                      "Comparison of status-quo positive IRSR sum against ERC0386 net-trade payouts across commissioning steps",
                      "Even at 0 MW physical flow, ERC0386 assigns pass-through net trade to the NSW–SA arm; observed 150 MW and 350 MW commissioning flows expand total loop residue while shifting bucket shares.",
                      fig, "pec_loop_settlement_bridge.csv")


def c5_pec_forecast_mae():
    df = ev("pec_issue_time_forecast_scores.csv")
    sub = df[df["product"] == "Predispatch"].copy()
    lb_order = ["intraday", "6-24h", "day 2-3", "day 4-7"]
    models = ["Persistence", "Delivery-Period Baseline", "AEMO Issued Forecast", "Regional Forecast", "Regional + Constraints"]
    m_cols = [C["slate"], C["sky"], C["gold"], C["teal"], C["deep"]]
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12, subplot_titles=["NSW → SA tight limit MAE (MW)", "SA → NSW tight limit MAE (MW)"])
    for ci, d_lbl in enumerate(["NSW -> SA (tight)", "SA -> NSW (tight)"], 1):
        g = sub[sub["direction"] == d_lbl]
        for m, clr in zip(models, m_cols):
            gm = g[g["model"] == m].set_index("lead_band").reindex(lb_order).reset_index()
            fig.add_bar(name=m, x=gm["lead_band"], y=gm["mae_mw"], marker_color=clr, legendgroup=m, showlegend=(ci == 1), row=1, col=ci,
                        hovertemplate=m + " · %{x}<br>MAE: %{y:.1f} MW<extra></extra>")
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "", 395, "", margin_t=66, legend_y=1.18)
    fig.update_yaxes(title_text="MAE (MW)", row=1, col=1)
    return chart_spec("c5", "Exhibit 3.1: EnergyConnect issue-time Predispatch forecast MAE across five models and four lead bands",
                      "Evaluated strictly on identical as-of rows across 48,336 Predispatch forecasts (Oct–Nov 2026)",
                      "Quantifies where AEMO's issued forecast and constraint-aware models beat persistence versus where discrete commissioning configuration switches dominate medium-horizon errors.",
                      fig, "pec_issue_time_forecast_scores.csv")


def c6_pec_interval_coverage():
    df = ev("pec_issue_time_forecast_scores.csv")
    sub = df[df["product"] == "Predispatch"].dropna(subset=["interval_coverage_pct"])
    agg = sub.groupby(["lead_band", "model"], as_index=False)["interval_coverage_pct"].mean()
    lb_order = ["intraday", "6-24h", "day 2-3", "day 4-7"]
    models = ["Persistence", "AEMO Issued Forecast", "Regional Forecast", "Regional + Constraints"]
    m_cols = [C["slate"], C["gold"], C["teal"], C["deep"]]
    fig = go.Figure()
    for m, clr in zip(models, m_cols):
        gm = agg[agg["model"] == m].set_index("lead_band").reindex(lb_order).reset_index()
        fig.add_scatter(x=gm["lead_band"], y=gm["interval_coverage_pct"], name=m, mode="lines+markers",
                        line=dict(color=clr, width=2.4), marker=dict(size=7))
    fig.add_hline(y=80.0, line_dash="dash", line_color=C["red"], annotation_text="80% nominal target", annotation_position="bottom right")
    style_plotly_white(fig, "Empirical interval coverage (%)", 365, "Predispatch lead band")
    return chart_spec("c6", "Exhibit 3.2: Issue-time prediction interval coverage on EnergyConnect across lead bands",
                      "Mean coverage (%) across NSW→SA and SA→NSW tight-limit targets (48,336 Predispatch rows)",
                      "Discrete commissioning-step jumps between 0, 150, and 350 MW test intervals sharply at day 2–7 horizons unless configuration regimes are explicitly known at issue time.",
                      fig, "pec_issue_time_forecast_scores.csv")


def c7_longrange_50_bands():
    df = ev("longrange_band_verdict.csv")
    band_order = ["days_1_7", "days_8_14", "days_15_30", "days_31_60", "days_61_90"]
    band_lbl = {"days_1_7": "1–7d", "days_8_14": "8–14d", "days_15_30": "15–30d", "days_31_60": "31–60d", "days_61_90": "61–90d"}
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12, subplot_titles=["VNI (VIC–NSW) 1–90d MAE (MW)", "QNI (NSW–QLD) 1–90d MAE (MW)"])
    t_cols = {"export_tight": C["deep"], "import_tight": C["blue"], "export": C["teal"], "import": C["gold"], "flow": C["red"]}
    for ci, conn in enumerate(["VNI", "QNI"], 1):
        sub = df[df["connector"] == conn]
        for tgt, clr in t_cols.items():
            g = sub[sub["target"] == tgt].set_index("band").reindex(band_order).reset_index()
            fig.add_scatter(x=[band_lbl[b] for b in g["band"]], y=g["model_mae"], name=tgt, mode="lines+markers",
                            legendgroup=tgt, showlegend=(ci == 1), line=dict(color=clr, width=2.2), row=1, col=ci,
                            hovertemplate=conn + " · " + tgt + " (%{x})<br>Model MAE: %{y:.1f} MW<extra></extra>")
    style_plotly_white(fig, "", 390, "", margin_t=66, legend_y=1.18)
    fig.update_yaxes(title_text="MAE (MW)", row=1, col=1)
    return chart_spec("c7", "Exhibit 4.1: All fifty long-range MT PASA horizon-band MAE trajectories across VNI and QNI",
                      "Daily 08:00 NEM origins · 5 targets × 5 lead bands (1–7 through 61–90 days)",
                      "Error expands steadily beyond two weeks as weather and unbooked outage uncertainty overtake initial-state memory, explaining why no challenger cleared promotion gates.",
                      fig, "longrange_band_verdict.csv")


def c8_longrange_cell_verdict():
    df = ev("longrange_cell_decisions.csv")
    df["label"] = df["connector"] + " · " + df["target"]
    fig = go.Figure()
    fig.add_bar(name="Skill vs calendar baseline (%)", x=df["label"], y=df["weighted_primary_skill"] * 100, marker_color=C["deep"])
    fig.add_bar(name="Skill vs persistence (%)", x=df["label"], y=df["weighted_primary_skill_vs_persistence"] * 100, marker_color=C["teal"])
    fig.add_hline(y=0, line_color="#102a43", line_width=1)
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "Weighted primary skill (%)", 385)
    fig.update_xaxes(tickangle=-25)
    return chart_spec("c8", "Exhibit 4.2: Long-range cell verdict across all ten connector × target cells (10/10 retain baseline)",
                      "Weighted primary skill versus calendar baseline and persistence across 1–90 day horizons",
                      "Although QNI ridge/boosting challengers show positive point skill versus calendar baselines, wide confidence intervals and negative persistence skill on QNI export prevented promotion in all 10 cells.",
                      fig, "longrange_cell_decisions.csv")


def c9_clustering_stability():
    df = ev("clustering_stability_summary.csv")
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.12, subplot_titles=["VNI state stability (ARI)", "QNI state stability (ARI)"])
    for ci, conn in enumerate(["VNI", "QNI"], 1):
        sub = df[df["connector"] == conn]
        for meth, ls, col in [("kmeans", "solid", C["deep"]), ("gmm", "dash", C["gold"])]:
            g = sub[sub["method"] == meth].sort_values("k")
            fig.add_scatter(x=g["k"], y=g["mean_block_ari"], name=f"{meth.upper()} block ARI", mode="lines+markers",
                            legendgroup=f"{meth}_blk", showlegend=(ci == 1), line=dict(color=col, width=2.4, dash=ls), row=1, col=ci)
            fig.add_scatter(x=g["k"], y=g["mean_seed_ari"], name=f"{meth.upper()} seed ARI", mode="lines+markers",
                            legendgroup=f"{meth}_sd", showlegend=(ci == 1), line=dict(color=C["sky"] if meth == "kmeans" else C["red"], width=1.6, dash="dot"), row=1, col=ci)
        fig.update_xaxes(title_text="Cluster count k", dtick=1, row=1, col=ci)
    style_plotly_white(fig, "", 385, "", margin_t=66, legend_y=1.18)
    fig.update_yaxes(range=[0, 1.05])
    fig.update_yaxes(title_text="Adjusted Rand Index (ARI)", row=1, col=1)
    return chart_spec("c9", "Exhibit 5.1: Chronological block stability versus random-seed stability in QNI/VNI regime clustering",
                      "Mean Adjusted Rand Index across chronological folds for k = 1 to 8 (K-means and Gaussian Mixture)",
                      "Only coarse two-state partitions (k = 2) remain structurally stable across chronological blocks; finer k = 4 through k = 8 partitions decay sharply out-of-sample.",
                      fig, "clustering_stability_summary.csv")


def c10_clustering_vs_controls():
    df = ev("clustering_vs_controls.csv")
    sub = df[df["control_model"].isin(["boost_fundamentals", "persistence"])].copy()
    sub["label"] = sub["connector"] + " · " + sub["target"]
    fig = go.Figure()
    for ctrl, lbl, clr in [("boost_fundamentals", "vs Matched Boost Fundamentals", C["deep"]), ("persistence", "vs Persistence", C["gold"])]:
        g = sub[sub["control_model"] == ctrl]
        fig.add_bar(name=lbl, x=g["label"], y=g["mean_effect_pct"], marker_color=clr,
                    customdata=np.stack([g["wins_raw"], g["comparisons"], g["sig_holm_wins"]], axis=-1),
                    hovertemplate="%{x}<br>" + lbl + "<br>Mean MAE Δ: %{y:.1f}%<br>Raw wins: %{customdata[0]}/%{customdata[1]} (Holm sig: %{customdata[2]})<extra></extra>")
    fig.add_hline(y=0, line_color="#102a43", line_width=1)
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "Mean MAE change vs control (% · negative = cluster wins)", 385)
    fig.update_xaxes(tickangle=-20)
    return chart_spec("c10", "Exhibit 5.2: Leakage-controlled clustering MAE effects against matched boosting and persistence controls",
                      "Seven-day block-bootstrap evaluations across folds and horizon bands (negative = improvement)",
                      "While local cluster experts occasionally trim short-horizon QNI MAE before multiple-testing correction, zero evaluations survive Holm-Bonferroni correction across all folds.",
                      fig, "clustering_vs_controls.csv")


def all_charts() -> dict[str, dict]:
    items = [
        c1_pec_observed_configs(), c2_pec_southern_ring_coupling(), c3_loop_settlement_bridge(),
        c4_loop_share_and_dilution(), c5_pec_forecast_mae(), c6_pec_interval_coverage(),
        c7_longrange_50_bands(), c8_longrange_cell_verdict(), c9_clustering_stability(),
        c10_clustering_vs_controls(),
    ]
    return {c["id"]: c for c in items}
