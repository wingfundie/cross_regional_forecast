"""Render the paired research notes and the offline collection from retained tables."""
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import html
import json
import os
import re
import base64
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import markdown

out = Path(__file__).resolve().parent
root = out.parents[1]
css = """body{max-width:880px;margin:auto;padding:32px 20px 64px;background:white;color:#20313b;font:17px/1.65 Georgia,serif}h1,h2,h3,nav,th{font-family:Arial,sans-serif}h1{line-height:1.12;font-size:clamp(30px,5vw,47px)}h2{margin-top:2em;font-size:23px}a{color:#195968;overflow-wrap:anywhere}section{border-top:2px solid #43696c;margin-top:45px;padding-top:18px}.scroll{max-width:100%;overflow:auto}table{border-collapse:collapse;font:14px/1.4 Arial,sans-serif}td,th{padding:8px;text-align:left;border-bottom:1px solid #cad5d6}th{background:#f1f5f4}li{margin-bottom:8px}nav{font-size:14px}"""
def render(md):
    return markdown.markdown(md,extensions=['tables']).replace('<table>','<div class="scroll"><table>').replace('</table>','</table></div>')
def page(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+css+'</style><body>'+body+'</body></html>'
records=[]
for entry in (out/'edition.txt').read_text(encoding='utf8').strip().split('\n===\n'):
    lines=entry.splitlines()
    slug,title,original=lines[0].split('|')
    original=root/original
    prior=original.read_text(encoding='utf-8-sig')
    md='# '+title+'\n\n'+'\n'.join('- '+s for s in lines[1:4])+'\n\n'+'\n'.join(lines[5:])+'\n'
    if slug=='forward':
        md+='\n## Choosing an input by operating condition\n\n'
        import csv
        with (original.parent/'recommendations.csv').open(encoding='utf8') as source:
            md+='| Input | First source | Regional fallback |\n|---|---|---|\n'
            for r in csv.DictReader(source):
                md+='| '+' | '.join(r[k] for k in ['family','public_first_choice','if_only_regional_forecasts'])+' |\n'
    else:
        tables=re.findall(r'(?m)(?:^\|[^\n]*\n){3,}',prior+'\n')
        for table in tables:
            if any(x in table for x in ['http','[',']']): continue
            heading=next((x.lstrip('# ') for x in reversed(prior[:prior.find(table.rstrip())].splitlines()) if x.startswith('#')),title)
            md+='\n### '+heading+'\n\n'+table.replace('—','–')
    source=os.path.relpath(original,out).replace(os.sep,'/')
    md+='\n## Sources and evidence\n\n- [February 2026 research record, method and supporting tables]('+source+')\n'
    if slug=='sydney':
        md+='- [February site diagnostic, both interval alignments](../../local_exports/rhs_approximation_study/local/sydney_west_scores.csv)\n'
    refs=re.findall(r'\[([^\]]+)\]\((https?://[^)]+)\)',prior)
    urls=set()
    for label,url in refs:
        if url not in urls:
            md+='- ['+label+']('+url+')\n'
            urls.add(url)
        if len(urls)==4: break
    chart=None
    if slug in ('thermal','forward'):
        if slug=='thermal':
            data=pd.read_csv(original.parent/'dynamic_rating_metrics.csv').set_index('method').mae
            values=data.loc[['train_median','static_25C','clock_profile','weather_static_alternate','weather_regression']]
            labels=['Training median','Static at 25°C','Clock profile','Temperature lookup','Temperature and wind']
            caption='Red Cliffs–Wemen rating error'
            unit='MVA'
        else:
            data=pd.read_csv(original.parent/'local/scores.csv')
            values=data.query("target=='Sydney area' and kind=='PREDISPATCHIS'").set_index('method').mae.loc[['Population share','Issued local monitor','Clock demand share','Anchor plus regional change']]
            labels=['Population share','Issued local monitor','Clock-specific share','Local reading + change']
            caption='Sydney-area previous-afternoon load error'
            unit='MW'
        fig,ax=plt.subplots(figsize=(7.2,3.2),layout='constrained')
        bars=ax.barh(labels,values,color='#406d75')
        ax.invert_yaxis()
        ax.bar_label(bars,fmt='%.1f',padding=4)
        ax.set_xlim(0,max(values)*1.17)
        ax.set_xlabel(f'Mean absolute error ({unit}) · February 2026 · 12 half-hours')
        ax.spines[['right','top']].set_visible(False)
        chart=out/(slug+'.png')
        fig.savefig(chart,dpi=145,facecolor='white');plt.close(fig)
        md=md.replace('## Sources and evidence',f'![{caption}]({chart.name})\n\n## Sources and evidence')
    (out/(slug+'.md')).write_text(md,encoding='utf8')
    body=render(md)
    if chart:
        body=body.replace('src="'+chart.name+'"','style="width:100%;height:auto" src="data:image/png;base64,'+base64.b64encode(chart.read_bytes()).decode()+'"')
    (out/(slug+'.html')).write_text(page(title,'<nav><a href="index.html">Research collection</a></nav>'+body),encoding='utf8')
    records.append((slug,title,body))
nav='\n'.join(f'- [{t}]({s}.md)' for s,t,_ in records)
(out/'README.md').write_text('# NEM constraint research\n\nFebruary 2026 dispatch replays and forward experiments. All market times use fixed UTC+10. The final note brings the input recommendations together.\n\n'+nav+'\n',encoding='utf8')
contents=''.join(f'<li><a href="#{s}">{html.escape(t)}</a></li>' for s,t,_ in records)
(out/'index.html').write_text(page('NEM constraint research','<h1>NEM constraint research</h1><p>February 2026 · Fixed NEM time (UTC+10)</p><nav><ol>'+contents+'</ol></nav>'+''.join('<section id="'+s+'">'+b+'</section>' for s,_,b in records)),encoding='utf8')
paths=sorted([*out.glob('*.md'),*out.glob('*.html'),*out.glob('*.png'),out/'edition.txt',Path(__file__)])
(out/'manifest.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2))
