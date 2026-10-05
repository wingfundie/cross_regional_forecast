"""Rebuild the forward forecasting verdict from frozen, compact research evidence."""
from pathlib import Path
import base64, hashlib, io, json, sys
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_theme.report_theme import hero, metric, finding, figure_html, render_page, matplotlib_style
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'reports/forward_forecasting_verdict_20261005'
SRC = ROOT / 'reports/qni_vni_longrange_v1'
BANDS = ['days_1_7','days_8_14','days_15_30','days_31_60','days_61_90']
LABELS = ['0.5 h–7 d','8–14 d','15–30 d','31–60 d','61–90 d']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def table(df): return '<div class="table-wrap" tabindex="0">'+df.to_html(index=False, border=0, float_format=lambda x:f'{x:.2f}')+'</div>'
def chart(fig, title, note, data='downloads/band_metrics.csv'):
    buf=io.BytesIO(); fig.savefig(buf,format='png',bbox_inches='tight',dpi=150); plt.close(fig)
    return figure_html('<img style="min-width:760px" alt="'+escape(title)+'" src="data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()+'">',title,note,data)
class MarkdownText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.href=None; self.rows=None; self.row=[]; self.cell=None
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='table': self.rows=[]
        if tag=='tr': self.row=[]
        if tag in ['td','th']: self.cell=[]
        if self.rows is not None: return
        if tag in ['p','li','ol','ul','h3','div','pre']: self.parts.append('\n\n')
        if tag=='li': self.parts.append('- ')
        if tag=='a': self.href=attrs.get('href'); self.parts.append('[')
        if tag=='img': self.parts.append('[Chart: '+attrs.get('alt','')+' — see HTML edition]')
    def handle_endtag(self, tag):
        if tag in ['td','th']:
            self.row.append(''.join(self.cell).strip().replace('|','/')); self.cell=None
        if tag=='tr': self.rows.append(self.row)
        if tag=='table':
            for i,row in enumerate(self.rows):
                self.parts.append('\n| '+' | '.join(row)+' |')
                if i==0: self.parts.append('\n|'+'---|'*len(row))
            self.parts.append('\n\n'); self.rows=None
        if self.rows is not None: return
        if tag in ['p','li','h3','div','pre']: self.parts.append('\n\n')
        if tag=='a': self.parts.append(']('+str(self.href)+')')
    def handle_data(self,data):
        if self.cell is not None: self.cell.append(data)
        elif self.rows is None: self.parts.append(data)

def build():
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'downloads').mkdir(exist_ok=True)
    inputs=[SRC/'downloads/cell_results.csv',SRC/'downloads/band_metrics.csv',ROOT/'configs/experiments/qni_vni_longrange_v1.json',ROOT/'docs/RESEARCH_REGISTER.json',ROOT/'docs/VNI_DIURNAL_NOS_RESULTS.md',ROOT/'docs/QNI_DIURNAL_NOS_RESULTS.md',SRC/'manifest.json',ROOT/'execution/qni_vni_longrange_v1/METHODOLOGY.md']
    for name in ['cell_results.csv','band_metrics.csv']:
        (OUT/'downloads'/name).write_bytes((SRC/'downloads'/name).read_bytes())
    cells=pd.read_csv(inputs[0]); bands=pd.read_csv(inputs[1]); config=json.loads(inputs[2].read_text())
    registry=json.loads(inputs[3].read_text())['entries']
    assert len(cells)==10 and len(bands)==50 and not cells.duplicated(['connector','target']).any()
    assert bands.groupby(['connector','target']).size().eq(5).all()
    primary=bands[bands.band.isin(BANDS[:2])]
    calibrated=int(primary.groupby(['connector','target']).calibrated.all().sum())
    promoted=int(cells.decision.eq('improvement_demonstrated').sum())
    plt.rcParams.update(matplotlib_style())
    sections=[]; md=['# Forward forecasting: evidence and verdict','', 'Presentation: 5 October 2026. Results are frozen historical research; no new fit or live forecast is claimed.','']
    def section(key,title,prose,extra=''):
        sections.append(f'<section id="{key}"><h2>{escape(title)}</h2><p>{escape(prose)}</p>{extra}</section>')
        parser=MarkdownText(); parser.feed(extra)
        md.extend(['## '+title,'',prose,'',''.join(parser.parts),''])
    section('verdict','01 · What can be used now',
      'Use the calendar baseline and target persistence as transparent research references. The VNI diurnal policy is the strongest short-range candidate for prospective testing. No saved research model has established an operational forward-forecasting claim. The new long-range campaign promotes zero replacements, and its shadow route retains calendar in every cell. Both collection and shadow schedules were paused at the user’s request on 4 October 2026.',
      table(pd.DataFrame([
       ['Calendar + persistence','Reference outlook / manual shadow','Track both; calendar is the retained route, not proven best everywhere'],
       ['VNI diurnal/NOS v2','Priority short-range shadow candidate','Verify live feature contract and recalibrate uncertainty'],
       ['QNI diurnal/NOS v2','Target-specific research only','Mixed skill and inconclusive primary confidence bounds'],
       ['Long-range MT PASA v1','Sparse-horizon research outlook','No challenger passes; not a full 4,320-step path'],
       ['Six-link original backtest','Conditional scenarios','Realised future fundamentals preclude a live accuracy claim'],
       ['NOS / outage scenarios','Qualitative risk and scenario analysis','Associations and scenario deltas are not calibrated event probabilities'],
       ['Fundamentals v3 / clustering','Development evidence','Revalidation and prospective confirmation remain outstanding'],
       ['Production scaffold','Reusable engineering components','Not an approved deployed service or model promotion'],
       ['Valuation v2','Historical settlement / hedge research','Forward futures history and issue-time regimes still required']
      ],columns=['Component','Permitted use','Condition / limitation'])))
    section('scope','02 · What the new experiment actually covers',
      'The prepared dataset contains 305 daily origins from 2 August 2025 to 2 June 2026 and 54,900 connector-target-lead rows. The held-out block contains 56 daily origins; each target has 1,008 evaluated rows. Only 18 half-hour-indexed leads are sampled. Each shadow output therefore has 90 rows per connector (18 leads × 5 targets), rather than 90 daily values or a complete half-hour curve. Delivery outcomes extend to day 90 after the last origin. Historical report-generation times are availability proxies, not measured receipts.',
      '<div class="callout scope-note">The first band includes 0.5 hours through 7 days. Only two sampled leads support each later band. Results cannot establish accuracy for every intervening half-hour, every delivery period, or all seasons.</div>'+table(pd.DataFrame({'Lead index':config['leads_half_hours'],'Hours ahead':[x/2 for x in config['leads_half_hours']],'Days ahead':[x/48 for x in config['leads_half_hours']]})))
    display=cells[['connector','target','winner','weighted_primary_skill','weighted_primary_skill_vs_persistence','decision']].copy()
    display.iloc[:,3:5]=display.iloc[:,3:5]*100
    display.columns=['Connector','Target','Selection winner','Skill vs calendar (%)','Skill vs persistence (%)','Decision']
    fig,ax=plt.subplots(figsize=(11,6)); y=np.arange(len(cells)); labels=(cells.connector+' / '+cells.target).str.replace('_',' ')
    ax.barh(y-.18,cells.weighted_primary_skill*100,.34,label='vs calendar',color='#5696b9');ax.barh(y+.18,cells.weighted_primary_skill_vs_persistence*100,.34,label='vs persistence',color='#ce9a48')
    ax.set_yticks(y,labels);ax.invert_yaxis();ax.axvline(0,color='#666');ax.set_xlabel('Weighted MAE skill (%) · positive is better');ax.legend(loc='lower right')
    section('results','03 · New results: comparison with both controls',
      '“Selection winner” means the model chosen before evaluation; it does not mean a promoted model. VNI gains little against calendar even where it beats persistence. QNI export and flow gains against calendar disappear against persistence. QNI import is promising on average, but fails the dependence-aware confidence gates. A 75% / 25% weighting of the two primary bands cannot substitute for evidence in both bands.',
      chart(fig,'Weighted primary skill by target','Frozen selection winners; matched evaluation rows. Calendar winners have exactly zero skill against themselves.','downloads/cell_results.csv')+table(display))
    for connector in ['VNI','QNI']:
        fig,axes=plt.subplots(1,2,figsize=(12,4.6))
        for ax,target in zip(axes,['export_tight','import_tight']):
            g=bands[(bands.connector==connector)&(bands.target==target)].set_index('band').loc[BANDS]
            for col,label in [('model_mae','Selection winner'),('baseline_mae','Calendar'),('persistence_mae','Persistence')]: ax.plot(LABELS,g[col],marker='o',label=label)
            ax.set_title(target.replace('_',' '));ax.set_ylabel('MAE (MW)');ax.tick_params(axis='x',rotation=25)
        axes[0].legend(fontsize=9);fig.tight_layout()
        section(connector.lower(),f'04 · {connector}: tight-limit performance by horizon',
          'Tight limits are the minimum of the six five-minute observations in each complete half-hour. The retained sign convention matters: negative limits can represent forced flow. These are AEMO dispatch-solution limits, not maximum secure physical transfer capability. Lines connect sampled-band summaries and do not represent a continuous forecast path.',
          chart(fig,f'{connector} tight-limit MAE','Lower is better. Same held-out population within each cell; band populations differ.'))
    fig,axes=plt.subplots(1,2,figsize=(12,6))
    for ax,col,nominal,threshold in zip(axes,['coverage_80','coverage_95'],[80,95],[77,92]):
        matrix=bands.assign(cell=bands.connector+' / '+bands.target).pivot(index='cell',columns='band',values=col).reindex(columns=BANDS)*100
        ax.grid(False); im=ax.imshow(matrix,aspect='auto',vmin=0,vmax=100,cmap='YlGnBu');ax.set_yticks(range(len(matrix)),matrix.index);ax.set_xticks(range(5),LABELS,rotation=35,ha='right');ax.set_title(f'Nominal {nominal}% · gate ≥{threshold}%')
        for i in range(len(matrix)):
            for j in range(5):ax.text(j,i,f'{matrix.iloc[i,j]:.0f}',ha='center',va='center',color='white' if matrix.iloc[i,j]>85 else '#282b30',fontsize=8)
    fig.tight_layout()
    section('uncertainty','05 · Uncertainty is still a separate gate',
      f'{calibrated} of 10 selected-model cells meet both empirical interval thresholds in both primary bands. These coverage checks do not establish prospective calibration, interval sharpness, or coverage of the retained calendar route where a challenger was evaluated. Interval widths, event precision/recall and false-alert durations are not present in this compact long-range evidence; they remain unverified, not zero. Wide intervals can achieve coverage without being useful.',
      chart(fig,'Empirical interval coverage (%)','Coverage applies to the selection winner. Acceptance floors are 77% / 92% for nominal 80% / 95%.') )
    ci=primary.copy();ci['cell']=ci.connector+' / '+ci.target+' / '+ci.band
    fig,axes=plt.subplots(1,2,figsize=(14,9))
    for ax,col,title in zip(axes,['improvement_mw_ci95','persistence_improvement_mw_ci95'],['Against calendar','Against persistence']):
        vals=np.array([json.loads(v) for v in ci[col]]); yy=np.arange(len(ci)); ax.hlines(yy,vals[:,0],vals[:,1],color='#5696b9',linewidth=2); ax.scatter(vals.mean(axis=1),yy,s=12,color='#268a87');ax.axvline(0,color='#ce9a48');ax.set_yticks(yy,ci.cell.str.replace('_',' ') if ax==axes[0] else ['']*len(ci));ax.invert_yaxis();ax.set_title(title);ax.set_xlabel('95% interval for MAE improvement (MW)')
    fig.tight_layout()
    section('confidence','06 · Why the headline gains do not pass',
      'Promotion requires at least 2% weighted skill against both controls and a strictly positive lower confidence bound against both controls in each primary band. None passes all conditions. The seven-day moving-block bootstrap accounts for short-run dependence, but the evaluation contains only 56 issue days; long-lead overlap and a single seasonal evaluation window limit generalisation. The chart shows confidence interval ranges; dots indicate interval midpoints, not separately estimated effects.',chart(fig,'Primary-band improvement confidence intervals','Crossing zero means an improvement is not established by this gate.'))
    coverage_rows=[]
    for connector in ['VNI','QNI']:
        text=(ROOT/f'docs/{connector}_DIURNAL_NOS_RESULTS.md').read_text(encoding='utf-8')
        for line in text.splitlines():
            parts=[v.strip() for v in line.strip().strip('|').split('|')]
            if len(parts)>3 and parts[0]=='Delivery period':
                coverage_rows.append({'connector':connector,'nominal':float(parts[1].rstrip('%')),'coverage':float(parts[2].rstrip('%'))})
    earlier=pd.DataFrame(coverage_rows).sort_values(['connector','nominal'])
    assert len(earlier)==4
    earlier.to_csv(OUT/'downloads/earlier_coverage.csv',index=False)
    fig,ax=plt.subplots(figsize=(10,4))
    yy=np.arange(len(earlier));ax.bar(yy-.18,earlier.nominal,.34,label='Nominal',color='#ce9a48');ax.bar(yy+.18,earlier.coverage,.34,label='Empirical',color='#5696b9')
    ax.set_xticks(yy,[f'{r.connector} / {r.nominal:.0f}%' for r in earlier.itertuples()]);ax.set_ylabel('Coverage (%)');ax.legend();ax.set_ylim(0,105)
    earlier_chart=chart(fig,'Earlier diurnal models: interval undercoverage','Twelve rolling monthly folds; delivery-period calibration; distinct from long-range v1.','downloads/earlier_coverage.csv')
    section('prior','07 · How the earlier research changes the verdict',
      'VNI diurnal v2 has the strongest retrospective evidence: tight-export skill versus persistence is 33.2%, 42.0%, 36.3% and 19.8% across its four bands through seven days; tight-import skill is 17.1%, 25.1%, 26.4% and 22.0%. Its primary moving-block tests exclude zero. QNI is mixed: the shortest-band export improves 4.6%, while import worsens 8.7%, and primary confidence intervals include zero. These studies have different samples, features and protocols from long-range v1; their percentages must not be ranked as a single leaderboard.',
      '<p>VNI nominal 80% / 95% intervals cover 74.14% / 90.53%; QNI covers 71.93% / 87.41%. Both under-cover. The diurnal “calendar policy” includes learned delivery-time specialisation and observed history; it is not the simple calendar-only long-range baseline. NOS point-model additions were not admitted to the VNI default. Fundamentals v3 retains a historical report but requires ledger revalidation. Clustering remains development evidence; no promotion record is established here.</p>'+earlier_chart)
    section('methods','08 · Data, method and implementation changes',
      'Origins are fixed at 08:00 NEM time (UTC+10), equivalent to 06:00 Singapore. The experiment compares a seasonal calendar model, target-specific persistence at origin minus 30 minutes, ridge and fixed shallow boosting. Challengers add coherent source/sink MT PASA availability summaries and the observed target anchor. Selection and calibration each reserve 28 origins and evaluation reserves 56; delivery outcomes are purged at boundaries. This is a single chronological held-out experiment, not repeated walk-forward confirmation.',
      '<p>The new implementation preserves source/product/run identity, completed receipt time, age and hashes; records only lineage actually used; supports revision-aware outcomes, daily alert episodes and outage scenarios; and extends the scaffold’s horizon contract. These are engineering improvements, not measured forecasting skill. Prospective source selection requires receipt completed before issue and source age no greater than 42 hours. Realised future weather, demand, VRE, dispatch and constraint setters are excluded from this challenger.</p><p>The challenger adds an anchor as well as availability features relative to the calendar baseline. Consequently, this comparison does not isolate the incremental contribution of MT PASA; an anchor-only matched ablation is still needed. No matched AEMO forecast comparison is supplied in the new long-range scorecard.</p>')
    section('next','09 · Practical route to usable forward forecasts',
      'First establish a trusted prospective scorecard, then add complexity only when matched evidence supports it. Schedules remain paused; publishing this report does not resume collection or shadow execution.',
      '<ol><li><strong>Freeze the evidence contract.</strong> Keep the new evaluation as development evidence. Specify point, risk and interval acceptance rules before the next unseen period.</li><li><strong>Complete delivery coverage.</strong> Generate and assess the requested 4,320 half-hour leads, with season and delivery-period breakdowns. Sparse lead tests are insufficient for a daily full-path product.</li><li><strong>Prove the feed.</strong> When collection is deliberately resumed, preserve completed receipts, coherent vintages, coverage, stale-source fallbacks and immutable issued forecasts.</li><li><strong>Test simple alternatives first.</strong> Run calendar, persistence and calendar-plus-anchor on identical rows. Add MT PASA alone next; use matched AEMO vintages where available.</li><li><strong>Prioritise VNI short-range.</strong> Reproduce its exact saved feature contract and collect prospective predictions. Treat QNI by direction and lead, with persistence retained as a serious competitor.</li><li><strong>Repair uncertainty and risk.</strong> Calibrate on eligible history and report coverage plus width, incident recall/precision, false episodes and duration. Test the agreed budget of at most three false episodes per connector per day.</li><li><strong>Promote only after confirmation.</strong> Require positive point-skill evidence against both controls, acceptable uncertainty and risk, provenance checks and an explicit promotion record. Use out-of-fold upstream forecasts in downstream valuation.</li></ol>')
    section('data','10 · Full long-range evidence',
      'All 50 target-band records are provided below and as CSV. Missing metrics are not inferred. These compact tables allow independent comparison without publishing raw observations or fitted models.',table(bands))
    links=''.join(f'<li><a href="../../{escape(str(p.relative_to(ROOT)).replace(chr(92),chr(47)))}">{escape(str(p.relative_to(ROOT)))}</a></li>' for p in inputs)
    section('sources','11 · Sources, provenance and rebuilding',
      'This report synthesises the repository’s frozen research evidence; no external market data was refreshed and no model was retrained. The manifest hashes the inputs, generator, local theme and delivered outputs. The HTML embeds its figures and CSS and works offline; keep the downloads folder alongside it for CSV access.',
      '<ul>'+links+'</ul><p><a href="downloads/cell_results.csv" download>Cell results CSV</a> · <a href="downloads/band_metrics.csv" download>Band metrics CSV</a> · <a href="report.md">Markdown edition</a> · <a href="manifest.json">Build manifest</a></p><pre>python scripts/build_forward_forecasting_verdict.py</pre>')
    body=hero('INTERFLOW / RESEARCH REVIEW','Forward forecasting.','Evidence before deployment.','A consolidated verdict on the new 90-day experiment, the strongest earlier models, and the remaining requirements for a trustworthy forward service.',['Presentation · 5 Oct 2026','New evaluation · 56 issue days','Research only','Schedules paused'])
    body+='<nav>'+''.join(f'<a href="#{k}">{v}</a>' for k,v in [('verdict','Verdict'),('scope','Coverage'),('results','Results'),('uncertainty','Uncertainty'),('prior','Earlier research'),('methods','Methods'),('next','Next steps'),('data','Data')])+'</nav>'
    body+='<div class="metrics">'+metric('New cells evaluated',len(cells),'2 connectors × 5 targets')+metric('Replacements promoted',promoted,'Both-control gates required')+metric('Primary interval gates',f'{calibrated}/10','Selected models; historical coverage')+metric('Sampled horizons',len(config['leads_half_hours']),'0.5 hours through 90 days')+'</div>'
    body+='<div class="findings">'+finding(1,'VNI is the first prospective candidate','Earlier short-range evidence is stronger, but receipt-time verification and recalibration remain necessary.')+finding(2,'QNI needs both benchmarks','Calendar-relative gains can coexist with material underperformance against persistence.')+finding(3,'Long-range coverage is incomplete','The campaign samples 18 horizons. It does not validate a complete half-hour forecast curve.')+'</div>'
    body+=''.join(sections)
    (OUT/'index.html').write_text(render_page('Forward forecasting — evidence and verdict',body,plotly=False),encoding='utf-8')
    md+=['## New cell results','',display.to_markdown(index=False),'','## Full band results','',bands.to_markdown(index=False),'']
    (OUT/'report.md').write_text('\n'.join(line.rstrip() for line in '\n'.join(md).splitlines())+'\n',encoding='utf-8')
    artifacts=[OUT/'index.html',OUT/'report.md',OUT/'downloads/cell_results.csv',OUT/'downloads/band_metrics.csv',OUT/'downloads/earlier_coverage.csv']
    inputs += [Path(__file__),ROOT/'scripts/report_theme/report_theme.py',ROOT/'scripts/report_theme/report.css']
    manifest={'built_at':datetime.now(timezone.utc).isoformat(),'presentation_date':'2026-10-05','claim':'Historical development evidence; no operational promotion','rebuild':'python scripts/build_forward_forecasting_verdict.py','visual_review':'Desktop/mobile browser layout not verified: local-file browser access was blocked in this session','dependencies':{'pandas':pd.__version__,'matplotlib':matplotlib.__version__},'inputs':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in inputs],'outputs':[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':sha(p)} for p in artifacts]}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(OUT/'index.html')
if __name__=='__main__': build()
