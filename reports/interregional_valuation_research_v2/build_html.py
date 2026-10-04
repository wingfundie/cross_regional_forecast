"""Build the offline v2 report from frozen evidence.

1. Render research_report.template.md -> research_report.md (v1 includes + {{numbers}} from
   evidence/headline_numbers.json; the build fails on any unfilled placeholder).
2. Markdown -> HTML with server-side KaTeX (convert_markdown.mjs, pinned in tools/).
3. Embed Plotly, KaTeX CSS with base64 fonts, both datasets (full window and v1 window),
   the 27 new exhibits (charts.py) and evidence downloads. No network access at view time.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import plotly
import plotly.graph_objects as go
from bs4 import BeautifulSoup, NavigableString

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from report_theme import hero, metric, figure_html, style_plotly, render_page  # noqa: E402
import charts  # noqa: E402

V1 = ROOT / 'reports/interregional_valuation_research_20260918'
parser = argparse.ArgumentParser()
parser.add_argument('--node', default=shutil.which('node') or str(Path.home() / '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'))
args = parser.parse_args()


def sha(p: Path) -> str:
    b = p.read_bytes()
    if p.suffix.lower() in {'.py', '.md', '.json', '.csv', '.js', '.mjs', '.cjs', '.css', '.txt', '.html'}:
        b = b.replace(b'\r\n', b'\n')
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------ 1. render the report text
from nemic.valuation import summary  # noqa: E402
N = summary.write()
v1 = (V1 / 'research_report.md').read_text(encoding='utf-8')


def v1_section(heading: str) -> str:
    i = v1.index(heading + '\n')
    j = v1.find('\n## ', i + len(heading))
    return v1[i + len(heading):j if j > 0 else None].strip('\n')


def include(m):
    body = v1_section(m.group(1))
    body = body.replace('![Figure 1 Quarterly spread decomposition](figures/quarterly_spreads.png)', '')
    return (m.group(2) + '\n\n' if m.group(2) else '') + body


tpl = (HERE / 'research_report.template.md').read_text(encoding='utf-8')
md = re.sub(r'\{\{include_v1 "([^"]+)" "([^"]*)"\}\}', include, tpl)
missing = sorted(set(re.findall(r'\{\{([a-zA-Z0-9_]+)\}\}', md)) - set(N))
if missing:
    raise SystemExit(f'Unfilled placeholders: {missing}')
md = re.sub(r'\{\{([a-zA-Z0-9_]+)\}\}', lambda m: str(N[m.group(1)]), md)
(HERE / 'research_report.md').write_text(md, encoding='utf-8', newline='\n')
print('Report text rendered:', len(md), 'characters;', len(N), 'numbers', flush=True)

# ------------------------------------------------------------------ 2. markdown + KaTeX
proc = subprocess.run([args.node, str(HERE / 'convert_markdown.mjs'), str(HERE / 'research_report.md')], capture_output=True, text=True, encoding='utf-8')
if proc.returncode:
    raise SystemExit(proc.stderr)
math_count = json.loads(proc.stderr.strip().splitlines()[-1])['math']
soup = BeautifulSoup(proc.stdout, 'html.parser')
if soup.h1:
    soup.h1.decompose()
toc = []
for i, h in enumerate(soup.find_all('h2')):
    h['id'] = 'chapter-' + str(i); toc.append((h['id'], h.get_text()))
for i, h in enumerate(soup.find_all('h3')):
    h['id'] = 'subsection-' + str(i)
for p in soup.find_all('p'):
    m = re.match(r'^\[([SLR]\d{2})\]', p.get_text())
    if m:
        p['id'] = 'source-' + m.group(1); p['class'] = 'source-entry'
for node in list(soup.find_all(string=True)):
    if node.parent.name in ('a', 'code', 'pre', 'script', 'style', 'annotation') or node.find_parent(class_='katex'):
        continue
    if node.parent.get('class') == ['source-entry']:
        continue
    ms = list(re.finditer(r'\[([SLR]\d{2})((?:(?:[–-]|, )[SLR]?\d{2})*)\]', str(node)))
    if not ms:
        continue
    start = 0
    for m in ms:
        node.insert_before(NavigableString(str(node)[start:m.start()]))
        a = soup.new_tag('a', href='#source-' + m.group(1)); a['class'] = 'citation'; a.string = m.group(0)
        node.insert_before(a); start = m.end()
    node.insert_before(NavigableString(str(node)[start:])); node.extract()
for table in soup.find_all('table'):
    table.wrap(soup.new_tag('div', attrs={'class': 'table-wrap', 'tabindex': '0', 'role': 'region', 'aria-label': 'Research table'}))
embedded_figures = []
for img in soup.find_all('img', src=True):
    src = (HERE / img['src']).resolve()
    embedded_figures.append(src.relative_to(HERE).as_posix())
    img['src'] = 'data:image/png;base64,' + base64.b64encode(src.read_bytes()).decode(); img['loading'] = 'lazy'
for a in soup.find_all('a', href=True):
    if a['href'].startswith('https://'):
        a['target'] = '_blank'; a['rel'] = 'noopener noreferrer'
chapters, content = [], None
for child in list(soup.contents):
    if getattr(child, 'name', None) == 'h2':
        det = soup.new_tag('details', attrs={'class': 'chapter', 'open': ''})
        summ = soup.new_tag('summary'); summ.append(child.extract()); det.append(summ)
        content = soup.new_tag('div', attrs={'class': 'chapter-content'}); det.append(content); chapters.append(det)
    elif content is not None:
        content.append(child.extract())
research_html = ''.join(str(c) for c in chapters)
print('Research converted:', len(chapters), 'chapters,', math_count, 'KaTeX formulas', flush=True)

# KaTeX stylesheet with woff2 fonts inlined
kdir = HERE / 'tools/node_modules/katex/dist'
kcss = (kdir / 'katex.min.css').read_text(encoding='utf-8')


def font_face(m):
    block = m.group(0)
    w = re.search(r'url\((fonts/[^)]+\.woff2)\)', block)
    if not w:
        return block
    data = base64.b64encode((kdir / w.group(1)).read_bytes()).decode()
    return re.sub(r'src:[^;}]+', f'src:url(data:font/woff2;base64,{data}) format("woff2")', block)


kcss = re.sub(r'@font-face\{[^}]+\}', font_face, kcss)
assert 'url(fonts/' not in kcss

# ------------------------------------------------------------------ 3. data and exhibits
import csv  # noqa: E402


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


EV = HERE / 'evidence'
DATA = {'spreads': load_csv(EV / 'spread_decomposition.csv'), 'regions': load_csv(EV / 'regional_decomposition.csv'),
        'regimes': load_csv(EV / 'joint_regimes.csv'), 'flows': load_csv(EV / 'flow_diagnostics_full.csv')}
DATA_V1 = {'spreads': load_csv(V1 / 'historical_spread_decomposition.csv'), 'regions': load_csv(V1 / 'historical_regional_decomposition.csv'),
           'regimes': load_csv(V1 / 'historical_joint_regimes.csv'), 'flows': load_csv(EV / 'flow_diagnostics_v1window.csv')}
for d in (DATA, DATA_V1):
    assert all(abs(r['spread'] - r['energy'] - r['scarcity']) < 1e-3 for r in d['spreads'])
NEW = charts.all_charts()
sections = {
    'ledger': ('Realised SRA payoffs', 'Settled residue, not a proxy: what units actually paid', 'chapter-6'),
    'auctions': ('Auction prices against realised payoffs', 'Were SRA units cheap?', 'chapter-7'),
    'hedging': ('SRA units against futures spreads', 'What one unit hedges, and when it fails', 'chapter-8'),
    'futures': ('Futures premia (AER public data)', 'The missing leg', 'chapter-8'),
    'loss': ('Loss-driven and congestion-driven spread', 'The part of a spread an SRA only half earns', 'chapter-10'),
    'evidence': ('Extended evidence base', 'Nineteen quarters and Basslink', 'chapter-4'),
    'uncertainty': ('Uncertainty and dependence', 'One quarter is one draw', 'chapter-4'),
    'counterprice': ('Mechanisms', 'Counter-price flow, constraints and outage plans', 'chapter-11'),
    'loop': ('The loop rule applied to history', 'Who is paid after November 2026', 'chapter-12'),
    'settings': ('Market settings and time of day', 'Cap levels and diurnal structure', 'chapter-13'),
    'valuation': ('Valuation benchmarks', 'Forecasts, option benchmark and measured sensitivities', 'chapter-14'),
    'microstructure': ('Auction microstructure', 'Bid stacks and demand', 'chapter-15'),
    'strategic': ('Strategic behaviour pilot', 'Offer-curve steepness at interconnector limits', 'chapter-16'),
}
chart_by_section = {}
for c in NEW:
    chart_by_section.setdefault(c['section'], []).append(c)
download_names = sorted({c['csv'] for c in NEW} | {'spread_decomposition.csv', 'regional_decomposition.csv', 'joint_regimes.csv', 'flow_diagnostics_full.csv',
                                                    'sra_unit_registry.csv', 'sra_reconciliation.csv', 'data_audit.json', 'scenario_registry.json', 'headline_numbers.json'})


def chart_block(c):
    link = f'<span class="figure-links"><a href="#dl-{escape(c["csv"].replace(".", "-"))}">Data ↓</a></span>'
    return (f'<figure id="fig-{c["id"]}"><figcaption><span>{escape(c["title"])}</span>{link}</figcaption>'
            f'<div class="chart-scroll"><div id="{c["id"]}" class="plot" role="img" aria-label="{escape(c["title"])}"></div></div>'
            f'<p class="figure-note">{escape(c["note"])}</p></figure>')


new_sections = []
for key, (kicker, title, chap) in sections.items():
    cs = chart_by_section.get(key, [])
    if not cs:
        continue
    new_sections.append(f'<section id="v2-{key}" class="exhibit-section"><div class="section-kicker">Version 2 evidence · {escape(kicker)}</div>'
                        f'<h2>{escape(title)}</h2><p class="section-dek">Method, formulas and caveats: <a href="#{chap}">the corresponding chapter</a>.</p>'
                        + ''.join(chart_block(c) for c in cs) + '</section>')
new_html = ''.join(new_sections)

diagrams = '''
<div id="settlementPipeline" class="mechanism-panel"><div class="diagram-caption"><span>Exhibit D4: From dispatch to a unit payoff (pre-loop)</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>Per asset, per interval</h3><span>Metered energy at each regional reference node</span><span>Losses split by FROMREGIONLOSSSHARE</span><span>Residue r = P<sub>to</sub>·flow in − P<sub>from</sub>·flow out</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Directional pooling</h3><span>VNI · QNI + Terranora · Heywood + Murraylink</span><span>Direction from net flow</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>Sign treatment</h3><span>Positive → SRA pool</span><span>Negative → importing-region TNSP (NER 3.6.5)</span><span>NRM clamps at −$100k accumulated</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>Unit cashflow</h3><span>Pool × unit proportion</span><span>Less fees; price paid on calendar date</span><span>Weekly distributions</span></div></div>
<p class="figure-note">AEMO publishes the settled result per interconnector and region as SETIRSURPLUS; version 2 reconciles its engine to that table and uses it for realised payoffs.</p></div>
<div id="loopAllocation" class="mechanism-panel"><div class="diagram-caption"><span>Exhibit D5: Loop settlement by net trade (from November 2026)</span></div><div class="mechanism-flow">
<div class="mechanism-column"><h3>1 · Allocations</h3><span>Existing methodology per arm</span><span>Net loop IRSR = sum of arms</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>2 · Net trade</h3><span>Regional net exports at the RRN</span><span>Trade on exporter → importer arms</span><span>Pass-through region carries none</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column"><h3>3 · Amounts</h3><span>Quantity × price difference</span><span>Scaled to the net loop IRSR</span></div><div class="flow-arrow">→</div>
<div class="mechanism-column contract-column"><h3>4 · Secondary netting</h3><span>Negative arm netted from positive arm</span><span>Units never pay; net-negative loops recovered from networks</span></div></div>
<p class="figure-note">AEMC ERC0386 final rule. Tested in tests/test_valuation_settlement.py against the determination's Figure 3.1 and Example 4.</p></div>'''


def embedded_download(name: str) -> str:
    p = EV / name
    mime = 'text/csv' if name.endswith('.csv') else 'application/json'
    return f'<a id="dl-{escape(name.replace(".", "-"))}" href="data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}" download="{escape(name)}">{escape(name)} ↓</a>'


def field(id_, label, value, step='1', minimum=None):
    lo = f' min="{minimum}"' if minimum is not None else ''
    return f'<label for="{id_}">{label}<input id="{id_}" type="number" value="{value}" step="{step}"{lo}></label>'


def dyn(label, id_, note):
    return metric(label, '—', note).replace('<strong>', f'<strong id="{id_}">')


v1_body = (V1 / 'build_html.py').read_text(encoding='utf-8')
# ------------------------------------------------------------------ page body
hl = N
body = f'''
<div id="top" class="masthead"><div class="brand"><strong>IC Flow<br>Forecasting</strong><span>Electricity<br>Research</span></div><div class="dateline">Version 2 · 26 September 2026<br>Australian National Electricity Market</div></div>
<div class="hero-band">{hero('Interregional Strategy', 'Valuing interregional spreads and SRA units:', 'what settlement residue units paid, and what they hedge', '', [])}</div>
<nav class="topnav" aria-label="Report shortcuts"><a href="#v2-auctions">Auctions vs realised</a><a href="#v2-hedging">Hedging</a><a href="#v2-loop">Loop rule</a><a href="#historicalExplorer">Historical evidence</a><a href="#valuationLab">Workbench</a><a href="#fullResearch">Full research</a><a href="#downloads">Data</a><button id="printReport">Print / save PDF</button></nav>
<div class="front"><div><ul class="summary-points">
<li><strong>Units paid {hl['auction_ratio']}× their price.</strong> Across {hl['auction_tranches']} settled tranches (Oct 2021 – Jun 2026), realised payoff ÷ clearing price, weighted by units sold, was {hl['auction_ratio']} (95% interval {hl['auction_ratio_lo']}–{hl['auction_ratio_hi']}). It rises from {hl['ratio_h12']} one to two quarters ahead to {hl['ratio_h912']} nine to twelve quarters ahead.</li>
<li><strong>The price is still the best forecast.</strong> At each auction the clearing price beat every history-based rule (mean absolute error {hl['wf_mae_market_clearing_price'].replace(chr(92), '')} per unit) but was biased low by {hl['wf_bias_market_clearing_price'].replace(chr(92), '')}: a premium, not ignorance.</li>
<li><strong>Hedge quality depends on direction.</strong> A VICNSW unit removed {hl['hedge_vr_VICNSW']} of the variance of a 1 MW NSW−VIC spread and paid {hl['hedge_ratio_top_VICNSW']} MW-equivalent in the ten worst weeks; VICSA removed {hl['hedge_vr_VICSA']} and QLDNSW {hl['hedge_vr_QLDNSW']}.</li>
<li><strong>The loop rule redistributes the pool.</strong> Applied to settled history, VICNSW's payout changes by {hl['loop_change_VICNSW']} and new NSW–SA categories take {hl['loop_new_categories'].replace(chr(92), '')}; Victoria is a pass-through region in {hl['loop_pass_through']} of intervals.</li>
</ul></div><aside class="research-note"><h3>Research brief</h3><p><strong>Evidence</strong><br>{hl['intervals']} five-minute intervals, {hl['complete_quarters']} complete quarters, AEMO-settled residues, every public SRA auction result and bid stack since 2021.</p><p><strong>New in version 2</strong><br>27 new exhibits, KaTeX-typeset formulas, a reconciled settlement ledger and a response to every review item (Appendix C).</p><p><strong>Not yet observed</strong><br>Futures and cap quotes: the AER blocks automated access; loaders are built.</p><p><strong>Status</strong><br>Research evidence, not a live trading signal.</p></aside></div>
{new_sections[0] if new_sections else ''}
'''
# keep version-1 interactive exhibits (history, events, workbench, atlas), adapted
v1_sections = re.search(r"<section id=\"historicalExplorer\".*?</div></section>\n<div class=\"reading-intro\"", v1_body, re.S).group(0)[:-len('\n<div class="reading-intro"')]
v1_sections = v1_sections.replace('<div class="controls"><label for="direction">',
                                  '<div class="controls"><label for="window">Evidence window<select id="window"><option value="full">Oct 2021 – Aug 2026 (v2)</option><option value="v1">Sep 2024 – Aug 2026 (v1)</option></select></label><label for="direction">', 1)
v1_sections = v1_sections.replace('<option value="VIC1">Victoria</option>', '<option value="VIC1">Victoria</option><option value="TAS1">Tasmania</option>')
v1_sections = v1_sections.replace("{field('deliveryHours','Quarter delivery hours',2208,'1',1)}{field('physicalSpread','Physical model · expected spread',39,'.1')}",
                                  "{field('deliveryHours','Quarter delivery hours',2160,'1',1)}{field('physicalSpread','Physical model · expected spread',30,'.1')}")
v1_sections = v1_sections.replace("{field('unitPrice','Unit purchase price',10000,'100',0)}{field('unitMean','Expected discounted distributions',11600,'100',0)}",
                                  "{field('unitPrice','Unit purchase price',15000,'100',0)}{field('unitMean','Expected discounted distributions',20000,'100',0)}")
v1_sections = v1_sections.replace('<p id="scarcityInference"></p></div>', '<p id="scarcityInference"></p><p id="spreadHours" class="small-note"></p></div>')
v1_sections = v1_sections.replace("'Exhibit 9: Flow–spread covariance is often a large part of the gross revenue proxy'", "'Exhibit 9: Flow–spread covariance, corrected for the gating artefact'")
v1_sections = v1_sections.replace("For each physical direction, mean(flow × positive spread) equals mean(flow) × mean(positive spread) plus covariance. This diagnostic omits losses and contractual allocation, so it is not an SRA valuation. It shows why average flow and average spread cannot be multiplied mechanically.",
                                  "Version 2 uses the ungated mean of positive flow; version 1 multiplied a flow already gated on a positive spread, which adds a mechanical positive covariance. Hover shows the Spearman correlation given a positive spread. Lossless and single-link: see Exhibits N1 and N10 for settled payoffs.")
v1_sections = v1_sections.replace("Source: archived project five-minute prices; complete quarters only, 2024 Q4–2026 Q2.", "Source: AEMO dispatch prices; complete quarters only; window selectable above.")
v1_sections = v1_sections.replace("Price archive has not been reconciled to all final exchange revisions.", "All complete-quarter intervals are PRICE_STATUS FIRM.")
# the v1 python f-string fragments need evaluating in this module's namespace
history_note = 'Source: AEMO dispatch prices; complete quarters only. Energy = min(price, 300); scarcity = max(price − 300, 0). Bar components sum algebraically.'
body_mid = v1_sections
# v1 sections contain f-string code: evaluate them with the helpers defined above
body_mid = eval("f'''" + body_mid.replace("'''", "\\'\\'\\'") + "'''", {**globals(), 'figure_html': figure_html, 'field': field, 'dynamic_metric': dyn, 'history_note': history_note})
body_mid = body_mid.replace('</section>\n<section id="visualAtlas"', '</section>\n<section id="visualAtlas"', 1)
atlas_close = body_mid.rfind('</section>')
body_mid = body_mid[:atlas_close] + diagrams + body_mid[atlas_close:]
body += body_mid + ''.join(new_sections[1:])
body += f'''
<div class="reading-intro" id="fullResearch"><div><div class="section-kicker">The full research document</div><h2>From settlement mechanics to a tested valuation</h2></div><div class="reading-actions"><button id="expandChapters">Expand all</button><button id="collapseChapters">Collapse all</button></div></div>
<p class="small-note">{len(chapters)} chapters and appendices · {math_count} typeset formulas · every number generated from evidence/headline_numbers.json.</p>
<div class="reading-layout"><article class="research-body">{research_html}</article><aside class="research-rail" aria-label="Research navigation"><div class="rail-label">Reading guide</div><label class="sr-only" for="reportSearch">Search the full research</label><input id="reportSearch" type="search" placeholder="Find a topic, e.g. loop" autocomplete="off"><div id="searchResults" aria-live="polite"></div><nav class="toc">{''.join(f'<a href="#{i}">{escape(t)}</a>' for i, t in toc)}</nav></aside></div>
<section class="downloads" id="downloads"><h2>Research data and reproducibility</h2><p class="small-note">Every exhibit's data are embedded below. Rebuild: <code>python -m nemic.valuation all</code> then <code>python build_html.py</code>.</p><div class="download-grid">{''.join(embedded_download(n) for n in download_names)}</div></section>
<footer class="footer"><span>IC Flow Forecasting · Electricity Research · Version 2<br>Evidence window Oct 2021 – Aug 2026, NEM time (UTC+10)</span><span>Research evidence; not a trading recommendation.</span></footer><a class="back-top" href="#top" aria-label="Back to top">↑ Top</a>
'''

template = go.Figure(); style_plotly(template, '')
base_layout = template.to_plotly_json()['layout']; base_layout.pop('template', None)
dj = lambda o: json.dumps(o, ensure_ascii=False, allow_nan=False, default=lambda x: None).replace('</', '<\\/')


def clean(o):
    if isinstance(o, float) and o != o:
        return None
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [clean(v) for v in o]
    return o


runtime = (f'<script>const DATA={dj(clean(DATA))};const DATA_V1={dj(clean(DATA_V1))};const BASE_LAYOUT={json.dumps(base_layout)};'
           f'const NEWCHARTS={dj(clean([{"id": c["id"], "fig": c["fig"]} for c in NEW]))};</script>'
           '<script>' + (HERE / 'report_interactions.js').read_text(encoding='utf-8') + '</script>')
html = render_page('Interregional valuation v2 | IC Flow Forecasting', body, plotly=True, accent='blue')
html = html.replace('</head>', '<style>' + kcss + '</style><style>' + (HERE / 'institutional.css').read_text(encoding='utf-8') +
                    '.math-display{overflow-x:auto;overflow-y:hidden;padding:.2rem 0}.katex .katex-mathml{left:0;top:0}.research-body,.front,.exhibit-section{overflow-x:clip}.research-body p,.research-body li{overflow-wrap:anywhere}@media(max-width:600px){.math-display .katex{font-size:.78em}}.katex{font-size:1.05em}.research-body table .katex{font-size:1em}</style></head>')
html = html.replace('</body>', runtime + '</body>')
out = HERE / 'Interregional_Valuation_Research_v2.html'
out.write_text(html, encoding='utf-8', newline='\n')
inputs = ['research_report.template.md', 'research_report.md', 'charts.py', 'build_html.py', 'make_figures.py', 'convert_markdown.mjs', 'report_interactions.js',
          'institutional.css', 'report.css', 'report_theme.py', 'tools/package.json', 'tools/package-lock.json'] + embedded_figures
manifest = {
    'version': 2, 'research_cutoff': '2026-09-26', 'evidence_window': 'interval ending after 2021-10-01 00:00 through 2026-09-01 00:00 UTC+10',
    'output': out.name, 'chapters': len(chapters), 'katex_formulas': math_count, 'new_exhibits': len(NEW), 'v1_exhibits_retained': 12,
    'hash_convention': 'SHA-256 of file bytes with CRLF normalised to LF for text files',
    'inputs_sha256': {n: sha(HERE / n) for n in inputs},
    'evidence_sha256': {p.name: sha(p) for p in sorted(EV.glob('*')) if p.is_file()},
    'code_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted((ROOT / 'nemic/valuation').glob('*.py'))},
    'output_sha256': sha(out),
    'dependencies': {'plotly': plotly.__version__, 'katex': '0.16.22', 'marked': '15.0.12', 'node': args.node},
    'futures': json.loads((EV / 'futures_status.json').read_text()),
}
(HERE / 'report_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8', newline='\n')
print(json.dumps({'output': str(out), 'bytes': out.stat().st_size, 'chapters': len(chapters), 'math': math_count, 'new_charts': len(NEW)}), flush=True)
