# Refining VNI and QNI forecasts with diurnal structure and network outages

## 1. Research conclusion

Time-of-day specialization and Network Outage Scheduler (NOS) information deserve a controlled experiment. The recommended starting point is a shared, regularized persistence-correction model whose coefficients vary smoothly with delivery time, followed by the addition of scheduled outage exposure and constraint-family features. Separate period models should remain explicit challengers. Their extra flexibility needs to outperform both shared models and a validation-selected persistence fallback.

The objectives are **directional-limit forecast accuracy** and **advance warning of contractions**. These require separate selections and scorecards. A lower mean absolute error (MAE) does not establish better incident recall, and a useful warning model need not produce the best point forecasts. Flow remains a secondary compatibility check.

The strongest new data finding is that public NEMWEB network archives contain successive intraday outage snapshots. This supports an as-of-schedule experiment over the available archive period. It does not establish complete two-year coverage or actual historical receipt times. Monthly MMSDM outage extracts remain useful for reconstruction, but cannot be assumed to preserve the information available at each historical issue time.

No new forecasting model has been trained for this report. The numerical results below reproduce saved development forecasts. Model improvements described later are hypotheses and proposed acceptance criteria, not measured gains. The complete engineering specification is in [the implementation plan](QNI_VNI_DIURNAL_NOS_IMPLEMENTATION_PLAN.md).

## 2. What the current repository actually supports

The relevant baseline is the completed `nemic.experiments` VNI/QNI campaign, rather than the older six-interconnector conditional LightGBM experiment. It has 130 main jobs, comprising 104 numeric and 26 event jobs, plus pooled linear comparisons. The historical development interval is September 2024–August 2026. Twelve expanding monthly evaluation folds and one fixed split are retained. The fixed and rolling evaluations overlap and must not be added together as independent evidence. [L1]

The numeric framework issues forecasts every 30 minutes. Four horizon bands cover 0.5–6 hours, 6.5–24 hours, 24.5–72 hours and 72.5–168 hours. Fourteen representative leads are scored, rather than all 336 leads at every origin. Targets are half-hour mean flow, mean export/import directional limits, and minimum five-minute export/import directional limits **within the delivery half-hour**. These minimum targets are not the minimum limit over the entire interval from issue to delivery. [L2]

The current feature builder already uses delivery-hour sine/cosine, annual sine/cosine, weekend and lead features. It includes lagged targets, limit changes, reconstructed network headroom, setter competition, generator tightening/relief and lagged regional context. Ridge, elastic net, additive terms, headroom regimes, shallow boosting, quantiles and blends have already been tested. Persistence can already win the overall target/band selection; the proposed addition is a more carefully regularized *period-dependent* fallback. [L2]

Four implementation findings affect the new experiment:

| Finding | Consequence |
|---|---|
| Ridge calendar terms are additive; the existing regime model gates on standardized headroom | Test explicit time-varying network/pressure coefficients, not merely another hour column |
| Aggregate-pressure forecasts use one representative lead per horizon band | Test lead-conditioned pressure forecasts independently, to avoid mistaking a horizon correction for a diurnal improvement |
| Event features use the calendar at issue +120 minutes | Represent the entire 30–120-minute warning window when testing time-of-day effects |
| Promotion settings still prioritize flow MAE | Add explicit directional-limit and contraction-risk selection gates |

The shadow recorder also uses raw `IMPORTLIMIT`, whereas prepared directional-import targets use `-IMPORTLIMIT`. This is a concrete sign mismatch in the inspected code. Correct it before prospective comparisons, with regression cases for ordinary and forced-direction conditions. Negative directional limits must remain negative; clipping them to zero would erase meaningful outcomes. [L2, L3]

## 3. Reproduced time-of-day evidence

The saved rolling predictions reproduce the earlier analysis. The table uses delivery **interval-ending timestamps**, fixed NEM-time buckets, and the five scored leads in the first band: 0.5, 1, 2, 4 and 6 hours. Values are MAE in MW; each cell is **selected model / persistence**. [L4]

| Delivery period | VNI export minimum | VNI import minimum | QNI export minimum | QNI import minimum |
|---|---:|---:|---:|---:|
| 00:00–06:00 | 111.43 / 152.08 | 121.34 / 155.99 | 75.94 / 83.70 | 69.63 / 61.07 |
| 06:00–10:00 | 255.91 / 389.09 | 212.83 / 246.64 | 121.66 / 126.20 | 145.05 / 171.01 |
| 10:00–16:00 | 262.90 / 330.31 | 199.27 / 235.39 | 117.27 / 117.88 | 139.69 / 161.84 |
| 16:00–21:00 | 275.02 / 454.11 | 253.24 / 296.07 | 150.84 / 188.80 | 183.08 / 192.75 |
| 21:00–24:00 | 164.86 / 353.90 | 175.71 / 249.24 | 101.51 / 115.73 | 110.65 / 109.80 |

There are respectively 21,576, 14,600, 21,900, 18,250 and 10,950 origin/lead observations per connector/target in these buckets. These are repeated forecasts, not that many independent days or incidents. The machine-readable reproduction, including source hashes, accompanies this report. [L4]

Reproduce these results with `python scripts/reproduce_diurnal_nos_evidence.py`. The script reads 48 retained prediction files, rejects duplicate forecast keys or unmatched observations, and writes the 20 period cells with input and extractor hashes. It does not retrain or select a model.

Three comparisons justify specific hypotheses:

* QNI overnight minimum-import MAE is about 14% worse than persistence. A period-dependent fallback has a concrete opportunity to recover lost skill.
* QNI solar-period minimum-export improvement is only about 0.5%. Additional specialization must demonstrate value beyond an already competitive persistence baseline.
* VNI evening minimum-export MAE improves by about 39% against persistence despite its high absolute error. Evening forecasts already add substantial value; a blanket move to persistence would discard it.

Higher daytime MAE alone does not establish that separate daytime models will work. It may reflect higher target variability, more setter switching, or different outage exposure. The research should first distinguish time-varying mean limits, time-varying sensitivity to drivers, and time-varying uncertainty. These are three different modelling problems.

## 4. What the literature supports

Soares and Medeiros build separate hourly electricity-load models, with deterministic calendar structure and autoregressive dynamics. Their Brazilian load results provide precedent for hour-specific relationships. They do not demonstrate that independent hourly models improve Australian interconnector-limit predictions. Electricity load and directional transfer limits have different mechanisms. [^1]

Montero-Manso and Hyndman show why global forecasting methods can be competitive even across heterogeneous series, and why local-model complexity increases as the number of series increases. This supports testing partial sharing before multiplying small models across connector, direction, horizon, period and season. It does not imply that a single pooled linear model must win here. [^2]

Hyndman and Athanasopoulos describe Fourier regression as a compact way to represent long and multiple seasonal periods, with the number of harmonics controlling smoothness. The useful extension here is to interact a small cyclic basis with network conditions. Fourier terms alone describe a daily shape; interactions allow the *response to network conditions* to change throughout the day. [^3]

Rolling-origin validation ensures that prediction uses earlier observations and supports evaluation at the intended multi-step horizons. The repository already follows this broad structure. The new work must extend its time discipline to outage revisions, source publication, calibration and all derived features. [^4]

Time-series conformal research supports investigating adaptive uncertainty calibration under dependence and distribution changes. Multi-step work explicitly addresses delayed outcome feedback. Such results do not provide automatic conditional coverage guarantees for every outage family or time bucket. For this project, measured coverage, interval width and matured-feedback discipline are more useful acceptance criteria than a blanket guarantee. [^5][^6]

The literature therefore supports a model ladder: shared seasonal model; shared time-varying coefficients; partial period correction; independent period models; nonlinear challenger. It provides no defensible basis for promising a particular MW improvement in advance.

## 5. Why NOS could help

AEMO describes NOS as covering planned and unplanned transmission-network outages, including protection and control work. Its process includes reassessment as conditions change, so a published booking is not a guarantee that an outage will proceed as scheduled. NOS is not the source for generating-unit outages. Unit availability requires a separate forecast-vintage data stream. [^7]

Constraint equations represent limitations for particular network configurations. AEMO's explanation distinguishes system-normal and outage configurations and notes that the constraint RHS is not generally the interconnector limit itself. That supports using outage information to anticipate a change in relevant equations, rather than assigning every outage a fixed MW derating. [^8]

The schema explicitly links outage IDs to constraint sets **expected** to be invoked. This is a forward-looking bridge:

`outage snapshot → expected constraint set → versioned member equations → connector/direction exposure`

The bridge is a feature representation, not a complete power-flow model or a verified future dispatch solution. [^9]

### 5.1 Public-source feasibility audit

The current network sample inspected was `PUBLIC_NETWORK_20260914233030_0000000537882802.zip`. It contained 12,277 `NETWORK,OUTAGEDETAIL,4` rows and 1,038 `NETWORK,OUTAGECONSTRAINTSET,1` rows. The outage header includes `ELEMENTID`, in addition to the familiar identifiers, schedule, status, resubmission, recall and actual-time fields. The older HTML schema omits that newer field, so the parser must use each file's own header. These are sample counts, not a complete population audit. [^10][^11]

The archive listing exposed 54 bundles, from `PUBLIC_NETWORK_20250822.zip` through `PUBLIC_NETWORK_20260828.zip`. The first inspected bundle was approximately 84.8 MB and held 350 inner ZIPs, with filenames spanning 22–29 August 2025. The first inner report contained 10,641 outage-detail rows and 702 outage-set links. This establishes snapshot retention in that sampled bundle; continuity, duplicates and missing intervals still require inventory across all bundles. [^12]

The September 2024 monthly outage-detail extract contained 781,144 rows, 397,223 distinct outage IDs and 8,713 repeated composite primary keys. Its maximum `LASTCHANGED` was **8 October 2024**. Multiple versions exist, but the monthly filename is plainly insufficient to reconstruct knowledge within September. Neither `SUBMITTEDDATE` nor a later row's `LASTCHANGED` proves the first public availability of every field or link. [^13]

The sampled status dictionary includes submitted, likely-to-proceed timeframes, permission-to-proceed/restore, complete, withdrawn and resubmitted states. Treat these as categories, with explicit unknown handling. Do not impose an arbitrary numerical ranking such as “complete = highest outage severity.” [^14]

AEMO's explanatory pages differ in how they describe the longer-term 13-month schedule and spreadsheet arrangements. This plan uses the inspected machine-readable NOS reports as its primary source and does not assume identical coverage across TNSPs or a guaranteed 13-month constraint-mapping horizon. [^7][^15]

### 5.2 Most promising feature families

| Feature family | Proposed construction | Predictive hypothesis |
|---|---|---|
| Scheduled exposure | Distinct relevant bookings and asset count; overlap with each delivery half-hour | Anticipates a topology condition not visible in current limits |
| Transition proximity | Time to expected start/end; starts/ends within issue-to-delivery and warning windows | Helps forecast contractions and recoveries around transitions |
| Constraint-family exposure | Counts of expected mapped upper/lower candidates, thermal/stability families, and newly introduced families | Distinguishes potentially important outages from unrelated maintenance |
| Revision information | Start/end shifts, status changes, booking age and resubmission chains known at issue | Captures unstable schedules and forecast uncertainty |
| Concurrent outages | Relevant asset/set co-occurrence and shared-family exposure | Tests interactions that a raw outage count misses |
| Outage × operating state | Scheduled exposure multiplied by headroom, setter gaps, generator pressure and time basis | Tests whether the same outage matters differently at different operating points |
| Data quality | Snapshot age, unmapped share, absent status and ambiguous linkage | Prevents unknown network state from being interpreted as no outage |

An especially useful distinction is **already active** versus **new before delivery**. An active outage may already be reflected in current limits and reconstructed state. A scheduled future transition can add information those features cannot contain. Separate ablations should quantify these contributions.

The most valuable question is not “Does an outage flag improve MAE?” It is whether delivery-specific exposure, revision information and mapped constraint families improve prediction beyond lagged limits and current network state on the same observations.

### 5.3 Features requiring stronger controls

Before NOS-aware model fitting, run the implementation plan's §3.6 outage-impact analysis. Build distinct booking-chain episodes and map asset → expected set → versioned equation family, keeping scheduled exposure, observed invocation and actual limit-setter evidence separate. Compare directional limit changes with matched unexposed windows controlling for pre-transition operating state, calendar and overlapping outages. Report adjusted associations with episode/block uncertainty and pre-trend/placebo diagnostics, not causal deratings inferred from raw low limits.

Identify “usually highest impact” assets/sets using supported median episode-level MW reductions, and publish separate tail-severity and cumulative-capability-reduction rankings. Require at least ten usable recurring episodes across three months and credible matched support for the recurring shortlist; rare severe cases and poorly identified concurrent outages remain separate. The analysis must precede NOS HPO and deliver an episode ledger, ranked effect tables, event-time charts and a versioned feature proposal. Outcome-derived impact weights form a separate O5 challenger, fitted chronologically within training splits, never from full-history ranks. No particular outage has yet been established as highest-impact by this planned analysis.

Secondary-equipment work must be kept separate from primary transmission-equipment outages. The older schema explicitly says that the associated transmission equipment can remain in service. Day and night recall times also exist, but the schema does not define those clock boundaries; retain both fields rather than inventing a mapping from the five modelling periods. [^11]

`ACTUAL_STARTTIME` and `ACTUAL_ENDTIME` may be used only when present in a snapshot available by issue time. Final actual dates cannot be backfilled into earlier forecasts. A scheduled end that has passed without an observed restoration should generate an uncertain/overdue state, not an automatic assertion that capacity has recovered.

Resubmissions can receive new outage IDs. Use explicit chains to avoid double-counting an old and replacement booking; never merge unrelated outages solely because their descriptions look similar. Cancelled or withdrawn bookings remain useful historical information but must cease contributing to scheduled active exposure according to their as-of state.

Direction should come from versioned equation algebra and inequality orientation, rather than equipment names or the sign of one coefficient in isolation. Multiple affected generators and other LHS/RHS terms can offset one another. An outage-conditioned candidate score is not a fixed physical derating.

## 6. Experiments that answer the question cleanly

The central design is a controlled comparison across two axes: daily specialization and outage information. Each experiment retains connector, direction, target, horizon, folds, information track and evaluation population.

| Comparison | What it establishes |
|---|---|
| Existing recipe vs richer additive cyclic calendar | Whether the average daily shape is underfit |
| Rich cyclic calendar vs cyclic driver interactions | Whether sensitivities vary with delivery time |
| Shared interactions vs period corrections vs independent period models | Whether splitting the data earns its extra complexity |
| No NOS vs active-only NOS vs delivery-scheduled NOS | Whether advance schedules add more than contemporaneous state |
| Scheduled NOS vs mapped families vs revision features | Which outage representation contributes useful information |
| Calendar + NOS additions vs explicit calendar × NOS interactions | Whether outage effects vary by period |
| Original band-representative pressure vs lead-conditioned pressure | Whether horizon alignment explains part of the gain |

The five original buckets remain fixed for reporting and the initial specialist challenger. Do not optimize their boundaries against already inspected errors. Use smooth cyclic coefficients as the primary way to avoid artificial switches. Fully independent 24-hour or 48-half-hour models would subdivide the data further without evidence that the five-period experiment works; defer them.

A shared shape across connectors is also worth testing, with connector-specific deviations and training-only target scaling. Sharing calendar response does not require sharing all outage coefficients. Keep a connector-local baseline and inspect whether pooling helps one connector by harming the other.

Calendar period routing must use delivery time. For the event classifier, however, the target is an onset anywhere in 30–120 minutes, so use features representing that whole window. Routing the classifier using the *actual future onset time* would leak the outcome.

## 7. Evaluation and interpretation

For numeric accuracy display **MAPE, |actual| ≥50 MW**, then **MAE (MW)**, followed by RMSE, bias, P95 absolute error and improvement against both persistence and the corrected incumbent. The headline percentage metric is conditional: `100 × mean(abs(prediction−actual)/abs(actual))` on a shared actual-based eligibility mask. Show eligible counts/coverage, 25/100 MW threshold sensitivities and separate near-zero/zero MAE and overstatement scores. Ordinary nonzero MAPE uses an absolute denominator, including negative limits; full-population ordinary MAPE is undefined if zeros occur. Never replace zeros with epsilon or omit them from MW/risk metrics. Primary point-model optimization, selection and promotion minimize MAE in MW on all target-eligible observations. MAPE is assessment-only and never changes the fitting population or chooses a model. Promotion requires at least 5% MAE improvement over the corrected incumbent, improvement over persistence and the declared risk/statistical gates. These are the same rules as implementation-plan §6.1, not a change to the historical MAE measurements above.

Test a bounded directional-reference percentage-error challenger, DR-NMAE: weighted mean absolute MW error divided observation-by-observation by a positive directional capacity reference known at issue time, multiplied by 100. A constant denominator within a separately fitted direction merely rescales MAE, so assess it without redundant HPO. The nontrivial challenger uses the latest admissible observed directional-limit magnitude, floored by its inner-training positive-magnitude 10th percentile, with a frozen training-median fallback for missing/stale references. Store provenance and test denominator/weight stability; never divide by future realised limits or model predictions. Compare against matched MAE-tuned models, retain MAE-based main-policy selection, and report relative-error gains separately. The implementation plan §6.1 specifies objective mathematics, training-loss versus tuning-loss distinctions, sensitivity diagnostics and leakage tests.

For directional capacities, overstatement means `prediction − actual > threshold`, for both directions after sign normalization. Report rates above 100 and 200 MW, mean positive overstatement and contraction-window error. AEMO reports calculated directional limits separately from realised flow: flow not reaching a limit does not make that label invalid. Binding status may explain a performance slice but must not filter valid limit targets. [AEMO dispatch interconnector fields](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_127.htm).

For contraction risk retain the existing 30-minute-drop detector, training-fitted monthly percentile thresholds, incident grouping and 30–120-minute warning window. Preserve fixed 100/200/400 MW event definitions as additional severity scorecards. Report Brier score, log loss, precision–recall performance, incident recall, false alarms per day and warning lead times. These outcomes must not be replaced by the much easier question of whether a limit is low.

The configured false-alarm budget is three per day **across both directions of one connector**. Specialization must not give each period its own budget. Report the combined two-connector burden too; the existing configuration could allow six per day across VNI and QNI. Exposure denominators and outage-related missingness must be explicit. [L2]

Use paired calendar-week blocks for numeric uncertainty and paired chronological blocks retaining whole incident matches for risk comparisons. Origin/lead rows are correlated, and one outage can affect both directions and both connectors. Report distinct days, incidents and outage episodes, not just row counts. The confidence interval should compare candidates directly, rather than compare two unrelated confidence intervals.

All September 2024–August 2026 outcomes are development evidence because they have already informed modelling choices. Newly frozen, prospectively issued forecasts are required for confirmation. NOS archive coverage is shorter still: a fair NOS comparison must refit the no-NOS control over the same available history rather than award one model more training data. A retrospective improvement and a deployable improvement are separate claims.

Before historical NOS HPO, require at least four eligible monthly folds, 90 covered training days per fold and at least 80% admissible fresh-snapshot coverage in every partition and across candidate evaluation months; otherwise route the performance question to prospective data. A historical risk cell needs at least 30 eligible distinct incidents, plus an explicit dependence-aware power assessment for the +10 percentage-point recall target at the joint three-false-alarms/day budget. The count floor alone is not sufficient power; below 80% simulated power under plausible documented assumptions, classify historical risk findings as exploratory. Exact definitions and the simulation protocol are in implementation-plan §4.3. Even passing these gates cannot turn previously inspected history into confirmation.

The new saved-policy audit finds 694/402 eligible VNI export/import onset timestamps and 527/1,219 QNI onset timestamps over March–August 2026, before NOS coverage filtering. Counts do not establish independent outage-episode support. Combined directional false-alarm rates over 183.5 issue-exposure days are 3.27/day for VNI and 3.55/day for QNI: these saved evaluation policies did not meet the three/day budget over this cohort. No evaluation thresholds were retuned. Reproduce monthly counts and source hashes with `scripts/audit_nos_incident_support.py`. Final matched NOS counts and v2 eligibility remain unmeasured.

Compare the selection-frozen primary policy against both controls with Holm correction jointly across eight numeric hypotheses (four connector/direction cells × two controls); use a separate two-connector risk family. If retaining a broad exploratory leaderboard, report a 90% Model Confidence Set per cell on matched daily losses with dependence-block sensitivity. This complements the restricted shortlist; it does not correct data reuse or replace prospective confirmation. [Hansen, Lunde and Nason (2011)](https://doi.org/10.3982/ECTA5771).

## 8. Recommended implementation order

First establish a reproducible baseline and correct sign, timestamp and label-maturity inconsistencies. Then run the calendar-only ladder, which does not depend on NOS recovery. In parallel engineering work, build the immutable NOS snapshot store and mapping audit. Combine only the best preselected calendar candidates with the compact outage blocks, rather than launching an unrestricted Cartesian product of every model and feature.

Implementation-plan §4.4 now limits studies to registered §4.3 candidates: the core upper bounds are 720 point and 336 risk study slots before pruning/deduplication, using one primary band, the two minimum-limit targets and one NOS information track. They are scope ceilings, not trial counts or instructions to run every slot. Later bands, mean targets and interaction/refinement experiments require separate bounded survivor manifests. Training-derived support and chronological pilot results determine parameter ranges and adaptive trial counts. A measured VNI cost probe must project complete workload and two-worker wall-clock cost before launch; funding is shared across each 12-hour batch. No runtime measurements or new HPO results exist yet.

The preferred first combined experiment is **persistence-correction ridge + smooth delivery-time interactions + as-of scheduled outage exposure**, with a regularized period fallback and separately calibrated contraction classifier. Add mapped families and revisions one block at a time. Compare against a shallow LightGBM challenger using the same information.

Promote an accuracy model only when directional-limit gains survive risk guardrails; promote a risk model only when incident gains survive capacity-accuracy guardrails. If the experiment finds that shared models work best, that is a successful resolution of the hypothesis. If NOS adds little after current state, quantify whether the limitation is redundant information, missing mappings, limited archive history or unpredictable changes.

The verdict must attribute diurnal gains separately to additive mean shape, changing driver sensitivities and changing uncertainty. Compare T1 against T0, matched-basis T2/T3 against T1, and period-conditioned against pooled calibration on the identical frozen point model. Report paired metrics and inconclusive components; these predictive ablations do not establish physical causation. Extra correction or boosting effects receive separate attribution.

The initial NOS verdict is conditional on the observed/lagged operating-state information included in the core model. Since NOS is network-only and the forward-generation block is deferred, a weak result cannot rule out NOS value in combination with forecast generation availability or renewable/demand ramps. Before making that broader claim, require a matched NOS off/on × issue-vintage forward-fundamentals off/on experiment and report its interaction effect. If original forecast vintages are unavailable, report that limitation explicitly and retain the conditional verdict; future actuals cannot substitute for deployable inputs.

## Sources and local evidence

All web sources were accessed on 14 September 2026. Dynamic listings describe availability when inspected, not guaranteed continuing retention. Source-based statements above are separated from proposed modelling choices.

[^1]: Soares, L. J., and Medeiros, M. C. (2008). [Modeling and forecasting short-term electricity load: A comparison of methods with an application to Brazilian data](https://www.econ.puc-rio.br/marcelomedeiros/Soares%20and%20Medeiros%20%28IJF%2C%202008%29.pdf). *International Journal of Forecasting*, 24, 630–644. Author-hosted paper.
[^2]: Montero-Manso, P., and Hyndman, R. J. (2021). [Principles and algorithms for forecasting groups of time series: Locality and globality](https://www.sciencedirect.com/science/article/pii/S0169207021000558). *International Journal of Forecasting*, 37, 1632–1653. [Author preprint](https://arxiv.org/abs/2008.00444).
[^3]: Hyndman, R. J., and Athanasopoulos, G. (2021). [Dynamic harmonic regression](https://otexts.com/fpp3/dhr.html), *Forecasting: Principles and Practice*, 3rd edition, §10.5.
[^4]: Hyndman, R. J., and Athanasopoulos, G. (2021). [Time series cross-validation](https://otexts.com/fpp3/tscv.html), *Forecasting: Principles and Practice*, 3rd edition, §5.10.
[^5]: Zaffran, M., Feron, O., Goude, Y., Josse, J., and Dieuleveut, A. (2022). [Adaptive Conformal Predictions for Time Series](https://proceedings.mlr.press/v162/zaffran22a.html). *ICML / PMLR*, 162, 25834–25866.
[^6]: Hallberg Szabadvary, J. (2024). [Adaptive Conformal Inference for Multi-Step Ahead Time-Series Forecasting Online](https://proceedings.mlr.press/v230/hallberg-szabadvary24a.html). *PMLR*, 230, 250–263.
[^7]: AEMO. [Network Outages](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/nem-events-and-reports/network-outages). Undated live explanatory page, §§1–4.
[^8]: AEMO. [Constraint Frequently Asked Questions](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq). Undated live explanatory page, constraint equations and RHS interpretation.
[^9]: AEMO. [NETWORK_OUTAGECONSTRAINTSET](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_460.htm). Legacy HTML MMS data-model documentation; checked against the inspected report header.
[^10]: AEMO/NEMWEB. [Current Network reports](https://www.nemweb.com.au/Reports/CURRENT/Network/) and [inspected report](https://www.nemweb.com.au/Reports/CURRENT/Network/PUBLIC_NETWORK_20260914233030_0000000537882802.zip). Read and parsed in memory; no raw archive retained for this report.
[^11]: AEMO. [NETWORK_OUTAGEDETAIL](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_461.htm). Legacy HTML schema; current sample additionally contains `ELEMENTID`.
[^12]: AEMO/NEMWEB. [Network archive listing](https://www.nemweb.com.au/Reports/ARCHIVE/Network/) and [22 August 2025 bundle](https://www.nemweb.com.au/Reports/ARCHIVE/Network/PUBLIC_NETWORK_20250822.zip). Inner report membership and first report inspected in memory.
[^13]: AEMO/NEMWEB. [September 2024 NETWORK_OUTAGEDETAIL monthly extract](https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2024/MMSDM_2024_09/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_ARCHIVE%23NETWORK_OUTAGEDETAIL%23FILE01%23202409010000.zip). Parsed in memory for row/version and timestamp audit.
[^14]: AEMO/NEMWEB. [September 2024 NETWORK_OUTAGESTATUSCODE extract](https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/2024/MMSDM_2024_09/MMSDM_Historical_Data_SQLLoader/DATA/PUBLIC_ARCHIVE%23NETWORK_OUTAGESTATUSCODE%23FILE01%23202409010000.zip). Sampled dictionary, not an assertion that future codes cannot change.
[^15]: AEMO. [Planned Electricity Network Outages](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/network-data/planned-electricity-network-outages). Undated live page; broader schedule description differs from parts of source 7.

Local evidence, inspected in this workspace:

* **L1:** [Campaign operations](forecast_experiment_operations.md) and [completed experiment results](forecast_experiment_framework_results.md).
* **L2:** [Experiment configuration](../configs/experiments/vni_qni.json); `nemic/experiments/data.py`, `models.py`, `runner.py`, `validation.py`, `events.py` and `benchmarks.py`. These define the current feature, fold, model, event and scoring behaviour.
* **L3:** `nemic/prepare.py` and `nemic/experiments/shadow.py`; the prepared five-minute data confirmed negative raw import limits becoming positive directional-import capacity and vice versa.
* **L4:** [Period-evidence reproduction script](../scripts/reproduce_diurnal_nos_evidence.py), aggregating rolling `*tight_predictions.parquet` files under the completed campaign. It writes `docs/data/qni_vni_diurnal_nos_evidence.json` locally; generated evidence and source predictions are not included in this upload. Connector/target/band/protocol are retained; fixed predictions are excluded. The resulting 20 comparisons are included in this report's table.
* **L5:** [Earlier improvement methodology](QNI_VNI_FORECAST_MODEL_IMPROVEMENT_PLAN.md) and [expanded forecasting research](QNI_VNI_EXPANDED_FORECAST_RESEARCH.md). Used as prior hypotheses, not as evidence that their proposed extensions were implemented.
