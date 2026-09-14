"""Limit-only research with held-out, grouped block-permutation diagnostics.

Extract uses local saved models and outcomes; render uses the published snapshot.
"""
from pathlib import Path
import sys,json,argparse
from html import escape
import numpy as np
import pandas as pd
import joblib
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from nemic.experiments.core import load_config,digest,clean
from nemic.experiments.data import connector_data,base_frame,design,STATE,PRESSURE,QUALITY
from nemic.experiments.models import forecast_pressure
from nemic.experiments.validation import folds,pairs
from nemic.experiments.runner import reference
from scripts.build_forecast_research_report import aggregate,BANDS
from scripts.report_theme.report_theme import hero,metric,finding,figure_html,style_plotly,render_page

SNAPSHOT=ROOT/'docs/data/limit_forecast_research_snapshot.json'
OUTPUT=ROOT/'docs/html/vni_qni_limit_forecast_research.html'
TARGETS={'export':'Mean export limit','import':'Mean import limit','export_tight':'Minimum export limit','import_tight':'Minimum import limit'}
AUDIT_MONTHS=['2025-09','2025-12','2026-03','2026-06']
AUDIT_LEADS=[1,48,144,336]


def groups(columns):
    return {
        'Observed history':[c for c in columns if '_lag' in c or c.endswith('_delta')],
        'Network headroom / candidates':[c for c in columns if c in STATE],
        'Generator pressure / relief':[c for c in columns if c in PRESSURE],
        'Setter age / switching':[c for c in columns if 'setter_age' in c or 'switch_recent' in c],
        'Reconstruction quality':[c for c in columns if c in QUALITY],
        'Forecast aggregate pressure':[c for c in columns if c.startswith('predicted_pressure_')],
        'Regional context':[c for c in columns if c.startswith('ctx_')],
        'Delivery calendar':[c for c in columns if c in ['hour_sin','hour_cos','year_sin','year_cos','weekend']]}


def shift_days(frame,days):
    if len(frame)%48:raise ValueError('Permutation requires complete half-hourly days')
    return np.roll(np.arange(len(frame)),48*days)


def bundle_prediction(bundle,frames,anchor,seasonal):
    def component(name):
        if name=='persistence':return anchor
        if name.startswith('seasonal'):return seasonal[name]
        model,recipe=bundle['models'][name]
        return anchor+model.predict(frames[recipe])
    if bundle['winner']=='blend':
        w=bundle['blend_weight'];return w*component(bundle['simple'])+(1-w)*component(bundle['boosted'])
    return component(bundle['winner'])


def risk_metrics(actual,pred):
    a=np.asarray(actual);p=np.asarray(pred);m=np.isfinite(a)&np.isfinite(p);e=p[m]-a[m]
    if not len(e):return {'n':0}
    return {'n':len(e),'mae':float(np.abs(e).mean()),'rmse':float(np.sqrt((e**2).mean())),
        'bias':float(e.mean()),'over_100_pct':float(100*(e>100).mean()),'over_200_pct':float(100*(e>200).mean()),
        'under_100_pct':float(100*(e< -100).mean()),'optimistic_error_mw':float(np.maximum(e,0).mean())}


def extract():
    c=load_config();run=c['_run'];basepath=ROOT/'docs/data/forecast_experiment_research_snapshot.json'
    base=json.loads(basepath.read_text(encoding='utf-8'));sources=[{'path':str(basepath.relative_to(ROOT)),'sha256':digest(basepath)}]
    cache=run/'limit_report_importance.json';importance=[]
    if cache.exists():
        prior=json.loads(cache.read_text())
        if prior.get('extractor_sha256')==digest(Path(__file__)):importance=prior['rows']
    done={(r['ic'],r['fold'],r['band'],r['target']) for r in importance}
    risk=[];season=[];examples=[];cis=[];selection_counts=[]
    for ic in c['connectors']:
        data=connector_data(c,ic);data['base']=base_frame(data);idx=data['y'].index
        for target in TARGETS:
            paths=sorted((run/'trials'/ic['name']).glob(f'20*/band*/{target}_predictions.parquet'))
            f=pd.concat([pd.read_parquet(p) for p in paths],ignore_index=True)
            for path in paths:sources.append({'path':str(path.relative_to(ROOT)),'sha256':digest(path)})
            f['change']=data['y'][target].diff().reindex(pd.DatetimeIndex(f.delivery)).to_numpy()
            f['season']=np.array(['Summer','Autumn','Winter','Spring'])[(pd.to_datetime(f.delivery).dt.month.to_numpy()%12)//3]
            for b,part in f.groupby('band'):
                for name,col in [('Selected policy','prediction'),('Persistence','persistence')]:
                    for slice_name,sub in [('All intervals',part),('Realized fall ≥100 MW',part[part.change.le(-100)])]:
                        risk.append({'ic':ic['name'],'target':target,'band':int(b),'model':name,'slice':slice_name,**risk_metrics(sub.actual,sub[col])})
                    for s,sub in part.groupby('season'):season.append({'ic':ic['name'],'target':target,'band':int(b),'model':name,'season':s,**risk_metrics(sub.actual,sub[col])})
                ee=(part.prediction-part.actual).abs();bb=(part.persistence-part.actual).abs()
                dd=pd.DataFrame({'day':pd.to_datetime(part.origin).dt.normalize(),'e':ee,'b':bb}).groupby('day').sum().sort_index()
                a=dd.reindex(pd.date_range(dd.index.min(),dd.index.max(),freq='D'),fill_value=0).to_numpy();rng=np.random.default_rng(741);v=[]
                for _ in range(1000):
                    starts=rng.integers(0,len(a),int(np.ceil(len(a)/7)));ii=((starts[:,None]+np.arange(7))%len(a)).ravel()[:len(a)];s=a[ii].sum(axis=0)
                    v.append(100*(1-s[0]/s[1]))
                cis.append({'ic':ic['name'],'target':target,'band':int(b),'n':len(part),'gain_pct':100*(1-ee.sum()/bb.sum()),'low':float(np.quantile(v,.025)),'high':float(np.quantile(v,.975))})
            for (b,model),sub in f.groupby(['band','model']):selection_counts.append({'ic':ic['name'],'target':target,'band':int(b),'model':model,'n':len(sub),'fold_count':sub.fold.nunique()})
            if target.endswith('_tight'):
                half=f[f.lead.eq(1)].copy();half['day']=pd.to_datetime(half.origin).dt.normalize();half['error']=(half.actual-half.prediction).abs()
                worst_day=half.groupby('day').error.mean().idxmax()
                shock=half.loc[half.change.idxmin()];shock_day=shock.day
                for label,day in [('Largest realized half-hour fall',shock_day),('Largest daily forecast MAE',worst_day)]:
                    sub=half[half.day.eq(day)]
                    examples.append({'ic':ic['name'],'target':target,'selection':label,'day':str(day.date()),
                        'rows':sub[['origin','delivery','actual','prediction','persistence','q0.1','q0.9','change']].to_dict('records'),
                        'selected_metrics':risk_metrics(sub.actual,sub.prediction),'persistence_metrics':risk_metrics(sub.actual,sub.persistence)})
            print('limit outcomes',ic['name'],target,'done',flush=True)
        for fold in [f for f in folds(c) if f.name in AUDIT_MONTHS]:
            for b,lead in enumerate(AUDIT_LEADS):
                if all((ic['name'],fold.name,b,t) in done for t in TARGETS):continue
                lo,hi=c['bands'][b];forecast=forecast_pressure(data,fold,int(np.median([x for x in c['leads'] if lo<=x<=hi])))
                o,h=pairs(idx,fold,[lead]);mask=fold.masks(idx[o],h*30)['evaluate'];o=o[mask];h=h[mask]
                days=pd.Series(idx[o].normalize()).value_counts();complete=days[days.eq(48)].index
                keep=idx[o].normalize().isin(complete);o=o[keep];h=h[keep]
                if len(o)<48*8:raise ValueError('Too few complete days for block permutation')
                for target in TARGETS:
                    if (ic['name'],fold.name,b,target) in done:continue
                    modelpath=run/'trials'/ic['name']/fold.name/f'band{b}'/f'{target}_model.joblib'
                    bundle=joblib.load(modelpath);recipes={r for _,r in bundle['models'].values()}
                    frames={r:design(data,o,h,r,forecast) for r in recipes}
                    anchor=reference(data,o,h,target);actual=data['y'][target].to_numpy()[o+h]
                    seasonal={name:reference(data,o,h,target,p) for name,p in [('seasonal_daily',48),('seasonal_weekly',336)]}
                    pred=bundle_prediction(bundle,frames,anchor,seasonal)
                    saved=pd.read_parquet(modelpath.with_name(f'{target}_predictions.parquet'))
                    saved=saved[saved.lead.eq(lead)].set_index('origin').prediction.reindex(idx[o]).to_numpy()
                    mismatch=float(np.nanmax(np.abs(pred-saved)))
                    if mismatch>1e-4:raise ValueError(f'Saved prediction reproduction failed: {mismatch}')
                    baseline=risk_metrics(actual,pred)['mae'];allcols=list(dict.fromkeys(x for f in frames.values() for x in f))
                    offsets=sorted(set([1,7,max(2,len(o)//48//2)]))
                    for group,cols in groups(allcols).items():
                        changes=[]
                        for offset in offsets:
                            ii=shift_days(next(iter(frames.values())),offset);perturbed={}
                            for recipe,frame in frames.items():
                                z=frame.copy();cc=[x for x in cols if x in z]
                                if cc:z.loc[:,cc]=frame.iloc[ii][cc].to_numpy()
                                perturbed[recipe]=z
                            # The forecast is anchor + learned residual. Move the
                            # anchor with history so coefficient cancellation does
                            # not inflate apparent reliance on historical inputs.
                            moved_anchor=anchor[ii] if group=='Observed history' else anchor
                            moved_seasonal={k:v[ii] for k,v in seasonal.items()} if group=='Observed history' else seasonal
                            changes.append(risk_metrics(actual,bundle_prediction(bundle,perturbed,moved_anchor,moved_seasonal))['mae']-baseline)
                        importance.append({'ic':ic['name'],'fold':fold.name,'target':target,'band':b,'lead_hours':lead/2,'winner':bundle['winner'],
                            'group':group,'n':int(np.isfinite(actual).sum()),'baseline_mae':baseline,'delta_mae':float(np.mean(changes)),
                            'minimum_delta':float(min(changes)),'maximum_delta':float(max(changes)),'repeats':len(changes),'columns':cols,
                            'max_reproduction_error_mw':mismatch,'model_sha256':digest(modelpath)})
                    done.add((ic['name'],fold.name,b,target))
                    cache.write_text(json.dumps(clean({'extractor_sha256':digest(Path(__file__)),'rows':importance})),encoding='utf-8')
                print('permutation',ic['name'],fold.name,'band',b,'done',flush=True)
    result={'campaign':base['campaign'],'overall':[r for r in base['overall'] if r['target'] in TARGETS],
        'bands':[r for r in base['bands'] if r['target'] in TARGETS],'quantiles':[r for r in base['quantiles'] if r['target'] in TARGETS],
        'quantile_bands':[r for r in base['quantile_bands'] if r['target'] in TARGETS],
        'aemo_matched':[r for r in base['aemo_matched'] if r['target'] in TARGETS],
        'pooled':[r for r in base['pooled'] if r['target'] in TARGETS],
        'risk':risk,'season':season,'gain_ci':cis,'examples':examples,'selection_counts':selection_counts,'importance':importance,
        'sources':sources,'source_fingerprint':base['source_fingerprint'],'extractor_sha256':digest(Path(__file__)),
        'importance_scope':{'months':AUDIT_MONTHS,'leads_halfhours':AUDIT_LEADS,'models':len(done),
            'method':'Three circular whole-day shifts per feature group, preserving time of day within complete issue days. All columns in a group move jointly. History shifts also move persistence anchors and seasonal references; other groups hold the anchor fixed. Diagnostic model sensitivity, not causal importance. Calendar shifts preserve hour-of-day, so do not measure full calendar importance. No retraining or evaluation-based model replacement.'}}
    SNAPSHOT.write_text(json.dumps(clean(result),separators=(',',':')),encoding='utf-8');return result


def render(d):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from datetime import datetime,timezone
    score=pd.DataFrame(d['overall']);band=pd.DataFrame(d['bands']);risk=pd.DataFrame(d['risk']);imp=pd.DataFrame(d['importance'])
    def value(ic,model,target,protocol='rolling'):
        return score[score.ic.eq(ic)&score.model.eq(model)&score.target.eq(target)&score.protocol.eq(protocol)].iloc[0]
    def gain(ic,target):return 100*(1-value(ic,'selected_policy',target).mae/value(ic,'persistence',target).mae)
    def p(text):return '<p>'+escape(text)+'</p>'
    def table(rows,columns=None):
        f=pd.DataFrame(rows)
        if columns:f=f.reindex(columns=columns)
        return '<div class="table-wrap" tabindex="0">'+f.to_html(index=False,escape=True,float_format=lambda x:f'{x:,.2f}',na_rep='—')+'</div>'
    figure_count=0
    def chart(fig,title,note,height=550):
        nonlocal figure_count
        figure_count+=1;style_plotly(fig,title,height);fig.update_layout(title=None,margin=dict(t=65,b=80),legend=dict(y=1.04,yanchor='bottom'))
        if fig.data and fig.data[0].type=='heatmap':
            fig.update_layout(margin=dict(l=225,r=110));fig.update_xaxes(tickangle=-20)
        if fig.layout.updatemenus:fig.update_layout(margin=dict(t=145))
        return figure_html(fig.to_html(full_html=False,include_plotlyjs=False,div_id=f'limit-figure-{figure_count}',config={'responsive':True,'displaylogo':False}),f'Figure {figure_count}. {title}',note)
    def section(anchor,title):return f'<section id="{anchor}"><h2>{escape(title)}</h2>'
    body=hero('Focused research · Interconnector capacity','Forecasting the limits','before they move',
        'A detailed assessment of VNI and QNI directional capacity forecasts: average accuracy, sudden contractions, feature importance, uncertainty and model choices.',
        ['Four limit targets','Rolling evaluation · Sep 2025–Aug 2026','30 minutes–7 days','128 saved-model importance audits'])
    body+='<nav>'+' · '.join(f'<a href="#{a}">{b}</a>' for a,b in [('findings','Findings'),('performance','Performance'),('models','Model choices'),('features','Feature importance'),('risk','Contractions'),('examples','Forecast examples'),('uncertainty','Intervals'),('aemo','AEMO'),('next','Recommendations'),('methods','Methods')])+'</nav>'
    body+='<div class="metrics">'+''.join(metric(ic+' · '+TARGETS[t],f'{gain(ic,t):+.1f}%','Selected MAE improvement vs persistence') for ic in ['VNI','QNI'] for t in ['export_tight','import_tight'])+'</div>'
    body+=section('findings','The main finding: VNI improves materially; QNI needs a more selective policy')
    body+=p('Limit forecasting should be evaluated separately from flow forecasting. A forecast can estimate normal transfers reasonably well while missing a sudden loss of directional capacity. This report evaluates both the average directional limit and the minimum five-minute limit within each half-hour, then asks whether model skill survives the periods when those limits fall.')
    body+='<div class="findings">'+finding(1,'Strong VNI gains',f'For the minimum export limit, selected-policy MAE falls from {value("VNI","persistence","export_tight").mae:.1f} to {value("VNI","selected_policy","export_tight").mae:.1f} MW. The minimum import limit improves from {value("VNI","persistence","import_tight").mae:.1f} to {value("VNI","selected_policy","import_tight").mae:.1f} MW.')+finding(2,'Weak QNI export gains',f'The selected QNI minimum-export policy is slightly worse than persistence: {value("QNI","selected_policy","export_tight").mae:.1f} versus {value("QNI","persistence","export_tight").mae:.1f} MW. Its minimum-import improvement is only {gain("QNI","import_tight"):.1f}%. A uniform model replacement is not supported.')+finding(3,'Contraction risk remains', 'Average error improvements do not prevent optimistic capacity forecasts during sudden falls. The report measures those errors explicitly and shows adverse days, alongside the full-year results.')+'</div>'
    body+=p('All headline improvements refer to the policy selected using earlier validation data, not whichever model happens to score best on the evaluation year. The latter is reported separately as a shortlist for a future, predeclared test. None of these reconstructed-network models has verified live input eligibility.')
    body+=table([
        {'Target':'Mean export / import limit','Meaning':'Average of six five-minute directional capacity observations in the delivery half-hour.'},
        {'Target':'Minimum export / import limit','Meaning':'Minimum of those six observations; a separate target designed to retain within-half-hour tightening.'},
        {'Target':'Direction','Meaning':'VNI export is VIC→NSW, import NSW→VIC; QNI export is NSW→QLD, import QLD→NSW.'},
        {'Target':'Negative directional limit','Meaning':'Retained as reported; it can imply a requirement for flow in the opposite direction. Forecasts and observations are not clipped to zero.'},
        {'Target':'Evaluation scope','Meaning':'Two years of source studies; one year of rolling evaluation, Sep 2025–Aug 2026. Fixed Mar–Aug 2026 scores remain separate.'}])+'</section>'
    body+=section('performance','1. Performance across targets and horizons')
    body+=table([{'IC':ic,'Target':TARGETS[t],'Persistence MAE (MW)':value(ic,'persistence',t).mae,'Selected MAE (MW)':value(ic,'selected_policy',t).mae,'Selected RMSE (MW)':value(ic,'selected_policy',t).rmse,'Bias (MW)':value(ic,'selected_policy',t).bias,'MAE improvement (%)':gain(ic,t)} for ic in ['VNI','QNI'] for t in TARGETS])
    names=['persistence','ridge_base','ridge_state','ridge_pressure','ridge_full','ridge_forecast','ridge_context','elastic_context','additive_context','regime_context','boost_base','boost_context','boost_l2_context','blend','selected_policy']
    for ic in ['VNI','QNI']:
        z=[[value(ic,m,t).mae for t in TARGETS] for m in names]
        fig=go.Figure(go.Heatmap(x=list(TARGETS.values()),y=[n.replace('_',' ') for n in names],z=z,text=[[f'{v:.1f}' for v in r] for r in z],texttemplate='%{text}',colorscale=[[0,'#f4f8fc'],[1,'#8ab5d0']],colorbar=dict(title='MAE (MW)')))
        fig.update_yaxes(autorange='reversed');fig.update_layout(margin=dict(l=180))
        body+=chart(fig,ic+' model comparison across all limit targets','Rolling evaluation, all scored origin–lead pairs. Lower is better. Read model comparisons within a target; different directional capacities have different scales.',670)
    ci=pd.DataFrame(d['gain_ci'])
    for ic in ['VNI','QNI']:
        fig=go.Figure()
        for t in TARGETS:
            f=ci[ci.ic.eq(ic)&ci.target.eq(t)].sort_values('band');fig.add_scatter(name=TARGETS[t],x=[BANDS[x] for x in f.band],y=f.gain_pct,mode='lines+markers',error_y=dict(type='data',array=f.high-f.gain_pct,arrayminus=f.gain_pct-f.low))
        fig.add_hline(y=0,line_color='#66717e');fig.update_yaxes(title='Selected-policy MAE improvement (%)')
        body+=chart(fig,ic+' improvement by forecast horizon','95% intervals from 1,000 paired circular seven-day resamples of issue days, conditional on fitted models. Positive is better than persistence; intervals spanning zero do not establish a clear improvement.')
    body+=p('The horizon charts are more useful for model policy than the all-lead average. Each band contains a different number of scored leads, so the overall number weights origin–lead pairs, not the four bands equally. A model that helps short-horizon QNI capacity can still fail to improve the aggregate policy once longer leads and different selection months are included.')
    body+='<details><summary>Fixed versus rolling protocol: all four limits</summary>'+table([{'IC':ic,'Target':TARGETS[t],'Protocol':pr,'Selected MAE':value(ic,'selected_policy',t,pr).mae,'Persistence MAE':value(ic,'persistence',t,pr).mae} for ic in ['VNI','QNI'] for t in TARGETS for pr in ['fixed','rolling']])+'</details></section>'
    body+=section('models','2. Which model families deserve the next test?')
    eligible=band[band.protocol.eq('rolling')&~band.model.isin(['oracle_ridge','selected_policy'])]
    rows=[]
    simple_names=['persistence','seasonal_daily','seasonal_weekly','ridge_base','ridge_state','ridge_pressure','ridge_full','ridge_forecast','ridge_context','elastic_context','additive_context','regime_context']
    for (ic,t,b),f in eligible.groupby(['ic','target','band']):
        best=f.loc[f.mae.idxmin()];simple=f[f.model.isin(simple_names)];simple=simple.loc[simple.mae.idxmin()]
        rows.append({'IC':ic,'Target':TARGETS[t],'Horizon':BANDS[b],'Best simple / baseline':simple.model,'Simple MAE (MW)':simple.mae,'Lowest observed model':best.model,'Lowest MAE (MW)':best.mae,'Extra improvement (%)':100*(1-best.mae/simple.mae)})
    body+=p('The following table is an evaluation-informed research shortlist. It does not rewrite the historical validation-selected policy. “Best simple” includes persistence, seasonal baselines and linear/additive/regime models; the last columns show whether a boosted or blended specification earns an additional improvement in this studied sample.')
    body+=table(rows)
    body+=p('For VNI export limits, shallow boosting and blends are credible challengers to a simpler ridge baseline. VNI import limits often favour shallow boosting, including the history-only boosted recipe at longer leads. For QNI, the winning families vary more: short leads favour context boosting in this sample, while ridge state/pressure and elastic net appear among the better longer-lead candidates. This supports a compact connector/target/horizon policy, not a single complex model for every limit.')
    body+=p('Preserve persistence as the reference and fallback, especially for QNI export. The additive and regime specifications tested here do not show a general limit advantage. A small ridge or elastic-net correction should be the first challenger; add boosting only where its incremental error reduction is material and repeats across an untouched evaluation period.')+'</section>'
    body+=section('features','3. Feature importance: predictive value and model reliance are different questions')
    body+='<h3>Does adding the feature block improve forecasts?</h3>'
    ablations=['ridge_state','ridge_pressure','ridge_full','ridge_forecast','ridge_context']
    for ic in ['VNI','QNI']:
        z=[[100*(value(ic,m,t).mae/value(ic,'ridge_base',t).mae-1) for t in TARGETS] for m in ablations]
        fig=go.Figure(go.Heatmap(x=list(TARGETS.values()),y=['State','Generator pressure','State + pressure','+ pressure forecasts','+ regional context'],z=z,text=[[f'{v:+.2f}%' for v in r] for r in z],texttemplate='%{text}',colorscale=[[0,'#b4d9ee'],[.5,'#fafafa'],[1,'#efb9af']],zmid=0,colorbar=dict(title='MAE change (%)')))
        fig.update_yaxes(autorange='reversed')
        body+=chart(fig,ic+' feature ablations within ridge','Change relative to history-only ridge. Negative means lower error. Regularization is selected on validation within each recipe. These are comparisons of trained models, not permutation importance.',450)
    body+=p('Unlike the earlier flow-only conclusions, some state and pressure additions are useful for limit targets. The relevant question is target-specific: directional headroom can help a capacity forecast even if it adds little to a flow forecast. However, gains from a full context recipe cannot be assigned solely to generators because it changes several blocks together. Forecast aggregate pressure is not the same as forecasting each generator’s dispatch.')
    body+='<h3>Which inputs do the saved selected models rely on?</h3>'
    ia=pd.DataFrame(aggregate(imp,['ic','target','group'],['delta_mae','baseline_mae']))
    for ic in ['VNI','QNI']:
        f=ia[ia.ic.eq(ic)];order=f.groupby('group').delta_mae.mean().sort_values(ascending=False).index.tolist()
        z=f.pivot(index='group',columns='target',values='delta_mae').reindex(index=order,columns=list(TARGETS))
        fig=go.Figure(go.Heatmap(x=list(TARGETS.values()),y=z.index,z=z.to_numpy(),text=[[f'{v:+.2f}' for v in r] for r in z.to_numpy()],texttemplate='%{text}',colorscale=[[0,'#b4d9ee'],[.5,'#fafafa'],[1,'#efb9af']],zmid=0,colorbar=dict(title='MAE increase (MW)')))
        fig.update_yaxes(autorange='reversed')
        body+=chart(fig,ic+' grouped feature importance on held-out dates','Mean MAE increase after three whole-day shifts per group; weighted by valid audit observations across four seasonal months and four representative leads. Positive indicates reliance; negative indicates the perturbation improved error. These are sensitivity diagnostics, not causal effects.',560)
    top=[]
    for ic in ['VNI','QNI']:
        f=pd.DataFrame(aggregate(imp[imp.ic.eq(ic)],['group'],['delta_mae'])).sort_values('delta_mae',ascending=False)
        top.append(f'{ic}: '+', '.join(f'{r.group} ({r.delta_mae:+.2f} MW)' for r in f.head(3).itertuples()))
    body+=p('The three largest average perturbation effects in this audit are '+ '; '.join(top)+'. These averages combine targets and representative leads for orientation; inspect the target heatmaps and detailed horizon table before choosing features.')
    body+=p('The audit uses September 2025, December 2025, March 2026 and June 2026, with 30-minute, 24-hour, 72-hour and 168-hour leads: 128 saved selected-model bundles. Predictions are first reproduced against the saved evaluation files, then each feature group is shifted by one, seven and approximately half a month of complete issue days. Columns within a group move together. No model is refitted and no new winner is selected.')
    body+=p('A crucial detail is the persistence anchor: the forecast is an anchor plus a learned correction. When historical inputs move, the anchor and seasonal references move with them; otherwise an artificial mismatch would exaggerate history importance. For other groups the anchor stays fixed. Day shifts preserve the time of day, so the calendar result does not measure the full importance of hour-of-day effects. Correlated inputs and the artificial combinations created by permutation can distort attribution. Negative or near-zero importance is not proof that the underlying physical mechanism is irrelevant.')
    detail=aggregate(imp,['ic','target','band','group'],['delta_mae','baseline_mae'])
    body+='<details><summary>Feature importance by target and representative horizon</summary>'+table(detail)+'</details>'
    body+=p('These models use aggregate pressure, not separate generator identities. The audit therefore cannot rank Tumut 3 or another DUID as a causal driver. Generator-specific conclusions require forecasting unit movements and projecting them through the relevant equation coefficients, with RHS, other-generator and setter changes accounted for. The existing equation studies supply hypotheses for that extension, not an attribution already established by this report.')+'</section>'
    body+=section('risk','4. Optimistic capacity errors during limit falls')
    body+=p('For this section, an optimistic error means predicted directional capacity exceeds realized capacity. Overstatement greater than 100 MW is counted directly, along with MAE and bias. The stress slice is a fall of at least 100 MW between successive half-hour target values. It is an outcome-based diagnostic slice, not the earlier five-minute, training-percentile incident label and not an advance-warning success rate.')
    for ic in ['VNI','QNI']:
        fig=make_subplots(rows=1,cols=2,subplot_titles=['All delivery intervals','Half-hour target fall ≥100 MW'])
        for col,slice_name in enumerate(['All intervals','Realized fall ≥100 MW'],1):
            for model,color in [('Persistence','#ce9a48'),('Selected policy','#5696b9')]:
                f=risk[risk.ic.eq(ic)&risk.band.eq(0)&risk.model.eq(model)&risk.slice.eq(slice_name)].set_index('target').reindex(list(TARGETS))
                fig.add_bar(name=model,legendgroup=model,showlegend=col==1,x=list(TARGETS.values()),y=f.over_100_pct,marker_color=color,row=1,col=col)
        fig.update_yaxes(title='Forecasts overstating capacity by >100 MW (%)');fig.update_xaxes(tickangle=-25)
        body+=chart(fig,ic+' capacity-overstatement risk at 0.5–6 hours','Percentages count origin–lead pairs, not unique incidents. Several forecasts can target the same fall. The stress-slice denominator is smaller and selected by realized outcomes.',580)
    body+=table(risk[risk.band.eq(0)&risk.model.eq('Selected policy')],['ic','target','slice','n','mae','bias','over_100_pct','over_200_pct'])
    body+=p('The contraction slice exposes a failure that average MAE can hide: the policy often predicts more capacity than subsequently materializes. A better average limit forecast is therefore not sufficient for decisions that depend on the limit holding. A future conservative policy should be evaluated using explicit asymmetric error costs or a lower predictive quantile, with its loss of usable capacity measured alongside the reduction in optimistic errors. That decision rule has not been validated here.')+'</section>'
    body+=section('examples','5. Forecast examples: the largest falls and the worst days')
    body+=p('Each chart offers two deterministic examples through its selector: the largest realized half-hour fall and the day with the highest average 30-minute forecast error for that target. These are deliberately adverse examples from the rolling year. Lines show half-hour minimum limits, not raw five-minute traces. They are not representative random days or a complete generator-attributed incident study.')
    for ic in ['VNI','QNI']:
        for t in ['export_tight','import_tight']:
            cases=[e for e in d['examples'] if e['ic']==ic and e['target']==t];fig=go.Figure();buttons=[]
            for i,case in enumerate(cases):
                f=pd.DataFrame(case['rows']);visible=i==0
                fig.add_scatter(x=f.delivery,y=f['q0.9'],mode='lines',line=dict(width=0),showlegend=False,hoverinfo='skip',visible=visible)
                fig.add_scatter(x=f.delivery,y=f['q0.1'],mode='lines',line=dict(width=0),fill='tonexty',fillcolor='rgba(86,150,185,.18)',name='80% predictive interval',visible=visible)
                for name,col,color in [('Realized minimum','actual','#66717e'),('Selected forecast','prediction','#5696b9'),('Persistence','persistence','#ce9a48')]:
                    fig.add_scatter(x=f.delivery,y=f[col],name=name,mode='lines+markers',line_color=color,marker_size=4,visible=visible)
                buttons.append(dict(label=case['selection']+' · '+case['day'],method='update',args=[{'visible':[j//5==i for j in range(len(cases)*5)]}]))
            fig.update_layout(updatemenus=[dict(buttons=buttons,x=0,y=1.18,xanchor='left',yanchor='top')]);fig.update_yaxes(title='Directional minimum limit (MW)');fig.update_xaxes(title='Delivery time · NEM UTC+10')
            body+=chart(fig,ic+' · '+TARGETS[t]+' · 30-minute forecasts','Use the selector to switch adverse days. Forecasts were issued 30 minutes before delivery. Point forecasts and interval medians are separate estimates; negative limits are retained.',630)
            body+=table([{'Example':e['selection'],'Day':e['day'],'Selected MAE (MW)':e['selected_metrics']['mae'],'Persistence MAE (MW)':e['persistence_metrics']['mae'],'Overstatement >100 MW (%)':e['selected_metrics']['over_100_pct']} for e in cases])
    body+=p('The plotted forecast response can be inspected directly against the realized contraction and interval width. A slow forecast response suggests a ramp/transition problem, but the graphs alone do not identify which generator or constraint caused it. An equation-level explanation must join the exact active constraint, coefficients, generator changes and RHS movement for that event.')+'</section>'
    body+=section('uncertainty','6. Predictive intervals for the limit targets')
    q=pd.DataFrame(d['quantiles']);q=q[q.protocol.eq('rolling')]
    for ic in ['VNI','QNI']:
        fig=go.Figure()
        for model,color in [('linear','#ce9a48'),('boost','#8370b4'),('selected_calibrated','#5696b9')]:
            f=q[q.ic.eq(ic)&q.model.eq(model)].set_index('target').reindex(list(TARGETS));fig.add_bar(name=model.replace('_',' '),x=list(TARGETS.values()),y=f.coverage_80*100,marker_color=color)
        fig.add_hline(y=80,line_dash='dash',line_color='#66717e');fig.update_yaxes(title='Empirical 80% interval coverage (%)')
        body+=chart(fig,ic+' limit-interval calibration','Average coverage can hide shortfalls on contraction days. Linear uses smooth quantile regression; boost uses shallow quantile trees. The selected family is chosen on validation before residual calibration.')
    body+=table(q[q.model.eq('selected_calibrated')],['ic','target','n','wis','coverage_95','coverage_80','coverage_50','width_80'])
    calibrated=q[q.model.eq('selected_calibrated')]
    coverage=[]
    for ic in ['VNI','QNI']:
        f=calibrated[calibrated.ic.eq(ic)]
        coverage.append(f'{ic}: {100*f.coverage_80.min():.1f}–{100*f.coverage_80.max():.1f}% actual coverage')
    body+=p('All four selected limit intervals under-cover their nominal 80% level on both connectors. '+ '; '.join(coverage)+'. This is a material calibration weakness, even before conditioning on sharp falls. The stronger average point-forecast results therefore do not establish that the associated uncertainty bands are sufficiently conservative.')
    body+=p('Coverage must be considered with interval width and weighted interval score; a very wide interval is easier to cover. The table reports coverage as fractions and width in MW. It does not establish a calibrated safety margin conditional on outages, sharp contractions or forced flows. Any use of a lower quantile as a conservative limit needs a separate decision-cost test.')+'</section>'
    body+=section('aemo','7. Original AEMO limit forecasts on the same observations')
    a=pd.DataFrame(d['aemo_matched'])
    for ic in ['VNI','QNI']:
        fig=go.Figure()
        for model,color in [('AEMO original','#268a87'),('Selected retrospective','#5696b9'),('Persistence','#ce9a48')]:
            f=a[a.ic.eq(ic)&a.model.eq(model)].copy();f['label']=f.target.map(TARGETS)+' · '+f.band.map({0:'0.5–6 h',1:'12–24 h',2:'36 h'})
            fig.add_bar(name=model,x=f.label,y=f.mae,marker_color=color)
        fig.update_yaxes(title='Matched-sample limit MAE (MW)');fig.update_xaxes(tickangle=-30)
        body+=chart(fig,ic+' matched AEMO mean-limit benchmark','March–August 2026, exact shared origin/lead pairs. Mean directional limits only; there is no matching AEMO minimum-within-half-hour target. The third lead group is 36 hours, not the full three-day band.',590)
    body+=p('Original AEMO mean-limit forecasts outperform the selected research policy on the displayed short-horizon matched samples. The practical priority is an issue-vintage residual model around AEMO, not immediate replacement of AEMO with the reconstructed-feature model. A longer archive of original issues is needed to train and evaluate that correction fairly. The current experiment did not prove a learned AEMO correction benefit.')
    body+='<details><summary>Exact matched benchmark counts and coverage</summary>'+table(d['aemo_matched'])+'</details></section>'
    body+=section('next','8. Recommended model and feature development path')
    body+=table([
        {'Use case':'VNI mean and minimum export limits','Next model test':'Small shallow-boosting / validation-blend challenger, with ridge baseline','Reason':'Material gains over persistence; nonlinear models add skill beyond the simpler baselines in the studied sample.'},
        {'Use case':'VNI import limits','Next model test':'History-only versus context boosting; retain compact ridge reference','Reason':'Context is not uniformly necessary, especially at longer leads. Avoid retaining extra blocks solely because they are available.'},
        {'Use case':'QNI export limits','Next model test':'Persistence plus a small state/ridge or elastic-net challenger; boosted short-lead challenger only','Reason':'The earlier-selected policy does not improve aggregate export-limit MAE. Improvements must be established by horizon.'},
        {'Use case':'QNI import limits','Next model test':'Pressure-aware ridge or elastic net at longer leads; shallow boosting at short leads','Reason':'Observed gains are modest and depend on horizon; preserve a simple fallback.'},
        {'Use case':'Operational 0.5–36 hour mean limits','Next model test':'Ridge correction around the original AEMO issue forecast','Reason':'AEMO is the stronger matched benchmark. Add boosting only after a predeclared correction test shows extra value.'},
        {'Use case':'Abrupt contractions / conservative capacity','Next model test':'Separate contraction probability plus an asymmetric or quantile limit decision','Reason':'Average MAE masks optimistic capacity errors on falls. Explicitly measure useful capacity forgone and overstatement risk.'}])
    body+=p('For features, begin with reliable lagged limits and changes, then test directional slack and pressure independently. The next mechanism extension should predict generator movements and translate those movements into conditional equation impacts, while also predicting setter changes and RHS terms. Keep data-quality and coefficient-coverage flags. Add demand, renewables, outage and weather forecasts only with issue-time provenance. Observed retrospective context is not a substitute for archived forecast vintages.')
    body+=p('Use the ablation result to judge incremental skill, the permutation audit to inspect what a selected model uses, and the event graph to understand failure shape. None of those alone establishes generator causation. Freeze the next model choice and alert/decision thresholds before new evaluation; do not promote the table’s lowest observed model retrospectively.')+'</section>'
    body+=section('methods','Methods, provenance and reproducibility')
    body+=p('The report uses all four limit targets from the completed 130-job VNI/QNI campaign. Numeric performance covers 14 half-hour-grid leads from 30 minutes to seven days; rolling folds have separate training, selection, calibration, alert-tuning and evaluation partitions. Fixed and rolling samples are not combined. All-lead MAE is weighted by valid forecast pairs; RMSE uses squared errors. Overlapping origins create dependence, addressed partially by the paired seven-day resampling, not by treating every pair as independent.')
    body+=p('The original network studies supply 24 calendar months of data, but the primary rolling evaluation is one year. Historical first-publication timing and complete target-window availability have not been fully validated. The model selection dates precede evaluation, but the overall research periods have already been studied. The results are development evidence, not proof of live performance.')
    body+=p('The feature audit reuses saved model bundles and first checks their predictions against saved evaluation outputs. Its 128 audits cover four preselected seasonal months and four representative leads, not every issue/lead in the full year. Permutation shifts preserve time of day and joint columns within a group, but break relationships between groups. Dispersion across three shifts is perturbation sensitivity, not a confidence interval. No new market data was downloaded and no forecast model was retrained.')
    body+='<ul><li><a href="../data/limit_forecast_research_snapshot.json" download>Numerical results, examples, importance audit and source hashes</a></li><li><a href="../data/limit_forecast_research_build.json" download>Report build manifest</a></li><li><a href="vni_qni_forecast_experiment_research.html">Full forecasting research report</a></li><li><a href="forecast_experiment_framework.html">Complete experiment explorer</a></li><li><a href="../forecast_experiment_operations.md">Data requirements and operating instructions</a></li></ul>'
    body+=p('Rebuild from the committed snapshot with: python scripts/build_limit_forecast_report.py. Recompute metrics and feature importance from local saved artifacts with: python scripts/build_limit_forecast_report.py --extract. The latter requires the ignored original datasets and saved models. The HTML reads offline; linked downloads are separate committed files.')
    body+=p('Data cutoff: 31 August 2026. Report built '+datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')+'. Visual review is recorded separately from static validation.')+'</section>'
    body+='<style>.table-wrap{overflow-x:auto;max-width:100%}.chart-scroll{overflow-x:auto;max-width:100%}.chart-scroll>.plotly-graph-div{min-width:680px}nav{line-height:2.2}details{margin:24px 0}summary{font-weight:650;cursor:pointer}p{max-width:1100px}</style>'
    OUTPUT.write_text(render_page('VNI and QNI — directional limit forecasting research',body,accent='blue'),encoding='utf-8')
    manifest={'report_sha256':digest(OUTPUT),'snapshot_sha256':digest(SNAPSHOT),'generator_sha256':digest(Path(__file__)),
        'theme_sha256':digest(ROOT/'scripts/report_theme/report_theme.py'),'css_sha256':digest(ROOT/'scripts/report_theme/report.css'),
        'source_fingerprint':d['source_fingerprint'],'charts':figure_count,'importance_audits':d['importance_scope']['models'],
        'max_saved_prediction_reproduction_error_mw':float(imp.max_reproduction_error_mw.max()),
        'visual_review':'Not verified: local HTML browser previews have been blocked by browser policy; no alternate route used.'}
    (SNAPSHOT.parent/'limit_forecast_research_build.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({'html':str(OUTPUT),'charts':figure_count,'importance_audits':d['importance_scope']['models']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--extract',action='store_true');p.add_argument('--extract-only',action='store_true');args=p.parse_args()
    with threadpool_limits(limits=2):d=extract() if args.extract or args.extract_only else json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    if not args.extract_only:render(d)
