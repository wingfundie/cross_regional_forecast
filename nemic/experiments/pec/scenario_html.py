"""Render the local PEC scenario tool without browser dependencies."""

from pathlib import Path
import json

import pandas as pd


def render_scenario(observations, presets, features, directions, aggregations, periods, replicates, floor):
    fields = ["time", "configuration", "configuration_evidenced", "study_day", "delivery_period", *features]
    fields.extend(f"{direction}_{value}" for direction in directions
                  for value in (*aggregations, "setter", "minimum_time"))
    episode_fields = [f"{direction}_episode_id" for direction in directions
                      if f"{direction}_episode_id" in observations]
    fields.extend(episode_fields)
    observed = observations[observations["configuration"].notna()].loc[:, fields]
    payload = {
        "observations": json.loads(observed.to_json(orient="records", date_format="iso", double_precision=15)),
        "presets": json.loads(presets.to_json(orient="records", date_format="iso", double_precision=15)),
        "features": features, "directions": directions, "aggregations": aggregations,
        "periods": periods, "replicates": replicates, "floor": floor, "episode_fields": episode_fields,
    }
    if not observed.empty:
        payload["start"] = pd.Timestamp(observed["study_day"].min()).strftime("%d %b %Y")
        payload["end"] = pd.Timestamp(observed["study_day"].max()).strftime("%d %b %Y")
    encoded = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    script = Path(__file__).with_name("scenario_app.js").read_text(encoding="utf-8")
    return (PAGE.replace("/* __SCENARIO_CODE__ */", script)
            .replace("__SCENARIO_DATA__", encoded).replace("__CALIPER_FLOOR__", str(floor)))


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EnergyConnect limit scenarios</title>
<style>
:root{color-scheme:light;--paper:#f4f4ef;--panel:#fff;--ink:#162c2b;--sub:#4f6160;--line:#d3dfdb;--accent:#0a604e;--soft:#e5f1ec;--warn:#7e450a}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 system-ui,"Segoe UI",sans-serif}
header,main,footer{max-width:1240px;margin:0 auto;padding:0 clamp(16px,4vw,48px)}
header{padding-top:clamp(30px,6vw,72px);padding-bottom:22px}
.source{color:var(--accent);font:600 .85rem/1.4 system-ui;letter-spacing:.02em}h1,h2,h3,p{margin:0}
h1{font:normal clamp(2.25rem,5.2vw,4rem)/.99 Georgia,serif;letter-spacing:-.035em;margin:12px 0 16px}
h2{font:normal 1.8rem/1.15 Georgia,serif}h3{font-size:1rem}p+p{margin-top:10px}
.lead{max-width:68ch;color:var(--sub)}.periods{font-variant-numeric:tabular-nums}
main{display:grid;gap:20px}.panel{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:clamp(15px,3vw,28px)}
.tabs,.actions{display:flex;align-items:center;flex-wrap:wrap;gap:8px}
.tabs{padding-bottom:16px;border-bottom:1px solid var(--line);margin-bottom:18px}
button,select,input{font:inherit}button,select,input:not([type=file]){border:1px solid #9ab2ac;border-radius:8px;min-height:42px}
button{cursor:pointer;color:var(--ink);background:#fff;padding:6px 13px}button[aria-pressed=true]{background:var(--soft);border-color:var(--accent);color:var(--accent);font-weight:650}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:650}
button:hover:not(.primary){background:var(--soft)}button:disabled{opacity:.45;cursor:default}
button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,a:focus-visible{outline:3px solid #a86e18;outline-offset:3px}
input:not([type=file]),select{background:#fff;color:var(--ink);width:100%;padding:5px 8px}
input[type=file]{max-width:100%;font-size:.92rem}label{display:grid;gap:4px;font-size:.92rem;color:var(--sub);min-width:0}
.controls,.features{display:grid;grid-template-columns:minmax(0,1.4fr) repeat(2,minmax(0,1fr));gap:12px}
.controls{margin:12px 0}.features{grid-template-columns:repeat(3,minmax(0,1fr));margin:.7rem 0}
#feature-details{margin:6px 0 10px}select{text-overflow:ellipsis}
fieldset{padding:10px 12px;border:1px solid var(--line);border-radius:8px;margin:0;display:grid;gap:6px;min-width:0}legend{font-size:.87rem;font-weight:650;text-transform:uppercase}
summary{cursor:pointer;color:var(--accent);font-weight:650}small,.hint,.status{color:var(--sub)}small{display:block}
.hint,.status{margin:10px 0;font-size:.91rem}.error{color:#9b2a17}.thin{color:var(--warn)}[hidden]{display:none!important}
.resultbar{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.tablewrap{overflow:auto;max-height:34rem;border:1px solid var(--line);border-radius:8px;margin-top:10px}
table{border-collapse:collapse;width:100%;font-size:.85rem;font-variant-numeric:tabular-nums;white-space:nowrap}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line)}
thead th{position:sticky;top:0;background:#eaf0ee;z-index:1}
td.numeric{text-align:right}td button{min-height:30px;padding:3px 6px;text-align:left;font:inherit}
tbody tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#f7f9f8}
.detail{margin-top:18px;border-top:1px solid var(--line);padding-top:16px}.detail p{font-size:.92rem}
.days{margin:.65rem 0;white-space:normal;overflow-wrap:anywhere}
footer{padding-top:22px;padding-bottom:35px;font-size:.92rem;color:var(--sub)}a{color:var(--accent);text-underline-offset:3px}
@media(max-width:620px){
  .controls,.features{grid-template-columns:minmax(0,1fr)}
  .features fieldset{grid-template-columns:repeat(3,minmax(0,1fr))}
  .tabs button{flex:1 1 40%}
  #result-wrap[data-single=true]{max-height:none}
  #result-table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%)}
  #result-table,#result-table tbody{display:block}
  #result-table tr{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));padding:8px;border-bottom:1px solid var(--line)}
  #result-table td{min-width:0;font-size:.9rem;padding:4px 6px;border:0;text-align:left;white-space:normal;overflow-wrap:anywhere}
  #result-table td:nth-child(1),#result-table td:nth-child(9){grid-column:1/-1}
  #result-table td:nth-child(2){grid-column:span 2;font-weight:650}
  #result-table td:is(:nth-child(4),:nth-child(5),:nth-child(6)){background:var(--soft);font-weight:650}
  #result-table td[data-label]::before{content:attr(data-label);display:block;color:var(--sub);font-size:.7rem;font-weight:500}
}
</style>
</head>
<body>
<header>
  <div class="source" id="source">NSW1-SA1 · NEM time (UTC+10)</div>
  <h1>EnergyConnect limit scenarios</h1>
  <p class="lead">Compare observed limits in both directions under a selected network configuration and regional conditions. All estimates use AEMO dispatch-solution limits in MW.</p>
</header>
<main>
  <section class="panel" aria-label="Scenario inputs">
    <div class="tabs" aria-label="Input mode">
      <button type="button" data-mode="conditions" aria-pressed="true">Regional conditions</button>
      <button type="button" data-mode="upload" aria-pressed="false">Upload a CSV path</button>
      <button type="button" data-mode="historical" aria-pressed="false">Historical day</button>
    </div>
    <form id="conditions-form">
      <div class="controls">
        <label>Observed configuration <select id="configuration" required></select></label>
        <label>Delivery period <select id="period"></select></label>
        <label>Condition preset <select id="preset"></select></label>
      </div>
      <small id="preset-note"></small>
      <details id="feature-details">
        <summary>Edit regional MW values</summary>
        <p class="hint">Leave a field blank to omit it from matching.</p>
        <div class="features" id="features"></div>
      </details>
      <div class="actions"><button type="submit" class="primary">Estimate limits</button></div>
    </form>
    <form id="upload-form" hidden>
      <p class="hint">Upload interval-ending half-hours in ascending order. Enter local NEM timestamps such as 2026-11-20 00:30. Each row uses the exact configuration name.</p>
      <p class="hint">The template includes one observed day. Keep <code>time</code> and <code>configuration</code>. The nine regional MW columns are optional.</p>
      <label>Half-hour CSV file <input id="path-file" type="file" accept=".csv,text/csv" required></label>
      <div class="actions" style="margin-top:10px"><button type="submit" class="primary">Estimate path</button><button type="button" id="template">Download template</button></div>
    </form>
    <form id="historical-form" hidden>
      <div class="controls"><label>Observed NEM day <select id="historical-day" required></select></label></div>
      <p class="hint">Use a day's recorded configuration and regional MW values as the scenario path. Compare each half-hour with the study's observed intervals, including the selected day.</p>
      <div class="actions"><button type="submit" class="primary">Estimate using this day</button><button type="button" id="export-day">Download this input path</button></div>
    </form>
    <p id="error" class="status error" role="alert" hidden></p>
  </section>
  <section class="panel" id="results" aria-labelledby="results-heading">
    <div class="resultbar">
      <h2 id="results-heading">Directional assumptions</h2>
      <button type="button" id="export-results" disabled>Download results</button>
    </div>
    <p class="status" id="status" role="status"></p>
    <div class="tablewrap" id="result-wrap" tabindex="0" aria-label="Scenario estimates" hidden>
      <table id="result-table">
        <thead><tr><th scope="col">Input</th><th scope="col">Direction</th><th scope="col">Target</th>
          <th scope="col">P10 MW</th><th scope="col">Median MW</th><th scope="col">P90 MW</th>
          <th scope="col">Intervals</th><th scope="col">Days</th><th scope="col">Historical setter at minimum</th><th scope="col">Support</th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
    <div id="detail" class="detail" hidden></div>
  </section>
</main>
<footer>
  <p>Negative limits indicate forced flow. The quantiles describe observed limits. The 95% uncertainty intervals resample whole NEM days of matching intervals.</p>
  <p>The matching rule requires the same observed configuration and delivery period. For each entered MW field, the observed value must be within one cohort interquartile range or __CALIPER_FLOOR__ MW, whichever is greater. A query beyond the observed range in any field returns unsupported.</p>
  <p><a href="downloads/conditional_limits.csv">Download the configuration and period lookup</a> · <a href="downloads/conditional_support.csv">Download supporting intervals</a></p>
</footer>
<script type="application/json" id="data">__SCENARIO_DATA__</script>
<script>
/* __SCENARIO_CODE__ */
</script>
</body>
</html>
"""
