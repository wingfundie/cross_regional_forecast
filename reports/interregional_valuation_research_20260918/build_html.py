"""Build the offline report from the frozen research and CSV results.

Run with the bundled Python runtime; --node and --marked override dependencies.
No price or market data is fetched during the presentation build.
"""
from pathlib import Path
import argparse, base64, csv, hashlib, json, re, subprocess
from datetime import datetime, timezone
from html import escape
from bs4 import BeautifulSoup, NavigableString
import plotly.graph_objects as go
import plotly
from report_theme import hero, metric, figure_html, style_plotly, render_page

ROOT = Path(__file__).resolve().parent
RUNTIME = Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies'
parser = argparse.ArgumentParser()
parser.add_argument('--node',default=str(RUNTIME/'node/bin/node.exe'))
parser.add_argument('--marked',default=str(RUNTIME/'node/node_modules/marked/lib/marked.esm.js'))
args = parser.parse_args()

def load_csv(name):
    rows=[]
    for row in csv.DictReader((ROOT/name).open(encoding='utf-8-sig',newline='')):
        for k,v in row.items():
            if v in ('True','False'): row[k]=v=='True'
            else:
                try: row[k]=float(v)
                except ValueError: pass
        rows.append(row)
    return rows

DATA={
    'spreads':load_csv('historical_spread_decomposition.csv'),
    'regions':load_csv('historical_regional_decomposition.csv'),
    'regimes':load_csv('historical_joint_regimes.csv'),
    'flows':load_csv('historical_flow_diagnostics.csv'),
}
audit=json.loads((ROOT/'historical_audit.json').read_text())
assert {r['direction'] for r in DATA['spreads']}=={'VIC to NSW','NSW to QLD','VIC to SA'}
assert all(abs(r['spread']-r['energy']-r['scarcity'])<1e-8 for r in DATA['spreads'])
print('Frozen data loaded and decomposition checked.',flush=True)
converted=subprocess.run([args.node,str(ROOT/'convert_markdown.mjs'),args.marked,str(ROOT/'research_report.md')],capture_output=True,text=True,encoding='utf-8',check=True).stdout
soup=BeautifulSoup(converted,'html.parser')
if soup.h1: soup.h1.decompose()
toc=[]
for i,h in enumerate(soup.find_all('h2')):
    title=h.get_text()
    ident='chapter-'+str(i)
    h['id']=ident
    toc.append((ident,title))
for i,h in enumerate(soup.find_all('h3')): h['id']='subsection-'+str(i)
for p in soup.find_all('p'):
    m=re.match(r'^\[([SL]\d{2})\]',p.get_text())
    if m:
        p['id']='source-'+m.group(1)
        p['class']='source-entry'
for node in list(soup.find_all(string=True)):
    if node.parent.name in ('a','code','pre','script','style'):continue
    if node.parent.get('class')==['source-entry']: continue
    matches=list(re.finditer(r'\[([SL]\d{2})\]',str(node)))
    if not matches: continue
    start=0
    for m in matches:
        node.insert_before(NavigableString(str(node)[start:m.start()]))
        a=soup.new_tag('a',href='#source-'+m.group(1));a['class']='citation';a.string=m.group(0)
        a['aria-label']='Source '+m.group(1);node.insert_before(a);start=m.end()
    node.insert_before(NavigableString(str(node)[start:]));node.extract()
for table in soup.find_all('table'):
    wrapper=soup.new_tag('div',attrs={'class':'table-wrap','tabindex':'0','role':'region','aria-label':'Research table; scroll horizontally if needed'})
    table.wrap(wrapper)
embedded_figures=[]
for img in soup.find_all('img',src=True):
    source=(ROOT/img['src']).resolve()
    if not source.is_relative_to(ROOT) or not source.is_file():
        raise ValueError('Missing or unexpected local figure: '+img['src'])
    embedded_figures.append(source.relative_to(ROOT).as_posix())
    image_mime='image/png' if source.suffix.lower()=='.png' else 'image/jpeg'
    img['src']='data:'+image_mime+';base64,'+base64.b64encode(source.read_bytes()).decode()
    img['loading']='lazy'
for a in soup.find_all('a',href=True):
    if a['href'].startswith('https://'):a['target']='_blank';a['rel']='noopener noreferrer'
chapters=[];current=None;content=None
for child in list(soup.contents):
    if getattr(child,'name',None)=='h2':
        current=soup.new_tag('details',attrs={'class':'chapter','open':''})
        summary=soup.new_tag('summary');summary.append(child.extract());current.append(summary)
        content=soup.new_tag('div',attrs={'class':'chapter-content'});current.append(content);chapters.append(current)
    elif content is not None:content.append(child.extract())
research_html=''.join(str(c) for c in chapters)
assert len(chapters)==26, len(chapters)
print('Full research converted: 26 chapters and appendices.',flush=True)

def embedded_download(name,label):
    mime='text/csv' if name.endswith('.csv') else ('application/json' if name.endswith('.json') else 'text/plain')
    payload=base64.b64encode((ROOT/name).read_bytes()).decode()
    return f'<a href="data:{mime};base64,{payload}" download="{escape(name)}">{escape(label)} ↓</a>'

def field(id,label,value,step='1',minimum=None):
    lo=f' min="{minimum}"' if minimum is not None else ''
    return f'<label for="{id}">{label}<input id="{id}" type="number" value="{value}" step="{step}"{lo}></label>'

def dynamic_metric(label,id,note):
    result=metric(label,'—',note)
    return result.replace('<strong>',f'<strong id="{id}">')

first=next(r for r in DATA['spreads'] if r['direction']=='VIC to NSW' and r['quarter']=='2024Q4')
sa=next(r for r in DATA['spreads'] if r['direction']=='VIC to SA' and r['quarter']=='2026Q1')
history_note='Source: archived project five-minute prices; complete quarters only, 2024 Q4–2026 Q2. Energy = min(price, 300); scarcity = max(price − 300, 0). Price archive has not been reconciled to all final exchange revisions. Bar components sum algebraically, including when one is negative.'
body=f'''
<div id="top" class="masthead"><div class="brand"><strong>IC Flow<br>Forecasting</strong><span>Electricity<br>Research</span></div><div class="dateline">18 September 2026<br>Australian National Electricity Market</div></div>
<div class="hero-band">{hero('Interregional Strategy','Valuing quarterly interregional spreads:', 'Energy, scarcity and the price of transmission', '', [])}</div>
<nav class="topnav" aria-label="Report shortcuts"><a href="#historicalExplorer">Historical evidence</a><a href="#eventExplorer">Scarcity events</a><a href="#valuationLab">Valuation workbench</a><a href="#visualAtlas">Visual framework</a><a href="#fullResearch">Full research</a><a href="#chapter-23">Sources</a><button id="printReport">Print / save PDF</button></nav>
<div class="front"><div><ul class="summary-points">
<li><strong>Value the joint behaviour of prices and flows across the quarter.</strong> Average flow alone cannot value a regional futures spread or an SRA. The model needs to preserve when price separation occurs, whether transfer is feasible, and how the contract allocates the resulting residue.</li>
<li><strong>Separate capped energy from scarcity excess with an exact identity.</strong> The first $300/MWh of every price remains in energy; only the excess belongs to the scarcity component. Base futures less $300 caps provide the matching market decomposition.</li>
<li><strong>The source of spread value changes materially by quarter.</strong> NSW minus VIC averaged ${first['spread']:.2f}/MWh in 2024 Q4: ${first['energy']:.2f} from capped energy and ${first['scarcity']:.2f} from scarcity excess. In 2026 Q1, scarcity contributed ${sa['scarcity']:.2f} of the ${sa['spread']:.2f}/MWh SA-minus-VIC spread. <a class="citation" href="#source-L01">[L01]</a></li>
<li><strong>Build two linked distributions: a physical forecast and a market calibration.</strong> Infer what scarcity severity, duration, coincidence and transfer availability would justify observed prices. Keep uncertainty and risk premia visible; a quoted cap or SRA does not uniquely identify event probability.</li>
</ul></div><aside class="research-note"><h3>Research brief</h3><p><strong>Coverage</strong><br>Quarterly futures, $300 caps and directional settlement residue auction units.</p><p><strong>Evidence</strong><br>32 external references; original analysis of {audit['intervals']:,} five-minute timestamps across four mainland regions.</p><p><strong>Data window</strong><br>September 2024–August 2026. Seven complete quarters in the interactive exhibits.</p><p><strong>Valuation status</strong><br>Research design and historical evidence. No current executable quote curve or live buy/sell conclusion.</p></aside></div>
<section id="historicalExplorer" class="exhibit-section"><div class="section-kicker">Interactive exhibit 01 · realised history</div><h2>How much of the regional spread came from energy or scarcity?</h2><p class="section-dek">Select the destination and origin explicitly. Positive means the destination price was higher. Reversing direction reverses the spread and exchanges the one-region scarcity states.</p>
<div class="controls"><label for="direction">Origin → destination<select id="direction"></select></label><label for="quarter">Delivery quarter<select id="quarter"></select></label><span class="selection-label" id="selectedRoute"></span></div>
<div class="metrics" aria-live="polite">{dynamic_metric('Total spread · AUD/MWh','totalValue','Destination minus origin')}{dynamic_metric('Capped energy · AUD/MWh','energyValue','Difference of min(price, $300)')}{dynamic_metric('Scarcity excess · AUD/MWh','scarcityValue','Difference of $300 cap payouts')}{dynamic_metric('Realised spread value · AUD/MW-quarter','quarterValue','Delivery hours × total spread').replace('Delivery hours × total spread','<span id="hoursNote">Delivery hours × total spread</span>')}</div>
{figure_html('<div id="historyChart" class="plot" role="img" aria-label="Quarterly capped energy and scarcity components with total price spread"></div>','Exhibit 1: The composition of spread value changes across quarters',history_note)}
<p id="historyInsight" class="exhibit-insight" aria-live="polite"></p>
<h3>Which regions exceeded $300 during the selected quarter?</h3><p class="small-note">Contributions below use all quarter hours as the denominator, so each column adds to its quarterly average. They are not conditional average prices during the state.</p>
<div class="table-wrap" tabindex="0" role="region" aria-label="Joint price-state decomposition"><table class="numeric-table"><thead><tr><th scope="col">Regions above $300</th><th scope="col">Hours</th><th scope="col">Frequency</th><th scope="col">Energy<br>AUD/MWh</th><th scope="col">Scarcity<br>AUD/MWh</th><th scope="col">Total<br>AUD/MWh</th></tr></thead><tbody id="regimeBody"></tbody></table></div><p class="identity" id="identityCheck"></p>
{figure_html('<div id="regimeChart" class="plot" role="img" aria-label="Quarterly price spread contribution from four joint regional scarcity states"></div>','Exhibit 2: The same total spread can come from very different joint price states','The four state contributions sum to the quarterly spread. Destination-only and origin-only labels follow the selected trade direction; reversing the trade swaps those states and changes the contribution sign.')}
<details class="primer"><summary>Why “prices below $300” needs a precise definition</summary><p>A price of $1,000 decomposes into $300 of capped energy and $700 of scarcity excess. Averaging only observations below $300 drops the other intervals and will not reproduce base-minus-cap exposure. Negative prices remain in energy. The threshold is a financial definition, not proof of physical capacity shortage.</p><p>Read <a href="#chapter-3">chapter 3</a> for payoff identities and <a href="#chapter-4">chapter 4</a> for coverage, partial-quarter treatment and the cost of averaging prices before calculating caps.</p></details></section>
<section id="eventExplorer" class="exhibit-section"><div class="section-kicker">Interactive exhibit 02 · tail behaviour</div><h2>Scarcity frequency, severity and concentration explain different risks</h2><p class="section-dek">A cap payout is the fraction of time above $300 multiplied by the mean excess during those intervals. Episode persistence and coincidence with the neighbouring region then determine the interregional exposure.</p>
<div class="controls"><label for="region">Region<select id="region"><option value="NSW1">New South Wales</option><option value="QLD1">Queensland</option><option value="SA1" selected>South Australia</option><option value="VIC1">Victoria</option></select></label><label for="eventQuarter">Delivery quarter<select id="eventQuarter"></select></label></div>
<div class="metrics" aria-live="polite">{dynamic_metric('Time above $300','eventHours','Total five-minute exceedance hours')}{dynamic_metric('Mean excess during scarcity','eventSeverity','AUD/MWh above the $300 strike')}{dynamic_metric('Quarterly cap payout','eventCap','AUD/MWh across all quarter hours')}{dynamic_metric('Top five days’ share of cap payout','eventConcentration','Concentration of quarterly tail value')}</div>
{figure_html('<div id="eventChart" class="plot" role="img" aria-label="Quarterly hours above 300 dollars and regional cap payout"></div>','Exhibit 3: More scarcity hours do not necessarily mean a more valuable cap','Source: archived project five-minute prices. Left axis: exceedance hours. Right axis: cap payout, AUD/MWh. The metrics refer to the selected quarter; the chart shows the full complete-quarter history.')}
<p class="exhibit-insight" id="eventIdentity" aria-live="polite"></p>
<div class="visual-grid">
{figure_html('<div id="scarcityMap" class="plot compact-plot" role="img" aria-label="Scarcity frequency versus conditional severity by region and quarter"></div>','Exhibit 4: Frequency and severity are separate dimensions of cap value','Each point is one region-quarter. Bubble area reflects realised cap payout. Hover to see episodes and the share of payout concentrated in the five largest days.')}
{figure_html('<div id="concentrationChart" class="plot compact-plot" role="img" aria-label="Heatmap of the share of regional cap payout concentrated in the five largest days"></div>','Exhibit 5: A few days often dominate the quarter','Top-five-day concentration is shown only where a positive cap payout exists. High concentration raises sampling and scenario-generation risk even when total exceedance hours look adequate.')}
</div>
<p class="small-note">These are observed frequencies, not quarterly forecasts. Heat or cold, low renewable output, outages, storage depletion, binding constraints and rebidding can combine to trigger separation. See <a href="#chapter-7">chapter 7</a> for the trigger framework and <a href="#chapter-12">chapter 12</a> for occurrence, duration and severity models.</p></section>
<section id="valuationLab" class="exhibit-section"><div class="section-kicker">Interactive exhibit 03 · assumptions workbench</div><h2>Translate market quotes into a testable valuation thesis <span class="lab-badge">Illustrative inputs</span></h2><p class="section-dek">Change the inputs to explore the accounting and assumptions. The starting numbers are hypothetical; this workbench is not connected to a market feed. Use aligned delivery periods, quote timestamps, contract definitions and currency.</p>
<div class="lab-grid"><div class="input-panel"><h3>Base and cap futures · AUD/MWh</h3><div class="inputs">
{field('baseA','Origin A · base future',76,'.1')}{field('baseB','Destination B · base future',110,'.1')}{field('capA','Origin A · $300 cap',9,'.1',0)}{field('capB','Destination B · $300 cap',25,'.1',0)}{field('deliveryHours','Quarter delivery hours',2208,'1',1)}{field('physicalSpread','Physical model · expected spread',39,'.1')}
</div><p class="input-help">Terminal values exclude variation margin funding and transaction costs. The physical expectation is a user assumption, not an output from an estimated model.</p></div>
<div class="input-panel"><h3>What scarcity hours would fit the destination cap?</h3><div class="inputs">{field('severity','Assumed mean excess · AUD/MWh',2000,'100',1)}{field('rho','Multiplicative risk loading ρ',.25,'.05',-.99)}</div><p class="input-help">Assumption: cap price = (1 + ρ) × expected physical cap payout. This is one sensitivity convention; risk premia need not follow it. The mean excess is above $300, not the full spike price.</p><div class="worked-output"><strong id="impliedHours"></strong><p id="scarcityInference"></p></div><p class="warning" id="infeasibleWarning" hidden>The inputs require more scarcity hours than the quarter contains. This combination of severity and risk loading is infeasible.</p></div></div>
<p class="warning" id="calcError" hidden>Please enter finite numeric inputs. Caps, purchase price, distributions and costs must be nonnegative; quarter hours and severity must be positive, and ρ must exceed −1.</p>
<div class="metrics" aria-live="polite">{dynamic_metric('Market total spread','marketTotal','B base − A base · AUD/MWh')}{dynamic_metric('Market capped-energy spread','marketEnergy','Base spread − cap spread · AUD/MWh')}{dynamic_metric('Market scarcity-excess spread','marketScarcity','B cap − A cap · AUD/MWh')}{dynamic_metric('Physical expectation minus quote','marketEdge','Before costs and risk adjustment · AUD/MWh')}</div><p class="small-note" id="longShort"></p>
{figure_html('<div id="impliedChart" class="plot" role="img" aria-label="Scarcity hours consistent with different conditional severity assumptions"></div>','Exhibit 6: The same cap price can support many frequency–severity combinations','Illustrative sensitivity, not an estimated market probability. Logarithmic severity axis. Changes in severity, risk loading or the scenario distribution alter the inference. The curve does not identify duration, coincidence, import availability or an SRA payout.')}
{figure_html('<div id="payoffChart" class="plot" role="img" aria-label="Illustrative base spread, cap spread and capped-energy spread payoffs across destination prices"></div>','Exhibit 7: Base spread equals capped-energy spread plus scarcity spread in every scenario','The origin spot price is fixed at the illustrative origin input while the destination spot price varies. This is a payoff identity, not a price forecast; forward quotes only set the valuation reference shown in the workbench above.')}
<details class="primer"><summary>Why SRA prices require a separate bridge</summary><p>Regional futures settle a time-weighted price difference. SRA units receive an entitlement to allocated residue under effective rules. Flow, losses, settlement aggregation, negative residues, unit entitlements and loop allocation intervene. A dollar-per-unit SRA quote cannot be subtracted from a dollar-per-MWh futures spread.</p><p>The calculator below accepts a scenario model’s expected discounted distribution. It does not manufacture that value from average flow or the futures inputs above. See <a href="#chapter-5">chapter 5</a> for settlement and <a href="#chapter-14">chapter 14</a> for the comparison framework.</p></details>
<div class="lab-grid"><div class="input-panel"><h3>SRA value bridge · AUD per unit</h3><div class="inputs">{field('unitPrice','Unit purchase price',10000,'100',0)}{field('unitMean','Expected discounted distributions',11600,'100',0)}{field('unitFees','Additional costs, not already deducted',150,'10',0)}{field('hurdle','Risk / uncertainty valuation reserve',800,'100')}</div></div><div class="input-panel"><h3>Residual model value after the reserve</h3><div class="worked-output"><strong id="unitEdge"></strong><p id="unitBridge"></p></div><p class="input-help">All four SRA inputs are illustrative. Discount purchase instalments consistently if their timing is material. A positive result alone does not establish an executable opportunity or an adequate portfolio hedge.</p></div></div>
<div class="controls"><button id="resetInputs">Reset illustrative assumptions</button><span class="small-note">All calculations run locally in this HTML file.</span></div></section>
<section id="visualAtlas" class="exhibit-section"><div class="section-kicker">Visual framework · from evidence to valuation</div><h2>See the complete chain from physical triggers to contract value</h2><p class="section-dek">These exhibits connect the historical decompositions to the proposed quarterly model. They separate what is observed, what must be simulated jointly, and what each contract actually settles.</p>
<div class="controls"><label for="heatMetric">Heatmap measure<select id="heatMetric"><option value="spread">Total spread</option><option value="energy">Capped energy</option><option value="scarcity">Scarcity excess</option><option value="scarcity_share">Scarcity share of absolute components</option></select></label><span class="selection-label">Complete quarters · canonical signed directions</span></div>
{figure_html('<div id="spreadHeatmap" class="plot" role="img" aria-label="Heatmap of quarterly spread, energy or scarcity values by canonical direction"></div>','Exhibit 8: Value composition changes across both direction and quarter','Canonical signs are NSW minus VIC, QLD minus NSW and SA minus VIC. For scarcity share, the denominator is absolute energy plus absolute scarcity so offsetting components do not create misleading percentages.')}
{figure_html('<div id="flowBridge" class="plot" role="img" aria-label="Flow times positive spread decomposition into independence approximation and covariance"></div>','Exhibit 9: Flow–spread covariance is often a large part of the gross revenue proxy','For each physical direction, mean(flow × positive spread) equals mean(flow) × mean(positive spread) plus covariance. This diagnostic omits losses and contractual allocation, so it is not an SRA valuation. It shows why average flow and average spread cannot be multiplied mechanically.')}
<div id="triggerMap" class="mechanism-panel" aria-labelledby="triggerMapTitle"><div class="diagram-caption"><span id="triggerMapTitle">Exhibit 10: Trigger pathways must preserve timing and dependence</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Issue-known drivers</h3><span>Demand and weather paths</span><span>Wind, solar and hydro availability</span><span>Generation and network outages</span><span>Storage state and endurance</span></div><div class="flow-arrow" aria-hidden="true">→</div>
<div class="mechanism-column"><h3>System state</h3><span>Accessible reserve margin</span><span>Import headroom and losses</span><span>Constraint / loop regime</span><span>Bid and rebid response</span></div><div class="flow-arrow" aria-hidden="true">→</div>
<div class="mechanism-column"><h3>Joint outcomes</h3><span>Regional price paths</span><span>Scarcity occurrence and duration</span><span>Interconnector flow paths</span><span>Joint tail dependence</span></div><div class="flow-arrow" aria-hidden="true">→</div>
<div class="mechanism-column contract-column"><h3>Settlement layer</h3><span>Base and cap futures</span><span>Directional residue</span><span>Fees, losses and loop allocation</span><span>Portfolio cashflows</span></div></div><p class="figure-note">A trigger can raise one regional price, both regional prices, or neither spread materially. Its value depends on coincidence with transfer availability and the contract settlement mapping.</p></div>
<div id="modelArchitecture" class="mechanism-panel" aria-labelledby="architectureTitle"><div class="diagram-caption"><span id="architectureTitle">Exhibit 11: Recommended five-layer valuation architecture</span></div><div class="architecture-flow"><article><b>01</b><h3>Information set</h3><p>Freeze forecasts, outages, quotes and effective rules at the valuation timestamp.</p></article><article><b>02</b><h3>Joint scenarios</h3><p>Generate weather, demand, renewables, availability, storage and network states together.</p></article><article><b>03</b><h3>Price and flow</h3><p>Clear feasible regional outcomes with constraints, losses and tail dependence.</p></article><article><b>04</b><h3>Contract settlement</h3><p>Calculate base, cap and SRA cashflows under the effective product rules.</p></article><article><b>05</b><h3>Decision layer</h3><p>Compare physical and market distributions after costs, liquidity and portfolio risk.</p></article></div><p class="figure-note">Each layer has a different validation target. Good flow MAE does not establish good scarcity probability, and neither establishes correct SRA settlement.</p></div>
<div id="implementationRoadmap" class="mechanism-panel" aria-labelledby="roadmapTitle"><div class="diagram-caption"><span id="roadmapTitle">Exhibit 12: Build evidence in the order that reduces valuation error</span></div><ol class="roadmap"><li><b>Ledger</b><span>Reconcile five-minute prices, cap identities and SRA settlement cashflows.</span></li><li><b>Baselines</b><span>Freeze seasonal and fundamentals-only forecasts with issue-time controls.</span></li><li><b>Tails</b><span>Add occurrence, duration, severity, storage and network regimes.</span></li><li><b>Market calibration</b><span>Join dated base, cap and SRA quotes without collapsing physical and pricing distributions.</span></li><li><b>Prospective test</b><span>Run untouched quarters and evaluate payoff error, hedge error and decision value.</span></li></ol></div></section>
<div class="reading-intro" id="fullResearch"><div><div class="section-kicker">The full research document</div><h2>From market mechanics to an implementable model</h2></div><div class="reading-actions"><button id="expandChapters">Expand all</button><button id="collapseChapters">Collapse all</button></div></div>
<p class="small-note">26 chapters and appendices · 32 external references · complete methodology, literature synthesis, data design, validation and implementation programme. Click any chapter title to fold it; use the reading guide to jump to a topic.</p>
<div class="reading-layout"><article class="research-body">{research_html}</article><aside class="research-rail" aria-label="Research navigation"><div class="rail-label">Reading guide</div><label class="sr-only" for="reportSearch">Search the full research by topic</label><input id="reportSearch" type="search" placeholder="Find a topic, e.g. entropy" autocomplete="off"><div id="searchResults" aria-live="polite"></div><nav class="toc">{''.join(f'<a href="#{ident}">{escape(title)}</a>' for ident,title in toc)}</nav></aside></div>
<section class="downloads" id="downloads"><h2>Research data and reproducibility</h2><p class="small-note">The report, charts and calculators work offline. These downloads are embedded in the HTML. CSVs include partial quarters flagged in the data; the interactive historical exhibits use complete quarters only.</p><div class="download-grid">
{embedded_download('historical_spread_decomposition.csv','Quarterly spread components')}{embedded_download('historical_regional_decomposition.csv','Regional energy and scarcity')}{embedded_download('historical_joint_regimes.csv','Joint price-state contributions')}{embedded_download('historical_flow_diagnostics.csv','Flow diagnostic — not SRA settlement')}{embedded_download('historical_audit.json','Coverage and input hashes')}{embedded_download('research_report.md','Full research text and sources')}
</div></section><footer class="footer"><span>IC Flow Forecasting · Electricity Research<br>Research cutoff: 18 September 2026 · Historical archive through 31 August 2026 NEM time</span><span>Original research synthesis and presentation.<br>Independent report; no affiliation with the issuers of the supplied style references.</span></footer><a class="back-top" href="#top" aria-label="Back to top">↑ Top</a>
<noscript><p class="warning">JavaScript is disabled. The complete research remains readable below; enable JavaScript for charts and calculators.</p></noscript>
'''

template=go.Figure();style_plotly(template,'')
base_layout=template.to_plotly_json()['layout'];base_layout.pop('template',None)
data_json=json.dumps(DATA,ensure_ascii=False,allow_nan=False).replace('</','<\\/')
runtime=f'<script>const DATA={data_json};const BASE_LAYOUT={json.dumps(base_layout)};</script><script>'+(ROOT/'report_interactions.js').read_text(encoding='utf-8')+'</script>'
html=render_page('Quarterly interregional valuation | IC Flow Forecasting',body,plotly=True,accent='blue')
html=html.replace('</head>','<style>'+ (ROOT/'institutional.css').read_text(encoding='utf-8')+'</style></head>')
html=html.replace('</body>',runtime+'</body>')
out=ROOT/'Quarterly_Interregional_Valuation_Research.html'
out.write_text(html,encoding='utf-8')
inputs=['research_report.md','historical_audit.json','historical_spread_decomposition.csv','historical_regional_decomposition.csv','historical_joint_regimes.csv','historical_flow_diagnostics.csv','report_theme.py','report.css','institutional.css','report_interactions.js','convert_markdown.mjs','build_html.py']+embedded_figures
manifest={
    'research_cutoff':'2026-09-18','historical_end_inclusive':'2026-09-01 00:00:00 UTC+10',
    'presentation_built_utc':datetime.now(timezone.utc).isoformat(),'output':out.name,
    'theme':'editorial-html-report/1.0, locally adapted to the two supplied institutional research PDF references',
    'sources_count':32,'chapters_count':len(chapters),'complete_quarters':sorted({r['quarter'] for r in DATA['spreads'] if r['complete']}),
    'dependencies':{'python':'3.x','plotly':plotly.__version__,'beautifulsoup4':'installed','node':args.node,'marked':args.marked},
    'rebuild':'python build_html.py [--node PATH_TO_NODE --marked PATH_TO_MARKED_ESM]',
    'data_rebuild':'python analyse_history.py (requires pandas, pyarrow and archived project inputs)',
    'inputs_sha256':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in inputs},
    'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
    'notes':['No market data refreshed during presentation build.','Nine interactive charts, three explanatory diagrams, scripts, styles and downloads are embedded. External references require internet access.','Historical data are descriptive, not a forecast or an independently reconciled exchange settlement series.']
}
(ROOT/'report_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'output':str(out),'bytes':out.stat().st_size,'chapters':len(chapters),'source_entries':len(BeautifulSoup(research_html,'html.parser').select('.source-entry'))}),flush=True)
