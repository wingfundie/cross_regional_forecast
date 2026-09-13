"""Build an offline documentation handbook without loading data or models."""
from pathlib import Path
import hashlib
import html
import json
import re
import markdown
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    ('overview', 'README.md', 'Overview'),
    ('results', 'BACKTEST_REPORT.md', 'Executed results'),
    ('features', 'docs/RESULTS_DATA_AND_FEATURES.md', 'Results, data and features'),
    ('methods', 'docs/METHODS_AND_RESEARCH.md', 'Methods and research'),
    ('backtest', 'docs/BACKTEST_PROTOCOL.md', 'Backtest protocol'),
    ('roadmap', 'docs/IMPROVEMENT_ROADMAP.md', 'Improvement roadmap'),
    ('constraint-features', 'docs/CONSTRAINT_NETWORK_FEATURES.md', 'Constraint-derived network features'),
    ('constraint-pilot', 'docs/CONSTRAINT_FEATURE_PILOT.md', 'Executed VNI constraint-feature pilot'),
    ('vni-influence', 'docs/VNI_GENERATOR_INFLUENCE_STUDY.md', 'VNI generator influence study'),
    ('vni-two-year', 'docs/VNI_TWO_YEAR_CONSTRAINT_STUDY.md', 'VNI two-year constraint study'),
    ('vni-event-atlas', 'docs/VNI_TWO_YEAR_EVENT_ATLAS.md', 'VNI event atlas'),
    ('event-methodology', 'docs/INTERCONNECTOR_EVENT_ANALYSIS_METHODOLOGY.md', 'Interconnector event methodology'),
    ('qni-influence', 'docs/QNI_GENERATOR_INFLUENCE_STUDY.md', 'QNI generator influence study'),
    ('qni-two-year', 'docs/QNI_TWO_YEAR_CONSTRAINT_STUDY.md', 'QNI two-year constraint study'),
    ('vsa-two-year', 'docs/VSA_TWO_YEAR_CONSTRAINT_STUDY.md', 'V-SA two-year constraint study'),
    ('vsa-event-atlas', 'docs/VSA_TWO_YEAR_EVENT_ATLAS.md', 'V-SA event atlas'),
    ('plan', 'BUILD_PLAN.md', 'Original build plan'),
]
CSS = '''
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f5f6fa;color:#202c43;font:16px/1.65 system-ui,sans-serif}
header{background:#142740;color:white;padding:52px max(24px,calc((100% - 1160px)/2))}header h1{font-size:clamp(32px,5vw,58px);line-height:1.1;margin:12px 0}header p{max-width:800px;color:#d2def0}
nav{display:flex;flex-wrap:wrap;gap:10px;padding:20px 0}nav a{color:white;border:1px solid #61768e;padding:7px 12px;border-radius:7px;text-decoration:none}
main{max-width:1210px;margin:auto;padding:24px}article{background:white;border:1px solid #dce2ed;border-radius:12px;margin:24px 0;padding:clamp(18px,4vw,44px);min-width:0}
h1,h2,h3{line-height:1.25;scroll-margin-top:20px}article h1{font-size:32px}h2{margin-top:36px;color:#264d84}a{color:#215ca0;overflow-wrap:anywhere}p,li{overflow-wrap:anywhere}
.table-wrap{overflow-x:auto;margin:24px 0}table{border-collapse:collapse;width:100%;font-size:14px;min-width:650px}th,td{text-align:left;vertical-align:top;border:1px solid #dce2ed;padding:11px}th{background:#eaf0f9}tr:nth-child(even){background:#f8faff}
pre{background:#edf1f7;padding:16px;overflow:auto;border-radius:6px}code{font-size:.9em}blockquote{border-left:4px solid #5980b5;margin-left:0;padding-left:18px}.source{font-size:13px;color:#63718a}.top{font-size:13px}
@media print{body{background:white}header{padding:20px}nav{display:none}main,article{padding:0;border:0}article{break-before:page}.table-wrap{overflow:visible}table{min-width:0;font-size:10px}a{color:inherit}}
'''

def result_charts():
    """Render a compact, committed results snapshot; never refit models."""
    snapshot = ROOT / 'docs/chart_data.json'
    frame = pd.DataFrame(json.loads(snapshot.read_text(encoding='utf-8'))['scores'])
    names = {'NSW1-QLD1':'QNI','N-Q-MNSP1':'Directlink','VIC1-NSW1':'VNI','V-SA':'Heywood','V-S-MNSP1':'Murraylink','T-V-MNSP1':'Basslink'}
    bands = ['0.5–6h','6.5–24h','24.5–72h','72.5–168h']
    blocks = []
    def add(fig, title, note):
        fig.update_layout(template='plotly_white', height=430, autosize=True,
            margin=dict(l=90,r=25,t=25,b=65), font=dict(family='Arial',size=12),
            paper_bgcolor='#ffffff',plot_bgcolor='#f3f5fb',
            legend=dict(orientation='h',y=-.22),hovermode='closest')
        chart = pio.to_html(fig, full_html=False, include_plotlyjs=True if not blocks else False,
            config={'responsive':True,'displaylogo':False}, div_id=f'chart-{len(blocks)+1}')
        blocks.append(f'<h2>{html.escape(title)}</h2>{chart}<p class="source">{html.escape(note)}</p>')
    flow = frame[frame.target.eq('flow')]
    base = flow[flow.model.eq('persistence')].set_index(['ic','band']).mae
    selected = flow[flow.model.eq('selected')].set_index(['ic','band']).mae
    delta = (base-selected).unstack('band').reindex(names)
    fig = go.Figure(go.Heatmap(z=delta.values,x=bands,y=list(names.values()),
        colorscale='RdBu',zmid=0,text=delta.round(1).values,texttemplate='%{text}',
        colorbar=dict(title='MW'),hovertemplate='%{y} · %{x}<br>MAE improvement: %{z:.1f} MW<extra></extra>'))
    add(fig,'01 · Flow forecast improvement versus persistence',
        'Persistence MAE minus selected P50 MAE, by connector and lead band. Positive values favour the selected forecast; negative values favour persistence. Each cell uses identical forecast pairs.')
    for target, label in [('export','Export'),('import','Import')]:
        fig = go.Figure()
        for ident,name in names.items():
            rows=frame[frame.target.eq(target)&frame.model.eq('selected')&frame.ic.eq(ident)].sort_values('band')
            fig.add_trace(go.Scatter(x=bands,y=rows.mae,mode='lines+markers',name=name))
        fig.update_yaxes(title='Mean absolute error (MW)',rangemode='tozero')
        add(fig,f'{len(blocks)+1:02d} · {label} limit errors by forecast horizon',
            'Average directional limit target; selected calibrated P50. MW errors are not normalised for connector size. Direction conventions are defined in the methods section.')
    chosen=frame[frame.model.eq('selected')].copy()
    chosen['covered']=chosen.coverage80*chosen.n
    grouped=chosen.groupby(['ic','band'])[['covered','n']].sum()
    coverage=(100*grouped.covered/grouped.n).unstack('band').reindex(names)
    fig=go.Figure(go.Heatmap(z=coverage.values,x=bands,y=list(names.values()),
        zmin=0,zmax=100,colorscale='Blues',text=coverage.round(1).values,texttemplate='%{text}%',
        colorbar=dict(title='%'),hovertemplate='%{y} · %{x}<br>Coverage: %{z:.1f}%<extra></extra>'))
    add(fig,'04 · Do the uncertainty intervals cover actual outcomes?',
        'Target coverage is 80%. Values aggregate all five targets using forecast-count weights. Overall coverage is 72.3%, so the intervals under-cover. Aggregation can hide target-specific weaknesses.')
    limits=chosen[chosen.target.isin(['export','import'])].groupby('ic')[['tp','fp','fn']].sum().reindex(names)
    fig=go.Figure()
    for label,values in [('Recall',100*limits.tp/(limits.tp+limits.fn)),('Precision',100*limits.tp/(limits.tp+limits.fp))]:
        fig.add_trace(go.Bar(x=list(names.values()),y=values,name=label))
    fig.update_layout(barmode='group');fig.update_yaxes(title='Percent',range=[0,100])
    add(fig,'05 · Restriction detection: misses and false alerts',
        'Pooled average import/export targets and all lead bands; TP/FP/FN counts are summed before calculating ratios. Recall measures restrictions caught; precision measures how often alerts were correct. Counts are forecast pairs, not distinct outage episodes.')
    return '<article id="charts"><h1>Backtest charts</h1><p>March–August 2026 test · six links · realised future inputs. Interactive figures use the saved completed-run scores. Hover for values; use the chart toolbar to export an image.</p>'+''.join(blocks)+'</article>'

def build():
    destination = ROOT / 'docs/html'
    destination.mkdir(parents=True, exist_ok=True)
    lookup = {(ROOT / path).resolve(): ident for ident, path, _ in PAGES}
    sections = []
    hashes = {}
    for ident, relative, title in PAGES:
        path = ROOT / relative
        text = path.read_text(encoding='utf-8')
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        rendered = markdown.markdown(text, extensions=['tables', 'fenced_code', 'toc'])
        anchors = re.findall(r' id="([^"]+)"', rendered)
        for anchor in anchors:
            rendered = rendered.replace(f'id="{anchor}"', f'id="{ident}-{anchor}"')
        def link(match):
            value = html.unescape(match.group(1))
            if value.startswith('#'):
                return f'href="#{ident}-{html.escape(value[1:], quote=True)}"'
            if '://' not in value:
                base, _, fragment = value.partition('#')
                target = (path.parent / base).resolve()
                if target in lookup:
                    prefix = lookup[target]
                    return f'href="#{prefix}' + (f'-{fragment}' if fragment else '') + '"'
                if target == destination / 'index.html':
                    return 'href="#top"'
                # The combined handbook is written under docs/html while
                # machine-readable snapshots live under docs/data.
                if base.startswith('data/'):
                    return f'href="../{html.escape(value, quote=True)}"'
                if base.startswith('html/'):
                    return f'href="{html.escape(value[5:], quote=True)}"'
            return match.group(0)
        rendered = re.sub(r'href="([^"]+)"', link, rendered)
        rendered = rendered.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')
        sections.append(f'<article id="{ident}"><p class="source">Source: {html.escape(relative)}</p>{rendered}<a class="top" href="#top">Back to navigation</a></article>')
    charts = result_charts()
    hashes['docs/chart_data.json'] = hashlib.sha256((ROOT/'docs/chart_data.json').read_bytes()).hexdigest()
    sections.insert(0, charts)
    nav = '<a href="#charts">Backtest charts</a>' + ''.join(f'<a href="#{i}">{html.escape(t)}</a>' for i, _, t in PAGES)
    document = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>INTERFLOW — Research handbook</title><style>{CSS}</style></head><body><header id="top"><span>NEM · INTERCONNECTOR FORECASTING</span><h1>INTERFLOW<br>Research handbook</h1><p>Methods, evidence and next experiments for six interconnectors. Historical data ends 1 September 2026 (interval-ending NEM time). The completed backtest uses realised future inputs and does not establish operational forecast accuracy.</p><nav>{nav}</nav></header><main>{''.join(sections)}</main></body></html>'''
    (destination / 'index.html').write_text(document, encoding='utf-8')
    manifest = {'inputs_sha256': hashes, 'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'markdown_version': markdown.__version__, 'command': 'python scripts/build_docs_html.py', 'offline': True}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(destination / 'index.html')

if __name__ == '__main__':
    build()
