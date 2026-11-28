"""Build the offline research report from the compact experiments."""
import base64
from pathlib import Path
import re
import markdown
from bs4 import BeautifulSoup
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path(__file__).resolve().parent
def load(file):return pd.read_csv(OUT/file)
def table(df):return df.to_markdown(index=False,floatfmt='.1f')
def chapter(folder):
    body=(OUT/folder/'report.md').read_text(encoding='utf-8-sig')
    return re.sub(r'\]\((?!https?:|#)([^)]+)\)',lambda m:']('+folder+'/'+m[1]+')',body)
def chart(frame,title,label,name):
    fig,ax=plt.subplots(figsize=(7.6,3.4),layout='constrained')
    for c,color in zip(frame.columns,['#205c66','#a35d36','#55698d','#476b44']):
        ax.plot(frame.index,frame[c],marker='o',label=c,color=color)
    ax.set_xticks([10,21,42]);ax.set(xlabel='Lead to delivery (days)',ylabel=label)
    ax.set_ylim(bottom=0);ax.grid(axis='y',alpha=.22);ax.spines[['right','top']].set_visible(False)
    ax.legend(frameon=False,fontsize=8);fig.savefig(OUT/name,dpi=150);plt.close(fig)
    return f'![{title}]({name})'
def main():
    co=load('points/coherent_scores.csv')
    q=co.query("phase=='routine' and point=='replayed'").pivot(index='method',columns='lead',values='mae')
    pv=load('solar/full_scores.csv').pivot(index='lead_days',columns='method',values='mae')
    prior=next(k for k in pv.columns if 'prior' in k.lower() and 'rhs' in k.lower())
    fig1=chart(pv[[prior,'geometry-adjusted 14-day median']].set_axis(['Prior RHS','Update rooftop solar'],axis=1),'Forecasting the complete SA MAXG dispatch limit','RHS mean absolute error (MW)','sa.png')
    fig2=chart(q.loc[['clock','prior bank configuration','demand plus bank analogue']].T.set_axis(['Historical paths','Prior bank state','Demand and bank state'],axis=1),'QNI MAXGEN forecast errors by scenario selection','RHS mean absolute error (MW)','qni.png')
    corr=load('points/breaker_scores.csv')
    cq=corr.query("partition=='routine'").pivot(index='method',columns='lead',values='mae').round(2)
    pt=load('points/scores.csv')
    pt=pt.query("phase=='routine' and lead==21").pivot(index='point',columns='method',values='mae')
    pts={'MW_AR_TX3':'Armidale transformer MW','MVA_AR_86':'Armidale–Tamworth MVA','MVAR_AR_TX3':'Armidale transformer MVAr','BU_SH1_LINE_220KV':'Bus voltage kV','VRAT15_RCWE':'Red Cliffs–Wemen rating MVA','TARBESS1':'Tarong battery signed MW','SHPUMP':'Shoalhaven pump MW','BL_PREVDI_TARGET':'Basslink prior target MW','Bango dispatch RHS':'Bango full RHS MW'}
    ps=pt.loc[list(pts)].rename(index=pts,columns={'carry':'Earlier reading','clock':'Clock median','topology':'Three state analogues'})
    rout=load('routing.csv')
    sc=load('screen.csv')
    net=load('network/scores.csv')
    league=net.query("partition=='routine' and lead==21 and target in ['export','import'] and method in ['seasonal direct','issued demand','clock equation']").pivot(index=['link','target'],columns='method',values='mae')
    b=load('points/breaker_predictions.csv')
    b=b.query("partition=='routine' and method=='previous state'").copy()
    mismatch=b.groupby('lead').apply(lambda g:int((g.prior_state!=g.actual_state).sum()),include_groups=False)
    body=f'''# Forecasting NEM dispatch constraints beyond seven days

## What to inject first

Use the dispatch formula at delivery. Give it complete operating scenarios built from information available at issue. AEMO's long-range adequacy reports supply regional energy, demand and availability assumptions. Historical electrical measurements supply plausible combinations of plant injections, line flows and device positions. The two sources have different resolution and uncertainty. [AEMO PASA](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/nem-forecasting-and-planning/forecasting-and-reliability/projected-assessment-of-system-adequacy)

- **Rooftop solar can be worth forecasting explicitly.** On 12 complete half-hours per lead, updating the prior SA operating state with a solar-elevation-adjusted forecast reduced full-equation error from {pv.loc[42,prior]:.1f} to {pv.loc[42,'geometry-adjusted 14-day median']:.1f} MW at 42 days. Its value depended on the active branch.
- **Spend network-data effort where it changes the answer.** For the NSW–Queensland MAXGEN equation, selecting historical paths by the earlier capacitor/reactor configuration improved 21-day RHS error from {q.loc['clock',21]:.1f} to {q.loc['prior bank configuration',21]:.1f} MW. At 42 days that choice increased error to {q.loc['prior bank configuration',42]:.1f} MW. Four morning half-hours per lead support this comparison. Use the spread of plausible paths at longer leads.
- **Retain independent forecasts for the reported directional limits.** At 21 days, the direct seasonal benchmark beat the demand-conditioned equation scenarios in all four directions. Binding alerts also require a forecast of weighted dispatch on the left-hand side. The issued-demand screen found 2 of 2 routine QNI binding half-hours with 43 false alerts and missed 17 of 17 VNI positives at the 25% cutoff.

The tests use 10, 21 and 42 days as representative leads for 8–14, 15–28 and 29–56 days. Scores apply to the tested leads and February 2026 samples. Every market time is an interval end in fixed UTC+10. [Candidate equation screen](screen.csv) · [Routing register](routing.csv)

## Directional limits and binding

Mean absolute error in MW for the reported tight half-hour limit at 21 days, four routine dates. Import uses the project's signed directional convention. Each forecast route is evaluated on the same delivery rows within a direction.

{table(league.reset_index())}

{chapter('network')}

## Rooftop solar and MAXG

For this SA equation, keep the regional entered PV estimate and the SAPN-controlled MW as separate inputs. On the ordinary PV-sensitive branch, an additional 100 MW in the entered solar estimate lowers the RHS by approximately 37.05 MW **while the same branch remains selected**. Each additional MW of controlled PV lowers it by 0.36 MW on that branch. An illustrative 5 MW RHS error budget therefore allows about 13.5 MW of entered PV error with every other input fixed. The observed long-lead regional forecast errors are much larger. Run low, central and high PV paths through the maximum and the flags; a fixed coefficient alone loses the transition to the insensitive branch. [Native replay and branch tests](solar/case_replays.csv)

{fig1}

{chapter('solar')}

## Forecasting the dispatch A and S terms together

The full NSW–Queensland MAXGEN equation includes signed Terranora and Muswellbrook load, an embedded Far North NSW load program, multiple capacitor and reactor groups, and the largest of eleven plant injections. Replaying its 2 December 2025 version against 90 native case outputs puts the largest discrepancy below 0.000001 MW. Other equation versions were excluded from that check. The scenario model evaluates this program for each native historical state before averaging six values. It preserves correlations between load, generation and switch positions. [Independent replay](points/qni_replay.csv) · [Native case extractor and formula](points/run.py)

{fig2}

Mean absolute error in MW of the half-hour average RHS. Each column holds four complete half-hours ending 10:30 on 4, 11, 18 and 25 February. “Clock” uses all eligible historical paths. “Last sampled state” carries the most recent eligible weekly case path. Nearest-demand routes use the three closest earlier mornings. Bank matching uses a six-device Tamworth state vector. The peak-based demand comparator scales a historical profile to the issued adequacy peak. Weekly energy uses the issued energy total. The analogue matches forecast regional demand to the historical case's initial regional demand, so differences between demand definitions also enter its error.

{table(q.reset_index())}

The first Tamworth capacitor contributes 120 × 0.2091 = **25.092 MW** when on, with other terms fixed. The two sampled Tamworth reactor inputs each contribute −10.455 MW when on. A plan that changes a device may also change the line loading and other dispatch inputs. Use those single-device numbers for sensitivity. Draw the feeder, generator and switch path together for a complete RHS scenario. Historical paths and their min/max range describe observed alternatives; their range carries no prescribed probability. [Whole-path predictions and realised values](points/coherent_predictions.csv) · [Scenario members](points/scenario_paths.csv)

### Breakers and apparent power at a named terminal

At the Ararat end of the Ararat–Stawell 66 kV line, the measured quantity is a state-estimated MVA value. We grouped historical readings by the simultaneous reported state of Ararat breaker F and Stawell breaker B. At each native interval, the forward predictor uses the most recent eligible case's state pair, then takes the historical median loading for that configuration and clock. A separate diagnostic supplies the realised state pair to isolate the potential value of knowing it. The two breaker IDs are operating-state indicators. A circuit diagram and dated switching instruction are needed to infer a unique physical state from an outage booking.

{table(cq.reset_index())}

The previous state pair differed from delivery on {mismatch.loc[10]}, {mismatch.loc[21]} and {mismatch.loc[42]} of 24 routine native intervals at 10, 21 and 42 days respectively. Unknown future states stay as separate configurations, each with the support count and conditional terminal loading in the download. [Conditional loading scenarios](points/breaker_scenarios.csv) · [Scores and denominators](points/breaker_scores.csv)

The quiet Ararat–Stawell sample understates the difficulty of forecasting a switching device that actually moves. For the Portland wind farm CNS 66 kV breaker, carrying the earlier sampled state missed **12/24, 14/24 and 16/24** routine native readings at the three leads. The corresponding stress-window counts were 4/12, 0/12 and 6/12. Six observations from one half-hour are correlated. For a material Portland status term, keep the two feasible operating branches explicit until a dated switching instruction or a validated plant-state model distinguishes them. [Device observations and predictions](points/predictions.csv)

### Other difficult measurements

Mean absolute errors at 21 days on the same routine mornings. Each row uses its stated engineering unit. These three marginal input benchmarks use persistence, a same-clock historical median or the three earlier days closest to a four-signal historical state vector. They test whether an input deserves a separate feed. The full NSW MAXGEN experiment above uses coherent native paths.

{table(ps.reset_index())}

For unit commitment and pumping, sample entire operating combinations. For storage, publish separate signed power paths until a dated energy and availability forecast can constrain them. A flat inertia or switch observation during a small evaluation offers no test of transition behaviour. Dynamic ratings and apparent power have different error mechanisms even though both are measured in MVA. Collect a terminal-specific rating before investing in a more detailed MW model. [All input scores, biases and earlier calibration widths](points/scores.csv)

## Public demand, availability and outages

{chapter('feeds')}

## Calculator handoff

{table(rout[['Input','8–56 day injection','When to report scenarios']])}

For a custom regional scenario, bind each delivery to one origin and retain the source run IDs. Change a net demand forecast only by the difference from the PV assumption already embedded in it. Evaluate the effective dispatch formula inside every feasible path. Record invocation, RHS, LHS and signed headroom, then take the tight directional limit across six complete native intervals. When no prospective device mapping or operator setting exists, disclose which assumption changes the decision and the two resulting limits. [Download the input register](routing.csv)

## Limits of the experiment and reproducibility

The screen cross-references {len(sc)} connector/direction/equation records from the September 2025 historical influence analysis with the typed dependency inventory of 4 February 2026. The inventory is a retrospective crosswalk and some equations or versions have no match. Long-range historical receipt by the user's system is unobserved. The studies enforce availability using dated public source records or a conservative delay, documented for each experiment. They test public stand-ins for the user's own forecasts. Evidence on one season or a few independent event dates cannot support a production alert cutoff.

The terminal pilot sampled Wednesday mornings from August 2025 to February 2026 and added 19 and 22 February as stress dates identified in earlier work. It omits 5 November because two native files had only over-constrained-dispatch rerun labels. The training library rolls forward using only case days at least two calendar days old whose archive timestamps precede origin. Its latest-state benchmark can consequently be older than an operational telemetry feed. December errors available before the earliest test origin calibrate the illustrative point-input bands. A separate command and source log are retained for each study. Files containing original forecast values, case member names and hashes are included in the evidence download.
'''
    (OUT/'report.md').write_text(body,encoding='utf8')
    page=BeautifulSoup(markdown.markdown(body,extensions=['tables','toc','fenced_code']),'html.parser')
    for img in page.find_all('img'):
        ref=OUT/img['src']
        img['src']='data:image/png;base64,'+base64.b64encode(ref.read_bytes()).decode()
    for t in page.find_all('table'):t.wrap(page.new_tag('div',attrs={'class':'scroll'}))
    nav=' · '.join(f'<a href="#{h["id"]}">{h.get_text()}</a>' for h in page.select('h2[id]'))
    css='body{max-width:1000px;margin:auto;padding:22px;color:#182f39;font:16px/1.6 system-ui;background:white}h1{font: bold clamp(32px,5vw,52px)/1.12 Georgia}h2{margin-top:42px;border-top:2px solid #33656d;padding-top:16px}a{color:#155c73;overflow-wrap:anywhere}img{max-width:100%;height:auto}table{font-size:14px;border-collapse:collapse}td,th{padding:8px;text-align:left;border-bottom:1px solid #ced9d8}th{background:#edf4f2}.scroll{overflow:auto}code{overflow-wrap:anywhere}nav{font-size:14px}p{max-width:90ch}'
    (OUT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Long-range NEM constraint research</title><style>'+css+'</style><body><nav>'+nav+'</nav>'+str(page)+'</body></html>',encoding='utf8')
if __name__=='__main__':main()
