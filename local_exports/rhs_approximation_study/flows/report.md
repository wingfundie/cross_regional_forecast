### Signed interconnector flow

Inject the signed initial metered MW for the physical link specified in the expression. The comparison covers all six original links. Each cell is five-minute MAE in MW on the same 72 dispatch intervals. The short column uses P5MIN issued about 34–60 minutes before interval end. The day-ahead column uses predispatch issued the previous afternoon, roughly 18–20 hours ahead. The clock benchmark averages earlier observations in the matching half-hour and weekday/weekend group. Short and day-ahead forecasts have different origin readings.

| Signed link   |   Short carry |   Short clock |   Short issued |   Day carry |   Day clock |   Day prior target |   Day ramp |
|:--------------|--------------:|--------------:|---------------:|------------:|------------:|-------------------:|-----------:|
| N-Q-MNSP1     |          13.9 |          41.9 |           23.7 |        63.8 |        41.9 |               57.2 |       58.0 |
| NSW1-QLD1     |         149.4 |         642.1 |          202.9 |       245.5 |       642.1 |              413.0 |      414.1 |
| T-V-MNSP1     |          35.9 |          86.8 |           34.7 |        48.3 |        86.8 |               61.2 |       59.7 |
| V-S-MNSP1     |          14.4 |          17.2 |           22.7 |        25.1 |        17.2 |                7.9 |        7.4 |
| V-SA          |          70.6 |         222.4 |          189.4 |       198.9 |       222.4 |              228.4 |      226.9 |
| VIC1-NSW1     |         118.5 |         101.1 |          244.6 |       146.4 |       101.1 |              380.8 |      386.4 |

For the issued path, use the **previous delivery period's MWFLOW target from the same forecast run** to estimate initial flow at the next period's start. The day-ahead ramp linearly interpolates from that previous target toward the current half-hour target at each five-minute start. On the 12 exact half-hour starts, preceding PD target Directlink MAE was 56.64 MW versus 63.57 MW for carrying the origin reading. Within-block interpolation is a scenario. Both issued methods use forecast targets, not realized downstream flows. Public labels are the DISPATCHIS METEREDMWFLOW field with matching sign and nonintervention run.

Recommended starting points are link- and horizon-specific. Directlink persistence beat the short issued target here. Murraylink benefited from the day-ahead path; VNI's earlier clock profile beat both the issued path and persistence in both lead bands. These three evaluation mornings do not establish a general route. For the Directlink input of the nonlinear NSW–Queensland equation, substituting only the signed flow and holding realized Terranora load constant changed the RHS by 1.12 MW MAE for short persistence vs 1.75 for the short issued path. Treat this attribution as a retrospective sensitivity diagnostic.

### Regional demand semantics and full NSW–Queensland RHS

The equations below estimate the dispatch RHS for N::Q_NIL_KC v1 effective 1 May 2023. Define N and Q as the equation-specific NSW and Queensland regional demand, d as Terranora load, and i as signed initial Directlink flow. The numerical program is `1383 − 0.001(i+d)² − 0.0239N + 0.0524Q − 0.6394d`. Every deployable estimate used only observations from before the forecast issue or data from the coherent forecast run. Scoring uses **native five-minute** dispatch RHS, including for hourly/half-hourly alternatives. PREDISPATCH values are held across their represented six deliveries unless a flow ramp is specified. Headline values can differ from earlier half-hour-average comparisons.

| method                                                                      |   Short MAE |   Day-ahead MAE |
|:----------------------------------------------------------------------------|------------:|----------------:|
| RHS persistence                                                             |       12.21 |           15.79 |
| clock RHS profile                                                           |       27.54 |           27.54 |
| issued AEMO RHS                                                             |       27.92 |           36.48 |
| Issued flow and local load + total demand plus three prior pump readings    |       11.44 |           36.50 |
| Issued flow and local load + total demand only                              |       27.92 |           36.50 |
| Issued flow and local load + total demand plus all issued dispatchable load |       19.06 |           12.06 |
| regional forecast change from observed RHS                                  |       10.95 |           51.23 |
| regional forecast with clock flow and fixed load share                      |       34.67 |           53.90 |

The regional-only approach uses matched historical signed flow and the fixed seven-morning Terranora-to-NSW ratio. The anchored change method starts from the latest observed RHS and changes the regional totals and implied Terranora load while holding observed flow. The adjusted aggregate forecast uses the preceding issued dispatchable-load target (interpolated for PD), which includes loads outside the equation's eligible class. It gave a smaller day-ahead error here, although its physical definition is poor. The three-pump approach uses previously published MW for SHPUMP in NSW and PUMP1/PUMP2 in Queensland from Dispatch SCADA, held through delivery, added to the corresponding regional TOTALDEMAND.

In a **separate target-time diagnostic** using contemporaneous observations for all other terms, RHS MAE was 22.18 MW using public TOTALDEMAND, 23.19 after adding all dispatchable-load targets, and 2.12 after adding just the three measured pumps. For the 19 February exact-case audit the latter reproduced the regional R components to within 0.0049 MW. Its RHS residual reached 9.08 MW on 22 February. Other eligible loads, snapshot timing or formulation inputs require further investigation. Future pump operation must itself be forecast. Short horizon persistence of those readings reduced RHS error. At the previous-afternoon horizon it provided almost no improvement. Use dated trader classifications and pump or scheduled-load operating scenarios; retain aggregate-load addition only as an empirical challenger with error monitoring.

For a user's demand scenario, the export tests +100 MW of NSW regional demand relative to the issued base, with the earlier training-share response for Terranora, unchanged QLD demand and the matched issued signed flow. Applying the full dispatch formula difference to the published forecast RHS moved the RHS by -2.61 to -2.53 MW over the test rows. This is a conditional sensitivity on the dispatch formula, not a measured prediction or an exact emulation of the PD-scope program.

### Binding and uncertainty on the NSW–Queensland equation

Every evaluated case had the equation active in both the public forecast and the physical nonintervention dispatch. Seven of 72 actual intervals had nonzero absolute marginal value above 0.00001, in three episodes, all on 19 February. P5MIN's issued marginal values captured seven and produced 11 false alerts. The day-ahead forecast called none and missed all seven. Repeating its half-hour classification at five-minute resolution tests what a flat warning would do within the block. Detection of future invocation or unreported equations is outside these counts.

For a forward physical screen we used the forecast run's **issued LHS**, never the delivery's realized LHS as a predictor. For each method and lead we measured the absolute error of predicted signed RHS-minus-LHS headroom on two earlier calibration mornings (48 observations), then used its empirical 90th percentile (higher order statistic) as a symmetric band. The published RHS/LHS pair's short band was ±260.3 MW and covered 54/72 held-out headrooms. It marked 47 clear, 25 uncertain and 0 definitively at risk. All seven economic binds were uncertain. The day-ahead band ±697.6 MW covered 39/72; all seven economic binds were classified clear. These counts argue against a point-RHS binding alert. Run invocation and topology scenarios, preserve LHS uncertainty and collect more independent event days before choosing alert thresholds.

Training was frozen on mornings 9–15 February, calibration on 16–17 February and evaluation on 19, 20 and 22 February. The original forecast headers and nested-file modification times precede the delivery. The conservative carried-forward source's header and archive time precede forecast issue. Historical workstation receipt time is unavailable. [AEMO predispatch](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/pre-dispatch) · [Public DispatchIS](https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/) · [Public unit SCADA](https://www.nemweb.com.au/Reports/ARCHIVE/Dispatch_SCADA/)
