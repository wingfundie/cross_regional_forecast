# QNI and VNI flow forecasting improvement methodology

## 1. Recommended approach

Build a compact, forecast-time representation of constraint pressure and test it first with persistence corrections, regularised linear models and additive spline models. Retain the existing LightGBM forecaster as a benchmark. Forecast directional limits and sharp-contraction risk explicitly, then test whether their **out-of-fold predictions** improve the flow model. Retain regional demand and supply conditions because an interconnector can change flow substantially without approaching a limit.

The recommended initial scope prioritises 30 minutes to six hours, while preserving the current half-hour to seven-day forecast interface. Begin with VNI, where the two-year reconstruction is more accurate, and develop QNI with stricter quality gating. Use the same feature definitions, time rules, evaluation and reporting across both connectors.

The studies establish useful candidate mechanisms, not demonstrated operational forecasting improvements. Their most valuable outputs are versioned equation coefficients, directional generator pressure, competing constraints, regime changes and event definitions. Two-year generator rankings should guide hypotheses and engineering diagnostics; they should not become permanent unit weights or be applied retrospectively across every training fold.

Set a candidate budget of **up to 40 network features**, rather than hundreds of generator columns, and retain only blocks that pass testing. Begin with a 12–20-feature simple model; assess the full specification of 24 directional features, eight quality features and eight generator-group features through ablations. A later market-context block may add eight features. These counts describe additions to the existing design, not the total number of model inputs.

A new exploratory comparison on the retained data supports this restraint: adding existing topology features improved ridge regression in 13 of 18 connector/target/horizon cells, but beat persistence in only eight. The same addition improved an additive model in only two cells. The first implementation recommendation is therefore a small, quality-gated ridge correction, with persistence retained wherever it wins; details and limitations appear in Section 11.

Three conditions govern the work:

1. Every input must carry evidence of when it became available. Historical data being public today does not establish availability at a historical forecast origin.
2. The reported-limit reconstruction and generator contribution calculations must be audited separately. Good accounting closure can coexist with incomplete physical attribution.
3. The previously examined September 2024–August 2026 period is development evidence for this new methodology. Future improvement claims require newly frozen evaluation and prospective forecasts.

## 2. Existing model and measured starting point

The repository pools six interconnectors in direct LightGBM regressors, separately fitted for signed dispatch flow, mean export limit, mean directional import limit, and the tightest five-minute export/import limits within each half-hour. It already includes calendar features, regional fundamentals, weather, lagged outcomes, reported setter categories, network flags, regional generation availability and other-interconnector flows. The current network estimator uses 180 trees, 23 leaves and absolute-error loss.[^1]

The primary flow target is `MWFLOW`, averaged over six dispatch intervals. `METEREDMWFLOW` is retained during preparation but is not the primary forecast target. Operational dispatch-target accuracy and physical metered-flow accuracy should therefore be reported separately if the latter is added.[^2]

The saved backtest supplies realised future demand, wind, solar and weather. It is a conditional experiment. It does not show how accurately the same model would perform with issue-time forecasts of those inputs. The nominal 80% prediction intervals achieved 72.3% aggregate coverage, indicating that uncertainty calibration also needs attention.[^3]

| Saved test metric | QNI | VNI | Implication for the proposed work |
|---|---:|---:|---|
| Flow MAE, 0.5–6 h | 206.5 MW | 248.7 MW | Establish matched baseline errors before changing features |
| Flow MAE, 6.5–24 h | 234.2 MW | 271.4 MW | Forecasted future network state matters beyond persistence |
| Export-limit MAE, 0.5–6 h | 121.9 MW | 231.5 MW | Evaluate whether contraction features reduce limit errors |
| Import-limit MAE, 0.5–6 h | 123.9 MW | 186.3 MW | Preserve direction-specific models and diagnostics |
| Existing export restriction recall / precision | 52.9% / 50.2% | 72.2% / 73.1% | Improve warning quality as well as recall |
| Existing import restriction recall / precision | 54.5% / 39.4% | 89.9% / 21.1% | VNI import false alerts are a particularly useful diagnostic |

These figures are from the saved March–August 2026 experiment. Restriction metrics aggregate forecast-origin/lead pairs across horizons and use the existing low-limit definition; they are not sharp-contraction event scores. Repeated predictions of one physical incident are not independent events.[^3]

The model currently has setter identity, but not a production integration of versioned generator coefficients, competing equation margins or a contraction-event head. `constraint_features.py` provides useful prototype calculations, including pressure, relief, candidate counts and switch gaps. Its retrospective feature construction and feasibility testing must be refactored into an issue-time pipeline before use in operational model claims.[^4]

## 3. Findings from the studies and their modelling implications

### 3.1 Different reconstruction quality

Both studies cover 1 September 2024 through 31 August 2026, with 210,240 five-minute observations per connector and two complete seasonal cycles. They distinguish binding equations, equations within 50 MW of binding, reported directional setters and reconstructed envelope leaders.[^5][^6]

| Diagnostic | VNI | QNI |
|---|---:|---:|
| Generator DUIDs with valid sensitivities | 232 | 238 |
| Equation versions researched | 20,827 | 15,010 |
| Upper / lower reconstruction coverage | 99.77% / 99.49% | 99.75% / 99.75% |
| Upper / lower reconstruction MAE | 7.11 / 22.55 MW | 410.58 / 248.90 MW |
| Exact dispatch-to-equation version match | 92.06% | 65.32% |

High numerical coverage is insufficient for QNI: a computed bound exists on almost every interval, but its average discrepancy is material. First stratify errors by month, direction, version-match status, equation family, tiny interconnector coefficients, interventions and reported-setter eligibility. Inspect whether errors arise from mapping, candidate selection, missing versions, static limits or mixed run solutions. Do not assume a particular cause before this audit.

Initially use reported QNI limits as state and outcome quantities. Admit QNI reconstructed pressure features only when their source and equation quality pass the configured gate. Retain the failed population in overall forecast scoring so a quality filter cannot make the results look better simply by excluding difficult intervals.

VNI offers a more promising starting point, but its aggregate accuracy does not remove the need for event-level checks. Report distributions of reconstruction error, including P95/P99 and the fraction within 1, 5 and 25 MW, rather than relying on mean error alone.

### 3.2 Generator candidates

The broad persistence-weighted candidate lists differ from the selected-event contribution rankings. VNI's broad leaders include MURRAY, LIMOSF11, TUMUT3, SUNRSF1, UPPTUMUT, DARLSF1, STWF1 and MUWAWF1. QNI's include NEWENSF2, NEWENSF1, SAPHWF1, WRWF1, METZSF1, TUMUT3, BW01 and GNNDHSF1.[^5][^6]

| Selected-case gross tightening contribution | VNI | QNI |
|---|---:|---:|
| TUMUT3 | 35,037.5 MW | 12,233.8 MW |
| UPPTUMUT | 9,712.73 MW | 3,132.48 MW |
| LIMOSF11 | 9,211.01 MW | Not shown in the atlas top-20 table |
| STAN-2 | Not shown in the atlas top-20 table | 4,679.85 MW |
| STAN-1 | Not shown in the atlas top-20 table | 4,044.73 MW |

These are sums of fixed-equation step contributions across selected cases, not single-event capacity reductions, energy in MWh or counterfactual causal effects. Relief terms can offset tightening. The atlas aggregate deduplicates shared physical steps; individual case windows can overlap. Switching is separately accounted for.[^7][^8]

The practical feature hypothesis is therefore **generator movement multiplied by its current equation-specific sensitivity**, conditioned on proximity to a relevant limit. Tumut 3 should not receive one global rule such as “more output means southward flow.” Its coefficient, eligible equation, competing constraints, other dispatch and RHS state determine the local implication.

### 3.3 Event and price evidence

| Atlas population | VNI | QNI |
|---|---:|---:|
| Contraction detections | 7,486 | 7,430 |
| Grouped incidents | 5,379 | 5,445 |
| Selected detailed contraction cases | 91 | 92 |
| Additional price-only cases | 12 | 13 |
| Contraction detections followed by receiving-region MPC within one hour | 13 | 5 |

The atlases report a positive matched peak-price-jump association for VNI: $94.97/MWh, with a day-block bootstrap interval of $58.27–136.83/MWh. QNI's estimate is $15.67/MWh, with an interval of −$26.73 to $53.33/MWh. These observational comparisons do not identify a causal price effect. Exact MPC observations are sparse and are counted by region-interval, not necessarily as independent price episodes.[^7][^8]

Prioritise limit contractions, direction and flow errors. Use MPC-linked episodes as a separate high-consequence diagnostic. The evidence does not support training the core model only on price-spike cases or promising reliable standalone MPC prediction.

The atlas detector and longitudinal reports can have slightly different counts because they have separate screening implementations and boundary/grouping rules. Preserve detector version and population identifiers in every new result; do not silently combine their denominators.

## 4. Forecast products and sign conventions

Use the existing positive directions:

| Connector | Identifier | Positive flow | Negative flow |
|---|---|---|---|
| VNI | `VIC1-NSW1` | Victoria to NSW | NSW to Victoria |
| QNI | `NSW1-QLD1` | NSW to Queensland | Queensland to NSW |

Let `F` be signed flow, `U = EXPORTLIMIT`, and `L = IMPORTLIMIT` in the raw signed-flow convention. The repository's directional import quantity is `C_lower = -L`; the export quantity is `C_upper = U`. Preserve negative directional quantities. For example, `U < 0` describes a reported upper bound requiring negative flow; `L > 0` describes a reported lower bound requiring positive flow. Crossed bounds and violated/intervention solutions require separate flags.[^2]

Maintain the existing five regression targets for comparability. Add event products with explicit semantics:

| Product | Definition | Initial horizons |
|---|---|---|
| Sharp-contraction probability | At least one new onset in a future window, separately for each directional capacity | Next 30, 60 and 180 minutes |
| Contraction severity | Maximum directional capacity loss from the origin level within the horizon; also report conditional-on-onset severity | Same windows |
| Direction state probability | Positive, near-zero or negative dispatch flow at delivery | Existing half-hour leads |
| Reversal probability | First transition to the opposite nonzero sign during the window | Next 30, 60 and 180 minutes |
| Forced-direction probability | Future reported `U < 0` or `L > 0`, with inconsistency separately classified | Same windows, then longer leads |

Use an initial ±25 MW near-zero band and test 10/25/50 MW as development sensitivity settings. This is a proposed noise tolerance, not an established market rule. Require an observable pre-event sign and distinguish a brief crossing from a sustained reversal, initially two consecutive five-minute intervals. Window labels require complete observations; missing outcomes must remain missing rather than becoming negative labels.

Use five-minute records for event detection even if the model issues every half-hour. Half-hour means can hide a sudden collapse and recovery. A later five-minute issue cycle is a separate freshness experiment, not part of the first feature-architecture comparison.

## 5. Constraint representation

### 5.1 Versioned conditional sensitivities

For an eligible constraint normalised to `<=`, write:

```text
a_ci F_i + sum_g(b_cg P_g) + sum_j(d_cj F_j) + Z_c <= R_c
```

`Z_c` contains the remaining LHS terms, including relevant regional or unit service quantities. For a nonzero subject-interconnector coefficient:

```text
B_ci = (R_c - sum_g(b_cg P_g) - sum_j(d_cj F_j) - Z_c) / a_ci
s_cg = -b_cg / a_ci
```

Positive `a_ci` supplies an upper candidate; negative `a_ci` supplies a lower candidate. Normalise `>=` first. Handle equality constraints explicitly according to their role and the applicable reporting procedure; do not force every equality into a one-sided capacity feature. Include standing limits and relevant reporting eligibility when reproducing reported values. AEMO's published reporting specification explains the substitution of other solved LHS quantities and directional min/max selection.[^9]

Where solved `LHS`, `RHS`, flow and exact `a_ci` are available from one consistent run, calculate the current conditional candidate as:

```text
B_ci = F_i + (R_c - LHS_c) / a_ci
```

This can recover a current bound without individually observing every LHS term. It does not identify how much of a future change comes from each generator. Treat current-bound reconstruction and term-level pressure completeness as different quality dimensions.[^4]

The sensitivity is conditional on the equation, other terms and RHS. It is not a bus-level PTDF or an unrestricted total derivative of dispatch. AEMO notes that RHS expressions can contain network state and feedback terms; future RHS can change alongside generation.[^10] Consequently, scenario pressure is a predictive input and a mechanical diagnostic, not a full NEMDE redispatch result.

### 5.2 Tightening and relief

For a generator change `delta_P_g`, let `m_cg = s_cg * delta_P_g`, the signed movement of that equation's flow bound. Define:

```text
upper tightening = sum_g max(-m_cg, 0)
upper relief     = sum_g max( m_cg, 0)
lower tightening = sum_g max( m_cg, 0)
lower relief     = sum_g max(-m_cg, 0)
net tightening   = tightening - relief
```

Lower tightening is an increase in the signed lower bound, hence a decrease in import-direction capacity. Compute at both five-minute and 30-minute lags. Within an observed fixed-version segment, retain the decomposition into generators, other LHS, RHS, switching and unresolved discrepancy. Never attribute a new setter's full discontinuity to the generators appearing in its equation.

For illustration only, suppose an upper equation is `F + 0.4P <= 900`, with all other contributions held fixed. A 100 MW generator increase contributes 40 MW of upper tightening. If the effective RHS simultaneously increases 60 MW, the bound expands by 20 MW overall. This explains why large gross generator tightening can coexist with an expanding limit.

For a lower equation `-F + 0.3P <= 200`, a 100 MW increase raises the lower bound by 30 MW, reducing import-direction capacity by 30 MW. Neither example is an observed Tumut 3 equation or an estimated forecast improvement.

### 5.3 Candidate competition

Use all **currently invoked, eligible, directly linked** candidate equations for the subject connector, including nonbinding candidates. Add future invocations only when a schedule or forecast publication available at the origin identifies them. Retain a small training-derived fallback library for unknown future regimes, explicitly marked uncertain. Do not choose the origin's candidate set using the future realised setter.

Binding status, reported setter, proximity to the current dispatch point and proximity to the leading bound answer different questions. Retain all four classifications. For upper candidates sorted increasingly, the switch gap is `B_2 - B_1`; for lower candidates sorted decreasingly it is `B_1 - B_2`. A small switch gap means the leading equation may change after a modest relative movement, even when flow is well inside the envelope.

Start with the top three eligible candidates per direction. These are retained as long-form diagnostic rows, not three copies of every model column. Aggregate candidate pressure using weights proportional to `q_c * exp(-gap_c / tau)`, normalised within direction, where `q_c` is an origin-known quality score. Tune `tau` from 25/50/100 MW in development folds. Always retain leader-only features as a simpler ablation and record when no candidate passes.

This weighted pressure is a model feature; it is not the derivative of the minimum of several equations. Candidate dependence, ties and activation uncertainty require learned or scenario-based treatment.

### 5.4 Generator grouping

Use a sparse equation–generator–interconnector incidence representation, with signed, versioned coefficients. This is a factor graph describing constraint relationships, not a claim to have complete electrical bus topology.

For an initial four-group configuration per connector, test:

| VNI starting groups | QNI starting groups |
|---|---|
| Snowy hydro: TUMUT3, UPPTUMUT, MURRAY | Snowy hydro: TUMUT3, UPPTUMUT, MURRAY where linked |
| Solar units represented by LIMOSF11, SUNRSF1, DARLSF1, AVLSF1 | New England generation represented by NEWENSF1/2, METZSF1, SAPHWF1, WRWF1 |
| Wind units represented by MUWAWF1, KIAMSF1, STWF1 | Queensland thermal generation represented by STAN-1/2 and related linked units |
| Storage and remaining eligible terms, including VBB1 where mapped | Storage and remaining eligible terms, including LDBESS1 where mapped |

These are illustrative study-informed memberships, not verified geographic boundaries or final learned clusters. In each fold, recompute eligible membership and weights from available metadata and training-only exposure. Keep each DUID in one reporting group per connector to avoid double counting. The same DUID can affect both connectors with different signed coefficients.

An alternative is to cluster units by their signed coefficient vectors across training equations, weighted by training invocation frequency. Compare four interpretable groups with a four-to-eight-dimensional truncated SVD representation fitted only on training data. Prefer the interpretable groups unless compression improves held-out results materially. Preserve individual unit contributions in diagnostic storage even when the model receives only aggregates.

## 6. Compact feature specification

### 6.1 Directional block: 24 additions

Compute the following 12 quantities separately for upper and lower capacity. All observed quantities end at the latest admissible source cutoff; all projected quantities use forecasts issued by the origin. Store physical units and source lineage before standardising for a linear model.

| Feature per direction | Construction | Expected use |
|---|---|---|
| `room_mw` | Upper: `U-F`; lower: `F-L`, using reported values initially | Current exposure to a limit |
| `capacity_change_30m` | Latest directional capacity minus its value 30 minutes earlier | Collapse or recovery momentum |
| `switch_gap_mw` | Leading-to-runner-up eligible bound gap | Setter competition |
| `near_candidate_count` | Invoked eligible candidates within 50 MW of the leading bound | Breadth of nearby restrictions |
| `setter_age_minutes` | Time since the latest observed setter/version change | Persistence of regime |
| `switches_60m` | Count of observed setter/version transitions over one hour | Regime instability |
| `gen_tightening_5m` | Quality-weighted candidate gross tightening from generator movement | Immediate generator pressure |
| `gen_relief_5m` | Corresponding gross relief | Offsetting movement |
| `gen_net_30m` | Net generator tightening over 30 minutes | Sustained pressure |
| `pressure_to_room` | `gen_net_30m / max(abs(room_mw), 25)`; preserve room sign separately | Pressure relative to margin |
| `projected_gen_net_h` | Sensitivity-weighted generator/group forecast change to delivery | Prospective pressure |
| `rhs_capacity_change_30m` | Directionally signed `delta_R/a` on fixed-version segments | Non-generator movement |

The 25 MW ratio floor is a development parameter. A negative room indicates an unusual/violated solution rather than excess available margin. Do not substitute the ratio for raw room or delete negative values. If the RHS is unavailable or its version changed, set that component missing and retain its quality flag. The observed total capacity change still exists.

Start with the existing reported setter categories and broad family labels. For simple regressions, cap family interactions to a small training-defined vocabulary, pooling rare families into `OTHER`. Avoid one coefficient per equation ID. The 50 MW candidate threshold is a continuity choice with the studies; compare 25/50/100 MW without reselecting it on evaluation outcomes.

### 6.2 Quality block: eight additions

| Quality feature | Meaning |
|---|---|
| `exact_version_fraction` | Fraction of selected candidates joined to the exact referenced version |
| `complete_terms_fraction` | Fraction whose required pressure terms are observed |
| `max_source_age_minutes` | Oldest required observation age across the feature block |
| `reconstruction_discrepancy_mw` | Maximum absolute current reported-versus-reconstructed bound discrepancy across directions |
| `unstable_factor_fraction` | Fraction rejected/flagged for numerically unstable subject coefficients |
| `unknown_family_flag` | Presence of an unrecognised leading family |
| `future_input_quality` | Defined numeric code for observed-only, modelled, archived-forecast or missing future input path |
| `envelope_inconsistent_flag` | Reconstructed lower bound exceeds upper bound |

Keep richer quality details in the diagnostic table even if only eight values enter the model. Do not calculate an origin's reliability score using future reconstruction performance of that equation. Numerical coefficient cutoffs must be invariant to rescaling of the whole equation: use a relative coefficient ratio and a sensitivity plausibility check, rather than an unexplained absolute `a` threshold.

### 6.3 Generator-group block: eight additions

For each of four groups, provide one projected net tightening value per direction. Their sum should reconcile with the corresponding aggregate when using the same complete candidate population. They explain which combination of units drives pressure without requiring each DUID as a model variable.

The group features are a hypothesis, not a requirement to retain all eight. Test whether they add information beyond total pressure. Ridge is suitable when correlated groups overlap in behaviour; elastic net may remove weak features but can choose arbitrarily among highly correlated units. Group ablation is more reliable than reading one fitted coefficient as proof of individual importance.

### 6.4 Optional market block: eight additions

After the network-only ablation, add receiving-minus-sending residual-demand forecast, its next-hour ramp, combined wind availability forecast, combined solar availability forecast, receiving-region available coal capacity, known offline coal capacity, a receiving-region temperature stress measure and the latest admissible regional price spread.

Residual demand must match the repository's demand definition: `TOTALDEMAND` is already net of embedded rooftop generation; do not subtract rooftop a second time.[^2] Unconstrained renewable availability and cleared renewable dispatch are different quantities. Future cleared output is partly determined by the congestion being predicted, so it cannot be treated as an externally known driver.

Zero coal generation alone means “not currently generating,” not “forced outage.” Distinguish registered capacity, offered availability, operating output, planned outage and confirmed forced outage. Leave unavailable outage classifications unknown. Temperature is a supplementary stress proxy unless a specific rating/RHS mechanism and suitable location are known. A weather station or reanalysis grid near a region is not automatically a transmission asset's operating temperature.

Use the event atlas's demand, renewable, coal and weather context to choose diagnostic slices and hypotheses, then rebuild features under the publication-time contract. Do not attach retrospective event-window maximum demand, realised outage duration or future price extremes to the forecast origin.

## 7. Required data and availability contract

### 7.1 Data inventory

| Data | Existing evidence | Operational input or new work | Priority |
|---|---|---|---|
| Five-minute IC flow, directional limits and setters | Full population grids retained | Capture public source issues and revisions; preserve physical/pricing run distinction | Essential |
| Constraint solutions: RHS, LHS, marginal value, violation | Monthly studies and selected windows | Audit fields available at each origin and reconstruct invoked eligible candidates | Essential |
| Versioned IC, connection-point and regional coefficients | Substantial standing extracts retained | Exact effective/version joins; source publication history; add required regional/FCAS terms | Essential |
| DUID and connection-point metadata | Standing mapping retained | Time-effective generation/load/BDU mapping; source versions | Essential |
| Unit SCADA | Need inventory of complete retained coverage | Public `DISPATCH_UNIT_SCADA` provides start-of-dispatch-interval MW; archive its actual arrival times | Essential for public unit movement |
| Unit dispatch targets, availability and ramps | Retrospective `DISPATCHLOAD` extracts | Do not assume whole-market targets are contemporaneously public; use entitled feeds or delayed research labels | Conditional |
| AEMO IC predispatch forecasts | Original-vintage benchmark already exists for a subset | Reuse; inventory P5MIN and predispatch issue/delivery coverage and gaps | High |
| Constraint invocation schedules and forecasts | Some standing invocation records | Preserve schedules as published, including revisions and cancellations | High |
| Regional demand / renewable forecasts | Realised series already exist | Replace realised future drivers with issue-time forecast paths | High |
| Weather forecast runs | Historical weather retained | Retrieve only selected locations, variables and issue runs if needed | Secondary |
| Coal capacity, outage schedules, prices | Selected-case context and regional prices | Full-timeline, time-effective source audit before modelling | Secondary |
| RHS formula details and telemetry | Partial equation reconstruction | Recover only dependencies needed to explain material residual components | Targeted extension |

AEMO identifies `DISPATCH_UNIT_SCADA` as public start-of-interval telemetry. It should not be equated with the end-of-interval dispatched energy target used in a solved equation.[^11] Whole-market `PREDISPATCHLOAD` is described as public next day, and the reviewed P5MIN unit specification marks unit solutions private. Archived `DISPATCHLOAD` also has private/public-next-day treatment. Therefore, the public implementation should start with SCADA-based observed ramps and its own unit/group forecasts; richer participant inputs require a separate entitlement and historical-availability check.[^12]

This changes interpretation: “SCADA pressure” approximates observed physical movement, while “solved-target pressure” explains the dispatch solution. Keep their feature names, training tracks and validation results separate. A fixed 30-minute lag alone cannot turn next-day information into a live input.

### 7.2 Four timestamps

Every retained observation or forecast must carry:

```text
valid_time        time the physical quantity or forecast applies to
issue_time        originating report/model run time
available_at      when this implementation could first consume the value
retrieved_at      when the archive was collected for research
```

Also retain the source's revision/`LASTCHANGED`, effective date, version, source URL/hash and run type. `LASTCHANGED` is not sufficient evidence of public availability. Forecast-time joins require `available_at <= origin`; among eligible versions select the latest appropriate issue. Future effective standing data can be used only if it had already been published and was scheduled to apply at delivery.

Where a historical arrival time is missing, use a clearly documented conservative release policy supported by the source, or exclude that feature from the strict operational track. Keep a separate simulated-latency experiment. Measure actual arrival lag during prospective collection rather than treating an assumed buffer as proven.

### 7.3 Forecast weather and horizon coverage

Open-Meteo distinguishes stitched historical forecast series from individual original model runs. The former should not be used as though they preserve every historical issue/horizon. Its current documentation lists ECMWF IFS HRES single-run coverage from March 2024, while other single-run archives generally start later. Verify coverage for each selected model, location and variable and account for run publication delay; model initialisation time is not availability time.[^13]

Reuse AEMO predispatch only within actual source coverage. The repository's historical benchmark matched 0.5–39-hour leads, not a universal seven-day product. Beyond available forecasts, use explicitly modelled demand, renewable and unit/group scenarios. Missing forecasts should trigger a known fallback with wider uncertainty, not forward-filled claims of fresh guidance.[^3]

### 7.4 Storage and download guard

Reuse the retained study partitions and source manifests first. Keep a **10 GB decimal combined cap** across study/event/new-feature working data, temporary archives, extracted batches and retained forecasts, with at least **20 GB free disk** reserved. Audit existing storage before beginning; the cap is not a statement that all repository data currently fit inside it. Model/result storage also needs a named budget so it cannot grow invisibly outside the data guard.

Build an explicit manifest of connector, date window, table, required columns, entity dependencies and exact archive URL. Never download an entire MMS database snapshot or recursively enqueue all monthly tables. Large monthly table archives may still contain the full market even when only a few entities are needed; filtering saves retained/expanded storage but does not reduce compressed download size. Check that distinction before each request.

Process one bounded table/month batch at a time. Reserve compressed plus maximum expanded space before download, stream and hash, filter during extraction, write compact Parquet, validate counts and keys, atomically mark the batch complete, then remove that batch's temporary archive/extraction. Log bytes downloaded, retained and deleted, checksums, row filters, missing files and retry status. Cleanup applies only to verified task-owned temporary paths.

Keep compact origin features, sparse standing coefficients, labels, summary scores and source provenance. Do not materialise the full generator × constraint × interval × horizon Cartesian product. Partition features by connector/month and forecast vintages by issue month. Retain a limited rolling window of full predictions plus permanent aggregate sufficient statistics and selected event traces. Optional external storage must preserve a manifest and ownership, not become an implicit unlimited download destination.

## 8. Models: simple first, with explicit escalation

### 8.1 Research synthesis

The reviewed literature does not establish that boosting is required for QNI/VNI flow forecasting. The closest statistical precedent found is Paretkar's Pacific Northwest intertie work using ARIMA and transfer-function models on public data. It is a 2008 master's thesis in a different system, so it supports a baseline class rather than an Australian performance claim.[^14]

Lago and colleagues provide an open electricity-price benchmark that includes a regularised autoregressive linear model, LEAR, and emphasises strong baselines, adequate test periods and reproducible comparisons. Price forecasting is adjacent to the flow task: borrow the evaluation discipline and regularisation approach, not its estimated accuracy.[^15] Additive/quantile-additive energy forecasting also has published precedent; spline-plus-ridge offers a small-dependency implementation in this repository, although it is not identical to a fully penalised statistical GAM.[^16]

| Evidence | Relevance to the local findings | Consequence |
|---|---|---|
| Versioned local equations give signed linear contributions within a regime | TUMUT3 and other units have changing signs/exposure | Engineer the regime and pressure first; fit a simple correction |
| The leading bound changes across equations | Single global linear effects can miss switching | Add hinge terms, a few family interactions or additive splines before trees |
| NESO's congestion project conditions on known day-ahead schedules and stresses data requirements | Some useful inputs exist only after a particular information release | Define the information set before comparing models[^17] |
| General tabular benchmarks find trees competitive | Irregular interactions may eventually benefit from trees | Justifies a challenger, not automatic selection for this task[^18] |
| A recent interconnector surrogate paper uses European simulated OPF outcomes | Physical consistency and future supply mix matter | Useful conceptual extension, but not evidence of live NEM forecast skill[^19] |

The June 2026 interconnector-surrogate preprint evaluates KNN and neural networks on synthetic European flows for reduced planning models. Its claimed simulation speedup is not an improvement in operational QNI/VNI forecast accuracy. It does not compare the proposed public-vintage linear model and cannot justify bypassing simple baselines.[^19]

### 8.2 Model ladder

| Stage | Method | Role and complexity control |
|---|---|---|
| M0 | Persistence, weekly seasonal persistence and admissible AEMO forecast | Mandatory benchmarks on common timestamps |
| M1 | Persistence/AEMO residual correction with ridge; elastic-net alternative | First implementation; linear, regularised, easily audited |
| M2 | Additive spline regression with ridge, plus a small predefined interaction set | Smooth nonlinear response without a tree ensemble |
| M3 | Logistic event/direction models and optional two-regime mixture of simple regressions | Separate contraction warnings from typical flow; only add mixture if useful |
| M4 | Existing LightGBM and a shallow constrained tuning grid | Challenger only after M1–M3 and quality fixes |
| M5 | Sequence or graph models | Deferred; require demonstrated residual problem, reliable topology/vintages and compute justification |

For M1 forecast a change from the latest admissible observation, or a residual from an admissible AEMO forecast:

```text
y_hat(origin, h) = anchor(origin, h)
                 + intercept(connector, band)
                 + beta(band)' * x(origin, h)
```

Start with separate connector and lead-band regressions or a shared regression with connector indicators and a few connector-by-pressure interactions. Include lead and log-lead within bands and check discontinuities at boundaries. Avoid 336 entirely independent regressions initially. Standardise using training-only statistics, impute with training-only values and include missingness indicators. Compare direct level regression with change regression; ridge optimises squared loss, so assess MAE explicitly and consider Huber or median regression if spikes dominate fitting.

The minimal M1 input set can contain reported room, recent flow/limit changes, net generator pressure in each direction, competing-bound gaps, quality, regional residual-demand forecast difference and calendar harmonics. This 12–20 feature subset precedes the full 40-feature ablation. A model with engineered nonlinear inputs is still linear in its fitted coefficients and can capture more than a regression on raw generator MW.

For M2 add low-degree splines to room, pressure, switch gap, residual-demand difference and lead. Use four to six knots fitted on training data; log the expanded design-column count and effective complexity. Add only a few predeclared interactions, such as pressure × near-limit flag, pressure × broad constraint family and demand imbalance × directional room. A spline basis expansion is not evidence of a physical threshold.

For events, start with regularised logistic regression. For direction, use a three-class logistic model or probabilities derived from a calibrated signed-flow distribution. Test a two-part contraction model: onset probability and severity conditional on onset. A rare-event classifier with class weighting must be recalibrated on naturally distributed data before probabilities are interpreted.

Do not hard-clip all flow forecasts to separately predicted reported limits. The limits depend on a dispatch solution; independently predicted bounds can cross, and marginal forecasts do not define a joint physically feasible dispatch. If a coherence adjustment is tested, evaluate it as a separate transformation with raw and adjusted scores and an explicit failure mode for inconsistent envelopes.

### 8.3 When boosting is justified

The justification requires both a plausible mechanism from research and local out-of-time evidence: persistent nonlinear residual interactions, sufficient representative samples, and repeatable improvement over the best simple candidate. A broad tabular result alone is insufficient. Use the existing LightGBM as a fixed reference and later test a limited 7/15/23-leaf grid, regularisation and early stopping on development folds.[^18][^20]

A proposed promotion rule is at least a 5% relative improvement in the primary predeclared error measure, a block uncertainty interval favouring the challenger, and no material deterioration in event warnings, calibration or important seasonal slices. This is a decision threshold to pre-register, not a promised uplift or universal statistical rule. Prefer the simpler model when differences are small or unstable; report inference cost, fit time and feature requirements alongside accuracy.

Temporal Fusion Transformers distinguish observed-history, known-future and static variables, which is conceptually relevant. They are a later comparator only: the reviewed paper does not establish a benefit on these interconnectors, and two years of highly dependent intervals do not provide millions of independent network regimes.[^21]

## 9. Connecting generator forecasts, limits and flows

At short horizons, observed generator pressure is useful only insofar as it predicts subsequent movement or regime persistence. Start unit/group forecasting with persistence and capped, decaying ramp extrapolation. Estimate decay on training data; apply admissible capacity/ramp bounds. For hydro and storage, include observed mode and available operational information, but do not invent water budgets, battery state of charge or future bids.

For six hours onward, use regularised unit/group response models or scenarios conditioned on available demand, renewable and price forecasts. For days two to seven, treat outages, resource availability and economic dispatch uncertainty explicitly. Never extend a five-minute ramp linearly for seven days. Use forecast ensembles or a small set of coherent baseline/tightening/relief scenarios, preserving regional and generator dependencies.

Fit the directional-limit models first. Produce historical out-of-fold limit medians, interval widths and event probabilities for the flow model; at live issue time use the deployed limit model's outputs. A flow model trained on realised future limits or in-sample fitted limit predictions will overstate this benefit.

Initially permit six additional downstream model inputs: predicted upper and lower median, their interval widths, and upper/lower contraction probabilities. This is a separate six-feature stacking block, so a flow model with the full network and optional market blocks adds at most 54 inputs: 40 + 8 + 6. It does not change the feature budget of the upstream limit model.

Test the following paths independently:

```text
Published inputs -> compact state -> simple flow correction
Published inputs -> compact state -> simple limit/event models
Out-of-fold limit/event predictions -> simple flow correction
```

The third path is adopted only if it improves on the first. Limits and actual flows are jointly determined, so a limits-first architecture is a forecasting hypothesis rather than a causal ordering claim. At short horizons with an AEMO forecast, a ridge correction around AEMO may outperform an entirely separate flow model. Compare on identical origin/delivery pairs and use a documented fallback where AEMO forecasts are unavailable.

## 10. Sharp-contraction labels and warning evaluation

The current atlas defines a drop as `C(t-30 minutes) - C(t)`. A sharp observation is positive, at least the month's 90th percentile of positive drops, and has all seven five-minute observations present. Months with fewer than 100 positive falls receive no threshold. An onset is a transition from not sharp to sharp.[^22]

Because that monthly percentile uses the full realised month, it is appropriate for retrospective screening but not an origin-known live trigger. Preserve those labels for reproducing the atlas. Add a new, separately versioned forecasting label using thresholds fitted only on past training data, with month-of-year pooling or a trailing historical window. Freeze the threshold rule before evaluation and show sensitivity to a training-defined absolute MW floor.

At origin `o`, an onset-window target is one when a new onset occurs in `(o, o+h]`. Label ongoing contractions separately; do not count an alarm after onset as an advance warning. Distinguish this from the continuous severity target `max(0, C(o)-min C(t))` over the same future window: an event detected by a rolling 30-minute comparison can have begun declining before the forecast origin.

Collapse adjacent alarms into warning episodes using a fixed cooldown and match them one-to-one to grouped incidents within the permitted lead window. Report incident recall, precision, false alerts per day, median advance warning and lead-time distribution. Also retain interval-level Brier/log loss and precision-recall curves. A useful warning system should improve recall at the same false-alert budget, rather than maximise F2 without regard to an operator's alert burden.

Keep contraction, low-capacity restriction, reversal, forced direction and price spike as distinct labels. Analyse their intersections after evaluating each product. For MPC-linked diagnostics, use the price cap effective at the event date and the receiving-region definition fixed by the event direction. Sparse MPC episodes should be shown individually with uncertainty, not used to tune a complicated dedicated model.

## 11. Additional assessment of retained repository data

A bounded retrospective probe compared persistence, ridge corrections and additive spline corrections using the retained monthly features. It read 48 monthly half-hour feature partitions, covering both connectors, plus the existing target table: approximately 25.13 MB of local source files. It downloaded no market data. The full source paths, byte counts, hashes, settings, environment and 90 score rows are retained in the [research evidence file](data/qni_vni_simple_model_research.json).[^23]

The base design has 17 inputs: three outcome lags for flow and tight directional limits, recent changes, delivery calendar harmonics and a weekend indicator. The augmented design has 37 raw inputs, adding 20 existing numeric topology columns. These are the existing prototype features, not an implementation of the proposed 40-feature specification. The additive version applies a small quadratic spline basis followed by ridge; its expanded design is larger than the 37 raw inputs.

All observations are shifted one half-hour. Models train on origins from 8 September 2024 with deliveries through 1 September 2025, choose ridge strength from 10/100/1000 using September 2025–February 2026 validation, and are evaluated on March–August 2026. Leads are 30, 60 and 180 minutes. Preprocessing uses training-only medians, scaling and 0.1/99.9 percentile clipping. There is no future realised demand/weather input and no refit after validation selection.

### 11.1 Flow results

| Connector | Lead | Persistence MAE | Ridge base | Ridge + topology | Additive base | Additive + topology |
|---|---:|---:|---:|---:|---:|---:|
| VNI | 30 min | 155.45 | 156.42 | 150.69 | 153.78 | 156.42 |
| VNI | 60 min | 197.08 | 194.12 | 191.65 | 193.02 | 195.71 |
| VNI | 180 min | 317.56 | 277.07 | 278.77 | 278.92 | 281.65 |
| QNI | 30 min | 115.29 | 117.41 | 114.89 | 119.59 | 116.62 |
| QNI | 60 min | 143.57 | 148.26 | 146.53 | 151.83 | 150.23 |
| QNI | 180 min | 211.84 | 219.10 | 219.34 | 225.25 | 234.26 |

All errors are MW. These comparisons show modest short-horizon VNI signal in the existing pressure block, limited QNI flow benefit and no automatic benefit from adding flexible response curves. The best evaluation column must not be retrospectively called the chosen production model. The evidence file separately records the regression candidate selected on validation; it excludes persistence from that particular regression-selection list, so deployment selection must explicitly restore all mandatory benchmarks.

### 11.2 Limit results and feature availability

Across all 18 connector/lead/target cells, topology improved ridge relative to its base version in 13 cells, but ridge with topology beat persistence in only eight. Topology improved the additive version in only two cells. These equal-weight cell counts are descriptive and do not establish statistical significance or commercial value.

Examples illustrate why the full losses matter. At 30 minutes, VNI tight export MAE fell from 152.90 to 145.68 MW with ridge topology, while its tight import MAE was still 130.05 MW against persistence's 114.10 MW. QNI tight export improved from 79.20 to 73.05 MW with ridge topology, but persistence achieved 62.75 MW. At 180 minutes, QNI additive tight import worsened from 156.13 to 197.60 MW when topology was added.[^23]

Monthly-average nonmissing pressure shares were about 99.71% upper / 99.43% lower for VNI and 99.69% / 99.69% for QNI. The weakest upper-pressure month was September 2024: 94.65% VNI and 94.10% QNI. These are unweighted averages of monthly half-hour coverage, not exact-version quality rates or a replacement for the five-minute reconstruction diagnostics. Near-complete feature availability does not make the QNI reconstruction accurate.

### 11.3 Interpretation and limits of this probe

This is an exploratory test of whether the retained representation contains potentially useful predictive structure. It does not validate operational availability, prove generator causality or measure event-warning skill. The period was already inspected; topology dependencies and standing-version recovery are retrospective; a half-hour lag does not remedy next-day release restrictions. The clipping and squared-loss ridge fit are deliberately simple choices that may suppress or underweight important contractions.

The appropriate next step is a public-vintage reconstruction and targeted block ablation, not a broader hyperparameter search on this evaluation period. In particular, test room/switching separately from generator pressure, separate exact from fallback versions, and compare SCADA-based pressure with retrospective solved-target pressure. A feature's failure in the aggregate does not disprove its physical relevance; it may be unforecastable, redundant, noisy, mistimed or represented incorrectly.

## 12. Evaluation design and leakage controls

### 12.1 Three evidence tracks

Maintain separate reports for an operational-input track, a conditional/oracle track and a mechanical scenario track. The first uses only admissible issue-time inputs. The second measures value under perfect or specified future fundamentals and can diagnose input uncertainty. The third decomposes a fixed-equation movement or evaluates a hypothetical dispatch path. Never pool their scores or describe mechanical sensitivities as forecast skill.

The original model trained on September 2023–August 2025, whereas detailed topology begins September 2024. Compare a retrained baseline and a topology model on identical eligible timestamps. Do not give the baseline an extra training year in the primary feature ablation, or silently zero-fill missing topology in that year. A longer-history baseline is a useful additional benchmark with its different training sample disclosed.[^1][^24]

The original March–August 2026 test is no longer untouched for feature discovery after the two-year studies and this probe. Retain it as a regression/development assessment. Freeze a final recipe, begin prospective shadow forecasts and evaluate only subsequently matured targets. An initial 8–12-week shadow assessment can validate operation and immediate value; it cannot establish full seasonal performance. A fresh full seasonal cycle requires continued observation.

### 12.2 Chronological folds

Use expanding or rolling training windows with monthly outer evaluation blocks, after sufficient initial history. For a practical retrospective design, use the first approximately nine months to initialise, reserve subsequent contiguous blocks for inner model selection/calibration, and roll forward monthly. Explicitly label early folds as having incomplete seasonal training coverage. Report results over the second full seasonal cycle where available, without claiming independence from prior exploratory inspection.

All preprocessing, candidate/group selection, basis knots, coefficient thresholds, event reference thresholds, category encodings, calibrators and ensemble weights are fitted within the corresponding training/inner-validation period. Training target windows and event recovery windows must finish before the next evaluation partition. Purge crossing samples based on the actual maximum label horizon; a nominal random train/test split or unexplained seven-day gap is not enough.

For stacked models, generate upstream predictions through nested chronological folds and train the downstream flow model only on those predictions. At evaluation, fit upstream models only on eligible historical data. Unknown families and newly commissioned units receive explicit fallbacks, not weights calculated from later exposure.

Use the repository's fixed UTC+10 NEM clock with no daylight-saving shift. Reconcile the study's inclusive five-minute grid ending 23:55 with the model's interval-ending half-hour convention and `(start,end]` filtering. A half-hour needs six distinct valid component intervals. Do not synthesise a missing boundary interval or accidentally assign a preceding-day interval to the next season in one report but not another.[^2][^24]

### 12.3 Controlled experiment matrix

| Experiment | Change from matched baseline | Question answered |
|---|---|---|
| E0 | Simple observed-state model and fixed existing LightGBM benchmark | How strong are mandatory comparators on the same data? |
| E1 | Reported room, capacity momentum and setter age | Does richer current state help without generator data? |
| E2 | Candidate gaps/counts and switching | Is competing-equation information valuable? |
| E3 | Signed generator tightening/relief | Does equation-aware pressure add beyond state? |
| E4 | Exact-version and completeness gating | Does reliability explain gains/losses, especially QNI? |
| E5 | Group decomposition | Is unit composition useful beyond net pressure? |
| E6 | Predicted generator changes versus persistence | Can future pressure actually be anticipated? |
| E7 | Operational fundamentals and optional market context | Does demand/supply context improve interior flows? |
| E8 | Out-of-fold limit/event stacking or AEMO residual correction | Do upstream forecasts improve flow accuracy? |
| E9 | Additive or limited regime interactions | Can a small nonlinear extension resolve residual structure? |
| E10 | Boosting challenger | Is additional complexity justified after simpler alternatives? |

Run single-block additions and selected removals, not only cumulative additions. Include a negative-control experiment with temporally displaced or shuffled training pressure, using blocks that preserve broad seasonal structure. It should not retain the same claimed gain. Do not use a favourable negative-control result to rescue a feature whose primary comparison fails.

### 12.4 Metrics and uncertainty

For continuous targets report MAE, RMSE, signed bias and error quantiles by connector, target and lead. Avoid MAPE for signed flow and near-zero limits. Report unweighted connector comparisons and explicitly weighted operational objectives separately. Standardising targets for training does not justify hiding errors in physical MW.

For probabilistic forecasts begin with simple regression residual intervals by connector/lead band, followed by linear/spline quantile regression if conditional uncertainty matters. Compare pinball loss, interval coverage and width together. Weighted interval score penalises both excessive width and observations outside the interval; its use is supported by the forecast-evaluation literature.[^25]

For events report Brier score, log loss, calibration curves, precision-recall, incident recall at fixed false-alert budgets and warning time. For flow direction report balanced class metrics with the near-zero class explicit. Compare contraction severity, time-to-trough and recovery errors without selecting cases based only on model success.

Use paired errors on the same origin/delivery rows and block resampling to reflect dependence. Start with seven-day origin blocks and sensitivity to longer blocks; report event-cluster uncertainty for incident scores. Multiple forecasts of one event and simultaneous QNI/VNI responses share information. Thousands of origin/lead pairs are not thousands of independent extreme episodes.

Calibration must use matured residuals only. A rolling recalibrator can adapt to drift, but sparse regimes need pooled fallback. Time-series conformal methods such as EnbPI provide relevant methodology; they do not automatically guarantee exact conditional coverage for arbitrary NEM regime shifts or joint seven-day paths.[^26] Report marginal coverage separately from any path-level guarantee.

## 13. Seasonal, diurnal and event diagnostics

Use the two existing seasonal cycles as explicit test strata and mechanism evidence. Compare each season-year separately before pooling. A winter-versus-summer difference may reflect outages, new capacity or equation revisions rather than a recurring seasonal relationship. Fit seasonal normalisations on historical training data only.

Report hour-of-day and weekday/weekend performance, with special attention to sunrise, evening renewable decline and high residual-demand ramps. Cross-tabulate these with constraint family and generator group. Use shrinkage or pooled estimates when cells are small; do not construct hundreds of independent hour × season × equation regressions.

For each important event, rebuild an issue-time view showing what was known 180, 60 and 30 minutes before onset. Compare the original atlas's retrospective explanation with the forecast model's inputs and warning. A correct explanation after the event is not evidence of an advance warning.

The final forecast-assessment HTML should include these views:

| View | Contents and interpretation |
|---|---|
| Error by lead | Persistence, simple baseline, topology model and optional boosting; paired uncertainty |
| Feature ablation matrix | MW change for every connector/direction/horizon, including losses |
| Calibration panel | Coverage versus width, probability reliability and event base rates |
| Seasonal/diurnal matrix | Error, onset recall and false alarms, with sample counts and separate years |
| Event timeline | Actual flow, reported limits, issue-specific forecasts and contraction markers |
| Generator contribution panel | Gross tightening/relief by group and leading DUIDs; observed versus forecast movement |
| Equation timeline | Setter/version, runner-up gap, invocation changes, RHS/other-LHS/switch components |
| Secondary market panel | Price, demand, renewables, coal availability/status, outage evidence and temperature |
| Failure cases | False alarms, missed onsets, reversals without contractions, and bad-version cases |

All event graphs must identify forecast origin, delivery time, data availability and whether a series is an observation, forecast or retrospective decomposition. Include a fixed selection of largest events, randomly sampled incidents, false positives and false negatives. For generator rankings, show both frequency and effect size with exposure denominators; preserve relief and uncertain attribution.

This methodology report contains study tables and a bounded model probe. The forecast-performance graphs above are specified deliverables of the implementation study, not claims that a new full operational study has already run.

## 14. Repository implementation plan

| Work package | Existing integration point | Proposed deliverable | Completion gate |
|---|---|---|---|
| A. Evidence baseline | Study reports, `results/`, `docs/data/` | Frozen input/result manifest and discrepancy audit | Baseline counts and sign/time conventions reconcile |
| B. Source availability | `constraint_ingest.py`, `constraint_longitudinal.py`, benchmark downloader | Source-specific issue/availability registry and scoped acquisition manifest | No future publication enters an origin |
| C. Reliable constraint state | `constraint_features.py`, standing joins | Versioned sparse candidate state and quality audit | Known fixed-equation examples reconcile; failures explicitly flagged |
| D. Compact feature interface | `prepare.py`, `model.py::Design` | Proposed `forecast_state.py` and feature schema | Identical transformation for historical replay and live origins |
| E. Simple model family | `model.py` | Proposed `simple_models.py`: ridge, additive and logistic models | Matched chronological baselines and saved coefficients |
| F. Event targets | `event_atlas.py` | Proposed forecast-label module with past-only thresholds | Onsets, ongoing states, boundaries and missing labels tested |
| G. Forecast evaluation | `backtest.py`, `aemo_benchmark.py` | Nested folds, ablations, event and probabilistic score tables | Full losses and common-sample comparisons retained |
| H. Reporting | Existing HTML builders, `report.py` | Forecast assessment and linked event pages | Every displayed metric traced to a result table |
| I. Operational trial | `scenario.py`, `ui.py` | Explicit observed/forecast/scenario inputs and fallback status | Shadow forecasts generated before outcomes, with immutable logs |

Module names marked proposed are design choices, not implemented files. Keep research scripts separate from production model loading. Replace cache-by-file-existence with manifests that include source hashes, feature schema, model settings, split boundaries, package versions and code revision. A stale model must not load after the feature meaning changes.

Use a shared connector configuration for ID, direction labels, adjoining regions, candidate eligibility, generator groups and known regime changes. Avoid hardcoding VNI names in QNI equations or charts. Preserve an adapter for the current five-target prediction interface and add event outputs under separate fields.

### Meaningful tests

Test coefficient and direction algebra with synthetic upper/lower/equality cases and whole-equation rescaling. Test generation, scheduled load and bidirectional-unit mapping using dated source records. Check that a missing generator term never silently becomes zero pressure and that an unobserved future unit does not enter the feature dictionary.

Test origin leakage by changing data strictly after an origin and asserting that its inputs/prediction remain unchanged. Test late publications, revised standing versions, announced future invocations, unknown categories and source-specific release lags. Test train-only group selection and complete separation of future targets from scenario inputs.

Test six-interval aggregation, midnight/month/season boundaries, negative limits, crossed envelopes, event cooldown, ongoing-event labels, missing target windows and intervention/pricing run separation. For stacked models, assert every training prediction came from a model that did not train on that target window.

Test the storage guard with oversize headers, streamed bytes exceeding the allowance, insufficient free space, interrupted extraction and restart. Verify a successfully compacted batch can be resumed without redownloading or deleting retained evidence. Run a small end-to-end fixture before any two-year rebuild.

## 15. Priorities, decision gates and deployment

First finish the provenance and QNI discrepancy audit, then build the public-data state and simple model comparison. Do not wait for complete weather/outage enrichment before testing network state. Conversely, do not infer that an unknown future outage is predictable just because its retrospective constraint set is present in the archive.

Use sequential gates rather than a fixed promise of completion time:

1. **Data gate:** usable source availability and version completeness are measured; all failed cases have fallbacks.
2. **Feature gate:** signed pressure and candidate competition pass algebra, timing and reconstruction checks; selected feature blocks improve matched development tests.
3. **Model gate:** a simple candidate competes against persistence and admissible AEMO forecasts; event metrics and calibration meet predeclared objectives.
4. **Complexity gate:** add boosting only when local evidence demonstrates material, stable benefit over the best simple alternative.
5. **Operational gate:** shadow forecasts run reliably, arrive before outcomes and retain performance after actual input uncertainty and missingness are included.

A proposed practical acceptance contract is no more than 2% deterioration in overall flow MAE while materially improving the primary contraction-warning objective, or at least 5% flow MAE improvement without material deterioration in warning quality. Choose the primary objective and tolerances before the next evaluation. Sparse seasonal/event slices require uncertainty disclosure rather than automatic pass/fail claims.

Monitor feature missingness, stale sources, unknown equation families, sensitivity distributions, prediction bias, event base rates and interval coverage. Fall back to the simplest available admissible model when quality fails. Update calibrators only after targets mature and retrain on a documented schedule or drift trigger, with rollback to the previous manifest.

AEMO's current Project EnergyConnect information targets physical loop operations from 1 October 2026 and settlement arrangements from 1 November 2026, subject to readiness and changes. It also distinguishes loop-flow equations from reported interconnector limit setters.[^27] This makes post-study structural change a specific concern for VNI. Tag actual commissioning/formulation changes as they occur, retain new families and avoid assuming the historical six-connector configuration is permanent.

## 16. Research evidence log and unresolved questions

The evidence base combines repository findings, a reproducible local-data probe, primary market documentation, academic studies and an operator's research programme. Research access was on 13 September 2026. Repository source observations refer to revision `820450d010be604f533902a6aba90da6bcbeaccc` plus the explicitly identified new research artifacts. This log records scope and decisions; it does not imply a systematic review of every published paper.

| Research area | Material examined | Finding retained | Limitation or next action |
|---|---|---|---|
| Existing forecasting | Model, preparation, protocol and executed backtest | Current model is conditional on actual future drivers; useful benchmark but not live skill | Rebuild operational-input track |
| VNI/QNI mechanisms | Two-year studies and event atlases | Signed pressure, switching and group exposure are useful feature hypotheses | No causal dispatch replay; selected cases are not the training population |
| Local model evidence | 48 monthly feature partitions and targets | Ridge gains are mixed; extra spline flexibility is often harmful | No publication-vintage proof or independent final holdout |
| Market definitions | AEMO limit reporting and constraint FAQ | Reported limits depend on a dispatch solution and other terms | Historical specification must be checked against current changes |
| Public availability | AEMO SCADA, dispatch and predispatch descriptions | Public SCADA differs from private/next-day unit results | Confirm per-field historical entitlement and release policy |
| Simple statistical models | Intertie ARIMA thesis; LEAR benchmark; additive forecasting paper | Strong reason to test parsimonious models first | Different regions/tasks; no transferable uplift percentage |
| Complex models | Tabular benchmark, TFT, European surrogate preprint | Plausible later challengers | No direct evidence requiring boosting or neural models here |
| Industry practice | NESO congestion programme and AEMO changes | Forecast-time information and network-data quality are central | GB findings are conceptual, not NEM validation |
| Uncertainty | Proper interval scoring and time-series conformal research | Assess calibration jointly with sharpness and dependence | No unconditional guarantee under structural change |
| Weather | Original-run versus stitched historical forecast documentation | Use issue-specific forecasts for historical replay | Coverage and release delay need per-model verification |

The exact reason for QNI's larger reconstruction errors remains unresolved. So do the operational availability of every desired unit/FCAS field, full historical outage-schedule vintages, and the incremental value of the proposed pressure block under strict public inputs. These are specific implementation investigations, not reasons to assume the mechanisms are absent.

No new boosting, graph or sequence model has been trained in this research. No bulk market download or production-model replacement occurred. The new numerical probe is limited to retained data and simple models; the full operational methodology remains proposed work.

## Sources

Numbered references below provide the source inventory for both the Markdown and HTML editions. Local links identify repository records; ignored data required to rerun the numerical probe remain on the research workstation, with hashes in its evidence file. Web publication dates are taken from the documents when identifiable, not search-engine crawl dates.

[^1]: INTERFLOW repository. [Current model implementation](../nemic/model.py), `Design`, `features`, training and estimator functions. Source revision `820450d`, inspected 13 September 2026. Local primary implementation evidence.
[^2]: INTERFLOW repository. [Preparation implementation](../nemic/prepare.py) and [connector definitions](../nemic/common.py). Source revision `820450d`; signs, aggregation, demand definition and run handling. Local primary implementation evidence.
[^3]: INTERFLOW. [Executed conditional backtest](../BACKTEST_REPORT.md), executed 11 September 2026, results and AEMO comparison. Local saved experiment; no claim of independent reproduction of its entire training run in this research.
[^4]: INTERFLOW. [Constraint feature implementation](../nemic/constraint_features.py) and [corrected VNI feasibility pilot](CONSTRAINT_FEATURE_PILOT.md), 11 September 2026. Local prototype and one-month development evidence.
[^5]: INTERFLOW. [VNI two-year constraint study](VNI_TWO_YEAR_CONSTRAINT_STUDY.md), September 2024–August 2026 population. Local saved report and linked aggregate evidence, inspected 13 September 2026.
[^6]: INTERFLOW. [QNI two-year constraint study](QNI_TWO_YEAR_CONSTRAINT_STUDY.md), September 2024–August 2026 population. Local saved report and linked aggregate evidence, inspected 13 September 2026.
[^7]: INTERFLOW. [VNI two-year event atlas](VNI_TWO_YEAR_EVENT_ATLAS.md), method `1.1-event-atlas-1`, September 2024–August 2026. Local selected-case accounting and population screening.
[^8]: INTERFLOW. [QNI two-year event atlas](QNI_TWO_YEAR_EVENT_ATLAS.md), method `1.1-event-atlas-1`, September 2024–August 2026. Local selected-case accounting and population screening.
[^9]: AEMO/NEMMCO. [Interconnector Limit Setter Reporting Changes—Business Specification](https://www.aemo.com.au/-/media/files/electricity/nem/security_and_reliability/dispatch/policy_and_process/interconnector-limit-setter-reporting-changes.pdf), version 1.02, effective 1 July 2005, especially Appendix 1, pp. 13–14. Historical primary definition; current reform changes must be checked separately.
[^10]: AEMO. [Constraint Frequently Asked Questions](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq), undated live page, accessed 13 September 2026. LHS/RHS, feedback, constraint sets and binding definitions.
[^11]: AEMO. [MMS Data Model: DISPATCH_UNIT_SCADA](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_123.htm), undated table documentation, accessed 13 September 2026. Public visibility and start-of-interval SCADA definition.
[^12]: AEMO. [MMS Data Model: PREDISPATCHLOAD](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_274.htm), undated; [Data Model v5.2 technical specification](https://di-help.docs.public.aemo.com.au/Content/Data_Model/EMMS_-_Technical_Specification_-_Data_Model_v5.2_-_May_2023.pdf), May 2023, section 6.9.2; [Electricity Data Model Package Summary v5.4](https://visualisations.aemo.com.au/aemo/di-help/Content/Data_Model/Electricity_Data_Model_Package_Summary_54.pdf), 7 October 2024, dispatch visibility. Historical specifications support conservative access treatment; current per-feed access remains an implementation audit.
[^13]: Open-Meteo. [Historical Forecast API documentation](https://open-meteo.com/en/docs/historical-forecast-api), live documentation, accessed 13 September 2026. Distinguishes historical weather, stitched forecasts, previous runs and individual runs; model coverage varies.
[^14]: Piyush S. Paretkar. [Short-Term Forecasting of Power Flows over Major Pacific Northwestern Interties: Using Box and Jenkins ARIMA Methodology](https://vtechworks.lib.vt.edu/server/api/core/bitstreams/1eeef9f3-ca78-43e5-9f14-00e4fca988fb/content), Virginia Tech master's thesis, 2008. Direct intertie forecasting precedent; historical non-NEM evidence.
[^15]: Jesus Lago, Grzegorz Marcjasz, Bart De Schutter and Rafał Weron. [Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark](https://arxiv.org/html/2008.08004v2), preprint revision 21 December 2020; published in Applied Energy, 2021. LEAR and evaluation methodology; adjacent price-forecasting task.
[^16]: Pierre Gaillard, Yannig Goude and Raphaël Nedellec. [Additive models and robust aggregation for GEFCom2014 probabilistic electric load and electricity price forecasting](https://doi.org/10.1016/j.ijforecast.2015.12.001), International Journal of Forecasting 32(3), 1038–1050, 2016. Publisher-indexed abstract reviewed; direct full-text fetch unavailable. Implementation references: scikit-learn [SplineTransformer](https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.SplineTransformer.html) and [Ridge](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html), live documentation accessed 13 September 2026. Installed versions are recorded in the local probe manifest.
[^17]: National Energy System Operator. [Forecasting the risk of congestion](https://www.neso.energy/about/innovation/our-innovation-projects/forecasting-risk-congestion), undated project page, accessed 13 September 2026. Industry programme scope and data lessons, not a measured QNI/VNI comparison.
[^18]: Leo Grinsztajn, Edouard Oyallon and Gaël Varoquaux. [Why do tree-based models still outperform deep learning on typical tabular data?](https://proceedings.neurips.cc/paper_files/paper/2022/hash/0378c7692da36807bdec87ab043cdadc-Abstract-Datasets_and_Benchmarks.html), NeurIPS Datasets and Benchmarks, 2022. General tabular evidence; not a comparison against this repository's simple engineered model.
[^19]: Robert Gaugl, Eloy Insunza, José Portela and Sonja Wogrin. [Surrogate Modeling of Interconnector Flows: A Machine Learning Alternative to Full-Scale Power System Simulations with Application to Cross-Border Electricity Exchange](https://arxiv.org/abs/2606.03475), preprint, 2 June 2026. European simulated planning flows; peer-reviewed status not established by the reviewed record.
[^20]: LightGBM contributors. [Parameters](https://lightgbm.readthedocs.io/en/stable/Parameters.html), live 4.7.0 documentation reviewed 13 September 2026. Regression, classification and quantile capabilities; no claim that the live documentation version matches every local experiment.
[^21]: Bryan Lim, Sercan Ö. Arık, Nicolas Loeff and Tomas Pfister. [Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting](https://arxiv.org/abs/1912.09363), preprint 2019/revised 2020; International Journal of Forecasting, 2021. Later sequence-model option, not local performance evidence.
[^22]: INTERFLOW. [Event detector implementation](../nemic/event_atlas.py), `detector`, and [general event-analysis methodology](INTERCONNECTOR_EVENT_ANALYSIS_METHODOLOGY.md). Source revision `820450d`, inspected 13 September 2026. Exact retrospective threshold and onset rule.
[^23]: INTERFLOW. [Simple-model research evidence](data/qni_vni_simple_model_research.json), generated 13 September 2026 by [the bounded research script](../scripts/research_simple_models.py). Contains all model cells, 49 local input-file hashes, configuration and limitations; no downloads. Local primary exploratory evidence.
[^24]: INTERFLOW. [Backtest protocol](BACKTEST_PROTOCOL.md), documented 11 September 2026. Exact partitions, input availability limitations, lead weighting, bootstrap and AEMO alignment.
[^25]: Johannes Bracher, Evan L. Ray, Tilmann Gneiting and Nicholas G. Reich. [Evaluating epidemic forecasts in an interval format](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1008618), PLOS Computational Biology 17(2), 2021. Proper interval scoring methodology; principles applied here to energy forecasts.
[^26]: Chen Xu and Yao Xie. [Conformal prediction interval for dynamic time-series](https://proceedings.mlr.press/v139/xu21h.html), Proceedings of ICML, PMLR 139, 2021. Time-series uncertainty methodology, with assumptions and limits.
[^27]: AEMO. [Project EnergyConnect market integration: Frequently asked questions](https://www.aemo.com.au/initiatives/major-programs/nem-reform-program/nem-reform-program-initiatives/project-energyconnect-market-integration-project/frequently-asked-questions), live page accessed 13 September 2026. Planned October/November 2026 changes and distinction between loop equations and limit setters; dates remain subject to AEMO updates.
