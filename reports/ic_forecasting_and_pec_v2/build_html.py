"""Build Flagship C: Interconnector Forecasting Verdict, Clustering & Project EnergyConnect (v2)."""
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
    "chapters/01_pec_commissioning_and_ring_coupling.md",
    "chapters/02_pec_to_loop_settlement_bridge.md",
    "chapters/03_pec_issue_time_forecasting.md",
    "chapters/04_longrange_forecasting_verdict.md",
    "chapters/05_clustering_and_regime_stability.md",
    "chapters/06_three_stack_governance_and_roadmap.md",
    "appendices/appendix_a_equations.md",
    "appendices/appendix_b_schema_and_lineage.md",
    "appendices/appendix_c_sources.md",
]

PART_MAP = {
    "chapters/01_pec_commissioning_and_ring_coupling.md": (
        "Part I · Project EnergyConnect Commissioning Physics & Loop Settlement Bridge",
        "Observed NSW1–SA1 telemetry, southern-ring coupling, and AEMC ERC0386 loop payouts",
        "Characterises observed commissioning limits and feeds them directly into the AEMC net-trade loop settlement engine alongside issue-time forecast accuracy.",
    ),
    "chapters/04_longrange_forecasting_verdict.md": (
        "Part II · Interconnector Forecasting Verdict & Clustering Evidence",
        "Why 1–90 day MT PASA challengers retained baseline and where clustering stops",
        "Visualises all 50 long-range band metrics and 362 leakage-controlled clustering comparisons against matched controls under strict multiple-testing discipline.",
    ),
    "chapters/06_three_stack_governance_and_roadmap.md": (
        "Part III · Three-Stack Governance & Prospective Confirmation Roadmap",
        "Keeping conditional backtests, experiment bundles, and production scaffolding distinct",
        "Enforces strict model-stack boundaries and defines the concrete prospective receipt-time gates required before promoting any live interconnector forecast.",
    ),
    "appendices/appendix_a_equations.md": (
        "Reference Appendices",
        "Mathematical identities, relocated schemas, and evidence register",
        "Consolidates KaTeX formulas, local archive schemas, rebuild commands, and permitted claims.",
    ),
}


def build_diagrams() -> dict[str, str]:
    d1 = """<div id="pecLoopMechanics" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D1: Bridging observed EnergyConnect commissioning physics into AEMC ERC0386 loop settlement</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>1 · Observed PEC</h3><span>15,264 5-min intervals</span><span>0 / 150 / 350 MW configs</span><span>Empirical utilisation ratio</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>2 · Ring coupling</h3><span>Shares VNI 060_051 thermal</span><span>Shares Heywood/SA UFLS</span><span>3-node triangle: NSW-VIC-SA</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>3 · ERC0386 net trade</h3><span>Net regional exports E<sub>r</sub></span><span>Allocate net loop IRSR ≥ 0</span><span>Secondary positive netting</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>4 · SRA reallocation</h3><span>6 loop directional buckets</span><span>Tracks PEC share 0→800 MW</span><span>Fixed-price stress test</span></div></div>
<p class="figure-note">Historical-price counterfactuals hold regional clearing prices and pre-existing VN/VS dispatch fixed while injecting observed PEC commissioning limit profiles into the verified AEMC ERC0386 net-trade loop engine.</p></div>"""

    d2 = """<div id="forecastHorizonFrontier" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D2: Predictability frontier across NEM interconnector forecast horizons</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Intraday (0–24h)</h3><span>AEMO Predispatch strong</span><span>Constraint &amp; ramp features</span><span>Watch discrete config jumps</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Short term (2–7d)</h3><span>ST PASA + confirmed NOS</span><span>Calibrated binding skill</span><span>Beats persistence clearly</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Medium (8–30d)</h3><span>31% NOS withdrawal drift</span><span>Weather skill decays fast</span><span>Calendar baseline tough</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>Long range (31–90d)</h3><span>MT PASA vintage only</span><span>10/10 cells retain baseline</span><span>Prospective gate pending</span></div></div>
<p class="figure-note">Horizon discipline prevents trading desks from extrapolating intraday or conditional backtest accuracy into 30-to-90-day forward transfer hedging.</p></div>"""

    d3 = """<div id="modelStackBoundary" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D3: Strict separation across the repository's three modelling stacks (per AGENTS.md)</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Stack 1 · Original</h3><span>run_pipeline.py (6 links)</span><span>Realised future weather/VRE</span><span>Conditional research ONLY</span></div><div class="flow-arrow">≠</div>
<div class="mechanism-column"><h3>Stack 2 · Experiments</h3><span>nemic.experiments bundles</span><span>Diurnal/NOS, PEC, clustering</span><span>Research-only until receipt gate</span></div><div class="flow-arrow">≠</div>
<div class="mechanism-column contract-column"><h3>Stack 3 · Production</h3><span>nemic.production scaffold</span><span>Provider-neutral routing</span><span>NOT a deployed live service</span></div></div>
<p class="figure-note">Feature contracts, bundle identities, and performance claims are never mixed across the three repository stacks.</p></div>"""
    return {"pecLoopMechanics": d1, "forecastHorizonFrontier": d2, "modelStackBoundary": d3}


def build_directories() -> tuple[dict[str, str], list[dict]]:
    pf = pd.read_csv(EV / "pec_issue_time_forecast_scores.csv").copy()
    pf_cols = [
        {"key": "product", "label": "Product"},
        {"key": "direction", "label": "Direction"},
        {"key": "lead_band", "label": "Lead band"},
        {"key": "model", "label": "Model"},
        {"key": "rows", "label": "Rows", "num": True, "fmt": "int"},
        {"key": "mae_mw", "label": "MAE (MW)", "num": True, "fmt": "f1"},
        {"key": "skill_vs_persistence_pct", "label": "vs Pers (%)", "num": True, "fmt": "f1"},
        {"key": "skill_vs_aemo_pct", "label": "vs AEMO (%)", "num": True, "fmt": "f1"},
        {"key": "interval_coverage_pct", "label": "Cov (%)", "num": True, "fmt": "f1"},
    ]
    pf_html = build_directory_widget_html(
        "pecForecastDirectory", "Interactive Lookup · EnergyConnect Issue-Time Forecast Scorecard",
        "Compare all five models across Predispatch and ST PASA lead bands on identical rows",
        "Filter by forecast product or sort by MAE, skill versus persistence, or empirical interval coverage.",
        pf_cols, filter_label="product", filter_options=["Predispatch", "ST PASA"],
        csv_name="pec_issue_time_forecast_scores.csv",
    )
    pf_data = {
        "id": "pecForecastDirectory", "cols": pf_cols, "filterKey": "product", "defaultSort": 5, "defaultAsc": True, "pageSize": 15,
        "rows": pf[[c["key"] for c in pf_cols]].fillna(0).to_dict("records"),
    }

    lb = pd.read_csv(EV / "longrange_band_verdict.csv").copy()
    lb["skill_pct"] = lb["skill"] * 100.0
    lb["pers_pct"] = lb["skill_vs_persistence"] * 100.0
    lb["cov80_pct"] = lb["coverage_80"] * 100.0
    lb_cols = [
        {"key": "connector", "label": "Link"},
        {"key": "target", "label": "Target"},
        {"key": "band", "label": "Horizon band"},
        {"key": "winner", "label": "Selected"},
        {"key": "model_mae", "label": "Model MAE", "num": True, "fmt": "f1"},
        {"key": "baseline_mae", "label": "Base MAE", "num": True, "fmt": "f1"},
        {"key": "skill_pct", "label": "vs Base (%)", "num": True, "fmt": "f1"},
        {"key": "pers_pct", "label": "vs Pers (%)", "num": True, "fmt": "f1"},
        {"key": "cov80_pct", "label": "Cov 80 (%)", "num": True, "fmt": "f1"},
    ]
    lb_html = build_directory_widget_html(
        "longrangeDirectory", "Interactive Lookup · Complete 50-Band Long-Range Forecast Ledger",
        "Inspect all 50 VNI and QNI horizon-band evaluations from 1–7 through 61–90 days",
        "Filter by interconnector or sort by MAE, baseline skill, persistence skill, or 80% interval coverage.",
        lb_cols, filter_label="connector", filter_options=["VNI", "QNI"],
        csv_name="longrange_band_verdict.csv",
    )
    lb_data = {
        "id": "longrangeDirectory", "cols": lb_cols, "filterKey": "connector", "defaultSort": 4, "defaultAsc": True, "pageSize": 15,
        "rows": lb[[c["key"] for c in lb_cols]].fillna(0).to_dict("records"),
    }
    return {"pecForecastDirectory": pf_html, "longrangeDirectory": lb_html}, [pf_data, lb_data]


def main():
    N = json.loads((EV / "headline_numbers.json").read_text(encoding="utf-8"))
    widgets_html, dir_data = build_directories()
    charts_map = charts.all_charts()
    diagrams_map = build_diagrams()
    clean_v = lambda k: str(N[k]).replace("\\$", "$")

    bullets = [
        f"<strong>Observed EnergyConnect commissioning telemetry ({N['pec_5m_intervals']} five-minute intervals) confirms tight southern-ring coupling.</strong> While dynamic 150 MW and 350 MW test caps lead normal intervals, shared VNI/Southern NSW equations set {N['pec_vni_ring_rev_share']} of SA→NSW bounds and Heywood/VIC–SA equations set {N['pec_heywood_ring_fwd_share']} of NSW→SA bounds.",
        f"<strong>Bridging observed EnergyConnect commissioning profiles into the AEMC ERC0386 loop engine quantifies southern-ring SRA reallocation.</strong> Holding 2024–2026 prices fixed, escalating PEC from 0 MW to observed 150 MW commissioning, 350 MW testing, and 800 MW Stage 2 shifts ERC0386 net-trade payouts from {clean_v('loop_net_pre_pec_m')} to {clean_v('loop_net_150_m')}, {clean_v('loop_net_350_m')}, and {clean_v('loop_net_800_m')}, lifting PEC's arm share from {N['loop_pec_share_150']} to {N['loop_pec_share_350']} and {N['loop_pec_share_800']}.",
        f"<strong>Long-range 1–90 day MT PASA challengers retained the baseline in all {N['lr_retained_baseline']}/{N['lr_total_cells']} historical cells.</strong> Across all {N['lr_total_bands']} horizon bands, VNI calendar baselines beat persistence by {N['lr_vni_cal_vs_pers_min']} to {N['lr_vni_cal_vs_pers_max']}, yet no challenger cleared both statistical CI and prospective receipt-time promotion gates.",
        f"<strong>Leakage-controlled regime clustering adds no Holm-significant forecasting edge ({N['cl_holm_sig_wins']}/{N['cl_total_7d_evals']} seven-day evaluations).</strong> Only coarse two-state partitions (VNI K-means k=2 block ARI {N['cl_vni_k2_block_ari']}) remain stable across chronological folds, decaying to {N['cl_vni_k4_block_ari']} by k=4.",
    ]
    brief = [
        ("Evidence base", f"{N['pec_5m_intervals']} observed PEC five-minute intervals (Oct–Nov 2026), 48,336 Predispatch + 17,808 ST PASA PEC forecasts, 50 long-range MT PASA bands, {N['cl_total_7d_evals']} clustering evaluations, and {N['rr_total_workstreams']} registered workstreams."),
        ("Upgrades delivered", "C10 observed EnergyConnect-to-ERC0386 loop settlement bridge; complete visual/KaTeX Virtual Barrels synthesis of PEC limits, long-range verdict, clustering, and 3-stack governance."),
        ("Model-stack rule", "Original conditional backtest, nemic.experiments research campaigns, and nemic.production routing scaffold remain strictly separated."),
        ("Permitted claim", "Retrospective observational telemetry, fixed-price loop counterfactuals, and research-only forecasting audits; shadow schedules paused."),
    ]
    downloads = [
        "pec_observed_configs.csv", "pec_southern_ring_coupling.csv", "pec_loop_settlement_bridge.csv",
        "pec_issue_time_forecast_scores.csv", "longrange_band_verdict.csv", "longrange_cell_decisions.csv",
        "clustering_vs_controls.csv", "clustering_stability_summary.csv", "model_stack_governance_register.csv",
        "headline_numbers.json",
    ]
    mf = assemble_flagship_html(
        report_dir=HERE,
        output_html_name="IC_Forecasting_and_PEC_v2.html",
        page_title="Interconnector Forecasting Verdict, Clustering & Project EnergyConnect v2 | IC Flow Forecasting",
        brand_sub="Forecasting Verdict &amp;<br>EnergyConnect Research",
        dateline_top="Flagship Edition C · Version 2 (Virtual Barrels)",
        dateline_bottom="Australian National Electricity Market · PEC, Long-Range & Clustering",
        hero_kicker="Forecasting Limits, Regime Clustering & Southern-Ring Loop Settlement",
        hero_title="NEM interconnector forecasting verdict, clustering, and Project EnergyConnect:",
        hero_accent="observed commissioning limits, ERC0386 loop payouts, 50 horizon bands, and stack governance",
        nav_links=[
            ("#chapter-1", "PEC Physics"), ("#chapter-2", "Loop Bridge"), ("#chapter-3", "PEC Forecasts"),
            ("#chapter-4", "Long-Range"), ("#chapter-5", "Clustering"), ("#chapter-6", "Governance"),
            ("#downloads", "Data"),
        ],
        summary_bullets_html=bullets,
        brief_items=brief,
        dual_paths=(
            ("Desk & SRA Path", 'Read <a href="#chapter-1">Ch. 1 (PEC Commissioning)</a>, <a href="#chapter-2">Ch. 2 (ERC0386 Loop Bridge)</a>, and <a href="#chapter-6">Ch. 6 (Operational Rules)</a>.'),
            ("Quant & Research Path", 'Read <a href="#chapter-3">Ch. 3 (PEC Issue-Time Forecasts)</a>, <a href="#chapter-4">Ch. 4 (50-Band Verdict)</a>, <a href="#chapter-5">Ch. 5 (Clustering Audit)</a>, and <a href="#chapter-7">Appendices A–C</a>.'),
        ),
        chapter_order=CHAPTER_ORDER,
        part_map=PART_MAP,
        headline_numbers=N,
        charts_map=charts_map,
        diagrams_map=diagrams_map,
        widgets_html_map=widgets_html,
        directory_widgets_data=dir_data,
        download_files=downloads,
        footer_left="IC Flow Forecasting · Flagship Edition C · Forecasting Verdict, Clustering &amp; Project EnergyConnect v2<br>Observed PEC Oct–Nov 2026 · Loop Panel Sep 2024–Aug 2026 · Fixed NEM time (UTC+10)",
        footer_right="Research-only retrospective synthesis &amp; fixed-price loop counterfactual; shadow schedules paused.",
        code_files_for_manifest=[
            ROOT / "nemic/experiments/ic_forecasting_pec_v2.py",
            ROOT / "nemic/valuation/loop.py",
            ROOT / "nemic/experiments/vb_report_kit.py",
        ],
    )
    print(json.dumps(mf, indent=2), flush=True)


if __name__ == "__main__":
    main()
