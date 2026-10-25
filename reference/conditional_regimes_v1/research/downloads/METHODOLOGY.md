# Conditional interconnector regimes v1 — frozen initial protocol

Agreed 25 October 2026. This is conditional research on reported dispatch limits. The portable package is a new contract; neither original six-link weights nor QNI/VNI forecast bundles are reused as fitted models.

## Targets, time and structural compatibility

Native observations are five-minute interval-ending fixed NEM time (UTC+10). A complete half-hour contains six distinct observations. Average directional capacity is the mean; tight capacity is the minimum. Forward uses EXPORTLIMIT and reverse uses minus IMPORTLIMIT. Negative values are retained. Physical intervention runs take precedence; source metadata remain intact.

Calendar quarters are Jan–Mar, Apr–Jun, Jul–Sep and Oct–Dec. Half-hour 0 is the interval ending 00:00, half-hour 47 ends 23:30; use the interval-ending timestamp consistently. Historical coverage dates and display dates are distinct.

Compatibility is connector-specific: Basslink MNSP/regulated eras split 1 July 2026; VNI, V-SA and Murraylink pre/PEC-market eras split 1 October 2026. These are market-representation boundaries, not assumed physical commissioning dates. Actual additional circuit states are separate outage/configuration conditions. Mapping of post-change identifiers requires evidence; unsupported mappings remain unavailable.

## Condition contract

One panel row is connector × direction × complete half-hour. Numeric conditions are publicly measurable regional demand/VRE/residual demand, ramps, weather and eligibility-audited electrical generation groups. Targets, setters, reconstructed target envelopes and prices are excluded from distance/model features. Unknown inputs are never zero/normal. Regional TOTALDEMAND is already net of embedded rooftop PV.

Relevant outage families are identified using connector terms in standing equations available at the initial training boundary, not future leading frequency. Active family and asset fields require six covered invocation intervals; partial coverage is distinct. Booked records are not presumed invoked. Episode linkage is historical final-state research. Asset linkage requires an overlapping nonwithdrawn episode and family invocation. Unsupported security/FCAS/protection and storage-energy measurements remain unavailable in the public input catalogue.

Electrical groups are frozen from signed connection-point/interconnector factors and effective-dated DUID mappings eligible at the first training end, 1 September 2025. The standing archive contains change records rather than a complete initial snapshot, so 1 September 2024 alone is inadequate; this adjustment was made during inventory before fitting. Tiny IC coefficients (<0.07), FCAS terms and discretionary equations are excluded. Group membership is engineering input, not a target-selected ranking. Contemporaneous dispatch makes these conditional features; it does not establish future availability.

## Analogue methods and support

Layer A: empirical quarter × half-hour profiles and a bounded catalogue of single/joint conditions. Seasonal thresholds and condition cutoffs are fit only on eligible training rows during evaluation. Named regimes are explanatory overlays and may overlap.

Layer B: robust feature scaling, numerical similarity and circular half-hour distance. Match compatible era and specified network states first. Candidate half-hour radii {1,2}, neighbour days {30,60,90}. Numeric exact-value requests match within one training IQR; min/max requests match the stated range. Similarity uses Gaussian distance weights and equal total exposure per selected day. Outage episodes and dates are reported separately. The baseline uses all eligible quarter/half-hour observations.

Supported convention: at least 20 distinct exact-condition days; outage-specific requests additionally need at least 5 linked episodes. These are study conventions, not proof of calibrated tails. Broader references explicitly identify relaxed numeric/calendar conditions. A known contradictory era or requested outage is never discarded. Unknown structural configurations return unavailable. Frequency outputs are empirical conditional frequencies, not unconditional forecast probabilities.

Layer C: training-fitted imputation/scaling and regularised additive quantile regression versus shallow quantile LightGBM at P10/P50/P90. The additive model uses piecewise linear terms, L2 shrinkage and a smooth pinball approximation with epsilon 0.005 of the target IQR, fitted with convergence-checked L-BFGS. The initial exact linear programme proved unnecessarily slow in the timing pilot and was replaced before the complete comparison. Additive samples have at most 1,800 rows; boosting at most 6,000. Quantile crossing is repaired by sorting, never by clamping signed targets. A model is served only from a hash-verified trusted local artifact and explicit extrapolation opt-in. Requested components/features absent from a model cannot silently be ignored. Unseen structural eras are not extrapolated. Additional outage effects are learned jointly, never summed as independent deductions.

## Chronology, incidents and selection

Expanding folds: minimum 12 calendar months training, 8 weeks selection, 4 weeks calibration (the last 2 weeks separately reserved for alert tuning), then 4 weeks evaluation. Step 4 weeks. All target intervals must lie inside their split. Crossing outage episodes are purged from earlier partitions; publish eligibility attrition. Fit imputers, scales, cutoffs, feature selection and model choice before evaluation. Calibrate ranges only on calibration rows; tune restriction alerts on the separate alert rows. No final fitted model is scored on its training rows.

All 48 half-hours are eligible for evaluation. Every method is compared on identical available rows; report model availability failures separately. Conditional-known-state evaluation and as-of-eligible evaluation have separate scorecards. Historical receipt/publication proxies cannot satisfy measured-receipt eligibility. Event-informed feature development is retrospective development research and requires future confirmation for a forecasting claim.

Select radius/neighbour count on selection quantile loss. Added models must improve MAE and mean quantile loss, preserve calibration and not materially worsen P95 overstatement, restriction recall at matched false-alert rate, or forced-flow recall. Material degradation is >5% relative (or >2 percentage points for rates). Require a paired day-block bootstrap improvement interval excluding zero before serving a more complex default. Otherwise retain the analogue/baseline and publish tradeoffs. Lower samples do not bypass risk gates.

Report MAE, RMSE, bias, P95 absolute error/overstatement, P10/P50/P90 pinball loss, weighted interval score, 80% coverage/width, restriction/forced-event recall/precision, false alerts per exposure day and counts by quarter, delivery period, outage state and support. Restriction is <50% of the training-only quarter median of positive capacity; forced is <0. Stress examples retain dates and observed values without assigned occurrence probabilities. Bootstrap uses paired seven-day blocks (300 repeats).

## Execution and resource rules

Use the campaign ledger, exclusive PID/create-time lock and artifact hashes. Reconcile stale owners only when no healthy owner exists. Cached rendering is separate from estimation. Two workers maximum, two numerical threads per worker, 8 GB worker RSS, 48 hours modelling cap. Any incomplete required stage remains incomplete; missing public source dates are explicit gaps rather than fabricated history. No schedules are enabled and no production route changes.

## Completion

Requires six-link evidence, benchmark scorecards, three offline reports and Markdown companions, installable package and versioned bundle, local selector, fresh XLSX, four runbooks, full repository tests, package installation test, source/report hash and offline/link checks and desktop/mobile visual checks. If a source or prospective gate cannot pass, document the blocked capability without calling it verified.
