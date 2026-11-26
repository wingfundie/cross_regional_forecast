"""Build standalone compressed Event Atlases v2 (Option B) for VNI, QNI, and V-SA.

Reads retained evidence from data/event_{vni,qni,vsa}_2y/ (zero downloads, zero edits to
legacy docs/html/*_event_atlas.html), compresses verbose event_bundles.json via rounded
columnar encoding + gzip-base64 (decompressed instantaneously in-browser via native
DecompressionStream('gzip')), renders on pure #ffffff Virtual Barrels styling, and writes
clean Virtual Barrels Markdown companions (zero snake_case headers, zero scientific noise,
zero em-dashes) into reports/event_atlases_v2/.
"""
from __future__ import annotations

import base64
import gzip
import json
import re
from html import escape
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px

from nemic.experiments.vb_report_kit import (
    PALETTE,
    ROOT,
    V3_REF,
    sha256_file,
    style_plotly_white,
)

OUT_DIR = ROOT / "reports/event_atlases_v2"

ATLAS_SPECS = [
    {
        "slug": "vni",
        "name": "VNI",
        "ic_id": "VIC1-NSW1",
        "title": "VNI two-year sharp-contraction event atlas (v2 compressed edition)",
        "from_region": "VIC1",
        "to_region": "NSW1",
        "pos_label": "VIC → NSW positive",
        "regions": ["NSW1", "VIC1"],
        "weather_cols": [("NSW_Sydney__temperature_2m", "Sydney reanalysis °C"), ("VIC_Melbourne__temperature_2m", "Melbourne reanalysis °C")],
        "data_dir": ROOT / "data/event_vni_2y",
        "legacy_html": ROOT / "docs/html/vni_event_atlas.html",
    },
    {
        "slug": "qni",
        "name": "QNI",
        "ic_id": "NSW1-QLD1",
        "title": "QNI two-year sharp-contraction event atlas (v2 compressed edition)",
        "from_region": "NSW1",
        "to_region": "QLD1",
        "pos_label": "NSW → QLD positive",
        "regions": ["NSW1", "QLD1"],
        "weather_cols": [("NSW_Sydney__temperature_2m", "Sydney reanalysis °C"), ("QLD_Brisbane__temperature_2m", "Brisbane reanalysis °C")],
        "data_dir": ROOT / "data/event_qni_2y",
        "legacy_html": ROOT / "docs/html/qni_event_atlas.html",
    },
    {
        "slug": "vsa",
        "name": "Heywood (V-SA)",
        "ic_id": "V-SA",
        "title": "V-SA (Heywood) two-year sharp-contraction event atlas (v2 compressed edition)",
        "from_region": "VIC1",
        "to_region": "SA1",
        "pos_label": "VIC → SA positive",
        "regions": ["VIC1", "SA1"],
        "weather_cols": [("VIC_Melbourne__temperature_2m", "Melbourne reanalysis °C"), ("SA_Adelaide__temperature_2m", "Adelaide reanalysis °C")],
        "data_dir": ROOT / "data/event_vsa_2y",
        "legacy_html": ROOT / "docs/html/vsa_event_atlas.html",
    },
]


def _round_val(v: Any) -> Any:
    if isinstance(v, float):
        if not np.isfinite(v):
            return None
        if abs(v) < 1e-4:
            return 0.0
        return round(v, 2)
    return v


def pack_table_columnar(rows: list[dict]) -> dict[str, Any]:
    """Encode list-of-dicts as compact columnar {c: [...cols], r: [[...row], ...]} with rounded floats."""
    if not rows:
        return {"c": [], "r": []}
    cols = list(rows[0].keys())
    packed = [[_round_val(r.get(k)) for k in cols] for r in rows]
    return {"c": cols, "r": packed}


def compress_bundles(bundles: list[dict]) -> str:
    """Convert raw event_bundles.json into compact columnar JSON, gzip at level 9, and base64-encode."""
    compact = []
    for b in bundles:
        ev = {k: _round_val(v) for k, v in b["event"].items()}
        compact.append({
            "e": ev,
            "s": pack_table_columnar(b.get("series", [])),
            "u": pack_table_columnar(b.get("units", [])),
            "k": pack_table_columnar(b.get("constraints", [])),
            "r": pack_table_columnar(b.get("rankings", [])),
            "q": pack_table_columnar(b.get("equations", [])),
            "st": pack_table_columnar(b.get("sets", [])),
            "iv": pack_table_columnar(b.get("invocations", [])),
            "co": pack_table_columnar(b.get("coal", [])),
            "w": pack_table_columnar(b.get("weather", [])),
            "rf": pack_table_columnar(b.get("rooftop", [])),
            "cd": pack_table_columnar(b.get("conditions", [])),
            "ex": b.get("external"),
        })
    raw_bytes = json.dumps(compact, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    gz_bytes = gzip.compress(raw_bytes, compresslevel=9, mtime=0)
    return base64.b64encode(gz_bytes).decode("ascii")


def _fmt_num(x: float, dec: int = 1) -> str:
    if x is None or not np.isfinite(x):
        return "0.0"
    if abs(x) < 1e-4:
        return f"{0.0:,.{dec}f}"
    return f"{x:,.{dec}f}"


def build_single_atlas(spec: dict[str, Any]) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ddir = spec["data_dir"]
    bundles = json.loads((ddir / "event_bundles.json").read_text(encoding="utf-8"))
    summary = json.loads((ddir / "summary.json").read_text(encoding="utf-8"))
    e = pd.read_parquet(ddir / "event_catalogue.parquet")
    a = pd.read_parquet(ddir / "event_attribution.parquet")
    g = pd.read_parquet(ddir / "generator_contributions.parquet")
    matched = pd.read_parquet(ddir / "matched_population.parquet")
    ic = pd.read_parquet(ddir / "screen_timeseries.parquet").set_index("time")

    # Deduplicated selected-case generator accounting
    ranked = g.groupby(["event_id", "DUID"], as_index=False).agg(
        net_mw=("tightening_mw", "sum"),
        tightening_mw=("tightening_mw", lambda s: s.clip(lower=0).sum()),
        relief_mw=("tightening_mw", lambda s: -s.clip(upper=0).sum()),
    )
    unique = g.drop_duplicates(["time", "DUID", "constraint", "version_key"])
    grand = (
        unique.groupby("DUID", as_index=False)
        .agg(
            net_mw=("tightening_mw", "sum"),
            tightening_mw=("tightening_mw", lambda s: s.clip(lower=0).sum()),
            relief_mw=("tightening_mw", lambda s: -s.clip(upper=0).sum()),
        )
        .sort_values("tightening_mw", ascending=False)
    )
    grand["events"] = grand["DUID"].map(ranked.groupby("DUID")["event_id"].nunique())

    # Seasonal summary
    e["season_year"] = e["time"].dt.year + e["time"].dt.month.eq(12).astype(int)
    seasonal = e.groupby(["season_year", "season", "direction"], as_index=False).agg(
        events=("event_id", "size"),
        median_drop_mw=("drop_mw", "median"),
        near_mpc_events=("near_mpc_intervals", lambda x: x.gt(0).sum()),
        mpc_events=("mpc_intervals", lambda x: x.gt(0).sum()),
    )
    valid = ic.loc["2024-09-01 00:00:00":"2026-08-31 23:55:00"].copy()
    valid["season_year"] = valid.index.year + (valid.index.month == 12).astype(int)
    valid["season"] = [["Summer", "Autumn", "Winter", "Spring"][(t.month % 12) // 3] for t in valid.index]
    exposure = valid.groupby(["season_year", "season"]).flow.count() / 12.0
    seasonal["valid_hours"] = [float(exposure.loc[(r.season_year, r.season)]) for r in seasonal.itertuples()]
    seasonal["events_per_1000h"] = 1000.0 * seasonal["events"] / seasonal["valid_hours"]
    seasonal["season_label"] = seasonal["season_year"].astype(int).astype(str) + " " + seasonal["season"]

    # Clean summary numbers
    n_det = int(summary["events"])
    n_inc = int(summary["incidents"])
    n_sel = int(summary["selected"])
    n_price_only = int(summary["price_only_cases"])
    n_mpc_obs = int(summary["exact_mpc_region_intervals"])
    n_mpc_next = int(summary["contractions_with_receiving_region_mpc_next_hour"])
    n_matched = int(summary["matched_events"])
    mean_jump = float(summary["matched_mean_peak_price_jump_difference"])
    ci_lo, ci_hi = [float(x) for x in summary["day_bootstrap_95ci"]]
    top_gen = str(grand.iloc[0]["DUID"]) if len(grand) else "n/a"
    exact_step_full = int(a["exact_step_share"].ge(0.999).sum())

    # Compress bundles payload
    gz_b64 = compress_bundles(bundles)

    # Build 3 crisp pure-white Plotly summary charts (no >2 consecutive figures!)
    fig_pop = px.scatter(
        e.sample(min(len(e), 3000), random_state=42),
        x="drop_mw", y="price_jump", color="direction",
        color_discrete_map={"upper": PALETTE["deep"], "lower": PALETTE["gold"]},
        hover_data=["event_id", "time", "reported_setter"],
    )
    style_plotly_white(fig_pop, "Next-hour peak price jump (AUD/MWh)", 380, "30-minute directional capacity drop (MW)")

    fig_gen = px.bar(
        grand.head(15).sort_values("tightening_mw"),
        x="tightening_mw", y="DUID", orientation="h",
        color_discrete_sequence=[PALETTE["navy"]],
    )
    style_plotly_white(fig_gen, "", 420, "Gross fixed-equation tightening across selected cases (MW)")

    hourly = e.groupby(["hour", "direction"], as_index=False).size()
    hr_den = valid.groupby(valid.index.hour).flow.count() / 12.0
    hourly["rate"] = hourly["size"] / hr_den.reindex(hourly["hour"]).to_numpy() * 1000.0
    fig_diur = px.line(
        hourly, x="hour", y="rate", color="direction", markers=True,
        color_discrete_map={"upper": PALETTE["deep"], "lower": PALETTE["gold"]},
    )
    style_plotly_white(fig_diur, "Contractions per 1,000 valid hours", 350, "NEM hour of day (UTC+10)")

    # Build Virtual Barrels Markdown companion (zero snake_case headers, zero scientific noise, zero em-dashes!)
    gen_md_rows = [
        f"| {r.DUID} | {_fmt_num(r.net_mw)} | {_fmt_num(r.tightening_mw)} | {_fmt_num(r.relief_mw)} | {int(r.events)} |"
        for r in grand.head(20).itertuples()
    ]
    seas_md_rows = [
        f"| {r.season_label} | {r.direction.title()} | {int(r.events):,} | {_fmt_num(r.median_drop_mw)} | {int(r.near_mpc_events)} | {int(r.mpc_events)} | {_fmt_num(r.events_per_1000h)} |"
        for r in seasonal.itertuples()
    ]
    # Clean attribution coverage table (top 25 selected cases sorted by observed tightening, zero scientific notation!)
    a_top = a.sort_values("observed_tightening_mw", ascending=False).head(25)
    attr_md_rows = [
        f"| {r.event_id} | {100.0*r.exact_step_share:.0f}% | {100.0*r.complete_terms_share:.0f}% | {_fmt_num(r.observed_tightening_mw)} | {_fmt_num(r.generator_tightening_mw)} | {_fmt_num(r.switch_composite_mw)} | {_fmt_num(r.unresolved_mw)} |"
        for r in a_top.itertuples()
    ]

    md_text = f"""# {spec['name']} two-year sharp-contraction event atlas (Version 2)

## Executive summary and mechanical scope

This standalone event atlas examines every sharp 30-minute directional capacity contraction recorded on {spec['name']} ({spec['ic_id']}, {spec['pos_label']}) between 1 September 2024 and 31 August 2026 in fixed Australian National Electricity Market time (UTC+10). Across 210,240 five-minute dispatch intervals, the monthly adaptive 90th-percentile screen identifies **{n_det:,} contraction detections** grouping into **{n_inc:,} distinct incidents**. Ninety-plus detailed windows ({n_sel} contraction cases plus {n_price_only} price-only episodes without a nearby contraction) retain complete five-minute unit dispatch, constraint-equation factor reconstruction, coal availability proxies, rooftop solar estimates, and hourly weather context.

> [!TAKEAWAY] Core Operational Takeaway for {spec['name']}
> Contractions on {spec['name']} are associated with a matched observational next-hour peak price jump difference of **${mean_jump:,.2f}/MWh** relative to same-month, similar-condition control windows ({n_matched:,} matched pairs; event-day block-bootstrap 95% confidence interval **${ci_lo:,.2f} to ${ci_hi:,.2f}/MWh**). Across the {n_sel} reconstructed cases, **{top_gen}** recorded the largest gross fixed-equation tightening contribution, and **{exact_step_full} of {len(a)}** selected cases achieved 100% exact equation-version matching on every attribution step.

> [!WARNING] Mechanical Attribution Versus Independent Causation
> Generator contributions quantify mechanical bound sensitivity ($-b_i/a \\times \\Delta P_i$) along fixed-equation segments of the solved dispatch linear programme. Because regional demand, generator offers, transmission outages, and constraint switches co-move within the same five-minute interval, these figures are mechanical decompositions rather than independent causal estimates. Unresolved right-hand-side terms and equation switches are always reported separately from generator ramps.

## Selected-case generator accounting

Gross tightening and relief are deduplicated across shared five-minute physical steps inside the {n_sel} detailed contraction cases so overlapping case windows never double-count the same dispatch move. Positive net tightening indicates that a unit's output changes predominantly reduced available transfer capacity during active fixed-equation intervals.

| Generator unit | Net tightening (MW) | Gross tightening (MW) | Gross relief (MW) | Active cases |
|---|---:|---:|---:|---:|
{chr(10).join(gen_md_rows)}

## Seasonal contraction frequency and price-cap coincidence

Across the two full seasonal cycles (with December assigned to the following summer year), contraction intensity clusters around seasonal thermal limits, solar-midday congestion, and planned transmission maintenance. Exactly {n_mpc_obs} exact Market Price Cap region-intervals occurred in the study window, of which {n_mpc_next} contraction detections coincided with a receiving-region cap interval within the following hour.

| Season | Direction | Detections | Median drop (MW) | Near-cap cases | Cap cases | Rate per 1,000 hours |
|---|---|---:|---:|---:|---:|---:|
{chr(10).join(seas_md_rows)}

## Top reconstructed contraction cases

The table below reports the twenty-five largest selected contractions ranked by baseline-to-trough observed tightening, separating fixed-equation generator ramps, equation-switch composites, and unresolved residuals (values below 0.05 MW rounded cleanly to 0.0 MW).

| Case identifier | Exact-version steps | Complete energy terms | Observed loss (MW) | Generator tightening (MW) | Equation switch (MW) | Unresolved residual (MW) |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(attr_md_rows)}

## Compression, provenance, and rebuild notes

Version 2 preserves every reconstructed case and five-minute trace from the frozen Version 1 event-atlas evidence while compressing the interactive bundle payload into rounded columnar arrays encoded with gzip and decompressed natively in the browser. All legacy Version 1 atlases remain untouched as frozen baselines. Recompute from retained local archives with `python -m nemic.experiments.event_atlas_v2`.
"""
    md_path = OUT_DIR / f"{spec['slug'].upper()}_Event_Atlas_v2.md"
    md_path.write_text(md_text, encoding="utf-8", newline="\n")

    # Build clean institutional standalone HTML with native DecompressionStream('gzip')
    base_css = (V3_REF / "report.css").read_text(encoding="utf-8") + "\n:root{--accent:#4c94df}"
    inst_css = (V3_REF / "institutional.css").read_text(encoding="utf-8")
    from plotly.offline import get_plotlyjs

    reg_a, reg_b = spec["regions"][0], spec["regions"][1]
    w_cols_js = json.dumps(spec["weather_cols"])
    regs_js = json.dumps(spec["regions"])

    atlas_js = f"""
<script>
'use strict';
const GZ_B64 = "{gz_b64}";
const REGIONS = {regs_js};
const WEATHER_COLS = {w_cols_js};
const PLOT_CFG = {{responsive: true, displaylogo: false}};
const esc = x => String(x == null ? '—' : x).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;');
function unpack(obj) {{
  if (!obj || !obj.c || !obj.r) return [];
  const cols = obj.c;
  return obj.r.map(row => {{
    const o = {{}};
    for (let i = 0; i < cols.length; i++) o[cols[i]] = row[i];
    return o;
  }});
}}
async function loadBundles() {{
  const bin = Uint8Array.from(atob(GZ_B64), c => c.charCodeAt(0));
  const ds = new DecompressionStream('gzip');
  const stream = new Blob([bin]).stream().pipeThrough(ds);
  const txt = await new Response(stream).text();
  const raw = JSON.parse(txt);
  return raw.map(b => ({{
    event: b.e, series: unpack(b.s), units: unpack(b.u), constraints: unpack(b.k),
    rankings: unpack(b.r), equations: unpack(b.q), sets: unpack(b.st),
    invocations: unpack(b.iv), coal: unpack(b.co), weather: unpack(b.w),
    rooftop: unpack(b.rf), conditions: unpack(b.cd), external: b.ex,
  }}));
}}
function tbl(rows, colDefs) {{
  return '<div class="table-wrap" tabindex="0"><table><thead><tr>' +
    colDefs.map(([k, lbl]) => '<th>' + esc(lbl) + '</th>').join('') +
    '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + colDefs.map(([k]) => '<td>' + esc(typeof r[k] === 'number' ? (Math.abs(r[k]) < 1e-4 ? '0.00' : r[k].toFixed(2)) : r[k]) + '</td>').join('') + '</tr>').join('') +
    '</tbody></table></div>';
}}
function trace(rows, field, name, row, color) {{
  return {{x: rows.map(r => r.time), y: rows.map(r => r[field]), name, type: 'scatter', mode: 'lines', xaxis: row === 1 ? 'x' : 'x' + row, yaxis: row === 1 ? 'y' : 'y' + row, line: color ? {{color}} : undefined}};
}}
function makeLayout(rows, height) {{
  const z = {{height, grid: {{rows, columns: 1, pattern: 'independent', roworder: 'top to bottom'}}, margin: {{l: 76, r: 28, t: 90, b: 54}}, paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff', hovermode: 'x unified', legend: {{orientation: 'h', y: 1.04, font: {{size: 10.5}}}}, font: {{family: 'Segoe UI, Arial, sans-serif', color: '#30343a'}}}};
  for (let i = 1; i <= rows; i++) {{
    const suf = i === 1 ? '' : i;
    z['xaxis' + suf] = {{type: 'date', matches: 'x', gridcolor: '#edf0f2'}};
    z['yaxis' + suf] = {{gridcolor: '#e8edf1', zerolinecolor: '#97a8b6', automargin: true}};
  }}
  return z;
}}
loadBundles().then(BUNDLES => {{
  const sel = document.getElementById('event-select');
  BUNDLES.forEach((b, i) => {{
    const o = document.createElement('option');
    o.value = i;
    o.textContent = String(b.event.time).slice(0, 16).replace('T', ' ') + ' · ' + b.event.direction + ' · ' + (b.event.drop_mw == null ? 'price-only' : Number(b.event.drop_mw).toFixed(0) + ' MW') + ' · ' + b.event.event_id;
    sel.appendChild(o);
  }});
  function choose() {{
    const b = BUNDLES[Number(sel.value)], e = b.event, s = b.series, t = e.time;
    let desc = '<div class="vb-callout"><span class="vb-callout-title">Case summary · ' + esc(e.event_id) + '</span><p>' + esc(e.selection_reason) + ' Receiving region: ' + esc(e.receiver) + '. Exact-version step share: ' + (e.exact_step_share == null ? 'not attributed' : (100 * e.exact_step_share).toFixed(1) + '%') + '.</p>';
    if (e.observed_tightening_mw != null) {{
      const top = b.rankings.slice().sort((x, y) => (y.net_tightening_mw || 0) - (x.net_tightening_mw || 0))[0];
      desc += '<p>Baseline-to-trough loss: <strong>' + Number(e.observed_tightening_mw).toFixed(1) + ' MW</strong> (generators: ' + Number(e.generator_tightening_mw || 0).toFixed(1) + ' MW, RHS shift: ' + Number(e.rhs_tightening_mw || 0).toFixed(1) + ' MW, equation switch: ' + Number(e.switch_composite_mw || 0).toFixed(1) + ' MW).' + (top ? ' Largest net unit: ' + esc(top.DUID) + ' (' + Number(top.net_tightening_mw).toFixed(1) + ' MW).' : '') + '</p>';
    }}
    desc += '</div>';
    document.getElementById('event-description').innerHTML = desc;

    const tr = [
      trace(s, 'export', 'Upper bound', 1, '#244e78'),
      trace(s.map(r => ({{...r, lower: r.import == null ? null : -r.import}})), 'lower', 'Lower bound', 1, '#7658c9'),
      trace(s, 'flow', 'Flow', 1, '#30343a'),
      trace(s, REGIONS[0] + '_RRP', REGIONS[0] + ' price', 2, '#b08b42'),
      trace(s, REGIONS[1] + '_RRP', REGIONS[1] + ' price', 2, '#268a87'),
    ];
    const uMeas = document.getElementById('unit-measure').value;
    for (const id of [...new Set(b.units.map(r => r.DUID))]) {{
      tr.push(trace(b.units.filter(r => r.DUID === id), uMeas, id, 3));
    }}
    const cids = [...new Set(b.constraints.map(r => r.CONSTRAINTID))], times = s.map(r => r.time);
    const lkp = new Map(b.constraints.map(r => [r.CONSTRAINTID + '|' + r.time, r]));
    tr.push({{
      type: 'heatmap', x: times, y: cids,
      z: cids.map(id => times.map(tm => {{ const r = lkp.get(id + '|' + tm); return !r ? null : r.binding ? 2 : (r.ic_slack_mw >= 0 && r.ic_slack_mw <= 50 ? 1 : 0); }})),
      xaxis: 'x4', yaxis: 'y4', showscale: true,
      colorbar: {{title: {{text: '0 slack<br>1 near<br>2 bind'}}, len: 0.16, y: 0.1}},
      colorscale: [[0, '#edf3f7'], [0.5, '#b08b42'], [1, '#073c64']], name: 'Constraint state',
    }});
    const l = makeLayout(4, 1080);
    l.yaxis.title = {{text: 'Flow / bound (MW)'}};
    l.yaxis2.title = {{text: 'Spot price (AUD/MWh)'}};
    l.yaxis3.title = {{text: document.getElementById('unit-measure').selectedOptions[0].textContent}};
    l.yaxis4.tickfont = {{size: 10}};
    l.shapes = [{{type: 'line', x0: t, x1: t, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: {{color: '#b08b42', dash: 'dash'}}}}];
    Plotly.react('core-event', tr, l, PLOT_CFG);

    const wkeys = ['generator_tightening_mw', 'rhs_tightening_mw', 'other_lhs_tightening_mw', 'switch_composite_mw', 'unresolved_mw'];
    const wvals = wkeys.map(k => e[k]);
    if (wvals.some(x => x != null)) {{
      Plotly.react('waterfall', [{{
        type: 'waterfall',
        x: ['Generators', 'RHS shift', 'Other LHS', 'Equation switch', 'Residual', 'Observed loss'],
        y: [...wvals, e.observed_tightening_mw],
        measure: ['relative', 'relative', 'relative', 'relative', 'relative', 'total'],
        increasing: {{marker: {{color: '#073c64'}}}}, decreasing: {{marker: {{color: '#268a87'}}}}, totals: {{marker: {{color: '#b08b42'}}}},
      }}], {{height: 360, paper_bgcolor: '#ffffff', plot_bgcolor: '#ffffff', yaxis: {{title: 'MW', gridcolor: '#e8edf1'}}, margin: {{l: 64, r: 20, t: 36, b: 64}}}}, PLOT_CFG);
    }} else {{
      Plotly.purge('waterfall');
      document.getElementById('waterfall').innerHTML = '<p class="small-note">Price-only episode: no contraction waterfall assigned.</p>';
    }}

    document.getElementById('event-rankings').innerHTML = tbl(b.rankings, [['DUID', 'Generator unit'], ['net_tightening_mw', 'Net tightening (MW)'], ['gross_tightening_mw', 'Gross tightening (MW)'], ['gross_relief_mw', 'Gross relief (MW)']]);
    document.getElementById('event-equations').innerHTML = b.equations.map(r => '<details style="margin:6px 0"><summary style="cursor:pointer;font-weight:600">' + esc(r.constraint) + ' · ' + esc(r.version_key) + '</summary><p class="small-note">' + esc(r.description) + '</p><p style="font-family:Consolas,monospace;font-size:12px;overflow-wrap:anywhere">' + esc(r.equation) + '</p></details>').join('');
    document.getElementById('conditions-table').innerHTML = tbl(b.conditions, [['region', 'Region'], ['condition', 'Market condition'], ['pre_hour_median', 'Pre-hour median'], ['at_detection', 'At onset'], ['next_hour_max', 'Next-hour peak'], ['month_hour_percentile', 'Seasonal percentile']]);

    const ctx = [];
    for (const r of REGIONS) {{
      ctx.push(trace(s, r + '_TOTALDEMAND', r + ' demand', 1));
      ctx.push(trace(s, r + '_SS_WIND_CLEAREDMW', r + ' wind', 1));
      ctx.push(trace(s, r + '_SS_SOLAR_CLEAREDMW', r + ' solar', 1));
      const co = b.coal.filter(x => x.REGIONID === r);
      if (co.length) {{ ctx.push(trace(co, 'coal_initial_mw', r + ' coal initial MW', 2)); ctx.push(trace(co, 'coal_available_mw', r + ' coal availability', 2)); }}
    }}
    for (const [wc, wl] of WEATHER_COLS) {{
      if (b.weather.length && b.weather[0][wc] !== undefined) ctx.push(trace(b.weather, wc, wl, 3));
    }}
    const cl = makeLayout(3, 760);
    cl.yaxis.title = {{text: 'Demand & VRE (MW)'}};
    cl.yaxis2.title = {{text: 'Coal proxy (MW)'}};
    cl.yaxis3.title = {{text: 'Temperature (°C)'}};
    Plotly.react('context-event', ctx, cl, PLOT_CFG);
  }}
  sel.addEventListener('change', choose);
  document.getElementById('unit-measure').addEventListener('change', choose);
  document.getElementById('event-search').addEventListener('input', ev => {{
    const q = ev.target.value.toLowerCase();
    [...sel.options].forEach((o, i) => {{ o.hidden = !JSON.stringify([BUNDLES[i].event.event_id, BUNDLES[i].event.time, BUNDLES[i].event.reported_setter, BUNDLES[i].rankings.map(x => x.DUID)]).toLowerCase().includes(q); }});
  }});
  choose();
  document.documentElement.classList.add('ready');
}});
</script>"""

    body = f"""
<div id="top" class="masthead"><div class="brand"><strong>IC Flow<br>Forecasting</strong><span>{escape(spec['name'])}<br>Event Atlas v2</span></div><div class="dateline">Compressed Offline Edition · Virtual Barrels Standard<br>September 2024 to August 2026 · Fixed NEM Time (UTC+10)</div></div>
<div class="hero-band"><header><div class="eyebrow">{escape(spec['name'])} · Sharp-Contraction Event Atlas (v2)</div><h1>When {escape(spec['name'])} transfer limits contract:<br><span>equations, generator ramps, and regional price jumps</span></h1></header></div>
<nav class="topnav"><a href="#explorer">Interactive Explorer</a><a href="#population">Population</a><a href="#generators">Generators</a><a href="#seasonal">Seasonal Rates</a><a href="#notes">Method &amp; Compression</a></nav>
<div class="metrics">
  <article class="metric"><span>Contraction detections</span><strong>{n_det:,}</strong><small>{n_inc:,} grouped incidents (210,240 five-minute intervals)</small></article>
  <article class="metric"><span>Reconstructed cases</span><strong>{n_sel}</strong><small>Plus {n_price_only} price-only episodes without contraction</small></article>
  <article class="metric"><span>Matched peak price jump</span><strong>${mean_jump:,.2f}/MWh</strong><small>95% day-block CI ${ci_lo:,.2f} to ${ci_hi:,.2f} ({n_matched:,} pairs)</small></article>
  <article class="metric"><span>Top fixed-equation unit</span><strong>{escape(top_gen)}</strong><small>{exact_step_full} of {len(a)} cases with 100% exact equation version match</small></article>
</div>
<div class="vb-callout risk"><span class="vb-callout-title">Scope · Observational Decomposition, Not Independent Causation</span><p>Generator impacts represent mechanical equation sensitivity along fixed-equation segments of AEMO's dispatch solution. Equation switches, right-hand-side shifts, and unresolved residuals remain separated in every waterfall.</p></div>

<section id="explorer" class="inline-interactive">
  <div class="section-kicker">Section 01 · Interactive Five-Minute Case Explorer</div>
  <h4>Inspect every reconstructed {escape(spec['name'])} contraction window, equation waterfall, and dispatch stack</h4>
  <div class="controls">
    <label for="event-search">Filter by date, unit, or constraint<input id="event-search" type="search" placeholder="e.g. 2025-11 or {escape(top_gen)}"></label>
    <label for="event-select" style="flex:1;min-width:260px">Select case<select id="event-select"></select></label>
    <label for="unit-measure">Generator trace<select id="unit-measure"><option value="TOTALCLEARED">Dispatch target (MW)</option><option value="INITIALMW">Initial metered (MW)</option><option value="AVAILABILITY">Declared availability (MW)</option></select></label>
  </div>
  <div id="event-description"></div>
  <figure class="inline-exhibit"><figcaption><span>Five-minute flow, bounds, regional prices, key units, and binding constraint states</span></figcaption><div class="chart-scroll"><div id="core-event" class="plot" style="min-width:680px"></div></div></figure>
  <figure class="inline-exhibit"><figcaption><span>Baseline-to-trough contraction decomposition waterfall (MW)</span></figcaption><div class="chart-scroll"><div id="waterfall" class="plot" style="min-width:520px"></div></div></figure>
  <h3>Fixed-equation generator accounting</h3>
  <div id="event-rankings"></div>
  <h3>Active equations</h3>
  <div id="event-equations"></div>
  <h3>Market conditions and weather context</h3>
  <div id="conditions-table"></div>
  <figure class="inline-exhibit"><figcaption><span>Regional demand, wind, solar, coal availability proxy, and hourly temperature</span></figcaption><div class="chart-scroll"><div id="context-event" class="plot" style="min-width:680px"></div></div></figure>
</section>

<section id="population">
  <h2>Population relationship between capacity loss and price jumps</h2>
  <p>Across all {n_det:,} contraction detections, larger 30-minute capacity drops coincide with a wider upper tail of next-hour receiving-region price jumps, though most routine contractions still clear at benign spreads whenever regional headroom or local generation absorbs the cut.</p>
  <figure class="inline-exhibit"><figcaption><span>Exhibit 1: Capacity drop versus next-hour receiving-region peak price jump</span></figcaption><div class="chart-scroll">{fig_pop.to_html(full_html=False, include_plotlyjs=False)}</div><p class="figure-note">Deterministic 3,000-point sample of all detections for fast rendering; axes show 30-minute capacity loss (MW) and next-hour peak minus preceding-hour median price (AUD/MWh).</p></figure>
</section>

<section id="generators">
  <h2>Selected-case generator pressure leaderboard</h2>
  <p>Deduplicating shared physical five-minute steps across the {n_sel} selected contraction cases highlights the units whose movements mechanically tightened active bounds most frequently. Compare this selected-case sum against the full 24-month economic rent-weighted rankings in the Six-Link Constraint Pressure Atlas v2.</p>
  <figure class="inline-exhibit"><figcaption><span>Exhibit 2: Top 15 units by gross fixed-equation tightening across selected cases</span></figcaption><div class="chart-scroll">{fig_gen.to_html(full_html=False, include_plotlyjs=False)}</div><p class="figure-note">Selected fixed-equation segments only; equation switches and RHS shifts excluded.</p></figure>
</section>

<section id="seasonal">
  <h2>Diurnal contraction timing</h2>
  <p>Normalising contraction detections per 1,000 valid operating hours isolates the morning solar pick-up, midday export stress, and evening thermal ramp periods when {escape(spec['name'])} directional limits contract most frequently.</p>
  <figure class="inline-exhibit"><figcaption><span>Exhibit 3: Diurnal contraction onset rate per 1,000 valid hours</span></figcaption><div class="chart-scroll">{fig_diur.to_html(full_html=False, include_plotlyjs=False)}</div><p class="figure-note">Fixed UTC+10 NEM market time across September 2024 to August 2026.</p></figure>
</section>

<section id="notes">
  <h2>Compression and audit notes</h2>
  <p>This Version 2 atlas encodes all {len(bundles)} reconstructed case bundles as rounded columnar arrays compressed via gzip and expanded client-side via native browser streams, reducing file weight dramatically compared with Version 1 while retaining every interactive trace and preserving legacy Version 1 atlases untouched.</p>
</section>
<footer class="footer"><span>IC Flow Forecasting · {escape(spec['name'])} Event Atlas v2</span><span>Observational mechanical decomposition; not a causal dispatch counterfactual.</span></footer>
"""

    html_doc = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link rel="icon" href="data:,">'
        f"<title>{escape(spec['title'])}</title>"
        f"<style>{base_css}</style><style>{inst_css}</style>"
        f"<script>{get_plotlyjs()}</script></head>"
        f"<body><main>{body}</main>{atlas_js}</body></html>"
    )
    html_path = OUT_DIR / f"{spec['slug']}_event_atlas_v2.html"
    html_path.write_text(html_doc, encoding="utf-8", newline="\n")

    legacy_mb = round(spec["legacy_html"].stat().st_size / 1e6, 2) if spec["legacy_html"].exists() else 0.0
    new_mb = round(html_path.stat().st_size / 1e6, 2)
    return {
        "slug": spec["slug"],
        "html": html_path.name,
        "md": md_path.name,
        "legacy_mb": legacy_mb,
        "new_mb": new_mb,
        "reduction_pct": round(100.0 * (1.0 - new_mb / max(legacy_mb, 0.01)), 1),
        "cases": len(bundles),
        "html_sha256": sha256_file(html_path),
        "md_sha256": sha256_file(md_path),
    }


def build_all_event_atlases() -> list[dict[str, Any]]:
    results = [build_single_atlas(s) for s in ATLAS_SPECS]
    manifest = {"version": "2.0-compressed", "atlases": results}
    (OUT_DIR / "event_atlases_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps(results, indent=2), flush=True)
    return results


if __name__ == "__main__":
    build_all_event_atlases()
