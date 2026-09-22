"""Cached VNI/QNI diagnostic reports. Never fits models or acquires sources.

Run: python -m scripts.build_ic_longform_assessments
"""
from __future__ import annotations

import base64
from collections import Counter
from datetime import datetime, timezone
from html import escape
import io
import json
import os
from pathlib import Path
import shutil
import importlib.metadata

os.environ.update(OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from threadpoolctl import threadpool_limits

from nemic.experiments.core import ROOT, digest
from nemic.fundamentals.balanced import _specs
from nemic.fundamentals.tracking import Ledger, atomic
from scripts.report_theme.report_theme import hero, metric, figure_html, render_page, matplotlib_style

DATA = ROOT/'data/forecast_experiments/qni_vni_fundamentals_v3'
OUT = ROOT/'reports/qni_vni_fundamentals_v3/longform'
TRACK = ROOT/'execution/qni_vni_fundamentals_v3/longform_assessments'
TARGETS = ['flow', 'export_tight', 'import_tight']
LABEL = {'flow': 'Flow', 'export_tight': 'Export tight limit', 'import_tight': 'Import tight limit'}
HOURS = {48: 24, 96: 48, 336: 168}
BAND = {0: '0.5–6h', 1: '6.5–24h', 2: '24.5–72h', 3: '72.5–168h'}
plt.rcParams.update(matplotlib_style())
plt.rcParams.update({'axes.spines.top': False, 'axes.spines.right': False})


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def statistics(frame, column='point'):
    a=frame.actual.to_numpy(float); p=frame[column].to_numpy(float)
    valid=np.isfinite(a)&np.isfinite(p); a=a[valid]; p=p[valid]
    if not len(a):return dict(n=0)
    e=p-a; ae=abs(e); denom=np.sum((a-a.mean())**2)
    return dict(n=len(a), mae=float(ae.mean()), rmse=float(np.sqrt(np.mean(e**2))),
                bias=float(e.mean()), median_ae=float(np.median(ae)), p90_ae=float(np.quantile(ae,.9)),
                p95_ae=float(np.quantile(ae,.95)), p99_ae=float(np.quantile(ae,.99)),
                max_ae=float(ae.max()), r2=float(1-np.sum(e**2)/denom) if denom else None)


def number(v, places=1):
    return '—' if v is None or pd.isna(v) else f'{v:,.{places}f}'


class Report:
    def __init__(self, connector):
        self.connector=connector; self.parts=[]; self.prose=[]; self.sections=[]; self.inputs=set(); self.initial_hashes={}
        self.downloads=OUT/'downloads'/connector; self.downloads.mkdir(parents=True,exist_ok=True)
        self.images=TRACK/connector; self.images.mkdir(parents=True,exist_ok=True)
        self.chart_count=0; self.table_count=0

    def source(self,path):
        resolved=Path(path).resolve()
        if resolved not in self.inputs:
            self.initial_hashes[resolved]=digest(resolved)
            self.inputs.add(resolved)
        return path

    def section(self, slug, title, paragraphs):
        if self.sections:self.parts.append('</section>')
        self.sections.append((slug,title)); self.parts.append(f'<section id="{slug}"><h2>{escape(title)}</h2>')
        self.prose.extend(['\n## '+title+'\n']+list(paragraphs))
        self.parts.extend(f'<p>{escape(p)}</p>' for p in paragraphs)

    def discuss(self, paragraph):
        self.prose.append(paragraph)
        self.parts.append(f'<p>{escape(paragraph)}</p>')

    def table(self, name, frame, caption, limit=None):
        frame=pd.DataFrame(frame); frame.to_csv(self.downloads/f'{name}.csv',index=False)
        shown=frame.head(limit) if limit else frame
        self.parts.append(f'<h3>{escape(caption)}</h3><div class="table-wrap" tabindex="0" aria-label="{escape(caption)}">'+
                          shown.to_html(index=False,border=0,float_format=lambda x:f'{x:,.3f}',na_rep='—')+'</div>'+
                          f'<p class="note"><a href="downloads/{self.connector}/{name}.csv">Download the full table</a></p>')
        self.prose.append(f'\nData: [full {name} table](downloads/{self.connector}/{name}.csv).\n')
        self.table_count+=1

    def chart(self,name,fig,title,note):
        fig.tight_layout(pad=1.7)
        buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=145,bbox_inches='tight');plt.close(fig)
        png=buffer.getvalue(); (self.images/f'{name}.png').write_bytes(png)
        encoded=base64.b64encode(png).decode('ascii')
        self.parts.append(figure_html(f'<img src="data:image/png;base64,{encoded}" alt="{escape(title)}" loading="lazy">',title,note))
        self.chart_count+=1


def load_predictions(report,stage):
    frames=[]; results=[]
    for path in sorted((DATA/'train'/report.connector/'balanced-v1'/stage).glob('*/*/band*/result.json')):
        result=read_json(report.source(path)); predpath=path.parent/'predictions.parquet'
        f=pd.read_parquet(report.source(predpath)); f['target']=result['target'];f['band']=result['band'];f['fold']=result['fold']
        assert not f.duplicated(['origin','delivery','lead']).any()
        required=['actual','point','network','persistence']
        if stage=='confirmation':
            required+=['seasonal48','seasonal336','q0.025','q0.1','q0.5','q0.9','q0.975']
        assert np.isfinite(f[required].to_numpy()).all()
        frames.append(f);results.append((path,result))
    frame=pd.concat(frames,ignore_index=True)
    assert not frame.duplicated(['target','origin','delivery','lead']).any()
    return frame,results


def build(connector,ledger):
    report=Report(connector); root=DATA/'balanced'/connector/'balanced-v1'
    status=lambda step: atomic(TRACK/'status.json',json.dumps(dict(connector=connector,step=step,updated=datetime.now(timezone.utc).isoformat())))
    status('loading cached predictions'); print(connector,'loading',flush=True)
    pred,results=load_predictions(report,'confirmation'); sensitivity,sens_results=load_predictions(report,'ecmwf_sensitivity')
    frozen=read_json(report.source(root/'frozen.json'));risk=read_json(report.source(root/'risk_summary.json'))
    assessment=read_json(report.source(DATA/'assessment/results.json'))
    audit=pd.DataFrame([r for r in assessment if r['connector']==connector and r['cohort']=='balanced-v1:pasa_coal'])
    primary_path=DATA/'features'/connector/'pasa_coal/table.parquet'
    schema=read_json(report.source(primary_path.with_suffix('.schema.json')))
    names=pq.ParquetFile(primary_path).schema_arrow.names; specs=_specs(names,schema)
    discoveries=[read_json(report.source(p)) for p in sorted((DATA/'train'/connector/'balanced-v1/discovery').glob('*/*/band*/result.json'))]
    checkpoints=pred[pred.lead.isin(HOURS)].copy();checkpoints['hours']=checkpoints.lead.map(HOURS)
    metrics=[]
    for (target,h),g in checkpoints.groupby(['target','hours']):
        for col in ['point','network','persistence','seasonal48','seasonal336','q0.5']:
            m=statistics(g,col);m.update(target=target,hours=int(h),forecast=col,days=int(g.origin.dt.normalize().nunique()))
            metrics.append(m)
    metrics=pd.DataFrame(metrics)
    rows=[]
    for (t,h),g in checkpoints.groupby(['target','hours']):
        m=statistics(g); n=statistics(g,'network');p=statistics(g,'persistence')
        rows.append(dict(target=t,hours=int(h),n=m['n'],MAE_MW=m['mae'],network_MAE_MW=n['mae'],
            skill_pct=100*(1-m['mae']/n['mae']),persistence_MAE_MW=p['mae'],RMSE_MW=m['rmse'],bias_MW=m['bias']))
    summary=pd.DataFrame(rows)
    cached=read_json(report.source(root/'horizon_scores.json'))
    for row in rows:
        parts=[x for x in cached['scores'] if x['target']==row['target'] and x['hours']==row['hours']]
        value=sum(x['model']['mae']*x['model']['n'] for x in parts)/sum(x['model']['n'] for x in parts)
        np.testing.assert_allclose(value,row['MAE_MW'],rtol=1e-10)
    direction='VIC1 → NSW1' if connector=='VNI' else 'NSW1 → QLD1'
    source,sink=('VIC1','NSW1') if connector=='VNI' else ('NSW1','QLD1')
    flow=summary[summary.target.eq('flow')].sort_values('hours')
    policy=('VNI improves flow and import-tight accuracy, but its export-tight alternatives increase error at all three requested checkpoints.'
            if connector=='VNI' else 'QNI shows large flow gains, while discovery selected the network recipe for every tight-limit band. Identical limit scores therefore mean the selected forecast is the control itself.')
    report.section('judgement','1. Assessment and principal findings',[
        f'This report assesses the {connector} balanced-v1 forecasting experiment in the signed {direction} convention. The strongest result is the improvement in flow MAE: '+
        ', '.join(f"{r.skill_pct:.1f}% at {r.hours:g} hours" for r in flow.itertuples())+'. '+policy,
        'That distinction between flow and transfer limits matters. A flow forecast describes the expected use of the interconnector; a tight-limit forecast estimates a directional restriction. Additional regional demand and renewable information can help explain flow without identifying the constraint equation, outage configuration or stability condition that will bind a future limit. A blended accuracy number across these targets conceals that difference, so this assessment keeps them separate.',
        'The headline comparison is the saved unadjusted point forecast against its matched network control. Simple persistence and seasonal controls are also assessed because beating a complex network model is insufficient if a simpler forecast performs better. A saved calibration-adjusted median is examined separately; it is a different output from the headline point forecast and must not silently replace it in the reported score.',
        'The study provides historical development evidence. Its global recipe and feature choices combine an early and a late discovery period before being applied across confirmation history. This means early confirmation periods are not a wholly untouched test of the complete selection process. The numerical gains describe the saved experiment, but they do not establish prospective performance of a model selected using only information available at each historical deployment date.',
        f"The combined fundamentals-plus-NOS risk experiment does not pass the historical acceptance gate. Its joint false-alert rate is {risk['aggregate']['both']['joint_false_alarms_per_day']:.3f} per day and its recall non-inferiority gate is {'passed' if risk['gates']['recall_noninferiority'] else 'failed'}. Operational provenance is also {'verified' if risk['operational_provenance_gate'] else 'unverified'}. The appropriate current use is research assessment and controlled follow-up, rather than an approved operational replacement."
    ])
    report.table('headline_accuracy',summary,'Primary forecast performance at the requested checkpoints')
    fig,axes=plt.subplots(1,3,figsize=(13,3.7),sharey=True)
    for ax,t in zip(axes,TARGETS):
        g=summary[summary.target.eq(t)];ax.bar(g.hours.astype(str),g.skill_pct,color='#5696b9');ax.axhline(0,color='#555',lw=.8);ax.set_title(LABEL[t]);ax.set_xlabel('Horizon (hours)')
    axes[0].set_ylabel('MAE improvement vs network (%)')
    report.chart('headline',fig,'Accuracy gains differ substantially by target','Saved point forecasts; positive skill means lower error. All percentages use matched rows within target and horizon.')

    status('coverage and feature audit')
    coverage=[]
    for (stage,frame) in [('Primary confirmation',pred),('ECMWF sensitivity',sensitivity)]:
        for t,g in frame.groupby('target'):
            coverage.append(dict(track=stage,target=t,folds=g.fold.nunique(),rows=len(g),origins=g.origin.nunique(),days=g.origin.dt.normalize().nunique(),first_origin=str(g.origin.min()),last_delivery=str(g.delivery.max()),leads=', '.join(str(int(v)) for v in sorted(g.lead.unique()))))
    report.section('scope','2. Data scope, chronology and what was actually tested',[
        f"There are {len(results)} primary confirmation cells and {len(sens_results)} ECMWF sensitivity cells for {connector}. The primary evaluation contains {pred.origin.nunique():,} distinct forecast origins; rows repeat those origins across targets and sampled horizons. The first scored origin is {pred.origin.min():%Y-%m-%d}, and the last scored delivery is {pred.delivery.max():%Y-%m-%d}. These dates describe scored history, not the much broader configured data acquisition period.",
        'The configured split begins with 60 training days followed by 14 days each for selection, calibration and alert-threshold choice, then 28 evaluation days. The training window expands as evaluation advances in 28-day increments. Rows enter a partition only when their delivery plus a half-hour maturity allowance falls before its end. Consequently each fold has an earlier final eligible origin at longer leads; a raw count of prediction rows is not a count of independent observations.',
        'The model was fitted and scored on 14 retained half-hour lead indices, not every interval from one to 336. The literal user-requested checkpoints are 24, 48 and 168 hours, corresponding to indices 48, 96 and 336. Literal 336 hours would require index 672 and is outside the retained coherent forecast coverage. It has no measured accuracy result. Neither gaps between sampled leads nor the missing two-week horizon are interpolated into apparent evidence.',
        'The discovery design deliberately reused early and late history to choose one recipe, family and feature set per target and band. Although each estimator fit respects its local chronological boundaries, a late discovery training window includes outcomes from earlier confirmation periods. A fresh evaluation entirely after the final selection freeze, or fully nested historical selection, is necessary to turn this into a clean estimate of forward deployment performance. This limitation also qualifies the cached significance tests.',
        'PASA/coal and ECMWF results are distinct information tracks. BOM was preferred by the acquisition policy, but this saved weather sensitivity is ECMWF exploratory history with publication/receipt limitations. It does not constitute a measured BOM comparison. Calendar labels in the retained naive timestamps follow the study NEM convention, fixed Australian eastern standard time; Victorian daylight-saving clock time is not used for the diagnostic hour bins.'
    ])
    report.table('coverage',coverage,'Coverage and effective evaluation sample')
    report.discuss('The discovery fold identifiers used for the global freeze are '+', '.join(sorted({d['fold'] for d in discoveries}))+'. Confirmation reuses the broader scored history, including earlier periods. The evidence tables distinguish these discovery decisions from each confirmation prediction; the distinction is essential when interpreting the reported gains.')
    cov=pred.assign(day=pred.origin.dt.normalize()).groupby(['fold','target']).size().unstack()
    fig,ax=plt.subplots(figsize=(11,4));cov.plot.bar(ax=ax);ax.set_ylabel('Prediction rows across sampled leads');ax.set_xlabel('Evaluation fold start');ax.tick_params(axis='x',rotation=35)
    report.chart('coverage',fig,'Mature evaluation support by fold','Counts include repeated horizons. Reduced support at long horizons is a maturity effect, not a model success.')

    groups=schema['groups']; parents=schema['parents']; candidate=set(specs['interactions'])
    feature_rows=[]
    for group in sorted(set(groups.values())):
        cols=[c for c in names if groups.get(c)==group]
        feature_rows.append(dict(group=group,available_columns=len(cols),primary_candidates=sum(c in candidate for c in cols),example=', '.join(cols[:2])))
    feature_rows=pd.DataFrame(feature_rows)
    report.section('features','3. Feature engineering and market interpretation',[
        f'The core directional comparison uses {source} as the source and {sink} as the sink. Endpoint differences are sink minus source, whereas generic regional-pair differences follow their stored pair ordering. The main balance proxy is demand50 minus unconstrained wind and solar availability. The coal-balance proxy subtracts forecast available coal capacity from that residual demand. These quantities describe forecast stress; neither is a complete reserve margin because hydro, gas, storage, other interconnectors and unit bidding are not fully represented.',
        'Regional inputs include demand quantiles, wind and solar UIGF, constrained renewable capacity, same-vintage ramps and the difference between unconstrained and constrained renewable forecasts. That last difference is a suppression proxy: it cannot automatically be interpreted as realised economic curtailment. A same-run requirement for ramp features helps avoid treating a forecast publication change as a physical change in supply or demand. Missingness and source-age indicators make source coverage visible to the estimator.',
        'The cross-region design includes all ten region pairs, signed and absolute differences, sums, normalized contrasts, endpoint totals and rest-of-NEM context. Joint endpoint demand asks whether both ends are under pressure; residual-demand differences ask which end has the stronger need for imports. Coal capacity differences and coal-balance differences provide a rough picture of available thermal support. Their statistical usefulness does not mean coal will actually dispatch at its available capacity.',
        'Interactions combine these balance measures with observed directional room, setter age, candidate switching gaps and tightening pressure. They are intended to distinguish a large regional imbalance when the network has room from the same imbalance when the corridor is close to a binding restriction. Available-coal concentration and recall information add fleet structure. Forecast temperatures, humidity, wind and spatial weather gradients exist in the wider design but are excluded, with their descendants, from the PASA/coal primary candidate set.',
        f"The stored schema makes {len(candidate):,} primary candidate columns available before screening, including network inputs; the separate own-anchor column is added during modelling. The network recipe has {len(specs['network'])} stored inputs plus that anchor. These counts describe candidates, not the columns that every winner uses. The source documentation also flags retrospective coal metadata and an assumed trading-day boundary; forecast-time availability is a provenance requirement still to be established for operational claims."
    ])
    report.table('feature_inventory',feature_rows,'Candidate feature families and actual primary eligibility')
    fig,ax=plt.subplots(figsize=(11,5)); feature_rows.set_index('group')[['available_columns','primary_candidates']].plot.barh(ax=ax);ax.set_xlabel('Columns');ax.set_ylabel('Feature family')
    report.chart('features',fig,'Feature breadth before reduction','Available columns are read from the physical cohort schema. Primary candidate counts apply weather and descendant exclusions.')

    selection=[];ablation=[];curves=[];stability=[]
    for d in discoveries:
        fs=d['feature_selection']; selection.append(dict(target=d['target'],band=BAND[d['band']],fold=d['fold'],method=fs['method'],fraction=fs['fraction'],raw=fs['raw_count'],retained=fs['selected_count'],seconds=fs['seconds']))
        for x in d['selection']:ablation.append(dict(target=d['target'],band=d['band'],fold=d['fold'],**x))
        for x in fs['inner_results']:curves.append(dict(target=d['target'],band=d['band'],discovery_fold=d['fold'],**{k:v for k,v in x.items() if k!='columns'}))
    for key,choice in frozen.items():
        ds=[d for d in discoveries if d['target']==choice['target'] and d['band']==choice['band']]
        sets=[set(d['selected_columns'][choice['winner']['recipe']]) for d in ds]
        inter=set.intersection(*sets); union=set.union(*sets)
        missing=[(child,p) for child in choice['columns'] for p in parents.get(child,[]) if p not in choice['columns']]
        stability.append(dict(target=choice['target'],band=BAND[choice['band']],recipe=choice['winner']['recipe'],family=choice['winner']['family'],frozen_features=len(choice['columns']),early_features=len(sets[0]),late_features=len(sets[-1]),jaccard=len(inter)/len(union),missing_parent_links=len(missing)))
    sel=pd.DataFrame(selection);stab=pd.DataFrame(stability); curves=pd.DataFrame(curves)
    report.section('selection','4. Feature reduction, recipe selection and stability',[
        'Feature reduction began inside the training history. The filter removes columns that are mostly missing, constant or highly correlated with an earlier main effect. Correlation grouping, standardized elastic-net coefficients and shallow-tree grouped permutation then compete as screening methods. Candidate subsets retain 25%, 50%, 75% or all ranked groups; a common ridge probe scores their inner chronological validation loss. The smallest eligible subset within one estimated standard error of the best is retained.',
        'The three non-network recipes are intersections with the same master selected set, rather than independently optimized searches of equal capacity. The main recipe drops named interaction terms; the interactions recipe retains them; the endpoint recipe excludes cross_region, weather_cross and nem_context families. The endpoint recipe can still contain regional main effects and other interaction terms. It should therefore not be interpreted as a strictly two-region-only ablation.',
        'For each target and band, discovery compares one ridge setting and one shallow boosting setting across four recipes. Average discovery selection MAE chooses the winner. The final frozen columns are the intersection of the early and late winning-recipe sets, falling back to their union only if the intersection is empty. The confirmation model is fitted on this frozen schema, which can be smaller than either discovery schema. This is a practical stability rule, but it also means the exact frozen intersection was not the feature set whose discovery MAE originally won.',
        f"Across the 12 target-band choices, Jaccard overlap between early and late selected recipe sets ranges from {stab.jaccard.min():.2f} to {stab.jaccard.max():.2f}; frozen sizes range from {stab.frozen_features.min()} to {stab.frozen_features.max()} columns. The direct frozen-schema audit finds {stab.missing_parent_links.sum()} missing interaction-parent links. Low overlap indicates sensitivity to historical regime or correlated substitutes, rather than proof that one unstable feature has a persistent physical effect.",
        'The reduction and ablation charts below are selection evidence, not a second estimate of held-out gains. They are useful for judging complexity and repeatability. They should be read alongside confirmation errors, because a recipe can look best during discovery and subsequently lose to the network or persistence control. Repeated elastic-net convergence warnings were recorded during the weather sensitivity run; a follow-up should audit converged screening and scaling before treating its feature ordering as stable.'
    ])
    report.table('frozen_selection',stab,'Frozen model choices and selection stability')
    for target in TARGETS:
        chosen=stab[stab.target.eq(target)]
        report.discuss(LABEL[target]+' has the following frozen progression from the shortest to longest band: '+
            '; '.join(f'{r.band}: {r.recipe}/{r.family}, {r.frozen_features} columns' for r in chosen.itertuples())+
            '. These are the actual selected estimators, not the entire engineered feature inventory. '+
            ('For this target, fundamentals were not retained in any winner; no fundamental-information gain should be inferred from its confirmation results.' if chosen.recipe.eq('network').all() else
             'The different counts and recipes indicate that the value of extra structure depends on forecast distance. Stability of a recipe name does not imply stability of its individual features.'))
    report.table('discovery_selection',sel,'Actual screening records',limit=24)
    report.table('inner_curves',curves.drop(columns=[],errors='ignore'),'Inner reduction diagnostics (full CSV)',limit=12)
    fig,axes=plt.subplots(1,2,figsize=(13,4.8));stab.assign(cell=stab.target+' / '+stab.band).plot.barh(x='cell',y='frozen_features',ax=axes[0],legend=False);axes[0].set_xlabel('Frozen feature count');axes[0].set_ylabel('')
    cf=curves[(curves.target=='flow')&(curves.band==1)].groupby(['method','fraction'],as_index=False).agg(mae=('mae','mean'),n_features=('n_features','mean'))
    for method,g in cf.groupby('method'):axes[1].plot(g.n_features,g.mae,'o-',label=method)
    axes[1].set_xlabel('Mean retained columns');axes[1].set_ylabel('Inner validation MAE (MW correction)');axes[1].legend(fontsize=8)
    report.chart('selection',fig,'Frozen complexity and the flow screening trade-off','Right panel: 6.5–24h band, averaged over discovery and inner folds; curves do not use confirmation performance.')
    abl=pd.DataFrame(ablation).groupby(['target','recipe','family'],as_index=False).mae.mean()
    report.table('recipe_ablation',abl,'Discovery recipe comparison; mean selection MAE across bands and discovery folds')
    fig,axes=plt.subplots(1,3,figsize=(13,3.8))
    for ax,t in zip(axes,TARGETS):
        abl[abl.target.eq(t)].pivot(index='recipe',columns='family',values='mae').plot.bar(ax=ax);ax.set_title(LABEL[t]);ax.set_ylabel('Selection MAE (MW)');ax.tick_params(axis='x',rotation=35)
    report.chart('ablation',fig,'Recipe and estimator screening results','Bands are averaged for a compact selection diagnostic; definitive comparisons use target and horizon specific confirmation results.')

    report.section('performance','5. Prediction performance and benchmark strength',[
        'Mean absolute error is the main interpretable measure here: an MAE of 250 MW means an average absolute miss of 250 MW over the scored rows. RMSE weights occasional large misses more heavily. Signed bias is prediction minus actual, so a positive number indicates systematic overprediction on the stored target scale. R-squared is descriptive relative to a constant test-sample mean and can be negative; it is not a percentage accuracy score.',
        policy+' The table compares each forecast on the same target, horizon and evaluation rows. This avoids making a longer-horizon forecast look better simply by comparing it with a baseline evaluated on a different set of days. The larger 168-hour errors also come from a smaller mature sample, so their difference from 24-hour errors reflects both forecast distance and sample support.',
        'Persistence repeats the value available at origin. The daily and weekly controls are the saved seasonal forecasts from the pipeline. These comparisons are essential for the tight-limit targets: stable limits can make persistence very competitive, while a regularized correction can introduce a sustained error if a new network regime differs from training. The winning discovery recipe is not automatically the best model for every subsequent fold.',
        'The q0.5 column adds the median calibration residual to the saved point forecast. It is evaluated below as an already-existing alternative output, not as a newly tuned correction. A substantial gap between point and q0.5 performance is evidence that calibration and the public point-output definition need closer attention. Choosing the better of them using these same evaluation results would require a fresh test afterwards.',
        'The final choice should be judged against the strongest admissible simple control, practical MW impact, seasonal stability, uncertainty coverage and risk behavior together. No reduction in one error metric automatically validates a constraint-warning threshold, and the current failed risk gates are not overturned by a favorable flow MAE.'
    ])
    report.table('all_metrics',metrics[['target','hours','forecast','n','days','mae','rmse','bias','r2','p95_ae']],'Matched forecast metrics; all errors in MW')
    for t in TARGETS:
        statements=[]
        for h in HOURS.values():
            z=metrics[(metrics.target==t)&(metrics.hours==h)].set_index('forecast')
            control=z.loc[['network','persistence','seasonal48','seasonal336']].mae.idxmin()
            gain=100*(1-z.loc['point','mae']/z.loc[control,'mae'])
            statements.append(f"at {h}h, point MAE {z.loc['point','mae']:.1f} MW versus the strongest listed control, {control}, at {z.loc[control,'mae']:.1f} MW ({abs(gain):.1f}% {'lower' if gain>=0 else 'higher'} error)")
        report.discuss(LABEL[t]+': '+'; '.join(statements)+'. The strongest control is identified retrospectively for diagnosis, not used to create a new forecast policy. '+
            ('The selected limit model therefore needs a persistence hurdle before further complexity is justified.' if connector=='QNI' and t!='flow' else
             'This comparison tests whether the network-only headline understates the strength of a simpler benchmark.'))
    fig,axes=plt.subplots(1,3,figsize=(13,4.1))
    for ax,t in zip(axes,TARGETS):
        metrics[metrics.target.eq(t)].pivot(index='hours',columns='forecast',values='mae').plot(ax=ax,marker='o');ax.set_title(LABEL[t]);ax.set_xlabel('Horizon (hours)');ax.set_ylabel('MAE (MW)');ax.legend(fontsize=6)
    report.chart('benchmarks',fig,'Accuracy against network, persistence and seasonal controls','Point is the frozen model output. q0.5 is the saved calibration-adjusted median, shown as a diagnostic comparison.')

    cases=[];day24=checkpoints[checkpoints.hours.eq(24)].copy()
    fig,axes=plt.subplots(3,3,figsize=(15,10))
    for ti,t in enumerate(TARGETS):
        g=day24[day24.target.eq(t)].copy();g['date']=g.delivery.dt.normalize();g['ae']=abs(g.point-g.actual)
        days=g.groupby('date').agg(mae=('ae','mean'),n=('ae','size'));days=days[days.n>=24].sort_values(['mae'])
        for ci,(kind,pos) in enumerate([('Best',0),('Median',len(days)//2),('Worst',-1)]):
            date=days.index[pos]; z=g[g.date.eq(date)].sort_values('delivery'); m=statistics(z)
            cases.append(dict(target=t,case=kind,date=str(date.date()),n=len(z),MAE_MW=m['mae'],network_MAE_MW=statistics(z,'network')['mae'],bias_MW=m['bias']))
            ax=axes[ti,ci]
            for col,color in [('actual','#282b30'),('point','#5696b9'),('network','#ce9a48')]:ax.plot(z.delivery.dt.hour+z.delivery.dt.minute/60,z[col],label=col,color=color,lw=1.3)
            ax.set_title(f'{LABEL[t]} · {kind.lower()}\n{date:%Y-%m-%d}',fontsize=10);ax.set_xlabel('Delivery hour (NEM)');ax.set_ylabel('MW')
    axes[0,0].legend(fontsize=8)
    report.section('paths','6. Actual versus predicted: representative and difficult days',[
        'An average score cannot show whether a model follows a daily shape, misses a level shift, or smooths a sharp transition. The nine panels below compare actual, model and network values at a fixed 24-hour lead. Each curve is a sequence of forecasts issued a day earlier, not a single-origin trajectory. This makes the comparison operationally interpretable while holding forecast distance constant.',
        'For each target, the best, median and worst eligible delivery day are selected by model daily MAE after outcomes are known. Days require at least 24 scored intervals. This deliberate case selection gives both favorable and adverse examples, but it is descriptive and must not be confused with independently chosen stress-test dates. The corresponding table states the date, row count, absolute error and bias.',
        'A forecast may follow turning points yet remain offset from actual values; that is a calibration or level problem. It may also hold roughly the right level while missing rapid transitions; that suggests missing regime or ramp information. In the tight-limit panels, abrupt changes should be interpreted with constraint and outage records before being attributed to weather or coal availability. The curves establish what was missed, not its physical cause.',
        'Actual-versus-predicted scatter plots provide the complementary full-sample picture. Deviations from the 45-degree line indicate systematic compression or expansion, and a dense central cloud with widely dispersed extremes identifies a model that works mainly in common conditions. The displayed scatter is deterministically sampled for readability; the surrounding tables and distribution statistics use every finite scored row.'
    ])
    report.table('case_days',cases,'Best, median and worst 24-hour delivery days')
    for t in TARGETS:
        z=next(c for c in cases if c['target']==t and c['case']=='Worst')
        report.discuss(f"The selected worst {LABEL[t].lower()} day is {z['date']}: MAE is {z['MAE_MW']:.1f} MW, network MAE {z['network_MAE_MW']:.1f} MW, and signed bias {z['bias_MW']:+.1f} MW. "+
            ('The absolute bias equals the MAE to rounding, meaning misses stayed on one side of actual throughout the scored day. That is a sustained level failure, not cancellation of small positive and negative misses.' if np.isclose(abs(z['bias_MW']),z['MAE_MW']) else
             'Comparing this signed bias with MAE helps distinguish a sustained level offset from errors on both sides of actual. The plotted sequence is necessary to see the missed transitions.'))
    report.chart('cases',fig,'Actual and forecast paths across selected days','Cases are selected retrospectively by error. These are sequences at a constant 24-hour lead; all units MW.')
    fig,axes=plt.subplots(1,3,figsize=(13,4.2))
    for ax,t in zip(axes,TARGETS):
        g=day24[day24.target.eq(t)];z=g.iloc[np.linspace(0,len(g)-1,min(3500,len(g)),dtype=int)]
        ax.scatter(z.actual,z.point,s=3,alpha=.2,color='#5696b9');lo=min(z.actual.min(),z.point.min());hi=max(z.actual.max(),z.point.max());ax.plot([lo,hi],[lo,hi],color='#ce9a48');ax.set_title(LABEL[t]);ax.set_xlabel('Actual (MW)');ax.set_ylabel('Point forecast (MW)')
    report.chart('scatter',fig,'Actual versus predicted at 24 hours','At most 3,500 evenly spaced rows per target; the 45-degree line represents a perfect point forecast.')

    tails=metrics[metrics.forecast.eq('point')][['target','hours','n','bias','median_ae','p90_ae','p95_ae','p99_ae','max_ae']]
    report.section('errors','7. Error distributions, bias and tail exposure',[
        'Error distributions separate the typical forecast from the costly exception. Median absolute error describes a central outcome, whereas P95 absolute error is the level exceeded by five percent of scored rows. The maximum is a single observed extreme and is highly sample-dependent. RMSE reacts strongly to tails; a large RMSE-to-MAE gap is a useful warning that the average miss understates occasional excursions.',
        'Signed residuals are forecast minus actual. For the stored directional tight-limit targets, positive residuals represent overstatement on that target scale. These directional bounds can be negative; they are not clipped to non-negative capacity. Their operational significance still depends on direction and how a forecast would be used. An apparently conservative negative bias can reduce overstatement while creating large absolute errors and poor availability estimates; it should not be counted as good forecasting solely because it lowers one risk statistic.',
        'The histograms show the middle 99% of residuals separately for each target so their shape remains legible. The tails are not discarded from any table. The exceedance curves use all absolute errors and show the fraction of rows above a chosen MW miss. Repeated origins and nearby deliveries make these observations dependent; these curves describe exposure in the study rather than independent incident probabilities.',
        'A model with a narrow central distribution but a heavy right tail may need explicit regime-change handling rather than further tuning of ordinary conditions. Conversely, a distribution that is broadly shifted suggests calibration drift or an unsuitable correction level. The point-versus-median comparison and monthly diagnostics help distinguish those possibilities. Any tail-focused retuning must use new training/validation history and preserve a separate evaluation period.'
    ])
    report.table('error_tails',tails,'Point-forecast error quantiles and extreme misses (MW)')
    for t in TARGETS:
        r=metrics[(metrics.target==t)&metrics.hours.eq(24)&metrics.forecast.eq('point')].iloc[0]
        report.discuss(f"For 24-hour {LABEL[t].lower()}, the median absolute miss is {r.median_ae:.1f} MW, P95 is {r.p95_ae:.1f} MW and P99 is {r.p99_ae:.1f} MW. The largest observed miss is {r.max_ae:.1f} MW. Signed bias is {r.bias:+.1f} MW, while RMSE is {r.rmse/r.mae:.2f} times MAE. "+
            ('The bias is large relative to average error, making level calibration a material issue rather than a secondary refinement.' if abs(r.bias)>r.mae*.5 else
             'The smaller aggregate bias should not be mistaken for small individual errors: opposite-signed misses can cancel in the mean while leaving substantial tail exposure.'))
    fig,axes=plt.subplots(2,3,figsize=(13,7.5))
    for j,t in enumerate(TARGETS):
        z=day24[day24.target.eq(t)];e=z.point-z.actual;lo,hi=np.quantile(e,[.005,.995]);axes[0,j].hist(e,bins=50,range=(lo,hi),color='#5696b9',density=True);axes[0,j].axvline(0,color='#333');axes[0,j].set_title(LABEL[t]);axes[0,j].set_xlabel('Signed error (MW)');axes[0,j].set_ylabel('Density')
        for col in ['point','network']:
            a=np.sort(abs(z[col]-z.actual));axes[1,j].plot(a,100*(1-np.arange(1,len(a)+1)/len(a)),label=col)
        axes[1,j].set_xlabel('Absolute error threshold (MW)');axes[1,j].set_ylabel('Rows exceeding threshold (%)');axes[1,j].legend(fontsize=8)
    report.chart('errors',fig,'Central residual shapes and full-range error exceedance','24-hour lead. Histograms display the central 99%; exceedance curves and quantile tables retain the complete error range.')

    status('condition diagnostics'); print(connector,'conditions',flush=True)
    base=DATA/'features'/connector/'table.parquet'; available=pq.ParquetFile(base).schema_arrow.names
    conditions={'Endpoint demand':'endpoint__demand50_sum','Endpoint renewable availability':'endpoint__renewables_uigf_sum','Endpoint available coal':'endpoint__coal_available_sum','Absolute endpoint residual difference':'endpoint__residual_uigf_difference','Source forecast temperature':source+'__demand__temperature_2m','Sink forecast temperature':sink+'__demand__temperature_2m'}
    columns=['origin','delivery','lead']+[v for v in conditions.values() if v in available]+[c for c in ['upper_switch_recent','lower_switch_recent'] if c in available]
    context=pd.read_parquet(report.source(base),columns=columns,filters=[('lead','==',48)])
    assert not context.duplicated(['origin','delivery','lead']).any()
    joined=day24.merge(context,on=['origin','delivery','lead'],how='left',validate='many_to_one',indicator=True)
    assert joined._merge.eq('both').all()
    cr=[];support=[]
    for title,col in conditions.items():
        if col not in joined:continue
        values=joined[col].abs() if title.startswith('Absolute') else joined[col]
        support.append(dict(condition=title,matched_rows=len(joined),finite_rows=int(np.isfinite(values).sum()),missing_pct=100*values.isna().mean(),minimum=values.min(),maximum=values.max()))
        q,edges=pd.qcut(values,q=4,duplicates='drop',retbins=True);code=q.cat.codes
        for (target,index),g in joined.groupby([joined.target,code]):
            if index<0:label='Missing';low=high=np.nan
            else:label=f'Q{index+1}';low=edges[index];high=edges[index+1]
            m=statistics(g);n=statistics(g,'network');cr.append(dict(condition=title,target=target,bin=label,low=low,high=high,n=len(g),days=g.origin.dt.normalize().nunique(),MAE_MW=m['mae'],network_MAE_MW=n['mae'],skill_pct=100*(1-m['mae']/n['mae']),bias_MW=m['bias']))
    for title,values in [('Delivery month',joined.delivery.dt.strftime('%Y-%m')),('Delivery hour',joined.delivery.dt.hour),('Recent constraint switch',np.where(joined[['upper_switch_recent','lower_switch_recent']].max(axis=1)>0,'Recent switch','No flagged switch'))]:
        for (t,b),g in joined.groupby([joined.target,values]):
            m=statistics(g);n=statistics(g,'network');cr.append(dict(condition=title,target=t,bin=str(b),low=np.nan,high=np.nan,n=len(g),days=g.origin.dt.normalize().nunique(),MAE_MW=m['mae'],network_MAE_MW=n['mae'],skill_pct=100*(1-m['mae']/n['mae']),bias_MW=m['bias']))
    for t,g in joined.groupby('target'):
        movement=abs(g.actual-g.persistence);q,edges=pd.qcut(movement,4,duplicates='drop',retbins=True)
        for idx,z in g.groupby(q.cat.codes):
            m=statistics(z);n=statistics(z,'network');cr.append(dict(condition='Realised movement from origin (outcome-derived)',target=t,bin=f'Q{idx+1}',low=edges[idx],high=edges[idx+1],n=len(z),days=z.origin.dt.normalize().nunique(),MAE_MW=m['mae'],network_MAE_MW=n['mae'],skill_pct=100*(1-m['mae']/n['mae']),bias_MW=m['bias']))
    cr=pd.DataFrame(cr);slices=cr[(cr.target=='flow')&cr.condition.isin(conditions)&cr.bin.ne('Missing')&(cr.n>=200)]
    cr['condition_unit']=cr.condition.map({k:('°C' if 'temperature' in k else 'MW') for k in conditions}).fillna('label / outcome diagnostic')
    best=slices.loc[slices.MAE_MW.idxmin()];worst=slices.loc[slices.MAE_MW.idxmax()]
    report.section('conditions','8. When the forecasts work well and when they struggle',[
        f"Among the adequately supported forecast-condition slices of 24-hour flow, the smallest measured MAE is {best.MAE_MW:.1f} MW in {best['condition']} {best['bin']} (range {best.low:.1f} to {best.high:.1f}; {best.n:,} rows). The largest is {worst.MAE_MW:.1f} MW in {worst['condition']} {worst['bin']} (range {worst.low:.1f} to {worst.high:.1f}; {worst.n:,} rows). These are overlapping descriptive slices, not independent regimes or causal estimates.",
        'The analysis joins forecast conditions using the exact origin, delivery and lead keys. It assesses joint endpoint demand, joint renewable availability, available coal and the magnitude of the residual-demand contrast. Each is split into quartiles of the evaluation sample. Those numeric cut points are published so low and high have a concrete meaning; they are not calibrated operating thresholds and must be fitted on training history if used in a future model.',
        'A high-demand or low-coal slice can have higher absolute error yet still show a larger improvement over network. Both values are displayed because a model can be useful precisely in difficult conditions. Temperature slices use archived forecasts, not realised weather, and are only diagnostic context for the PASA/coal model. Missing weather is shown with its support rather than silently assigned to a mild-weather category. Narrow temperature ranges or sparse extremes cannot establish heatwave performance.',
        'Month and delivery-hour profiles reveal drift and daily structure, while the recent-switch flag compares observations with and without an already-known change in the active constraint regime. They do not provide future constraint identities. Several conditions co-vary: demand, temperature, solar availability and season can describe much the same set of observations. These univariate comparisons cannot identify the marginal effect of any one input.',
        'The separate realised-movement diagnostic groups rows by the absolute change between actual delivery and origin persistence. It uses the outcome and is explicitly unavailable at issue time. A sharp rise in error in its upper quartile identifies large-change cases worth studying; it cannot itself be used as a live routing feature. Follow-up work should ask whether admissible forecast revisions, scheduled outages or observable network changes anticipate those cases.'
    ])
    report.table('condition_support',support,'Forecast-condition coverage and observed ranges')
    report.table('conditions',cr,'Conditional errors at 24 hours (full table available)',limit=60)
    for t in TARGETS:
        statements=[]
        for condition in ['Endpoint renewable availability','Endpoint available coal','Sink forecast temperature']:
            z=cr[(cr.target==t)&cr.condition.eq(condition)&cr.bin.isin(['Q1','Q4'])].set_index('bin')
            if {'Q1','Q4'}.issubset(z.index):
                statements.append(f"{condition.lower()}, Q1 to Q4: {z.loc['Q1','MAE_MW']:.1f} to {z.loc['Q4','MAE_MW']:.1f} MW MAE")
        months=cr[(cr.target==t)&cr.condition.eq('Delivery month')&(cr.n>=200)]
        strongest_month=months.loc[months.MAE_MW.idxmin()]; weakest_month=months.loc[months.MAE_MW.idxmax()]
        report.discuss(LABEL[t]+': '+'; '.join(statements)+f". Across months with at least 200 rows, error is lowest in {strongest_month['bin']} ({strongest_month.MAE_MW:.1f} MW) and highest in {weakest_month['bin']} ({weakest_month.MAE_MW:.1f} MW). These comparisons identify where to investigate, but co-varying season, operating state and source coverage prevent a causal attribution to any one fundamental.")
    fig,axes=plt.subplots(2,3,figsize=(13,7.5))
    for ax,(title,_) in zip(axes.flat,conditions.items()):
        z=cr[(cr.condition==title)&(cr.target=='flow')];ax.bar(z.bin,z.MAE_MW,color='#5696b9',label='point');ax.plot(np.arange(len(z)),z.network_MAE_MW,'o-',color='#ce9a48',label='network');ax.set_title(title,fontsize=10);ax.set_ylabel('Flow MAE (MW)');ax.legend(fontsize=7)
    report.chart('conditions',fig,'Flow error under forecast supply, demand and weather conditions','24-hour lead. Q1 to Q4 are evaluation-sample quartiles; ranges and support are given in the downloadable table.')
    fig,axes=plt.subplots(1,3,figsize=(14,4.2))
    for ax,t in zip(axes,TARGETS):
        z=cr[(cr.condition=='Delivery month')&(cr.target==t)];ax.plot(z.bin,z.MAE_MW,'o-',label='point');ax.plot(z.bin,z.network_MAE_MW,'o-',label='network');ax.set_title(LABEL[t]);ax.set_ylabel('24h MAE (MW)');ax.tick_params(axis='x',rotation=70);ax.legend(fontsize=8)
    report.chart('months',fig,'Accuracy through changing calendar conditions','Months have unequal support. Seasonal interpretation is descriptive and the global discovery reuse limitation still applies.')

    status('saved model importance and reload checks'); print(connector,'importance',flush=True)
    importance=[];parity=[];last=max(r['fold'] for _,r in results)
    for path,result in results:
        if result['fold']!=last:continue
        modelpath=report.source(path.parent/'model.joblib');bundle=joblib.load(modelpath);model=bundle['model'];cols=bundle['columns']
        if hasattr(model,'booster_'):values=model.booster_.feature_importance(importance_type='gain');kind='training split gain'
        else:values=abs(model[-1].coef_);kind='absolute standardized ridge coefficient'
        total=np.sum(values)
        for col,value in zip(cols,values):importance.append(dict(target=result['target'],band=result['band'],feature=col,group=groups.get(col,'own_anchor' if col=='own_anchor' else 'network'),kind=kind,share_pct=100*value/total if total else 0))
    imp=pd.DataFrame(importance);top=imp[imp.band.eq(1)].sort_values('share_pct',ascending=False).groupby('target').head(12)
    path,result=next((p,r) for p,r in results if r['fold']==last and r['target']=='flow' and r['band']==1)
    bundle=joblib.load(path.parent/'model.joblib');cols=bundle['columns'];model=bundle['model']
    sample=day24[(day24.target=='flow')&(day24.fold==last)].sort_values('origin').iloc[:2400].copy()
    xf=pd.read_parquet(report.source(primary_path),columns=list(dict.fromkeys(['origin','delivery','lead']+[c for c in cols if c!='own_anchor'])),filters=[('lead','==',48)])
    sample=sample.merge(xf,on=['origin','delivery','lead'],validate='one_to_one');x=sample[[c for c in cols if c!='own_anchor']].copy();x['own_anchor']=sample.persistence.to_numpy();x=x[cols]
    with threadpool_limits(limits=2):loaded=sample.persistence.to_numpy()+model.predict(x)
    np.testing.assert_allclose(loaded,sample.point,rtol=1e-6,atol=1e-6)
    parity.append(dict(target='flow',fold=last,hours=24,n=len(sample),max_absolute_difference=float(np.max(abs(loaded-sample.point))),status='passed'))
    baseline=np.mean(abs(loaded-sample.actual));permutation=[];days=sample.origin.dt.normalize();unique=sorted(days.unique());blocks=[np.flatnonzero(days.eq(d)) for d in unique]
    for group in sorted(set(groups.get(c,'own_anchor') for c in cols)):
        members={c for c in cols if groups.get(c,'own_anchor')==group}
        while True:
            extra={c for c in cols if any(p in members for p in parents.get(c,[]))}-members
            if not extra:break
            members.update(extra)
        changes=[]
        for fraction in [.25,.5,.75]:
            shift=max(1,min(len(blocks)-1,int(len(blocks)*fraction)));order=np.concatenate(blocks[shift:]+blocks[:shift])
            z=x.copy();columns=list(members);z[columns]=x.iloc[order][columns].to_numpy()
            with threadpool_limits(limits=2):estimate=sample.persistence.to_numpy()+model.predict(z)
            changes.append(float(np.mean(abs(estimate-sample.actual))-baseline))
        permutation.append(dict(group=group,perturbed_columns=len(members),n=len(sample),days=len(blocks),baseline_MAE_MW=baseline,mean_MAE_increase_MW=np.mean(changes),min_increase_MW=min(changes),max_increase_MW=max(changes)))
    perm=pd.DataFrame(permutation).sort_values('mean_MAE_increase_MW',ascending=False)
    lead_feature=top[top.target.eq('flow')].iloc[0];pg=perm.iloc[0]
    report.section('importance','9. What the saved models use: importance and perturbation',[
        f"In the final confirmation fold's 24-hour flow estimator, the largest native importance belongs to {lead_feature.feature}, accounting for {lead_feature.share_pct:.1f}% of that model's {lead_feature.kind}. The largest grouped perturbation effect is {pg.group}: rotating its columns and dependent interactions raises sample MAE by an average {pg.mean_MAE_increase_MW:.1f} MW. These quantify different aspects of the fitted model and should not be treated as interchangeable explanations.",
        'For boosted trees, native importance is the training split gain allocated to each feature. For ridge, it is the absolute standardized coefficient, normalized within that model. Gain can favor variables with many useful split points, and coefficients redistribute weight among correlated inputs. Shares sum within an estimator; a percentage for one estimator is not directly comparable to the same percentage in another estimator family. Directional causal effects cannot be inferred from either ranking.',
        'The top-feature panels show the final confirmation fold at the 24-hour boundary. The complete download retains all features and all four bands for that fold. They describe the saved fitted research models, not a full-history operational refit and not an average importance over every fold. Earlier/later selection stability in the previous section supplies a separate measure of robustness.',
        f'The flow perturbation check uses {len(sample):,} chronological rows across {len(blocks)} days from the final fold. Each feature family and its dependent interactions is rotated together in three non-zero day-block shifts, preserving the ordering within the moved blocks. Other families remain fixed. This disrupts temporal relationships and correlated cross-family combinations; it is a predictive reliance test, not a plausible intervention on the electricity market.',
        'The reported minimum and maximum are the spread of three rotations, not a confidence interval. Negative MAE change means disruption happened to improve this sample; it does not prove the feature should be deleted. The saved model reproduced its cached prediction on the importance sample within the stated tolerance. Any feature removal motivated by this post-hoc analysis requires new training-only selection and a fresh evaluation period.'
    ])
    report.discuss('The grouped perturbation operates on the correction estimator inputs. The additive origin-persistence component of the final prediction remains fixed, including when the own_anchor input is rotated. This estimates reliance inside the correction model, not the full value of historical levels to the complete forecast. Correlated copies in different groups also mean family effects are neither independent nor additive.')
    for t in TARGETS:
        leaders=top[top.target.eq(t)].head(3)
        report.discuss(LABEL[t]+' relies most heavily, under its own native ranking, on '+
            ', '.join(f'{r.feature} ({r.share_pct:.1f}%)' for r in leaders.itertuples())+
            '. Lag and anchor terms summarize the already-observed operating state; regional balance terms provide forward context. If both a target lag and own_anchor appear, they can encode the same level and split importance between correlated copies. Treat their combined information, not their ordering, as the substantive signal.')
    report.table('native_importance',imp.sort_values('share_pct',ascending=False),'Native importance for all final-fold models (top rows displayed)',limit=15)
    report.table('top_importance_24h',top[['target','feature','group','kind','share_pct']],'Leading features in the three 24-hour models')
    report.table('group_permutation',perm,'Grouped day-block permutation, final-fold 24-hour flow')
    report.table('reload_parity',parity,'Saved-model prediction reproduction')
    fig,axes=plt.subplots(3,1,figsize=(12,13))
    for ax,t in zip(axes,TARGETS):
        g=top[top.target.eq(t)].head(10).sort_values('share_pct');ax.barh(g.feature,g.share_pct,color='#5696b9');ax.set_title(LABEL[t]);ax.set_xlabel('Within-model importance share (%)');ax.tick_params(axis='y',labelsize=9)
    report.chart('importance',fig,'Leading predictive inputs at 24 hours','Final confirmation fold only. Training split gain for boosted models; standardized coefficient magnitude for ridge models.')
    fig,ax=plt.subplots(figsize=(10,4.5));g=perm.sort_values('mean_MAE_increase_MW');ax.barh(g.group,g.mean_MAE_increase_MW,color='#8370b4');ax.axvline(0,color='#555');ax.set_xlabel('Mean increase in sample MAE after permutation (MW)')
    report.chart('permutation',fig,'Model reliance on feature families','Three deterministic day-block rotations with descendant interactions. This is a descriptive post-hoc diagnostic, not a selection test.')

    interval=[]
    for (t,h),g in checkpoints.groupby(['target','hours']):
        for nominal,lo,hi in [(80,'q0.1','q0.9'),(95,'q0.025','q0.975')]:
            interval.append(dict(target=t,hours=int(h),nominal_pct=nominal,n=len(g),coverage_pct=100*((g.actual>=g[lo])&(g.actual<=g[hi])).mean(),mean_width_MW=(g[hi]-g[lo]).mean(),crossed=int((g[lo]>g[hi]).sum()),point_MAE_MW=statistics(g)['mae'],median_MAE_MW=statistics(g,'q0.5')['mae']))
    interval=pd.DataFrame(interval)
    report.section('calibration','10. Calibration, prediction intervals and the median output',[
        'Intervals were built by adding fixed residual quantiles from each fold and band calibration partition to the saved point prediction. Their nominal 80% and 95% labels describe the intended probability mass, not an observed guarantee. Empirical coverage is the percentage of subsequent actual values inside each interval; width measures how much uncertainty the model expresses to obtain that coverage.',
        'An interval can be ordered and still be miscalibrated. Undercoverage means the reported range excludes too many outcomes; overcoverage can mean useful conservatism or unnecessarily wide bands. A fixed residual adjustment cannot adapt fully to time-varying volatility, switching regimes or seasonal stress. Coverage should therefore be checked by horizon and target before aggregating across the study.',
        'The q0.5 median differs from the point forecast by the calibration median residual. For a model that systematically underpredicts a limit, this can materially reduce MAE without refitting the estimator. It may also harm accuracy when the offset changes again during evaluation. Both scores are shown to reveal that behavior, while the original point remains the headline output. This is especially relevant before deciding whether forecast skill should be credited to structural features or to a simple level correction.',
        'A follow-up should predeclare whether the delivered point is the raw correction model or the calibrated median. Adaptive calibration should be fitted only with outcomes already mature at issue time, and its evaluation should compare like-for-like calibrated network and simple controls. The existing intervals are a useful diagnostic starting point; their coverage does not remove the need for provenance and event-risk gates.'
    ])
    report.table('interval_calibration',interval,'Empirical interval calibration and point-versus-median error')
    for t in TARGETS:
        z=interval[(interval.target==t)&interval.nominal_pct.eq(80)].set_index('hours')
        report.discuss(f"For {LABEL[t].lower()}, nominal 80% coverage is {z.loc[24,'coverage_pct']:.1f}% at 24h and {z.loc[168,'coverage_pct']:.1f}% at 168h, with mean interval widths {z.loc[24,'mean_width_MW']:.1f} and {z.loc[168,'mean_width_MW']:.1f} MW. The 24h saved median has MAE {z.loc[24,'median_MAE_MW']:.1f} MW versus raw point MAE {z.loc[24,'point_MAE_MW']:.1f} MW. "+
            ('Long-horizon coverage falls materially short of the intended rate. Ordering alone is plainly not sufficient calibration evidence.' if z.loc[168,'coverage_pct']<75 else
             'This aggregate coverage is informative, but conditional undercoverage may remain within high-error regimes.'))
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,t in zip(axes,TARGETS):
        for nominal in [80,95]:
            g=interval[(interval.target==t)&(interval.nominal_pct==nominal)];ax.plot(g.hours,g.coverage_pct,'o-',label=f'{nominal}% interval');ax.axhline(nominal,lw=.8,ls='--')
        ax.set_ylim(0,101);ax.set_title(LABEL[t]);ax.set_xlabel('Hours');ax.set_ylabel('Observed coverage (%)');ax.legend(fontsize=8)
    report.chart('calibration',fig,'Nominal intervals versus realised coverage','Coverage uses each target and literal horizon separately. Dashed lines mark nominal probabilities.')

    sensitivity_rows=[]
    for (t,b),g in sensitivity.groupby(['target','band']):
        m=statistics(g);n=statistics(g,'network');sensitivity_rows.append(dict(target=t,band=BAND[b],rows=len(g),days=g.origin.dt.normalize().nunique(),MAE_MW=m['mae'],network_MAE_MW=n['mae'],skill_pct=100*(1-m['mae']/n['mae'])))
    sr=pd.DataFrame(sensitivity_rows)
    report.section('weather','11. Weather sensitivity and limits on provider conclusions',[
        'The ECMWF sensitivity reruns the frozen recipe and estimator family on the separately labelled weather cohort, with feature screening restricted to its training partition. It does not simply append weather to every selected primary model. In particular, a frozen network recipe can remain a network model in the weather cohort. Calling all sensitivity results weather uplift would therefore overstate what was tested.',
        'The table compares each sensitivity model against the network control on its own matched rows. Those within-cohort skill values are valid descriptions of the saved run. They cannot be subtracted from primary scores to estimate a pure weather benefit: the cohort has different coverage, fold dates and training samples, and the screening may choose different feature sets.',
        'No clean BOM-versus-ECMWF tournament was completed on common receipt-verified historical cycles. The retained ECMWF track carries the study publication assumptions and provider-history qualification. Sparse regional demand, corridor and renewable sites approximate broad conditions; they are not line-specific thermal ratings or plant cooling-water observations. Weather should be assessed as forecast context rather than an engineering replacement for network limits.',
        'A stronger follow-up would hold origin/delivery rows, model family, capacity and training windows constant, compare PASA/coal against PASA/coal plus one weather provider, and report incremental error by temperature, wind and humidity regime. Publication-delay shifts should be applied before feature selection. That design would isolate incremental forecast information and measure whether any benefit survives the loss of optimistic availability assumptions.'
    ])
    report.table('weather_sensitivity',sr,'Separate ECMWF sensitivity: matched model and network errors')
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,t in zip(axes,TARGETS):
        g=sr[sr.target.eq(t)];ax.bar(g.band,g.skill_pct,color='#268a87');ax.axhline(0,color='#555');ax.set_title(LABEL[t]);ax.set_xlabel('Lead band');ax.set_ylabel('MAE skill (%)');ax.tick_params(axis='x',rotation=30)
    report.chart('weather',fig,'ECMWF cohort sensitivity by target and band','Each bar is measured against the network control in the same sensitivity cohort. These are not weather-only causal gains.')

    risk_rows=[]
    for recipe,item in risk['aggregate'].items():
        for d,z in item['directions'].items():
            delta=item['recall_difference'][d];risk_rows.append(dict(recipe=recipe,direction=d,incidents=z['incidents'],recall_pct=z['recall']*100,precision_pct=z['precision']*100,brier=z['brier'],average_precision=z['average_precision'],joint_false_alerts_day=item['joint_false_alarms_per_day'],recall_delta_pp=100*delta['delta_recall'],lower95_pp=100*delta['ci95'][0],upper95_pp=100*delta['ci95'][1]))
    risk_rows=pd.DataFrame(risk_rows);both=risk['aggregate']['both'];failed=', '.join(k.replace('_',' ') for k,v in risk['gates'].items() if not v)
    evidence=[]
    for r in audit.to_dict('records'):
        evidence.append(dict(target=r['target'],band=BAND[r['band']],days=r['evaluation_days'],holm_p=r['holm_pvalue'],point_skill_supported=r['point_skill_supported'],overstatement_supported=r['overstatement_supported'],decision=r['decision']))
    report.section('risk','12. Statistical evidence, NOS risk and acceptance decision',[
        f"The cached paired audit supports the predefined point-skill condition in {int(audit.point_skill_supported.sum())} of 12 primary target-band cells. The capacity-overstatement condition is recorded as supported in {int(audit.overstatement_supported.sum())} cells, including flow cells where that directional condition is not applicable. These are band-level historical tests, not significance tests of the three individual checkpoint percentages. All 12 primary cells carry the connector's failed risk decision.",
        'The paired point audit averages lead losses within origins and then across calendar days, examines 7- and 14-day blocks, and adjusts p-values across the assessed family using Holm correction. Its practical skill threshold is a two-percent MAE improvement. The uncertainty calculations account for dependence more carefully than treating every row as independent, but they do not correct the global discovery-history reuse or historical publication-provenance problems.',
        'The NOS experiment uses a fixed shallow contraction classifier in four information combinations: network, fundamentals, NOS and both. It operates at a two-hour issue point with a 30–120 minute warning window. Its probabilities and joint directional alert thresholds have separate calibration and alert partitions. This task is different from predicting a 24-hour flow value; a good flow model may still fail to warn of a sudden limit contraction.',
        f"For {connector}, seven eligible folds provide {both['directions']['export']['incidents']} export and {both['directions']['import']['incidents']} import incidents. The combined recipe's recalls are {100*both['directions']['export']['recall']:.1f}% and {100*both['directions']['import']['recall']:.1f}% respectively, with {both['joint_false_alarms_per_day']:.3f} joint false alerts per day. The failed component gates are {failed}. Recall non-inferiority requires the lower paired 95% difference bound to remain above minus two percentage points; a favorable point estimate alone cannot pass that test.",
        'Operational promotion is independently blocked by reconstructed NOS mapping and missing historical receipt verification. The broader audit still lists publication-delay and coal-day-boundary sensitivity work. Therefore completed computation is not equivalent to completion of every scientific validation originally proposed. The recommendations below prioritize those unresolved questions instead of treating test-suite success or finished model files as deployment evidence.'
    ])
    report.table('risk_factorial',risk_rows,'Four-way NOS/fundamentals event-risk assessment')
    report.table('paired_acceptance',evidence,'Cached paired audit and conservative acceptance decisions')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5));risk_rows.pivot(index='recipe',columns='direction',values='recall_pct').plot.bar(ax=axes[0]);axes[0].set_ylabel('Incident recall (%)');axes[0].tick_params(axis='x',rotation=20)
    alarms=risk_rows.groupby('recipe').joint_false_alerts_day.first();alarms.plot.bar(ax=axes[1],color='#8370b4');axes[1].axhline(3,color='#b44',ls='--',label='3/day budget');axes[1].set_ylabel('Joint false alerts/day');axes[1].tick_params(axis='x',rotation=20);axes[1].legend()
    report.chart('risk',fig,'Warning recall and the joint false-alert budget','Seven held-out classifier folds; incident definitions and source-availability assumptions are retained from the saved risk study.')

    suggestions=[
        dict(priority=1,proposal='Untouched prospective or fully nested test',evidence='Global choices use the late discovery period',test='Freeze the full procedure before a new evaluation window; compare target-specific controls',success='Skill survives at least eight weekly blocks without evaluation reuse'),
        dict(priority=2,proposal='Define point output and adaptive calibration',evidence='Raw point and saved q0.5 have different scores',test='Predeclare point/median policy; calibrate only on mature history and match baseline calibration',success='Lower MAE and stable interval coverage on a fresh test'),
        dict(priority=3,proposal='Target-specific model routing',evidence=policy,test='Keep simple controls in training-only comparison; route by target and lead band',success='Beat the strongest admissible control for each proposed replacement'),
        dict(priority=4,proposal='Constraint transitions and future network context',evidence='Flow gains do not guarantee improved tight limits',test='Add issue-time outage plans, candidate/RHS context and forecast revisions with provenance',success='Lower tail errors in predeclared switch and high-movement regimes'),
        dict(priority=5,proposal='Risk threshold and event model redesign',evidence='Failed gates: '+failed,test='Fit joint thresholds with a validation safety margin; evaluate incident recall and false alerts',success='Joint rate <=3/day and recall lower bound >=-2 pp'),
        dict(priority=6,proposal='Matched weather and source-time sensitivities',evidence='ECMWF cohort differs; receipt and coal boundaries remain unverified',test='Same-row weather ablation; delay shifts; 00:00 versus 04:00 coal day audit',success='Incremental weather gain persists under conservative vintage assumptions'),
        dict(priority=7,proposal='Feature stability and sparse interactions',evidence=f'Frozen Jaccard range {stab.jaccard.min():.2f}–{stab.jaccard.max():.2f}',test='Converged screening, hierarchy audit, foldwise group stability and constrained interactions',success='Comparable error with a smaller, stable, fully auditable feature set')]
    strongest=flow.loc[flow.skill_pct.idxmax()]
    report.section('improvements','13. Improvement programme and final judgement',[
        f"The most promising result to preserve is {connector} flow: the strongest measured checkpoint gain is {strongest.skill_pct:.1f}% at {int(strongest.hours)} hours. {policy} The next iteration should treat each target and band as a separate replacement decision. There is little justification for carrying a weaker limit model forward merely because another target benefits from the same broad feature framework.",
        'The first priority is evaluation design. Freeze the full selection procedure before an untouched period, or reconstruct a genuinely nested historical experiment in which every choice precedes its evaluation. Continue to use mature delivery labels and independent calibration/alert windows. This addresses the most serious limitation on interpretation and should precede another broad feature search.',
        'The second priority is output and calibration discipline. Compare the raw point, predeclared calibrated median, network and simple persistence policies under identical timing rules. Investigate sustained residual shifts and conditional coverage. Where limits are persistent, a level correction that looks sensible during discovery can be much worse than repeating the latest known value. A controlled routing or blending rule can be useful, but it must be selected on training/validation history rather than by choosing retrospectively from these scores.',
        'The third priority is information about future constraint changes. The condition and tail analyses identify cases for engineering review, but their physical causes require linked outage, constraint equation and forecast-revision evidence. Region-wide weather and coal capacity are broad proxies. Adding more products of those proxies may increase complexity without resolving missing network information. Concentrate new interactions on hypotheses with stable support and check their parent closure after the final freeze.',
        'Risk deserves its own follow-up rather than being treated as an appendix to point accuracy. The event detector, probability calibration and shared false-alert budget must be judged jointly. Validate threshold safety margins under changing incident rates, retain a network-only warning control, and quantify recall uncertainty by direction. Publication-delay, coal trading-day and receipt-provenance audits are necessary parts of that exercise.',
        'The priority order below is a judgement based on the measured weaknesses; it is not a forecast of how much accuracy any proposed change will gain. The adjacent chart restates the current checkpoint evidence that motivates target-specific development. This report is suitable for reviewing the experiment and choosing the next controlled study. It does not certify production readiness or close unexecuted source and stress-test requirements.'
    ])
    report.table('improvement_programme',suggestions,'Prioritized improvements with measurable follow-up tests')
    fig,ax=plt.subplots(figsize=(10,4.6));pivot=summary.pivot(index='target',columns='hours',values='skill_pct').reindex(TARGETS);image=ax.imshow(pivot.values,cmap='RdYlGn',vmin=-15,vmax=40,aspect='auto');ax.set_xticks(range(3),pivot.columns.astype(str));ax.set_yticks(range(3),[LABEL[t] for t in pivot.index]);ax.set_xlabel('Horizon (hours)')
    for i in range(3):
        for j in range(3):ax.text(j,i,f'{pivot.iloc[i,j]:+.1f}%',ha='center',va='center',fontsize=12)
    fig.colorbar(image,ax=ax,label='MAE skill vs network (%)')
    report.chart('priorities',fig,'Evidence for target-specific improvement priorities','Measured skill is shown; expected gains from proposed experiments are not estimated.')

    report.parts.append('</section>')
    methodology=ROOT/'execution/qni_vni_fundamentals_v3/methodology'
    for name in ['methodology.md','feature_research.md','selection_review.md','longform_assessment_protocol.md']:
        p=report.source(methodology/name);(OUT/'methodology').mkdir(exist_ok=True);shutil.copy2(p,OUT/'methodology'/name)
    report.source(Path(__file__));report.source(ROOT/'scripts/report_theme/report_theme.py');report.source(ROOT/'scripts/report_theme/report.css');report.source(ROOT/'configs/experiments/qni_vni_fundamentals_v3.json')
    report.parts.append('<section id="methods"><h2>Methodology, evidence and reproducibility</h2><p>Rebuild from saved study artifacts with <code>python -m scripts.build_ic_longform_assessments</code>. All charts are embedded images; no network connection or JavaScript runtime is required. Download tables accompany the HTML in the downloads directory.</p><ul>'+''.join(f'<li><a href="methodology/{n}">{escape(n)}</a></li>' for n in ['methodology.md','feature_research.md','selection_review.md','longform_assessment_protocol.md'])+'</ul><details><summary>Read the assessment protocol inside this report</summary><pre>'+escape((methodology/'longform_assessment_protocol.md').read_text(encoding='utf-8'))+'</pre></details></section>')
    nav='<nav>'+''.join(f'<a href="#{slug}">{escape(title.split(". ",1)[1])}</a>' for slug,title in report.sections)+'<a href="#methods">Methodology</a></nav>'
    head=hero('Interconnector forecast assessment',connector+' forecast performance','Evidence, mechanisms and limitations',f'A detailed assessment of the {direction} balanced-v1 experiment, covering forecast fundamentals, selected models, actual errors and conditions of failure.',[datetime.now(timezone.utc).strftime('%Y-%m-%d'),'Historical development evidence','Research status','24 / 48 / 168 hours'])
    kpi='<div class="metrics">'+''.join([metric('Flow skill at 24h',f'{flow.iloc[0].skill_pct:.1f}%','MAE improvement vs network'),metric('Confirmation cells',len(results),'10 chronological evaluation folds'),metric('Risk false alerts/day',f"{both['joint_false_alarms_per_day']:.3f}",'Joint budget: 3 per day'),metric('Promotion','Not approved','Statistical and provenance gates')])+'</div>'
    css='<style>section>p{max-width:1040px;line-height:1.8}.table-wrap{contain:inline-size}main{min-width:0}.chart-scroll{overscroll-behavior-x:contain}.chart-scroll img{min-width:1000px;max-width:100%}.table-wrap table{white-space:normal;min-width:760px}td,th{overflow-wrap:anywhere}figure{border-top:2px solid #4c94df}section{border-top:1px solid #dfe3eb;padding-top:10px}@media print{.chart-scroll img{min-width:0}}</style>'
    html=render_page(connector+' — Detailed forecast assessment',head+kpi+nav+css+''.join(report.parts),plotly=False)
    output=OUT/f'{connector}_assessment.html';atomic(output,html)
    atomic(OUT/f'{connector}_assessment.md',f'# {connector} detailed forecast assessment\n\n'+ '\n\n'.join(report.prose))
    status('hashing and validating evidence')
    # Full source hashes protect all model results, predictions and projected feature inputs.
    final_hashes={p:digest(p) for p in sorted(report.inputs)}
    assert final_hashes==report.initial_hashes, 'Source artifacts changed while building report'
    manifest=dict(connector=connector,built=datetime.now(timezone.utc).isoformat(),forecast_rows=len(pred),confirmation_cells=len(results),sensitivity_cells=len(sens_results),
                  analytic_sections=len(report.sections),charts=report.chart_count,tables=report.table_count,
                  prose_words=len(' '.join(report.prose).split()),visual_layout_review='unverified: browser local-file access policy',
                  input_hashes={str(p.relative_to(ROOT)):h for p,h in final_hashes.items()},
                  output_sha256=digest(output),reload_parity=parity,source_unchanged=True,
                  rebuild_command='python -m scripts.build_ic_longform_assessments',
                  first_scored_origin=str(pred.origin.min()),last_scored_delivery=str(pred.delivery.max()),
                  dependencies={p:importlib.metadata.version(p) for p in ['numpy','pandas','pyarrow','matplotlib','scikit-learn','lightgbm','joblib']},
                  limitations=['Historical discovery reuse; not an untouched prospective test','Source receipt and coal/publication sensitivities remain unresolved','Native importance is not causal; permutation is diagnostic','336-hour forecast unavailable'])
    atomic(OUT/f'{connector}_manifest.json',json.dumps(manifest,indent=2))
    assert report.chart_count>=len(report.sections) and report.table_count>=len(report.sections)
    assert manifest['prose_words']>=3000
    print(connector,'done',manifest['prose_words'],'words',report.chart_count,'charts',report.table_count,'tables',flush=True)
    return output,OUT/f'{connector}_manifest.json'


def main():
    OUT.mkdir(parents=True,exist_ok=True);TRACK.mkdir(parents=True,exist_ok=True)
    ledger=Ledger()
    for connector in ['VNI','QNI']:
        with ledger.job(f'report/longform/{connector}',acceptance='Cached, target-specific long-form assessment with condition/importance diagnostics') as (artifacts,checkpoint):
            checkpoint({'step':'building','connector':connector})
            output,manifest=build(connector,ledger);artifacts.extend([output,manifest])
            checkpoint({'step':'rendered','visual_layout_review':'pending permitted visual inspection'})
    atomic(TRACK/'status.json',json.dumps(dict(stage='reports_generated',connectors=['VNI','QNI'],visual_layout_review='unverified',updated=datetime.now(timezone.utc).isoformat()),indent=2))


if __name__=='__main__':
    main()
