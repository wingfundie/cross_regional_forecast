"""Build the flows chapter and verify every reported score directly against interval evidence."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
P=Path(__file__).resolve().parent
tr=pd.read_csv(P/'flow_predictions.csv',parse_dates=['end','issued'])
rr=pd.read_csv(P/'rhs_predictions.csv',parse_dates=['end','issued'])
pump=pd.read_csv(P/'scheduled_load_predictions.csv',parse_dates=['end','issued'])
obs=pd.read_csv(P/'public_dispatch.csv',parse_dates=['end','modified']).set_index('end')
fc=pd.read_csv(P/'issued_values.csv',parse_dates=['end','issue','modified'])
cal=tr[tr.phase=='calibration']; test=tr[tr.phase=='test']
assert cal.end.max()<test.issued.min()
assert not tr.duplicated(['product','link','method','end']).any()
assert not rr.duplicated(['product','method','end']).any()
assert not pump.duplicated(['product','method','end']).any()
assert ((fc.modified.groupby(fc.run).first()-fc.issue.groupby(fc.run).first()).dt.total_seconds()>=0).all()
assert test[['issued','end']].drop_duplicates().issued.nunique()==15
assert (test.groupby(['product','link','method']).size()==72).all()
assert (rr.groupby(['product','method','phase']).size().unstack()['test']==72).all()
assert np.allclose(tr.prediction-tr.actual,tr.error)
both=pd.concat([rr,pump],ignore_index=True)
assert np.allclose(both.predicted_rhs-both.actual_rhs,both.error)
same=both[both.phase=='test']
flow=test.groupby(['product','method','link']).error.apply(lambda x:x.abs().mean()).unstack('method')
assert np.allclose(flow.stack().sort_index(),pd.read_csv(P/'flow_scores.csv').set_index(['product','link','method']).mae.sort_index())
cols=['persist','clock profile','prior issued target','issued ramp']
display=flow.reset_index().pivot(index='link',columns='product',values=cols)
flowrows=[]
for link,g in display.iterrows():
    flowrows.append((link,*(g[c,'P5MIN'] for c in cols[:3]),*(g[c,'PREDISPATCHIS'] for c in cols)))
ft=pd.DataFrame(flowrows,columns=['Signed link','Short carry','Short clock','Short issued','Day carry','Day clock','Day prior target','Day ramp']).to_markdown(index=False,floatfmt='.1f')
rhs=same.groupby(['method','product']).error.apply(lambda x:x.abs().mean()).unstack()
rhs.columns=['Short MAE','Day-ahead MAE']
rt=rhs.rename(index={'issued flow, local load and adjusted regional demand':'Issued flow and local load + total demand plus all issued dispatchable load','issued flow and local load with prior scheduled-load SCADA':'Issued flow and local load + total demand plus three prior pump readings','issued flow and local load with total demand':'Issued flow and local load + total demand only'}).to_markdown(floatfmt='.2f')
ef=test[test.link.eq('N-Q-MNSP1')].copy()
d=ef.end.map(obs.terr)
ef['conditional_rhs_error']=-.001*((ef.prediction+d)**2-(ef.actual+d)**2)
ef.to_csv(P/'flow_only_rhs_effect.csv',index=False)
fe=ef.groupby(['product','method']).conditional_rhs_error.apply(lambda x:x.abs().mean())
assert (test[test['product']=='P5MIN'].pivot(index=['link','end'],columns='method',values='prediction').eval('`prior issued target`-`issued ramp`').abs()<1e-9).all()
regional=pd.read_csv(P/'regional_semantics.csv')
rw=regional[regional.phase=='test'].groupby('method').error.apply(lambda x:x.abs().mean())
bt=pd.read_csv(P/'binding_scores.csv').set_index(['product','method'])
s=bt.loc[('P5MIN','issued AEMO RHS')]; l=bt.loc[('PREDISPATCHIS','issued AEMO RHS')]
a=pd.read_csv(P/'injection_scenarios.csv')
sd=a[a.phase=='test'].scenario_delta
regional_case=pd.read_csv(P.parents[2]/'reports/rhs_replay/cases/regional_validation.csv',parse_dates=['interval_end'])
regional_case['end']=regional_case.interval_end.dt.tz_localize(None).astype(str)
rc=regional[regional.method.eq('three metered pumps')].merge(regional_case,on='end')
rc['R_bridge_error']=np.where(rc.region=='NSW1',rc.regional_nsw,rc.regional_qld)-rc.rebuilt_rhs_region
assert len(rc)==48
rc.to_csv(P/'regional_case_crosscheck.csv',index=False)
evidence=f"""### Signed interconnector flow

Inject the signed initial metered MW for the physical link specified in the expression. The comparison covers all six original links. Each cell is five-minute MAE in MW on the same 72 dispatch intervals. The short column uses P5MIN issued about 34–60 minutes before interval end. The day-ahead column uses predispatch issued the previous afternoon, roughly 18–20 hours ahead. The clock benchmark averages earlier observations in the matching half-hour and weekday/weekend group. Short and day-ahead forecasts have different origin readings.

{ft}

For the issued path, use the **previous delivery period's MWFLOW target from the same forecast run** to estimate initial flow at the next period's start. The day-ahead ramp linearly interpolates from that previous target toward the current half-hour target at each five-minute start. On the 12 exact half-hour starts, preceding PD target Directlink MAE was 56.64 MW versus 63.57 MW for carrying the origin reading. Within-block interpolation is a scenario. Both issued methods use forecast targets, not realized downstream flows. Public labels are the DISPATCHIS METEREDMWFLOW field with matching sign and nonintervention run.

Recommended starting points are link- and horizon-specific. Directlink persistence beat the short issued target here. Murraylink benefited from the day-ahead path; VNI's earlier clock profile beat both the issued path and persistence in both lead bands. These three evaluation mornings do not establish a general route. For the Directlink input of the nonlinear NSW–Queensland equation, substituting only the signed flow and holding realized Terranora load constant changed the RHS by {fe['P5MIN','persist']:.2f} MW MAE for short persistence vs {fe['P5MIN','prior issued target']:.2f} for the short issued path. Treat this attribution as a retrospective sensitivity diagnostic.

### Regional demand semantics and full NSW–Queensland RHS

The equations below estimate the dispatch RHS for N::Q_NIL_KC v1 effective 1 May 2023. Define N and Q as the equation-specific NSW and Queensland regional demand, d as Terranora load, and i as signed initial Directlink flow. The numerical program is `1383 − 0.001(i+d)² − 0.0239N + 0.0524Q − 0.6394d`. Every deployable estimate used only observations from before the forecast issue or data from the coherent forecast run. Scoring uses **native five-minute** dispatch RHS, including for hourly/half-hourly alternatives. PREDISPATCH values are held across their represented six deliveries unless a flow ramp is specified. Headline values can differ from earlier half-hour-average comparisons.

{rt}

The regional-only approach uses matched historical signed flow and the fixed seven-morning Terranora-to-NSW ratio. The anchored change method starts from the latest observed RHS and changes the regional totals and implied Terranora load while holding observed flow. The adjusted aggregate forecast uses the preceding issued dispatchable-load target (interpolated for PD), which includes loads outside the equation's eligible class. It gave a smaller day-ahead error here, although its physical definition is poor. The three-pump approach uses previously published MW for SHPUMP in NSW and PUMP1/PUMP2 in Queensland from Dispatch SCADA, held through delivery, added to the corresponding regional TOTALDEMAND.

In a **separate target-time diagnostic** using contemporaneous observations for all other terms, RHS MAE was {rw['plain region']:.2f} MW using public TOTALDEMAND, {rw['all dispatchable load']:.2f} after adding all dispatchable-load targets, and {rw['three metered pumps']:.2f} after adding just the three measured pumps. For the 19 February exact-case audit the latter reproduced the regional R components to within {rc.R_bridge_error.abs().max():.4f} MW. Its RHS residual reached 9.08 MW on 22 February. Other eligible loads, snapshot timing or formulation inputs require further investigation. Future pump operation must itself be forecast. Short horizon persistence of those readings reduced RHS error. At the previous-afternoon horizon it provided almost no improvement. Use dated trader classifications and pump or scheduled-load operating scenarios; retain aggregate-load addition only as an empirical challenger with error monitoring.

For a user's demand scenario, the export tests +100 MW of NSW regional demand relative to the issued base, with the earlier training-share response for Terranora, unchanged QLD demand and the matched issued signed flow. Applying the full dispatch formula difference to the published forecast RHS moved the RHS by {sd.min():.2f} to {sd.max():.2f} MW over the test rows. This is a conditional sensitivity on the dispatch formula, not a measured prediction or an exact emulation of the PD-scope program.

### Binding and uncertainty on the NSW–Queensland equation

Every evaluated case had the equation active in both the public forecast and the physical nonintervention dispatch. Seven of 72 actual intervals had nonzero absolute marginal value above 0.00001, in three episodes, all on 19 February. P5MIN's issued marginal values captured seven and produced 11 false alerts. The day-ahead forecast called none and missed all seven. Repeating its half-hour classification at five-minute resolution tests what a flat warning would do within the block. Detection of future invocation or unreported equations is outside these counts.

For a forward physical screen we used the forecast run's **issued LHS**, never the delivery's realized LHS as a predictor. For each method and lead we measured the absolute error of predicted signed RHS-minus-LHS headroom on two earlier calibration mornings (48 observations), then used its empirical 90th percentile (higher order statistic) as a symmetric band. The published RHS/LHS pair's short band was ±{s.band:.1f} MW and covered {int(s.band_covered)}/72 held-out headrooms. It marked {int(s.clear)} clear, {int(s.uncertain)} uncertain and 0 definitively at risk. All seven economic binds were uncertain. The day-ahead band ±{l.band:.1f} MW covered {int(l.band_covered)}/72; all seven economic binds were classified clear. These counts argue against a point-RHS binding alert. Run invocation and topology scenarios, preserve LHS uncertainty and collect more independent event days before choosing alert thresholds.

Training was frozen on mornings 9–15 February, calibration on 16–17 February and evaluation on 19, 20 and 22 February. The original forecast headers and nested-file modification times precede the delivery. The conservative carried-forward source's header and archive time precede forecast issue. Historical workstation receipt time is unavailable. [AEMO predispatch](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/pre-dispatch) · [Public DispatchIS](https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/) · [Public unit SCADA](https://www.nemweb.com.au/Reports/ARCHIVE/Dispatch_SCADA/)
"""
(P/'report.md').write_text(evidence,encoding='utf-8')
paths=[p for p in P.iterdir() if p.is_file() and p.name!='manifest.json']
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'files':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths},
'dependencies':{str(p.relative_to(P.parents[2])):sha(p) for p in [
 P.parents[2]/'local_exports/rhs_forward_feb26/study.py',P.parents[2]/'reports/rhs_replay/cases/regional_validation.csv']},
'rebuild':'python study.py --download; python load_bridge.py --download; python report.py (omit --download for cached execution)',
'train_days':[9,10,11,12,13,14,15],'calibration_days':[16,17],'test_days':[19,20,22],
'input_time':'Fixed NEM time UTC+10; interval ending','retained_bytes_excluding_manifest_and_python_cache':sum(p.stat().st_size for p in paths)}
(P/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(manifest['retained_bytes_excluding_manifest_and_python_cache'])
