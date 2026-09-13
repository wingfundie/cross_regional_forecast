"""Rebuild expanded Markdown tables, source inventory and offline HTML from retained evidence."""
from pathlib import Path
from html import escape
import hashlib
import json
import re
import sys
from urllib.parse import urlsplit
import markdown
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts/report_theme'))
from report_theme import render_page

DOC = ROOT/'docs/QNI_VNI_EXPANDED_FORECAST_RESEARCH.md'
EVIDENCE = ROOT/'docs/data/qni_vni_expanded_model_evidence.json'
LOG = ROOT/'docs/data/qni_vni_expanded_search_log.json'
REFS = ROOT/'docs/data/qni_vni_expanded_sources.json'


def table(frame):
    frame = frame.copy()
    for c in frame:
        frame[c] = frame[c].map(lambda x: f'{x:.4f}' if isinstance(x,float) else str(x))
    rows = [list(frame.columns), ['---']*len(frame.columns)] + frame.values.tolist()
    return '\n'.join('| '+' | '.join(str(x).replace('|',' / ') for x in row)+' |' for row in rows)


def replace_block(text, name, value):
    start, end = f'<!-- {name} -->', f'<!-- END_{name} -->'
    if end in text:
        return re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:start+'\n\n'+value+'\n\n'+end,text,flags=re.S)
    return text.replace(start,start+'\n\n'+value+'\n\n'+end)


def render(source, output, title):
    engine=markdown.Markdown(extensions=['tables','fenced_code','footnotes','toc'],extension_configs={'toc':{'toc_depth':'2-2'}})
    body=engine.convert(source.read_text(encoding='utf-8'))
    def rewrite(m):
        h=m.group(1)
        return m.group(0) if h.startswith('#') or urlsplit(h).scheme else f'href="../{h}"'
    body=re.sub(r'href="([^"]+)"',rewrite,body)
    body=body.replace('<table>','<div class="table-scroll" tabindex="0"><table>').replace('</table>','</table></div>')
    pos=body.index('</h1>')+5
    nav='<nav aria-label="Contents"><details open><summary>Contents</summary>'+engine.toc+'</details></nav>'
    downloads=f'<p><a href="../{source.name}">Markdown edition</a> · <a href="../data/{EVIDENCE.name}">Numerical evidence and input hashes</a></p>'
    body=body[:pos]+downloads+nav+body[pos:]
    page=render_page(title,body,plotly=False,accent='blue')
    css='''body{background:#fff;color:#202327}main{max-width:1180px;padding:40px 28px 80px}
h1{font-size:clamp(32px,4vw,52px);line-height:1.12;letter-spacing:-.025em}h2{margin-top:48px;border-top:1px solid #ddd;padding-top:16px;font-size:26px}h3{margin-top:30px;font-size:20px}
p,li{line-height:1.7}a{color:#285f8e;overflow-wrap:anywhere}nav{background:#f7f7f7;padding:16px;margin:24px 0}nav ul{columns:2}nav li{break-inside:avoid;font-size:14px}
.table-scroll{overflow-x:auto;margin:24px 0;border:1px solid #ddd}table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}th{background:#f0f1f3}tr:nth-child(even){background:#fafafa}
pre{overflow-x:auto;background:#f6f6f6;padding:18px;border:1px solid #ddd;font-size:13px}.footnote{font-size:13px}.footnote li{margin:12px 0}summary{cursor:pointer}
@media(max-width:650px){main{padding:20px 14px}nav ul{columns:1}table{min-width:620px}}@media print{nav{display:none}main{padding:0}.table-scroll{overflow:visible}table{font-size:8px;min-width:0}h2{break-after:avoid}}'''
    page=page.replace('</style>',css+'</style>',1)
    output.write_text(page,encoding='utf-8')


def build():
    d=json.loads(EVIDENCE.read_text())
    r=pd.DataFrame(d['regression_scores']);e=pd.DataFrame(d['event_scores']);q=pd.DataFrame(d['monthly_quality'])
    source=DOC.read_text(encoding='utf-8')
    a=pd.DataFrame(d['attribution_quality']).drop(columns=['note'])
    source=replace_block(source,'ATTRIBUTION_TABLE',table(a))
    qc=['exact_version_match_fraction','upper_reconstruction_mae_mw','lower_reconstruction_mae_mw','upper_setter_match_fraction','lower_setter_match_fraction']
    med=q.groupby('ic')[qc].median().reset_index()
    source=replace_block(source,'QUALITY_TABLE',table(med))
    small=r[r.target.eq('flow')].pivot(index=['ic','horizon_minutes'],columns='model',values='mae_mw').reset_index()
    source=replace_block(source,'REGRESSION_SUMMARY',table(small))
    ec=['ic','direction','model','brier','average_precision','recall','precision','false_positive_rate']
    source=replace_block(source,'EVENT_TABLE',table(e[ec]))
    source=replace_block(source,'ALL_REGRESSION',table(r[['ic','target','horizon_minutes','model','n','mae_mw','rmse_mw','bias_mw','autumn_mae_mw','winter_mae_mw']]))
    source=replace_block(source,'ALL_EVENTS',table(e[['ic','direction','model','n','positives','base_rate','brier','log_loss','average_precision','threshold','tp','fp','fn','recall','precision','false_positive_rate','false_positive_origins_per_day']]))
    source=replace_block(source,'ALL_QUALITY',table(q[['ic','month','five_minute_rows','exact_version_match_fraction','upper_coverage','lower_coverage','upper_reconstruction_mae_mw','lower_reconstruction_mae_mw','upper_setter_match_fraction','lower_setter_match_fraction']]))
    refs=json.loads(REFS.read_text(encoding='utf-8'))
    first=(ROOT/'docs/QNI_VNI_FORECAST_MODEL_IMPROVEMENT_PLAN.md').read_text(encoding='utf-8')
    defs=re.findall(r'^\[\^\d+\]: .*$',first,re.M)
    defs += [f"[^{x['id']}]: {x['reference']}" for x in refs]
    source=replace_block(source,'SOURCES','\n\n'.join(defs))
    DOC.write_text(source,encoding='utf-8')
    search=json.loads(LOG.read_text())
    logdoc=ROOT/'docs/QNI_VNI_EXPANDED_RESEARCH_LOG.md'
    logtext='''# QNI and VNI expanded research log

Research access: 13 September 2026. This log accompanies the [expanded report](QNI_VNI_EXPANDED_FORECAST_RESEARCH.md). The full source inventory is at the end of that report. This is an expanded integrative review, not a systematic census of every database or paper.

## Questions and method

The review asks how the retained constraint studies can improve operational flow, limit, contraction and direction forecasts; what compact features preserve mechanisms; which simple and boosted models merit testing; and what information, calibration and validation are necessary. Searches expanded from direct interconnector forecasting into congestion/active-set learning, generator movement, price extremes, weather ramps, low-dimensional flows, model comparisons and temporal evaluation. Reference and documentation links were followed where relevant. Queries returning largely irrelevant results were not counted as positive evidence.

The first edition's primary market definitions and core forecasting references were retained and supplemented with newly opened operator, academic and AEMO documents. Not every inherited source was independently reopened in this second pass. The expanded numerical experiment reused local data and trained the models recorded in its evidence file; the full original production backtest was not rerun.

## Search batches

'''
    for b in search['batches']:
        logtext+=f"### Batch {b['batch']}\n\n"+'\n'.join('- '+x for x in b['queries'])+'\n\n'
    logtext+='''## Screening and access decisions

| Material | Access / decision | Effect on conclusions |
|---|---|---|
| Statnett mFRR flow uncertainty account | Primary operator article read | Direct industry precedent; HVDC ATC not imported as NEM hard bounds |
| AEMO current formulation guideline and consultation | Primary final document and effective-date text read | December 2025 measurement/regime break included |
| AEMO version 19 predispatch procedure | Primary current procedure read | Supersedes a 2023 draft encountered during search |
| AEMO PD7DAY documentation and market notice | Primary indexed fields and notice text available; some direct pages returned retrieval errors | Longer-horizon opportunity retained; historical vintage coverage unproven |
| Liu et al. NEM logistic extreme-price paper | Primary accepted-manuscript abstract indexed; direct full-text retrieval failed | Supports candidate choice, not verified operational performance or availability |
| Gaillard et al. additive forecasting | Publisher abstract/introductory excerpts available; complete fetch unavailable | No detailed reproduction or universal ranking claim |
| KTH weather/cross-border thesis | Record encountered; bot challenge and PDF retrieval failure | Excluded from core performance evidence |
| Ng et al. and Deka/Misra OPF learning | Primary papers examined | Mechanistic regime rationale; synthetic optimisation not live forecasting |
| Schäfer et al. flow PCA | Primary paper examined | Descriptive compression hypothesis only |
| Gaugl et al. interconnector surrogate | Primary 2026 preprint examined | Planning/simulation evidence; not treated as operational forecast skill |
| Worsnop et al. wind ramp scenarios | Primary paper examined | Temporal dependence lesson, including mixed method results |
| Elastic net, EBM, forecast combinations | Author paper, official docs and review examined | Model portfolio broadened without assuming superiority |
| Temporal evaluation papers | Primary papers examined | Chronological replay and contamination controls |
| Janzing et al.; CQR | Primary proceedings/arXiv summaries read in this pass | Limited conceptual use; no local causal or coverage guarantee |
| AER/FTI/Modo and additional ramp/regime sources | Search candidates surfaced but not fully appraised | Not used as decisive evidence or padded into the core bibliography |
| Generic web mirrors and secondary abstracts | Discovery aids only where primary sources could be identified | Core technical claims use primary records |

## Empirical work and reproducibility

The expanded experiment produced 144 regression rows and 20 event rows from 100 hashed existing files. It also audited 48 monthly feature partitions and 183 selected event cases. No new MMSDM archive or weather dataset was acquired. The evidence file records configurations, library versions, runtime, limitations and input hashes. Regression bootstrap intervals are exploratory; event probabilities have no incident-level confidence interval in this run.

The first experiment's 90 simple-model score rows remain available separately. The feature blocks and validation dates differ between experiments, so they must not be concatenated as one controlled architecture trial. No retained source files were deleted merely to reduce the apparent data size.

## Open issues and boundaries

Unresolved: QNI reconstruction discrepancies, strict public availability of each unit/FCAS input, historical outage and individual weather forecast vintages, historical PD7DAY coverage, prospective incident-warning skill and causal dispatch replay. There is no unseen seven-day, eight-season operational validation in this research. The next implementation is specified in the report rather than claimed complete.

The HTML editions are built from Markdown without remote rendering dependencies. Static link, anchor and source checks are required. Browser visual preview was unavailable because the earlier local report URL was blocked by browser policy; no alternate serving or browser workaround is used.
'''
    logdoc.write_text(logtext,encoding='utf-8')
    outputs=[ROOT/'docs/html/qni_vni_expanded_forecast_research.html',ROOT/'docs/html/qni_vni_expanded_research_log.html']
    render(DOC,outputs[0],'From constraint studies to better QNI and VNI forecasts')
    render(logdoc,outputs[1],'QNI and VNI expanded research log')
    files=[DOC,logdoc,EVIDENCE,LOG,REFS,Path(__file__),ROOT/'scripts/research_expanded_models.py',ROOT/'docs/QNI_VNI_FORECAST_MODEL_IMPROVEMENT_PLAN.md',ROOT/'scripts/report_theme/report_theme.py',ROOT/'scripts/report_theme/report.css']
    def item(p):return {'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    manifest={'date':'2026-09-13','status':'expanded integrative research and exploratory experiments','inputs':[item(p) for p in files],'outputs':[item(p) for p in outputs],'rebuild':'python scripts/build_expanded_research.py','experiment':'python scripts/research_expanded_models.py','market_downloads':[],'visual_preview':'not performed; browser policy blocked prior local report','markdown_version':markdown.__version__}
    (ROOT/'docs/data/qni_vni_expanded_research_build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Report words:',len(source.split()),'regression:',len(r),'event:',len(e),'monthly:',len(q))
    print(*outputs,sep='\n')


if __name__=='__main__':
    build()
