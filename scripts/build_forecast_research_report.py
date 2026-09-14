"""Extract an auditable experiment snapshot and render a research narrative offline.

python scripts/build_forecast_research_report.py --extract
python scripts/build_forecast_research_report.py
"""
from pathlib import Path
import sys
import json
import argparse
import importlib.metadata
from html import escape
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from nemic.experiments.core import load_config, digest, clean
from nemic.experiments.reports import collect
from scripts.report_theme.report_theme import hero,metric,finding,figure_html,style_plotly,render_page

SNAPSHOT=ROOT/'docs/data/forecast_experiment_research_snapshot.json'
OUTPUT=ROOT/'docs/html/vni_qni_forecast_experiment_research.html'
BANDS=['0.5–6 h','>6–24 h','>1–3 days','>3–7 days']
TARGETS={'flow':'Flow','export':'Mean export limit','import':'Mean import limit','export_tight':'Minimum export limit','import_tight':'Minimum import limit'}


def aggregate(frame,keys,metrics):
    out=[]
    for group,f in frame.groupby(keys,dropna=False,sort=True):
        if not isinstance(group,tuple):group=(group,)
        r=dict(zip(keys,group));r['n']=int(f.n.sum())
        for col in metrics:
            if col not in f:continue
            good=f[col].notna()&f.n.gt(0)
            if not good.any():r[col]=None;continue
            values=f.loc[good,col].astype(float)
            r[col]=float(np.sqrt(np.average(values**2,weights=f.loc[good,'n']))) if col=='rmse' else float(np.average(values,weights=f.loc[good,'n']))
        out.append(r)
    return out


def extract():
    c=load_config();run=c['_run'];trials,stale,inv=collect(c)
    if len(trials)!=130 or stale:raise ValueError('Research requires all 130 verified current trials')
    sources=[{'path':str((run/'inventory.json').relative_to(ROOT)),'sha256':digest(run/'inventory.json')}]
    for t in trials:
        p=run/'trials'/t['job']/'result.json';sources.append({'path':str(p.relative_to(ROOT)),'sha256':digest(p)})
    numeric=[t for t in trials if '/band' in t['job']]
    scores=pd.DataFrame([r for t in numeric for r in t['scores']])
    selected=scores[scores.selected].copy();selected['model']='selected_policy'
    both=pd.concat([scores,selected],ignore_index=True)
    metrics=['mae','rmse','bias','reference_mae']
    overall=aggregate(both,['ic','protocol','target','model'],metrics)
    band=aggregate(both,['ic','protocol','target','model','band'],metrics)
    monthly=both[(both.protocol=='rolling')&(both.target=='flow')].to_dict('records')
    quant=pd.DataFrame([r for t in numeric for r in t['quantiles']])
    qa=aggregate(quant,['ic','protocol','target','model'],['wis','coverage_95','coverage_80','coverage_50','width_95','width_80','width_50'])
    qa_band=aggregate(quant,['ic','protocol','target','model','band'],['wis','coverage_80','width_80'])
    slices=pd.DataFrame([r for t in numeric for r in t['slices'] if r['target']=='flow' and (r.get('selected') or r['model']=='persistence')])
    selected_slices=slices[slices.selected].copy();selected_slices['model']='selected_policy'
    slices=pd.concat([slices[slices.model.eq('persistence')],selected_slices],ignore_index=True)
    slices=slices.drop_duplicates(['ic','protocol','fold','band','slice','value','model'])
    sa=aggregate(slices,['ic','protocol','band','slice','value','model'],['mae','bias'])
    events=[r for t in trials if t['job'].endswith('/events') for r in t['scores']]
    secondary=pd.DataFrame([r for t in trials for r in t.get('secondary',[]) if 'n' in r])
    secondary_summary=aggregate(secondary,['ic','protocol','task','model'],['brier','log_loss','base_rate'])
    thresholds=[{'ic':t['job'].split('/')[0],'fold':t['fold']['name'],'direction':direction,**value}
        for t in trials if t['job'].endswith('/events') for direction,value in t['thresholds'].items()]
    er=[];reliability=[];em=[];absolute=[]
    for protocol in ['fixed','rolling']:
        for ic in ['VNI','QNI']:
            allrows=[r for r in events if r['ic']==ic and r['protocol']==protocol]
            names=sorted({r['model'] for r in allrows})+['selected_policy']
            for name in names:
                rows=[r for r in allrows if r.get('selected')] if name=='selected_policy' else [r for r in allrows if r['model']==name]
                if not rows:continue
                # Directions share calendar days. Sum false alarms, count each fold's days once.
                days=sum(max(r['incidents']['days'] for r in rows if r['fold']==fold) for fold in {r['fold'] for r in rows})
                tp=sum(r['incidents']['tp'] for r in rows);fp=sum(r['incidents']['fp'] for r in rows);n=sum(r['incidents']['incidents'] for r in rows)
                pn=sum(r['probability']['n'] for r in rows)
                leads=[x for r in rows for x in r['incidents']['leads']]
                er.append({'ic':ic,'protocol':protocol,'model':name,'incidents':n,'tp':tp,'fp':fp,'fn':n-tp,'days':days,
                    'recall':tp/n if n else None,'false_per_day':fp/days,'precision':tp/(tp+fp) if tp+fp else None,
                    'brier':sum(r['probability']['brier']*r['probability']['n'] for r in rows)/pn,
                    'median_lead':float(np.median(leads)) if leads else None})
                for level in ['100','200','400']:
                    rr=[r['absolute'][level] for r in rows];at=sum(r['tp'] for r in rr);an=sum(r['incidents'] for r in rr)
                    absolute.append({'ic':ic,'protocol':protocol,'model':name,'drop_mw':int(level),'incidents':an,'recall':at/an if an else None,'false_per_day':sum(r['fp'] for r in rr)/days})
                if name=='selected_policy':
                    for fold in sorted({r['fold'] for r in rows}):
                        fr=[r for r in rows if r['fold']==fold];nn=sum(r['incidents']['incidents'] for r in fr)
                        em.append({'ic':ic,'protocol':protocol,'fold':fold,'model':fr[0]['model'],
                            'recall':sum(r['incidents']['tp'] for r in fr)/nn if nn else None,
                            'false_per_day':sum(r['incidents']['fp'] for r in fr)/max(r['incidents']['days'] for r in fr)})
                    bins={}
                    for r in rows:
                        for b in r['probability']['reliability']:
                            key=min(int(b['predicted']*10),9);bins.setdefault(key,[]).append(b)
                    for key,bs in sorted(bins.items()):
                        bn=sum(b['n'] for b in bs)
                        reliability.append({'ic':ic,'protocol':protocol,'bin':key,'n':bn,
                            'predicted':sum(b['predicted']*b['n'] for b in bs)/bn,'observed':sum(b['observed']*b['n'] for b in bs)/bn})
    pooled=json.loads((run/'pooled.json').read_text())
    if not pooled['complete'] or len(pooled['scores'])!=520:raise ValueError('Pooled comparison incomplete')
    pa=aggregate(pd.DataFrame(pooled['scores']),['ic','protocol','target','band'],['mae','rmse'])
    sources += [{'path':str((run/name).relative_to(ROOT)),'sha256':digest(run/name)} for name in ['pooled.json','aemo_benchmark.json']]
    # Paired block bootstrap across complete issue days, separately by connector and band.
    ci=[];cases=[]
    for ic in ['VNI','QNI']:
        for band_no in range(4):
            paths=sorted((run/'trials'/ic).glob(f'20*/band{band_no}/flow_predictions.parquet'))
            f=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
            err=(f.actual-f.prediction).abs();base=(f.actual-f.persistence).abs()
            dd=pd.DataFrame({'day':pd.to_datetime(f.origin).dt.normalize(),'err':err,'base':base,'n':1}).groupby('day').sum().sort_index()
            dates=pd.date_range(dd.index.min(),dd.index.max(),freq='D');a=dd.reindex(dates,fill_value=0).to_numpy()
            rng=np.random.default_rng(741);vals=[]
            for _ in range(1000):
                starts=rng.integers(0,len(a),int(np.ceil(len(a)/7)))
                ii=((starts[:,None]+np.arange(7))%len(a)).ravel()[:len(a)];sample=a[ii].sum(axis=0)
                vals.append(100*(1-sample[0]/sample[1]) if sample[1]>0 else np.nan)
            ci.append({'ic':ic,'band':band_no,'gain_pct':100*(1-err.sum()/base.sum()),'low':float(np.nanquantile(vals,.025)),'high':float(np.nanquantile(vals,.975)),
                'mae':float(err.mean()),'persistence_mae':float(base.mean()),'n':len(f),'issue_days':len(dd)})
            if band_no==0:
                # Deterministic high-error example: highest mean daily 30-minute lead error.
                half=f[f.lead.eq(1)].copy();half['error']=(half.actual-half.prediction).abs();half['day']=pd.to_datetime(half.origin).dt.normalize()
                worst=half.groupby('day').error.mean().idxmax();window=half[half.day.eq(worst)]
                cases.append({'ic':ic,'day':str(worst.date()),'selection':'Largest mean absolute error day at 30-minute lead in rolling evaluation',
                    'rows':window[['delivery','actual','prediction','persistence','q0.1','q0.9']].to_dict('records')})
    # Matched-sample AEMO comparison from original issues and saved selected-policy predictions.
    vint=pd.read_parquet(ROOT/'results/aemo_vintages.parquet');matched=[]
    for ic in c['connectors']:
        a=vint[vint.INTERCONNECTORID.eq(ic['id'])].copy().rename(columns={'h':'lead'})
        if a.duplicated(['origin','lead']).any():raise ValueError('Duplicate original AEMO origin/lead')
        for target in ['flow','export','import']:
            files=sorted((run/'trials'/ic['name']).glob(f'20*/band*/{target}_predictions.parquet'))
            f=pd.concat([pd.read_parquet(p) for p in files],ignore_index=True)
            joined=f.merge(a[['origin','lead','issued','aemo_'+target]],on=['origin','lead'],how='inner',validate='one_to_one')
            if (pd.to_datetime(joined.issued)>pd.to_datetime(joined.origin)).any():raise ValueError('AEMO issue after origin')
            joined=joined.dropna(subset=['actual','prediction','persistence','aemo_'+target])
            for b,sub in joined.groupby('band'):
                for model,col in [('AEMO original','aemo_'+target),('Selected retrospective','prediction'),('Persistence','persistence')]:
                    matched.append({'ic':ic['name'],'target':target,'band':int(b),'model':model,'n':len(sub),'mae':float((sub.actual-sub[col]).abs().mean()),
                        'first_origin':str(sub.origin.min()),'last_origin':str(sub.origin.max()),'max_lead_hours':float(sub.lead.max()/2)})
    aemo_path=ROOT/'results/aemo_vintages.parquet';sources.append({'path':str(aemo_path.relative_to(ROOT)),'sha256':digest(aemo_path)})
    snapshot={'campaign':c['campaign'],'data_end':c['end'],'jobs':len(trials),'score_cells':len(scores),'event_cells':len(events),'quantile_cells':len(quant),
        'overall':overall,'bands':band,'monthly_flow':monthly,'quantiles':qa,'quantile_bands':qa_band,'slices':sa,
        'events':er,'event_months':em,'reliability':reliability,'absolute':absolute,'secondary':secondary_summary,'thresholds':thresholds,'pooled':pa,'paired_gain_ci':ci,'cases':cases,'aemo_matched':matched,
        'linear_quantile_nonconverged_cells':int((~quant[quant.model.eq('linear')].linear_converged).sum()),
        'sources':sources,'source_fingerprint':inv['fingerprint'],'extractor_sha256':digest(Path(__file__)),
        'method':'Sample-weighted MAE; RMSE from weighted squared RMSE. Fixed and rolling remain separate. Events summed across directions with fold days counted once. Circular 7-day paired block bootstrap, 1,000 resamples, conditional on fitted models.'}
    SNAPSHOT.parent.mkdir(exist_ok=True);SNAPSHOT.write_text(json.dumps(clean(snapshot),separators=(',',':')),encoding='utf-8')
    return snapshot


def render(d):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from datetime import datetime,timezone
    overall=pd.DataFrame(d['overall']);bands=pd.DataFrame(d['bands']);events=pd.DataFrame(d['events'])
    rolling=overall[overall.protocol.eq('rolling')]
    def row(ic,model,target='flow',protocol='rolling'):
        return overall[overall.ic.eq(ic)&overall.model.eq(model)&overall.target.eq(target)&overall.protocol.eq(protocol)].iloc[0]
    def ev(ic,model='selected_policy'):
        return events[events.ic.eq(ic)&events.model.eq(model)&events.protocol.eq('rolling')].iloc[0]
    def gain(ic,target='flow'):
        return 100*(1-row(ic,'selected_policy',target).mae/row(ic,'persistence',target).mae)
    def para(text):return '<p>'+escape(text)+'</p>'
    def tbl(records,columns=None):
        f=pd.DataFrame(records)
        if columns:f=f.reindex(columns=columns)
        return '<div class="table-wrap" tabindex="0">'+f.to_html(index=False,escape=True,na_rep='—',float_format=lambda x:f'{x:,.2f}')+'</div>'
    chart_no=0
    def chart(fig,title,note,height=560):
        nonlocal chart_no
        chart_no+=1;style_plotly(fig,title,height)
        fig.update_layout(title=None,margin=dict(t=65,b=75),legend=dict(y=1.04,yanchor='bottom'))
        return figure_html(fig.to_html(full_html=False,include_plotlyjs=False,div_id=f'figure-{chart_no}',config={'responsive':True,'displaylogo':False}),f'Figure {chart_no}. {title}',note)
    body=hero('Empirical research · VNI and QNI','Better flows,','unfinished warnings',
        'What 130 forecasting jobs reveal about simple models, network features, sharp limit contractions and the remaining gap to operational forecasts.',
        ['September 2024–August 2026 input window','September 2025–August 2026 rolling evaluation','30 minutes–7 days','Historical development evidence'])
    body+='<nav>'+ ' · '.join(f'<a href="#{anchor}">{label}</a>' for anchor,label in [('summary','Findings'),('design','Study design'),('accuracy','Models'),('features','Features'),('limits','Limits'),('seasons','Seasonality'),('warnings','Warnings'),('uncertainty','Uncertainty'),('benchmarks','AEMO & pooling'),('cases','Failure examples'),('decision','Decisions'),('sources','Sources')])+'</nav>'
    body+='<div class="metrics">'+metric('VNI flow MAE improvement',f'{gain("VNI"):.1f}%','Selected policy vs persistence · rolling')+metric('QNI flow MAE improvement',f'{gain("QNI"):.1f}%','Selected policy vs persistence · rolling')+metric('VNI false warnings / day',f'{ev("VNI").false_per_day:.2f}','Both directions combined · budget 3')+metric('QNI false warnings / day',f'{ev("QNI").false_per_day:.2f}','Both directions combined · budget 3')+'</div>'
    body+='<section id="summary"><h2>Executive findings</h2>'
    body+=para(f'The selected forecasting policy reduces rolling flow MAE from {row("VNI","persistence").mae:.1f} to {row("VNI","selected_policy").mae:.1f} MW for VNI and from {row("QNI","persistence").mae:.1f} to {row("QNI","selected_policy").mae:.1f} MW for QNI. This supports continued model development. It does not establish that the reconstructed topology features are the source of the improvement, nor that the models are ready for live use.')
    body+='<div class="findings">'+finding(1,'Simple models provide a strong starting point',f'Lag-and-calendar ridge reaches {row("VNI","ridge_base").mae:.1f} MW on VNI and {row("QNI","ridge_base").mae:.1f} MW on QNI. Shallow boosting and validation-tuned blends improve the results further, but the largest initial gain comes before adding network features.')+finding(2,'Topology needs more selective engineering',f'Adding the full reconstructed state/pressure block to ridge changes flow MAE from {row("VNI","ridge_base").mae:.1f} to {row("VNI","ridge_full").mae:.1f} MW on VNI and {row("QNI","ridge_base").mae:.1f} to {row("QNI","ridge_full").mae:.1f} MW on QNI. More features are not automatically more useful.')+finding(3,'A useful warning system remains unfinished',f'The selected policies recall {100*ev("VNI").recall:.1f}% of VNI incidents and {100*ev("QNI").recall:.1f}% of QNI incidents, with {ev("VNI").false_per_day:.2f} and {ev("QNI").false_per_day:.2f} false warnings per day. Both exceed the agreed evaluation burden.')+'</div>'
    body+=para('The practical conclusion is to retain a simple baseline, keep a small nonlinear challenger, and evaluate mechanism features as targeted additions. AEMO forecast anchoring deserves priority: the original AEMO issues outperform the selected research policy on the matched flow samples. No learned model is promoted by this report.')+'</section>'
    body+='<section id="design"><h2>1. What was actually tested</h2>'
    body+=para('The original VNI and QNI constraint studies suggested that generator dispatch, equation coefficients, headroom and changes in the active constraint could explain flow direction and limit contractions. This campaign asks a narrower predictive question: do compact versions of those observations improve forecasts beyond information already present in recent flows and limits? A physical influence in a binding equation need not deliver incremental forecast skill if its effect is already visible in the observed flow or cannot be forecast ahead of time.')
    body+=tbl([
        {'Dimension':'Connectors','Specification':'VNI (VIC1-NSW1) and QNI (NSW1-QLD1), fitted separately; pooled ridge challenger'},
        {'Dimension':'Data and evaluation','Specification':'24 calendar months of source studies; fitting starts 8 Sep 2024. Rolling evaluation covers 12 months, Sep 2025–Aug 2026. This is not two years of out-of-sample performance.'},
        {'Dimension':'Targets','Specification':'Mean dispatch flow; mean export/import limits; minimum five-minute export/import limits within each half-hour'},
        {'Dimension':'Lead grid','Specification':'0.5, 1, 2, 4, 6, 12, 24, 36, 48, 72, 96, 120, 144 and 168 hours; issue every 30 minutes'},
        {'Dimension':'Validation','Specification':'Fixed split plus 12 expanding monthly folds; distinct selection, calibration, warning-threshold and evaluation partitions'},
        {'Dimension':'Experiment scale','Specification':f'{d["jobs"]} main jobs; {d["score_cells"]:,} numeric model cells; {d["event_cells"]} directional warning cells; {d["quantile_cells"]:,} quantile cells; 520 pooled cells'},
        {'Dimension':'Information tracks','Specification':'Retrospective lagged network/context features; original AEMO issue benchmark; explicitly future-actual oracle diagnostic'},
        {'Dimension':'Storage discipline','Specification':'10 GB additional campaign cap, 20 GB free reserve, scoped DISPATCHLOAD recovery, raw archives deleted after verification'}])
    body+=para('For the fixed protocol, training ends at September 2025, model selection uses September–November, calibration uses December–January, alert tuning uses February 2026, and evaluation uses March–August 2026. For each rolling evaluation month, the preceding three months supply selection, calibration and alert tuning in order; training expands before them. Model choices are made before evaluation. Previously studied evaluation periods remain development data, not a new untouched test set.')
    body+=para('All headline results below use the rolling protocol unless marked otherwise. MAE is weighted by the number of valid origin–lead pairs; an all-lead average is not an equal-weight average of horizon bands. RMSE is reconstructed from weighted squared RMSE. Fixed and rolling results overlap and are never combined. Reconstructed inputs are lagged by 30 minutes, but historical first-publication timing has not been verified. The splitting code purges by delivery timestamp; stricter availability and complete target-window audits remain appropriate before an operational claim.')+'</section>'
    body+='<section id="accuracy"><h2>2. The model ladder: how much complexity earns its place?</h2>'
    names=['persistence','seasonal_daily','seasonal_weekly','ridge_base','ridge_pressure','ridge_full','ridge_context','elastic_context','additive_context','regime_context','boost_base','boost_context','blend','selected_policy']
    labels=['Persistence','Daily seasonal','Weekly seasonal','Ridge · history','Ridge · pressure','Ridge · state + pressure','Ridge · context','Elastic net · context','Additive · context','Regime · context','Boost · history','Boost · context','Validation-tuned blend','Selected policy']
    fig=go.Figure()
    for ic in ['VNI','QNI']:fig.add_bar(name=ic,x=labels,y=[row(ic,n).mae for n in names])
    fig.update_yaxes(title='Flow MAE (MW)');fig.update_xaxes(tickangle=-35)
    body+=chart(fig,'Flow accuracy across the model ladder','Rolling, all 14 scored leads. “Selected policy” is the model chosen separately per fold/target/band using the earlier selection partition. The lowest evaluation bar is not a fresh model-selection rule.',660)
    body+=para(f'Ridge with only history and calendar terms improves on persistence by {100*(1-row("VNI","ridge_base").mae/row("VNI","persistence").mae):.1f}% for VNI and {100*(1-row("QNI","ridge_base").mae/row("QNI","persistence").mae):.1f}% for QNI. The blend reaches {row("VNI","blend").mae:.1f} and {row("QNI","blend").mae:.1f} MW. For QNI, the blend’s aggregate evaluation score is slightly better than the earlier-selected policy; that difference should not be used to retroactively replace historical choices. It is evidence for the next predeclared comparison.')
    body+=para('The seasonal baselines are weak on these aggregate lead-weighted results. Additive and regime expansions also fail to deliver a clear general flow advantage over the smaller ridge baseline. Here “additive” means quadratic spline terms within the implemented regression, and “regime” means interactions gated by training-standardized headroom. These results do not rule out different additive structures or physically specified regimes.')
    cr=pd.DataFrame(d['paired_gain_ci']);fig=go.Figure()
    for ic in ['VNI','QNI']:
        f=cr[cr.ic.eq(ic)].sort_values('band');fig.add_scatter(name=ic,mode='lines+markers',x=[BANDS[x] for x in f.band],y=f.gain_pct,error_y=dict(type='data',array=f.high-f.gain_pct,arrayminus=f.gain_pct-f.low))
    fig.add_hline(y=0,line_color='#66717e');fig.update_yaxes(title='MAE reduction vs persistence (%)')
    body+=chart(fig,'Improvement depends on forecast horizon','Selected policy; 95% intervals from 1,000 paired circular seven-day block resamples of issue days. Conditional on fitted models and the studied sample; not uncertainty over all possible model-selection decisions.')
    body+=para('VNI’s improvement is substantial in every band, with the strongest relative gains between six hours and three days. QNI’s short-horizon gain is smaller and its longer-horizon gain larger. This argues for connector- and horizon-specific deployment decisions. The day-block intervals support a persistence improvement for each displayed band, while retaining the historical-development limitation.')
    months=pd.DataFrame(d['monthly_flow']);fig=make_subplots(rows=1,cols=2,subplot_titles=['VNI','QNI'])
    for col,ic in enumerate(['VNI','QNI'],1):
        m=months[months.ic.eq(ic)&months.model.isin(['selected_policy','persistence'])]
        ma=pd.DataFrame(aggregate(m,['fold','model'],['mae'])).pivot(index='fold',columns='model',values='mae')
        fig.add_scatter(x=ma.index,y=100*(1-ma.selected_policy/ma.persistence),mode='lines+markers',name=ic,row=1,col=col)
    fig.update_yaxes(title='Flow MAE reduction (%)');fig.update_xaxes(tickangle=-45)
    body+=chart(fig,'Monthly stability of the selected policy','Rolling monthly evaluation. Month-boundary delivery purging reduces eligible long-horizon origins near each month end.')
    body+=tbl([{'IC':ic,'Protocol':protocol,'Persistence MAE (MW)':row(ic,'persistence',protocol=protocol).mae,'Selected MAE (MW)':row(ic,'selected_policy',protocol=protocol).mae,'Improvement (%)':100*(1-row(ic,'selected_policy',protocol=protocol).mae/row(ic,'persistence',protocol=protocol).mae)} for ic in ['VNI','QNI'] for protocol in ['rolling','fixed']])+'</section>'
    body+='<section id="features"><h2>3. Which engineered features actually help?</h2>'
    ablations=[('ridge_state','State'),('ridge_pressure','Generator pressure'),('ridge_full','State + pressure'),('ridge_forecast','+ forecast aggregate pressure'),('ridge_context','+ regional context')]
    fig=go.Figure()
    for ic in ['VNI','QNI']:
        fig.add_bar(name=ic,x=[label for _,label in ablations],y=[100*(row(ic,m).mae/row(ic,'ridge_base').mae-1) for m,_ in ablations])
    fig.add_hline(y=0,line_color='#66717e');fig.update_yaxes(title='Flow MAE change vs history-only ridge (%)')
    body+=chart(fig,'Topology ablations within the same model family','Negative is better. Ridge regularization is reselected within each recipe using validation. This isolates the implemented feature blocks more closely than comparing a ridge baseline with a boosted context model.')
    body+=para(f'On VNI, every displayed expanded ridge recipe has higher aggregate flow MAE than the history-only ridge. QNI’s pressure-only recipe improves MAE by {100*(1-row("QNI","ridge_pressure").mae/row("QNI","ridge_base").mae):.2f}%, but adding the full state block removes that gain. The evidence therefore favours selective pressure features for further QNI tests, not wholesale expansion of the input set.')
    body+=para(f'Within boosting, context-rich inputs reduce flow MAE from {row("VNI","boost_base").mae:.1f} to {row("VNI","boost_context").mae:.1f} MW on VNI and {row("QNI","boost_base").mae:.1f} to {row("QNI","boost_context").mae:.1f} MW on QNI. This recipe changes several blocks together, including topology, predicted pressure and regional context. Its gain cannot be assigned to generator coefficients alone.')
    body+=tbl([
        {'Block':'History and calendar','Representation':'Flow and tight-limit lags at 30 minutes, one day and seven days; recent change; delivery calendar and lead'},
        {'Block':'State','Representation':'Directional headroom, next-candidate gaps and counts, observed setter age and recent switching'},
        {'Block':'Generator pressure','Representation':'Directional tightening/relief, pressure change, availability relief and reconstruction-quality indicators'},
        {'Block':'Pressure forecast','Representation':'Monthly out-of-fold forecasts of two aggregate net-pressure quantities at a representative lead per band; not individual DUID forecasts'},
        {'Block':'Regional context','Representation':'Lagged retained demand, renewable generation, available generation and weather observations where present'},
        {'Block':'Oracle diagnostic','Representation':'Actual future fundamentals. Changes the information set and recipe; cannot be interpreted as an achievable operational lower bound'}])
    body+=para(f'The future-actual ridge diagnostic reaches {row("VNI","oracle_ridge").mae:.1f} MW on VNI and {row("QNI","oracle_ridge").mae:.1f} MW on QNI. It suggests value in future fundamentals, but uses information unavailable at issue time. The next useful experiment is an archived-vintage forecast input, not a live model supplied with realized future demand or weather.')
    body+=para('The prior equation studies remain valuable as mechanism evidence. A large coefficient says how an equation’s balance changes conditional on its other terms; it does not establish an independent causal dispatch effect or a forecastable generator move. Candidate coverage, stale equation state, compensation by other units and setter switching can all weaken a compact pressure proxy. Those are explanations to investigate, not causal conclusions demonstrated by this campaign.')+'</section>'
    body+='<section id="limits"><h2>4. Limit forecasting is a different problem from flow forecasting</h2>'
    fig=go.Figure(go.Heatmap(x=list(TARGETS.values()),y=['VNI','QNI'],z=[[gain(ic,t) for t in TARGETS] for ic in ['VNI','QNI']],text=[[f'{gain(ic,t):.1f}%' for t in TARGETS] for ic in ['VNI','QNI']],texttemplate='%{text}',colorscale='RdBu',zmid=0,colorbar=dict(title='MAE gain (%)')))
    body+=chart(fig,'Selected-policy improvement across all five targets','Rolling sample-weighted MAE against persistence. Positive is better. Minimum-limit targets retain the worst five-minute capacity inside each half-hour.',430)
    body+=para(f'VNI’s limit results are stronger than QNI’s. Selected VNI export and import mean-limit MAE improve by {gain("VNI","export"):.1f}% and {gain("VNI","import"):.1f}%. QNI export mean-limit MAE changes from {row("QNI","persistence","export").mae:.1f} to {row("QNI","selected_policy","export").mae:.1f} MW: the selected model is worse than persistence. The QNI minimum export limit also fails to improve. A single “better flow model” label would conceal these target-level failures.')
    body+=tbl([{'IC':ic,'Target':TARGETS[t],'Persistence MAE (MW)':row(ic,'persistence',t).mae,'Selected MAE (MW)':row(ic,'selected_policy',t).mae,'Selected RMSE (MW)':row(ic,'selected_policy',t).rmse,'Improvement (%)':gain(ic,t)} for ic in ['VNI','QNI'] for t in TARGETS])
    body+=para('Keep persistence as a live fallback for QNI export capacity until a predeclared challenger improves it. The warning task must also be assessed directly: lower average limit error does not guarantee advance warning of an abrupt contraction.')+'</section>'
    body+='<section id="seasons"><h2>5. Seasonal and diurnal structure</h2>'
    sl=pd.DataFrame(d['slices']);fig=make_subplots(rows=1,cols=2,subplot_titles=['VNI','QNI'])
    for col,ic in enumerate(['VNI','QNI'],1):
        f=sl[sl.ic.eq(ic)&sl.protocol.eq('rolling')&sl.band.eq(0)&sl.slice.eq('season')]
        for name in ['persistence','selected_policy']:
            ss=f[f.model.eq(name)].set_index('value').reindex(['Spring','Summer','Autumn','Winter']);fig.add_bar(name=name.replace('_',' '),legendgroup=name,showlegend=col==1,x=ss.index,y=ss.mae,marker_color='#ce9a48' if name=='persistence' else '#5696b9',row=1,col=col)
    fig.update_yaxes(title='Flow MAE (MW)')
    body+=chart(fig,'Seasonal accuracy at 0.5–6 hours','Southern Hemisphere meteorological seasons, based on delivery time. Rolling evaluation gives one occurrence of each season, not two independent seasonal test years.')
    fig=make_subplots(rows=1,cols=2,subplot_titles=['VNI','QNI'])
    for col,ic in enumerate(['VNI','QNI'],1):
        f=sl[sl.ic.eq(ic)&sl.protocol.eq('rolling')&sl.band.eq(0)&sl.slice.eq('hour')].copy();f['hour']=f.value.astype(int)
        for name in ['persistence','selected_policy']:
            ss=f[f.model.eq(name)].sort_values('hour');fig.add_scatter(name=name.replace('_',' '),legendgroup=name,showlegend=col==1,x=ss.hour,y=ss.mae,mode='lines+markers',line_color='#ce9a48' if name=='persistence' else '#5696b9',row=1,col=col)
    fig.update_yaxes(title='Flow MAE (MW)');fig.update_xaxes(title='Delivery hour · NEM time (UTC+10)',dtick=4)
    body+=chart(fig,'Diurnal forecast error','0.5–6 hour leads. The pattern is an error diagnostic, not proof that a particular demand or renewable component caused the error.')
    body+=para('VNI’s selected short-horizon policy improves over persistence in all four displayed seasons; QNI’s improvement is much smaller. QNI summer remains a difficult absolute-error regime. Hourly curves identify where a single average MAE hides recurring weaknesses. Use them to predeclare future tests of ramp periods, demand forecasts and renewable forecast uncertainty; do not select a different model for each observed bad hour using this evaluation sample alone.')+'</section>'
    body+='<section id="warnings"><h2>6. Sharp contractions: useful signal, excessive burden</h2>'
    body+=para('A primary sharp contraction is a positive directional limit fall over 30 minutes that reaches the training-only 90th percentile for that month of the year. At least 100 positive training falls are required for a monthly threshold; otherwise the pooled training percentile is used. This is a relative severity definition, not a universal 100 MW threshold. Separate 100, 200 and 400 MW labels test absolute severity. Onsets less than or equal to 30 minutes apart are grouped into incidents. Warnings must precede the first onset by 30–120 minutes, and repeated alerts have a 120-minute per-direction refractory period.')
    fig=go.Figure()
    for ic in ['VNI','QNI']:
        f=events[events.ic.eq(ic)&events.protocol.eq('rolling')];fig.add_scatter(name=ic,x=f.false_per_day,y=f.recall*100,mode='markers',text=f.model,hovertemplate='%{text}<br>False/day %{x:.2f}<br>Recall %{y:.1f}%<extra></extra>',marker=dict(size=[16 if m=='selected_policy' else 10 for m in f.model],symbol='circle' if ic=='VNI' else 'diamond'))
    fig.add_vline(x=3,line_dash='dash',line_color='#ce9a48');fig.update_xaxes(title='False warnings per day · both directions');fig.update_yaxes(title='Incident recall (%)')
    body+=chart(fig,'Recall must be judged against false warnings','Thresholds are tuned to ≤3 false warnings/day on the earlier alert partition. This plot measures subsequent evaluation burden, which can exceed 3. Points at different burdens are not matched-budget superiority tests.')
    event_table=[{'IC':r['ic'],'Model':r['model'],'Recall (%)':100*r['recall'],'False/day':r['false_per_day'],'Precision (%)':100*r['precision'],'Brier':r['brier'],'Median useful lead (min)':r['median_lead']} for r in d['events'] if r['protocol']=='rolling']
    body+=tbl(event_table)
    body+=para(f'The selected policies catch {ev("VNI").tp:.0f} of {ev("VNI").incidents:.0f} scorable VNI incidents and {ev("QNI").tp:.0f} of {ev("QNI").incidents:.0f} QNI incidents. Median lead among correctly warned incidents is {ev("VNI").median_lead:.0f} and {ev("QNI").median_lead:.0f} minutes respectively; this excludes misses and is not the typical lead across all events. Selected precision is only {100*ev("VNI").precision:.1f}% for VNI and {100*ev("QNI").precision:.1f}% for QNI.')
    body+=para('Context boosting raises recall relative to a history-only logistic model, but at greater false-alarm burden. That does not satisfy the planned claim of a ten-percentage-point recall gain at the same burden. QNI’s context logistic model is a useful simple challenger near the desired burden; it is not a new winner selected on an untouched period. The warning policy requires a fresh threshold-stability experiment before promotion.')
    em=pd.DataFrame(d['event_months']);fig=go.Figure()
    for ic in ['VNI','QNI']:
        f=em[em.ic.eq(ic)&em.protocol.eq('rolling')];fig.add_scatter(name=ic,x=f.fold,y=f.false_per_day,mode='lines+markers')
    fig.add_hline(y=3,line_dash='dash',line_color='#ce9a48');fig.update_yaxes(title='Selected policy false warnings/day');fig.update_xaxes(tickangle=-45)
    body+=chart(fig,'Warning burden shifts from month to month','Both directions combined; one set of previously tuned thresholds per monthly fold. The horizontal line is the agreed evaluation burden, not a confidence bound.')
    fig=go.Figure();fig.add_scatter(x=[0,1],y=[0,1],name='Perfect calibration',mode='lines',line=dict(dash='dash',color='#66717e'))
    for ic in ['VNI','QNI']:
        f=pd.DataFrame(d['reliability']);f=f[f.ic.eq(ic)&f.protocol.eq('rolling')];fig.add_scatter(x=f.predicted,y=f.observed,name=ic,mode='lines+markers',customdata=f.n,hovertemplate='Forecast %{x:.2f}<br>Observed %{y:.2f}<br>Windows %{customdata}<extra></extra>')
    fig.update_xaxes(title='Mean predicted probability');fig.update_yaxes(title='Observed positive-window rate')
    body+=chart(fig,'Probability calibration of the selected warning models','Ten probability bins pooled with their observation counts. These are 30–120-minute event-window probabilities; calibration here is distinct from incident recall after alert deduplication. Overlapping windows are not independent.')
    aa=pd.DataFrame(d['absolute']);fig=make_subplots(rows=1,cols=2,subplot_titles=['Incident recall','False warnings per day'])
    for ic in ['VNI','QNI']:
        f=aa[aa.ic.eq(ic)&aa.protocol.eq('rolling')&aa.model.eq('selected_policy')].sort_values('drop_mw')
        fig.add_scatter(name=ic,x=f.drop_mw,y=f.recall*100,mode='lines+markers',line_color='#5696b9' if ic=='VNI' else '#ce9a48',row=1,col=1)
        fig.add_scatter(name=ic,showlegend=False,x=f.drop_mw,y=f.false_per_day,mode='lines+markers',line_color='#5696b9' if ic=='VNI' else '#ce9a48',row=1,col=2)
    fig.update_xaxes(title='Absolute 30-minute drop threshold (MW)');fig.update_yaxes(title='Recall (%)',row=1,col=1);fig.update_yaxes(title='False/day',row=1,col=2)
    body+=chart(fig,'Do the same warnings identify absolute large contractions?','Reuses the primary model and warning cutoffs; it does not retrain or retune on the 100/200/400 MW definitions. An alert for a smaller primary event can count as false against a larger absolute threshold.')
    body+='<h3>Other event tasks</h3>'+para('Flow reversal, setter switching and forced direction were also tested at a two-hour delivery horizon. These are probability classification diagnostics, not the primary incident-warning protocol. Brier scores are comparable between models within the same task and connector; differing event prevalence prevents a simple cross-task ranking.')
    secondary=pd.DataFrame(d['secondary']);body+=tbl(secondary[secondary.protocol.eq('rolling')],['ic','task','model','n','base_rate','brier','log_loss'])+'</section>'
    body+='<section id="uncertainty"><h2>7. Uncertainty bands are close on average, but not uniformly better after calibration</h2>'
    q=pd.DataFrame(d['quantiles']);q=q[q.protocol.eq('rolling')&q.target.eq('flow')]
    fig=make_subplots(rows=1,cols=2,subplot_titles=['80% interval coverage','Weighted interval score'])
    for ic in ['VNI','QNI']:
        f=q[q.ic.eq(ic)];color='#5696b9' if ic=='VNI' else '#ce9a48';fig.add_bar(name=ic,x=f.model,y=f.coverage_80*100,marker_color=color,row=1,col=1);fig.add_bar(name=ic,showlegend=False,x=f.model,y=f.wis,marker_color=color,row=1,col=2)
    fig.add_hline(y=80,line_dash='dash',line_color='#66717e',row=1,col=1);fig.update_yaxes(title='Empirical coverage (%)',row=1,col=1);fig.update_yaxes(title='Weighted interval score (MW)',row=1,col=2)
    body+=chart(fig,'Coverage and sharpness must be assessed together','Lower weighted interval score is better. Linear uses a smooth pinball approximation; boost uses shallow quantile trees. “Selected calibrated” selects the family on validation, then calibrates using the later calibration partition.')
    body+=tbl(q[['ic','model','wis','coverage_95','coverage_80','coverage_50','width_80']].rename(columns={'coverage_95':'95% coverage (fraction)','coverage_80':'80% coverage (fraction)','coverage_50':'50% coverage (fraction)','width_80':'80% mean width (MW)'}))
    body+=para('VNI’s selected 80% intervals attain approximately their intended average coverage; QNI’s are slightly below it. The uncalibrated boost challenger has a lower aggregate evaluation interval score than the selected/calibrated policy on both connectors. Calibration is therefore not an automatic improvement in sharpness-adjusted performance. These broad all-lead intervals can still fail on individual ramp days, so coverage should also be tested conditionally on lead and operating regime. All 520 linear quantile fits reported convergence; convergence does not imply calibrated predictions.')+'</section>'
    body+='<section id="benchmarks"><h2>8. AEMO anchoring is a stronger next step than replacing the operational forecast</h2>'
    a=pd.DataFrame(d['aemo_matched']);a=a[a.target.eq('flow')];fig=make_subplots(rows=1,cols=2,subplot_titles=['VNI','QNI'])
    for col,ic in enumerate(['VNI','QNI'],1):
        for name in ['AEMO original','Selected retrospective','Persistence']:
            f=a[a.ic.eq(ic)&a.model.eq(name)].sort_values('band');fig.add_bar(name=name,legendgroup=name,showlegend=col==1,x=[BANDS[b] if b!=2 else '36 h only' for b in f.band],y=f.mae,marker_color={'AEMO original':'#268a87','Selected retrospective':'#5696b9','Persistence':'#ce9a48'}[name],row=1,col=col)
    fig.update_yaxes(title='Matched-sample flow MAE (MW)')
    body+=chart(fig,'Original AEMO forecasts beat the research policy on matched flow observations','Exact shared origin/lead pairs in March–August 2026. The third group contains the 36-hour lead only (1,204 pairs per connector); it is not a three-day AEMO benchmark. Original issue timing is checked, with the source dataset’s assumed ingestion allowance.')
    def matched_value(ic,model):return float(a[a.ic.eq(ic)&a.model.eq(model)&a.band.eq(0)].mae.iloc[0])
    body+=para(f'The advantage over persistence does not translate into an advantage over AEMO. At 0.5–6 hours, matched VNI flow MAE is {matched_value("VNI","AEMO original"):.1f} MW for AEMO versus {matched_value("VNI","Selected retrospective"):.1f} MW for the selected research policy; QNI is {matched_value("QNI","AEMO original"):.1f} versus {matched_value("QNI","Selected retrospective"):.1f} MW. These numbers use identical outcomes, not the research policy’s broader rolling sample. No assertion is made that the AEMO and reconstructed-network inputs have identical information availability.')
    body+=para('The next operational candidate should predict the residual around the original AEMO forecast using only archived issue-time information. In this campaign, a learned AEMO bias correction could not be fairly trained for the relevant early cutoffs because the retained issue history starts only in March 2026. Recovering a longer, scoped vintage history is a prerequisite for that test; the current results do not demonstrate an implemented correction benefit.')
    body+='<details><summary>Matched AEMO results for flow and both mean limits</summary>'+tbl(d['aemo_matched'])+'</details>'
    p=pd.DataFrame(d['pooled']);p=p[p.protocol.eq('rolling')&p.target.eq('flow')]
    single=bands[bands.protocol.eq('rolling')&bands.target.eq('flow')&bands.model.eq('ridge_full')]
    p=p.merge(single,on=['ic','protocol','target','band'],suffixes=('_pooled','_single'));fig=go.Figure()
    for ic in ['VNI','QNI']:
        f=p[p.ic.eq(ic)].sort_values('band');fig.add_bar(name=ic,x=[BANDS[b] for b in f.band],y=100*(f.mae_pooled/f.mae_single-1))
    fig.add_hline(y=0,line_color='#66717e');fig.update_yaxes(title='Pooled flow MAE change vs separate ridge (%)')
    body+=chart(fig,'Pooling the connectors mostly reduces flow skill','Identical full state/pressure recipe, training-only per-connector residual scaling and a connector indicator. Positive is worse. This evaluates this pooled linear specification, not all possible transfer-learning designs.')
    body+=para('The pooled full-feature ridge is worse in all four QNI flow bands and in three of four VNI flow bands. The modest VNI long-lead exception does not justify a common model across the board. Separate connector models remain the better starting point for this tested representation.')+'</section>'
    body+='<section id="cases"><h2>9. Failure examples: aggregate skill does not eliminate bad days</h2>'
    body+=para('The following days are selected reproducibly as the highest mean absolute-error day at the 30-minute lead in each connector’s rolling evaluation. They are deliberately adverse examples, not representative average performance. They illustrate residual forecast risk; generator-level causal attribution was not performed for these examples.')
    for case in d['cases']:
        f=pd.DataFrame(case['rows']);fig=go.Figure()
        fig.add_scatter(x=f.delivery,y=f['q0.9'],mode='lines',line=dict(width=0),showlegend=False,hoverinfo='skip')
        fig.add_scatter(x=f.delivery,y=f['q0.1'],mode='lines',line=dict(width=0),fill='tonexty',fillcolor='rgba(86,150,185,.18)',name='80% interval')
        for name,col in [('Observed flow','actual'),('Selected forecast','prediction'),('Persistence','persistence')]:fig.add_scatter(x=f.delivery,y=f[col],mode='lines',name=name)
        fig.update_yaxes(title='Flow (MW)');fig.update_xaxes(title='Delivery time · NEM UTC+10')
        body+=chart(fig,f'{case["ic"]}: adverse 30-minute forecast day, {case["day"]}','Positive flow is VIC→NSW for VNI and NSW→QLD for QNI. The band is the saved selected calibrated interval; the point forecast need not equal its median.')
    body+=para('A complete explanation would combine these forecast errors with changing setter equations, signed generator movements, RHS changes and other-interconnector terms, then add demand, renewable output, outages, coal availability, weather and prices. That deeper 100-case-per-connector attribution remains unfinished. The existing constraint/event atlases provide mechanism hypotheses, but should not be presented as a causal explanation of these particular forecast errors without a joined event analysis.')+'</section>'
    body+='<section id="decision"><h2>10. Research decisions and the next experiment</h2>'
    body+=tbl([
        {'Decision':'Retain a simple reference model','Evidence':'History-only ridge captures much of the flow gain; keep it beside persistence and AEMO.'},
        {'Decision':'Keep shallow boosting/blending as challengers','Evidence':'Incremental flow and VNI limit gains exist, but not every target benefits. Select separately by connector, target and horizon.'},
        {'Decision':'Do not promote the contraction warning policy yet','Evidence':'Selected rolling burden exceeds 3/day on both connectors; matched-burden recall improvement is not demonstrated.'},
        {'Decision':'Prioritize an AEMO residual model','Evidence':'AEMO wins the matched flow benchmark. Recover earlier original issues and test small ridge/logistic corrections before a boosted correction.'},
        {'Decision':'Rebuild topology features selectively','Evidence':'Full ridge topology blocks do not improve aggregate flow MAE. Test current-candidate slack, forecast generator movement and switch probability as separate ablations.'},
        {'Decision':'Keep QNI export persistence available','Evidence':'Selected mean and minimum export-limit forecasts do not beat persistence in rolling aggregate MAE.'},
        {'Decision':'Prefer separate connector models','Evidence':'Pooled full-feature ridge mostly degrades the comparable separate-ridge flow results.'}])
    body+=para('A defensible next sequence is: first, audit source publication timing and complete target-window purging; second, recover sufficient original AEMO forecast issues and build a small residual correction; third, add forecast generator movement and equation headroom one block at a time; fourth, test alert-budget stability on a new period; finally, run an immutable shadow trial with matured outcomes. Keep all choices frozen before the next evaluation window. This sequence responds to the measured weaknesses rather than expanding model complexity indiscriminately.')
    body+=para('Promotion requires the agreed joint standard: at least 5% flow MAE improvement without material event harm, or at least ten percentage points more incident recall at the same burden with no more than 2% flow MAE deterioration, together with acceptable calibration and operational input eligibility. The historical flow improvement clears one component, but the complete promotion case has not been established.')
    body+='<h3>Interpretation limits</h3>'+para('The model grid is finite. Feature blocks are reconstructed and sometimes incomplete. Pressure forecasts use a representative lead within each band. The future-actual oracle is diagnostic. Overlapping origin windows create dependence; the paired day-block analysis addresses part of that dependence but does not make prior research periods untouched. Two years of source data support seasonal training coverage, while the primary scored rolling period contains only one year of seasonal evaluation. The campaign does not establish a deployable generator-causal model, price forecasting system or completed live validation.')+'</section>'
    body+='<section id="sources"><h2>Sources, methods and reproducibility</h2>'
    body+=para('This report is an analysis of the repository’s completed experiments, not a new external literature review. No additional market downloads or model retraining were needed. The numerical snapshot records original trial-result hashes, the inventory fingerprint, paired-score calculations, example series and matched AEMO comparisons. The original research explorer retains the detailed model cells.')
    body+='<ul><li><a href="forecast_experiment_framework.html">Full experiment explorer and original results</a></li><li><a href="qni_vni_expanded_forecast_research.html">Earlier literature and mechanism research</a></li><li><a href="vni_event_atlas.html">VNI event atlas</a> · <a href="qni_event_atlas.html">QNI event atlas</a></li><li><a href="../forecast_experiment_operations.md">Experiment operations and limitations</a></li><li><a href="../data/forecast_experiment_research_snapshot.json" download>Auditable numerical snapshot (JSON)</a></li><li><a href="../data/forecast_experiment_research_build.json" download>Report build manifest (JSON)</a></li></ul>'
    body+=para('Rebuild from the committed snapshot: python scripts/build_forecast_research_report.py. Re-extract against the original local campaign: python scripts/build_forecast_research_report.py --extract. The latter requires the ignored local study datasets and verifies all main trial artifacts. The HTML is self-contained for reading; linked downloads and related reports are separate repository files.')
    body+='<details><summary>Original result-file checksums</summary>'+tbl(d['sources'])+'</details>'
    body+=para('Data cutoff: 31 August 2026. Primary evaluation: 1 September 2025–31 August 2026. Report built: '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')+'. Static validation and visual review are recorded separately in the build manifest.')+'</section>'
    body+='<style>.table-wrap{max-width:100%;overflow-x:auto}.chart-scroll{overflow-x:auto;max-width:100%}.chart-scroll>.plotly-graph-div{min-width:620px}nav{line-height:2.2}details{margin:22px 0}summary{cursor:pointer;font-weight:650}p{max-width:1100px}</style>'
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(render_page('VNI and QNI forecasting experiments — research findings',body,accent='blue'),encoding='utf-8')
    manifest={'report':str(OUTPUT.relative_to(ROOT)),'report_sha256':digest(OUTPUT),'snapshot_sha256':digest(SNAPSHOT),
        'generator_sha256':digest(Path(__file__)),'theme_sha256':digest(ROOT/'scripts/report_theme/report_theme.py'),'css_sha256':digest(ROOT/'scripts/report_theme/report.css'),
        'source_fingerprint':d['source_fingerprint'],'chart_count':chart_no,'rebuild':'python scripts/build_forecast_research_report.py',
        'packages':{name:importlib.metadata.version(name) for name in ['pandas','numpy','plotly']},
        'visual_review':'Not yet verified; browser URL policy blocked earlier local report previews. No alternate browser route used.'}
    (SNAPSHOT.parent/'forecast_experiment_research_build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'html':str(OUTPUT),'charts':chart_no,'bytes':OUTPUT.stat().st_size}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--extract',action='store_true');parser.add_argument('--extract-only',action='store_true');args=parser.parse_args()
    d=extract() if args.extract or args.extract_only else json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    if not args.extract_only:render(d)
