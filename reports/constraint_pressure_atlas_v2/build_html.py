"""Build Flagship A: Six-Link Constraint Pressure, Generator Influence & Contraction Atlas (v2)."""
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
    "chapters/01_constraint_envelope_and_accounting.md",
    "chapters/02_six_link_parity_and_cobinding.md",
    "chapters/03_reconstruction_mae_audit.md",
    "chapters/04_diurnal_seasonal_and_weather_regimes.md",
    "chapters/05_contraction_lhs_rhs_and_switch.md",
    "chapters/06_cascades_and_nrm_clamping.md",
    "chapters/07_economic_vs_mechanical_influence.md",
    "chapters/08_bess_fast_ramp_and_technology_profiles.md",
    "chapters/09_event_atlas_synthesis_and_features.md",
    "appendices/appendix_a_equations.md",
    "appendices/appendix_b_schema_and_lineage.md",
    "appendices/appendix_c_sources.md",
]

PART_MAP = {
    "chapters/01_constraint_envelope_and_accounting.md": (
        "Part I · Grid Plumbing, Six-Link Parity & Reconstruction Integrity",
        "Equation accounting, full six-link coverage, and the QNI/V-SA residual audit",
        "Establishes exact linear-programme constraint mechanics, unlocks full 24-month evidence for Directlink, Murraylink, and Basslink, and diagnoses envelope reconstruction errors.",
    ),
    "chapters/04_diurnal_seasonal_and_weather_regimes.md": (
        "Part II · Diurnal Regimes, Contraction Anatomy & Multi-Link Cascades",
        "Confidence-bounded limits, LHS/RHS/switch attribution, and NRM clamping",
        "Quantifies seasonal headroom with seven-day block intervals, decomposes all sharp contractions across six links, and maps cross-corridor contagion.",
    ),
    "chapters/07_economic_vs_mechanical_influence.md": (
        "Part III · Economic Generator Influence & BESS Fast-Ramp Signatures",
        "Closing the MW-without-dollars disconnect across technologies and corridors",
        "Re-ranks generators and constraints by tight-headroom congestion rent and isolates five-minute utility battery impulses from hydro, coal, wind, and solar ramps.",
    ),
    "chapters/09_event_atlas_synthesis_and_features.md": (
        "Part IV · Event Atlases Synthesis & Modelling Playbook",
        "From five-minute forensic cases to compact, leak-free forecasting features",
        "Synthesises the standalone compressed VNI, QNI, and V-SA Event Atlases v2 into operational desk risk screens and feature contracts.",
    ),
    "appendices/appendix_a_equations.md": (
        "Reference Appendices",
        "Mathematical identities, relocated schemas, and evidence register",
        "Consolidates KaTeX equations, AEMO table mappings, rebuild commands, and methodological provenance.",
    ),
}


def build_diagrams() -> dict[str, str]:
    d1 = """<div id="constraintPipeline" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D1: From linear-programme generic constraints to economic congestion rent</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>1 · Solved equation</h3><span>a·F + Σ b<sub>i</sub>·P<sub>i</sub> + Z ≤ RHS</span><span>Exact effective version &amp; factors</span><span>Positive a = upper; negative a = lower</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>2 · Envelope &amp; headroom</h3><span>Conditional bound = F + (RHS − LHS)/a</span><span>Tightest upper / lower sets envelope</span><span>Headroom = cap − flow (tight ≤ 50 MW)</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>3 · Mechanical pressure</h3><span>Unit sensitivity s<sub>i</sub> = −b<sub>i</sub> / a</span><span>30-min ramp pressure = s<sub>i</sub>·ΔP<sub>i</sub></span><span>5-min impulse tracks BESS reversals</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>4 · Economic rent</h3><span>Binding shadow price |MV| &gt; 0</span><span>Rent weight = |s<sub>i</sub>·ΔP<sub>i</sub>| × Spread<sup>+</sup>/12</span><span>Translates MW moves into SRA dollars</span></div></div>
<p class="figure-note">Reported AEMO limits are dispatch-solution outputs rather than secure physical transfer capability; economic weighting isolates moves that actually separate regional prices.</p></div>"""

    d2 = """<div id="contractionSplit" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D2: Three-way mechanical decomposition of a 30-minute sharp limit contraction</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Observed contraction</h3><span>Directional limit falls ≥ monthly P90</span><span>Contiguous intervals grouped to onset</span><span>Captures local seasonal tail drops</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Path A · Equation switch</h3><span>Active leader changes over 30 minutes</span><span>Outage set invocation or #R ramp lock</span><span>Cannot be blamed on single-unit ramps</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Path B · Same-eq LHS</h3><span>Same leading equation holds across 30m</span><span>Net Σ s<sub>i</sub>·ΔP<sub>i</sub> explains clipped share</span><span>Predictable from scheduled unit ramps</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>Path C · Same-eq RHS</h3><span>Residual drop under same equation</span><span>Dynamic ratings, inertia, Z-term shifts</span><span>Requires weather/system-strength inputs</span></div></div>
<p class="figure-note">Separating equation switches from fixed-equation generator ramps prevents forecasting models from overfitting exogenous outage invocations to unit dispatch.</p></div>"""

    d3 = """<div id="featureBridge" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D3: Translating constraint-pressure diagnostics into leak-free forecasting and desk tools</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Reliability screen</h3><span>Quarantine high-MAE fallback regimes</span><span>Retain exact-version match flag</span><span>Separate ROCOF/#R from thermal</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Economic filter</h3><span>Select DUIDs by tight-headroom rent</span><span>Separate BESS 5m vs solar/hydro 30m</span><span>Pool episodic units by constraint family</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Cascade &amp; NRM state</h3><span>Track 6×6 co-contraction risk</span><span>Flag counter-price NRM clamp state</span><span>Track parallel HVDC headroom</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>Downstream target</h3><span>Feed Stage 2–3 valuation flow layer</span><span>Feed short-term limit contraction alerts</span><span>Respect issue-time vintage discipline</span></div></div>
<p class="figure-note">Compact network-state features enter experiments only under strict issue-time vintage replay and must beat persistence and AEMO predispatch on identical rows.</p></div>"""
    return {"constraintPipeline": d1, "contractionSplit": d2, "featureBridge": d3}


def build_directories() -> tuple[dict[str, str], list[dict]]:
    duid = pd.read_csv(EV / "duid_economic_influence.csv")
    duid["rent_k"] = duid["rent_weighted_aud"] / 1e3
    duid_cols = [
        {"key": "link", "label": "Link"},
        {"key": "DUID", "label": "Unit"},
        {"key": "tech", "label": "Technology"},
        {"key": "rank_rent_aud", "label": "Econ rank", "num": True, "fmt": "int"},
        {"key": "rank_all_mw", "label": "Mech rank", "num": True, "fmt": "int"},
        {"key": "rent_k", "label": "Rent weight ($k)", "num": True, "fmt": "aud0"},
        {"key": "all_abs_mw_obs", "label": "All MW-obs", "num": True, "fmt": "int"},
        {"key": "tight_share_pct", "label": "Tight share (%)", "num": True, "fmt": "f1"},
        {"key": "eve_share_pct", "label": "Evening (%)", "num": True, "fmt": "f1"},
    ]
    duid_html = build_directory_widget_html(
        "duidDirectory", "Interactive Lookup · Economic vs. Mechanical Generator Pressure",
        "Search and rank top 270 unit-corridor exposures across all six interconnectors",
        "Click any column header to sort; filter by interconnector to compare raw mechanical exposure against congestion-rent-weighted rankings.",
        duid_cols, filter_label="link", filter_options=["VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"],
        csv_name="duid_economic_influence.csv",
    )
    duid_data = {
        "id": "duidDirectory", "cols": duid_cols, "filterKey": "link", "defaultSort": 5, "defaultAsc": False, "pageSize": 15,
        "rows": duid[[c["key"] for c in duid_cols]].to_dict("records"),
    }

    ceq = pd.read_csv(EV / "constraint_economic_influence.csv")
    ceq["shadow_k"] = ceq["shadow_rent_aud_per_mw"] / 1e3
    ceq_cols = [
        {"key": "link", "label": "Link"},
        {"key": "CONSTRAINTID", "label": "Constraint ID"},
        {"key": "direction", "label": "Direction"},
        {"key": "family", "label": "Category"},
        {"key": "binding_intervals", "label": "Binding int.", "num": True, "fmt": "int"},
        {"key": "leading_intervals", "label": "Leading int.", "num": True, "fmt": "int"},
        {"key": "mean_abs_mv_when_binding", "label": "Mean |MV|", "num": True, "fmt": "aud2"},
        {"key": "shadow_k", "label": "Shadow rent ($k/MW)", "num": True, "fmt": "aud0"},
    ]
    ceq_html = build_directory_widget_html(
        "constraintDirectory", "Interactive Lookup · Shadow-Rent Constraint Register",
        "Search top 240 economically binding constraint equations across all six interconnectors",
        "Ranks constraints by cumulative shadow rent (binding intervals × mean |MV| / 12) rather than non-binding leader counts.",
        ceq_cols, filter_label="link", filter_options=["VNI", "QNI", "Heywood", "Directlink", "Murraylink", "Basslink"],
        csv_name="constraint_economic_influence.csv",
    )
    ceq_data = {
        "id": "constraintDirectory", "cols": ceq_cols, "filterKey": "link", "defaultSort": 7, "defaultAsc": False, "pageSize": 15,
        "rows": ceq[[c["key"] for c in ceq_cols]].to_dict("records"),
    }
    return {"duidDirectory": duid_html, "constraintDirectory": ceq_html}, [duid_data, ceq_data]


def main():
    N = json.loads((EV / "headline_numbers.json").read_text(encoding="utf-8"))
    widgets_html, dir_data = build_directories()
    charts_map = charts.all_charts()
    diagrams_map = build_diagrams()

    clean_v = lambda k: str(N[k]).replace("\\$", "$")
    bullets = [
        f"<strong>Economic weighting reshuffles generator influence rankings across every corridor.</strong> Weighting five-minute generator moves strictly during tight-headroom intervals (<= 50 MW) by regional price spread elevates market-moving dispatchable units such as <code>{N['top_econ_duid_vni']}</code> on VNI ({clean_v('top_econ_rent_vni')}, rank shift {N['top_econ_shift_vni']}), <code>{N['top_econ_duid_qni']}</code> on QNI ({clean_v('top_econ_rent_qni')}), and <code>{N['top_econ_duid_heywood']}</code> on Heywood ({clean_v('top_econ_rent_heywood')}) ahead of benign midday slack ramps.",
        f"<strong>All six NEM interconnectors now sit at full 24-month parity ({N['total_contraction_episodes_6link']} sharp contractions).</strong> Unlocking the retained Basslink, Directlink, and Murraylink two-year archives reveals high tight-headroom frequency on Directlink ({N['tight_pct_directlink_upper']} forward, {N['tight_pct_directlink_lower']} reverse) and Murraylink ({N['tight_pct_murraylink_upper']} forward, {N['tight_pct_murraylink_lower']} reverse), directly affecting pooled QNI and VIC–SA settlement residue buckets.",
        f"<strong>Equation switches drive {N['c4_switch_drop_pct_all']} of all 30-minute contraction MW, while LHS generator ramps explain {N['c4_lhs_drop_pct_all']}.</strong> Decomposing every sharp contraction across all six links separates exogenous outage and ramp-set switches from predictable fixed-equation generator ramping and RHS/dynamic-rating shifts ({N['c4_rhs_drop_pct_all']}).",
        f"<strong>QNI ({N['mae_qni_upper']} MW upper) and Heywood ({N['mae_vsa_upper']} MW upper) reconstruction residuals stem from unmatched setter versions and non-thermal regimes.</strong> Root-cause auditing isolates exactly where reconstructed envelopes are reliable versus where fallback equations, ramp sets, and ROCOF/UFLS limits must be quarantined before modelling.",
    ]
    brief = [
        ("Evidence base", f"24 months (September 2024 to August 2026), 210,240 five-minute intervals per link across all six NEM interconnectors, {N['total_unique_duids_6link']} active DUIDs, and {N['total_binding_eq_intervals_6link']} binding equation-intervals."),
        ("Upgrades delivered", "C1 economic/rent-weighted pressure; C2 6-link parity & parallel co-binding; C3 QNI/V-SA MAE audit; C4 full LHS/RHS/switch split; C5 BESS 5-minute impulse signature; C6 6×6 cascades & NRM clamping."),
        ("Companion atlases", "Standalone compressed Event Atlases v2 (VNI, QNI, V-SA) built in reports/event_atlases_v2/ at ~75% smaller file size."),
        ("Permitted claim", "Retrospective mechanical and economic attribution; AEMO limits are dispatch-solution outputs, not physical transfer capability."),
    ]
    downloads = [
        "six_link_parity_summary.csv", "parallel_link_cobinding.csv", "reconstruction_mae_audit.csv",
        "diurnal_seasonal_ci_profiles.csv", "contraction_lhs_rhs_switch.csv", "cross_link_cascades.csv",
        "nrm_clamping_attribution.csv", "duid_economic_influence.csv", "constraint_economic_influence.csv",
        "bess_ramp_signature.csv", "headline_numbers.json",
    ]
    mf = assemble_flagship_html(
        report_dir=HERE,
        output_html_name="Constraint_Pressure_Atlas_v2.html",
        page_title="Six-Link Constraint Pressure, Generator Influence & Contraction Atlas v2 | IC Flow Forecasting",
        brand_sub="Grid Constraints &amp;<br>Flow Research",
        dateline_top="Flagship Edition A · Version 2 (Virtual Barrels)",
        dateline_bottom="Australian National Electricity Market · 6 Interconnectors",
        hero_kicker="Six-Link Grid Physics & Economic Pressure",
        hero_title="NEM constraint pressure, generator influence, and limit contractions:",
        hero_accent="six-link parity, congestion-rent rankings, BESS ramps, and cascades",
        nav_links=[
            ("#chapter-1", "Plumbing"), ("#chapter-2", "6-Link Parity"), ("#chapter-3", "MAE Audit"),
            ("#chapter-5", "Contractions"), ("#chapter-6", "Cascades"), ("#chapter-7", "Econ DUIDs"),
            ("#chapter-8", "BESS Ramps"), ("#downloads", "Data"),
        ],
        summary_bullets_html=bullets,
        brief_items=brief,
        dual_paths=(
            ("Desk & Risk Path", 'Read <a href="#chapter-2">Ch. 2 (Six-Link Parity)</a>, <a href="#chapter-6">Ch. 6 (Cascades &amp; NRM)</a>, <a href="#chapter-7">Ch. 7 (Economic DUIDs)</a>, and <a href="#chapter-8">Ch. 8 (BESS Ramps)</a>.'),
            ("Quant & Modelling Path", 'Read <a href="#chapter-1">Ch. 1 (Equations)</a>, <a href="#chapter-3">Ch. 3 (MAE Audit)</a>, <a href="#chapter-5">Ch. 5 (LHS/RHS/Switch)</a>, <a href="#chapter-9">Ch. 9 (Feature Spec)</a>, and <a href="#chapter-10">Appendices A–C</a>.'),
        ),
        chapter_order=CHAPTER_ORDER,
        part_map=PART_MAP,
        headline_numbers=N,
        charts_map=charts_map,
        diagrams_map=diagrams_map,
        widgets_html_map=widgets_html,
        directory_widgets_data=dir_data,
        download_files=downloads,
        footer_left="IC Flow Forecasting · Flagship Edition A · Constraint Pressure Atlas v2<br>September 2024 to August 2026 · Fixed NEM time (UTC+10)",
        footer_right="Retrospective mechanical and economic attribution; not an operational dispatch forecast.",
        code_files_for_manifest=[
            ROOT / "nemic/experiments/constraint_pressure_v2.py",
            ROOT / "nemic/experiments/event_atlas_v2.py",
            ROOT / "nemic/experiments/vb_report_kit.py",
        ],
    )
    print(json.dumps(mf, indent=2), flush=True)


if __name__ == "__main__":
    main()
