"""Offline, checkpoint-aware presentation of the experiment ledger.

Rendering never fits a model or changes a completed trial.
"""
from html import escape
import json
from pathlib import Path
import sqlite3
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scripts.report_theme.report_theme import hero, metric, finding, figure_html, style_plotly, render_page
from .core import ROOT, Store, clean, digest
from .validation import folds


def table(rows, columns=None):
    frame=pd.DataFrame(rows)
    if frame.empty:return '<p>No completed results for this section yet.</p>'
    if columns:frame=frame.reindex(columns=columns)
    return '<div class="table-wrap" tabindex="0">'+frame.to_html(index=False,escape=True,float_format=lambda x:f'{x:,.3f}',na_rep='—')+'</div>'


def collect(c):
    store=Store(c)
    with store.connection() as con:
        records=con.execute("SELECT id,fingerprint,output FROM trials WHERE status='complete'").fetchall()
    inv=json.loads((store.root/'inventory.json').read_text())
    from .core import fingerprint
    valid=[];stale=[]
    for ident,fp,path in records:
        if '/band' not in ident and not ident.endswith('/events'):continue
        if fp!=fingerprint([inv['fingerprint'],ident]) or not store.valid(ident,fp):
            stale.append(ident);continue
        valid.append(json.loads((store.root/path).read_text()))
    return valid,stale,inv


def build(c):
    store=Store(c);trials,stale,inv=collect(c)
    expected=len(c['connectors'])*len(folds(c))*(len(c['bands'])+1)
    scores=[r for t in trials if '/band' in t['job'] for r in t['scores']]
    events=[r for t in trials if t['job'].endswith('/events') for r in t['scores']]
    quantiles=[r for t in trials for r in t.get('quantiles',[])]
    slices=[r for t in trials for r in t.get('slices',[])]
    status='Complete model campaign' if len(trials)==expected else 'Interim campaign — still incomplete'
    recovery=[]
    for p in sorted((store.root/'cache/dispatch_load').glob('*.json')):
        try:recovery.append(json.loads(p.read_text()))
        except (ValueError,OSError):pass
    summary={'status':status,'completed_jobs':len(trials),'expected_jobs':expected,'stale_or_invalid':stale,
             'scores':scores,'events':events,'quantiles':quantiles,'source_fingerprint':inv['fingerprint'],
             'claim':'Historical development evidence, not verified live model performance.'}
    store.json(store.root/'report_summary.json',summary)
    out=ROOT/'docs/html/forecast_experiment_framework.html';out.parent.mkdir(parents=True,exist_ok=True)
    body=hero('Interconnector forecast experiments','From network evidence','to tested forecasts',
        status+'. Fixed and rolling evaluations remain separate. Missing or stale trials are excluded.',
        [c['campaign'],'Data through 31 August 2026','NEM time · UTC+10','Retrospective development'])
    body+='<nav><a href="#accuracy">Accuracy explorer</a> · <a href="#events">Contraction warnings</a> · <a href="#uncertainty">Uncertainty</a> · <a href="#methods">Methods and gaps</a> · <a href="#sources">Sources</a></nav>'
    body+='<div class="metrics">'+metric('Completed jobs',f'{len(trials)} / {expected}','Checksummed current campaign trials')+metric('Scored model cells',len(scores),'Five targets; fixed and rolling folds')+metric('Event model cells',len(events),'Both directional limits')+metric('Framework storage',f'{store.used()/1e9:.2f} GB','10 GB shared additional budget')+'</div>'
    body+='<div class="findings">'+finding(1,'Comparison comes before promotion','Feature additions and model complexity are compared with persistence and seasonal baselines. Winners are chosen on earlier validation data.')+finding(2,'Warnings have an explicit cost','Contraction warning thresholds are chosen jointly across both directions with a maximum of three false alarms per day on the alert tuning partition. Evaluation may exceed that budget.')+finding(3,'Historical fit is not live eligibility','Reconstructed network features lack verified first-publication history. These models remain retrospective; original AEMO issue forecasts form a separate operational-input benchmark.')+'</div>'
    body+='<section id="accuracy"><h2>Accuracy explorer</h2><p>MAE in MW. Every point is one completed fold, target and horizon band. Lower is better. A selected model was selected before the evaluation period.</p>'
    for key,values in [('ic',[i['name'] for i in c['connectors']]),('protocol',['fixed','rolling']),('target',c['targets']),('band',list(range(len(c['bands']))))]:
        body+=f'<label>{escape(key.title())} <select id="filter-{key}">'+''.join(f'<option>{escape(str(v))}</option>' for v in values)+'</select></label> '
    body+='<div id="accuracy-chart"></div><div id="score-table" class="table-wrap" tabindex="0"></div></section>'
    data=json.dumps(clean(scores),separators=(',',':')).replace('</','<\\/')
    body+='''<script>const scores=DATA;
function draw(){const keys=['ic','protocol','target','band'];const s=scores.filter(r=>keys.every(k=>String(r[k])===document.getElementById('filter-'+k).value));
const names=[...new Set(s.map(r=>r.model))];Plotly.react('accuracy-chart',names.map(n=>({type:'scatter',mode:'lines+markers',name:n,x:s.filter(r=>r.model===n).map(r=>r.fold),y:s.filter(r=>r.model===n).map(r=>r.mae)})),{height:600,paper_bgcolor:'white',plot_bgcolor:'#ececf3',yaxis:{title:'MAE (MW)'},margin:{t:30,b:120},legend:{orientation:'h',y:-.3}},{responsive:true});
const root=document.getElementById('score-table');root.replaceChildren();const t=document.createElement('table');const columns=['fold','model','track','n','mae','rmse','bias','selected'];const head=t.insertRow();columns.forEach(k=>{const th=document.createElement('th');th.textContent=k;head.appendChild(th);});s.forEach(r=>{const row=t.insertRow();columns.forEach(k=>{const cell=row.insertCell();cell.textContent=typeof r[k]==='number'?r[k].toLocaleString(undefined,{maximumFractionDigits:3}):String(r[k]??'—');});});root.appendChild(t);}
['ic','protocol','target','band'].forEach(k=>document.getElementById('filter-'+k).addEventListener('change',draw));draw();</script>'''.replace('DATA',data)
    body+='<section id="events"><h2>Sharp-contraction warning results</h2><p>Monthly-of-year training-only 90th percentile of positive 30-minute limit falls; pooled fallback when fewer than 100 positive training observations exist. Incidents group adjacent onsets within 30 minutes. Useful warnings must precede the first onset by 30–120 minutes. The 100, 200 and 400 MW definitions are separate sensitivity analyses.</p>'
    event_rows=[{**{k:r.get(k) for k in ['ic','protocol','fold','direction','model','selected','threshold']},**{k:r['incidents'].get(k) for k in ['incidents','tp','fp','fn','recall','false_alarms_per_day']},'brier':r['probability'].get('brier')} for r in events]
    body+=table(event_rows)+'</section>'
    body+='<section id="uncertainty"><h2>Forecast uncertainty</h2><p>Linear smooth quantile regression and shallow quantile boosting compete on validation weighted interval score. A later partition calibrates quantiles before evaluation. Intervals are sorted to prevent crossing; reported point forecasts and interval medians are separate estimates.</p>'+table(quantiles)+'</section>'
    body+='<section><h2>Seasonal and diurnal accuracy</h2><p>Selected-model MAE by delivery season and hour. These are development diagnostics; fixed and rolling observations overlap and must not be pooled as independent evidence.</p>'
    selected=[r for r in slices if r.get('selected') and r['target']=='flow' and r['slice'] in ['season','hour']]
    body+=table(selected,['ic','protocol','fold','band','slice','value','model','n','mae','bias'])+'</section>'
    body+='<section><h2>Original AEMO forecast benchmark</h2><p>Original forecast issues are compared separately. Their coverage is shorter than the network study; missing leads and insufficient earlier bias-calibration history are unavailable comparisons.</p>'
    ap=store.root/'aemo_benchmark.json'
    if ap.exists():
        a=json.loads(ap.read_text());body+=table(a['scores'])+'<details><summary>Unavailable AEMO comparisons</summary>'+table(a['unavailable'])+'</details>'
    else:body+='<p>Benchmark has not completed yet.</p>'
    body+='</section><section><h2>Pooled linear transfer challenger</h2><p>A common ridge model uses the full state/pressure feature block and training-only per-connector residual scaling. Compare it with the corresponding connector-specific ridge_full result, not a different feature recipe.</p>'
    pp=store.root/'pooled.json'
    if pp.exists():
        pooled=json.loads(pp.read_text());body+='<p>Status: '+('complete' if pooled.get('complete') else 'incomplete')+'</p>'+table(pooled['scores'],['ic','protocol','fold','band','target','model','n','mae','rmse','bias'])
    else:body+='<p>Queued after the connector-specific campaign.</p>'
    body+='</section>'
    methods='''## Methods and current limitations

The campaign contains 104 numeric jobs and 26 directional-event jobs: VNI and QNI, one fixed split and twelve expanding monthly folds, and four numeric horizon bands. Forecast origins occur every 30 minutes; 14 scored leads span 30 minutes to seven days. Five numeric targets cover mean flow, mean directional limits and minimum five-minute directional limits within each half-hour. Full 336-step examples are produced at one declared origin per fold, not at every historical origin.

Training, model selection, quantile/probability calibration, alert tuning and evaluation are chronological and separate. Delivery windows crossing a partition boundary are purged. Preprocessing and event thresholds are fitted using training data. Aggregate generator-pressure forecasts use monthly out-of-fold estimates. They are not forecasts of individual generator dispatch.

The model ladder covers persistence, daily/weekly seasonal baselines, ridge, elastic net, additive and regime terms, shallow boosting, validation-selected blends and linear/boosted quantiles. Feature ablations isolate lagged flow, network state, generator pressure, forecast aggregate pressure and regional context. Future-actual fundamentals are an explicitly separate oracle diagnostic and cannot win a deployable-model comparison. Regime gates currently use training-relative standardized headroom. Boosting is a challenger, not an assumed winner.

The additional storage cap is shared across campaigns: 10 GB, with a 20 GB free-disk reserve. Only explicitly scoped monthly DISPATCHLOAD archives were recovered for the selected generator universe. Archives are streamed, filtered, hashed and removed after the derived file is verified. Original studies are preserved. Recovery does not establish historical first-publication availability.

Historical model promotion is provisional: at least 5% flow MAE improvement without material event harm, or at least 10 percentage points more incident recall at the same false-alarm burden with no more than 2% flow MAE deterioration. Operational eligibility and calibration remain additional requirements. No retrospective model is promoted automatically.

Outstanding extensions must not be mistaken for completed results: individual-generator dispatch forecast integration, complete 100-case-per-connector deep forecast-error attribution, historical weather/outage forecast vintages, and a verified live shadow trial. Generator dispatch recovery alone does not complete these extensions. Event-equation co-movement is not proof of generator causation.

Rebuild this checkpoint report with `python -m nemic.experiments report`. Resume cached model jobs with `python -m nemic.experiments run`. Source files, hashes, configuration and model code are recorded in the campaign inventory; completed trial artifacts have checksums. Report code changes do not invalidate model fits.
'''
    body+='<section id="methods"><h2>Methods and coverage gaps</h2>'+''.join('<p>'+escape(p)+'</p>' for p in methods.split('\n\n')[1:])+'</section>'
    body+='<section id="sources"><h2>Sources and provenance</h2><p>The campaign inventory records exact local paths and SHA-256 checksums for every model input. Recovered DISPATCHLOAD files have separate source URL and derived-file manifests. Previous VNI/QNI research and event atlases remain the source of network-mechanism hypotheses.</p>'+table(inv['sources'],['path','role','bytes','sha256'])+'</section>'
    html=render_page('VNI–QNI forecasting experiment framework',body,accent='blue')
    with store.reserve(len(html.encode())+2_000_000):out.write_text(html,encoding='utf-8')
    md=ROOT/'docs/forecast_experiment_framework_results.md'
    markdown='# VNI–QNI forecasting experiments\n\n'+status+f'. Completed verified jobs: {len(trials)}/{expected}.\n\n'+methods
    for title,values,columns in [('Numeric model scores',scores,['ic','protocol','fold','band','target','model','track','n','mae','rmse','selected']),('Contraction warnings',event_rows,None),('Quantile scores',quantiles,None)]:
        markdown+='\n## '+title+'\n\n'
        frame=pd.DataFrame(values)
        if columns and not frame.empty:frame=frame.reindex(columns=columns)
        if frame.empty:markdown+='No completed results yet.\n';continue
        # No optional tabulate dependency; all cell content is escaped for Markdown.
        cols=list(frame.columns);markdown+='| '+' | '.join(cols)+' |\n|'+'|'.join(['---']*len(cols))+'|\n'
        for row in frame.itertuples(index=False,name=None):
            markdown+='| '+' | '.join(str(x).replace('|','\\|').replace('\n',' ') for x in row)+' |\n'
    markdown+='\n## Sources\n\n'
    for source in inv['sources']:markdown+='- `'+source['path']+'` — SHA-256 `'+source['sha256']+'`.\n'
    md.write_text(markdown,encoding='utf-8')
    store.json(store.root/'report_build.json',{'report':str(out),'sha256':digest(out),'markdown':str(md),'completed_jobs':len(trials),'expected_jobs':expected,'source_fingerprint':inv['fingerprint'],'generator_sha256':digest(Path(__file__))})
    print(json.dumps({'html':str(out),'markdown':str(md),'completed_jobs':len(trials),'expected_jobs':expected}),flush=True)
