# Implementation plan for diurnal and NOS forecasting experiments

## 1. Outcome, scope and fixed decisions

Deliver a reproducible VNI/QNI research campaign that determines whether delivery-time specialization and as-of network-outage information improve directional limits and advance contraction warnings. The final handoff must include a report covering every evaluated model, model-by-model results, actual-versus-forecast limit charts with MAPE-first metrics tables, feature importance and SHAP decompositions, an assessment against fundamentals, an explicit model-choice verdict, and trained model bundles with exact parameters and inference instructions. Use chronological hyperparameter optimization, separate accuracy and risk selections, auditable feature/data lineage and matched historical scorecards. The supporting evidence and literature are in [the research report](QNI_VNI_DIURNAL_NOS_RESEARCH.md). This revision supersedes its earlier MAE-only reporting recommendation; percentage-metric eligibility is defined below.

This is an implementation specification. The modelling changes and campaign described here have not been executed. Existing v1 artifacts remain the historical reference.

| Decision | Specification |
|---|---|
| Connectors | VNI `VIC1-NSW1` and QNI `NSW1-QLD1` |
| Primary numeric outcomes | `export_tight`, `import_tight`: minimum five-minute directional limits in the delivery half-hour |
| Secondary outcomes | Mean `export`, mean `import`; flow as a compatibility diagnostic |
| Primary horizons | Existing five representative leads at 0.5, 1, 2, 4 and 6 hours |
| Extended horizons | All existing 14 leads to seven days; preserve full 336-step forecast output capability |
| Risk outcome | Existing sharp contraction onset within 30–120 minutes; additionally score 100/200/400 MW drops |
| Clock | Fixed UTC+10 NEM time; store receipt/publication timestamps in UTC; no Sydney/Melbourne daylight-saving conversion |
| Reporting periods | [00:00,06:00), [06:00,10:00), [10:00,16:00), [16:00,21:00), [21:00,24:00) |
| Warning budget | Three false alarms/day summed across both directions of each connector; no separate period budgets |
| Compute | Existing two model workers, two threads/worker, serial downloads, shared 10 GB additional-artifact cap and 20 GB free-disk reserve |
| Deployment | Historical experiments do not activate learned live models automatically |

Do not extend this campaign to other interconnectors, individual-generator forecasting, full network simulation, optimized time-bucket boundaries or a new dashboard architecture. Those can be separate follow-on decisions after the principal questions are answered.

## 2. Establish the baseline and repair measurement contracts

Create a new configuration and campaign, `vni_qni_diurnal_nos_v2`, using the existing experiment framework. Keep schema v1 readable; introduce a schema v2 config with explicit calendar, outage, selection and information-policy sections. Store all new trial outputs under the new campaign root. No historical model bundle or score is overwritten.

1. Reproduce the period table in the research report using saved rolling predictions. Record row counts, exact leads, target definitions, input hashes and aggregation code hash. Retain the five original bucket definitions and delivery-ending timestamp convention.
2. Centralize directional-limit normalization: export capacity is raw `EXPORTLIMIT`; import capacity is negative raw `IMPORTLIMIT`. Apply the same conversion to preparation, live recording and AEMO benchmark adapters. Preserve forced-direction negatives. Audit existing adapters before changing them, and mark affected old shadow scores obsolete without modifying their source forecasts.
3. Make delivery support explicit: an interval ending at D consists of five-minute endpoints D−25, D−20, …, D. Targets require all six observations. Numeric period labels use D for historical comparability; calendar and outage exposure may aggregate across those six endpoints.
4. Enforce `available_at <= origin` for inputs and label maturity before each fitting/selection/calibration cutoff. For retrospective observations, retain the conservative 30-minute delay as an explicit assumption. Never assume shifting by one row establishes publication availability.
5. Keep existing fold boundary dates. Recompute any affected eligibility masks, and rerun v2 baseline models on those same masks before measuring new-feature gains. Distinguish exact legacy reproduction from the corrected comparison baseline.
6. Replace one-random-lead-per-origin training with all configured leads within each band, weighting rows so each origin contributes total weight one. Apply this change equally to v2 controls and challengers. Preserve seed 741. Test the sampling change as its own bridge comparison against v1 before claiming calendar/NOS gains.

The baseline ladder is persistence, seasonal daily/weekly persistence, ridge history, ridge context and the existing validation-selected candidate/blend policy. AEMO original-issue forecasts are a secondary benchmark only on compatible, commonly available observations. Do not treat a half-hour AEMO forecast as a forecast of the tightest five-minute limit without explicitly constructing and qualifying that target.

**Exit condition:** period reproduction agrees within rounding; sign and time-support tests pass; the corrected baseline has a complete eligibility report, or each unavailable cell has an explicit reason.

## 3. NOS ingestion, temporal storage and exposure mapping

### 3.1 Source and archive strategy

Add a dedicated outage adapter under `nemic/experiments`, reusing the existing store, download verification and table parsing conventions. Extend the parser's registered identities for both `NETWORK_OUTAGEDETAIL` and `NETWORK_OUTAGECONSTRAINTSET`; merely requesting an unregistered table is insufficient because the existing parser prefilters known prefixes. Read a source-versioned outage-status dictionary separately.

Inventory every public current/archive Network report before bulk acquisition. Parse weekly outer archives and inner report timestamps, compute hashes and deduplicate identical report content. The sampled August 2025 archive confirms feasibility, not complete coverage. Record a half-hour coverage calendar, late/duplicate publications, missing reports and schema changes.

Retrieve one archive at a time, inspect recursive expanded sizes before extraction, retain compact changes plus report membership, and remove only verified campaign-owned scratch files. Do not retain every unchanged outage row from every snapshot. Budget recursively expanded bytes as well as compressed bytes; an 85 MB outer bundle contains many compressed inner reports. Preserve source URL, outer/inner hashes, schema, row counts and parse audit even after scratch cleanup.

Prefer intraday snapshots for advance-information experiments. Monthly MMSDM tables may supplement dictionary/version audits and a separate retrospective track. They must never silently fill earlier as-of rows with later revised schedules.

### 3.2 Minimal data interfaces

Add the following versioned internal tables; these are the public contracts between acquisition, feature building and model training:

| Table | Required content |
|---|---|
| `outage_reports` | Report ID, source URL, outer/inner hash, header/filename generation time, actual receipt time when available, assumed availability time, schema, completeness and row counts |
| `outage_versions` | Report/change validity range, outage ID, equipment composite key, optional element ID, scheduled/actual times, raw status, resubmission link, recall fields, source version and row hash |
| `outage_set_versions` | Report/change validity range, outage ID, constraint-set ID, expected start/end dispatch intervals, row hash |
| `constraint_exposure_versions` | Set membership and equation version/effective window, connector, eligible direction(s), limit family, provenance and mapping quality |
| `outage_features` | Connector, origin, lead, delivery end, feature values, information track, source/report IDs, coverage and fallback reason |

Raw identifiers stay strings. Preserve `ELEMENTID` where present; missing legacy fields are null. Do not key a complete outage history solely by `OUTAGEID`, because one booking may contain several equipment rows and changing schedules. Retain both raw composite keys and explicitly linked resubmission chains.

Provide `outages_asof(origin)` and `build_outage_features(origins, leads, connector, information_policy)` interfaces. Joining late-added set links must obey the same information cutoff as outage details. Fingerprints include schemas, row hashes, mapping versions, availability policy and all feature code dependencies.

### 3.3 Three information tracks

* **Retrospective:** monthly/reconstructed topology or unverified publication history. Useful for mechanism and feature-potential analysis; never labelled live eligible.
* **Archive-vintage simulation:** original intraday report snapshots with generation time plus a default 30-minute allowance. Audit filename/header agreement and run 5- and 60-minute timing sensitivities. This is an assumption-based historical simulation, not proof of actual receipt.
* **Prospective:** actual first-received timestamps for every admitted source and immutable forecasts. Only this track can establish observed operational availability.

The information track of a combined row is no stronger than its least-verifiable feature block. Valid NOS vintages do not turn unverified historical pressure features into operational inputs. Maintain an archive-NOS + observed-history control separately from archive-NOS + retrospective reconstructed-context experiments.

A report is stale when its assumed/actual availability is more than 90 minutes before origin. Keep stale schedules for diagnosis, but route prediction to the no-NOS control. A missing or incomplete report means unknown exposure, not zero outages. Preserve report absence explicitly; only infer row removal from a validated complete snapshot, and do not equate removal with completed restoration.

### 3.4 Mapping and status rules

Join outage → expected set → versioned member equation → connector factor/inequality. Start with direct connector relationships and mapped network families. Use NSW, Victoria and Queensland as contextual region groups; include a directly mapped outage regardless of its region. Keep unmatched regional outages in a separate contextual count, never invent a direct connector link from a name.

Resolve equation metadata with both effective time and availability time. For retrospective-only standing data, label mapping accordingly. Do not use future realised setters or full-period impact rankings to select future candidate equations.

Statuses remain categorical. Withdrawn, completed and replaced bookings are excluded from scheduled active exposure as of the applicable snapshot; withdrawal-request, unlikely-to-proceed and unknown states remain separate uncertainty features. Explicit resubmission successors supersede old scheduled exposure when the successor is visible; preserve unresolved chains as uncertain. Keep primary and secondary-equipment exposure separate.

`ACTUAL_*` values only affect forecasts after they appear in an admissible snapshot. Carry an overdue flag when a planned end passes without a known restoration, rather than asserting the equipment is back. Preserve invalid/sentinel dates and negative recall values in raw storage, but mask them from numeric lead/duration calculations and add validity indicators. Retain both day/night recall values until an authoritative clock definition is obtained; no invented day/night switch is permitted.

### 3.5 Initial feature blocks

Implement named blocks with stable column definitions. Counts refer to distinct outage chains or distinct sets/equations, not the number of duplicated equipment/link rows.

| Block | Initial columns/operations |
|---|---|
| O1: current exposure | Relevant active scheduled chain count, distinct primary assets, secondary assets, mapped sets, unknown/unmatched count |
| O2: future schedule | Delivery overlap fraction across six five-minute endpoints; starts and ends before delivery; starts/ends in next 30/120/360 minutes; clipped hours to next relevant start/end; new/ending mapped-set counts |
| O3: constraint families | Upper/lower eligible equation counts; thermal, voltage/transient stability, other/unknown family exposures; current-setter-family overlap; newly introduced family indicator |
| O4: revisions | Changes in start/end over previous 24 hours, latest shift in minutes, status-change count, minutes since latest visible revision, booking age, resubmission, overdue restoration and both recall values |
| OQ: quality | Source age, admissible snapshot flag, mapping coverage, unknown-status fraction, invalid-date flag, actual-time-known flags |

For equipment schedule times use interval overlap [start,end). For set `STARTINTERVAL`/`ENDINTERVAL`, follow their dispatch-interval semantics and test boundary inclusion explicitly; do not assume the equipment-time rule applies to both. When link intervals are absent, fall back to the booking window with a provenance flag. Intersect explicitly present equipment and set windows for joint exposure; preserve disagreement as a quality feature.

Build interactions only for total mapped delivery exposure and newly starting mapped exposure with: own-direction headroom, switch gap, net generator pressure, recent capacity change and the chosen cyclic basis. Do not multiply every sparse field by every period. Implement all named initial blocks within a 64-scalar NOS feature budget before interactions; report actual and expanded design sizes. Do not add individual-outage one-hot columns to fill the budget.

**Exit condition:** snapshot replay and mapping coverage are measured, all negative controls pass, and the data inventory determines eligible folds without examining their forecast errors.

## 4. Model ladder and staged experiments

### 4.1 Common estimator conventions

Numeric models predict a correction to the latest admissible persistence anchor. Use the existing train-only imputation, missingness indicators and scaling. Cyclic basis columns and period indicators must not be clipped using empirical feature quantiles. Build interactions after continuous-feature preprocessing; missingness indicators remain explicit. Retain separate target/direction fits and lead-band models for the principal comparison.

Keep the v1 parameter configurations as reference trials, not the final search space. Optimize every trainable family using the chronological search protocol in §4.4. Use the qualified MAPE objective in §6.1 for the main point-model search, with a separately labelled MAE-optimized challenger; use probability loss for classifier hyperparameters. The outer selection partition chooses recipes and policies after inner tuning. Record failed fits and convergence issues.

### 4.2 Calendar candidates

| ID | Candidate | Exact experiment |
|---|---|---|
| T0 | Current calendar control | Existing first daily harmonic and annual/weekend terms |
| T1 | Rich cyclic calendar | Daily Fourier pairs K∈{1,2,3,4}, additive to the same base predictors |
| T2 | Period-interaction ridge | Five fixed periods, shared main coefficients and regularized deviations for capacity change, room, switch gap, own/opposite net pressure and residual-demand context |
| T3 | Smooth interaction ridge | Same driver subset interacted with K∈{1,2,3} Fourier pairs; primary recommended specialist |
| T4 | Shared model + period correction | Ridge residual corrections trained on expanding-month out-of-fold base predictions inside the training partition |
| T5 | Independent period ridge/elastic net | Separate five-period fits on the same predictors; compare hard routing and a fixed 60-minute transition blend |
| T6 | Shared shallow boosting | Existing 7/15-leaf configurations as controls, plus Optuna-tuned boosting with the same feature blocks |

For period deviations seed the search with penalty multipliers {1,10,100} relative to shared coefficients, then optimize within §4.4's bounds. T4 corrections must never be trained on the base model's in-sample residuals or evaluation predictions. Refit its base model after generating chronological training residuals, keeping the residual learner fixed until the next fold.

A period-specific fit needs at least 90 distinct training days, 500 eligible training rows, and 20 selection days with 100 rows. Otherwise fall back to the shared fit and report insufficient support. This is a conservative engineering threshold, not a claim that 500 correlated observations are independent. Do not further split by season or weekday.

For smooth period routing, linearly interpolate adjacent specialists over ±30 minutes around each fixed boundary, including midnight. Train that variant using the corresponding routing weights. Retain hard routing as an explicit diagnostic challenger. Test artificial clock jumps by holding non-calendar features and lead fixed; do not smooth away genuine scheduled network changes.

For the fallback policy blend the specialized forecast with the persistence anchor using period weights from {0,.25,.5,.75,1}. Choose weights on the outer selection partition using the declared metric and MAE guardrails, plus a dimensionless shrinkage penalty: `lambda × mean squared deviation from the shared weight`, with lambda in {0,.01,.1} after dividing metric loss by the shared-policy loss. Use the same boundary blend for weights. Unsupported periods use the shared weight. The no-NOS fallback is independently fitted and selected, not the outage model with unknown outages set to zero.

### 4.3 Controlled campaign sequence

1. **Calendar:** run T0–T6 without NOS for the two primary minimum-limit targets across both connectors and all existing rolling folds. Select calendar families independently within each fold; save the complete trial ranking. Evaluate other horizon bands and mean limits with the selected procedures. Keep fixed-split results separate.
2. **NOS main effects:** use T0 and the fold-selected best of T2/T3 with O1, O1+O2, O1+O2+O3 and O1+O2+O3+O4. Include OQ whenever NOS is used. Refit no-NOS controls over identical eligible training and evaluation populations.
3. **Combined interactions:** compare the best scheduled-NOS recipe with/without the restricted outage × driver/time interactions. Run T6 on the same selected blocks. This directly measures synergy beyond additive calendar and outage effects.
4. **Refinements:** on the selected combined recipe, separately test lead-conditioned aggregate-pressure forecasts, cross-connector partial pooling and recent-data adaptation. Do not attribute their gains to NOS or time of day.

NOS fitting requires 90 distinct covered training days and at least 80% fresh-snapshot coverage within each fitted partition. Existing rolling folds remain unchanged; with snapshots beginning in late August 2025, March 2026 is the first *potential* evaluation month under these rules, subject to the full coverage audit. Earlier folds and the fixed split may be unavailable for NOS training. Mark them unavailable; do not move cutoffs after seeing scores.

Refinement defaults are: pressure predictions conditioned on actual lead and delivery calendar with chronological out-of-fold construction; cross-connector sharing of calendar coefficients with connector-specific network/outage coefficients; and expanding history versus trailing 180/365-day fits. Choose each on selection data. Keep these as individually named ablations so their effects are identifiable.

For novel outage families, use broad physical metadata and an unknown-family indicator. Family-specific learned encodings require at least ten distinct historical outage episodes and chronological out-of-fold estimation; otherwise use the broader family. Raw outage IDs are diagnostic keys, never predictive categories.

Solar elevation and issue-vintage demand/renewable ramps form a later, separately gated operating-state block. Add it only after the core matrix: use a reviewed fixed regional location map for deterministic solar geometry, and original issue vintages for future fundamentals. Future realised demand, solar, weather or generator availability may appear only in a clearly labelled oracle diagnostic. NOS `UNIT` equipment does not substitute for a generating-unit availability feed.

### 4.4 Mandatory chronological hyperparameter optimization

Use Optuna TPE for continuous/mixed searches and exhaustive enumeration for small discrete choices such as fixed routing variants. Persist studies in a campaign-owned SQLite database with one sequential optimization worker per study; run at most two independent studies concurrently. Set sampler seed 741, enqueue legacy/default parameters, and pin the tested Optuna, SHAP and estimator versions in the delivered environment lock. A bounded search finds the best tested configuration, not a proven global optimum. [Optuna TPE documentation](https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html).

Create a separate study for each outer fold, connector, target/direction, horizon band, family, feature recipe, information track and objective. Inside the outer training partition, use its final three non-overlapping seven-day blocks as chronological validation blocks, fitting on earlier observations each time. Purge labels crossing each cutoff and enforce the existing history/support requirements inside each inner fit. If fewer than two blocks qualify, mark HPO unsupported for that fold and use the documented fixed control; do not call it optimized or borrow parameters from later folds.

Fit every imputer, scaler, residual learner, forecast-pressure stage and learned encoding using only the inner training subset. The outer selection partition ranks the tuned families/recipes, followed by the untouched calibration, alert and evaluation partitions. Do not reuse evaluation results for trial proposals, search-range expansion, early stopping or background-sample selection.

| Parameter group | Initial search range |
|---|---|
| Ridge and additive corrections | `alpha` log-uniform 1e-3–1e5; period/interaction penalty multiplier log-uniform 1–1e3 |
| Elastic net | `alpha` log-uniform 1e-5–10 on the existing scaled target; `l1_ratio` uniform .05–.95 |
| Calendar shape | T1 Fourier K=1–4; T3 K=1–3; additive spline knots 4–10 when that family is used |
| Logistic event model | `C` log-uniform 1e-4–1e2; fixed L2 penalty; no arbitrary class weighting or resampling |
| LightGBM | `learning_rate` log .01–.15; `num_leaves` integer 7–63; `max_depth` {-1,3,4,5,6,7,8}; `min_child_samples` log integer 50–1000; `reg_alpha` {0 or log 1e-5–10}; `reg_lambda` log 1e-3–100; `colsample_bytree` .6–1; `subsample` .6–1 with `subsample_freq=1`; 100–1000 trees |
| Boosted point loss | L1 and L2 as named subfamilies, scored using the declared percentage/MW validation objective |
| Quantile models | Tune regularization/smoothing using mean pinball loss across the retained levels; independent calibration remains downstream |

Reject invalid combinations such as leaves above `2**max_depth` for bounded depth. Keep model-specific validity and minimum-support rules fixed. The Bayesian objective averages inner-block losses equally; within blocks retain equal total weight per origin across leads. Save each block's MAPE coverage, MAE, overstatement and timing alongside the objective. Apply the MAE feasibility constraint explicitly when selecting a point trial; no feasible trial means incumbent fallback.

Budget 40 trials for linear/additive families and 80 for boosting per study, including ten startup/default trials. Run the separately labelled MAE-objective comparison for point families with the same budgets. For boosting use early stopping after 50 non-improving rounds on inner validation only. Prune using intermediate completed-block losses after at least ten completed trials and two blocks; do not compare unmatched folds or different metric units. Refit the outer-training model with the median inner best iteration count, then freeze it before outer selection. Linear models do not need artificial epoch pruning.

After the initial search, check whether the best feasible trial lies within 5% of a continuous bound in its sampled scale. Permit one expansion by a factor of ten for penalization parameters, learning rate down to .003/up to .2, leaves up to 127, or tree ceiling up to 2000, only when the relevant boundary is hit. Add at most 20 trials. Retain all trials and original bounds; report unresolved boundary hits. Refine uncertainty around the selected values by reporting the parameter ranges of the best 10% of feasible trials, with a minimum of three trials. These are empirical near-best ranges, not confidence intervals for a true optimum.

Search-space expansion, trial counts and budgets are identical across matched ablations. Log interrupted/pruned/failed trials; resume by fingerprint. Within-study ordering is sequential for reproducibility. Store optimization history, best-trial ID, exact effective parameters, hyperparameter importance, runtime and convergence diagnostics. Hyperparameter importance must be labelled separately from input-feature importance. Resource exhaustion produces an incomplete-study flag, never a claim that optimization completed.

## 5. Contraction and uncertainty models

Retain existing five-minute event detection: positive 30-minute capacity drops, training-fitted monthly 90th-percentile thresholds with the current minimum-sample fallback, grouping of nearby onsets and one-to-one advance-warning matches. Freeze labels before comparing feature recipes. Also retain fixed 100/200/400 MW drops as secondary event catalogues.

Create logistic shared, logistic cyclic-interaction and shallow-boosted event candidates using the same selected feature blocks. Represent the event window with period-membership fractions and cyclic averages across eligible onset endpoints at +30,+35,…,+120 minutes, plus NOS transition flags within that window. Do not route using a realised onset or only the +120-minute clock. Report outcomes by actual onset period for diagnostic scoring only.

Select risk family/recipe on the selection partition using incident recall under the existing joint directional budget, with log loss then simpler model as tie-breakers. Those selection thresholds are provisional. Fit probability calibration only on the separate calibration partition, then tune final directional thresholds on the separate alert partition. Apply one threshold per direction across all periods initially; calendar enters the model, not five independently tuned alarm systems. Keep the 120-minute refractory rule continuous across period and day boundaries.

Compare existing pooled quantile calibration with period-conditioned residual adjustments using the selected numeric model. Require at least 20 distinct calibration days and 200 residuals in a period; otherwise use the target/band pooled adjustment. Retain the current 50%, 80% and 95% intervals, quantile ordering, pinball loss and WIS. Record crossing before any ordering repair and evaluate the issued, repaired intervals.

Adaptive rolling calibration is a separate prospective challenger, updated only when each horizon's outcomes have arrived. Initially use a trailing 60-day residual window and pooled fallback for insufficient support. Its policy is frozen before the confirmation period; it may adapt to matured outcomes but may not reselect itself using confirmation scores. Do not claim per-regime coverage guarantees.

## 6. Scorecards, uncertainty and promotion criteria

### 6.1 Matched scoring

Persist one prediction record per evaluated candidate policy, origin, connector, target and lead; save validation summaries for unselected hyperparameter trials. Records include actual, anchor, prediction, quantiles/probability where applicable, recipe/model version, routing weights, source age, information track and fallback reason.

Use identical target-eligible evaluation rows. Produce both common-source-coverage results and full-population results where missing features trigger fallback. Never let a quality filter remove the difficult rows from the main scorecard. Compare NOS controls using equal training history, not only equal evaluation rows.

Report each connector/direction/target/horizon separately, plus equal-weight mean skill across the four primary connector-direction cells. Show row-weighted MAE as secondary. Period slices, month/season, onset severity, scheduled starts/ends, stable outage periods, no mapped outage, unknown mapping and unseen families receive counts and uncertainty.

Display numeric metrics in this order: **MAPE (%), MAE (MW)**, followed by RMSE, bias, P95 absolute error, skill against the corrected incumbent/persistence, and overstatement measures. Risk measures remain incident recall at budget, false alarms/day, warning lead, precision, Brier score and log loss; MAPE is not a classification metric. Capacity overstatement uses positive `prediction − actual` after directional normalization.

Define ordinary MAPE as `100 × mean(abs(prediction − actual) / abs(actual))`. It is undefined at exactly zero and unstable near zero. Never silently replace zero with machine epsilon, cap errors, or drop difficult outcomes from MAE/risk scoring. Report ordinary MAPE on nonzero observations, with its nonzero denominator count, and label the full-population ordinary MAPE undefined if zero observations occur. Negative-limit rows use an absolute denominator and receive a separate forced-direction slice.

The headline and optimization percentage metric is explicitly labelled **MAPE, |actual| ≥50 MW**. Show its eligible count and coverage beside it, plus 25/100 MW threshold sensitivities. This is a conditional MAPE, not full-population MAPE. Fix the 50 MW threshold before fitting; all models use the same actual-based eligibility mask. Make near-zero/zero counts, their MAE and their overstatement rates visible alongside the headline. This avoids hiding precisely the contractions the models should handle. The numerical concern is documented in [scikit-learn's MAPE reference](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_absolute_percentage_error.html).

Use qualified MAPE for optimization/selection only when every applicable inner validation block has at least 100 eligible rows and 80% percentage-metric coverage. Determine this once from targets before the study; otherwise use MAE for that study and label the reason. Main point-model selection minimizes the qualified MAPE subject to full-population MAE being no more than 2% worse than the matched incumbent; retain an MAE-optimized comparison. Metric objectives, eligible populations and constraints cannot change between trials. Preserve conditional incident MAE, WIS and interval coverage/width.

For warning-rate denominators, use eligible observation exposure in 24-hour equivalents: eligible half-hour issue count /48. Also show the legacy distinct-calendar-day denominator for reconciliation. Apply the exposure convention to controls and challengers alike, and use common directional eligibility when enforcing the joint budget. Data gaps cannot create apparently cheap alarms by counting a partially observed day as a full day.

Retain exact lead results. The first-band pooled score averages five representative leads and must not be labelled performance at every half-hour lead. Evaluate all 336 curve steps at the first eligible issue of each evaluation day for shortlisted finalists, and report horizon-boundary jumps separately from time-period boundaries.

### 6.2 Statistical comparison

Use 2,000 paired moving-block bootstrap replicates with seven-day calendar blocks, retaining all directions, leads and candidates together. For incident summaries attach the complete match result to incident onset day and unmatched alarms to issue day; never rematch duplicated synthetic timelines. Repeat with 14-day blocks. Run leave-one-major-outage-chain-out influence summaries as diagnostics to identify gains dominated by a single episode.

For confirmatory numeric claims, use a prespecified Holm correction across four primary connector-direction cells against each of the two baselines. Use a separate two-connector family for risk claims. Report effect sizes and paired intervals; exploratory period/family slices are labelled exploratory. No fixed-plus-rolling pooling, row-level independent bootstrap or post-evaluation model replacement is permitted.

### 6.3 Explicit default gates

These are proposed engineering thresholds, frozen before the new campaign; they are not literature-derived universal cutoffs.

| Selection | Required evidence |
|---|---|
| Accuracy finalist | At least 5% first-band minimum-limit qualified-MAPE improvement over the corrected incumbent; beats persistence on the same metric; full-population MAE no more than 2% worse; positive paired improvement evidence after the declared multiplicity rule. Where the prespecified MAPE support rule fails, apply the 5% improvement and baseline comparison to MAE and label the fallback |
| Accuracy guardrails | No more than +1 percentage point in either 100/200 MW overstatement rate; no more than 2 pp loss of incident recall at the same budget; no more than 5% MAE worsening in a period with at least 30 evaluated days |
| Risk finalist | At least +10 pp incident recall over the incumbent warning policy at ≤3 false alarms/day per connector across both directions; no direction loses more than 2 pp recall |
| Risk guardrails | Associated minimum-limit forecasts deteriorate by no more than 2% MAE; no more than +1 pp overstatement-rate deterioration; no worsening of first-band Brier score |
| Interval gate | WIS no more than 2% worse and nominal 80/95% coverage shortfall no more than 2 pp worse than the matched control; prospective overall coverage must also reach at least 77%/92%; always display absolute coverage |

Apply gates per primary target cell for point forecasts and per connector for the combined risk policy. Retain a mixed selection where one direction or horizon benefits and another does not. The point and event heads can come from different models. A budget tuned in an earlier partition is not a guarantee of a future hard cap; report held-out burden and reject a promotion if it exceeds the criterion.

No tradeoff is hidden in a single blended score. If no candidate passes, retain the incumbent/persistence policy and document whether the evidence is negative or inconclusive.

## 7. Verification and acceptance tests

| Area | Required scenarios |
|---|---|
| Sign/targets | Positive and negative raw import/export limits; forced direction; incomplete six-point half-hour; benchmark and shadow normalization parity |
| Clock | NEM midnight, month/year boundary and NSW/Victoria daylight-saving dates; no duplicate/missing market half-hours; exact scheduled start/end and interval-link boundaries |
| As-of replay | A revision, cancellation, actual end or set link received after issue cannot change that forecast's features; all joined dependencies respect the cutoff |
| Snapshot integrity | Nested ZIPs, duplicate report hashes, duplicate primary keys, changing headers, missing `ELEMENTID`, partial reports, gaps and out-of-order arrival |
| Status/identity | Withdrawn versus withdrawal request; resubmission chains/cycles; multiple assets per booking; no double counting; secondary equipment; sentinel date and negative recall |
| Mapping | Future-effective equation version known early; effective version published late; unknown set; inequality/direction changes; no use of future setters |
| Folds/learning | Labels matured before cutoffs; no fitting of scaler, family encoding, residual correction, calibration or fallback weights on evaluation data |
| Specialist behaviour | Delivery-time routing across issue periods; midnight blending; unsupported-period fallback; fixed-state calendar continuity; scheduled discontinuities preserved |
| Warnings | Whole-window calendar features; single-class partitions; no resetting alarm refractory state at period boundaries; one-to-one matching; shared directional budget |
| Missingness | No NOS versus confirmed zero relevant exposure; stale NOS; unsupported mapping; full-population fallback and its independent score |
| Reproducibility | Identical rerun fingerprints; model/data/mapping changes invalidate fits; report-only changes do not; interruption resumes verified work |

Add a decisive leakage test: build features for an origin, insert a later snapshot with an earlier planned start and an actual end, and assert byte-identical original features. Add a positive control where a revision received before the next origin changes only that origin's future exposure.

Use one small VNI fold to verify end-to-end operation, then one QNI fold to exercise mapping/missingness differences, before launching the complete bounded campaign. Run the existing test suite plus new data-contract and scoring tests. Do not require large retraining runs for report-only edits.

## 8. Implementation sequence and handoff

| Stage | Main implementation surface | Deliverable / completion condition |
|---|---|---|
| A. Measurement contracts | Existing preparation, validation, shadow and benchmark adapters | Corrected control predictions; legacy reproduction; sign/time/maturity tests |
| B. Calendar experiments | `nemic/experiments/data.py`, `models.py`, runner/config | T0–T6, chronological residual correction and period fallback with fold-local selection |
| C. NOS store | New outage ingestion/as-of module plus existing parser/store | Hashed snapshot inventory, compact revisions, coverage and temporal negative controls |
| D. Exposure features | New outage mapping/features module | O1–O4/OQ, quality flags and origin/lead contracts; retrospective versus archive-vintage separation |
| E. Combined/risk campaign | Runner, events and calibration logic | Matched ablations, separate accuracy/risk choices and full-population fallbacks |
| F. Reporting and explanations | Existing experiment-report pipeline plus explanation adapter | Every model's results, aligned forecast charts, MAPE/MAE tables, permutation importance, SHAP and fundamentals assessment; §9 acceptance contract |
| F2. Trained-model handoff | Model serialization and inference adapter | Refitted recommended bundles, exact parameter manifests, routing/calibration/fallback assets and load/predict verification; §10 acceptance contract |
| G. Prospective validation | Existing shadow infrastructure after parity fixes | Immutable live forecasts, matured scoring and a frozen confirmation protocol |

Extend the existing CLI with explicit `inventory-nos`, `recover-nos`, `audit-nos` and `run --stage calendar|nos|combined|refinements` operations, while preserving current v1 commands. Add explicit `tune`, `explain`, `refit-final` and `export-models` operations for the search, attribution and model-handoff stages. All stages take the new configuration. Expose dry-run inventories and estimated scratch/output sizes before bulk downloads; honor the existing shared resource accounting.

The final research deliverables must satisfy §9 and §10, including the trained model files; a summary of the winning model alone is insufficient. Select up to 20 diagnostic examples per connector, balancing largest improvement, largest deterioration, false warnings, missed contractions and schedule revisions. Also include prespecified ordinary-day examples so charts are not solely selected by forecast performance. Explanation cases do not alter model selection.

Begin prospective collection only as an explicit execution stage, not an implicit background task created by this document. Use actual first-received timestamps and predict every 30 minutes. Freeze the shortlisted model, fallback and adaptation policies before a minimum 12-week confirmation period. Require at least 30 eligible incidents per direction for the primary risk comparison; otherwise continue collection and report that risk evidence is insufficient. Rare 400 MW incidents may remain inconclusive and must be labelled accordingly.

Before confirmation, every input used by a live model needs demonstrated receipt lineage. If only observed-history + NOS is operationally available, validate that model and keep reconstructed-context models retrospective. Score only matured outcomes, including the full seven-day delay for extended leads. Report weekly source coverage, forecast completeness, fallback use, latency, calibration and warning burden. Do not reselect the winner during confirmation; changes start a new version and confirmation period.

**Completion means:** the campaign can answer whether daily shape, changing sensitivities, outage schedules, or their interactions produced the improvement; all gains have matched controls and uncertainty; each candidate is explicitly classified as rejected, inconclusive, historical finalist or prospectively validated; and the report, explanations, search history, trained bundles and inference verification in §9–10 are delivered. The retrospective report and trained research bundle are delivered when historical work finishes, with prospective status pending rather than waiting 12 weeks to provide the handoff. A successful outcome need not be a more complicated model.

## 9. Mandatory final report and model explanations

Deliver `vni_qni_diurnal_nos_model_report.html` as a self-contained offline analytical report, with a Markdown findings companion and linked machine-readable tables. Reuse the repository's report components. Include a model selector and connector, direction, target, lead/band, fold and period controls; all displayed metrics and explanations must identify the selected information track. Bundle plotting assets locally. Produce standalone PNG/SVG exports for key charts and retain their underlying data. Do not require a running dashboard to read the report.

### 9.1 Models used and results for each

Include a model catalogue listing every baseline, tuned family, specialist, blend/fallback policy and event model that entered evaluation. Identify feature blocks, target, training window, search objective, initial/refined search bounds, trial budget consumed, best trial, exact parameters, effective tree count, runtime, convergence and eligibility. Show fixed/default and optimized results separately. Hyperparameter trials appear in an appendix; do not misrepresent every trial as an independently tested model.

For every evaluated candidate policy, give MAPE-first/MAE-second tables by connector, direction, minimum/mean limit target, exact lead/band, period and rolling fold. Include counts, percentage-metric coverage, paired differences against controls, intervals, risk measures and failed/unavailable cells. Save evaluation predictions for **every evaluated candidate policy**, not merely the winner; retain trial-level validation summaries for unselected hyperparameter trials. Store compressed partitions and budget them before launch.

### 9.2 Actual-versus-forecast limit graphs with aligned tables

Provide both (a) a fixed-issue forecast curve over delivery time and (b) a rolling forecast trace at one fixed lead. Never silently splice different leads or forecasts issued after delivery. Overlay actual limits, selected model, incumbent/persistence and selected quantile bands; allow comparison with any evaluated model. Keep signed negative limits and missing-data gaps visible. Show issue time, NEM delivery time, lead, model/version and scheduled outage transitions known at that issue.

Place a metrics table directly below each chart, computed on exactly its plotted, matched observations: qualified MAPE and its coverage, ordinary nonzero MAPE, MAE, RMSE, bias and >100/>200 MW overstatement. Keep full-period metrics in a separate table. Show interval coverage/width when enough observations exist; otherwise show sample size and insufficient support.

Include the first eligible full issue day of every evaluation month as prespecified ordinary examples, the existing daily 336-step finalist curves, and the up-to-20 diagnostic event cases per connector. For every non-finalist candidate, retain enough fixed-lead traces and configured-lead curves to support actual-versus-forecast inspection. Charts of sparse configured leads must display their actual points and identify any connecting lines as interpolation. Missing model coverage is shown explicitly.

### 9.3 Feature importance for every evaluated model

Use held-out grouped permutation importance as the common performance-based measure. Report change in qualified MAPE and full-population MAE for numeric models, and Brier/log loss for risk models, with week-block uncertainty. Use five deterministic whole-day block permutations on a shared evaluation sample. Move correlated feature groups together; recompute derived interactions, routing and persistence anchors when their source group changes. For daily calendar importance, apply a seeded nonzero circular phase offset of 1–47 half-hours independently to each complete day, move sine/cosine and period columns coherently, and recompute routing/interactions. Whole-day shifts alone would leave hour-of-day unchanged. Label all perturbations as model-sensitivity diagnostics.

Publish group and feature rankings, fold stability and period/NOS-regime differences. Supplement them with standardized linear coefficients and tree gain/split importance where available; native importance is never the sole assessment. Baselines receive explicit analytic input attribution (for example, the selected historical limit) rather than invented tree importance. Assess features used by fallback/routing as well as the learned correction. State which feature changes produce unrealistic network combinations.

### 9.4 SHAP decomposition for every evaluated model

For each evaluated family/policy and fold, select at most 1,000 held-out origins deterministically, stratified by period and NOS exposure using covariates, with at most 100 training-only background rows. Use the same eligible explanation sample across matched candidates. Keep separately selected extreme-error/contraction cases out of representative global averages, and apply sampling weights to pooled summaries.

Use `LinearExplainer` for linear models on their actual transformed design and `TreeExplainer` for supported tree models with explicit background and dependence settings. Group expanded Fourier, spline, categorical and interaction columns into named feature groups while preserving the ungrouped values. These explain transformed features; do not present grouped transformed-column SHAP as uniquely defined raw-feature SHAP. For raw physical-feature questions, explain the full preprocessing-and-prediction callable using [grouped permutation SHAP](https://shap.readthedocs.io/en/latest/generated/shap.PermutationExplainer.html). [LinearExplainer](https://shap.readthedocs.io/en/latest/generated/shap.LinearExplainer.html), [TreeExplainer](https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html).

For numeric persistence-correction models, show the identity `forecast = observed anchor + expected correction + sum(correction SHAP)`. Label this as correction SHAP with anchor displayed separately. Also explain the full issued forecast for baseline, blend, period-routing and fallback policies using a model-agnostic grouped permutation explainer; use at most 200 representative rows and 20 permutation passes per row. Rebuild derived features inside the callable. Do not simply average component SHAP with input-dependent weights and call it whole-policy SHAP. Fixed-weight components may be combined only with compatible backgrounds and output units, and must pass reconstruction tests.

For classifiers distinguish raw log-odds contributions from calibrated probability. Explain the full calibrated predictor on the probability scale with grouped permutation SHAP for the same 200-row subset; do not add raw-logit SHAP values to a probability. Quantile outputs receive their own decomposition when displayed; a median explanation is not an explanation of interval width. Explain linear/non-tree quantile and unsupported models through their prediction callable. Use the supported SHAP API for the pinned version; no silent substitution with an unrelated surrogate model.

Every model page includes a mean-absolute-SHAP ranking, beeswarm/summary plot, at least one local waterfall, and a time-aligned contribution plot for an actual-versus-forecast case. Add dependence plots for its five most influential physical inputs and its relevant NOS/time interactions. Preserve baseline values, signed SHAP arrays, feature values, background/sample IDs, grouping map, output units and explainer version. Explain persistence analytically relative to a training background, not as a fabricated fitted model.

Verify additive reconstruction against the exact stored prediction: tolerance `max(.01 MW, 1e-5 × abs(prediction))` for numeric output and 1e-4 for probabilities. Show approximation residual and sampling sensitivity; if reconstruction fails, mark the explanation invalid and resolve it before delivering that model's explanation. Interventional/background assumptions and correlated-input ambiguity must be stated. SHAP describes predictive attribution, not causal outage impact.

### 9.5 Feature relevance to fundamentals

Provide one assessment row per feature group per model: definition/units, issue-time availability, hypothesized physical mechanism, expected direction where defensible, observed coefficient/SHAP behaviour, permutation/ablation evidence, stability across periods/folds/outages, redundancy and retain/revise/remove verdict. Explain how load/renewable patterns, generator pressure, candidate competition, outage timing, concurrent topology changes and schedule revisions relate to the forecast.

Investigate sign reversals and apparently implausible dependencies by checking equation version, connector/direction, operating regime, correlated proxies and missingness. Do not impose one universal monotonic relation on all outages or generators. Support conclusions with withheld feature-block ablations and representative event timelines, not SHAP magnitude alone. Any feature change motivated by evaluation explanations is a new exploratory version requiring fresh validation.

### 9.6 Model-choice verdict

End with a clear decision table: recommended point model per connector/direction/target/band, recommended contraction model, exact parameter-set ID, MAPE and MAE versus both controls, risk guardrails, source eligibility, fallback and artifact path. Explain why the closest alternatives lost. If percentage and MW objectives disagree, show the tradeoff and apply the frozen guardrails rather than conceal it. Report a single model of choice only where one model genuinely wins the required cells; otherwise deliver an explicit routed collection.

Separate “best tested historical model” from “eligible for live use” and “prospectively validated.” A no-improvement result still requires a trained incumbent/fallback handoff and a clear verdict. No blanket winner may be selected using evaluation scores and then presented as if chosen before those scores.

## 10. Trained-model package, exact parameters and delivery checks

Export evaluated fold bundles and a final recommended research bundle. After historical assessment, lock the selected recipe and search procedure. For the final refit, use the existing fixed protocol's relative layout ending at the latest mature-data cutoff: training before the final six months, then three months for selection, two months for calibration and one month for alert tuning. Run tuning inside training only. Restrict NOS-dependent fits to covered history and enforce support requirements; if insufficient, deliver the last eligible evaluated bundle and explain its cutoff. Do not reuse calibration from a different refitted point predictor.

This final refit is an inference artifact; historical scores belong to the evaluated fold models, not to the newly refitted file. An optional later deployment refit starts a new version and calibration sequence. Prospective claims still require §8's confirmation protocol.

Each delivered bundle contains:

* Serialized estimator(s), fitted preprocessing, exact feature order/types/units, calendar transforms and learned encodings.
* Shared/period routing, persistence anchors, outage quality gates, no-NOS fallback, blending weights, quantile adjustments, probability calibration and alert thresholds.
* `parameters.json` with every effective estimator and pipeline setting, study/best-trial IDs, search bounds, seeds, tree counts, training/selection/calibration dates and information-track eligibility.
* Model card, source/code hashes, target/sign/time conventions, training coverage and tested input/output examples.
* Environment lock, checksums, loading instructions and a minimal inference example using `predict_limits(origin, source_snapshot, leads)`; return point/quantile limits, risk output where supported, source age, model ID and fallback reason.

Save human-readable parameters and machine-readable manifests alongside binary files; a list of suggested hyperparameters alone does not satisfy the handoff. Retain an explicit connector/direction/target/band routing manifest when the recommended solution uses several estimators. Include paths to both the fitted model and its relevant report section.

Before delivery, test reload/prediction parity, missing/stale NOS fallbacks, required-column/schema rejection, signed import conversion and calibration/feature-order integrity. Validate Optuna resume and cutoff isolation; MAPE zero/negative/tiny-limit behaviour and denominator parity; SHAP reconstruction and output units; and chart/table row alignment. Open and visually verify the offline report, selectors, waterfalls and downloadable chart assets. Verify that every model in the catalogue has a result section and explanation, or a concrete unavailable/failed status with reason. Link the final report, trained bundles and exact parameter files in the handoff response.
