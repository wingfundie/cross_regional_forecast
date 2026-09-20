"""Offline editorial evidence suite; never invent results or retrain on render."""
import json
from html import escape
from pathlib import Path

import markdown
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from scripts.report_theme.report_theme import hero,metric,figure_html,style_plotly,render_page
from nemic.experiments.core import ROOT,digest,clean
from .tracking import atomic,now


def table(rows):
    if not rows:return '<p>No measured results are available for this section.</p>'
    frame=pd.DataFrame(rows)
    return '<div style="overflow-x:auto">'+frame.to_html(index=False,escape=True,border=0)+'</div>'


def chart(fig,title,note):
    style_plotly(fig,title,height=480)
    return figure_html(fig.to_html(full_html=False,include_plotlyjs=False),title,note)


def render(ledger):
    ledger.export()
    out=ROOT/'reports'/ledger.c['campaign'];out.mkdir(parents=True,exist_ok=True)
    status=json.loads((ledger.root/'status.json').read_text())
    covpath=ledger.data/'coverage.json';coverage=json.loads(covpath.read_text()) if covpath.exists() else {'partitions':[]}
    candidates=list((ledger.data/'train').glob('**/result.json'))
    measured=[]
    for path in candidates:
        result=json.loads(path.read_text())
        if (path.parent/'predictions.parquet').exists() and {'connector','target','band','fold','score','network_score'}<=set(result):
            measured.append((path,result))
    result_paths=[path for path,_ in measured];results=[result for _,result in measured]
    links=[('index.html','Overview'),('deck.html','Presentation'),('feature_research.html','Feature research'),
           ('selection.html','Feature reduction'),('pipeline.html','Data and pipeline'),('QNI.html','QNI'),('VNI.html','VNI'),('decisions.html','Decisions'),('execution.html','Execution')]
    nav='<nav>'+ ' · '.join(f'<a href="{p}">{escape(t)}</a>' for p,t in links)+'</nav>'
    note='Historical development. No improvement or deployment eligibility is implied by completed software or acquired samples.'
    pages={}
    stats=[metric('Connectors',2,'QNI and VNI'),metric('Targets per connector',5,'Flow plus four directional limits'),
           metric('Measured model cells',len(results),'Only result artifacts actually present'),metric('Historical PASA overlap',coverage.get('historical_pasa_days',0),'Source days; interval coverage requires further checks')]
    summary=hero('Forecast fundamentals research','QNI and VNI','Evidence before adoption',note,[now()[:10],ledger.c['feature_version'],'BOM → ECMWF'])+nav+'<div class="metrics">'+''.join(stats)+'</div>'
    pages['index.html']=summary+'<section><h2>Current evidence</h2>'+table([dict(job=r['id'],status=r['status'],detail=r.get('detail')) for r in status['jobs'] if '/' not in r['id']])+'</section>'
    for filename,title,source in [('feature_research.html','Feature engineering research','feature_research.md'),('selection.html','Feature reduction methodology','selection_review.md')]:
        source_text=(ledger.root/'methodology'/source).read_text(encoding='utf-8')
        if source_text.startswith('# '):source_text=source_text.partition('\n')[2]
        content=markdown.markdown(source_text,extensions=['tables','fenced_code'])
        content=content.replace('<table>','<div style="overflow-x:auto;max-width:100%"><table>').replace('</table>','</table></div>')
        pages[filename]=hero('Methodology and evidence',title,'Definitions and tests',note,[])+nav+content
    selected=[]
    for r in results:
        for recipe,s in r.get('feature_search',{}).items():
            selected.append(dict(connector=r['connector'],target=r['target'],band=r['band'],fold=r['fold'],recipe=recipe,method=s['method'],raw=s['raw_count'],selected=s['selected_count'],seconds=s['seconds']))
    pages['selection.html']+='<section><h2>Measured selection results</h2>'+table(selected)+'</section>'
    if selected:
        df=pd.DataFrame(selected)
        pages['selection.html']+=chart(px.scatter(df,x='selected',y='seconds',color='connector',hover_data=['target','recipe']),'Retained features and screening runtime','Actual chronological selector runs, not feature-importance proxies.')
    source_rows=coverage.get('partitions',[])
    pages['pipeline.html']=hero('Source contracts','Forecast inputs','Availability and coverage',note,[])+nav
    pipeline=go.Figure(go.Scatter(x=list(range(6)),y=[1]*6,mode='lines+markers+text',text=['Public runs','As-of store','Network + inputs','Inner selection','Held-out scores','Research package'],textposition='top center'))
    pipeline.update_yaxes(visible=False);pipeline.update_xaxes(visible=False)
    pages['pipeline.html']+=chart(pipeline,'Pipeline stages','Every stage references a frozen methodology and ledger checkpoint.')
    pages['pipeline.html']+=table(source_rows)
    if source_rows:
        df=pd.DataFrame(source_rows)
        pages['pipeline.html']+=chart(px.bar(df,x='product',y='rows',color='product'),'Acquired normalized source rows','Counts measure acquisition, not independent samples or historical training coverage.')
    weather=[]
    for path in (ledger.data/'sources/weather').glob('*.json'):
        w=json.loads(path.read_text());weather.append(dict(run=w['run'],provider=w['provider'],rows=w['rows'],provenance=', '.join(w['provenance']),fallback=json.dumps(w['fallback_reasons'])))
    pages['pipeline.html']+='<h2>Weather provider audit</h2>'+table(weather)
    for name in ('VNI','QNI'):
        rs=[r for r in results if r['connector']==name]
        rows=[dict(target=r['target'],band=r['band'],fold=r['fold'],winner=r.get('winner'),mae=r['score']['mae'],network_mae=r['network_score']['mae'],skill=r.get('skill'),promotion=r.get('promotion',False),risk_gate=r.get('risk_gate','Provider sensitivity; primary risk gate not applicable')) for r in rs]
        pages[name+'.html']=hero('Connector assessment',name,'Model comparisons',note,[])+nav+table(rows)
        if rows:
            df=pd.DataFrame(rows)
            pages[name+'.html']+=chart(px.bar(df,x='band',y='mae',color='target',barmode='group'),'Measured MAE by lead band','Matched chronological evaluation; development evidence.')
            pp=next((p.parent/'predictions.parquet' for p in result_paths if name in p.parts),None)
            if pp is not None:
                f=pd.read_parquet(pp);origin=f.origin.min();curve=f[f.origin.eq(origin)]
                pages[name+'.html']+=chart(px.line(curve,x='delivery',y=['actual','point','network','persistence']),'Example forecast path',f'Origin {origin}; sampled configured leads. This is not exhaustive 336-lead verification.')
    pages['decisions.html']=hero('Acceptance audit','Model decisions','Measured gains and remaining gates',note,[])+nav+markdown.markdown((ledger.root/'decisions.md').read_text(encoding='utf-8'))
    pages['decisions.html']+='<p>Replacement requires 2% MAE skill, supported paired uncertainty, capacity-overstatement and recall non-inferiority, and the joint false-alert budget. Missing risk evidence prevents promotion.</p>'
    pages['decisions.html']+=table([dict(connector=r['connector'],target=r['target'],band=r['band'],winner=r.get('winner'),promotion=r.get('promotion',False),reason=r.get('risk_gate','Provider sensitivity; primary risk gate not applicable')) for r in results])
    pages['execution.html']=hero('Persistent execution record','Campaign state','Checkpoints and next actions','Generated from the authoritative dedicated ledger.',[])+nav+table([dict(job=r['id'],status=r['status'],updated=r['updated'],detail=r['detail']) for r in status['jobs']])
    benchmark_path=ledger.root/'benchmarks/scalar_baseline.json'
    benchmark=json.loads(benchmark_path.read_text()) if benchmark_path.exists() else {}
    daily=[]
    for path in (ledger.data/'features').glob('*/partitions/**/*.json'):
        try:
            item=json.loads(path.read_text());
            if 'rows_per_second' in item:daily.append(dict(connector=path.parts[-4],date=path.stem,rows_per_second=item['rows_per_second'],rss_gb=item.get('peak_rss_bytes',0)/1e9,rows=item.get('rows',0)))
        except (json.JSONDecodeError,KeyError):pass
    pages['pipeline.html']+='<section><h2>Measured performance</h2>'+table([benchmark]+daily[-30:])+'</section>'
    if daily:
        perf=pd.DataFrame(daily)
        pages['pipeline.html']+=chart(px.line(perf,x='date',y='rows_per_second',color='connector',markers=True),'Feature throughput by partition','Cached partition manifests; no pipeline execution occurs during report rendering.')
    panels=[('Purpose','Improve network models using forecast fundamentals with issue-time discipline.'),('Scope','QNI and VNI; flow and four limits; seven days.'),
        ('Source roles','PD/ST PASA demand and renewables; MT PASA coal; BOM/ECMWF weather.'),('Weather policy','Prefer usable BOM; ECMWF fallback; distinguish older hindcasts.'),
        ('Vintage contract','Publication evidence, initialization and retrieval are distinct.'),('Regional balance','Demand minus renewable availability/constrained capacity.'),
        ('Cross-region features','All ten pairs, endpoint imbalance, joint stress and rest-of-NEM context.'),('Coal availability','Offered capacity is not dispatch, reserve or inertia.'),
        ('Interaction hypotheses','Balance × room; coal stress × demand; renewable surplus × constraints.'),('Feature reduction','Training-only grouping, screening and one-standard-error subset selection.'),
        ('Chronological evaluation','Separate training, selection, calibration, alert and evaluation windows.'),('Network controls','Keep the original 41-feature design; establish a flow control.'),
        ('Acquired evidence',f'{len(source_rows)} source partitions; {len(weather)} weather runs.'),('Measured models',f'{len(results)} saved evaluation cells.'),
        ('Risk requirements','2% MAE improvement; overstatement/recall margins; joint three-alert/day budget.'),('Current limitations','Consult execution state; unexecuted experiments are not negative results.'),
        ('Reproducibility','Immutable sources, versioned methodology, ledger, hashes and saved schemas.'),('Decision','Retain controls unless all measured acceptance checks pass.')]
    panel_charts={3:chart(pipeline,'Data to model pipeline','Source and selection stages are tracked independently.')}
    if source_rows:panel_charts[13]=chart(px.bar(pd.DataFrame(source_rows),x='product',y='rows',color='product'),'Acquisition evidence','Normalized rows, not model accuracy.')
    pages['deck.html']=hero('Research presentation','QNI/VNI fundamentals','Implementation and evidence',note,[])+nav+'<style>.slide{min-height:65vh;padding:40px 0;border-bottom:2px solid #dfe3eb;break-after:page}.slide h2{font-size:36px}</style>'+''.join(f'<section class="slide" id="slide-{i}"><p>{i:02d} / {len(panels)}</p><h2>{escape(title)}</h2><p class="dek">{escape(body)}</p>{panel_charts.get(i, "")}</section>' for i,(title,body) in enumerate(panels,1))
    downloads_nav='<section><h2>Evidence downloads</h2><p><a href="downloads/results.json">Measured model results (JSON)</a> · <a href="downloads/coverage.json">Source coverage (JSON)</a> · <a href="downloads/feature_selection.csv">Feature-selection results (CSV)</a></p></section>'
    assets=out/'assets';assets.mkdir(exist_ok=True)
    from plotly.offline import get_plotlyjs
    atomic(assets/'plotly.min.js',get_plotlyjs())
    for name,body in pages.items():atomic(out/name,render_page('QNI/VNI · '+name.removesuffix('.html'),body+downloads_nav,plotly='assets/plotly.min.js'))
    downloads=out/'downloads';downloads.mkdir(exist_ok=True)
    atomic(downloads/'results.json',json.dumps(clean(results),indent=2));atomic(downloads/'coverage.json',json.dumps(coverage,indent=2))
    pd.DataFrame(selected).to_csv(downloads/'feature_selection.csv',index=False)
    manifest=dict(built=now(),methodology=ledger.method_hash,code=ledger.code_hash,rebuild='python -m nemic.fundamentals report',
                  measured_cells=len(results),visual_review='pending',plotly_asset=digest(assets/'plotly.min.js'),
                  inputs=dict(status=digest(ledger.root/'status.json'),coverage=digest(covpath) if covpath.exists() else None,
                              results={str(p.relative_to(ROOT)):digest(p) for p in result_paths}),
                  outputs=[dict(path=str((out/n).relative_to(ROOT)),sha256=digest(out/n)) for n in pages])
    atomic(out/'manifest.json',json.dumps(manifest,indent=2))
    # Rendering is complete; the higher report stage stays open for visual QA.
    ledger.record('report/render','completed','Cached evidence rendered; visual QA remains',[out/'manifest.json'])
    return out/'index.html'
