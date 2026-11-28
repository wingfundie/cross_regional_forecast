### QNI and VNI dispatch and limit experiment

All times are fixed NEM time. The forecast origin is midnight 10, 21 or 42 calendar days before each delivery day. Four routine Wednesdays (4, 11, 18 and 25 February 2026) contribute 192 half-hours per connector and lead. A separate stress day per connector maximised the representative equation’s five-minute economic bind count among disjoint February dates: 8 February for QNI and 17 February for VNI. Dates selected on outcomes describe stress behaviour, not event prevalence. Four earlier November delivery days (23, 24, 26, 28) set error bands. Their November archive was created 8 December, before the first February test origin. Calibration and evaluation reuse correlated half-hours.

The QNI thermal case N>>NIL_85_86_S v1, effective 22 September 2025, includes Waratah protection headroom, registered plant power, ratings and status gates. Its link coefficient is −0.986. The VNI voltage case V^^N_NIL_1 v1, effective 31 October 2024, includes Portland load, reactive power, pump power and discrete equipment counts. Its coefficient is +1. Both are ≤ dispatch equations. Earlier QNI studies also established a separately replayable stability expression, N::Q_NIL_KC. We test it numerically with a distinct formula and archive target. The two main equations have usable exact-version records throughout the tested windows. Invocation is assumed for these snapshots. This selection does not test detection of other newly invoked equations.

**Direct route.** The seasonal baseline forecasts each reported signed directional limit as its median in pre-October 2025 history (from January 2024), at the same clock and weekend class within ±35 calendar days of its annual delivery date. The comparator uses the minimum of six native directional limits in each historical half-hour. Original pre-origin DispatchIS persistence carries the last sampled interval labelled five minutes before midnight, checking both creation and nested-file timestamp. Original reports were recovered for every routine and stress origin. Eleven earlier archive dates returned 404. For original-report persistence the 21- and 42-day calibration bands remain unavailable and the 10-day band uses one calibration day. The monthly archive persistence rule uses only the last completed archive whose original header predates origin and is a stale-feed fallback. Historical client receipt was not recorded.

**Equation route.** Seven complete training days (23–29 September 2025) supplied matched same-clock five-minute dispatch states. September’s archive was created 8 October, before the earliest forecast. Clock scenarios give all seven days equal weight. Issued-demand scenarios select the three nearest NSW and adjacent-region half-hour demands, scaled by their training standard deviations, using one original MT PASA weekly-energy vintage converted to half-hour demand by the feed study. Each retained analogue carries one coherent RHS, LHS, signed flow and competing-equation envelope. This estimates joint operating states of the two complex equations. It does not independently forecast all their meter readings, switching configurations or other units’ bids.

For link coefficient a, the candidate signed flow bound is F + (RHS − LHS)/a. Each native analogue intersects this bound with its reconstructed competing-equation envelope in the appropriate direction. The opposite direction uses that envelope alone. We take the minimum of the six export values and the minimum of the six negated signed lower bounds, then average paths. An additional empirical bridge applies the median training-period difference between each envelope and the corresponding reported directional limit. Its errors appear as adjusted export and adjusted import in the scorecard. The scenario calculation holds the analogue dispatch pattern fixed. Reported limits are dispatch-solution outputs and can differ substantially from a conditional physical envelope.

For QNI’s stability equation we also explicitly calculate 1383 − 0.001(i+d)Â² − 0.0239N + 0.0524Q − 0.6394d on each five-minute path. Here i is an analogue of signed initial Directlink MW and d is Terranora MW (verified monitor with the 10,000 MW offset removed). N and Q are regional-demand proxies. The issued route injects the forecast NSW and Queensland half-hour demands. The clock route uses matched historical regional demand. No future pumps are observed or added. Score differences include eligible-load definition errors and regional forecast errors.

### Reported limit and RHS error

Mean absolute error in MW. Reported directional limits use tight half-hour targets. RHS uses a six-interval mean; minimum signed headroom and native RHS/LHS paths are available separately. A blank cell denotes a quantity outside the route’s output.

| link   | method                       |   lead |   export |   import |   rhs |    kc |
|:-------|:-----------------------------|-------:|---------:|---------:|------:|------:|
| qni    | carry last published archive |     10 |    248.3 |    314.4 | 241   |  21.1 |
| qni    | carry last published archive |     21 |    237.4 |    311.9 | 245.8 |  22.2 |
| qni    | carry last published archive |     42 |    239.6 |    316   | 284.4 |  24   |
| qni    | clock equation               |     10 |    660.7 |    182.7 |  68.5 |  35.1 |
| qni    | clock equation               |     21 |    660.7 |    182.7 |  68.5 |  35.1 |
| qni    | clock equation               |     42 |    660.7 |    182.7 |  68.5 |  35.1 |
| qni    | issued demand                |     10 |    692.9 |    175.1 |  71.9 |  30.8 |
| qni    | issued demand                |     21 |    692.9 |    175.1 |  71.9 |  30.8 |
| qni    | issued demand                |     42 |    692.9 |    175.1 |  71.9 |  30.8 |
| qni    | last original DispatchIS     |     10 |    246.6 |    257.3 | 236.9 |  22.1 |
| qni    | last original DispatchIS     |     21 |    269.1 |    240.7 | 239.9 |  22.5 |
| qni    | last original DispatchIS     |     42 |    254.2 |    267   | 263.3 |  22   |
| qni    | seasonal direct              |     10 |    210.8 |    158.2 | nan   | nan   |
| qni    | seasonal direct              |     21 |    210.8 |    158.2 | nan   | nan   |
| qni    | seasonal direct              |     42 |    210.8 |    158.2 | nan   | nan   |
| vni    | carry last published archive |     10 |    600.9 |    274.2 |  49.3 | nan   |
| vni    | carry last published archive |     21 |    592   |    254.8 |  44.1 | nan   |
| vni    | carry last published archive |     42 |    631   |    254.4 |  50.5 | nan   |
| vni    | clock equation               |     10 |    407.8 |    280.5 |  52.4 | nan   |
| vni    | clock equation               |     21 |    407.8 |    280.5 |  52.4 | nan   |
| vni    | clock equation               |     42 |    407.8 |    280.5 |  52.4 | nan   |
| vni    | issued demand                |     10 |    457.3 |    343.8 |  71   | nan   |
| vni    | issued demand                |     21 |    457.3 |    343.8 |  71   | nan   |
| vni    | issued demand                |     42 |    457.3 |    343.8 |  71   | nan   |
| vni    | last original DispatchIS     |     10 |    580.4 |    416.7 |  64.4 | nan   |
| vni    | last original DispatchIS     |     21 |    647.5 |    513.6 |  82.6 | nan   |
| vni    | last original DispatchIS     |     42 |    578.9 |    344   |  60.7 | nan   |
| vni    | seasonal direct              |     10 |    210.6 |    194.1 | nan   | nan   |
| vni    | seasonal direct              |     21 |    210.6 |    194.1 | nan   | nan   |
| vni    | seasonal direct              |     42 |    210.6 |    194.1 | nan   | nan   |

### Probability screen and forecast bands

An analogue path casts a positive half-hour vote if its representative equation bound economically in at least one native interval, using absolute nonintervention marginal value above 0.00001. This is an empirical scenario frequency estimating future economic binding. It is distinct from a calculation of joint forecast physical headroom. Seven clock paths or three demand-matched paths yield coarse probability steps. Carry-forward probabilities are zero or one. A 25% cutoff is shown to expose the tradeoff. The evidence files also contain 10% and 50% cutoffs.

| link   | partition   | method                       |   n |   event_days |   positives |   tp |   fp |   fn |
|:-------|:------------|:-----------------------------|----:|-------------:|------------:|-----:|-----:|-----:|
| qni    | routine     | carry last published archive | 192 |            1 |           2 |    0 |    0 |    2 |
| qni    | stress      | carry last published archive |  48 |            1 |          18 |    0 |    0 |   18 |
| qni    | routine     | clock equation               | 192 |            1 |           2 |    2 |   54 |    0 |
| qni    | stress      | clock equation               |  48 |            1 |          18 |   14 |    0 |    4 |
| qni    | routine     | issued demand                | 192 |            1 |           2 |    2 |   43 |    0 |
| qni    | stress      | issued demand                |  48 |            1 |          18 |   13 |    0 |    5 |
| qni    | routine     | last original DispatchIS     | 192 |            1 |           2 |    0 |    0 |    2 |
| qni    | stress      | last original DispatchIS     |  48 |            1 |          18 |    0 |    0 |   18 |
| vni    | routine     | carry last published archive | 192 |            1 |          17 |    0 |    0 |   17 |
| vni    | stress      | carry last published archive |  48 |            1 |          12 |    0 |    0 |   12 |
| vni    | routine     | clock equation               | 192 |            1 |          17 |    0 |    0 |   17 |
| vni    | stress      | clock equation               |  48 |            1 |          12 |    0 |    0 |   12 |
| vni    | routine     | issued demand                | 192 |            1 |          17 |    0 |    5 |   17 |
| vni    | stress      | issued demand                |  48 |            1 |          12 |    0 |    1 |   12 |
| vni    | routine     | last original DispatchIS     | 192 |            1 |          17 |    0 |    0 |   17 |
| vni    | stress      | last original DispatchIS     |  48 |            1 |          12 |    0 |    0 |   12 |

The bands use the higher 90th percentile of absolute forecast errors from four calibration days, per method, target, connector and lead. Width is full MW width. A stable level is not sufficient for production calibration.

| link   | target   |   lead |   calibration_n |   width |   coverage |
|:-------|:---------|-------:|----------------:|--------:|-----------:|
| qni    | headroom |     21 |             192 |  2373.2 |        1   |
| qni    | export   |     21 |             192 |  6851.5 |        1   |
| qni    | import   |     21 |             192 |  1235.1 |        0.9 |
| vni    | headroom |     21 |             192 |  1830.7 |        0.9 |
| vni    | export   |     21 |             192 |  2339.3 |        1   |
| vni    | import   |     21 |             192 |  1598.5 |        0.9 |

### Network recommendation

At 21 days the direct seasonal reference beat both dated-origin persistence and the analogue envelope in all four routine directions. Issued demand reduced the explicit QNI stability error from 35.10 to 30.81 MW relative to the clock analogue, although original DispatchIS persistence scored 22.5 MW. The issued-demand event screen caught both routine QNI positives with 43 false calls, and missed all 17 routine VNI positives with five false calls. Routine events occurred on one of four days per link. The QNI and VNI headroom bands covered 97.9% and 90.6% of outcomes, but their full widths were 2,373 and 1,831 MW. Use the direct historical forecast and a dated origin reading as benchmarks for all four directions. Keep analogue-based dispatch outputs as conditional scenarios, particularly on directions where an empirical shift is needed to align an envelope with AEMO’s reported limit. For a high-value direct equation, investigate the inputs that move its bound jointly with dispatch before investing in a market-wide solver. The scope here includes no private offers, future observed dispatch or fitted out-of-sample interconnector targets as predictors. One month of delivery dates and two outcome-selected stress days cannot establish seasonal skill or a production alert threshold.

[Interval forecasts](predictions.csv) Â· [All errors, widths and coverage](scores.csv) Â· [Alert tradeoffs](alerts.csv) Â· [Native RHS/LHS forecasts](native_predictions.parquet) Â· [Dispatch archive lineage](archive_sources.json) Â· [Original origin reports](anchor_sources.json)
