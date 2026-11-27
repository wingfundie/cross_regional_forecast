"""Build the study from the retained evidence in the IC FLOW FORECASTING workspace."""
from pathlib import Path
import base64
import html
import re
import shutil
import sys

import markdown
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT/'scripts/report_theme'))
from report_theme import hero, metric, render_page, matplotlib_style, figure_html

context = OUT/'context'
context.mkdir(exist_ok=True)
prior = ROOT/'local_exports/rhs_forward_feb26'
for source, new in [(prior/'metrics.csv','earlier_scores.csv'), (prior/'bango_injection_list.csv','bango_inputs.csv'),
                    (prior/'population.json','population.json'),(prior/'sources.json','earlier_sources.json'),
                    (ROOT/'reports/rhs_replay/inventory/dependencies.csv','dependencies.csv'),
                    (ROOT/'reports/rhs_replay/sydney_sources.csv','sydney_sources.csv'),
                    (next((ROOT/'data/manifest_records').glob('*ROOFTOP_PV_ACTUAL*202602*')), 'rooftop_actual.json')]:
    shutil.copyfile(source, context/new)

scores = pd.read_csv(OUT/'local/scores.csv')
s = scores.set_index(['target','kind','method']).mae
short,day = 'P5MIN','PREDISPATCHIS'

def score_table(targets, methods, names):
    rows = []
    for target in targets:
        for product, label in [(short,'Short'),(day,'Previous afternoon')]:
            rows.append([target,label,*[s.loc[target,product,m] for m in methods]])
    return pd.DataFrame(rows,columns=['Input','Forecast origin',*names]).to_markdown(index=False,floatfmt='.1f')

local_table = score_table(['Sydney area','Terranora','Canberra','Central West NSW','Southwest NSW'],
                          ['Clock demand share','Anchor plus regional change','Clock plus demand and PV','Issued local monitor'],
                          ['Clock share','Anchor','Demand + PV','Issued monitor'])
plants = score_table(['BANGOWF1','CAPTL_WF','CULLRGWF','GOONSF1'],
                     ['Persistence','Issued regional generation share','Anchor plus generation change'],
                     ['Carry latest','Regional share','Anchor + change'])
rec = pd.read_csv(OUT/'recommendations.csv')
matrix = rec[['family','public_first_choice','if_only_regional_forecasts']].set_axis(
    ['Input family','First public source or benchmark','Fallback to test'],axis=1).to_markdown(index=False)
figdir = OUT/'figures'
figdir.mkdir(exist_ok=True)
plt.rcParams.update(matplotlib_style())
methods = ['Population share','Fixed demand share','Clock demand share','Issued local monitor',
           'Clock plus demand and PV','Anchor plus regional change']
fig,ax = plt.subplots(figsize=(7.8,3.7),layout='constrained')
values = [s.loc['Sydney area',day,m] for m in methods]
ax.barh(methods,values,color=['#aa7c45','#8799a6','#8799a6','#657bad','#268a87','#268a87'],zorder=2)
for i,v in enumerate(values):ax.text(v+6,i,f'{v:.0f}',va='center',fontsize=10)
ax.invert_yaxis()
ax.set_xlim(0,max(values)*1.14)
ax.set_xlabel('Mean absolute error in MW · 12 held-out half-hours')
fig.savefig(figdir/'sydney.png');plt.close(fig)

flow = pd.read_csv(OUT/'flows/flow_scores.csv')
f = flow[flow['product']==day].pivot(index='link',columns='method',values='mae')
ratios = (f['issued ramp']/f['persist']).sort_values()
fig,ax = plt.subplots(figsize=(7.8,3.5),layout='constrained')
ax.barh(ratios.index,ratios,color=['#268a87' if x<1 else '#657bad' for x in ratios],zorder=2)
ax.axvline(1,color='#222',ls='--',lw=1,zorder=3)
for i,v in enumerate(ratios):ax.text(v+.03,i,f'{v:.2f}×',va='center')
ax.invert_yaxis()
ax.set_xlim(0,ratios.max()+.43)
ax.set_xlabel('Previous-afternoon flow MAE / persistence MAE · below 1 favours the issued path')
fig.savefig(figdir/'flows.png');plt.close(fig)

main = (OUT/'overview.md').read_text(encoding='utf-8').replace('{{LOAD_TABLE}}',local_table).replace(
    '{{GEN_TABLE}}',plants).replace('{{MATRIX}}',matrix)
unit = pd.read_csv(OUT/'local/unit_crosscheck.csv')
matched = unit[unit.dispatch_matches.gt(0)]
audit = (f'The independent dispatch-solution check found {int(unit.dispatch_matches.sum()):,} matching '
         f'unit-interval records among {int(unit.scada_rows.sum()):,} SCADA records. Maximum absolute '
         f'difference on matched observations was {matched.max_abs_mw.max():.4f} MW. '
         'BANGOWF1, GOONSF1 and both batteries matched on every sampled record. CAPTL_WF and '
         'CULLRGWF had public SCADA but no matching DUID in the sampled dispatch solution. '
         'The plant forecast errors above are against public SCADA. '
         '[Unit identity cross-check](local/unit_crosscheck.csv)')
main = main.replace('Regional rooftop PV was worth',audit+'\n\nRegional rooftop PV was worth')

def chapter(name):
    md=(OUT/name/'report.md').read_text(encoding='utf-8').strip()
    def prefix(match):
        target=match.group(1)
        return ']('+ (target if target.startswith(('https:','http:','#')) else name+'/'+target) +')'
    return re.sub(r'\]\(([^)]+)\)',prefix,md)

main = main.replace('## When to use the result',
       '## Signed flows and the QNI network equation\n\n![Issued flow error relative to persistence](figures/flows.png)\n\n'+
       chapter('flows')+'\n\n## Thermal limits and Bango\n\n'+chapter('thermal')+
       '\n\n## Switches, electrical conditions and outages\n\n'+chapter('states')+'\n\n## When to use the result')
main += '''

## Evidence and reproduction

The files contain interval-level predictions so each comparison can be recalculated on matched rows. The scripts use the existing project checkout and its data readers. The standalone HTML includes the charts and tables. Extract the evidence bundle alongside it to use the local downloads.

| Topic | Evidence | Reproduction in the project checkout |
|---|---|---|
| Local demand, renewables and storage | [Predictions](local/predictions.csv), [sample and run metadata](local/observed_inputs.csv), [scores](local/scores.csv) | [Local experiment](local/run_local.py), [independent unit cross-check](local/check_units.py) |
| Signed flows, regional demand and binding | [Flow scores](flows/flow_scores.csv), [pump experiment](flows/scheduled_load_scores.csv), [RHS scores](flows/rhs_scores.csv), [headroom and alerts](flows/binding_scores.csv) | [Flow experiment](flows/study.py), [pump comparison](flows/load_bridge.py) |
| Thermal equation | [Inputs](thermal/input_metrics.csv), [full RHS](thermal/rhs_metrics.csv), [binding](thermal/binding.csv) | [Thermal experiment](thermal/thermal.py) |
| Network states | [Outage predictions](states/outage_predictions.csv), [outage scores](states/outage_metrics.csv) | [State and outage experiment](states/study.py) |
| Recommendations and provenance | [Input-by-input routing](recommendations.csv), [study decisions](decisions.tsv), [file hashes](manifest.json) | [Report builder](build_report.py) |
'''
title='Forecasting NEM constraint right-hand sides'
(OUT/'report.md').write_text('# '+title+'\n\n'+main,encoding='utf-8')
head=hero('NEM interconnector research', 'Forecasting constraint', 'right-hand sides',
          'How far regional demand can take an RHS calculator, which public inputs improve it, and when a binding call is justified.',
          ['February 2026 data','Fixed NEM time · UTC+10','Public archived vintages'])
cards=''.join(metric(*args) for args in [('Local demand','5 areas','Verified against named monitor values'),
             ('Physical flows','6 links','Signed initial flow compared at two leads'),
             ('Broad Sydney','420 MW','Day-ahead population-share MAE on the later sample'),
             ('QNI alerts','7 missed','Day-ahead economic binds missed out of seven')])
sections = re.split(r'(?m)^## ',main)[1:]
titles = [sec.split('\n',1)[0] for sec in sections]
anchors=['section-'+str(i+1) for i in range(len(titles))]
navlabels=['Feasibility','Local demand','Plant MW','Input guide','QNI flows','Thermal limits','Network states','Decision rules','Methods','Evidence']
assert len(titles)==len(navlabels)
nav='<nav aria-label="Sections">'+''.join(f'<a href="#{a}">{n}</a>' for a,n in zip(anchors,navlabels))+'</nav>'
body=head+nav+'<div class="metrics">'+cards+'</div>'
for i,sec in enumerate(sections):
    heading,content=sec.split('\n',1)
    block=markdown.markdown(content,extensions=['tables','fenced_code','sane_lists'])
    block=block.replace('<table>','<div class="table-wrap" tabindex="0"><table>').replace('</table>','</table></div>')
    def image_tag(match):
        alt,src=match.groups()
        data=base64.b64encode((OUT/src).read_bytes()).decode()
        img=f'<img alt="{alt}" src="data:image/png;base64,{data}">'
        local='sydney' in src
        return figure_html(img,alt,'Previous-afternoon forecasts on matched held-out deliveries.',
                           'local/scores.csv' if local else 'flows/flow_scores.csv')
    block=re.sub(r'<p><img alt="([^"]+)" src="([^"]+)"\s*/?></p>',image_tag,block)
    body+=f'<section id="{anchors[i]}"><h2>{html.escape(heading)}</h2>{block}</section>'
body+='<footer>IC Flow Forecasting · Public-data research · February 2026 interval samples</footer>'
page=render_page(title,body,plotly=False)
css='p, li {max-width:91ch} .table-wrap td,.table-wrap th{white-space:normal;text-align:left;min-width:84px} .table-wrap td:first-child{min-width:125px} img{max-width:100%} figure img{max-width:880px;margin:auto} h2{color:#283a51} section{border-top:1px solid #dfe3eb} .table-wrap{background:white} a{overflow-wrap:anywhere}'
(OUT/'index.html').write_text(page.replace('</style>',css+'</style>'),encoding='utf-8')
