"""Twelve curated inline Plotly exhibits for Flagship A (Constraint Pressure Atlas v2)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from nemic.experiments.vb_report_kit import (
    LINK_COLORS,
    PALETTE as C,
    TECH_COLORS,
    chart_spec,
    style_plotly_white,
)

EV = Path(__file__).resolve().parent / "evidence"
LINK_ORDER = ["VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"]


def ev(name: str) -> pd.DataFrame:
    return pd.read_csv(EV / name)


def a1_six_link_parity():
    df = ev("six_link_parity_summary.csv")
    fig = make_subplots(rows=1, cols=2, subplot_titles=["Tight-headroom intervals (<= 50 MW, %)", "Sharp 30-min contraction episodes (24 months)"])
    for d_key, lbl, col in [("upper", "Forward (upper)", C["deep"]), ("lower", "Reverse (lower)", C["sky"])]:
        sub = df[df["direction"] == d_key].set_index("link").reindex(LINK_ORDER).reset_index()
        fig.add_bar(x=sub["link"], y=sub["tight_headroom_pct"], name=lbl, marker_color=col, legendgroup=lbl, row=1, col=1,
                    hovertemplate="%{x} (" + lbl + ")<br>Tight headroom: %{y:.1f}%<extra></extra>")
        fig.add_bar(x=sub["link"], y=sub["contraction_episodes"], name=lbl, marker_color=col, legendgroup=lbl, showlegend=False, row=1, col=2,
                    hovertemplate="%{x} (" + lbl + ")<br>Contraction episodes: %{y:,}<extra></extra>")
    style_plotly_white(fig, "", 385, "", margin_t=68, legend_y=1.18)
    fig.update_yaxes(title_text="% of intervals", row=1, col=1)
    fig.update_yaxes(title_text="Episodes", row=1, col=2)
    return chart_spec("a1", "Exhibit 2.1: Full six-link parity across tight headroom and sharp contractions",
                      "All 6 NEM interconnectors · September 2024 to August 2026 (210,240 five-minute intervals per link)",
                      "Extends full 24-month constraint attribution to Directlink, Murraylink, and Basslink alongside VNI, QNI, and Heywood.",
                      fig, "six_link_parity_summary.csv")


def a2_parallel_cobinding():
    df = ev("parallel_link_cobinding.csv")
    df["label"] = df["pair"].str.replace(" (QLD-NSW)", "", regex=False).str.replace(" (VIC-SA)", "", regex=False) + " · " + df["direction"].str.title()
    fig = go.Figure()
    fig.add_bar(name="Main link tight (%)", x=df["label"], y=df["a_tight_pct"], marker_color=C["deep"])
    fig.add_bar(name="Parallel HVDC tight (%)", x=df["label"], y=df["b_tight_pct"], marker_color=C["teal"])
    fig.add_bar(name="Both tight simultaneously (%)", x=df["label"], y=df["both_tight_pct"], marker_color=C["gold"])
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "% of five-minute intervals", 360)
    return chart_spec("a2", "Exhibit 2.2: Simultaneous tight-headroom co-binding on pooled parallel corridors",
                      "QNI + Directlink (QLD–NSW) and Heywood + Murraylink (VIC–SA) · 24 months",
                      "Because Directlink pools into QNI SRA buckets and Murraylink pools into VIC–SA SRA buckets, parallel co-binding determines whether backup transfer remains available during stress.",
                      fig, "parallel_link_cobinding.csv")


def a3_reconstruction_mae_audit():
    df = ev("reconstruction_mae_audit.csv")
    agg = df.groupby(["link", "setter_family"], as_index=False)["err_contribution_mw"].sum()
    top_fams = agg.groupby("setter_family")["err_contribution_mw"].sum().nlargest(6).index.tolist()
    agg["fam_clean"] = np.where(agg["setter_family"].isin(top_fams), agg["setter_family"], "Other families")
    piv = agg.groupby(["link", "fam_clean"], as_index=False)["err_contribution_mw"].sum()
    # Average across upper & lower directions (divide by 2)
    piv["avg_mae_contrib"] = piv["err_contribution_mw"] / 2.0
    fig = go.Figure()
    fam_cols = [C["deep"], C["blue"], C["gold"], C["teal"], C["purple"], C["red"], C["slate"]]
    for i, fam in enumerate(sorted(piv["fam_clean"].unique())):
        sub = piv[piv["fam_clean"] == fam].set_index("link").reindex(LINK_ORDER).fillna(0.0).reset_index()
        fig.add_bar(name=fam, x=sub["link"], y=sub["avg_mae_contrib"], marker_color=fam_cols[i % len(fam_cols)],
                    hovertemplate="%{x}<br>" + fam + ": %{y:.1f} MW MAE contribution<extra></extra>")
    fig.update_layout(barmode="stack")
    style_plotly_white(fig, "Mean directional reconstruction MAE (MW)", 390)
    return chart_spec("a3", "Exhibit 3.1: Root-cause attribution of envelope reconstruction error across six links",
                      "Contribution to directional reconstruction MAE (MW) by AEMO reported setter family",
                      "Explains why QNI and Heywood show large reconstruction residuals relative to VNI by isolating unmatched standing versions, ramp/discretionary sets, and ROCOF/UFLS equations.",
                      fig, "reconstruction_mae_audit.csv")


def a4_diurnal_ci_profiles():
    df = ev("diurnal_seasonal_ci_profiles.csv")
    # Show forward-direction median capacity with 95% CI across 4 diurnal blocks (all-season average of seasonal medians)
    blk_order = ["Overnight (21:00-05:55)", "Morning Peak (06:00-08:55)", "Solar Midday (09:00-15:55)", "Evening Ramp (16:00-20:55)"]
    short = {"Overnight (21:00-05:55)": "Overnight", "Morning Peak (06:00-08:55)": "Morning", "Solar Midday (09:00-15:55)": "Solar Midday", "Evening Ramp (16:00-20:55)": "Evening Ramp"}
    sub = df[df["direction"] == "upper"].groupby(["link", "block"], as_index=False).agg(
        med=("median_cap_mw", "mean"), lo=("cap_ci_lo", "mean"), hi=("cap_ci_hi", "mean")
    )
    fig = go.Figure()
    for lk in LINK_ORDER:
        g = sub[sub["link"] == lk].set_index("block").reindex(blk_order).reset_index()
        fig.add_scatter(
            x=[short[b] for b in g["block"]], y=g["med"], name=lk, mode="lines+markers",
            line=dict(color=LINK_COLORS[lk], width=2.2),
            error_y=dict(type="data", symmetric=False, array=(g["hi"] - g["med"]).clip(lower=0), arrayminus=(g["med"] - g["lo"]).clip(lower=0), thickness=1.2),
            hovertemplate=lk + " · %{x}<br>Median forward cap: %{y:.0f} MW<extra></extra>",
        )
    style_plotly_white(fig, "Forward directional capacity (MW, 95% block CI)", 385)
    return chart_spec("a4", "Exhibit 4.1: Diurnal forward-capacity profiles with seven-day block-bootstrap 95% intervals",
                      "MW · Mean across four seasonal blocks (September 2024 to August 2026)",
                      "Replaces unweighted descriptive point profiles with formal seven-day block-bootstrap confidence intervals that respect multi-day weather and outage persistence.",
                      fig, "diurnal_seasonal_ci_profiles.csv")


def a5_tight_headroom_heatmap():
    df = ev("diurnal_seasonal_ci_profiles.csv")
    # Forward tight-headroom % by link x season (averaged across diurnal blocks)
    piv = df[df["direction"] == "upper"].pivot_table(index="link", columns="season", values="tight_headroom_pct", aggfunc="mean")
    seas_order = ["Summer", "Autumn", "Winter", "Spring"]
    piv = piv.reindex(index=LINK_ORDER, columns=seas_order)
    fig = go.Figure(go.Heatmap(
        x=seas_order, y=LINK_ORDER, z=piv.to_numpy(),
        colorscale=[[0, "#edf3f7"], [0.5, "#83b6d9"], [1, "#073c64"]],
        texttemplate="%{z:.1f}%", colorbar=dict(title="% tight", thickness=12),
        hovertemplate="%{y} · %{x}<br>Forward tight headroom: %{z:.1f}%<extra></extra>",
    ))
    style_plotly_white(fig, "", 350)
    fig.update_yaxes(autorange="reversed")
    return chart_spec("a5", "Exhibit 4.2: Seasonal concentration of tight forward headroom (<= 50 MW)",
                      "% of five-minute intervals with forward headroom at or below 50 MW",
                      "Highlights where routine seasonal transfer demand presses directly against active dispatch bounds rather than clearing with idle slack.",
                      fig, "diurnal_seasonal_ci_profiles.csv")


def a6_lhs_rhs_switch():
    df = ev("contraction_lhs_rhs_switch.csv")
    df["label"] = df["link"] + " (" + df["direction"].str.title() + ")"
    fig = go.Figure()
    fig.add_bar(name="Active-leader equation switch (%)", x=df["label"], y=df["switch_drop_share_pct"], marker_color=C["deep"])
    fig.add_bar(name="Same-equation LHS generator ramp (%)", x=df["label"], y=df["lhs_gen_drop_share_pct"], marker_color=C["teal"])
    fig.add_bar(name="Same-equation RHS / Z-term shift (%)", x=df["label"], y=df["rhs_z_drop_share_pct"], marker_color=C["gold"])
    fig.update_layout(barmode="stack")
    style_plotly_white(fig, "Share of total 30-min contraction MW (%)", 400)
    fig.update_xaxes(tickangle=-25)
    return chart_spec("a6", "Exhibit 5.1: Full-population decomposition of sharp contractions into switches, LHS ramps, and RHS shifts",
                      "% of cumulative 30-minute contraction MW across all 12 directional populations (24 months)",
                      "Quantifies the exact split between exogenous equation switches (outage/ramp set takeovers), same-equation LHS generator ramping, and same-equation RHS/dynamic-rating shifts.",
                      fig, "contraction_lhs_rhs_switch.csv")


def a7_cascade_heatmap():
    df = ev("cross_link_cascades.csv")
    piv = df.pivot(index="source_link", columns="target_link", values="lift_ratio").reindex(index=LINK_ORDER, columns=LINK_ORDER)
    z = piv.to_numpy().copy()
    np.fill_diagonal(z, np.nan)
    fig = go.Figure(go.Heatmap(
        x=LINK_ORDER, y=LINK_ORDER, z=z,
        colorscale=[[0, "#edf3f7"], [0.4, "#83b6d9"], [1, "#073c64"]],
        texttemplate="%{z:.2f}×", colorbar=dict(title="Lift", thickness=12),
        hovertemplate="If %{y} contracts → %{x} within ±30m<br>Lift vs baseline: %{z:.2f}×<extra></extra>",
        hoverongaps=False,
    ))
    style_plotly_white(fig, "Triggering link", 380, "Co-contracting link (within ±30 minutes)")
    fig.update_yaxes(autorange="reversed")
    return chart_spec("a7", "Exhibit 6.1: Six-by-six cross-link contraction cascade lift matrix (±30 minute window)",
                      "Conditional probability divided by unconditional baseline occupancy (diagonal masked)",
                      "Values above 1.0× measure genuine multi-corridor contagion where a contraction on one interconnector coincides with rapid contractions on electrically coupled neighbours.",
                      fig, "cross_link_cascades.csv")


def a8_nrm_clamping():
    df = ev("nrm_clamping_attribution.csv")
    df = df[df["forced_intervals"] > 0].copy()
    df["label"] = df["link"] + " (" + df["direction"].str.title() + ")"
    fig = go.Figure()
    fig.add_bar(name="Counter-price share of forced intervals (%)", x=df["label"], y=df["forced_during_counterprice_pct"], marker_color=C["red"])
    fig.add_bar(name="NRM / ramp setter share of forced intervals (%)", x=df["label"], y=df["nrm_or_ramp_setter_during_forced_pct"], marker_color=C["deep"])
    fig.update_layout(barmode="group")
    style_plotly_white(fig, "% of forced-negative limit intervals", 380)
    fig.update_xaxes(tickangle=-25)
    return chart_spec("a8", "Exhibit 6.2: Counter-price and NRM/ramp setter shares during forced-negative directional limits",
                      "% of intervals where reported directional capacity fell below 0 MW",
                      "Separates forced-negative limits triggered by AEMO's automated Negative Residue Management clamping from non-NRM thermal or stability loop-flow forcing.",
                      fig, "nrm_clamping_attribution.csv")


def a9_econ_vs_mech_duids():
    df = ev("duid_economic_influence.csv")
    sub = df[df["link"].isin(["VNI", "QNI", "Heywood"])].copy()
    sub = sub.groupby("link", group_keys=False).head(15)
    fig = make_subplots(rows=1, cols=3, horizontal_spacing=0.13, subplot_titles=["VNI (VIC–NSW)", "QNI (NSW–QLD)", "Heywood (VIC–SA)"])
    for i, lk in enumerate(["VNI", "QNI", "Heywood"], 1):
        g = sub[sub["link"] == lk].sort_values("rent_weighted_aud", ascending=True).tail(10)
        cols = [TECH_COLORS.get(t, C["slate"]) for t in g["tech"]]
        fig.add_bar(
            y=g["DUID"], x=g["rent_weighted_aud"] / 1e6, orientation="h",
            marker_color=cols, showlegend=False, row=1, col=i,
            customdata=np.stack([g["tech"], g["rank_all_mw"], g["rank_rent_aud"]], axis=-1),
            hovertemplate="%{y} (%{customdata[0]})<br>Rent-weighted: $%{x:.2f}m<br>Mech rank #%{customdata[1]} → Econ rank #%{customdata[2]}<extra></extra>",
        )
    style_plotly_white(fig, "", 410, "", margin_t=62)
    for col_i in (1, 2, 3):
        fig.update_xaxes(title_text="Rent weight ($m)", row=1, col=col_i)
    fig.update_layout(margin=dict(l=88, r=20, t=62, b=54))
    return chart_spec("a9", "Exhibit 7.1: Top ten generators by congestion-rent-weighted pressure on VNI, QNI, and Heywood",
                      "AUD millions · Sum of |s_i × ΔP_i| × max(spread, 0) / 12 strictly during tight-headroom intervals (coloured by technology)",
                      "Colour encodes technology class (purple = BESS, deep navy = Hydro, gold = Solar, teal = Wind, slate = Coal, red = Gas). Hover compares mechanical vs economic rank shifts.",
                      fig, "duid_economic_influence.csv")


def a10_top_shadow_constraints():
    df = ev("constraint_economic_influence.csv")
    top = df.sort_values("shadow_rent_aud_per_mw", ascending=False).head(18).sort_values("shadow_rent_aud_per_mw")
    cols = [LINK_COLORS.get(lk, C["deep"]) for lk in top["link"]]
    fig = go.Figure(go.Bar(
        y=top["CONSTRAINTID"] + " (" + top["link"] + ")",
        x=top["shadow_rent_aud_per_mw"] / 1e3,
        orientation="h", marker_color=cols,
        customdata=np.stack([top["binding_intervals"], top["mean_abs_mv_when_binding"], top["family"]], axis=-1),
        hovertemplate="%{y}<br>Shadow rent: $%{x:,.1f}k/MW<br>Binding intervals: %{customdata[0]:,}<br>Mean |MV|: $%{customdata[1]:.1f}/MWh<br>Family: %{customdata[2]}<extra></extra>",
    ))
    style_plotly_white(fig, "", 470, "Cumulative 24-month binding shadow rent ($ thousands per MW)")
    fig.update_layout(margin=dict(l=210, r=24, t=42, b=56))
    return chart_spec("a10", "Exhibit 7.2: Eighteen highest shadow-rent constraint equations across all six interconnectors",
                      "AUD thousands per MW (sum of binding intervals × mean |MV| / 12) · September 2024 to August 2026",
                      "Ranks equations by actual economic shadow price rather than non-binding leader counts, isolating the specific thermal, voltage, and transient constraints that move market prices.",
                      fig, "constraint_economic_influence.csv")


def a11_bess_impulse_signature():
    df = ev("bess_ramp_signature.csv")
    agg = df.groupby("tech", as_index=False).agg(
        p95_imp5=("p95_impulse_5m_mw", "mean"),
        p95_30m=("p95_abs_30m_mw", "mean"),
        rent_m=("rent_weighted_m", "sum"),
        eve_pct=("eve_share_pct", "mean"),
    ).sort_values("p95_imp5", ascending=False)
    fig = make_subplots(rows=1, cols=2, subplot_titles=["P95 five-minute impulse jump (MW)", "Share of total pressure in Evening Ramp (16:00–21:00)"])
    cols = [TECH_COLORS.get(t, C["slate"]) for t in agg["tech"]]
    fig.add_bar(x=agg["tech"], y=agg["p95_imp5"], marker_color=cols, showlegend=False, row=1, col=1,
                hovertemplate="%{x}<br>P95 5-min impulse: %{y:.1f} MW<extra></extra>")
    fig.add_bar(x=agg["tech"], y=agg["eve_pct"], marker_color=cols, showlegend=False, row=1, col=2,
                hovertemplate="%{x}<br>Evening Ramp share: %{y:.1f}%<extra></extra>")
    style_plotly_white(fig, "", 375, "", margin_t=62)
    fig.update_yaxes(title_text="MW per 5-min step", row=1, col=1)
    fig.update_yaxes(title_text="% of technology exposure", row=1, col=2)
    return chart_spec("a11", "Exhibit 8.1: Five-minute impulse severity and evening-ramp concentration by technology class",
                      "Six-link average across active equation DUIDs · September 2024 to August 2026",
                      "Separates fast-ramping grid-scale batteries (BESS) and dispatchable hydro from solar and wind farms across five-minute step jumps and evening peak exposure.",
                      fig, "bess_ramp_signature.csv")


def a12_tech_rent_by_link():
    df = ev("bess_ramp_signature.csv")
    techs = ["BESS", "Hydro", "Solar", "Wind", "Coal", "Gas", "Other"]
    fig = go.Figure()
    for t in techs:
        sub = df[df["tech"] == t].set_index("link").reindex(LINK_ORDER).fillna(0.0).reset_index()
        fig.add_bar(name=t, x=sub["link"], y=sub["rent_share_pct"], marker_color=TECH_COLORS[t],
                    hovertemplate="%{x} · " + t + ": %{y:.1f}% of rent-weighted pressure<extra></extra>")
    fig.update_layout(barmode="stack")
    style_plotly_white(fig, "Share of congestion-rent-weighted pressure (%)", 385)
    return chart_spec("a12", "Exhibit 8.2: Technology-class composition of congestion-rent-weighted pressure by link",
                      "% of tight-headroom congestion-rent-weighted pressure across all six interconnectors",
                      "Shows how economic constraint pressure shifts from Snowy hydro and NSW solar on VNI, to Queensland coal/solar/BESS on QNI, to South Australian BESS and wind on Heywood and Murraylink.",
                      fig, "bess_ramp_signature.csv")


def all_charts() -> dict[str, dict]:
    items = [
        a1_six_link_parity(), a2_parallel_cobinding(), a3_reconstruction_mae_audit(),
        a4_diurnal_ci_profiles(), a5_tight_headroom_heatmap(), a6_lhs_rhs_switch(),
        a7_cascade_heatmap(), a8_nrm_clamping(), a9_econ_vs_mech_duids(),
        a10_top_shadow_constraints(), a11_bess_impulse_signature(), a12_tech_rent_by_link(),
    ]
    return {c["id"]: c for c in items}
