"""INTERFLOW — local NEM conditional forecast and backtest workspace."""
import base64,io,json,functools
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash,html,dcc,Input,Output,State,ALL,ctx,no_update
import joblib
from nemic.common import *
from nemic.model import Design,IDS,BANDS,band,predict,chosen
from nemic.scenario import template,run_scenario
from nemic.ui import *

app=Dash(__name__,title='INTERFLOW · NEM',suppress_callback_exceptions=True,update_title=None)
server=app.server
LABELS={'flow':'Dispatch flow','export':'Export limit','import':'Import limit','export_tight':'Tightest export limit','import_tight':'Tightest import limit'}
METHOD_LABELS={'selected':'Selected + calibrated','network':'Network history','weather':'Renewables + weather','fundamentals':'Demand + renewables','availability':'Renewable availability','persistence':'Persistence','seasonal':'Same week slot','AEMO':'AEMO predispatch'}

@functools.lru_cache(maxsize=1)
def design():return Design()

@functools.lru_cache(maxsize=1)
def model_assets():
    return joblib.load(MODELS/'conditional_cache.joblib'),[joblib.load(MODELS/f'network_{t}.joblib') for t in TARGETS],json.loads((MODELS/'selection.json').read_text())

@functools.lru_cache(maxsize=64)
def snapshot(ic,origin):
    d=design();origin=pd.Timestamp(origin);oi=d.time.get_indexer([origin])[0]
    if oi<337:raise ValueError('Origin must have sufficient observed history.')
    i=IDS.index(ic);h=np.arange(1,min(337,len(d.time)-oi))
    begin=d.time.searchsorted(pd.Timestamp('2026-03-01'))+((oi-d.time.searchsorted(pd.Timestamp('2026-03-01')))//336)*336
    path=RESULTS/'predictions'/f'{ic}_{begin}.parquet'
    if path.exists():
        out=pd.read_parquet(path,filters=[('origin_idx','==',oi)]).copy()
    else:
        ci=np.full(len(h),i);os=np.full(len(h),oi);vi=os+h
        cache,models,configs=model_assets();pred=predict(d,ci,os,h,cache,models);sel=chosen(d,ci,vi,h,pred,configs)
        out=pd.DataFrame({'origin_idx':os,'valid_idx':vi,'h':h,'band':band(h)})
        for j,t in enumerate(TARGETS):
            out[t+'_actual']=d.y[ci,vi,j]
            for m,a in pred.items():out[t+'_'+m]=a[:,j]
            for q,a in sel[t].items():out[t+'_'+q]=a
    out['time']=d.time[out.valid_idx.to_numpy()]
    for j,t in enumerate(['export','import']):out[t+'_threshold']=d.threshold[i,out.valid_idx.to_numpy(),j]
    return out

def get_scores():
    path=RESULTS/'scores.csv'
    return pd.read_csv(path) if path.exists() else pd.DataFrame()

def origin_value(date,clock):return str(pd.Timestamp(str(date)+' '+clock))

def forecast_figure(s,target,hours=168):
    s=s[s.h<=hours*2];fig=go.Figure()
    fig.add_trace(go.Scatter(x=s.time,y=s[target+'_p90'],mode='lines',line=dict(width=0),showlegend=False,hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=s.time,y=s[target+'_p10'],mode='lines',line=dict(width=0),fill='tonexty',fillcolor='rgba(73,217,208,.12)',name='P10–P90',hoverinfo='skip'))
    fig.add_trace(go.Scatter(x=s.time,y=s[target+'_actual'],name='Actual',line=dict(color='#c1cad7',width=1.5)))
    fig.add_trace(go.Scatter(x=s.time,y=s[target+'_p50'],name='P50',line=dict(color=CYAN,width=2)))
    fig.add_trace(go.Scatter(x=s.time,y=s[target+'_persistence'],name='Persistence',line=dict(color='#687b92',width=1,dash='dot')))
    if target!='flow':
        direction='export' if target.startswith('export') else 'import'
        fig.add_trace(go.Scatter(x=s.time,y=s[direction+'_threshold'],name='50% restriction threshold',line=dict(color=ORANGE,width=1,dash='dash')))
    fig.update_yaxes(title='MW');theme(fig,410)
    return fig

def risk_figure(s,hours):
    s=s[s.h<=hours*2];fig=go.Figure()
    for t,color in [('export',CYAN),('import',ORANGE)]:
        fig.add_trace(go.Scatter(x=s.time,y=s[t+'_probability']*100,name=t.title(),line=dict(color=color,width=1.6)))
    fig.update_yaxes(range=[0,100],title='Probability %');return theme(fig,225)

def watchlist(origin,hours):
    rows=[]
    for k in IDS:
        s=snapshot(k,origin);s=s[s.h<=min(hours,24)*2]
        if s.empty:continue
        risk=max(s.export_probability.max(),s.import_probability.max())
        flagged=((s.export_probability>=s.export_cutoff)|(s.import_probability>=s.import_cutoff)).any()
        rows.append([IC[k]['name'],fmt(s.flow_p50.iloc[0]),fmt(risk*100,'%'),html.Span('FLAG' if flagged else 'CLEAR',className='pill warn' if flagged else 'pill')])
    return table(['Link','Next MW','Max risk','Signal'],rows)

def forecast_page(ic,origin,target,hours):
    s=snapshot(ic,origin);f=s[s.h<=hours*2]
    if f.empty:return notice('No future outcomes are available after this origin. Choose an earlier date.')
    first=f.iloc[0];risk=max(f.export_probability.max(),f.import_probability.max())
    daily=f.set_index('time').resample('D').agg({'flow_p50':'mean','export_p50':'mean','import_p50':'mean'})
    rows=[[str(day.strftime('%a %d %b')),fmt(row.flow_p50),fmt(row.export_p50),fmt(row.import_p50)] for day,row in daily.iterrows()]
    return html.Div([
      html.Div([stat('Dispatch flow',fmt(first.flow_p50,' MW'),IC[ic]['label'],'cyan'),
        stat('Export limit',fmt(first.export_p50,' MW'),'Next half-hour · directional','cyan'),
        stat('Import limit',fmt(first.import_p50,' MW'),'Next half-hour · reverse direction','orange'),
        stat('Maximum interval risk',fmt(risk*100,'%'),f'50% restriction · next {min(hours,len(f)/2):g}h','orange')],className='kpi-row'),
      html.Div([panel(LABELS[target],graph(forecast_figure(s,target,hours)),f'{IC[ic]["name"]} · half-hourly · fixed NEM time (UTC+10)'),
        html.Div([panel('NEM transfer monitor',watchlist(origin,hours),'Next half-hour flow · maximum interval risk over 24h'),
          panel('Daily outlook',table(['NEM day','Flow','Export','Import'],rows),'Mean of half-hour P50 forecasts · MW')])],className='two-column'),
      panel('Restriction probability',graph(risk_figure(s,hours)),'Probability of each half-hour average limit falling below 50% of its seasonal reference.'),
      notice('Conditional replay: future realised demand, renewables and weather are supplied. Shaded ranges are calibrated marginal P10–P90 intervals, not simultaneous seven-day bounds. Reported limits depend on dispatch and can be negative during forced-flow conditions.'),
      panel('Five-minute detail',graph(five_min_figure(ic,origin,target)),'First six hours after this origin · original observations; brief restrictions remain visible.')])

@functools.lru_cache(maxsize=1)
def five_min():return pd.read_parquet(PROCESSED/'ic_5min.parquet',columns=['time','INTERCONNECTORID','flow','export','import'])

def five_min_figure(ic,origin,target):
    t='export' if target.startswith('export') else 'import' if target.startswith('import') else 'flow'
    df=five_min();o=pd.Timestamp(origin);s=df[(df.INTERCONNECTORID==ic)&(df.time>o)&(df.time<=o+pd.Timedelta(hours=6))]
    fig=go.Figure(go.Scatter(x=s.time,y=s[t],name='5-minute actual',line=dict(color=PURPLE,width=1.7),mode='lines'))
    fig.update_yaxes(title='MW');return theme(fig,230)

def performance_page(ic,target,slice_name):
    scores=get_scores()
    if scores.empty:return notice('The exhaustive test is running. Scorecards will become available after all interconnectors and horizons finish.')
    s=scores[(scores.ic==ic)&(scores.target==target)&(scores['slice']==slice_name)]
    if s.empty:return notice(f'No {slice_name} observations in this test slice. The final test covers March–August 2026; choose All or a season represented in that period.')
    chosen_scores=s[s.model=='selected']
    fig=go.Figure()
    for m in ['persistence','seasonal','fundamentals','weather','availability','network','selected']:
        g=s[s.model==m].sort_values('band')
        fig.add_trace(go.Bar(x=[BANDS[int(b)] for b in g.band],y=g.mae,name=METHOD_LABELS[m]))
    fig.update_layout(barmode='group');fig.update_yaxes(title='MAE · MW');theme(fig,390)
    rows=[]
    for _,r in chosen_scores.sort_values('band').iterrows():
        rows.append([BANDS[int(r.band)],fmt(r.mae,'',1),fmt(r.rmse,'',1),fmt(r.coverage80*100,'%'),fmt(r.width80,'',1),fmt(r.recall*100,'%') if target!='flow' else '—',fmt(r.precision*100,'%') if target!='flow' else '—',f'{int(r.n):,}'])
    calibration=go.Figure(go.Bar(x=[BANDS[int(b)] for b in chosen_scores.band],y=chosen_scores.coverage80*100,marker_color=CYAN,name='Observed coverage'))
    calibration.add_hline(y=80,line_dash='dash',line_color=ORANGE);calibration.update_yaxes(range=[0,100],title='Coverage %');theme(calibration,290)
    skill=pd.read_csv(RESULTS/'skill_confidence.csv');g=skill[(skill.ic==ic)&(skill.target==target)&(skill.baseline=='persistence')]
    confidence=go.Figure(go.Scatter(x=[BANDS[int(b)] for b in g.band],y=g.improvement_mw,mode='markers',marker=dict(size=9,color=CYAN),error_y=dict(type='data',symmetric=False,array=g.ci_high-g.improvement_mw,arrayminus=g.improvement_mw-g.ci_low,color=CYAN)))
    confidence.add_hline(y=0,line_dash='dot',line_color=ORANGE);confidence.update_yaxes(title='MAE reduction · MW');theme(confidence,290)
    cfg=json.loads((MODELS/'selection.json').read_text())
    winners=[[BANDS[b],METHOD_LABELS[cfg[f'{ic}|{target}|{b}']['model']],f"{cfg[f'{ic}|{target}|{b}']['calibration_n']:,}"] for b in range(4)]
    components=[panel('Out-of-sample model comparison',graph(fig),'Lower is better · every available half-hour origin and all 336 lead times'),
      panel('Selected forecast scorecard',table(['Lead','MAE','RMSE','80% cover','Width MW','Recall','Precision','Pairs'],rows),'Selection and calibration frozen before March 2026.'),
      html.Div([panel('Percentile calibration',graph(calibration),'Dashed line: nominal 80% coverage.'),panel('Skill against persistence',graph(confidence),'95% seven-day block bootstrap interval · positive is better · full test slice.')],className='equal-columns'),
      panel('Models chosen on validation',table(['Lead','Selected method','Calibration pairs'],winners))]
    aemo=RESULTS/'aemo_scores.csv'
    if aemo.exists() and target in ['flow','export','import']:
        a=pd.read_csv(aemo);a=a[(a.ic==ic)&(a.target==target)]
        components.append(panel('Matched AEMO comparison',table(['Lead','AEMO MAE','Selected MAE','Pairs'],[[BANDS[int(r.band)],fmt(r.aemo_mae,'',1),fmt(r.selected_mae,'',1),f'{int(r.n):,}'] for _,r in a.iterrows()]),'Same origins and delivery intervals; original forecast issue timestamps. AEMO uses forecast inputs; our experiment uses realised inputs.'))
    else:components.append(notice('AEMO original-vintage comparison is being assembled; it is limited to AEMO’s published horizon and the three average targets.'))
    return html.Div(components)

def drivers_page(ic,origin,target,hours):
    d=design();s=snapshot(ic,origin);times=s.time[s.h<=hours*2];g=d.drivers.reindex(times)
    fig=go.Figure()
    for region in [IC[ic]['source'],IC[ic]['sink']]:fig.add_trace(go.Scatter(x=times,y=g[region+'__residual_demand'],name=region.replace('1','')+' residual demand',line=dict(width=1.7)))
    fig.update_yaxes(title='MW');theme(fig,320)
    imp=pd.read_csv(RESULTS/f'importance_{target}.csv').head(14).sort_values('gain')
    importance=go.Figure(go.Bar(x=imp.gain,y=imp.feature.str.replace('__',' · ').str.replace('_',' '),orientation='h',marker_color=CYAN))
    theme(importance,390).update_layout(margin=dict(l=220,r=20,t=20,b=35));importance.update_xaxes(title='Split gain · model-wide')
    v=pd.read_csv(RESULTS/'validation_leaderboard.csv');v=v[(v.ic==ic)&(v.target==target)]
    rows=[[BANDS[b]]+[fmt(v[(v.band==b)&(v.model==m)].mae.iloc[0],'',1) for m in ['fundamentals','weather','availability','network']] for b in range(4)]
    return html.Div([panel('Regional supply balance',graph(fig),'Residual demand = TOTALDEMAND − semi-scheduled wind − solar. Rooftop is already embedded in demand.'),
      panel('What added information helps?',table(['Lead','Demand + RE','+ Weather','Availability','Network history'],rows),'Validation MAE in MW. Availability substitutes UIGF for cleared wind/solar; network adds only delayed origin information.'),
      panel('Network model drivers',graph(importance),'Training split gain across all connectors. These are predictive associations, not causal effects.'),
      notice('Realised renewable dispatch may already reflect congestion. The availability experiment tests sensitivity to this dependence. Temperature, wind, radiation, cloud and humidity come from 15 representative locations, not a full line-rating or wind-farm model.')])

def pricing_page(ic,origin):
    prices=pd.read_parquet(PROCESSED/'prices.parquet');t=design().targets[ic]
    p=prices.join(t[['export','import','export_threshold','import_threshold']])
    p['spread']=p[IC[ic]['sink']]-p[IC[ic]['source']]
    p=p[(p.index>='2026-03-01')&(p.index<='2026-09-01')]
    p['state']=np.select([(p.export<p.export_threshold)&(p['import']<p.import_threshold),p.export<p.export_threshold,p['import']<p.import_threshold],['Both flagged','Export flagged','Import flagged'],default='Neither flagged')
    fig=go.Figure()
    for name in ['Neither flagged','Export flagged','Import flagged','Both flagged']:
        g=p[p.state==name]
        fig.add_trace(go.Box(y=g.spread,name=name,boxpoints=False))
    theme(fig,370);fig.update_yaxes(title='Receiving − sending price · $/MWh')
    o=pd.Timestamp(origin);g=p[(p.index>=o)&(p.index<=o+pd.Timedelta(days=7))]
    line=go.Figure(go.Scatter(x=g.index,y=g.spread,name='Regional spread',line=dict(color=ORANGE,width=1.5)));theme(line,300);line.update_yaxes(title='$/MWh')
    rows=[]
    for name,g in p.groupby('state'):
        rows.append([name,f'{len(g):,}',fmt(g.spread.median(),' $',1),fmt(g.spread.quantile(.1),'',1),fmt(g.spread.quantile(.9),'',1)])
    return html.Div([panel('Regional price separation',graph(line),IC[ic]['label']+' · receiving-region RRP minus sending-region RRP'),panel('Price spreads during restrictions',graph(fig),'Untouched test period · all prices retained; boxes show distribution, not an estimated causal effect.'),panel('Historical context',table(['Limit state','Half-hours','Median','P10','P90'],rows)),notice('Prices are excluded from every predictive feature. A restriction and a price spread can share causes, including supply shortages, outages and bids. This view does not estimate how much changing a limit would change price.')])

def scenario_page():
    return html.Div([panel('Seven-day conditional scenario',html.Div([
      html.Div([html.Label([html.Span('Apply changes to',className='field-label'),dcc.Dropdown(id='scenario-region',options=[{'label':'All regions','value':'ALL'}]+[{'label':r,'value':r} for r in REGIONS],value='ALL',clearable=False)],className='field'),
      html.Label([html.Span('Demand change %',className='field-label'),dcc.Input(id='scenario-demand',type='number',value=0,min=-50,max=50,className='scenario-input')],className='field'),
      html.Label([html.Span('Wind / solar change %',className='field-label'),dcc.Input(id='scenario-renewables',type='number',value=0,min=-100,max=100,className='scenario-input')],className='field'),
      html.Label([html.Span('Temperature change °C',className='field-label'),dcc.Input(id='scenario-temp',type='number',value=0,min=-15,max=15,className='scenario-input')],className='field'),html.Button('Run scenario',id='scenario-run',className='button primary')],className='scenario-controls'),
      html.Div([html.Button('Download input template',id='template-download',className='button'),dcc.Upload(id='scenario-upload',children=html.Div('Or upload a 336-row scenario CSV'),className='upload',multiple=False)],className='scenario-controls'),
      html.Div(id='scenario-result',className='body-copy',children='Start from the selected historical origin. Edit its realised input paths, or upload your own. The model keeps only information available at that origin for network history.')]),'P10 / P50 / P90, with restriction probabilities. No automatic live-input forecasting.'),dcc.Store(id='scenario-store'),dcc.Download(id='scenario-file'),dcc.Download(id='template-file')])

def methods_page():
    a=json.loads((RESULTS/'data_audit.json').read_text());split=json.loads((RESULTS/'split.json').read_text())
    references=pd.read_csv(RESULTS/'seasonal_references.csv');rows=[]
    for _,r in references.iterrows():rows.append([IC[r.ic]['name'],['Summer','Autumn','Winter','Spring'][int(r.season)],fmt(r['export']),fmt(r['import']),fmt(r['export']/2),fmt(r['import']/2)])
    text=dcc.Markdown('''**Experiment.** Three years: September 2023–August 2026. Every half-hour origin, with leads from 30 minutes to seven days. All six historically represented interconnectors; five targets per connector.

**Splits.** September 2023–August 2025: fit models and seasonal references. September–November 2025: select a method per connector, target and lead band. December 2025–January 2026: calibrate residual percentiles. February 2026: tune alert cutoffs using F2 (recall weighted more than precision). March–August 2026: untouched test. Origin/target pairs cannot cross their partition boundaries.

**Inputs.** Future realised demand, semi-scheduled wind/solar, rooftop PV and ERA5 weather are allowed. Network features use observations delayed 30 minutes: limits, flows, limit setters, outage flags, generation availability and other interconnector flows. Future realised prices, constraint setters and flows are forbidden. Renewable availability is a separate sensitivity experiment.

**Models.** Persistence, same-week-slot persistence, boosted demand/renewable models, weather and availability variants, and direct multi-horizon network-history boosting. Training uses a reproducible random lead in each of four bands at each eligible half-hour origin. Testing evaluates all 336 leads. Selection is by validation MAE; methods are allowed to lose to persistence.

**Percentiles and probabilities.** P10/P50/P90 come from the selected forecast plus the empirical validation residual distribution for that connector, target and lead band. Restriction probability is the residual CDF at the seasonal 50% threshold. These are marginal, band-calibrated distributions—not joint seven-day bounds or a physics simulation. Calibration quality and Brier scores are tested, not assumed.

**Restriction definition.** Half the seasonal median of positive reported directional limits, estimated from training only. Zero and negative target limits remain in the data and can trigger flags. Import is minus the raw signed IMPORTLIMIT. Mean and tightest limits are separate forecasts; they are not a simultaneously feasible operating envelope.

**Coverage and limitations.** AEMO regional renewable fields cover semi-scheduled generation; they are not all renewable output. Rooftop remains separate and is not subtracted from demand twice. Weather uses 15 representative sites and interpolated hourly reanalysis. Rare missing rooftop values remain missing, handled by the trees. Revised archive data and realised renewable endogeneity limit operational interpretation. Future outage schedules are not reconstructed; delayed observed outage/limit-setting regimes are used instead. New EnergyConnect representation has no three-year standalone sample; existing-link regime changes remain in the test.

**Pricing.** Historical regional spreads are descriptive. They are not model inputs or causal price-impact estimates.

**Reproducibility.** Raw source ZIPs, original forecast issue timestamps, checksum manifests, processed five-minute data, model files, frozen selections and per-origin predictions are retained locally. The seven-day scenario runner accepts explicit input paths; it does not pretend to know next week's realised inputs.
''',link_target='_blank')
    return html.Div([html.Div([stat('Historical window','36 months','Sep 2023 — Aug 2026'),stat('Half-hour targets',f"{a['half_hour_count']:,}",'Six links · five targets'),stat('Target completeness','100%','All expected five-minute intervals'),stat('Forecast resolution','30 min','336 leads · seven days')],className='kpi-row'),panel('Research design',html.Div(text,className='body-copy')),panel('Seasonal reference and flag levels',table(['Link','Season','Export ref','Import ref','Export flag','Import flag'],rows),'MW · positive directional limits in training only'),panel('Sources and research',html.Div(dcc.Markdown('''- [AEMO: interpretation of interconnector limits, Appendix A](https://aemo.com.au/-/media/files/electricity/nem/market_notices_and_events/power_system_incident_reports/2024/final-report---loss-of-moorabool---sydenham-500-kv-lines-on-13-feb-2024.pdf)
- [AEMO constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq)
- [Transmission capacity forecasting research](https://d-nb.info/1204086990/34)
- [Boosted congestion probability research](https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2024.1351306/full)
- [Rolling-origin evaluation](https://otexts.com/fpp3/tscv.html)
- [NEMWEB](https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/) · [Open-Meteo ERA5](https://open-meteo.com/en/docs/historical-weather-api)
''',link_target='_blank'),className='body-copy'))])

def layout():
    return html.Div([dcc.Store(id='selected-ic',data='NSW1-QLD1'),dcc.Download(id='download'),
      html.Aside([html.Div([html.Span('⇄',className='brand-mark'),html.Div([html.Strong('INTERFLOW'),html.Small('NEM RESEARCH DESK')])],className='brand'),html.Div('INTERCONNECTORS',className='rail-label'),html.Div([html.Button([html.Div([html.Strong(IC[k]['name']),html.Small(IC[k]['label'])]),html.Span('↗',className='arrow')],id={'type':'connector','key':k},className='connector-button'+(' active' if k=='NSW1-QLD1' else ''),n_clicks=0) for k in IDS],className='connector-list'),html.Div([html.Strong('36 months of history'),html.Br(),'Sep 2023 — Aug 2026',html.Br(),html.Br(),'NEMWEB × Open-Meteo',html.Br(),'Fixed NEM time · UTC+10'],className='rail-bottom')],className='sidebar'),
      html.Main([html.Header([html.Div([html.Span('RESEARCH'),html.Span('/'),html.Strong('Interconnector intelligence')],className='breadcrumb'),html.Div([html.Span('HISTORICAL REPLAY',className='badge'),html.Span('REALISED INPUTS',className='badge secondary')],className='badges')],className='topbar'),
      html.Div([html.Div([html.Div([html.H1('Transfer outlook'),html.Div('Directional limits, dispatch flows and restriction risk across the NEM.',className='subtitle')]),html.Button('Export data ↓',id='export-view',className='button',n_clicks=0)],className='title-row'),
      dcc.Tabs(id='page',value='forecast',className='tabs',mobile_breakpoint=0,children=[dcc.Tab(label=label,value=value) for value,label in [('forecast','Forecast'),('performance','Backtest'),('drivers','Drivers'),('pricing','Price context'),('scenario','Scenarios'),('methods','Data & methods')]]),
      html.Div([html.Label([html.Span('Forecast origin · NEM time',className='field-label'),dcc.DatePickerSingle(id='origin-date',date='2026-08-24',min_date_allowed='2026-03-01',max_date_allowed='2026-09-01',display_format='DD MMM YYYY',clearable=False)],className='field'),
        html.Label([html.Span('Issue time',className='field-label'),dcc.Dropdown(id='origin-clock',options=[f'{h:02d}:{m:02d}' for h in range(24) for m in [0,30]],value='00:00',clearable=False)],className='field'),
        html.Label([html.Span('Target',className='field-label'),dcc.Dropdown(id='target',options=[{'label':v,'value':k} for k,v in LABELS.items()],value='flow',clearable=False)],className='field wide'),
        html.Label([html.Span('Horizon',className='field-label'),dcc.Dropdown(id='horizon',options=[{'label':'24 hours','value':24},{'label':'3 days','value':72},{'label':'7 days','value':168}],value=168,clearable=False)],className='field'),
        html.Label([html.Span('Scorecard slice',className='field-label'),dcc.Dropdown(id='score-slice',options=[{'label':v.title(),'value':v} for v in ['all','restricted','summer','autumn','winter','spring','intervention']],value='all',clearable=False)],className='field')],className='controls'),
      dcc.Loading(html.Div(id='page-body'),type='dot',color=CYAN,delay_show=500),html.Footer([html.Span('CONDITIONAL RESEARCH · NOT A LIVE DISPATCH FORECAST'),html.Span('AEMO / Open-Meteo · Percentiles calibrated on validation')],className='footer')],className='content')])],className='app-shell')
app.layout=layout

@app.callback(Output('selected-ic','data'),Input({'type':'connector','key':ALL},'n_clicks'),prevent_initial_call=True)
def select_ic(clicks):return ctx.triggered_id['key'] if ctx.triggered_id else no_update

@app.callback(Output({'type':'connector','key':ALL},'className'),Input('selected-ic','data'))
def active_ic(ic):return ['connector-button'+(' active' if k==ic else '') for k in IDS]

@app.callback(Output('page-body','children'),Input('page','value'),Input('selected-ic','data'),Input('origin-date','date'),Input('origin-clock','value'),Input('target','value'),Input('horizon','value'),Input('score-slice','value'))
def render(page,ic,date,clock,target,hours,slice_name):
    origin=origin_value(date,clock)
    if page=='forecast':return forecast_page(ic,origin,target,hours)
    if page=='performance':return performance_page(ic,target,slice_name)
    if page=='drivers':return drivers_page(ic,origin,target,hours)
    if page=='pricing':return pricing_page(ic,origin)
    if page=='scenario':return scenario_page()
    return methods_page()

@app.callback(Output('download','data'),Input('export-view','n_clicks'),State('page','value'),State('selected-ic','data'),State('origin-date','date'),State('origin-clock','value'),prevent_initial_call=True)
def export_view(n,page,ic,date,clock):
    df=get_scores() if page=='performance' else snapshot(ic,origin_value(date,clock))
    return dcc.send_data_frame(df.to_csv,f'interflow_{ic}_{page}.csv',index=False)

@app.callback(Output('template-file','data'),Input('template-download','n_clicks'),State('origin-date','date'),State('origin-clock','value'),prevent_initial_call=True)
def export_template(n,date,clock):return dcc.send_data_frame(template(origin_value(date,clock)).to_csv,'scenario_inputs.csv')

@app.callback(Output('scenario-result','children'),Output('scenario-store','data'),Input('scenario-run','n_clicks'),State('scenario-region','value'),State('scenario-demand','value'),State('scenario-renewables','value'),State('scenario-temp','value'),State('scenario-upload','contents'),State('origin-date','date'),State('origin-clock','value'),State('selected-ic','data'),State('target','value'),prevent_initial_call=True)
def scenario_callback(n,region,demand,renewables,temp,upload,date,clock,ic,target):
    try:
        origin=origin_value(date,clock)
        inputs=pd.read_csv(io.BytesIO(base64.b64decode(upload.split(',',1)[1])),index_col='time',parse_dates=['time']) if upload else template(origin)
        regions=REGIONS if region=='ALL' else [region]
        for r in regions:
            inputs[r+'__demand']*=1+float(demand or 0)/100
            for f in ['wind','solar','wind_available','solar_available']:inputs[r+'__'+f]*=1+float(renewables or 0)/100
            for c in inputs:
                if c.startswith(r.replace('1','')+'_') and c.endswith('temperature_2m'):inputs[c]+=float(temp or 0)
        out=run_scenario(origin,inputs);s=out[out.ic==ic];base=snapshot(ic,origin)
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=s.time,y=s[target+'_p90'],line=dict(width=0),showlegend=False,hoverinfo='skip'))
        fig.add_trace(go.Scatter(x=s.time,y=s[target+'_p10'],line=dict(width=0),fill='tonexty',fillcolor='rgba(178,156,255,.13)',name='Scenario P10–P90'))
        fig.add_trace(go.Scatter(x=base.time,y=base[target+'_p50'],name='Original P50',line=dict(color='#8b9fb5',width=1.5,dash='dot')))
        fig.add_trace(go.Scatter(x=s.time,y=s[target+'_p50'],name='Scenario P50',line=dict(color=PURPLE,width=2)))
        theme(fig,380);fig.update_yaxes(title='MW')
        return html.Div([graph(fig),html.Button('Download scenario results',id='scenario-export',className='button'),html.P('Input paths are assumptions, not an automatic weather-to-demand response. Network history is held at the selected origin.')]),out.to_json(orient='split',date_format='iso')
    except (ValueError,KeyError,TypeError) as e:return notice(str(e)),None

@app.callback(Output('scenario-file','data'),Input('scenario-export','n_clicks'),State('scenario-store','data'),prevent_initial_call=True)
def export_scenario(n,data):return dcc.send_data_frame(pd.read_json(io.StringIO(data),orient='split').to_csv,'scenario_results.csv',index=False)

if __name__=='__main__':app.run(host='127.0.0.1',port=8050,debug=False)
