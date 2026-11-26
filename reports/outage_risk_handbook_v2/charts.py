"""Ten curated inline Plotly exhibits for Flagship B (Outage Risk & NOS Regime Handbook v2)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nemic.experiments.vb_report_kit import (
    LINK_COLORS,
    PALETTE as C,
    chart_spec,
    style_plotly_white,
)

EV = Path(__file__).resolve().parent / "evidence"
LINK_ORDER = ["VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"]


def ev(name: str) -> pd.DataFrame:
    return pd.read_csv(EV / name)


def b1_booking_reliability():
    df = ev("nos_booking_reliability_summary.csv")
    agg = df.groupby("name", as_index=False).agg(
        withdrawn=("withdrawn_share", "mean"),
        invoked=("invoked_share", "mean"),
        actual_win=("actual_window_share", "mean"),
        early_ret=("early_return_share", "mean"),
        overrun=("overrun_share", "mean"),
    ).set_index("name").reindex(LINK_ORDER).reset_index()
    fig = go.Figure()
    fig.add_bar(name="Withdrawn / cancelled (%)", x=agg["name"], y=agg["withdrawn"] * 100, marker_color=C["red"])
    fig.add_bar(name="Constraint set invoked (%)", x=agg["name"], y=agg["invoked"] * 100, marker_color=C["deep"])
    fig.add_bar(name="Returned early (%)", x=agg["name"], y=agg["early_ret"] * 100, marker_color=C["teal"])
    fig.add_bar(name="Overran booked end (%)", x=agg["name"], y=agg["overrun"] * 100, marker_color=C["gold"])
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "% of booked NOS episodes", 375)
    return chart_spec("b1", "Exhibit 1.1: Network Outage Scheduler booking withdrawal, invocation, and schedule drift across six links",
                      "Mean share of NOS episodes across study years (September 2024 to August 2026)",
                      "Schedule drift, withdrawals, and early returns explain why naive outage-calendar models systematically over-predict realised binding probabilities.",
                      fig, "nos_booking_reliability_summary.csv")


def b2_nos_sra_day_impact():
    df = ev("nos_economic_effects.csv").dropna(subset=["sra_day_effect_aud"])
    if "well_supported" in df.columns:
        df = df[df["well_supported"]].copy()
    # Pick top 8 positive and top 8 negative SRA $/day well-supported families
    pos = df.nlargest(8, "sra_day_effect_aud")
    neg = df.nsmallest(8, "sra_day_effect_aud")
    sub = pd.concat([neg, pos], ignore_index=True).drop_duplicates(subset=["ic", "direction", "GENCONSETID"])
    sub = sub.sort_values("sra_day_effect_aud", ascending=True)
    labels = sub["GENCONSETID"] + " (" + sub["link"] + " " + sub["direction"].str[:3] + ")"
    cols = [C["red"] if v < 0 else C["deep"] for v in sub["sra_day_effect_aud"]]
    fig = go.Figure(go.Bar(
        y=labels, x=sub["sra_day_effect_aud"] / 1e3, orientation="h", marker_color=cols,
        error_x=dict(
            type="data", symmetric=False,
            array=((sub["sra_day_ci_hi"] - sub["sra_day_effect_aud"]).clip(lower=0) / 1e3).to_numpy(),
            arrayminus=((sub["sra_day_effect_aud"] - sub["sra_day_ci_lo"]).clip(lower=0) / 1e3).to_numpy(),
            thickness=1.1, color="#52606d",
        ),
        customdata=np.stack([sub["spread_effect_aud"].fillna(0), sub["matched_hh"]], axis=-1),
        hovertemplate="%{y}<br>Matched SRA impact: $%{x:,.1f}k/day<br>Spread delta: $%{customdata[0]:,.1f}/MWh<br>Matched half-hours: %{customdata[1]:,}<extra></extra>",
    ))
    fig.add_vline(x=0, line_color="#102a43", line_width=1)
    style_plotly_white(fig, "", 490, "Matched SRA residue change ($ thousands per day, 95% block CI)")
    fig.update_layout(margin=dict(l=225, r=24, t=42, b=56))
    return chart_spec("b2", "Exhibit 2.1: Highest positive and negative matched SRA residue impacts by NOS outage family",
                      "AUD thousands per day (treated minus matched control, seven-day block-bootstrap 95% CI)",
                      "Red bars indicate outage families that destroy directional SRA payouts via flow clamping or counter-price forcing; navy bars indicate families that widen with-price congestion rent.",
                      fig, "nos_economic_effects.csv")


def b3_cap_vs_spread_scatter():
    df = ev("nos_economic_effects.csv").dropna(subset=["effect_capacity", "spread_effect_aud"])
    # Trim extreme >$1000/MWh outliers only for readability while keeping hover accurate
    sub = df[df["matched_hh"] >= 48].copy()
    sub["sp_clip"] = sub["spread_effect_aud"].clip(-250, 350)
    fig = go.Figure()
    for lk in LINK_ORDER:
        g = sub[sub["link"] == lk]
        if g.empty:
            continue
        fig.add_scatter(
            x=g["effect_capacity"], y=g["sp_clip"], mode="markers", name=lk,
            marker=dict(color=LINK_COLORS[lk], size=np.clip(np.sqrt(g["matched_hh"]) * 0.45, 6, 18), opacity=0.78, line=dict(width=0.7, color="#ffffff")),
            customdata=np.stack([g["GENCONSETID"], g["direction"], g["spread_effect_aud"], g["sra_day_effect_aud"].fillna(0) / 1e3], axis=-1),
            hovertemplate=lk + " · %{customdata[0]} (%{customdata[1]})<br>Cap delta: %{x:.0f} MW<br>Spread delta: $%{customdata[2]:.1f}/MWh<br>SRA delta: $%{customdata[3]:.1f}k/day<extra></extra>",
        )
    fig.add_hline(y=0, line_dash="dot", line_color="#9fb3c8")
    fig.add_vline(x=0, line_dash="dot", line_color="#9fb3c8")
    style_plotly_white(fig, "Matched directional spread change ($/MWh, display clipped)", 400, "Matched directional capacity effect (MW)")
    return chart_spec("b3", "Exhibit 2.2: Matched capacity contraction versus regional price-spread change across supported outage families",
                      "Each point is one outage family-direction (>= 48 matched half-hours); marker size reflects sample hours",
                      "Demonstrates why MW capacity drops alone do not map monotonically to $/MWh spreads: outages cutting slack capacity move prices little, while modest cuts on tight corridors widen spreads sharply.",
                      fig, "nos_economic_effects.csv")


def b4_n11_superadditivity():
    df = ev("nos_n11_superadditivity.csv")
    sub = df.head(14).sort_values("super_additivity_mw", ascending=False)
    labels = sub["family_a"] + " + " + sub["family_b"] + " (" + sub["link"] + " " + sub["direction"].str[:3] + ")"
    fig = go.Figure()
    fig.add_bar(name="Linear additive sum ΔCap(A)+ΔCap(B)", y=labels, x=sub["additive_sum_mw"], orientation="h", marker_color=C["sky"])
    fig.add_bar(name="Observed concurrent joint ΔCap(A+B)", y=labels, x=sub["observed_joint_mw"], orientation="h", marker_color=C["deep"])
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "", 480, "Capacity change vs baseline (MW)")
    fig.update_layout(margin=dict(l=265, r=24, t=46, b=56))
    return chart_spec("b4", "Exhibit 3.1: N-1-1 concurrent-outage compounding across the fourteen most super-additive family pairs",
                      "Observed joint half-hour tight-limit drop versus linear sum of standalone outage effects (MW)",
                      "When two outages overlap simultaneously, the joint transfer reduction frequently cuts hundreds of megawatts deeper than adding each outage's standalone impact.",
                      fig, "nos_n11_superadditivity.csv")


def b5_n11_spread_compounding():
    df = ev("nos_n11_superadditivity.csv")
    sub = df[df["is_compounding"]].copy()
    if len(sub) < 6:
        sub = df.head(12).copy()
    agg = df.groupby("link", as_index=False).agg(
        tested=("super_additivity_mw", "count"),
        compounding=("is_compounding", "sum"),
        mean_super_mw=("super_additivity_mw", "mean"),
        p10_super_mw=("super_additivity_mw", lambda s: np.percentile(s, 10)),
    ).set_index("link").reindex(LINK_ORDER).fillna(0.0).reset_index()
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Compounding pairs (super-additivity < -20 MW, CI < 0)", "10th-percentile (worst-decile) compounding loss (MW)"])
    fig.add_bar(x=agg["link"], y=agg["compounding"], marker_color=C["deep"], showlegend=False, row=1, col=1,
                hovertemplate="%{x}<br>Compounding pairs: %{y}<extra></extra>")
    fig.add_bar(x=agg["link"], y=agg["p10_super_mw"], marker_color=C["red"], showlegend=False, row=1, col=2,
                hovertemplate="%{x}<br>P10 compounding loss: %{y:.0f} MW<extra></extra>")
    style_plotly_white(fig, "", 375, "", margin_t=62)
    fig.update_yaxes(title_text="Pair count", row=1, col=1)
    fig.update_yaxes(title_text="Extra MW lost beyond linear sum", row=1, col=2)
    return chart_spec("b5", "Exhibit 3.2: Distribution and tail severity of N-1-1 concurrent-outage compounding by interconnector",
                      "All tested concurrent outage family pairs (>= 24 overlapping half-hours and >= 24 standalone half-hours each)",
                      "Highlights which interconnectors suffer the sharpest non-linear N-1-1 ceiling collapses when planned maintenance windows overlap.",
                      fig, "nos_n11_superadditivity.csv")


def b6_reliability_curves():
    df = ev("nos_reliability_curves.csv")
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.11, subplot_titles=["Binding layer reliability", "Setter layer reliability"])
    for ci, lay in enumerate(["binding", "setter"], 1):
        sub = df[df["layer"] == lay]
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color="#9fb3c8", dash="dash", width=1.2), name="Perfect calibration", showlegend=(ci == 1), row=1, col=ci)
        for mkey, mlbl, col in [("raw_outlook", "Legacy raw outlook", C["red"]), ("calibrated_eb_iso", "EB + Isotonic calibrated", C["deep"])]:
            g = sub[(sub["model"] == mkey) & (sub["n"] >= 10)].sort_values("p_mean")
            fig.add_scatter(
                x=g["p_mean"] * 100, y=g["y_mean"] * 100, mode="lines+markers", name=mlbl, legendgroup=mlbl,
                showlegend=(ci == 1), line=dict(color=col, width=2.4), marker=dict(size=7),
                customdata=g["n"], hovertemplate=mlbl + "<br>Predicted: %{x:.1f}%<br>Realised: %{y:.1f}%<br>n = %{customdata:,}<extra></extra>",
                row=1, col=ci,
            )
        fig.update_xaxes(title_text="Predicted probability (%)", range=[0, 95], row=1, col=ci)
        fig.update_yaxes(title_text="Realised frequency (%)" if ci == 1 else "", range=[0, 95], row=1, col=ci)
    # Fix diagonal to 0..95 scale
    for tr in fig.data:
        if tr.name == "Perfect calibration":
            tr.x = [0, 95]
            tr.y = [0, 95]
    style_plotly_white(fig, "", 390, "", margin_t=68, legend_y=1.18)
    return chart_spec("b6", "Exhibit 4.1: Out-of-sample reliability curves before and after chronological Empirical-Bayes isotonic calibration",
                      "Strictly expanding-origin out-of-sample predictions across origins 2 to 12 (September 2025 to August 2026)",
                      "Eliminates the legacy 36%-predicted-versus-15%-realised over-prediction bias on binding probabilities and brings both binding and setter layers tightly onto the 45-degree calibration line.",
                      fig, "nos_reliability_curves.csv")


def b7_skilful_cells_by_lead():
    df = ev("nos_outlook_calibration.csv")
    lb_order = ["0-7", "8-30", "31-90", "91-365"]
    agg = df.groupby("lead_band", as_index=False).agg(
        total=("cal_skilful", "count"),
        raw_sk=("raw_skilful", "sum"),
        cal_sk=("cal_skilful", "sum"),
        cal_beats=("cal_beats_raw", "sum"),
    ).set_index("lead_band").reindex(lb_order).reset_index()
    fig = go.Figure()
    fig.add_bar(name="Legacy raw outlook skilful (out of 24)", x=agg["lead_band"], y=agg["raw_sk"], marker_color=C["slate"])
    fig.add_bar(name="EB + Isotonic calibrated skilful (out of 24)", x=agg["lead_band"], y=agg["cal_sk"], marker_color=C["deep"])
    fig.add_bar(name="Calibrated beats raw Brier (out of 24)", x=agg["lead_band"], y=agg["cal_beats"], marker_color=C["teal"])
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "Cell count (out of 24 per lead band)", 375, "Booking lead horizon (days)")
    return chart_spec("b7", "Exhibit 4.2: Out-of-sample skilful cell counts across lead horizons (96 total cells)",
                      "Cells beating both system-normal and last-year Brier baselines on identical out-of-sample rows",
                      "Calibration lifts skilful coverage substantially across every lead band, with the largest gains at 8 to 90 day horizons where booking withdrawals and family-inference noise were previously unshrunk.",
                      fig, "nos_outlook_calibration.csv")


def b8_corridor_pooled_risk():
    df = ev("line_corridor_pooled_risk.csv").sort_values("mean_eb_cap_eff_mw", ascending=True)
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.14, subplot_titles=["Mean EB capacity impact (MW)", "Mean EB price & spread ($/MWh)"])
    fig.add_bar(y=df["corridor"], x=df["mean_eb_cap_eff_mw"], orientation="h", marker_color=C["deep"], showlegend=False, row=1, col=1,
                hovertemplate="%{y}<br>Mean EB cap drop: %{x:.0f} MW<extra></extra>")
    fig.add_bar(y=df["corridor"], x=df["mean_eb_spread_eff_aud"], orientation="h", name="Spread delta", marker_color=C["gold"], row=1, col=2,
                hovertemplate="%{y}<br>Mean EB spread delta: $%{x:.1f}/MWh<extra></extra>")
    fig.add_bar(y=df["corridor"], x=df["mean_eb_price_eff"], orientation="h", name="Regional price delta", marker_color=C["teal"], row=1, col=2,
                hovertemplate="%{y}<br>Mean EB price delta: $%{x:.1f}/MWh<extra></extra>")
    style_plotly_white(fig, "", 410, "", margin_t=64, legend_y=1.18)
    fig.update_xaxes(title_text="MW", row=1, col=1)
    fig.update_xaxes(title_text="$/MWh", row=1, col=2)
    fig.update_yaxes(showticklabels=False, row=1, col=2)
    fig.update_layout(margin=dict(l=225, r=24, t=64, b=54))
    return chart_spec("b8", "Exhibit 5.1: Hierarchical corridor-level outage risk across all 50 NEM transmission lines",
                      "Eight electrically coherent regional corridors · Empirical-Bayes partial-pooled means",
                      "Consolidates the 50 monitored transmission lines into eight physical corridors, revealing where transmission outages cut transfer ceilings deepest versus where regional prices separate most.",
                      fig, "line_corridor_pooled_risk.csv")


def b9_eb_shrinkage_50_lines():
    df = ev("line_50_directory.csv").dropna(subset=["raw_cap_eff_mw", "eb_cap_eff_mw"])
    df["bucket"] = np.where(df["events"] <= 3, "Low-sample lines (<= 3 events)", "Well-observed lines (>= 4 events)")
    fig = go.Figure()
    lim_lo = float(min(df["raw_cap_eff_mw"].min(), df["eb_cap_eff_mw"].min()) - 25)
    lim_hi = float(max(df["raw_cap_eff_mw"].max(), df["eb_cap_eff_mw"].max()) + 25)
    fig.add_scatter(x=[lim_lo, lim_hi], y=[lim_lo, lim_hi], mode="lines", line=dict(color="#9fb3c8", dash="dash"), name="No shrinkage (45°)")
    for bkt, col in [("Well-observed lines (>= 4 events)", C["deep"]), ("Low-sample lines (<= 3 events)", C["red"])]:
        g = df[df["bucket"] == bkt]
        fig.add_scatter(
            x=g["raw_cap_eff_mw"], y=g["eb_cap_eff_mw"], mode="markers", name=bkt,
            marker=dict(color=col, size=np.clip(g["events"] * 0.55 + 6, 7, 18), opacity=0.82, line=dict(width=0.7, color="#ffffff")),
            customdata=np.stack([g["asset"], g["corridor"], g["events"], g["eb_cap_weight"] * 100], axis=-1),
            hovertemplate="%{customdata[0]} (%{customdata[1]})<br>Events: %{customdata[2]}<br>Raw cap delta: %{x:.0f} MW<br>EB pooled: %{y:.0f} MW (weight %{customdata[3]:.0f}%)<extra></extra>",
        )
    style_plotly_white(fig, "Empirical-Bayes corridor-pooled capacity effect (MW)", 395, "Raw single-line matched capacity effect (MW)")
    return chart_spec("b9", "Exhibit 5.2: Empirical-Bayes shrinkage across the 50-line cohort by sample event count",
                      "Low-event lines (<= 3 events, red) shrink strongly toward their corridor prior; well-observed lines retain line-specific signal",
                      "Solves the small-sample inferential fragility of legacy line-by-line testing without discarding individual line evidence when event counts are high.",
                      fig, "line_50_directory.csv")


def b10_line6_line8_peers():
    df = ev("line_deep_dives_6_8.csv").dropna(subset=["asset"])
    df = df.sort_values("events", ascending=True)
    fig = make_subplots(rows=1, cols=2, horizontal_spacing=0.14, subplot_titles=["Matched NSW price effect ($/MWh)", "Matched worst IC capacity effect (MW)"])
    fig.add_bar(name="Raw line estimate", y=df["asset"], x=df["raw_price_eff"], orientation="h", marker_color=C["sky"], legendgroup="raw", row=1, col=1)
    fig.add_bar(name="EB corridor-pooled estimate", y=df["asset"], x=df["eb_price_eff_aud"], orientation="h", marker_color=C["deep"], legendgroup="eb", row=1, col=1)
    fig.add_bar(name="Raw line estimate", y=df["asset"], x=df["raw_cap_eff_mw"], orientation="h", marker_color=C["sky"], legendgroup="raw", showlegend=False, row=1, col=2)
    fig.add_bar(name="EB corridor-pooled estimate", y=df["asset"], x=df["eb_cap_eff_mw"], orientation="h", marker_color=C["deep"], legendgroup="eb", showlegend=False, row=1, col=2)
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "", 375, "", margin_t=64, legend_y=1.18)
    fig.update_xaxes(title_text="$/MWh", row=1, col=1)
    fig.update_xaxes(title_text="MW", row=1, col=2)
    fig.update_yaxes(showticklabels=False, row=1, col=2)
    fig.update_layout(margin=dict(l=165, r=24, t=64, b=54))
    return chart_spec("b10", "Exhibit 6.1: Capital–Canberra Line 6 and Dapto–Marulan Line 8 benchmarked against Southern NSW 330 kV peers",
                      "Raw single-line estimates versus Empirical-Bayes Southern NSW corridor-pooled estimates",
                      "Line 6 (only 2 historical events) receives stronger corridor pooling than Line 8 (8 events) and Marulan Line 5 (11 events), preventing noise from masquerading as a structural regime.",
                      fig, "line_deep_dives_6_8.csv")


def all_charts() -> dict[str, dict]:
    items = [
        b1_booking_reliability(), b2_nos_sra_day_impact(), b3_cap_vs_spread_scatter(),
        b4_n11_superadditivity(), b5_n11_spread_compounding(), b6_reliability_curves(),
        b7_skilful_cells_by_lead(), b8_corridor_pooled_risk(), b9_eb_shrinkage_50_lines(),
        b10_line6_line8_peers(),
    ]
    return {c["id"]: c for c in items}
