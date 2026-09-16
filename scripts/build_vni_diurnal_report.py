"""Render cached v2 results without fitting or silently changing their snapshot."""
import html
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nemic.experiments.core import load_config, clean, digest
from nemic.experiments.diurnal import metrics,origin_weights,PERIODS
from report_theme.report_theme import hero, metric, figure_html, style_plotly, render_page


def table(rows):
    if not rows:
        return '<p>Unavailable: no completed result.</p>'
    return '<div class="table-wrap" tabindex="0">' + pd.DataFrame(rows).to_html(index=False, escape=True, float_format=lambda x:f'{x:,.3f}') + '</div>'


def lazy_chart(fig):
    payload=fig.to_json().replace('</','<\\/')
    return '<div class="lazy-plot" style="min-height:510px"><script type="application/json">'+payload+'</script></div>'


def build():
    c=load_config('configs/experiments/vni_diurnal_nos_v2.json'); root=c['_run']
    paths=sorted((root/'diurnal').glob('*/band*/*/result.json'))
    results=[json.loads(p.read_text()) for p in paths]
    if not results:
        raise ValueError('No completed VNI models')
    output=root/'report';output.mkdir(parents=True,exist_ok=True)
    body=hero('VNI forecasting research', 'Directional limits', 'Diurnal models and outage evidence',
        'MAE selects the point forecasts. Percentage metrics assess their errors. Historical results are development evidence; prospective validation is separate.',
        ['VNI · VIC1-NSW1', 'NEM time · UTC+10', 'Outcomes through August 2026', f'{len(results)} completed cells'])
    body+='<nav><a href="#results">Results</a> · <a href="#models">Models and charts</a> · <a href="#nos">NOS</a> · <a href="#risk">Warnings</a> · <a href="#methods">Methods</a></nav>'
    body+='<section class="metrics">'+metric('Completed cells',len(results),'Fold × target × horizon band')+metric('Primary objective','MAE','Origin-balanced; all finite targets including zero and negative limits')+metric('Percentage assessment','MAPE','Qualified |actual| ≥50 MW, with coverage')+metric('Validation status','Historical','No prospective claim')+'</section>'
    glossary=[
        {'ID':'persistence','model':'Latest admissible directional limit','role':'Primary benchmark'},
        {'ID':'seasonal_daily / weekly','model':'Same half-hour one day / one week earlier','role':'Seasonal benchmarks'},
        {'ID':'T0','model':'Shared regularized ridge with base calendar terms','role':'Shared-model control'},
        {'ID':'T1','model':'Profile-supported daily Fourier ridge','role':'Richer mean diurnal shape'},
        {'ID':'T2','model':'Five-period coefficient-deviation ridge','role':'Discrete delivery-period sensitivity'},
        {'ID':'T3','model':'Smooth daily driver-interaction ridge','role':'Smooth delivery-time sensitivity'},
        {'ID':'T4','model':'Out-of-fold shared forecast plus period residual correction','role':'Cautious specialization'},
        {'ID':'T5','model':'Support-gated period specialists with boundary blending','role':'Separate-model challenger'},
        {'ID':'T6','model':'Shallow LightGBM absolute-error correction','role':'Nonlinear challenger'},
        {'ID':'O1 / O2 / O3 / O4','model':'NOS burden / transitions / mapped constraint mechanisms / revision and recall state','role':'Cumulative outage ablations'},
        {'ID':'OX','model':'Restricted outage × room, pressure and delivery-time interactions','role':'Combined-mechanism test'},
        {'ID':'DR-NMAE','model':'Directional-reference percentage-error tuning','role':'Bounded challenger; MAE still selects the main policy'}]
    body+='<section><h2>Models used</h2>'+table(glossary)+'</section>'
    records=[]; all_frames=[]
    for result,path in zip(results,paths):
        f=pd.read_parquet(path.parent/'predictions.parquet')
        f['fold']=result['fold']['name'];f['target']=result['target'];f['band']=result['band']
        f['selected_prediction']=f[result['winner']]
        all_frames.append(f)
        for score in result['scores']:
            records.append({'fold':result['fold']['name'],'target':result['target'],'band':result['band'],
                'model':score['model'],'selected':score['selected'],'MAPE ≥50 (%)':score['mape_50'],
                'MAPE coverage':score['mape_50_coverage'],'MAE (MW; origin-balanced)':score['weighted_mae'], 'DR-NMAE (%)':score.get('dr_nmae'),
                '>100 MW overstatement':score['over100'],'>200 MW overstatement':score['over200']})
    body+='<section id="results"><h2>Model results</h2><p>Selection occurs before evaluation. Tables identify the selected policy separately from the best observed evaluation score.</p>'
    aggregate=[]
    rolling_frames=[f for f,r in zip(all_frames,results) if r['fold']['protocol']=='rolling']
    combined=pd.concat(rolling_frames,ignore_index=True)
    for (target,band),f in combined.groupby(['target','band']):
        for model in ['persistence','T0_mae','selected_prediction']:
            if model not in f or f[model].isna().any():continue
            score=metrics(f.actual.to_numpy(),f[model].to_numpy(),f.reference.to_numpy(),origin_weights(f.origin))
            aggregate.append({'target':target,'band':band,'policy':model,'MAPE ≥50 (%)':score['mape_50'],
                              'coverage':score['mape_50_coverage'],'MAE (MW; origin-balanced)':score['weighted_mae'],'DR-NMAE (%)':score['dr_nmae'],'rows':len(f)})
    fixed_rows=[]
    fixed_frames=[f for f,r in zip(all_frames,results) if r['fold']['protocol']=='fixed']
    if fixed_frames:
        fixed_frame=pd.concat(fixed_frames,ignore_index=True)
        for (target,band),f in fixed_frame.groupby(['target','band']):
            for model in ('persistence','T0_mae','selected_prediction'):
                score=metrics(f.actual.to_numpy(),f[model].to_numpy(),f.reference.to_numpy(),origin_weights(f.origin))
                fixed_rows.append({'target':target,'band':band,'policy':model,'MAPE ≥50 (%)':score['mape_50'],
                    'MAPE coverage':score['mape_50_coverage'],'MAE (MW; origin-balanced)':score['weighted_mae']})
    period_rows=[]
    for (target,band,period),f in combined.groupby(['target','band','period']):
        for model in ('persistence','T0_mae','selected_prediction'):
            if model not in f:continue
            score=metrics(f.actual.to_numpy(),f[model].to_numpy(),f.reference.to_numpy(),origin_weights(f.origin))
            period_rows.append({'target':target,'band':band,'delivery period':PERIODS[int(period)],'policy':model,
                'MAPE ≥50 (%)':score['mape_50'],'MAPE coverage':score['mape_50_coverage'],
                'MAE (MW; origin-balanced)':score['weighted_mae'],'rows':len(f)})
    period_frame=pd.DataFrame(period_rows);period_verdict=[]
    for keys,f in period_frame.groupby(['target','band','delivery period']):
        values=f.set_index('policy')['MAE (MW; origin-balanced)']
        if {'selected_prediction','T0_mae'}.issubset(values.index):
            gain=1-values['selected_prediction']/values['T0_mae']
            period_verdict.append({'target':keys[0],'band':keys[1],'delivery period':keys[2],
                'incremental skill vs T0':gain,'assessment':'specialization improves' if gain>0 else 'shared T0 is better'})
    body+=table(aggregate)+'<h3>Fixed-split sensitivity · reported separately</h3>'+table(fixed_rows)
    body+='<h3>Delivery-period results</h3>'+table(period_rows)
    body+='<h3>Does specialization improve on the shared model?</h3>'+table(period_verdict)
    body+='<details><summary>Every evaluated model and fold</summary>'+table(records)+'</details></section>'
    curve_scores=[];curve_charts='';boundary_rows=[]
    for path in sorted((root/'curves').glob('*/*/result.json')):
        result=json.loads(path.read_text());f=pd.read_parquet(path.parent/'predictions.parquet')
        score=result['score'];curve_scores.append({'fold':result['fold']['name'],'target':result['target'],
            'MAPE ≥50 (%)':score['mape_50'],'MAPE coverage':score['mape_50_coverage'],'MAE (MW)':score['mae'],
            'RMSE (MW)':score['rmse'],'bias (MW)':score['bias'],'rows':result['rows'],'daily origins':result['origins']})
        boundary_rows.extend([{'fold':result['fold']['name'],'target':result['target'],**row} for row in result['boundary_summary']])
        trace=f[f.origin.eq(f.origin.min())]
        fig=go.Figure();fig.add_trace(go.Scatter(x=trace.delivery,y=trace.upper95,line=dict(width=0),showlegend=False,hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=trace.delivery,y=trace.lower95,name='95% interval',fill='tonexty',line=dict(width=0),fillcolor='rgba(86,150,185,.2)'))
        fig.add_trace(go.Scatter(x=trace.delivery,y=trace.actual,name='Actual',line=dict(color='#282b30',width=2)))
        fig.add_trace(go.Scatter(x=trace.delivery,y=trace.forecast,name='Finalist forecast',line=dict(color='#b34d3d',width=2)))
        style_plotly(fig,f'{result["fold"]["name"]} · {result["target"]} · 336-step curve',height=520)
        fig.update_yaxes(title='Directional limit (MW)');fig.update_xaxes(title='Delivery interval ending · NEM time')
        plotted=metrics(trace.actual.to_numpy(),trace.forecast.to_numpy(),trace.reference.to_numpy())
        curve_charts+='<details><summary>'+html.escape(result['fold']['name']+' · '+result['target'])+'</summary>'+figure_html(lazy_chart(fig),
            'First eligible evaluation-day issue','Each half-hour lead is routed through its frozen horizon-band policy; lines do not splice later issues.')
        curve_charts+=table([{'MAPE ≥50 (%)':plotted['mape_50'],'MAPE coverage':plotted['mape_50_coverage'],
            'ordinary nonzero MAPE (%)':plotted['mape_0'],'MAE (MW)':plotted['mae'],'RMSE (MW)':plotted['rmse'],
            'bias (MW)':plotted['bias'],'>100 MW overstatement':plotted['over100'],'>200 MW overstatement':plotted['over200'],
            'rows':plotted['n']}])+'</details>'
    body+='<section><h2>Full 336-step finalist curves</h2>'+table(curve_scores)+curve_charts
    body+='<h3>Boundary-jump audit</h3>'+table(boundary_rows)+'</section>'
    bridge=[]
    for path in sorted((root/'bridge').glob('*/*/result.json')):
        result=json.loads(path.read_text())
        for row in result['selection']:
            bridge.append({'fold':result['fold']['name'],'target':result['target'],'sampling':row['sampling'],
                'selected legacy policy':row['winner'],'MAPE ≥50 (%)':row['scores']['mape_50'],
                'MAPE coverage':row['scores']['mape_50_coverage'],'MAE (MW)':row['scores']['mae'],
                'training pairs':row['train_pairs']})
    body+='<section><h2>Corrected legacy-policy bridge</h2><p>This isolates the sampling change from the calendar ladder.</p>'+table(bridge)+'</section>'
    refinements=[];refinement_importance=[];refinement_shap=[];refinement_charts=''
    for path in sorted((root/'refinements').glob('*/*/result.json')):
        result=json.loads(path.read_text())
        for row in result['scores']:
            refinements.append({'fold':result['fold']['name'],'target':result['target'],'base NOS policy':result['base_nos_policy'],
                'refinement':row['model'],'selected':row['model']==result['winner'],'MAPE ≥50 (%)':row['mape_50'],
                'MAPE coverage':row['mape_50_coverage'],'MAE (MW; origin-balanced)':row['weighted_mae'],
                'training days':row['training_days']})
        predictions=pd.read_parquet(path.parent/'predictions.parquet')
        trace=predictions[predictions.lead.eq(predictions.lead.min())].copy()
        trace=trace[trace.origin.lt(trace.origin.min()+pd.Timedelta(days=7))]
        fig=go.Figure();fig.add_trace(go.Scatter(x=trace.delivery,y=trace.actual,name='Actual',line=dict(color='#282b30',width=2)))
        for name in result['selection']:
            fig.add_trace(go.Scatter(x=trace.delivery,y=trace[name],name=name,visible=True if name==result['winner'] else 'legendonly'))
        style_plotly(fig,f'{result["fold"]["name"]} · {result["target"]} · refinements',height=500)
        fig.update_yaxes(title='Directional limit (MW)');fig.update_xaxes(title='Delivery interval ending · NEM time')
        refinement_charts+=figure_html(lazy_chart(fig),'Actual versus refinement forecasts · first available week',
            'The refinement is selected on the selection partition; the chart is held-out evaluation.')
        explanation=path.parent/'explanations.json'
        if explanation.exists():
            evidence=json.loads(explanation.read_text())
            refinement_importance.extend([{'fold':result['fold']['name'],'target':result['target'],
                **{k:v for k,v in row.items() if k!='replicates'}} for row in evidence['importance']])
            for row in evidence['shap']:
                sf=pd.read_parquet(path.parent/row['artifact'])
                top=sf.groupby('feature').shap_mw.apply(lambda s:float(np.mean(abs(s)))).sort_values(ascending=False).head(8)
                refinement_shap.extend([{'fold':result['fold']['name'],'target':result['target'],'model':row['model'],
                    'feature':feature,'mean |SHAP| (MW)':value,'reconstruction error':row['max_reconstruction_error_mw']} for feature,value in top.items()])
    body+='<section><h2>Bounded refinements</h2><p>Lead-conditioned aggregate pressure and recent-history windows are assessed after the calendar/NOS recipe is frozen. Cross-connector pooling awaits QNI.</p>'+table(refinements)
    body+='<h3>Refinement actual-versus-forecast charts</h3>'+refinement_charts
    body+='<h3>Refinement grouped feature importance</h3>'+table(refinement_importance)
    body+='<h3>Refinement SHAP decomposition · leading contributions</h3>'+table(refinement_shap)+'</section>'
    body+='<section id="models"><h2>Models, actual limits and explanations</h2>'
    all_importance=[]
    options=''.join(f'<option value="cell-{i}">{html.escape(r["fold"]["name"]+" · "+r["target"]+" · band "+str(r["band"]))}</option>' for i,r in enumerate(results))
    body+='<label for="cell-picker">Result cell </label><select id="cell-picker">'+options+'</select>'
    for i,(result,path,f) in enumerate(zip(results,paths,all_frames)):
        folder=path.parent
        body+=f'<article class="result-cell" id="cell-{i}"'+(' hidden' if i else '')+'>'
        body+=f'<h3>{html.escape(result["fold"]["name"]+" · "+result["target"])} · band {result["band"]}</h3>'
        body+=f'<p>Selection-frozen policy: <strong>{html.escape(result["winner"])}</strong>. Input track: {html.escape(result["information_track"])}.</p>'
        # Exact fixed-lead observations, plotted without conflating forecasts from different origins.
        trace=f[f.lead.eq(f.lead.min())].copy()
        trace=trace[trace.origin.lt(trace.origin.min()+pd.Timedelta(days=7))]
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=trace.delivery,y=trace.actual,name='Actual directional limit',line=dict(color='#282b30',width=2)))
        for name in ['persistence']+list(result['search']):
            fig.add_trace(go.Scatter(x=trace.delivery,y=trace[name],name=name,visible=True if name==result['winner'] else 'legendonly'))
        style_plotly(fig,'Actual versus forecast limits · fixed lead',height=510);fig.update_yaxes(title='Directional limit (MW)')
        fig.update_xaxes(title='Delivery interval ending · NEM time')
        body+=figure_html(lazy_chart(fig),f'First available week · lead {int(trace.lead.iloc[0])*30} minutes',
                          'Toggle model traces in the legend. The following table uses exactly these plotted observations.')
        chart_rows=[]
        for name in ['persistence']+list(result['search']):
            m=metrics(trace.actual.to_numpy(),trace[name].to_numpy(),trace.reference.to_numpy())
            chart_rows.append({'model':name,'MAPE ≥50 (%)':m['mape_50'],'coverage':m['mape_50_coverage'],'MAE (MW)':m['mae'],'DR-NMAE (%)':m['dr_nmae'],'rows':len(trace)})
        body+=table(chart_rows)
        body+='<details><summary>Hyperparameters, data profile and search history</summary>'
        for name,search in result['search'].items():
            body+=f'<h4>{html.escape(name)}</h4><p>{html.escape(search["stop"])}</p>'
            body+='<pre>'+html.escape(json.dumps({'chosen':search['chosen'],'actual_parameters':search['actual_parameters'],
                'data_shape':search.get('data_shape'),'profile':search['profile']},indent=2))+'</pre>'
            body+=table([{'validation_loss':r['loss'],'seconds':r['seconds'],'parameters':json.dumps(r['settings'])} for r in search['history']])
        body+='</details><h4>Uncertainty calibration on the same point model</h4>'+table(result['intervals'])
        explanations=folder/'explanations.json'
        if explanations.exists():
            evidence=json.loads(explanations.read_text())
            all_importance.extend([{**r,'fold':result['fold']['name'],'target':result['target'],'band':result['band']} for r in evidence['importance']])
            body+='<h4>Grouped feature importance</h4>'+table([{k:v for k,v in r.items() if k!='replicates'} for r in evidence['importance']])
            body+='<h4>SHAP decomposition</h4>'+table(evidence['shap'])
            for status in evidence['shap']:
                name=status['model']; shap_frame=pd.read_parquet(folder/f'{name}_shap.parquet')
                case=shap_frame[shap_frame.case.eq(0)].copy().sort_values('shap_mw',key=abs,ascending=False)
                top=case.head(12); remainder=case.iloc[12:].shap_mw.sum()
                values=[case.base_mw.iloc[0]]+top.shap_mw.tolist()+[remainder,case.prediction_mw.iloc[0]]
                labels=['Expected prediction']+top.feature.tolist()+['Other features','Forecast']
                chart=go.Figure(go.Waterfall(x=labels,y=values,measure=['absolute']+['relative']*(len(values)-2)+['total']))
                style_plotly(chart,f'{name} · full forecast decomposition',height=500);chart.update_yaxes(title='MW');chart.update_xaxes(tickangle=-35)
                body+=figure_html(lazy_chart(chart),name+' · diagnostic case 0',status['method'])
        else:body+='<p>Explanations pending. This cell is not yet a completed handoff.</p>'
        body+='</article>'
    body+='</section><script>function renderVisible(){document.querySelectorAll(".lazy-plot").forEach(x=>{if(!x.closest("[hidden],details:not([open])")&&!x.dataset.rendered){let f=JSON.parse(x.querySelector("script").textContent);x.dataset.rendered="1";Plotly.newPlot(x,f.data,f.layout,{responsive:true});}});}document.getElementById("cell-picker").addEventListener("change",function(){document.querySelectorAll(".result-cell").forEach(x=>x.hidden=x.id!==this.value);renderVisible();window.dispatchEvent(new Event("resize"));});document.addEventListener("toggle",function(){renderVisible();window.dispatchEvent(new Event("resize"));},true);renderVisible();</script>'
    body+='<section id="fundamentals"><h2>Feature relevance to fundamentals</h2>'
    hypotheses={'observed_history':('Recent limits and changes','Current topology and operating conditions persist, especially at short leads.'),
        'network_state':('Headroom, candidate competition and setter state','Constraint geometry changes which equation can set each directional limit.'),
        'generator_pressure':('Aggregate generator tightening and relief','Generation patterns alter the LHS/RHS balance and available transfer capability.'),
        'calendar':('Delivery-time cycles','Demand, renewable output and unit commitment share daily patterns; calendar remains a proxy.'),
        'horizon':('Forecast lead','Uncertainty and persistence decay vary with lead.'),
        'quality':('Coverage and reconstruction quality','Missing or inconsistent state can mimic a physical regime change.'),
        'scheduled_outage':('Scheduled NOS exposure','Equipment unavailability changes the available constraint set and can reduce transfer capability.')}
    fundamentals=[]
    if all_importance:
        evidence=pd.DataFrame(all_importance).groupby(['model','group']).mae_degradation.mean().reset_index()
        for r in evidence.itertuples():
            label,mechanism=hypotheses.get(r.group,(r.group,'Model input group; mechanism requires review.'))
            verdict='retain for testing' if r.mae_degradation>0 else 'review redundancy or instability'
            fundamentals.append({'model':r.model,'feature group':label,'mean held-out MAE degradation (MW)':r.mae_degradation,
                                 'fundamental mechanism':mechanism,'assessment':verdict})
    body+=table(fundamentals)+'<p>Permutation and SHAP measure model dependence. They do not establish that a feature caused a physical limit change.</p></section>'
    body+='<section id="nos"><h2>NOS outage evidence</h2>'
    for filename in ['coverage_audit.json','mapping_audit.json','nos_feasibility.json']:
        p=root/'nos'/filename
        body+=f'<h3>{html.escape(filename)}</h3>'
        body+=('<pre>'+html.escape(p.read_text())+'</pre>') if p.exists() else '<p>Pending; no result claimed.</p>'
    impact=root/'nos/impact/full_development/status.json'
    if impact.exists():
        status=json.loads(impact.read_text())
        body+='<h3>Pre-model matched outage assessment</h3>'+table(status.get('highest_impact',[]))
        body+=f'<p>O5 outcome-weighted feature gate: <strong>{"open" if status.get("O5_gate") else "closed"}</strong>. {html.escape(status.get("reason",""))}</p>'
    else:body+='<p>Matched outage-impact analysis pending; no highest-effect ranking is claimed.</p>'
    nos_scores=[];nos_importance=[];nos_shap=[];nos_charts='';nos_verdict=[]
    for path in sorted((root/'nos_models').glob('*/*/result.json')):
        result=json.loads(path.read_text())
        predictions=pd.read_parquet(path.parent/'predictions.parquet')
        trace=predictions[predictions.lead.eq(predictions.lead.min())].copy()
        trace=trace[trace.origin.lt(trace.origin.min()+pd.Timedelta(days=7))]
        fig=go.Figure();fig.add_trace(go.Scatter(x=trace.delivery,y=trace.actual,name='Actual',line=dict(color='#282b30',width=2)))
        for name in predictions.columns:
            if name.startswith(('T0_','T2_','T3_','T6_')):
                fig.add_trace(go.Scatter(x=trace.delivery,y=trace[name],name=name,
                    visible=True if name==result['winner'] else 'legendonly'))
        style_plotly(fig,f'{result["fold"]["name"]} · {result["target"]} · NOS models',height=500)
        fig.update_yaxes(title='Directional limit (MW)');fig.update_xaxes(title='Delivery interval ending · NEM time')
        nos_charts+='<details><summary>'+html.escape(result['fold']['name']+' · '+result['target'])+'</summary>'
        nos_charts+=figure_html(lazy_chart(fig),'Actual versus source-common NOS forecasts · first available week',
            'The winning recipe was selected before evaluation; toggle other models in the legend.')
        local=[]
        for score in result['scores']:
            common=score['common_source']
            row={'fold':result['fold']['name'],'target':result['target'],'model':score['model'],
                'selected':score['model']==result['winner'],'MAPE ≥50 (%)':common['mape_50'],
                'MAPE coverage':common['mape_50_coverage'],'MAE (MW; origin-balanced)':common['weighted_mae'],
                'known evaluation fraction':score['known_evaluation_fraction']}
            nos_scores.append(row);local.append(row)
        lookup={row['model']:row for row in local};calendar=result['winner'].split('_',1)[0]
        chosen=lookup[result['winner']];control=lookup[calendar+'_O0']
        nos_verdict.append({'fold':result['fold']['name'],'target':result['target'],'selected policy':result['winner'],
            'selected MAE':chosen['MAE (MW; origin-balanced)'],'same-family O0 MAE':control['MAE (MW; origin-balanced)'],
            'NOS skill vs O0':1-chosen['MAE (MW; origin-balanced)']/control['MAE (MW; origin-balanced)'],
            'verdict':'NOS recipe selected' if not result['winner'].endswith('_O0') else 'no NOS recipe selected'})
        nos_charts+=table(local)+'</details>'
        explanation=path.parent/'explanations.json'
        if explanation.exists():
            evidence=json.loads(explanation.read_text())
            nos_importance.extend([{'fold':result['fold']['name'],'target':result['target'],
                **{k:v for k,v in row.items() if k!='replicates'}} for row in evidence['importance']])
            for row in evidence['shap']:
                sf=pd.read_parquet(path.parent/row['artifact'])
                top=(sf.groupby('feature').shap_mw.apply(lambda s:float(np.mean(abs(s))))
                     .sort_values(ascending=False).head(8))
                nos_shap.extend([{'fold':result['fold']['name'],'target':result['target'],'model':row['model'],
                    'feature':feature,'mean |SHAP| (MW)':value,'reconstruction error (MW)':row['max_reconstruction_error_mw']}
                    for feature,value in top.items()])
    body+='<h3>NOS point-model ablations · common source</h3>'+table(nos_scores)
    body+='<h3>NOS incremental verdict by held-out fold</h3>'+table(nos_verdict)
    body+='<h3>NOS actual-versus-forecast charts and metrics</h3>'+nos_charts
    body+='<h3>NOS grouped feature importance</h3>'+table(nos_importance)
    body+='<h3>NOS SHAP decomposition · leading contributions</h3>'+table(nos_shap)
    body+='</section><section id="risk"><h2>Contraction warnings</h2>'
    risk=[];risk_importance=[];risk_shap=[]
    for path in sorted((root/'risk').glob('*/result.json')):
        r=json.loads(path.read_text())
        for s in r['scores']:
            risk.append({'fold':r['fold']['name'],'model':s['family'],'direction':s['direction'],
                         'selected':s['family']==r['winner'],'recall':s['events']['recall'],
                         'false alarms/day':s['events']['false_alarms_per_day'],'incidents':s['events']['incidents'],
                         'Brier':s['probability']['brier']})
        explanation=path.parent/'explanations.json'
        if explanation.exists():
            evidence=json.loads(explanation.read_text())
            risk_importance.extend([{'fold':r['fold']['name'],**row} for row in evidence['importance']])
            for row in evidence['shap']:
                sf=pd.read_parquet(path.parent/f'{row["model"]}_shap.parquet')
                top=sf.groupby('feature').shap_log_odds.apply(lambda s:float(np.mean(abs(s)))).sort_values(ascending=False).head(8)
                risk_shap.extend([{'fold':r['fold']['name'],'model':row['model'],'feature':feature,
                    'mean |SHAP| (calibrated log odds)':value,'reconstruction error':row['reconstruction_error']} for feature,value in top.items()])
    for path in sorted((root/'nos_risk').glob('*/result.json')):
        r=json.loads(path.read_text());winner=tuple(r['winner'])
        for s in r['scores']:
            risk.append({'fold':r['fold']['name'],'model':s['family']+' · '+s['recipe'],'direction':s['direction'],
                         'selected':(s['recipe'],s['family'])==winner,'recall':s['events']['recall'],
                         'false alarms/day':s['events']['false_alarms_per_day'],'incidents':s['events']['incidents'],
                         'Brier':s['probability']['brier']})
        explanation=path.parent/'explanations.json'
        if explanation.exists():
            evidence=json.loads(explanation.read_text())
            risk_importance.extend([{'fold':r['fold']['name'],**row} for row in evidence['importance']])
            for row in evidence['shap']:
                sf=pd.read_parquet(path.parent/row['artifact'])
                top=sf.groupby('feature').shap_log_odds.apply(lambda s:float(np.mean(abs(s)))).sort_values(ascending=False).head(8)
                risk_shap.extend([{'fold':r['fold']['name'],'model':row['model'],'feature':feature,
                    'mean |SHAP| (calibrated log odds)':value,'reconstruction error':row['max_reconstruction_error']} for feature,value in top.items()])
    body+=table(risk)+'<h3>Risk-model grouped feature importance</h3>'+table(risk_importance)
    body+='<h3>Risk-model SHAP decomposition · leading contributions</h3>'+table(risk_shap)
    body+='</section><section id="verdict"><h2>Model-choice verdict</h2>'
    verdict=[]
    for (target,band),f in combined.groupby(['target','band']):
        weights=origin_weights(f.origin)
        chosen=metrics(f.actual.to_numpy(),f.selected_prediction.to_numpy(),f.reference.to_numpy(),weights)
        persistence=metrics(f.actual.to_numpy(),f.persistence.to_numpy(),f.reference.to_numpy(),weights)
        shared=metrics(f.actual.to_numpy(),f.T0_mae.to_numpy(),f.reference.to_numpy(),weights) if 'T0_mae' in f else None
        skill=1-chosen['weighted_mae']/persistence['weighted_mae']
        incremental=None if shared is None else 1-chosen['weighted_mae']/shared['weighted_mae']
        verdict.append({'target':target,'band':band,'selection-frozen routed MAE':chosen['weighted_mae'],
            'MAPE ≥50 assessment':chosen['mape_50'],'persistence MAE':persistence['weighted_mae'],
            'shared T0 MAE':shared['weighted_mae'] if shared else None,'skill vs persistence':skill,
            'incremental skill vs T0':incremental,
            'diurnal verdict':'specialization improves on T0' if incremental is not None and incremental>0 else 'specialization does not improve on T0',
            'historical gate':'passes 5% vs persistence' if skill>=.05 else 'does not pass 5% vs persistence',
            'live status':'not operationally eligible'})
    body+=table(verdict)
    statistics=root/'statistics.json'
    if statistics.exists():body+='<h3>Paired statistical comparisons</h3><pre>'+html.escape(statistics.read_text())+'</pre>'
    final=root/'final/catalogue.json'
    if final.exists():
        bundles=[]
        for row in json.loads(final.read_text()):
            manifest=root/Path(row['path']).parent/'manifest.json';detail=json.loads(manifest.read_text())
            bundles.append({**row,'selection MAE by candidate':json.dumps(detail['selection_mae']),
                'exact fitted parameters':json.dumps(detail['parameters']),'schema columns':len(detail['schema']),
                'reload parity':detail['reload_parity'],'operationally eligible':detail['operationally_eligible']})
        body+='<h3>Trained research bundles and parameters</h3>'+table(bundles)
    else:body+='<p>Final refit bundles are pending; no trained handoff is claimed.</p>'
    body+='</section>'
    body+='<section id="methods"><h2>Methods and limits of the evidence</h2><p>Rolling chronological partitions separate training, selection, calibration, alert thresholds and evaluation. Inputs use the declared retrospective information track; label maturity includes a 30-minute allowance. MAPE is assessment-only. Directional-reference percentage loss uses a training-fitted floor and the directional limit known at origin. Feature importance and SHAP are predictive diagnostics, not causal outage effects.</p><p>Generator pressure represents the retained aggregate state, not a verified forward generating-unit availability forecast. Any NOS conclusion is conditional on that information set. Prospective confirmation is pending.</p></section><script>renderVisible();</script>'
    result_path=output/'vni_diurnal_nos_model_report.html';result_path.write_text(render_page('VNI directional-limit research',body),encoding='utf-8')
    pd.DataFrame(records).to_csv(output/'model_results.csv',index=False)
    evidence_paths=set(paths)
    for pattern in ('curves/*/*/result.json','bridge/*/*/result.json','refinements/*/*/result.json','nos_models/*/*/result.json','risk/*/result.json','nos_risk/*/result.json',
                    'nos/coverage_audit.json','nos/mapping_audit.json','nos/nos_feasibility.json',
                    'nos/impact/full_development/status.json','statistics.json','final/*/*/manifest.json'):
        evidence_paths.update(root.glob(pattern))
    (output/'build.json').write_text(json.dumps(clean({'sources':[{'path':str(p.relative_to(ROOT)),'sha256':digest(p)} for p in sorted(evidence_paths)],
                'generator_sha256':digest(__file__),'completed_cells':len(results),'report_sha256':digest(result_path)}),indent=2)+'\n')
    print(result_path)


if __name__=='__main__':build()
