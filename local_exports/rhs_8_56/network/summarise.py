"""Combine as-of persistence with scenario forecasts and build the network scorecard."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from study import OUT,ROOT,score,MONTHS

d=pd.read_csv(OUT/'predictions.csv',parse_dates=['end','day','origin'])
d=d[d.method.ne('last original DispatchIS')]
d=d.drop(columns='anchor',errors='ignore')
if (OUT/'public_anchor.csv').exists():
    a=pd.read_csv(OUT/'public_anchor.csv',parse_dates=['origin','anchor'])
    keys=['link','origin']
    b=d[d.method.eq('carry last published archive')].drop(columns=['export','import','rhs','headroom','economic_frequency','kc'])
    b=b.merge(a,on=keys,how='inner',validate='many_to_one')
    assert b.anchor.lt(b.origin).all()
    b['method']='last original DispatchIS'
    d=pd.concat([d,b],ignore_index=True)
d.to_csv(OUT/'predictions.csv',index=False)
metrics,alerts=score(d)
metrics.to_csv(OUT/'scores.csv',index=False);alerts.to_csv(OUT/'alerts.csv',index=False)
assert not d.duplicated(['link','end','origin','method']).any()
assert d.query("method=='issued demand' and partition=='routine'").groupby(['link','lead']).size().eq(192).all()
n=pd.read_parquet(OUT/'native_predictions.parquet')
assert n.groupby(['link','origin','method',n.end.dt.ceil('30min')]).size().eq(6).all()
def exhibit(rows,columns):
    return rows[columns].round(1).to_markdown(index=False)

r=metrics.query("partition=='routine'").copy()
long=r.query("target in ['export','import','rhs','kc']").pivot_table(index=['link','method','lead'],columns='target',values='mae').reset_index()
at=alerts.query("lead==21 and cutoff==0.25")
band=r.query("method=='issued demand' and target in ['headroom','export','import'] and lead==21")
body=f"""### QNI and VNI dispatch and limit experiment

All times are fixed NEM time. The forecast origin is midnight 10, 21 or 42 calendar days before each delivery day. Four routine Wednesdays (4, 11, 18 and 25 February 2026) contribute 192 half-hours per connector and lead. A separate stress day per connector maximised the representative equationâ€™s five-minute economic bind count among disjoint February dates: 8 February for QNI and 17 February for VNI. Dates selected on outcomes describe stress behaviour, not event prevalence. Four earlier November delivery days (23, 24, 26, 28) set error bands. Their November archive was created 8 December, before the first February test origin. Calibration and evaluation reuse correlated half-hours.

The QNI thermal case N>>NIL_85_86_S v1, effective 22 September 2025, includes Waratah protection headroom, registered plant power, ratings and status gates. Its link coefficient is âˆ’0.986. The VNI voltage case V^^N_NIL_1 v1, effective 31 October 2024, includes Portland load, reactive power, pump power and discrete equipment counts. Its coefficient is +1. Both are â‰¤ dispatch equations. Earlier QNI studies also established a separately replayable stability expression, N::Q_NIL_KC. We test it numerically with a distinct formula and archive target. The two main equations have usable exact-version records throughout the tested windows. Invocation is assumed for these snapshots. This selection does not test detection of other newly invoked equations.

**Direct route.** The seasonal baseline forecasts each reported signed directional limit as its median in pre-October 2025 history (from January 2024), at the same clock and weekend class within Â±35 calendar days of its annual delivery date. The comparator uses the minimum of six native directional limits in each historical half-hour. Original pre-origin DispatchIS persistence carries the last sampled interval labelled five minutes before midnight, checking both creation and nested-file timestamp. Original reports were recovered for every routine and stress origin. Eleven earlier archive dates returned 404. For original-report persistence the 21- and 42-day calibration bands remain unavailable and the 10-day band uses one calibration day. The monthly archive persistence rule uses only the last completed archive whose original header predates origin and is a stale-feed fallback. Historical client receipt was not recorded.

**Equation route.** Seven complete training days (23â€“29 September 2025) supplied matched same-clock five-minute dispatch states. Septemberâ€™s archive was created 8 October, before the earliest forecast. Clock scenarios give all seven days equal weight. Issued-demand scenarios select the three nearest NSW and adjacent-region half-hour demands, scaled by their training standard deviations, using one original MT PASA weekly-energy vintage converted to half-hour demand by the feed study. Each retained analogue carries one coherent RHS, LHS, signed flow and competing-equation envelope. This estimates joint operating states of the two complex equations. It does not independently forecast all their meter readings, switching configurations or other unitsâ€™ bids.

For link coefficient a, the candidate signed flow bound is F + (RHS âˆ’ LHS)/a. Each native analogue intersects this bound with its reconstructed competing-equation envelope in the appropriate direction. The opposite direction uses that envelope alone. We take the minimum of the six export values and the minimum of the six negated signed lower bounds, then average paths. An additional empirical bridge applies the median training-period difference between each envelope and the corresponding reported directional limit. Its errors appear as adjusted export and adjusted import in the scorecard. The scenario calculation holds the analogue dispatch pattern fixed. Reported limits are dispatch-solution outputs and can differ substantially from a conditional physical envelope.

For QNIâ€™s stability equation we also explicitly calculate 1383 âˆ’ 0.001(i+d)Â² âˆ’ 0.0239N + 0.0524Q âˆ’ 0.6394d on each five-minute path. Here i is an analogue of signed initial Directlink MW and d is Terranora MW (verified monitor with the 10,000 MW offset removed). N and Q are regional-demand proxies. The issued route injects the forecast NSW and Queensland half-hour demands. The clock route uses matched historical regional demand. No future pumps are observed or added. Score differences include eligible-load definition errors and regional forecast errors.

### Reported limit and RHS error

Mean absolute error in MW. Reported directional limits use tight half-hour targets. RHS uses a six-interval mean; minimum signed headroom and native RHS/LHS paths are available separately. A blank cell denotes a quantity outside the routeâ€™s output.

{exhibit(long,['link','method','lead','export','import','rhs','kc'])}

### Probability screen and forecast bands

An analogue path casts a positive half-hour vote if its representative equation bound economically in at least one native interval, using absolute nonintervention marginal value above 0.00001. This is an empirical scenario frequency estimating future economic binding. It is distinct from a calculation of joint forecast physical headroom. Seven clock paths or three demand-matched paths yield coarse probability steps. Carry-forward probabilities are zero or one. A 25% cutoff is shown to expose the tradeoff. The evidence files also contain 10% and 50% cutoffs.

{exhibit(at,['link','partition','method','n','event_days','positives','tp','fp','fn'])}

The bands use the higher 90th percentile of absolute forecast errors from four calibration days, per method, target, connector and lead. Width is full MW width. A stable level is not sufficient for production calibration.

{exhibit(band,['link','target','lead','calibration_n','width','coverage'])}

### Network recommendation

At 21 days the direct seasonal reference beat both dated-origin persistence and the analogue envelope in all four routine directions. Issued demand reduced the explicit QNI stability error from 35.10 to 30.81 MW relative to the clock analogue, although original DispatchIS persistence scored 22.5 MW. The issued-demand event screen caught both routine QNI positives with 43 false calls, and missed all 17 routine VNI positives with five false calls. Routine events occurred on one of four days per link. The QNI and VNI headroom bands covered 97.9% and 90.6% of outcomes, but their full widths were 2,373 and 1,831 MW. Use the direct historical forecast and a dated origin reading as benchmarks for all four directions. Keep analogue-based dispatch outputs as conditional scenarios, particularly on directions where an empirical shift is needed to align an envelope with AEMOâ€™s reported limit. For a high-value direct equation, investigate the inputs that move its bound jointly with dispatch before investing in a market-wide solver. The scope here includes no private offers, future observed dispatch or fitted out-of-sample interconnector targets as predictors. One month of delivery dates and two outcome-selected stress days cannot establish seasonal skill or a production alert threshold.

[Interval forecasts](predictions.csv) Â· [All errors, widths and coverage](scores.csv) Â· [Alert tradeoffs](alerts.csv) Â· [Native RHS/LHS forecasts](native_predictions.parquet) Â· [Dispatch archive lineage](archive_sources.json) Â· [Original origin reports](anchor_sources.json)
"""
(OUT/'report.md').write_text(body,encoding='utf8')
files=[ROOT/'data/processed/ic_5min.parquet',ROOT/'data/processed/regional_30min.parquet',OUT.parent/'feeds/regional_forecasts.csv']
for tag in ('qni','vni'):
    files.extend(ROOT/f'data/constraint_{tag}_2y/months'/m/'constraint_features_5min.parquet' for m in MONTHS)
log=[]
for f in files:
    with f.open('rb') as stream:log.append(dict(path=str(f.relative_to(ROOT)),bytes=f.stat().st_size,sha256=hashlib.file_digest(stream,'sha256').hexdigest()))
(OUT/'supplement_sources.json').write_text(json.dumps(log,indent=2))
print(long.query('lead==21').round(1).to_string(index=False))
