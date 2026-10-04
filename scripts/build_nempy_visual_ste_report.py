"""Build an offline visual report from saved evidence; no data acquisition or fitting."""
from __future__ import annotations

import base64
import csv
import hashlib
import importlib.metadata
import io
import json
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import markdown
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'reports/nempy_forward_forecast_visual_ste_20261004'
OLD = ROOT/'reports/nempy_forward_forecast_design_20261004'
SOURCE = OUT/'NEMPy_Visual_Report_STE.md'
sys.path.insert(0,str(ROOT/'scripts/report_theme'))
from report_theme import hero, metric, finding, figure_html, matplotlib_style, render_page

BANDS = ['0.5–6 h','6.5–24 h','24.5–72 h','72.5–168 h']
COLORS = {'VNI export_tight':'#397fab','VNI import_tight':'#268a87',
          'QNI export_tight':'#7658b5','QNI import_tight':'#bf8528'}
CHARTS = {}
DATASETS = {}
DIAGRAMS = {}
SOURCE_HASHES = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_text(rel):
    p = ROOT/rel
    SOURCE_HASHES[rel] = sha(p)
    return p.read_text(encoding='utf-8')


def write_json(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')


def number(s):
    return float(s.strip().replace(',','').replace('%','').replace('−','-').replace(' pp','').replace(' MW',''))


def table(rows):
    if not rows:
        return ''
    def val(v):
        if isinstance(v,float): return f'{v:,.2f}'.rstrip('0').rstrip('.')
        return str(v)
    columns=list(rows[0])
    return '<div class="table-wrap" tabindex="0"><table><thead><tr>'+''.join(
        '<th>'+escape(c.replace('_',' '))+'</th>' for c in columns)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join('<td>'+escape(val(r[c]))+'</td>' for c in columns)+'</tr>' for r in rows)+'</tbody></table></div>'


def csv_data(name, rows):
    buffer=io.StringIO(newline='')
    w=csv.DictWriter(buffer,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    content=buffer.getvalue()
    (OUT/'data'/f'{name}.csv').write_text(content,encoding='utf-8',newline='')
    DATASETS[name]=rows
    return 'data:text/csv;charset=utf-8;base64,'+base64.b64encode(content.encode()).decode()


def chart(name, fig, title, note, rows, source, kind='Historical evidence'):
    fig.tight_layout()
    path=OUT/'figures'/f'{name}.svg'
    fig.savefig(path,format='svg',metadata={'Date':None})
    plt.close(fig)
    data_href=csv_data(name,rows)
    encoded=base64.b64encode(path.read_bytes()).decode()
    img=f'<img src="data:image/svg+xml;base64,{encoded}" alt="{escape(title)}" loading="lazy">'
    frame=figure_html(img,title,note)
    frame=frame.replace('<figure>',f'<figure id="fig-{name}" data-kind="{escape(kind)}">',1)
    frame=frame.replace('<div class="chart-scroll">','<div class="chart-scroll" tabindex="0" aria-label="Chart. Scroll sideways to view all data.">')
    source_html='<p class="chart-source"><span class="type-badge">'+escape(kind)+'</span> '+source+'</p>'
    detail='<details class="chart-data"><summary>View chart data</summary>'+table(rows)+f'<a class="download" href="{data_href}" download="{name}.csv">Download CSV</a></details>'
    CHARTS[name]=frame+source_html+detail


def load_evidence():
    performance=[];coverage=[]
    for ic in ['VNI','QNI']:
        rel=f'docs/{ic}_DIURNAL_NOS_RESULTS.md'
        count={'export_tight':0,'import_tight':0}
        for line in source_text(rel).splitlines():
            c=[v.strip() for v in line.strip().strip('|').split('|')]
            if line.startswith('|') and len(c)==8 and c[0].lower() in ['export tight','import tight','export minimum','import minimum']:
                target=c[0].split()[0].lower()+'_tight';band=count[target];count[target]+=1
                performance.append(dict(connector=ic,target=target,lead_band=BANDS[band],
                    selected_mae_mw=number(c[2]),persistence_mae_mw=number(c[4]),
                    ridge_mae_mw=number(c[5]),skill_pct=number(c[6]),source=rel))
            if line.startswith('|') and len(c)==6 and c[0]=='Delivery period':
                coverage.append(dict(connector=ic,nominal_pct=number(c[1]),observed_pct=number(c[2]),
                    gap_pp=number(c[3]),mean_width_mw=number(c[4]),forecast_rows=int(number(c[5])),source=rel))
    assert len(performance)==16 and len(coverage)==4
    # The source table rounds skill and MAE separately. Keep the reported values.
    for r in performance:
        derived=100*(1-r['selected_mae_mw']/r['persistence_mae_mw'])
        assert abs(derived-r['skill_pct']) < .12
    nos_rel='execution/nos_constraint_binding_v1/RESULTS_SUMMARY.md'
    nos=source_text(nos_rel)
    medians=[]
    for line in nos.splitlines():
        c=[v.strip() for v in line.strip().strip('|').split('|')]
        if line.startswith('|') and len(c)==7 and c[0] in ['QNI','Directlink','VNI','Heywood','Murraylink','Basslink']:
            medians.append(dict(link=c[0],supported_family_directions=int(c[1]),
                median_limit_setting_pct=number(c[2]),median_binding_pct=number(c[4]),source=nos_rel))
    assert len(medians)==6
    shares=re.search(r'both binds and sets the limit (\d+)% of the time, sets the limit without binding (\d+)%, binds without setting it (\d+)%, and does neither (\d+)%',nos)
    assert shares
    agreement=[dict(state=label,share_pct=float(v),source=nos_rel) for label,v in zip(
        ['Binding and limit-setting','Limit-setting only','Binding only','Neither'],shares.groups())]
    assert sum(r['share_pct'] for r in agreement)==100
    win=re.search(r'Brier score in (\d+) of (\d+)',nos)
    calibration=re.search(r'averaging (\d+)% were followed by (\d+)% realised',nos)
    mapping=re.search(r'Among the ([\d,]+) bookings that did, it was right (\d+)% of the time \(top three (\d+)%\)',nos)
    assert win and calibration and mapping
    nos_quality=[dict(measure='Cells with better Brier score',value_pct=100*int(win[1])/int(win[2]),
                      numerator=int(win[1]),denominator=int(win[2]),source=nos_rel),
                 dict(measure='Predicted binding in one bin',value_pct=float(calibration[1]),numerator='',denominator='One well-populated bin',source=nos_rel),
                 dict(measure='Actual binding in that bin',value_pct=float(calibration[2]),numerator='',denominator='Same bin',source=nos_rel),
                 dict(measure='First inferred family correct',value_pct=float(mapping[2]),numerator='',denominator=int(mapping[1].replace(',','')),source=nos_rel),
                 dict(measure='First three include correct family',value_pct=float(mapping[3]),numerator='',denominator=int(mapping[1].replace(',','')),source=nos_rel)]
    toy_rel='reports/nempy_forward_forecast_design_20261004/toy_results.csv'
    toy=list(csv.DictReader(io.StringIO(source_text(toy_rel))))
    for r in toy:
        for key in ['flow_mw','southern_generation_mw','northern_generation_mw','offer_cost_per_hour']:
            r[key]=float(r[key])
    assert abs(toy[1]['flow_mw']-700/1.5)<1e-8
    source_text('reports/nempy_forward_forecast_design_20261004/Forward_Forecast_with_NEMPy.md')
    source_text('reports/nempy_forward_forecast_design_20261004/manifest.json')
    return performance,coverage,medians,agreement,nos_quality,toy


def make_charts(performance,coverage,medians,agreement,quality,toy):
    plt.rcParams.update(matplotlib_style())
    plt.rcParams.update({'font.size':11,'svg.fonttype':'path'})
    refs='<a href="../../docs/VNI_DIURNAL_NOS_RESULTS.md">VNI results</a> · <a href="../../docs/QNI_DIURNAL_NOS_RESULTS.md">QNI results</a>'
    nosref='<a href="../../execution/nos_constraint_binding_v1/RESULTS_SUMMARY.md">NOS mechanics and outlook</a>'
    fig,axes=plt.subplots(1,2,figsize=(11,4.7),sharey=True)
    for ax,ic in zip(axes,['VNI','QNI']):
        for target,marker in [('export_tight','o'),('import_tight','s')]:
            rs=[r for r in performance if r['connector']==ic and r['target']==target]
            ax.plot(range(4),[r['skill_pct'] for r in rs],marker=marker,label=target.split('_')[0].title(),color=COLORS[ic+' '+target],lw=2.3)
            other=[r for r in performance if r['connector']==ic and r['target']!=target]
            for x,r in enumerate(rs):
                offset=10 if r['skill_pct']>=other[x]['skill_pct'] else -18
                ax.annotate(f"{r['skill_pct']:g}",(x,r['skill_pct']),xytext=(0,offset),
                            textcoords='offset points',ha='center',fontsize=9)
        ax.axhline(0,color='#66717e',lw=1);ax.set_title(ic,pad=15)
        ax.set_xticks(range(4),['0.5–6','6.5–24','24.5–72','72.5–168'])
        ax.set_xlabel('Lead (hours)');ax.set_ylim(-16,50);ax.legend(loc='upper right',frameon=False)
    axes[0].set_ylabel('Tight-limit MAE skill (%)')
    chart('skill',fig,'01 · VNI has stronger tight-limit skill',
          'Positive values mean lower MAE than persistence. Each point is a reported target and lead cell.',performance,refs)

    fig,ax=plt.subplots(figsize=(8.5,5.4))
    ax.plot([100,510],[100,510],color='#66717e',ls='--',label='Equal error')
    for ic in ['VNI','QNI']:
        for target,marker in [('export_tight','o'),('import_tight','s')]:
            rs=[r for r in performance if r['connector']==ic and r['target']==target]
            ax.scatter([r['persistence_mae_mw'] for r in rs],[r['selected_mae_mw'] for r in rs],s=75,
                       color=COLORS[ic+' '+target],marker=marker,label=ic+' '+target.split('_')[0])
    ax.set(xlim=(100,510),ylim=(100,510),xlabel='Persistence MAE (MW)',ylabel='Selected-model MAE (MW)')
    ax.text(305,140,'Below the line:\nlower model error',color='#268a87')
    ax.legend(ncol=2,fontsize=9,loc='upper left')
    chart('mae',fig,'02 · Compare the error in MW',
          'The chart contains 16 tight-limit cells. Lower error is better. The data table identifies each lead band.',performance,refs)

    fig,ax=plt.subplots(figsize=(9.5,4.6))
    ordered=sorted(coverage,key=lambda r:(r['nominal_pct'],r['connector']))
    for y,r in enumerate(ordered):
        col='#7658b5' if r['connector']=='QNI' else '#397fab'
        ax.plot([r['observed_pct'],r['nominal_pct']],[y,y],color=col,lw=5,alpha=.4)
        ax.scatter(r['observed_pct'],y,s=95,color=col,zorder=3)
        ax.scatter(r['nominal_pct'],y,s=110,facecolors='white',edgecolors='#282b30',zorder=3)
        ax.text(r['observed_pct']-.5,y-.17,f"{r['observed_pct']:.2f}%",ha='right',fontsize=10)
        ax.text(r['nominal_pct']+.65,y+.08,f"Target {r['nominal_pct']:g}%",fontsize=10)
    ax.set_yticks(range(4),[r['connector']+' · '+str(int(r['nominal_pct']))+'% interval' for r in ordered])
    ax.invert_yaxis();ax.set_xlim(65,103);ax.set_xlabel('Outcomes inside the interval (%)')
    chart('coverage',fig,'03 · The saved intervals are too narrow',
          'Filled circles show observed coverage. Open circles show nominal coverage. Each source pools four targets and four lead bands.',coverage,refs)

    fig,ax=plt.subplots(figsize=(10,4.8))
    y=np.arange(len(medians));h=.33
    a=ax.barh(y-h/2,[r['median_limit_setting_pct'] for r in medians],height=h,color='#397fab',label='Own set sets the limit')
    b=ax.barh(y+h/2,[r['median_binding_pct'] for r in medians],height=h,color='#7658b5',label='Own set is binding')
    ax.bar_label(a,labels=[f"{r['median_limit_setting_pct']:g}%" for r in medians],padding=4,fontsize=9)
    ax.bar_label(b,labels=[f"{r['median_binding_pct']:g}%" for r in medians],padding=4,fontsize=9)
    ax.set_yticks(y,[r['link']+f"  (n={r['supported_family_directions']})" for r in medians]);ax.invert_yaxis()
    ax.set_xlim(0,25);ax.set_xlabel('Median share of invoked intervals (%)')
    ax.legend(loc='lower right',fontsize=9)
    chart('nos_medians',fig,'04 · Most outage sets do not control most intervals',
          'n counts supported family-directions. Shares are conditional on actual invocation. These are descriptive results.',medians,nosref)

    fig,ax=plt.subplots(figsize=(10,2.9))
    left=0;colors=['#268a87','#397fab','#bf8528','#b6bdc9']
    for r,col in zip(agreement,colors):
        ax.barh([0],[r['share_pct']],left=[left],height=.42,color=col,label=r['state']+f" · {r['share_pct']:g}%")
        if r['share_pct']>=5:
            ax.text(left+r['share_pct']/2,0,f"{r['share_pct']:g}%",ha='center',va='center',color='white' if r['share_pct']<50 else '#282b30',fontsize=12,fontweight='bold')
        left+=r['share_pct']
    ax.set_xlim(0,100);ax.set_yticks([]);ax.set_xlabel('Average share across supported families (%)')
    ax.legend(ncol=2,loc='upper center',bbox_to_anchor=(.5,1.5),fontsize=9)
    ax.set_ylim(-.6,.6)
    chart('layer_agreement',fig,'05 · Binding and limit-setting are different outcomes',
          'The source reports rounded mean shares during invocation. The 1% binding-only segment is shown in gold.',agreement,nosref)

    fig,axes=plt.subplots(1,3,figsize=(11,4.2))
    axes[0].bar(['Better score','Other cells'],[quality[0]['numerator'],quality[0]['denominator']-quality[0]['numerator']],color=['#268a87','#b6bdc9'])
    axes[0].set_ylim(0,96);axes[0].set_ylabel('Comparison cells');axes[0].set_title('Outlook selection',pad=14)
    for x,val in enumerate([quality[0]['numerator'],quality[0]['denominator']-quality[0]['numerator']]):
        axes[0].text(x,val+3,str(val),ha='center')
    axes[1].bar(['Forecast','Actual'],[quality[1]['value_pct'],quality[2]['value_pct']],color=['#7658b5','#397fab'])
    axes[1].set_ylim(0,50);axes[1].set_ylabel('Binding share (%)');axes[1].set_title('One probability bin',pad=14)
    axes[2].bar(['First family','First three'],[quality[3]['value_pct'],quality[4]['value_pct']],color=['#397fab','#268a87'])
    axes[2].set_ylim(0,50);axes[2].set_ylabel('Correct family (%)');axes[2].set_title('1,175 later invocations',pad=14)
    for ax,rs in [(axes[1],quality[1:3]),(axes[2],quality[3:5])]:
        for x,r in enumerate(rs): ax.text(x,r['value_pct']+1.5,f"{r['value_pct']:g}%",ha='center')
    chart('nos_limits',fig,'06 · NOS needs selection and probability checks',
          'The panels use different populations. Compare values only within each panel. The outlook result uses 23 of 96 cells.',quality,nosref)

    fig,ax=plt.subplots(figsize=(9.5,4.2))
    labels=['Fixed reference bound','Complete equation','Equation plus fixed bound']
    bars=ax.barh(labels,[r['flow_mw'] for r in toy],color=['#7658b5','#268a87','#bf8528'],height=.5)
    ax.invert_yaxis();ax.set_xlim(0,560);ax.set_xlabel('Northbound flow (MW)')
    ax.bar_label(bars,labels=[f"{r['flow_mw']:.2f} MW" for r in toy],padding=6)
    chart('toy',fig,'07 · Redispatch changes the conditional bound',
          'Synthetic NEMPy 3.0.3 results. Northern demand is 1,000 MW. The example has no losses or southern demand.',toy,
          '<a href="../nempy_forward_forecast_design_20261004/toy_results.csv">Saved synthetic results</a>',kind='Synthetic example')

    fig,ax=plt.subplots(figsize=(9,5.4))
    x=np.linspace(0,700,101);edge=1400-2*x
    ax.fill_between(x,0,edge,color='#268a87',alpha=.12,label='Area within the network bound')
    ax.plot(x,edge,color='#268a87',lw=2.2,label='F + 0.5P = 700')
    ax.plot(x,x,color='#397fab',lw=2,label='Future balance: P = F')
    ax.axvline(400,color='#7658b5',ls='--',label='Fixed reference bound: F = 400')
    ax.scatter([400,700/1.5],[600,700/1.5],color=['#7658b5','#268a87'],s=85,zorder=4)
    ax.annotate('Reference state\nF = 400, P = 600',(400,600),xytext=(80,1000),arrowprops={'arrowstyle':'->','color':'#66717e'},fontsize=10)
    ax.annotate('Future maximum\nF = P = 466.67',(700/1.5,700/1.5),xytext=(500,850),arrowprops={'arrowstyle':'->','color':'#66717e'},fontsize=10)
    ax.set(xlim=(0,750),ylim=(0,1500),xlabel='Northbound flow F (MW)',ylabel='Southern generation P (MW)')
    ax.legend(loc='upper right',fontsize=8.5)
    grid=[dict(flow_mw=float(f),network_max_generation_mw=float(p),future_balance_generation_mw=float(f),
               future_balance_meets_network=bool(1.5*f<=700+1e-9),kind='synthetic') for f,p in zip(x,edge)]
    chart('geometry',fig,'08 · The equation permits a different operating point',
          'The shaded area represents this one synthetic inequality. Other real network restrictions are absent.',grid,
          'Derived from the synthetic equation in Section 9.',kind='Synthetic example')


def card(title,body,tag=''):
    return '<div class="diagram-card">'+(f'<span class="step-tag">{escape(tag)}</span>' if tag else '')+f'<h3>{escape(title)}</h3><p>{escape(body)}</p></div>'


def diagram(name,title,body,note='Design proposal. The diagram does not show measured accuracy.'):
    DIAGRAMS[name]=f'<div class="design-figure" id="diagram-{name}" role="group" aria-label="{escape(title)}"><div class="diagram-heading"><span class="type-badge">Design</span><h3>{escape(title)}</h3></div>{body}<p class="diagram-note">{escape(note)}</p></div>'


def make_diagrams():
    diagram('routes','Three model paths', '<div class="diagram-grid cols3">'+
        card('Forecast bounds','Research model → signed bounds → NEMPy results','E')+
        card('Complete equations','Outage scenarios → equations and RHS → NEMPy results','C')+
        card('Combined results','Checked selection rule → model result or forecast combination','H')+
        '</div><div class="diagram-result">Compare every path on the same permitted inputs and delivery intervals.</div>')
    steps=[('Booking','Planned equipment event'),('Actual event','Occurrence and timing'),('Active equations','Applicable set and version'),
           ('Dispatch','Generation and flow'),('Binding result','Slack and economic effect')]
    diagram('outage_chain','From outage booking to binding result','<ol class="flow-steps">'+''.join(
        '<li><strong>'+escape(t)+'</strong><span>'+escape(b)+'</span></li>' for t,b in steps)+'</ol>',
        'Each arrow needs data or a stated assumption. A booking does not prove the final result.')
    diagram('horizons','One calendar, three forecast bases','<div class="horizon-grid">'+
        card('Days 1–7','Supported short-range models. Joint demand, generation, and outage scenarios.','7 DAYS')+
        card('Days 8–14','Verified extended forecasts or coherent historical analogs. Separate evaluation.','7 DAYS')+
        card('Days 15–30','Seasonal paths, outage timing, and energy budgets. Weekly and monthly exposure.','16 DAYS')+
        '</div><div class="diagram-result">A new forecast basis needs its own input contract and validation.</div>')
    diagram('signed_bounds','Convert directional targets into signed bounds','<div class="formula-grid">'+
        '<div><span>Export target</span><strong>U = E</strong><p>Upper signed bound</p></div>'+
        '<div><span>Import target</span><strong>L = −I</strong><p>Lower signed bound</p></div>'+
        '<div><span>Dispatch condition</span><strong>L ≤ F ≤ U</strong><p>Keep negative target values.</p></div></div>',
        'QNI and VNI use positive flow for the northbound direction under the repository contract.')
    diagram('provenance','Check availability at the forecast origin','<ol class="flow-steps four">'+
        ''.join('<li><strong>'+a+'</strong><span>'+b+'</span></li>' for a,b in [
            ('Issue','Provider creates the forecast'),('Publication','Provider releases the data'),
            ('Receipt','This system receives the data'),('Origin','The forecast uses eligible inputs')])+
        '</ol><div class="formula-strip">Required: publication time ≤ origin · receipt time ≤ origin</div>',
        'Keep the delivery interval separately. It identifies when the forecast value applies.')
    diagram('run_flow','The forecast process','<div class="run-grid">'+
        card('1 · Save inputs','Origin, versions, hashes, and source coverage.')+
        card('2 · Create scenarios','Joint fundamentals, outages, offers, and uncertainty.')+
        card('3 · Build restrictions','Bounds or complete equations with duplicate checks.')+
        card('4 · Calculate dispatch','Carry ramps and energy state through time.')+
        card('5 · Check results','Balances, violations, solver status, and coverage.')+
        card('6 · Save and evaluate','Issue the forecast first. Add actual outcomes later.')+'</div>')
    diagram('test_lanes','Three test types','<div class="diagram-grid cols3">'+
        card('Historical replay','Actual inputs check the engine. This is not a forward accuracy claim.','ENGINE')+
        card('Conditional research','Selected actual future inputs show the value of better information.','DIAGNOSIS')+
        card('Issue-time evaluation','Only eligible inputs enter the forecast. Later outcomes determine accuracy.','FORECAST')+'</div>')
    roadmap=[('Contract','Inputs and time rules'),('Replay','Engine verification'),('Bounds','First forecast comparison'),
             ('Scenarios','NOS and uncertainty'),('Equations','Supported mechanisms'),('Month ahead','Separate days 8–30 model'),('Shadow run','Live input and outcome checks')]
    diagram('roadmap','Stages with explicit decisions','<ol class="roadmap">'+''.join(
        f'<li><span>{i:02}</span><strong>{escape(a)}</strong><small>{escape(b)}</small></li>' for i,(a,b) in enumerate(roadmap,1))+'</ol>',
        'Start the month-ahead work after the shared contract and bound model. It can proceed beside the equation pilot.')


TERMS=[
    ('AEMO','Australian Energy Market Operator.'),('NEM','National Electricity Market.'),
    ('NEMPy','Python software for dispatch calculations.'),('QNI','Queensland–New South Wales interconnector.'),
    ('VNI','Victoria–New South Wales interconnector.'),('NOS','Network Outage Schedule.'),
    ('VRE','Variable renewable energy, including wind and solar generation.'),
    ('FCAS','Frequency control ancillary services.'),('DUID','Identifier for a dispatchable unit.'),
    ('dispatch','The generation, load, and flow result of a market calculation.'),
    ('forecast origin','Time when the forecast uses its available information.'),
    ('delivery interval','Market interval that a forecast value describes.'),
    ('forecast version','One provider run with its issue time and related values.'),
    ('forecast bounds','Lower and upper signed limits supplied to the dispatch model.'),
    ('tight limit','Minimum directional limit across six five-minute observations.'),
    ('mean limit','Average directional limit across six five-minute observations.'),
    ('constraint set','Group of equations for a network condition.'),
    ('binding constraint','Constraint at its limit within a stated numerical tolerance.'),
    ('limit setter','Equation that sets a reported directional limit.'),
    ('RHS','Right-hand-side value of a constraint equation.'),
    ('LHS','Left-hand-side terms of a constraint equation.'),
    ('headroom','Remaining room before a stated restriction becomes active.'),
    ('redispatch','Change in generator dispatch for changed conditions.'),
    ('forced flow','Flow that a signed bound requires in one direction.'),
    ('regime','Defined operating condition with relevant forecast behavior.'),
    ('scenario','One coherent set of input assumptions through time.'),
    ('ensemble','Collection of related scenarios or forecast members.'),
    ('calibration','Adjustment of forecast uncertainty against earlier errors.'),
    ('persistence','Forecast that uses the latest permitted target value.'),
    ('MAE','Mean absolute error.'),('RMSE','Root mean squared error.'),
    ('skill','Relative improvement against the stated reference forecast.'),
    ('coverage','Share of actual outcomes inside a stated prediction interval.'),
    ('Brier score','Mean squared error of a probability forecast for a binary outcome.'),
    ('out-of-fold forecast','Forecast from a model without training on the scored period.'),
    ('price spread','Difference between the stated regional prices.'),
    ('provenance','Record of source, version, timing, and data identity.'),
    ('MW','Megawatt, the unit of power.'),('pp','Percentage points, a difference between percentages.')]


def simulator():
    return '''<div class="simulator" id="simulator" role="group" aria-labelledby="sim-title">
    <span class="type-badge">Synthetic example</span><h3 id="sim-title">Change the reference condition</h3>
    <p>The controls change the same example as the charts. They do not run NEMPy or use market data.</p>
    <div class="controls"><label for="rhs">RHS (MW)<input id="rhs" type="range" min="100" max="1500" step="50" value="700"><output id="rhs-value" for="rhs">700 MW</output></label>
    <label for="reference">Reference generation (MW)<input id="reference" type="range" min="0" max="1400" step="50" value="600"><output id="reference-value" for="reference">600 MW</output></label></div>
    <div class="sim-results" aria-live="polite"><div><span>Fixed reference bound</span><strong id="fixed-result">400.00 MW</strong></div>
    <div><span>Equation-model flow</span><strong id="equation-result">466.67 MW</strong></div>
    <div><span>Both restrictions</span><strong id="combined-result">400.00 MW</strong></div></div>
    <p id="sim-note">The fixed bound prevents 66.67 MW of transfer in this example.</p>
    <p class="small">Future balance: P = F. Northern demand: 1,000 MW. Network equation: F + 0.5P ≤ RHS.</p>
    <button type="button" id="reset-sim">Reset example</button></div>'''


CSS='''
.report-content{max-width:1120px;margin:auto}.report-content h2{margin-top:65px;scroll-margin-top:76px;border-top:1px solid #dfe3eb;padding-top:26px}
.report-content h3{margin-top:28px}.report-content p{max-width:1040px;line-height:1.75}
.report-content table{white-space:normal;min-width:680px;font-size:14px}.report-content th,.report-content td{text-align:left;vertical-align:top}
.report-content th:first-child,.report-content td:first-child{min-width:130px}.report-content pre{background:#ececf3;padding:22px;border-radius:10px;font-size:15px;line-height:1.7}
.report-content code{font-size:.88em}.report-content a{overflow-wrap:anywhere}.report-content img{display:block;max-width:100%;height:auto}
.chart-scroll img{min-width:690px;border-top:2px solid #4c94df}.chart-source{font-size:13px;margin-top:9px!important;color:#636870}
figure,.design-figure,.simulator,.chart-data{scroll-margin-top:76px}
.type-badge{display:inline-block;font-size:11px;letter-spacing:.04em;text-transform:uppercase;font-weight:700;color:#286763;background:#e4f1ee;border-radius:5px;padding:4px 8px;margin-right:9px}
.chart-data{padding:12px 18px;margin:12px 0 32px;font-size:14px}.chart-data table{font-size:12px}.chart-data .table-wrap{max-height:440px;overflow:auto}.chart-data summary{font-size:13px}
.download,.button-link{display:inline-block;border:1px solid #cad7e5;border-radius:7px;padding:8px 12px;background:white;font-weight:650;font-size:13px;margin:8px 8px 0 0}
.topnav{position:sticky;top:0;background:#f5f6f9f5;backdrop-filter:blur(8px);z-index:10;padding:11px 0;margin-bottom:20px;gap:10px;align-items:center;border-bottom:1px solid #dfe3eb}
.topnav a{font-size:12px;border:1px solid #dfe3eb;border-radius:16px;padding:4px 9px;background:white}.topnav label{font-size:12px;margin-left:auto;display:flex;gap:7px;align-items:center}
.topnav select{max-width:250px;padding:7px;border:1px solid #cfd8e5;border-radius:5px;background:white;color:#282b30}
.hero-summary{font-size:19px;margin:25px 0;max-width:1000px}.metrics{margin:26px 0}.findings{margin:22px 0 35px}
.design-figure{margin:27px 0;padding:24px;background:white;border:1px solid #dfe3eb;border-radius:10px;overflow:hidden}
.diagram-heading{display:flex;align-items:center;gap:9px;margin-bottom:20px}.diagram-heading h3{margin:0;font-size:20px}
.diagram-grid,.horizon-grid,.formula-grid,.run-grid{display:grid;gap:14px}.cols3,.horizon-grid,.formula-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.run-grid{grid-template-columns:repeat(3,minmax(0,1fr))}
.diagram-card{background:#f5f6f9;border:1px solid #e0e5ed;border-top:3px solid #4c94df;border-radius:7px;padding:18px;min-width:0}
.diagram-card h3{margin:8px 0 10px;font-size:18px}.diagram-card p{font-size:14px;line-height:1.6;margin:0}.step-tag{font-size:11px;letter-spacing:.1em;color:#7658c9;font-weight:750}
.diagram-result,.formula-strip{background:#eaf3f5;border-left:4px solid #268a87;padding:14px 17px;margin-top:15px;font-size:14px}.diagram-note{font-size:12px;color:#636870;margin-bottom:0}
.flow-steps{list-style:none;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:15px;margin:0;padding:0;counter-reset:step}.flow-steps.four{grid-template-columns:repeat(4,minmax(0,1fr))}
.flow-steps li{margin:0;background:#ececf3;border-radius:6px;padding:17px 13px;position:relative}.flow-steps li:not(:last-child):after{content:'→';position:absolute;right:-14px;top:40%;color:#397fab}
.flow-steps strong{display:block;font-size:14px}.flow-steps span{display:block;font-size:12px;line-height:1.5;color:#636870;margin-top:8px}
.formula-grid>div{background:#ececf3;padding:18px;border-radius:7px}.formula-grid span{font-size:12px;color:#636870}.formula-grid strong{font-size:26px;display:block;margin:9px 0;color:#286763}.formula-grid p{font-size:13px;margin:0}
.roadmap{list-style:none;padding:0;display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:10px}.roadmap li{margin:0;border-top:3px solid #4c94df;background:#f5f6f9;padding:12px 10px;min-width:0}.roadmap span{font-size:23px;color:#7658c9;display:block}.roadmap strong{font-size:13px;display:block;margin:8px 0}.roadmap small{font-size:11px;line-height:1.5;display:block;color:#636870}
.simulator{padding:25px;border:1px solid #b8d2d1;background:#eef7f5;border-radius:10px;margin:27px 0}.simulator h3{margin:12px 0}.controls{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin:20px 0}
.controls label{font-weight:650;font-size:14px}.controls input{display:block;width:100%;margin:18px 0 8px;accent-color:#268a87}.controls output{font-size:14px;color:#286763}
.sim-results{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.sim-results>div{padding:15px;background:white;border-radius:7px;border:1px solid #d0e4df;min-width:0}.sim-results span{display:block;font-size:12px;color:#636870}.sim-results strong{display:block;font-size:25px;line-height:1.3;margin-top:8px}
button{background:#268a87;color:white;border:0;padding:10px 14px;border-radius:6px;font:inherit;font-size:13px;cursor:pointer}button:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #4c94df;outline-offset:3px}
.language-note{font-size:13px;background:#fff8e8;border-left:4px solid #bf8528;padding:15px 19px;margin:22px 0}
.toc{column-count:2;column-gap:28px}.toc ul{list-style:none;margin:0;padding:0}.toc li{margin:9px 0;break-inside:avoid;font-size:13px}.toc>ul>li>a{display:none}.toc>ul>li{margin:0}
.contents-panel{padding:20px 24px;background:white;border:1px solid #dfe3eb;border-radius:10px}.contents-panel h2{font-size:21px;margin:0 0 15px}.reading-tools{display:flex;flex-wrap:wrap;gap:8px;margin:20px 0}
@media(max-width:1000px){.roadmap{grid-template-columns:repeat(4,minmax(0,1fr))}.flow-steps{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:720px){.cols3,.horizon-grid,.formula-grid,.run-grid{grid-template-columns:1fr}.flow-steps,.flow-steps.four{grid-template-columns:1fr}.flow-steps li:not(:last-child):after{content:'↓';right:50%;top:auto;bottom:-17px}.roadmap{grid-template-columns:repeat(2,minmax(0,1fr))}.diagram-heading{align-items:flex-start;flex-direction:column}.design-figure{padding:18px}.topnav{position:static}.topnav label{margin-left:0;width:100%}.topnav select{max-width:none;width:100%}.toc{column-count:1}.controls{grid-template-columns:1fr;gap:12px}.sim-results{grid-template-columns:1fr}.simulator{padding:18px}.report-content h2{font-size:25px}.metric strong{font-size:26px}.hero-summary{font-size:17px}}
@media print{.topnav,.reading-tools,.simulator,.chart-data{display:none}.report-content h2{scroll-margin-top:0}.chart-scroll img{min-width:0}figure,.design-figure{break-inside:avoid}.report-content table{min-width:0}.table-wrap{overflow:visible}.report-content{max-width:none}}
'''


JS='''
(()=>{const rhs=document.getElementById('rhs'),ref=document.getElementById('reference');
const set=(id,v)=>document.getElementById(id).textContent=v;
function update(){const R=Number(rhs.value),P=Number(ref.value),bound=R-.5*P,equation=Math.min(1000,R/1.5);
const fixed=bound<0?null:Math.min(1000,bound),combined=bound<0?null:Math.min(fixed,equation);
set('rhs-value',R+' MW');set('reference-value',P+' MW');set('fixed-result',fixed===null?'Infeasible':fixed.toFixed(2)+' MW');
set('equation-result',equation.toFixed(2)+' MW');set('combined-result',combined===null?'Infeasible':combined.toFixed(2)+' MW');
set('sim-note',fixed===null?'The reference bound is negative. This northbound-only example has no feasible fixed-bound solution.':
fixed<equation?'The fixed bound prevents '+(equation-fixed).toFixed(2)+' MW of transfer in this example.':
fixed>equation?'The fixed-bound result exceeds the complete equation result by '+(fixed-equation).toFixed(2)+' MW.':
'Both methods give the same flow in this example.');}
rhs.addEventListener('input',update);ref.addEventListener('input',update);
document.getElementById('reset-sim').addEventListener('click',()=>{rhs.value=700;ref.value=600;update()});update();
document.getElementById('section-jump').addEventListener('change',e=>{if(e.target.value)document.getElementById(e.target.value).scrollIntoView({behavior:'smooth',block:'start'})});
document.getElementById('print-report').addEventListener('click',()=>window.print());
})();
'''


def language_check(html):
    soup=BeautifulSoup(html,'html.parser')
    records=[];paragraph_violations=[]
    for node in soup.select('p,li,td,th,summary,label'):
        if node.find(['p','li','table','input']) or node.find_parent(['pre','nav']):
            continue
        txt=node.get_text(' ',strip=True)
        if not txt: continue
        # This ordinary-token method is conservative and is not the complete STE counting method.
        sentences=re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])',txt)
        if node.name=='p' and len(sentences)>6:
            paragraph_violations.append(txt)
        for sentence in sentences:
            words=re.findall(r"[A-Za-z0-9]+(?:[’'_-][A-Za-z0-9]+)*",sentence)
            if words: records.append(dict(text=sentence,words=len(words),element=node.name))
    banned=re.compile(r"\b(utilize|leverage|commence|whilst|henceforth|aforementioned|therein)\b",re.I)
    contractions=re.compile(r"\b(?:don't|doesn't|isn't|aren't|can't|won't|it's|we're|you'll|they're)\b",re.I)
    long=[r for r in records if r['words']>20]
    return dict(target='ASD-STE100 Issue 9',status='Controlled-English draft; full dictionary conformity unverified',
                scope='Visible prose, table cells, labels, and diagram text. Excludes code, equations, source titles, and chart image labels.',
                method='Conservative ordinary-token count; not a full STE grammar or dictionary validator.',
                prose_sentence_limit=20,sentences_checked=len(records),max_words=max(r['words'] for r in records),
                over_limit=long,paragraphs_over_six_sentences=paragraph_violations,
                contractions=contractions.findall(soup.get_text(' ',strip=True)),
                selected_complex_words=banned.findall(soup.get_text(' ',strip=True)),
                technical_terms=len(TERMS),
                open_checks=['Complete approved-word, part-of-speech, and approved-meaning review against the full Issue 9 dictionary.',
                             'Independent conformity review; no conformity claim is made.'],
                standard_access='Official public guidance and indexed rule extracts available; direct full PDF access returned HTTP 403.',
                sources=['https://www.asd-ste100.org/STE_faq.html','https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf'])


def render(performance,quality):
    text=SOURCE.read_text(encoding='utf-8')
    md=markdown.Markdown(extensions=['tables','fenced_code','toc'],extension_configs={'toc':{'toc_depth':'2'}})
    raw=md.convert(text)
    replacements={**CHARTS,**DIAGRAMS,'calculator':simulator(),'glossary':table([{'term':a,'meaning':b} for a,b in TERMS])}
    for key,value in replacements.items():
        marker=f'<!-- visual:{key} -->'
        assert marker in raw,key
        raw=raw.replace(marker,value)
    assert '<!-- visual:' not in raw
    soup=BeautifulSoup(raw,'html.parser')
    title_id=soup.h1.get('id');soup.h1.decompose()
    for t in soup.find_all('table'):
        if not t.find_parent(class_='table-wrap'):
            t.wrap(soup.new_tag('div',attrs={'class':'table-wrap','tabindex':'0'}))
    headings=[(h['id'],h.get_text(' ',strip=True)) for h in soup.find_all('h2')]
    nav=('<nav class="topnav" aria-label="Report navigation">'+''.join(f'<a href="#{id_}">{label}</a>' for id_,label in [
        (headings[0][0],'Decision'),(headings[1][0],'Evidence'),(headings[6][0],'Bounds'),(headings[7][0],'Equations'),
        (headings[15][0],'Validation'),(headings[16][0],'Month ahead')])+
        '<label for="section-jump">Section<select id="section-jump"><option value="">Select a section</option>'+''.join(
            f'<option value="{escape(i)}">{escape(t)}</option>' for i,t in headings)+'</select></label></nav>')
    best=max(r['skill_pct'] for r in performance if r['connector']=='VNI')
    negatives=sum(r['skill_pct']<0 for r in performance if r['connector']=='QNI')
    body=hero('INTERFLOW / VISUAL RESEARCH REPORT','NEMPy forecast design.','Seven days to one month.',
              'Use forecast bounds first. Add equation scenarios where the inputs support them.',
              ['4 October 2026','Historical evidence through August 2026','STE draft · Issue 9'])
    body=body.replace('<header>',f'<header id="{title_id}">',1)
    body+='<p class="hero-summary">Start with VNI. Keep separate choices for QNI. Use a new scenario model for days 8–30.</p>'
    body+=('<div class="metrics">'+metric('VNI · best tight-limit cell',f'{best:.1f}%','MAE skill against persistence')+
        metric('QNI · negative-skill cells',f'{negatives} / 8','Tight limits across four lead bands')+
        metric('NOS · better Brier score',f"{quality[0]['numerator']} / {quality[0]['denominator']}",'Outlook comparison cells')+
        metric('Forecast scope','7 + 23 days','Separate input contracts')+'</div>')
    body+=('<div class="findings">'+finding(1,'Keep the simple reference','Forecast bounds give the first comparison. Better limit forecasts must also improve useful downstream results.')+
        finding(2,'Let dispatch determine binding','Use bookings and regimes to prepare network scenarios. Keep normal equations where they remain applicable.')+
        finding(3,'Use one restriction once','A fixed reported bound can prevent redispatch. Check duplicate restrictions before combining models.')+'</div>')
    body+='<div class="language-note"><strong>Language status:</strong> This draft applies the verified STE rules. Full dictionary conformity remains unverified. Section 20 records the limit.</div>'
    md_download='data:text/markdown;charset=utf-8;base64,'+base64.b64encode(text.encode()).decode()
    data_download='data:application/json;base64,'+base64.b64encode(json.dumps(DATASETS,ensure_ascii=False).encode()).decode()
    body+=('<div class="reading-tools"><button id="print-report" type="button">Print report</button>'+f'<a class="button-link" href="{md_download}" download="NEMPy_Visual_Report_STE.md">Download report text</a>'+
        f'<a class="button-link" href="{data_download}" download="research_evidence.json">Download all chart data</a></div>')
    body+='<details class="contents-panel"><summary>View all 20 sections</summary>'+md.toc+'</details>'+nav
    content='<article class="report-content">'+str(soup)+'</article>'
    language=language_check(content)
    write_json(OUT/'language_review.json',language)
    body+=content
    page=render_page('NEMPy forecast design — visual report and STE draft',body,plotly=False)
    page=page.replace('</head>','<style>'+CSS+'</style></head>').replace('</body>','<script>'+JS+'</script></body>')
    (OUT/'index.html').write_text(page,encoding='utf-8')
    return language


def main():
    for folder in [OUT,OUT/'data',OUT/'figures']:folder.mkdir(parents=True,exist_ok=True)
    evidence=load_evidence();make_charts(*evidence);make_diagrams()
    csv_data('technical_terms',[dict(term=a,meaning=b) for a,b in TERMS])
    write_json(OUT/'data/research_evidence.json',DATASETS)
    language=render(evidence[0],evidence[4])
    mapping={'1':[1],'2':[2,3,4,5],'3':[4,7,8],'4':[6,17],'5':[7],'6':[8,9],
        '7':[10],'8':[11],'9':[4,5],'10':[11,12],'11':[13],'12':[14],'13':[15],
        '14':[3,17,18],'15':[16],'16':[18],'17':[18],'18':[19],'19':[1,18],'20':[20]}
    write_json(OUT/'content_map.json',dict(original_report=str((OLD/'Forward_Forecast_with_NEMPy.md').relative_to(ROOT)),
        original_sections_to_new_sections=mapping,original_section_count=20,new_section_count=20))
    snapshot=[]
    for rel,expected in SOURCE_HASHES.items():
        actual=sha(ROOT/rel);assert actual==expected,f'Source changed during build: {rel}'
        snapshot.append(dict(path=rel,sha256=actual))
    write_json(OUT/'source_audit.json',dict(sources=snapshot,presentation_only=True,
        new_market_acquisition=False,new_model_training=False,all_source_hashes_unchanged=True))
    paths=[SOURCE,OUT/'index.html',OUT/'language_review.json',OUT/'content_map.json',OUT/'source_audit.json',
           *sorted((OUT/'data').glob('*')),*sorted((OUT/'figures').glob('*'))]
    inputs=[Path(__file__),ROOT/'scripts/verify_nempy_visual_ste_report.py',
            ROOT/'scripts/report_theme/report_theme.py',ROOT/'scripts/report_theme/report.css']
    manifest=dict(report='nempy_forward_forecast_visual_ste_20261004',report_date='2026-10-04',
        built_at=datetime.now(timezone.utc).isoformat(),rebuild='python scripts/build_nempy_visual_ste_report.py',
        charts=len(CHARTS),design_diagrams=len(DIAGRAMS),interactive_examples=1,
        source_cutoff='Primarily August 2026; no market-data refresh',
        language_status=language['status'],
        dependencies={n:importlib.metadata.version(n) for n in ['Markdown','matplotlib','numpy','beautifulsoup4']},
        inputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in inputs],
        outputs=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in paths])
    write_json(OUT/'manifest.json',manifest)
    print(json.dumps(dict(words=len(SOURCE.read_text(encoding='utf-8').split()),charts=len(CHARTS),diagrams=len(DIAGRAMS),
                         sentences_checked=language['sentences_checked'],over_limit=len(language['over_limit']),
                         max_words=language['max_words'],bytes=(OUT/'index.html').stat().st_size)))


if __name__=='__main__': main()
