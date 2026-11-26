"""Build the self-contained offline interregional valuation research v3 report.

Pipeline:
  1. Assemble modular Markdown chapters (`chapters/*.md`, `appendices/*.md`).
  2. Fill every `{{number}}` placeholder from `evidence/headline_numbers.json` (fail on missing).
  3. Write unified `research_report.md` (with embed directives stripped cleanly for standalone reading).
  4. Convert assembled Markdown to HTML with server-side KaTeX, Virtual Barrels callouts, and
     inline exhibit/diagram/interactive slots (`convert_markdown.mjs`).
  5. Replace every `div.embed-slot` with its corresponding Plotly exhibit, diagram, interactive lab,
     or part banner, embedding Plotly, KaTeX CSS + woff2 fonts, datasets, and downloadable CSVs.
  6. Run Virtual Barrels prose lint verification and write `report_manifest.json`.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

import plotly
import plotly.graph_objects as go
from bs4 import BeautifulSoup, NavigableString

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from report_theme import hero, metric, style_plotly, render_page  # noqa: E402
import charts  # noqa: E402
from nemic.valuation import v3_summary  # noqa: E402

V1 = ROOT / 'reports/interregional_valuation_research_20260918'
V2 = ROOT / 'reports/interregional_valuation_research_v2'
EV = HERE / 'evidence'

CHAPTER_ORDER = [
    'chapters/01_instruments_and_accounting.md',
    'chapters/02_flows_losses_and_ledger.md',
    'chapters/03_loop_regime_dilution_and_basslink.md',
    'chapters/04_empirical_baseline_cpt_and_diurnal.md',
    'chapters/05_loss_congestion_and_dependence.md',
    'chapters/06_counterprice_constraints_and_triggers.md',
    'chapters/07_auctions_premia_drift_and_slippage.md',
    'chapters/08_hedging_sra_loop_and_cap_mixes.md',
    'chapters/09_benchmarks_greeks_and_workbench.md',
    'chapters/10_system_architecture_and_data_contracts.md',
    'chapters/11_modelling_playbook_and_literature.md',
    'chapters/12_validation_gates_and_build_roadmap.md',
    'appendices/appendix_a_formulas.md',
    'appendices/appendix_b_technical_schema.md',
    'appendices/appendix_c_sources_and_changelog.md',
]

PART_MAP = {
    'chapters/01_instruments_and_accounting.md': ('Part I · Market Plumbing & Settlement Rules', 'Contracts, physical flows, and the transition to loop settlement', 'Establishes the exact contractual payoffs, loss equations, pre-loop pooling, and post-November 2026 net-trade mechanics before interpreting market prices.'),
    'chapters/04_empirical_baseline_cpt_and_diurnal.md': ('Part II · Empirical Structure & Physical Mechanisms', 'Nineteen quarters of spreads, fragility, losses, and constraints', 'Documents the five-minute telemetry base, CPT-aware statutory ceilings, diurnal regimes, loss-versus-congestion shares, and physical separation triggers.'),
    'chapters/07_auctions_premia_drift_and_slippage.md': ('Part III · Market Valuation, Hedging & Benchmarks', 'Auction premia, directional firmness, and walk-forward tests', 'Evaluates clearing prices against settled payoffs, credit-support carry, weekly and quarterly hedge replication, and out-of-sample valuation benchmarks.'),
    'chapters/10_system_architecture_and_data_contracts.md': ('Part IV · Implementation Blueprint & Engineering Spec', 'System architecture, modelling playbook, literature synthesis, and gates', 'Translates the physical and market findings into five-layer module contracts, exhaustive literature synthesis, worked calibration mathematics, and validation acceptance gates.'),
    'appendices/appendix_a_formulas.md': ('Reference Appendices', 'Mathematical identities, technical schemas, and tiered evidence register', 'Consolidates every formula, relocated AEMO table identifier, rebuild command, and primary source citation.'),
}

parser = argparse.ArgumentParser()
parser.add_argument('--node', default=shutil.which('node') or r'C:\Program Files\nodejs\node.EXE')
args = parser.parse_args()


def sha(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix.lower() in {'.py', '.md', '.json', '.csv', '.js', '.mjs', '.cjs', '.css', '.txt', '.html'}:
        b = b.replace(b'\r\n', b'\n')
    return hashlib.sha256(b).hexdigest()


def load_csv(p: Path):
    rows = []
    for row in csv.DictReader(p.open(encoding='utf-8-sig', newline='')):
        for k, v in row.items():
            if v in ('True', 'False'):
                row[k] = v == 'True'
            else:
                try:
                    row[k] = float(v)
                except (ValueError, TypeError):
                    pass
        rows.append(row)
    return rows


def field(id_, label, value, step='1', minimum=None):
    lo = f' min="{minimum}"' if minimum is not None else ''
    return f'<label for="{id_}">{label}<input id="{id_}" type="number" value="{value}" step="{step}"{lo}></label>'


def dyn(label, id_, note, note_id=None):
    out = metric(label, '—', note).replace('<strong>', f'<strong id="{id_}">')
    if note_id:
        out = out.replace('<small>', f'<small id="{note_id}">')
    return out


def embedded_download(name: str) -> str:
    p = EV / name
    mime = 'text/csv' if name.endswith('.csv') else 'application/json'
    return f'<a id="dl-{escape(name.replace(".", "-"))}" href="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}" download="{escape(name)}">{escape(name)} ↓</a>'


def build_diagrams() -> dict[str, str]:
    d4 = '''<div id="settlementPipeline" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D4: Pre-loop settlement chain from metered energy to unit cashflow</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>1 · Metered interval</h3><span>Five-minute energy at each regional reference node</span><span>Losses split via dated from-region loss share</span><span>Asset residue r = P<sub>to</sub>·flow in − P<sub>from</sub>·flow out</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>2 · Directional pooling</h3><span>VNI standalone</span><span>QNI pooled with Terranora</span><span>Heywood pooled with Murraylink</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>3 · Sign treatment</h3><span>Positive intervals enter SRA pool</span><span>Negative intervals recovered from importing TNSP</span><span>NRM clamps at −$100k accumulated</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>4 · Unit cashflow</h3><span>Pool × dated unit proportion</span><span>Auction price paid on calendar instalment date</span><span>Weekly distributions with settlement revisions</span></div></div>
<p class="figure-note">Metered reconstruction reconciles within 0.03% on northbound VNI and −0.09% on northbound QNI against AEMO settled inter-regional surplus.</p></div>'''

    d5 = '''<div id="loopAllocation" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D5: Net-trade loop settlement across NSW, Victoria, and South Australia (from November 2026)</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>1 · Arm allocations</h3><span>Existing loss-adjusted allocation per arm</span><span>Net loop residue equals sum of all three arms</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>2 · Net regional trade</h3><span>Net export balance computed per region</span><span>Trade assigned on exporter-to-importer arms</span><span>Pass-through Victoria carries zero net trade</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>3 · Provisional split</h3><span>Notional trade quantity × regional spread</span><span>Scaled proportionally to net loop residue</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>4 · Secondary netting</h3><span>Negative provisional arms netted from positive arms</span><span>Units never pay; net-negative loops go to networks</span></div></div>
<p class="figure-note">AEMC ERC0386 final determination (25 September 2025), verified against Figure 3.1 and Appendix B Example 4 in automated settlement unit tests.</p></div>'''

    d1 = '''<div id="mechanismChain" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D1: Causal chain from physical grid triggers to contract payoffs</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Physical triggers</h3><span>Heatwaves, cold snaps, low wind, evening ramps</span><span>Thermal unit outages and battery depletion</span><span>Planned and forced transmission constraints</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Dispatch clearing</h3><span>Regional supply stack meets net demand</span><span>Generic constraints bind or force reverse flows</span><span>Marginal loss factors scale coupled prices</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Joint price–flow state</h3><span>Four joint spike regimes above $300/MWh</span><span>Flow expansion vs. firmness collapse in stress</span><span>Counter-price intervals and NRM clamping</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>Contract settlement</h3><span>Linear quarterly base and $300 cap futures</span><span>Nonlinear flow-weighted SRA unit pools</span><span>Effective-dated pre-loop vs. loop allocation</span></div></div>
<p class="figure-note">Prices and transfer flows are co-determined by the same dispatch state; valuing contracts requires joint scenario generation followed by an exact settlement layer.</p></div>'''

    d2 = '''<div id="architecturePanel" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D2: Five-layer quarterly valuation system architecture</span></div><div class="architecture-flow">
<article><b>LAYER 1</b><h3>As-of snapshot</h3><p>Issue- and receipt-dated forecasts, outage plans, unit registry, statutory caps, and matched market quotes.</p></article>
<article><b>LAYER 2</b><h3>Joint fundamentals</h3><p>Spatially coherent multi-day weather blocks, demand, VRE availability, outage durations, and storage state.</p></article>
<article><b>LAYER 3</b><h3>Network &amp; prices</h3><p>Clipped-energy pricing, 4-state joint spike hazard/duration/severity, and shared constraint regimes.</p></article>
<article><b>LAYER 4</b><h3>Settlement engine</h3><p>Five-minute loss-adjusted pooling, effective-dated loop net-trade, fees, and exact contract payoffs.</p></article>
<article><b>LAYER 5</b><h3>Valuation &amp; risk</h3><p>Physical distribution P, entropy-pooled Q*, CVaR hedge optimisation, and attribution diagnostics.</p></article>
</div><p class="figure-note">Stage 1 (Layer 4 ledger and loop rules) and Stage 4a (auction history) are built and tested in the valuation package; Layers 2, 3, and 5 define Stages 2, 3, and 4b/5.</p></div>'''

    d3 = '''<div id="roadmapPanel" class="mechanism-panel"><div class="diagram-caption"><span>Diagram D3: Five-stage implementation and prospective validation roadmap</span></div><ol class="roadmap">
<li><b>Stage 1 · Ledger (Done)</b><span>19-quarter five-minute panel, reconciled pre-loop ledger, and tested AEMC loop calculator.</span></li>
<li><b>Stage 2 · Physical P</b><span>7-day weather blocks, clipped-energy models, and calibrated 4-state spike hazard, duration, and tail severity.</span></li>
<li><b>Stage 3 · Structural</b><span>Storage state-of-charge depletion, outage restoration, and post-EnergyConnect dispatch sensitivities.</span></li>
<li><b>Stage 4 · Market Q*</b><span>Auction premia (done) joined with timestamped base/cap futures quotes, dual entropy pooling, and CVaR sizing.</span></li>
<li><b>Stage 5 · Prospective</b><span>Freeze specification, log issue-time revisions, and verify economic P&amp;L net of slippage and carry.</span></li>
</ol><p class="figure-note">Progression across stages requires passing the acceptance gates in Chapter 12 on identical frozen auction dates.</p></div>'''

    return {'settlementPipeline': d4, 'loopAllocation': d5, 'mechanismChain': d1, 'architecturePanel': d2, 'roadmapPanel': d3}


def build_interactives() -> dict[str, str]:
    hist = f'''<div id="historicalExplorer" class="inline-interactive">
<div class="section-kicker">Interactive Explorer · Realised Five-Minute History</div>
<h4>Explore quarterly spread composition, joint scarcity states, and regional tail concentration</h4>
<p class="section-dek">Select window, signed direction (positive means destination dearer than origin), and delivery quarter. Every panel recalculates live from embedded five-minute summaries.</p>
<div class="controls">
  <label for="window">Evidence window<select id="window"><option value="full">October 2021 – June 2026 (19 quarters)</option><option value="v1">September 2024 – June 2026 (v1 window)</option></select></label>
  <label for="direction">Origin → destination<select id="direction"></select></label>
  <label for="quarter">Delivery quarter<select id="quarter"></select></label>
  <span class="selection-label" id="selectedRoute">VIC → NSW · 2026 Q2</span>
</div>
<div class="metrics">
  {dyn('Total spread (AUD/MWh)', 'totalValue', 'Destination minus origin')}
  {dyn('Capped energy (AUD/MWh)', 'energyValue', 'Difference of min(price, $300)')}
  {dyn('Scarcity excess (AUD/MWh)', 'scarcityValue', 'Difference of $300 cap payouts')}
  {dyn('Realised spread value (AUD/MW-qtr)', 'quarterValue', '2,184 delivery hours · one MW', note_id='hoursNote')}
</div>
<figure class="inline-exhibit"><figcaption><span>Interactive Exhibit I1: Quarterly spread split into capped energy and scarcity excess</span><span class="figure-links"><a href="#dl-spread_decomposition-csv">Data ↓</a></span></figcaption>
<div class="chart-scroll"><div id="historyChart" class="plot" role="img" aria-label="Quarterly spread decomposition"></div></div>
<p class="figure-note">Source: AEMO five-minute dispatch prices (complete quarters, firm status). Capped energy plus scarcity excess sums identically to the total spread.</p></figure>
<div class="exhibit-insight" id="historyInsight"></div>
<div class="table-wrap"><table class="numeric-table"><thead><tr><th>Joint $300 exceedance state</th><th>Hours</th><th>Frequency</th><th>Energy (AUD/MWh)</th><th>Scarcity (AUD/MWh)</th><th>Total (AUD/MWh)</th></tr></thead><tbody id="regimeBody"></tbody></table></div>
<p class="identity" id="identityCheck"></p>
<div class="visual-grid">
  <figure class="inline-exhibit"><figcaption><span>Interactive Exhibit I2: Four-state spread contribution across quarters</span><span class="figure-links"><a href="#dl-joint_regimes-csv">Data ↓</a></span></figcaption><div class="chart-scroll"><div id="regimeChart" class="plot"></div></div><p class="figure-note">State contributions divide by total quarter hours so all four bars sum algebraically to the quarterly spread.</p></figure>
  <figure class="inline-exhibit"><figcaption><span>Interactive Exhibit I3: Frequency against severity across all regions</span><span class="figure-links"><a href="#dl-regional_decomposition-csv">Data ↓</a></span></figcaption><div class="chart-scroll"><div id="scarcityMap" class="plot"></div></div><p class="figure-note">Bubble area scales with quarterly $300 cap payout. Identical cap payouts arise from very different combinations of hours and severity.</p></figure>
</div>
<div class="controls">
  <label for="region">Single-region scarcity view<select id="region"><option value="NSW1">New South Wales</option><option value="QLD1">Queensland</option><option value="SA1">South Australia</option><option value="VIC1">Victoria</option><option value="TAS1">Tasmania</option></select></label>
  <label for="eventQuarter">Inspect quarter<select id="eventQuarter"></select></label>
</div>
<div class="metrics">
  {dyn('Hours above $300', 'eventHours', 'Five-minute exceedance duration')}
  {dyn('Mean excess when above $300', 'eventSeverity', 'Conditional tail severity')}
  {dyn('Quarterly $300 cap payout', 'eventCap', 'Frequency × severity')}
  {dyn('Top five days share', 'eventConcentration', 'Share of quarter cap payout')}
</div>
<p class="identity" id="eventIdentity"></p>
<div class="visual-grid">
  <figure class="inline-exhibit"><figcaption><span>Interactive Exhibit I4: Regional hours above $300 against cap payout</span><span class="figure-links"><a href="#dl-regional_decomposition-csv">Data ↓</a></span></figcaption><div class="chart-scroll"><div id="eventChart" class="plot"></div></div><p class="figure-note">Hours above $300 (bars, left axis) alongside realised $300 cap payout (line, right axis).</p></figure>
  <figure class="inline-exhibit"><figcaption><span>Interactive Exhibit I5: Share of regional cap payout earned in the top five days</span><span class="figure-links"><a href="#dl-regional_decomposition-csv">Data ↓</a></span></figcaption><div class="chart-scroll"><div id="concentrationChart" class="plot"></div></div><p class="figure-note">Across nearly every active quarter, 80% to 100% of quarterly scarcity value concentrates inside five calendar days.</p></figure>
</div>
<div class="controls">
  <label for="heatMetric">Cross-link heatmap measure<select id="heatMetric"><option value="spread">Total spread (AUD/MWh)</option><option value="energy">Capped energy (AUD/MWh)</option><option value="scarcity">Scarcity excess (AUD/MWh)</option><option value="scarcity_share">Scarcity share of absolute components (%)</option></select></label>
  <span class="selection-label">Complete quarters · canonical signed directions</span>
</div>
<figure class="inline-exhibit"><figcaption><span>Interactive Exhibit I6: Nineteen-quarter cross-link spread matrix (including Basslink)</span><span class="figure-links"><a href="#dl-spread_decomposition-csv">Data ↓</a></span></figcaption><div class="chart-scroll"><div id="spreadHeatmap" class="plot"></div></div><p class="figure-note">Canonical signs: NSW minus VIC, QLD minus NSW, SA minus VIC, and VIC minus TAS. Consolidates v2 Exhibits 8 and N13 into a single interactive view.</p></figure>
</div>'''

    flow_bridge = '''<div id="flowBridgeWrap" class="inline-interactive">
<div class="section-kicker">Interactive Diagnostic · Flow–Spread Dependence</div>
<h4>Ungated product of means versus covariance across directional interconnectors</h4>
<figure class="inline-exhibit"><figcaption><span>Interactive Exhibit I7: Flow–spread covariance corrected for the gating artefact</span><span class="figure-links"><a href="#dl-flow_diagnostics_full-csv">Data ↓</a></span></figcaption>
<div class="chart-scroll"><div id="flowBridge" class="plot"></div></div>
<p class="figure-note">Uses ungated mean positive flow so the shared positive-spread indicator no longer creates artificial positive covariance. Hover displays conditional Spearman rank correlation given a positive spread.</p></figure>
</div>'''

    payoff_geom = '''<div id="payoffGeomWrap" class="inline-interactive">
<div class="section-kicker">Interactive Payoff Geometry · Linear Spread vs. Clipped Energy &amp; Cap</div>
<h4>Exact additive split across destination spot prices (synced to Workbench origin price)</h4>
<figure class="inline-exhibit"><figcaption><span>Interactive Exhibit I8: Realised spread payoff split at the $300 strike</span></figcaption>
<div class="chart-scroll"><div id="payoffChart" class="plot"></div></div>
<p class="figure-note">Adjust origin and destination assumptions in the Chapter 9 Workbench to update this payoff curve live. Above $300/MWh, incremental destination price movement transfers entirely into the scarcity cap leg.</p></figure>
</div>'''

    workbench = f'''<div id="valuationLab" class="inline-interactive">
<div class="section-kicker">Interactive Desk Workbench · Relative-Value Arithmetic <span class="lab-badge">Illustrative defaults synced to Chapter 9 example</span></div>
<h4>Decompose matched futures quotes, test cap-implied scarcity hours, and check SRA unit margin</h4>
<p class="section-dek">Default inputs match the worked 90-day NSW minus VIC example in Chapter 9. Replace with live matched quotes to decompose market-implied energy and scarcity expectations.</p>
<div class="lab-grid">
  <div class="input-panel">
    <h4>Futures, caps &amp; scarcity inputs</h4>
    <div class="inputs">
      {field('baseA', 'Origin base future A ($/MWh)', 76, '.5')}
      {field('baseB', 'Destination base future B ($/MWh)', 110, '.5')}
      {field('capA', 'Origin $300 cap future A ($/MWh)', 9, '.25', 0)}
      {field('capB', 'Destination $300 cap future B ($/MWh)', 25, '.25', 0)}
      {field('deliveryHours', 'Quarter delivery hours', 2160, '1', 1)}
      {field('physicalSpread', 'Physical model spread ($/MWh)', 30, '.5')}
      {field('severity', 'Assumed mean excess >$300 ($/MWh)', 2500, '100', 1)}
      {field('rho', 'Cap risk-premium loading (fraction)', 0, '.05')}
    </div>
    <p class="input-help">Positive spread = destination B minus origin A. Risk loading 0.20 implies market cap trades 20% above physical expected cap payout.</p>
    <h4 style="margin-top:16px">SRA unit valuation inputs</h4>
    <div class="inputs">
      {field('unitPrice', 'Unit purchase price ($/unit)', 15000, '100', 0)}
      {field('unitMean', 'Expected discounted payoff ($/unit)', 20000, '100', 0)}
      {field('unitFees', 'Auction fees &amp; carry ($/unit)', 200, '50', 0)}
      {field('hurdle', 'Valuation &amp; model reserve ($/unit)', 750, '50', 0)}
    </div>
    <div style="margin-top:12px"><button id="resetInputs" type="button">Reset to Chapter 9 worked defaults</button></div>
    <div id="calcError" class="warning" hidden>Enter finite nonnegative numbers (delivery hours &gt; 0, severity &gt; 0, risk loading &gt; −1).</div>
  </div>
  <div>
    <div class="metrics" style="grid-template-columns:1fr 1fr;margin-top:0">
      {dyn('Market base spread', 'marketTotal', 'B minus A ($/MWh)')}
      {dyn('Market capped-energy', 'marketEnergy', '(B − capB) − (A − capA)')}
      {dyn('Market scarcity spread', 'marketScarcity', 'capB minus capA')}
      {dyn('Physical − market edge', 'marketEdge', 'Positive = market cheap')}
    </div>
    <p class="small-note" id="longShort"></p>
    <div class="worked-output">
      <span>Destination cap-implied scarcity hours</span>
      <strong id="impliedHours">—</strong>
      <p id="scarcityInference"></p>
      <p id="spreadHours" class="small-note" style="margin-top:6px"></p>
    </div>
    <div id="infeasibleWarning" class="warning" hidden>Implied scarcity hours exceed total hours in the quarter; raise assumed severity or lower cap price.</div>
    <figure class="inline-exhibit" style="margin-top:14px"><figcaption><span>Implied scarcity hours across conditional severity assumptions</span></figcaption><div class="chart-scroll"><div id="impliedChart" class="plot" style="min-width:340px"></div></div></figure>
    <div class="worked-output">
      <span>SRA unit net valuation margin</span>
      <strong id="unitEdge">—</strong>
      <p id="unitBridge"></p>
    </div>
  </div>
</div>
</div>'''

    return {
        'historicalExplorer': hist,
        'flowBridge': flow_bridge,
        'payoffGeometry': payoff_geom,
        'valuationLab': workbench,
    }


def main():
    # 1. Refresh v3 headline numbers from v3 evidence
    N = v3_summary.write()

    # 2. Assemble modular chapters & appendices
    raw_parts = []
    for rel in CHAPTER_ORDER:
        p = HERE / rel
        text = p.read_text(encoding='utf-8').replace('\r\n', '\n').strip()
        if rel in PART_MAP:
            kicker, title, dek = PART_MAP[rel]
            raw_parts.append(f'{{{{part:{kicker}||{title}||{dek}}}}}\n\n' + text)
        else:
            raw_parts.append(text)
    front_md = (HERE / 'chapters/00_front.md').read_text(encoding='utf-8').replace('\r\n', '\n').strip()
    full_tpl = front_md + '\n\n' + '\n\n'.join(raw_parts) + '\n'

    # Validate all numeric placeholders (ignoring {{exhibit:...}}, {{diagram:...}}, {{interactive:...}}, {{part:...}})
    tokens = set(re.findall(r'\{\{([a-zA-Z0-9_]+)\}\}', full_tpl))
    missing = sorted(tokens - set(N))
    if missing:
        raise SystemExit(f'Unfilled numeric placeholders: {missing}')
    assembled = re.sub(r'\{\{([a-zA-Z0-9_]+)\}\}', lambda m: str(N[m.group(1)]), full_tpl)

    # Write clean standalone Markdown (strip internal layout directives for readable GitHub/Markdown copy)
    clean_md = re.sub(r'^\{\{(?:exhibit|diagram|interactive|part):[^}]+\}\}\n*', '', assembled, flags=re.M)
    clean_md = re.sub(r'\n{3,}', '\n\n', clean_md)
    (HERE / 'research_report.md').write_text(clean_md, encoding='utf-8', newline='\n')
    (HERE / '.assembled_build.md').write_text(assembled, encoding='utf-8', newline='\n')

    # 3. Convert Markdown -> HTML with server-side KaTeX + Virtual Barrels callouts + embed slots
    proc = subprocess.run([args.node, str(HERE / 'convert_markdown.mjs'), str(HERE / '.assembled_build.md')],
                          capture_output=True, text=True, encoding='utf-8')
    (HERE / '.assembled_build.md').unlink(missing_ok=True)
    if proc.returncode:
        raise SystemExit(proc.stderr)
    meta_out = json.loads(proc.stderr.strip().splitlines()[-1])
    math_count = meta_out['math']
    mod_root = Path(meta_out['modRoot'])

    soup = BeautifulSoup(proc.stdout, 'html.parser')
    if soup.h1:
        soup.h1.decompose()

    # Build charts, diagrams, interactives
    CHARTS = charts.all_charts()
    DIAGRAMS = build_diagrams()
    INTERACTIVES = build_interactives()
    used_charts = []

    def chart_html(cid: str) -> str:
        c = CHARTS[cid]
        used_charts.append(c)
        link = f'<span class="figure-links"><a href="#dl-{escape(c["csv"].replace(".", "-"))}">Data ↓</a></span>'
        return (f'<figure id="fig-{c["id"]}" class="inline-exhibit">'
                f'<figcaption><span>{escape(c["title"])}</span>{link}</figcaption>'
                f'<p class="exhibit-sub">{escape(c["subtitle"])}</p>'
                f'<div class="chart-scroll"><div id="{c["id"]}" class="plot" role="img" aria-label="{escape(c["title"])}"></div></div>'
                f'<p class="figure-note">{escape(c["note"])}</p></figure>')

    # Replace embed slots
    for slot in list(soup.find_all('div', class_='embed-slot')):
        kind = slot['data-kind']
        arg = slot['data-arg']
        if kind == 'exhibit':
            frag = BeautifulSoup(chart_html(arg), 'html.parser')
        elif kind == 'diagram':
            frag = BeautifulSoup(DIAGRAMS[arg], 'html.parser')
        elif kind == 'interactive':
            frag = BeautifulSoup(INTERACTIVES[arg], 'html.parser')
        elif kind == 'part':
            kicker, title, dek = arg.split('||', 2)
            part_html = (f'<div class="part-banner" data-part-kicker="{escape(kicker)}">'
                         f'<div class="part-kicker">{escape(kicker)}</div>'
                         f'<h2>{escape(title)}</h2><p>{escape(dek)}</p></div>')
            frag = BeautifulSoup(part_html, 'html.parser')
        else:
            raise SystemExit(f'Unknown embed directive: {kind}:{arg}')
        slot.replace_with(frag)

    # IDs, citations, tables, links
    toc = []
    chap_idx = 0
    for h in soup.find_all('h2'):
        if h.find_parent(class_='part-banner'):
            kicker = h.find_parent(class_='part-banner').get('data-part-kicker', '')
            toc.append(('__part__', kicker))
            continue
        h['id'] = f'chapter-{chap_idx}'
        toc.append((h['id'], h.get_text()))
        chap_idx += 1
    for i, h in enumerate(soup.find_all('h3')):
        h['id'] = f'subsection-{i}'
    for p in soup.find_all('p'):
        m = re.match(r'^\[([SLR]\d{1,2})\]', p.get_text())
        if m:
            p['id'] = 'source-' + m.group(1)
            p['class'] = 'source-entry'
    for node in list(soup.find_all(string=True)):
        if node.parent.name in ('a', 'code', 'pre', 'script', 'style', 'annotation') or node.find_parent(class_='katex'):
            continue
        if node.parent.get('class') == ['source-entry']:
            continue
        ms = list(re.finditer(r'\[([SLR]\d{1,2})((?:(?:[–-]|, )[SLR]?\d{1,2})*)\]', str(node)))
        if not ms:
            continue
        start = 0
        for m in ms:
            node.insert_before(NavigableString(str(node)[start:m.start()]))
            a = soup.new_tag('a', href='#source-' + m.group(1))
            a['class'] = 'citation'
            a.string = m.group(0)
            node.insert_before(a)
            start = m.end()
        node.insert_before(NavigableString(str(node)[start:]))
        node.extract()
    for table in soup.find_all('table'):
        if not table.find_parent(class_='table-wrap'):
            table.wrap(soup.new_tag('div', attrs={'class': 'table-wrap', 'tabindex': '0', 'role': 'region', 'aria-label': 'Research table'}))
    for a in soup.find_all('a', href=True):
        if a['href'].startswith('https://'):
            a['target'] = '_blank'
            a['rel'] = 'noopener noreferrer'

    # Wrap chapters (skipping front matter which sits before chapter-0, and keeping part banners outside <details>)
    blocks = []
    content = None
    in_chapters = False
    for child in list(soup.contents):
        name = getattr(child, 'name', None)
        if name == 'div' and 'part-banner' in (child.get('class') or []):
            blocks.append(child.extract())
            content = None
            in_chapters = True
        elif name == 'h2' and child.get('id', '').startswith('chapter-'):
            if child['id'] == 'chapter-0':
                # Executive overview sits as chapter-0 open
                pass
            det = soup.new_tag('details', attrs={'class': 'chapter', 'open': ''})
            summ = soup.new_tag('summary')
            summ.append(child.extract())
            det.append(summ)
            content = soup.new_tag('div', attrs={'class': 'chapter-content'})
            det.append(content)
            blocks.append(det)
            in_chapters = True
        elif content is not None:
            content.append(child.extract())
        elif not in_chapters:
            child.extract()
    research_html = ''.join(str(b) for b in blocks)

    # Inline KaTeX CSS + woff2 fonts
    kdir = mod_root / 'katex/dist'
    kcss = (kdir / 'katex.min.css').read_text(encoding='utf-8')

    def font_face(m):
        block = m.group(0)
        w = re.search(r'url\((fonts/[^)]+\.woff2)\)', block)
        if not w:
            return block
        data_b64 = base64.b64encode((kdir / w.group(1)).read_bytes()).decode()
        return re.sub(r'src:[^;}]+', f'src:url(data:font/woff2;base64,{data_b64}) format("woff2")', block)

    kcss = re.sub(r'@font-face\{[^}]+\}', font_face, kcss)
    assert 'url(fonts/' not in kcss

    # Datasets for interactive explorer
    DATA = {
        'spreads': load_csv(EV / 'spread_decomposition.csv'),
        'regions': load_csv(EV / 'regional_decomposition.csv'),
        'regimes': load_csv(EV / 'joint_regimes.csv'),
        'flows': load_csv(EV / 'flow_diagnostics_full.csv'),
    }
    DATA_V1 = {
        'spreads': load_csv(V1 / 'historical_spread_decomposition.csv'),
        'regions': load_csv(V1 / 'historical_regional_decomposition.csv'),
        'regimes': load_csv(V1 / 'historical_joint_regimes.csv'),
        'flows': load_csv(EV / 'flow_diagnostics_v1window.csv'),
    }

    # Downloads list (every chart CSV + all new Tier A CSVs + manifests)
    download_names = sorted(
        {c['csv'] for c in used_charts}
        | {
            'spread_decomposition.csv', 'regional_decomposition.csv', 'joint_regimes.csv',
            'flow_diagnostics_full.csv', 'sra_unit_registry.csv', 'sra_reconciliation.csv',
            'sra_payoff_decomposition.csv', 'auction_regime_sensitivity.csv',
            'auction_tranche_drift.csv', 'auction_carry_returns.csv',
            'loop_attribution_waterfall.csv', 'loop_hedge_effectiveness.csv',
            'loop_parametric_pec.csv', 'hedge_quarterly_and_components.csv',
            'hedge_two_instrument_frontier.csv', 'diurnal_regime_summary.csv',
            'negative_price_mechanics.csv', 'walk_forward_v3_scores.csv',
            'walk_forward_by_direction.csv', 'walk_forward_by_horizon.csv',
            'qni_dilution_check.csv', 'basslink_proforma_backcast.csv',
            'bid_stack_slippage.csv', 'mpc_cpt_normalised.csv',
            'qni_south_reconciliation_diag.csv', 'option_benchmark_v3.csv',
            'option_sensitivity_v3.csv', 'constraint_top_setters.csv',
            'data_audit.json', 'scenario_registry.json', 'headline_numbers.json',
        }
    )

    hl = N
    toc_html = ''.join(
        f'<a class="toc-part" tabindex="-1">{escape(t)}</a>' if i == '__part__' else f'<a href="#{i}">{escape(t)}</a>'
        for i, t in toc
    )

    body = f'''
<div id="top" class="masthead"><div class="brand"><strong>IC Flow<br>Forecasting</strong><span>Electricity<br>Research</span></div><div class="dateline">Version 3 · Mechanics-First Edition<br>Australian National Electricity Market</div></div>
<div class="hero-band">{hero('Interregional Strategy & Valuation', 'Valuing interregional spreads and SRA units in the NEM:', 'settlement plumbing, auction premia, hedge firmness, and implementation', '', [])}</div>
<nav class="topnav" aria-label="Report navigation">
  <a href="#chapter-1">Plumbing</a>
  <a href="#historicalExplorer">Explorer</a>
  <a href="#chapter-7">Auctions</a>
  <a href="#chapter-8">Hedging</a>
  <a href="#valuationLab">Workbench</a>
  <a href="#chapter-10">Implementation</a>
  <a href="#downloads">Data</a>
  <button id="printReport" type="button">Print / save PDF</button>
</nav>
<div class="front">
  <div>
    <ul class="summary-points">
      <li><strong>SRA units paid {hl['auction_ratio']}× clearing prices, and the discount survives outside the 2022 crisis.</strong> Across {hl['auction_tranches']} delivered tranches (October 2021 to June 2026), realised payoffs divided by clearing prices averaged {hl['auction_ratio']} (95% interval {hl['auction_ratio_lo']}–{hl['auction_ratio_hi']}). Excluding 2022 Q2 and 2022 Q3, the ratio remains {hl['auc_ratio_ex_2022_crisis']} ({hl['auc_lo_ex_2022_crisis']}–{hl['auc_hi_ex_2022_crisis']}), rising with horizon even after accounting for auction-to-cash credit-support carry.</li>
      <li><strong>Clearing prices remain the strongest ex-ante benchmark, and naive debiasing overshoots.</strong> Across {hl['wf3_n_market_clearing_price']} tranches with at least four prior settled quarters ({hl['wf3_first_auction']} to {hl['wf3_last_auction']}), raw clearing prices beat every historical rule ({hl['wf3_mae_market_clearing_price'].replace(chr(92), '')} MAE, biased low by {hl['wf3_bias_market_clearing_price'].replace(chr(92), '')}). Multiplying clearing prices by trailing crisis-inflated horizon ratios worsens MAE to {hl['wf3_mae_debiased_clearing_price'].replace(chr(92), '')}, showing that regime shifts punish mechanical ratio scaling.</li>
      <li><strong>Payoff drivers and hedge firmness diverge by corridor.</strong> On VICNSW, {hl['sra_dec_econg_pct_VICNSW']} of settled dollars came from sub-$300 energy congestion and {hl['sra_dec_scarc_pct_VICNSW']} from scarcity; one unit removes {hl['hedge_vr_VICNSW']} of weekly flat-spread variance ({hl['hc_qr2_tot_VICNSW']} quarterly) and drops to {hl['hedge_ratio_top_VICNSW']} MW-equivalent in stress weeks unless paired with a New South Wales $300 cap.</li>
      <li><strong>The November 2026 loop rule and 2027 Q2 QNI unit expansion reprice forward units.</strong> Under fixed dispatch, net-trade allocation trims VICNSW by {hl['loop_change_VICNSW']} (driven jointly by negative-loop netting and Victoria pass-through reallocation) and routes {hl['loop_new_categories'].replace(chr(92), '')} to NSW–SA categories, while QNI's 2027 Q2 unit expansion mechanically dilutes NSWQLD per-unit share by {hl['dil_pct_NSWQLD']}.</li>
    </ul>
  </div>
  <aside class="research-note">
    <h3>Research brief</h3>
    <p><strong>Evidence base</strong><br>{hl['intervals']} five-minute intervals ({hl['complete_quarters']} complete quarters, October 2021 to June 2026), AEMO-settled residues, and every public SRA auction and bid stack.</p>
    <p><strong>Version 3 upgrades</strong><br>Mechanics-first Virtual Barrels rewrite; inline exhibits; SRA dollar decomposition; ex-2022 &amp; carry tests; 3-way loop attribution; CPT-aware cap scaling; ex-ante option benchmark; full Part IV engineering runbook.</p>
    <p><strong>External data status</strong><br>AER base futures remain unobserved (automated retrieval blocked); loaders and conditional exhibits stay ready.</p>
    <p><strong>Status</strong><br>Research evidence and implementation specification, not a live trading signal.</p>
  </aside>
</div>
<div class="dual-paths">
  <div><strong>Desk &amp; Portfolio Path</strong><p>Read <a href="#chapter-2">Ch. 2 (Settlement Ledger)</a>, <a href="#chapter-3">Ch. 3 (Loop &amp; Dilution)</a>, <a href="#chapter-7">Ch. 7 (Auctions &amp; Carry)</a>, <a href="#chapter-8">Ch. 8 (Hedging &amp; Caps)</a>, and <a href="#chapter-9">Ch. 9 (Benchmarks &amp; Workbench)</a>.</p></div>
  <div><strong>Quant &amp; Implementation Path</strong><p>Read <a href="#chapter-1">Ch. 1 (Accounting)</a>, <a href="#chapter-2">Ch. 2–3 (Rules)</a>, <a href="#chapter-10">Ch. 10 (5-Layer Contracts)</a>, <a href="#chapter-11">Ch. 11 (Playbook &amp; Literature)</a>, <a href="#chapter-12">Ch. 12 (Validation Gates)</a>, and <a href="#chapter-13">Appendices A–C</a>.</p></div>
</div>
<div class="reading-intro" id="fullResearch">
  <div><div class="section-kicker">Complete mechanics-first analysis</div><h2>Four parts · twelve chapters · three technical appendices</h2></div>
  <div class="reading-actions"><button id="expandChapters" type="button">Expand all</button><button id="collapseChapters" type="button">Collapse all</button></div>
</div>
<p class="small-note">{chap_idx} chapters and appendices · {len(used_charts)} inline Plotly exhibits · 5 structural diagrams · 4 interactive labs · {math_count} KaTeX formulas · every statistic bound to audited CSVs.</p>
<div class="reading-layout">
  <article class="research-body">{research_html}</article>
  <aside class="research-rail" aria-label="Research navigation">
    <div class="rail-label">Reading guide</div>
    <label class="sr-only" for="reportSearch">Search the report</label>
    <input id="reportSearch" type="search" placeholder="Search topic, e.g. loop or CPT" autocomplete="off">
    <div id="searchResults" aria-live="polite"></div>
    <nav class="toc">{toc_html}</nav>
  </aside>
</div>
<section class="downloads" id="downloads">
  <h2>Research data and reproducibility</h2>
  <p class="small-note">Every exhibit dataset is embedded offline below. Recompute Tier A analytics with <code>python -m nemic.valuation.v3_analytics</code> and rebuild with <code>python build_html.py</code>.</p>
  <div class="download-grid">{''.join(embedded_download(n) for n in download_names)}</div>
</section>
<footer class="footer">
  <span>IC Flow Forecasting · Electricity Research · Version 3 (Virtual Barrels Edition)<br>Evidence window October 2021 – June 2026 (complete quarters), NEM time (UTC+10)</span>
  <span>Research evidence and implementation specification; not a trading recommendation.</span>
</footer>
<a class="back-top" href="#top" aria-label="Back to top">↑ Top</a>
'''

    template = go.Figure()
    style_plotly(template, '')
    base_layout = template.to_plotly_json()['layout']
    base_layout.pop('template', None)
    dj = lambda o: json.dumps(o, ensure_ascii=False, allow_nan=False, default=lambda x: None).replace('</', '<\\/')

    def clean(o):
        if isinstance(o, float) and o != o:
            return None
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o

    runtime = (
        f'<script>const DATA={dj(clean(DATA))};const DATA_V1={dj(clean(DATA_V1))};const BASE_LAYOUT={json.dumps(base_layout)};'
        f'const NEWCHARTS={dj(clean([{"id": c["id"], "fig": c["fig"]} for c in used_charts]))};</script>'
        '<script>' + (HERE / 'report_interactions.js').read_text(encoding='utf-8') + '</script>'
    )
    html = render_page('Interregional valuation research v3 | IC Flow Forecasting', body, plotly=True, accent='blue')
    html = html.replace('</head>', '<style>' + kcss + '</style><style>' + (HERE / 'institutional.css').read_text(encoding='utf-8') + '</style></head>')
    html = html.replace('</body>', runtime + '</body>')

    out = HERE / 'Interregional_Valuation_Research_v3.html'
    out.write_text(html, encoding='utf-8', newline='\n')

    # Write manifest
    chapter_files = ['chapters/00_front.md'] + CHAPTER_ORDER
    inputs = chapter_files + [
        'research_report.md', 'charts.py', 'build_html.py', 'convert_markdown.mjs',
        'report_interactions.js', 'institutional.css', 'report.css', 'report_theme.py', 'qa_report.cjs',
    ]
    manifest = {
        'version': 3,
        'editorial_standard': 'virtual-barrels-analysis',
        'evidence_window': 'interval ending after 2021-10-01 00:00 through 2026-09-01 00:00 UTC+10 (19 complete quarters 2021 Q4 to 2026 Q2)',
        'output': out.name,
        'chapters_and_appendices': chap_idx,
        'katex_formulas': math_count,
        'inline_plotly_exhibits': len(used_charts),
        'diagrams': len(DIAGRAMS),
        'interactive_labs': len(INTERACTIVES),
        'hash_convention': 'SHA-256 of file bytes with CRLF normalised to LF for text files',
        'inputs_sha256': {n: sha(HERE / n) for n in inputs if (HERE / n).exists()},
        'evidence_sha256': {p.name: sha(p) for p in sorted(EV.glob('*')) if p.is_file()},
        'code_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / 'nemic/valuation').glob('*.py'))},
        'output_sha256': sha(out),
        'dependencies': {'plotly': plotly.__version__, 'katex': '0.16.22', 'marked': '15.0.12', 'node': args.node},
        'futures': json.loads((EV / 'futures_status.json').read_text()),
    }
    (HERE / 'report_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8', newline='\n')
    print(json.dumps({
        'output': str(out), 'bytes': out.stat().st_size,
        'chapters': chap_idx, 'math': math_count, 'inline_charts': len(used_charts),
        'words_md': len(re.findall(r'\b\w+\b', clean_md)),
    }), flush=True)


if __name__ == '__main__':
    main()
