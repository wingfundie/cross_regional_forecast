"""Build Flagship B: Outage Risk & NOS Regime Handbook (v2)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import charts  # noqa: E402
from nemic.experiments.vb_report_kit import (  # noqa: E402
    assemble_flagship_html,
    build_directory_widget_html,
)

EV = HERE / "evidence"

CHAPTER_ORDER = [
    "chapters/01_nos_booking_reliability_and_matching.md",
    "chapters/02_nos_economic_spread_and_sra_impacts.md",
    "chapters/03_n11_concurrent_outage_compounding.md",
    "chapters/04_calibrated_nos_binding_outlook.md",
    "chapters/05_corridor_pooling_fifty_lines.md",
    "chapters/06_line6_and_line8_forensic_deep_dives.md",
    "chapters/07_desk_playbook_and_live_screening.md",
    "appendices/appendix_a_equations.md",
    "appendices/appendix_b_schema_and_lineage.md",
    "appendices/appendix_c_sources.md",
]

PART_MAP = {
    "chapters/01_nos_booking_reliability_and_matching.md": (
        "Part I · Network Outage Scheduler Plumbing & Economic Attribution",
        "Booking drift, matched-pair controls, and $/MWh plus $/day SRA impacts",
        "Establishes why raw outage calendars deceive desks, then values every supported outage family across all six interconnectors in regional price spreads and settled SRA dollars.",
    ),
    "chapters/03_n11_concurrent_outage_compounding.md": (
        "Part II · N-1-1 Compounding & Calibrated Forward Outlook",
        "Non-linear concurrent-outage super-additivity and chronological probability calibration",
        "Quantifies extra transfer losses when maintenance windows collide and repairs the legacy outlook's systematic over-prediction across all 96 lead-band cells.",
    ),
    "chapters/05_corridor_pooling_fifty_lines.md": (
        "Part III · Transmission-Line Corridor Pooling & Line 6 / Line 8 Deep Dives",
        "Empirical-Bayes partial pooling across all 50 lines and Southern NSW forensics",
        "Groups low-sample lines into eight electrically coherent corridors and benchmarks Capital–Canberra Line 6 and Dapto–Marulan Line 8 against their 330 kV peers.",
    ),
    "chapters/07_desk_playbook_and_live_screening.md": (
        "Part IV · Operational Outage-Risk Screening Playbook",
        "Calibrated forward-book screening and SRA hedge sizing rules",
        "Translates calibrated outage probabilities, N-1-1 overlap alerts, and corridor risk scores into concrete desk screening workflows.",
    ),
    "appendices/appendix_a_equations.md": (
        "Reference Appendices",
        "Mathematical identities, relocated schemas, and evidence register",
        "Consolidates KaTeX equations, NOS/MMS table mappings, rebuild commands, and scope qualifications.",
    ),
}


def build_diagrams() -> dict[str, str]:
    d1 = """<div id="outagePipeline" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D1: From raw NOS booking to settled $/day SRA residue impact</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>1 · NOS booking</h3><span>Booked start / end &amp; asset</span><span>Subject to withdrawal &amp; drift</span><span>Linked to GENCONSETID family</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>2 · Control match</h3><span>Exact half-hour calendar match</span><span>Same season, time, system state</span><span>Eliminates diurnal confounding</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>3 · Physical shift</h3><span>Directional limit ΔCap (MW)</span><span>Binding &amp; setter rate jump</span><span>Headroom &amp; flow pass-through</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>4 · Dollar impact</h3><span>Regional ΔSpread ($/MWh)</span><span>Settled ΔSRA ($/day)</span><span>7-day block-bootstrap 95% CI</span></div></div>
<p class="figure-note">Every economic outage estimate pairs treated half-hours strictly against matched non-outage control half-hours on the exact same interconnector and direction.</p></div>"""

    d2 = """<div id="calibrationFix" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D2: Strictly chronological Empirical-Bayes + Isotonic outlook calibration pipeline</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Raw legacy score</h3><span>Historical family rate q</span><span>Over-predicts 36% vs 15%</span><span>Ignores withdrawal hazard</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Hazard &amp; EB shrink</h3><span>Lead-band occurrence scale</span><span>Shrink to cell prior (m₀=25)</span><span>Weight by family_probability</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Isotonic map</h3><span>Fit strictly on past origins</span><span>Monotonic per layer × lead</span><span>Zero future leakage</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>Verified OOS score</h3><span>Scored on identical rows</span><span>Beats normal &amp; last-year</span><span>Eliminates reliability bias</span></div></div>
<p class="figure-note">Calibration is refit chronologically at each monthly origin using strictly earlier as-of snapshots so out-of-sample Brier skill and ECE remain fully audit-clean.</p></div>"""

    d3 = """<div id="corridorPooling" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D3: Hierarchical Empirical-Bayes corridor pooling for low-sample transmission lines</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Raw line estimate</h3><span>50 lines (many n ≤ 3 events)</span><span>Wide CIs &amp; noisy extremes</span><span>Binary tail tests underpowered</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Corridor prior μ<sub>c</sub></h3><span>8 regional electrical corridors</span><span>Inverse-variance corridor mean</span><span>Between-line variance τ<sub>c</sub>²</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Partial pooling</h3><span>Weight w<sub>i</sub> = τ<sub>c</sub>²/(τ<sub>c</sub>² + s<sub>i</sub>²)</span><span>Low-n lines borrow strength</span><span>High-n lines keep signal</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>Continuous risk</h3><span>EB ΔCap (MW) &amp; ΔSpread</span><span>Binding |MV| severity</span><span>Actionable 50-line register</span></div></div>
<p class="figure-note">Partial pooling prevents two-event lines such as Capital–Canberra Line 6 from being dismissed as zero-signal or over-reacted to as extreme outliers.</p></div>"""
    return {"outagePipeline": d1, "calibrationFix": d2, "corridorPooling": d3}


def build_directories() -> tuple[dict[str, str], list[dict]]:
    # 1. NOS Economic Effects Directory
    ne = pd.read_csv(EV / "nos_economic_effects.csv").head(260).copy()
    ne["sra_k"] = ne["sra_day_effect_aud"] / 1e3
    ne_cols = [
        {"key": "link", "label": "Link"},
        {"key": "direction", "label": "Dir"},
        {"key": "GENCONSETID", "label": "Outage family"},
        {"key": "matched_hh", "label": "Matched hh", "num": True, "fmt": "int"},
        {"key": "effect_capacity", "label": "Cap Δ (MW)", "num": True, "fmt": "f1"},
        {"key": "spread_effect_aud", "label": "Spread Δ ($/MWh)", "num": True, "fmt": "aud2"},
        {"key": "sra_k", "label": "SRA Δ ($k/day)", "num": True, "fmt": "aud2"},
        {"key": "treated_median_abs_mv", "label": "Med |MV|", "num": True, "fmt": "aud0"},
    ]
    ne_html = build_directory_widget_html(
        "nosEconDirectory", "Interactive Lookup · Supported Outage Family Economic Directory",
        "Search and sort top 260 matched NOS outage family-directions across all six interconnectors",
        "Filter by interconnector or sort by $/day SRA impact, $/MWh spread change, or MW capacity drop.",
        ne_cols, filter_label="link", filter_options=["VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"],
        csv_name="nos_economic_effects.csv",
    )
    ne_data = {
        "id": "nosEconDirectory", "cols": ne_cols, "filterKey": "link", "defaultSort": 6, "defaultAsc": False, "pageSize": 15,
        "rows": ne[[c["key"] for c in ne_cols]].fillna(0).to_dict("records"),
    }

    # 2. 50-Line Corridor Pooled Directory
    d50 = pd.read_csv(EV / "line_50_directory.csv").copy()
    d50["eb_w_pct"] = d50["eb_cap_weight"].fillna(0) * 100.0
    l_cols = [
        {"key": "region", "label": "Region"},
        {"key": "corridor", "label": "Corridor"},
        {"key": "asset", "label": "Transmission line"},
        {"key": "events", "label": "Events", "num": True, "fmt": "int"},
        {"key": "raw_cap_eff_mw", "label": "Raw Cap Δ", "num": True, "fmt": "f0"},
        {"key": "eb_cap_eff_mw", "label": "EB Cap Δ", "num": True, "fmt": "f0"},
        {"key": "eb_spread_eff_aud", "label": "EB Spread Δ", "num": True, "fmt": "aud2"},
        {"key": "max_median_abs_mv", "label": "Max |MV|", "num": True, "fmt": "aud0"},
    ]
    l_html = build_directory_widget_html(
        "line50Directory", "Interactive Lookup · 50-Line Hierarchical Corridor Risk Register",
        "Search and compare raw versus Empirical-Bayes pooled risk across all 50 NEM transmission lines",
        "Filter by NEM region or sort by Empirical-Bayes capacity drop, spread widening, or binding marginal value.",
        l_cols, filter_label="region", filter_options=["NSW1", "VIC1", "QLD1", "SA1", "TAS1"],
        csv_name="line_50_directory.csv",
    )
    l_data = {
        "id": "line50Directory", "cols": l_cols, "filterKey": "region", "defaultSort": 5, "defaultAsc": True, "pageSize": 15,
        "rows": d50[[c["key"] for c in l_cols]].fillna(0).to_dict("records"),
    }

    # 3. Calibrated Live Outlook Directory
    lv = pd.read_csv(EV / "nos_live_outlook_calibrated.csv").head(120).copy()
    if "top_binding_p_cal" in lv.columns:
        lv["p_raw_pct"] = lv["top_binding_p_raw"] * 100.0
        lv["p_cal_pct"] = lv["top_binding_p_cal"] * 100.0
        lv_cols = [
            {"key": "name", "label": "Link"},
            {"key": "direction", "label": "Dir"},
            {"key": "week", "label": "Week"},
            {"key": "outages", "label": "Outages", "num": True, "fmt": "int"},
            {"key": "largest_reduction_mw", "label": "Max ΔCap (MW)", "num": True, "fmt": "f0"},
            {"key": "top_binding_eq", "label": "Top binding eq."},
            {"key": "p_raw_pct", "label": "Raw P (%)", "num": True, "fmt": "f1"},
            {"key": "p_cal_pct", "label": "Cal. P (%)", "num": True, "fmt": "f1"},
        ]
        f_key = "name"
    else:
        lv["p_raw_pct"] = lv.get("p_binding_raw", 0) * 100.0
        lv["p_cal_pct"] = lv.get("p_binding_cal", 0) * 100.0
        lv_cols = [
            {"key": "name", "label": "Link"},
            {"key": "direction", "label": "Dir"},
            {"key": "OUTAGEID", "label": "Outage ID"},
            {"key": "family", "label": "Family"},
            {"key": "lead_band", "label": "Lead"},
            {"key": "p_raw_pct", "label": "Raw P (%)", "num": True, "fmt": "f1"},
            {"key": "p_cal_pct", "label": "Cal. P (%)", "num": True, "fmt": "f1"},
        ]
        f_key = "name"
    lv_html = build_directory_widget_html(
        "liveOutlookDirectory", "Interactive Lookup · Calibrated Forward Outage Watchlist",
        "Top forward outage weeks / bookings ranked by isotonic-calibrated binding probability",
        "Compares raw legacy binding probabilities against calibrated probabilities trained on the full 12-origin history.",
        lv_cols, filter_label="link", filter_options=["VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"],
        csv_name="nos_live_outlook_calibrated.csv",
    )
    lv_data = {
        "id": "liveOutlookDirectory", "cols": lv_cols, "filterKey": f_key, "defaultSort": len(lv_cols) - 1, "defaultAsc": False, "pageSize": 12,
        "rows": lv[[c["key"] for c in lv_cols]].fillna("").to_dict("records"),
    }
    return {"nosEconDirectory": ne_html, "line50Directory": l_html, "liveOutlookDirectory": lv_html}, [ne_data, l_data, lv_data]


def main():
    N = json.loads((EV / "headline_numbers.json").read_text(encoding="utf-8"))
    widgets_html, dir_data = build_directories()
    charts_map = charts.all_charts()
    diagrams_map = build_diagrams()
    clean_v = lambda k: str(N[k]).replace("\\$", "$")

    bullets = [
        f"<strong>Economic attribution translates outage MW into real $/MWh spreads and $/day SRA impacts across {N['c7a_supported_family_dirs']} family-directions.</strong> Matched-pair valuation identifies {N['c7a_sra_sig_count']} family-directions with statistically non-zero daily SRA shifts, spanning from {clean_v('c7a_top_gain_sra')} ({N['c7a_top_gain_fam']} on {N['c7a_top_gain_link']}) down to {clean_v('c7a_top_loss_sra')} ({N['c7a_top_loss_fam']} on {N['c7a_top_loss_link']}).",
        f"<strong>Chronological Empirical-Bayes and isotonic calibration fixes the legacy outlook's over-prediction bias.</strong> Across all {N['c7b_total_cells']} layer-by-lead-by-corridor cells on identical out-of-sample rows, calibrated probabilities beat raw scores on {N['c7b_cal_beats_raw']}/96 cells, expand skilful coverage from {N['c7b_raw_skilful']}/96 to {N['c7b_cal_skilful']}/96 cells, and cut binding Expected Calibration Error from {N['c7b_ece_raw_bind']} to {N['c7b_ece_cal_bind']}.",
        f"<strong>N-1-1 concurrent outages compound non-linearly beyond the linear sum of standalone drops.</strong> Testing {N['c8_pairs_tested']} overlapping family pairs isolates {N['c8_compounding_pairs']} statistically super-additive pairs where concurrent maintenance slashes transfer capacity deeper than additive estimates, led by {N['c8_worst_pair']} on {N['c8_worst_link']} ({N['c8_worst_super_mw']} extra loss).",
        f"<strong>Hierarchical corridor pooling stabilises all {N['c9_total_lines']} monitored transmission lines across {N['c9_total_corridors']} electrical corridors.</strong> Empirical-Bayes partial pooling resolves small-sample noise on low-event assets such as Capital–Canberra Line 6 ({N['c9_line6_events']} events) while preserving line-specific evidence on well-observed assets like Dapto–Marulan Line 8 ({N['c9_line8_events']} events).",
    ]
    brief = [
        ("Evidence base", f"24 months of NOS episodes ({N['bk_total_episodes']} booked across 6 links), 126,582 walk-forward outlook rows (12 chronological monthly origins), and 50 transmission lines ({N['c9_total_events']} verified events)."),
        ("Upgrades delivered", "C7a NOS $/MWh & $/day SRA economics; C7b chronological EB + isotonic outlook calibration; C8 N-1-1 concurrent super-additivity; C9 50-line hierarchical corridor pooling + Line 6 & Line 8 deep dives."),
        ("Legacy preserved", "All baseline files in reports/nos_outage_regime_research_20260924/ and reports/line_outage_risk_v1/ remain untouched."),
        ("Permitted claim", "Matched observational attribution and walk-forward research-only outlook calibration; not a deployed live outage-alert service."),
    ]
    downloads = [
        "nos_economic_effects.csv", "nos_outlook_calibration.csv", "nos_reliability_curves.csv",
        "nos_live_outlook_calibrated.csv", "nos_n11_superadditivity.csv", "line_corridor_pooled_risk.csv",
        "line_50_directory.csv", "line_deep_dives_6_8.csv", "nos_booking_reliability_summary.csv",
        "headline_numbers.json",
    ]
    mf = assemble_flagship_html(
        report_dir=HERE,
        output_html_name="Outage_Risk_Handbook_v2.html",
        page_title="Outage Risk & NOS Regime Handbook v2 | IC Flow Forecasting",
        brand_sub="Outage Regimes &amp;<br>Transmission Risk",
        dateline_top="Flagship Edition B · Version 2 (Virtual Barrels)",
        dateline_bottom="Australian National Electricity Market · NOS & 50 Transmission Lines",
        hero_kicker="Transmission Outages, Economic Risk & Calibrated Outlooks",
        hero_title="NEM transmission outage risk and NOS regimes:",
        hero_accent="SRA dollar impacts, N-1-1 compounding, calibrated outlooks, and 50-line corridor pooling",
        nav_links=[
            ("#chapter-1", "NOS Reliability"), ("#chapter-2", "SRA Dollars"), ("#chapter-3", "N-1-1 Risk"),
            ("#chapter-4", "Calibration"), ("#chapter-5", "50 Lines"), ("#chapter-6", "Line 6 & 8"),
            ("#chapter-7", "Playbook"), ("#downloads", "Data"),
        ],
        summary_bullets_html=bullets,
        brief_items=brief,
        dual_paths=(
            ("Desk & Hedge Path", 'Read <a href="#chapter-2">Ch. 2 (SRA Dollar Impacts)</a>, <a href="#chapter-3">Ch. 3 (N-1-1 Compounding)</a>, <a href="#chapter-6">Ch. 6 (Line 6 &amp; 8)</a>, and <a href="#chapter-7">Ch. 7 (Live Watchlist)</a>.'),
            ("Quant & Calibration Path", 'Read <a href="#chapter-1">Ch. 1 (Matching &amp; Drift)</a>, <a href="#chapter-4">Ch. 4 (EB/Isotonic Calibration)</a>, <a href="#chapter-5">Ch. 5 (Corridor Pooling)</a>, and <a href="#chapter-8">Appendices A–C</a>.'),
        ),
        chapter_order=CHAPTER_ORDER,
        part_map=PART_MAP,
        headline_numbers=N,
        charts_map=charts_map,
        diagrams_map=diagrams_map,
        widgets_html_map=widgets_html,
        directory_widgets_data=dir_data,
        download_files=downloads,
        footer_left="IC Flow Forecasting · Flagship Edition B · Outage Risk &amp; NOS Regime Handbook v2<br>September 2024 to August 2026 · Fixed NEM time (UTC+10)",
        footer_right="Matched observational attribution &amp; chronological walk-forward research; not a live alert service.",
        code_files_for_manifest=[
            ROOT / "nemic/experiments/outage_risk_v2.py",
            ROOT / "nemic/experiments/vb_report_kit.py",
        ],
    )
    print(json.dumps(mf, indent=2), flush=True)


if __name__ == "__main__":
    main()
