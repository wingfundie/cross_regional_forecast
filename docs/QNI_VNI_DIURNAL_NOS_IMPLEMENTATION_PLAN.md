# Implementation plan for diurnal and NOS forecasting experiments

## 1. Outcome, scope and fixed decisions

Deliver a reproducible VNI/QNI research campaign that determines whether delivery-time specialization and as-of network-outage information improve directional limits and advance contraction warnings. The final handoff must include a report covering every evaluated model, model-by-model results, actual-versus-forecast limit charts with MAPE-first metrics tables, feature importance and SHAP decompositions, an assessment against fundamentals, an explicit model-choice verdict, and trained model bundles with exact parameters and inference instructions. Use chronological hyperparameter optimization, separate accuracy and risk selections, auditable feature/data lineage and matched historical scorecards. The supporting evidence and literature are in [the research report](QNI_VNI_DIURNAL_NOS_RESEARCH.md); both documents use the percentage-metric eligibility policy in §6.1.

This is an implementation specification. VNI-first execution began on 15 September 2026 under `configs/experiments/vni_diurnal_nos_v2.json`; completion is determined by the execution artifacts and gates, not by the existence of this document. Existing v1 artifacts remain the historical reference. QNI execution and prospective confirmation are separate pending stages.

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

### 3.6 Mandatory pre-model outage and constraint impact analysis

Run this analysis after snapshot/mapping validation and before any **NOS-aware predictive model fitting or NOS HPO**. Calendar-only work may proceed independently. The objective is to establish which outage assets, expected sets and equation families are repeatedly associated with lower directional limits, under what operating conditions, and which of those relationships are available early enough to forecast. Do not publish a list of supposedly highest-impact outages from names or engineering intuition alone.

Keep three evidence levels separate: NOS scheduled exposure, independently observed set invocation, and the equation reported as setting the directional limit. An expected NOS set is not proof of invocation or of setting the limit. Missing invocation/setter history remains unknown. Multiple sets may operate concurrently, so do not sum their apparent effects as independent deratings. See [AEMO NOS set definitions](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_458.htm) and [AEMO outage assessment](https://aemo.com.au/-/media/files/electricity/nem/security_and_reliability/power_system_ops/procedures/so_op_3718-outage-assessment.pdf).

#### Step 1 — Freeze the cohort and build an episode ledger

Apply the §4.3 NOS feasibility gate first. Build a distinct-chain episode ledger with stable asset identifiers/descriptions, region, voltage/equipment class where verified, primary/secondary work, status and resubmission lineage, planned/known-actual transitions, source vintage, expected sets, versioned member equations and connector/direction mapping. Separate thermal, voltage, transient-stability and other/unknown mechanisms using authoritative metadata, with source and confidence. An equation's name alone is insufficient evidence of a mechanism or affected direction.

Store one observation per connector/direction/delivery interval for impact measurement, rather than duplicating outcomes for every forecast lead. Retain a separate origin/lead exposure table for forecastability. Group genuinely linked bookings; do not merge different asset outages because their times overlap. Label overlapping groups and recurring episodes of the same asset. Distinguish an observed completion from a scheduled end, and record whether each transition was known 30 minutes, two hours, six hours and one day ahead.

#### Step 2 — Describe severity, duration and constraint evidence

For each asset, expected set and physical family, separately by VNI/QNI and import/export, report episode count, distinct days/weeks, mapped coverage, overlap share, exposed hours, absolute minimum/median/P10 limits and contraction frequencies at 100/200/400 MW. Include both mean and minimum half-hour limits. Report known invocation and setter shares with their own availability denominators; no binding-only target filter is permitted. Describe starts, stable exposure, restoration and revisions separately. An outage may reduce one direction and increase the other; retain signed effects.

Measure transition profiles initially from six hours before to 24 hours after start/end, in half-hour bins; flag truncated windows and censor at subsequent overlapping transitions for the isolated-transition analysis. These are prespecified diagnostic windows, not inferred physical response times. Compare a fixed two-hour pre-transition baseline with 0–2 h, 2–6 h and 6–24 h post-transition windows. Analyse longer stable exposure separately. Use scheduled transitions for issue-vintage forecastability and known-actual transitions only in clearly labelled realised-operation diagnostics. A cancelled or delayed booking must remain in the schedule-reliability denominator.

#### Step 3 — Estimate adjusted associations with matched controls

Raw low limits during an outage do not identify its contribution. Match exposed episodes to unexposed reference windows for the same connector/direction, clock period, season, weekday/weekend, pre-transition limit level/trend and pre-transition operating state. Include other-outage exposure and forward fundamentals only when admissible vintages exist. Choose matching variables, distances and tolerances using the fold's training support and balance diagnostics, not the size of the resulting limit difference. Require overlap in operating conditions; show retained/excluded episode counts, effective reference count, reuse and standardized balance differences. If no credible controls exist, report descriptive severity only.

Report both the raw before/after change and the matched change difference: `(post−pre exposed) − (post−pre reference)`. Define associated derating as the negative of that difference, in MW; positive means lower capacity. Label it an adjusted association, not a causal estimate. Do not match on post-outage limits, realised generation or actual setter status: these can be consequences of the outage. Later setter observations may support a mechanism diagnostic, but cannot select predictive features at an earlier origin. Check pre-transition trends and matched pseudo-starts on unexposed windows; unstable pre-trends, anticipation or placebo effects weaken the claim.

Separate isolated episodes from overlaps. For common overlapping pairs, require observed support for neither/A-only/B-only/both in comparable operating states before reporting a combined-interaction contrast. If these states are absent or perfectly confounded, attribute only to the outage combination; mark individual effects unidentified. Do not enumerate all asset pairs. Retain only combinations supported by training episodes and the existing feature/compute budget.

#### Step 4 — Rank what usually matters, with uncertainty

Produce three distinct rankings: **typical associated derating** (median episode-level adjusted MW reduction), **tail severity** (P90 positive episode reduction, with sample support), and **cumulative capacity reduction** (positive adjusted MW shortfall integrated over exposure hours). The last has units MW-hours of reduced transfer capability, not measured lost energy or economic cost. Also show the frequency of supported episodes exceeding 100/200/400 MW reduction and the fraction with the same effect sign. Long outages must not dominate the typical-effect ranking simply by contributing more rows.

For a recurring asset/set to enter the “usually highest impact” shortlist, require at least ten distinct usable episodes spanning at least three months, adequate matched-control support and acceptable documented balance; these are screening floors, not guarantees of precision. Pool sparse assets to a defensible physical family or mark them insufficient evidence. Rare severe events remain in a separate case-study list, never presented as a typical recurring effect. Show all supported ranks with intervals, probability of positive derating and leave-one-episode-out rank stability; disclose the shortlist size before comparing outcomes. Do not force a top-ten winner list when fewer entries qualify.

Reuse the campaign's 2,000 paired block resamples, preserving shared outage chains and overlapping connector/direction observations; aggregate typical effects at episode level and run calendar-block sensitivity for residual dependence. Correct exploratory family-wide screens for multiple comparisons using a declared Benjamini–Hochberg procedure, retain raw effect intervals and explicitly label the ranking exploratory. Do not interpret a narrow row-level interval as episode-level certainty. Split tables by clock period or operating regime only where independent episode support permits; otherwise show pooled results and an insufficiency flag.

#### Step 5 — Translate evidence into a frozen feature proposal

For each shortlisted family, document mechanism, direction, typical/tail effect, independent support, schedule reliability, early-availability coverage and proposed feature. Candidate features include delivery-overlap exposure by family, start/restoration proximity, supported concurrent-family flags and exposure weighted by a shrunken training-estimated effect with an uncertainty/support flag. This adds a separately named **O5: historical impact summary** challenger within the 64-scalar NOS budget; it must earn incremental value over O1–O4/OQ. Never hard-code an observed average as a physical capacity deduction or create a raw-outage-ID feature.

All outcome-derived ranks, grouping decisions, shrinkage and weights must be fitted **inside each inner training split**, using only matured earlier episodes, then frozen for its validation window. Generate training encodings chronologically out of fold; unseen/sparse families use the supported parent-family estimate or an unknown flag. Outer evaluation outcomes may appear in the descriptive final atlas but cannot feed any model tested on those outcomes. A whole-history atlas is explicitly development-only and does not authorize backfilling full-history rankings into earlier folds. Apply the existing chronological validation discipline ([FPP3](https://otexts.com/fpp3/tscv.html)).

Freeze a bounded feature-ablation manifest comparing selected O1–O4/OQ models with and without O5; include any supported interactions as a separate comparison. Keep matched information/history and tuning opportunity. A family can have a large observed impact but little incremental forecasting value if lagged limits already capture it. The final verdict must distinguish physical plausibility, observed association and out-of-sample predictive value.

#### Step 6 — Publish the pre-model analysis and enforce its gate

Deliver `nos_outage_impact_analysis.html` with a Markdown summary, episode ledger, asset/set/family impact tables and a versioned `nos_impact_feature_manifest.json`. Include ranked MW-effect plots with intervals, connector/direction × family heatmaps, matched event-time curves, concurrent-outage comparisons, and annotated limit/schedule/setter traces for supported high-impact examples and counterexamples. Each table includes source track, cutoff, episode counts, coverage, raw/adjusted effects, uncertainty and limitations. Percentage changes use the §6.1 denominator policy; MW is the primary unit for outage derating, while model scorecards remain MAPE-first/MAE-second.

The VNI execution exposes `analyse-nos-impacts`, `audit-nos-feasibility` and the NOS impact-report builder described in the execution guide. Cache by source/mapping/fold/matching-policy hashes, run within shared resource limits, and write a resumable audit log. Dependencies are inventory → snapshot/mapping audit → historical feasibility → episode ledger → matched analysis/rank stability → feature manifest → NOS model fitting. Require this gate to check lineage, duplicate/overlap accounting, control balance, insufficient-support labels and training-only encodings. An inconclusive analysis may still admit broad unweighted O1–O4 features under the existing feasibility rules; it must disable unsupported O5 weights rather than invent effects.

## 4. Model ladder and staged experiments

### 4.1 Common estimator conventions

Numeric models predict a correction to the latest admissible persistence anchor. Use the existing train-only imputation, missingness indicators and scaling. Cyclic basis columns and period indicators must not be clipped using empirical feature quantiles. Build interactions after continuous-feature preprocessing; missingness indicators remain explicit. Retain separate target/direction fits and lead-band models for the principal comparison.

Keep the v1 parameter configurations as reference trials, not the final search space. Optimize every trainable family using the chronological search protocol in §4.4. **Minimize MAE in MW for primary point-model HPO, early stopping where supported, recipe selection and fallback selection. MAPE is assessment-only.** Test the separately defined directional-reference percentage-error objective in §6.1 as a bounded challenger; use probability loss for classifier hyperparameters. The outer selection partition chooses recipes and policies after inner tuning. Record failed fits and convergence issues. Prefer native absolute-error training where the family supports it; ridge/elastic-net retain their declared squared-error training loss and are tuned/selected by held-out MAE. Record estimator fitting loss separately from HPO/selection loss rather than claiming ridge minimizes absolute error directly.

### 4.2 Calendar candidates

| ID | Candidate | Exact experiment |
|---|---|---|
| T0 | Current calendar control | Existing first daily harmonic and annual/weekend terms |
| T1 | Rich cyclic calendar | Daily Fourier complexity derived from the training profile and chronological pilots in §4.4, additive to the same base predictors |
| T2 | Period-interaction ridge | Five fixed periods, shared main coefficients and regularized deviations for capacity change, room, switch gap, own/opposite net pressure and residual-demand context |
| T3 | Smooth interaction ridge | Same driver subset interacted with profile-supported Fourier pairs; primary recommended specialist |
| T4 | Shared model + period correction | Ridge residual corrections trained on expanding-month out-of-fold base predictions inside the training partition |
| T5 | Independent period ridge/elastic net | Separate five-period fits on the same predictors; compare hard routing and a fixed 60-minute transition blend |
| T6 | Shared shallow boosting | Existing 7/15-leaf configurations as controls, plus Optuna-tuned boosting with the same feature blocks |

For period deviations use the block-specific shrinkage paths and support audit in §4.4; existing multipliers are historical benchmark probes only. T4 corrections must never be trained on the base model's in-sample residuals or evaluation predictions. Refit its base model after generating chronological training residuals, keeping the residual learner fixed until the next fold.

A period-specific fit needs at least 90 distinct training days, 500 eligible training rows, and 20 selection days with 100 rows. Otherwise fall back to the shared fit and report insufficient support. This is a conservative engineering threshold, not a claim that 500 correlated observations are independent. Do not further split by season or weekday.

For smooth period routing, linearly interpolate adjacent specialists over ±30 minutes around each fixed boundary, including midnight. Train that variant using the corresponding routing weights. Retain hard routing as an explicit diagnostic challenger. Test artificial clock jumps by holding non-calendar features and lead fixed; do not smooth away genuine scheduled network changes.

For the fallback policy blend the specialized forecast with the persistence anchor using period weights from {0,.25,.5,.75,1}. Choose weights on the outer selection partition using the declared metric and MAE guardrails, plus a dimensionless shrinkage penalty: `lambda × mean squared deviation from the shared weight`, with lambda in {0,.01,.1} after dividing metric loss by the shared-policy loss. Use the same boundary blend for weights. Unsupported periods use the shared weight. The no-NOS fallback is independently fitted and selected, not the outage model with unknown outages set to zero.

### 4.3 Controlled campaign sequence

1. **Calendar:** screen T0–T6 without NOS for the two primary minimum-limit targets, first horizon band and one frozen base-feature recipe across both connectors and all existing rolling folds, with MAE as the primary objective. Select calendar families independently within each fold; save the complete trial ranking. Limit directional-reference percentage-objective retuning to at most two training/selection-preselected families per cell. Evaluate other horizon bands and mean limits later with the selected procedures, without repeating the full ladder. Keep fixed-split results separate.
2. **NOS main effects:** use T0 and the fold-selected best of T2/T3 with O1, O1+O2, O1+O2+O3 and O1+O2+O3+O4. Include OQ whenever NOS is used. Refit no-NOS controls over identical eligible training and evaluation populations.
3. **Combined interactions:** compare the best scheduled-NOS recipe with/without the restricted outage × driver/time interactions. Run T6 on the same selected blocks. This directly measures synergy beyond additive calendar and outage effects.
4. **Refinements:** on the selected combined recipe, separately test lead-conditioned aggregate-pressure forecasts, cross-connector partial pooling and recent-data adaptation. Do not attribute their gains to NOS or time of day.

NOS fitting requires 90 distinct covered training days and at least 80% fresh-snapshot coverage within each fitted partition. Existing rolling folds remain unchanged; with snapshots beginning in late August 2025, March 2026 is the first *potential* evaluation month under these rules, subject to the full coverage audit. Earlier folds and the fixed split may be unavailable for NOS training. Mark them unavailable; do not move cutoffs after seeing scores.

#### Historical NOS evidence gate, before model fitting

Freeze the gate before examining new NOS model scores. Require at least four eligible monthly folds, each satisfying the 90-day training rule and at least 80% admissible fresh-snapshot coverage in training, selection, calibration, alert **and evaluation**. Coverage uses all scheduled half-hour origins, not only rows remaining after source filtering. Require at least 80% coverage across the candidate evaluation months as well. If either fold-count or coverage gate fails, stop historical NOS HPO and route the NOS performance question to prospective collection; retain the archive audit as descriptive evidence. Calendar-only work can continue. These are declared feasibility thresholds, not data-estimated optima.

On eligible folds count warning-eligible distinct incidents, incident days/weeks and independent outage chains for each connector/direction, both on common-source rows and the full fallback population. Incidents are eligible when an admissible issue exists 30–120 minutes before onset. Count incidents independently of alarms: the three-false-alarms/day budget constrains detections, not event prevalence. Require at least 30 distinct eligible incidents per direction for a historical risk comparison; below this, classify that risk cell as exploratory and defer its promotion test to prospective data. Counts above 30 do not establish adequate power. Never infer NOS-specific support from all-network incident totals.

A reproducible preliminary audit of saved March–August 2026 v1 predictions gives the following **pre-NOS, development-only** evidence. These are observed counts, not an estimate of the still-unknown matched NOS cohort:

| Connector / direction | Distinct eligible onset timestamps | Saved-policy detections | False alarms |
|---|---:|---:|---:|
| VNI export | 694 | 274 | 393 |
| VNI import | 402 | 93 | 207 |
| QNI export | 527 | 73 | 94 |
| QNI import | 1,219 | 585 | 558 |

Each cell has 8,808 eligible origins, equivalent to 183.5 days at 48 issues/day. Combined directional false-alarm rates are 600/183.5 = **3.27/day for VNI** and 652/183.5 = **3.55/day for QNI**; selection-time budget compliance did not guarantee evaluation-time compliance. Do not retune on this evaluation period. Reproduce with `python scripts/audit_nos_incident_support.py`; its local JSON records monthly counts and input hashes. Distinct onset timestamps need not be independent episodes, and v2 label/source eligibility must be re-audited.

Before expensive NOS tuning, write `nos_feasibility.json` with the exact eligible cohort, exclusions, event/episode counts, baseline recall/burden and uncertainty. Estimate the detectable recall improvement using paired week/episode-block simulations over a documented grid of baseline/candidate detection discordance and dependence, preserving the joint alarm budget and chronological threshold-fitting partitions. Report power for the proposed +10 pp gain and the minimum detectable gain at 80% power under the declared multiplicity procedure. Use pre-evaluation training/selection/alert evidence for design assumptions; evaluation incident counts are descriptive feasibility checks only. If plausible assumptions do not support 80% power, label historical risk conclusions exploratory regardless of the 30-event floor. The archive remains development evidence even when all gates pass.

Refinement defaults are: pressure predictions conditioned on actual lead and delivery calendar with chronological out-of-fold construction; cross-connector sharing of calendar coefficients with connector-specific network/outage coefficients; and expanding history versus trailing 180/365-day fits. Choose each on selection data. Keep these as individually named ablations so their effects are identifiable.

For novel outage families, use broad physical metadata and an unknown-family indicator. Family-specific learned encodings require at least ten distinct historical outage episodes and chronological out-of-fold estimation; otherwise use the broader family. Raw outage IDs are diagnostic keys, never predictive categories.

Solar elevation and issue-vintage demand/renewable ramps form a later, separately gated operating-state block. Add it only after the core matrix: use a reviewed fixed regional location map for deterministic solar geometry, and original issue vintages for future fundamentals. Future realised demand, solar, weather or generator availability may appear only in a clearly labelled oracle diagnostic. NOS `UNIT` equipment does not substitute for a generating-unit availability feed.

Consequently, the first-pass NOS verdict is conditional on the available observed/lagged operating state and existing pressure forecasts. A weak result cannot establish that NOS is unhelpful when forward generation information is available. Before a broader verdict, run a matched 2×2 ablation: NOS off/on × issue-vintage forward fundamentals off/on, with identical history, folds, calendar family and tuning opportunity. Include scheduled generator availability and renewable/demand forecasts where their original vintages are recoverable. Report the interaction gain as well as each main effect. If vintages are unavailable, mark this comparison unavailable and retain the conditional verdict.

### 4.4 Mandatory data-informed hyperparameter optimization

Derive search ranges and trial allocation from each study's **actual training design and chronological pilot results**. The earlier universal parameter intervals, fixed 40/80-trial allocations and automatic tenfold expansions are replaced by the requirements below. Data shape determines feasible complexity; pilot validation determines useful parameter regions. Neither establishes a global optimum by itself.

Use deterministic regularization paths for cheap, low-dimensional problems and Optuna TPE for the coupled active parameters left after profiling. Persist studies, seed 741 and exact library versions; keep sequential trials within a study and at most two concurrent independent studies. Legacy parameters are reference probes, not presumed optimal ranges. [Optuna TPE](https://optuna.readthedocs.io/en/stable/reference/samplers/generated/optuna.samplers.TPESampler.html).

#### Measured starting evidence

A read-only profile on 15 September 2026 expanded configured leads in the first and last rolling training folds, requiring finite targets/anchors and `delivery end +30 minutes < training cutoff`. Counts apply to both minimum-limit targets on each connector, before new NOS/expanded-feature eligibility gates:

| Fold / horizon band | Forecast pairs | Distinct origins | Days | Smallest period's distinct origins |
|---|---:|---:|---:|---:|
| September 2025 / 0.5–6 h | 63,808 | 12,766 | 266 | 4,521 |
| September 2025 / 72.5–168 h | 50,012 | 12,575 | 262 | 1,571 |
| August 2026 / 0.5–6 h | 143,968 | 28,798 | 600 | 10,199 |
| August 2026 / 72.5–168 h | 114,140 | 28,607 | 596 | 3,575 |

An origin can appear in several delivery periods, so period counts are not additive independent observations. Short-band row counts are roughly five times origin counts. A separate period model has materially less support, and NOS coverage must be measured independently rather than assigned these totals.

The current `full` recipe at a fixed half-hour lead has 40 columns, 38 varying columns and constant `lead`/`log_lead` columns. Median-imputed float64 standardized training designs require 32–33 singular components to explain 99% of variation. This diagnostic excluded the final seven training days, leaving 12,432/28,464 rows in the first/last fold. It describes collinearity, not an independent sample count or a prescribed model dimension. Multi-lead and new-feature designs need fresh profiles. Detect constants using distinct values/tolerance, not float32 standard deviation alone.

First-band training MAPE eligibility at `|actual| >=50 MW` ranges from 90.22% to 98.35% in the inspected cells; this does not establish inner-validation support. Sources were configured targets/monthly features and the existing `connector_data`, `base_frame` and `design` functions. No predictive models or HPO pilots were run for this planning profile.

#### Required per-study profile and temporal controls

Write `data_shape_profile.json` before tuning, with source/code hashes and cutoffs. Include rows, sum of weights, distinct origins/deliveries/days/weeks, per-period/lead support, post-transform dimensions, constant/all-missing fields, category frequencies, unique split values, weighted design spectrum and condition diagnostics. Add target/correction quantiles and scale, zero/negative/near-zero rates, MAPE coverage, distinct contraction incidents/positive days and outage chains.

Measure temporal dependence on unique-origin target-correction and chronological baseline-error series, separately by lead. Record autocorrelation through seven days within contiguous segments and an effective-size proxy from the positive-sequence autocorrelation sum, bounded by the distinct-origin count. Show daily-aggregation sensitivity and label this a proxy, not a verified independent sample size. Do not multiply it by lead count. For rare events/outage effects, incident and episode counts constrain interpretation regardless of row count.

Construct a study only for an explicitly admitted §4.3 candidate; fold, connector, target/direction, band, family, recipe, information track and objective identify it, **not dimensions to cross automatically**. Profiles used to generate a candidate's numeric bounds come only from its inner training data. Search dimensionless controls and translate them separately on each inner training design, then again on outer refit. Fit all preprocessing, pressure forecasts and residual learners within those same training cutoffs. Do not seed an earlier fold with later-fold winners.

Register the sparse study manifest before launch. For the primary point campaign the maximum is: calendar `12 folds ×4 connector-direction cells ×7 families =336` main-objective studies; at most `12×4×2 =96` DR-NMAE challengers; NOS `6 eligible folds ×4 cells ×2 calendar survivors ×5 recipes (including matched no-NOS) =240`; at most `6×4×2 =48` NOS DR-NMAE challengers. Thus **720 point-study slots**, before deduplication, unsupported cells and pruning, rather than multiplying by four bands, four targets and all information tracks. Primary NOS comparison uses one declared archive-vintage track. Retrospective/oracle and prospective tracks are separate campaigns. For risk, admit at most two preselected classifier families: calendar `12×4×2=96`, NOS `6×4×2×5=240`, hence **336 risk-study slots** using probability loss only. These are conservative scope ceilings, not a requirement to execute 1,056 studies or a runtime estimate.

Combined interactions, other bands/mean targets, forward fundamentals and refinements each require a separate bounded manifest restricted to survivors. Count composite-model subfits, calibration and explanations in compute accounting even when they are not separate studies. A family may be removed within a fold using that fold's inner validation/selection evidence and the declared simpler-model rule. Do not globally eliminate it from later-fold evaluation on the strength of an earlier evaluation score; chronological training-only pilots may screen later searches. Log every omitted comparison and preserve matched ablation pairs.

Use expanding inner training with up to three non-overlapping validation windows entirely inside outer training. Window duration is at least `ceil(maximum lead in days) +7 days`, enlarged when the training-derived dependence block or event support requires it. This leaves scored observations after purging even at seven-day leads. Record eligible counts; require at least two qualifying windows. If history cannot support them, mark HPO unsupported and retain the fixed control. Keep matched ablation windows identical and leave outer selection, calibration, alert and evaluation separate.

#### Parameter bounds derived from profiles and pilots

| Parameter group | Required derivation |
|---|---|
| Ridge / additive shrinkage | For centered standardized X, use eigenvalues `s_j` of `X' W X / sum(w)` and `edf(lambda)=sum(s_j/(s_j+lambda))`. Probe EDF levels from one toward numerical rank by doubling, plus a near-unregularized endpoint; solve for lambda. For sklearn Ridge's weighted sum loss, translate with `alpha=sum(w)*lambda`. Bracket and refine the feasible validation minimum along this path. Retain EDF, normalized penalty and actual estimator alpha. |
| Period / interaction penalties | Apply the spectrum/support audit to shared and deviation blocks separately. Pilot shared-only, tied and separately shrunk deviations; bracket useful block shrinkage using chronological loss. Unsupported blocks remain shared. Do not assign the same raw-alpha interval to different sample sizes or feature expansions. |
| Elastic net | For positive mixing fraction r, construct the weighted centered path relative to `alpha_max=max(abs(X' W y))/(sum(w)*r)` under the matching objective. Pilot pure L1/mixed paths with ridge as the pure-L2 endpoint; descend until active sets/predictions stabilize or validation deteriorates. Refine mixing and normalized-alpha regions supported by those paths. Record sparsity and correlation structure. |
| Logistic model | Use class prevalence, standardized weighted design and intercept-only Fisher-information spectrum to seed an L2 path. Refine from observed probability loss, separation/convergence and incident support. Verify the mapping from normalized penalty to the pinned solver's C convention; do not copy numeric-regression penalties. |
| Fourier / spline complexity | Propose complexity from training daily correction profiles, harmonic energy, stability across training subwindows, distinct-value support and expanded rank. Increase harmonics/occupied knots only while chronological validation resolves an improvement. At half-hour sampling, allow no more than 23 full daily sine/cosine pairs; spline complexity cannot exceed distinct-value support. Spectral energy proposes candidates, not proven forecast value. |
| Tree leaves / depth / minimum support | Pilot a stump and the existing benchmark tree. Inspect actual leaf row/weight, unique-origin/day and outage-episode occupancy. Derive minimum-leaf candidates from occupancy quantiles and test adjacent simpler/more-complex trees; admit finer leaves only when gains survive whole-day/episode resampling. Translate origin support to row/Hessian parameters and audit realized leaves. Repeated leads do not establish independent support. Couple depth/leaves and reject incompatible settings. |
| Learning rate / rounds | Halve/double the benchmark rate as diagnostic probes and adjust round allowance to compare similar boosting progress. Use measured learning curves, best-iteration distributions and plateau lengths to bracket useful rates, rounds and early-stopping patience. A resource ceiling hit while loss still improves is unresolved search. |
| Tree penalties / sampling | Use objective-specific gradient/Hessian and accepted-split statistics to scale penalty probes. Compare full sampling with reductions supported by redundancy and origin/class coverage. Reject settings that discard rare supported regimes. Record row-based versus grouped-origin subsampling. Fix controls the pilot cannot identify instead of needlessly expanding search dimension. |
| Quantiles | Derive shrinkage/smoothing paths from weighted design and correction scale, then score pinball loss and tail stability. Extreme quantiles need their own tail-support audit, not the median's chosen penalty by assumption. |

Use the one-standard-error preference for the simpler setting when paired validation differences are unresolved. Probe ratios and operational ceilings are algorithmic safeguards, not data-estimated optima. Measure pilot fit/predict time, memory, gradient/Hessian scale and effective model size. For LightGBM leaf-size tuning, rebuild datasets or disable feature prefiltering so the first candidate cannot permanently remove features for later candidates. [Ridge objective](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html), [elastic-net path](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.enet_path.html), [LightGBM tuning](https://lightgbm.readthedocs.io/en/stable/Parameters-Tuning.html).

#### Trial allocation, refinement and stopping

Use a deterministic path when sufficient. Otherwise let d be the empirically active search dimensions and seed Optuna with feasible pilot incumbents plus `max(4,2*d+1)` space-filling trials. This is an explicit exploration rule, not a claim that this count is optimal. Include pilot, inner-fold, pruned and failed fits in cost accounting. Keep the declared MAE or DR-NMAE objective and denominator policy fixed and average inner-block objectives equally. MAPE is assessment-only.

Measure median/P90 complete-trial time and peak memory from pilots. Write `search_budget.json` with active dimensions, finite candidate counts, measured cost, block-noise estimates and trials feasible in the existing 12-hour resumable work batch. Allocate that batch across concurrent jobs, not 12 hours to each study. Matched ablations receive equal pilot opportunity and additional compute allowance under the same stopping rule; actual trial counts may differ with cost and saturation. Apply the same resource policy to primary MAE and admitted DR-NMAE studies; constant-denominator equivalents do not consume duplicate study slots.

Turn the first VNI fold smoke test into a cost probe covering admitted linear, composite and tree families, including NOS feature materialization after its coverage gate passes. Benchmark representative early/late training sizes without reading their evaluation targets for selection. Forecast work seconds as `sum(study trial allowance × measured P90 complete-trial seconds) + measured preprocessing/refit/report costs`; record serial and measured two-worker wall-clock projections and contention. Do not divide by two without a concurrency benchmark. Fund only jobs that fit the shared 12-hour batch; defer complete matched comparison groups when they do not fit. Before full launch the manifest must contain a numeric measured wall-clock estimate and batch count. No pilot runtime has yet been measured, so this plan does not invent a completion time or optimal trial count.

Continue in batches of `max(4,d)` feasible trials. Use the paired block standard error of candidate-control objective differences as a validation-noise floor. Stop after two batches with improvement below that floor, stable parameter rankings under block resampling, and no unresolved improving boundary. For a one-dimensional path, stop when its minimum is bracketed and refinement cannot distinguish neighbours. These are saturation diagnostics, not confirmatory evidence or proof of a global optimum.

Expand bounds only when several feasible near-boundary trials consistently improve beyond the paired noise floor and retain adequate support. Move to the next profile/path-derived candidate rather than automatically multiplying bounds by ten. If runtime/storage limits stop the study before saturation, mark it budget-limited, retain the best tested result and report justified next trials. Do not call resource exhaustion convergence.

Prune only after comparable completed pilot/batch results support a reference distribution, using at least two completed inner blocks. Refit with selected normalized controls and the measured best-iteration rule; record exact effective raw parameters, convergence and actual leaf support. Resume by fingerprint, without reusing later information.

#### Deliverables and acceptance

Every model page must show **data profile → proposed bounds → pilot evidence → refined bounds → trials used and stopping reason**. Deliver `data_shape_profile.json`, `search_space_manifest.json`, pilot results, `search_budget.json` and full path/Optuna histories. Show empirical near-best ranges and their fold variation, not an unsupported universal optimal interval. Keep hyperparameter importance separate from predictive feature importance.

Test invariance of normalized penalties/origin-support measures when lead rows are duplicated with total origin weight preserved; time isolation of profile/bounds; fresh profiling for smaller NOS/period cohorts; nonempty purged seven-day validation; rank-deficient/constant designs; solver penalty translations; and study resume/cost accounting. A static numeric table or fixed trial count without profile and pilot evidence no longer satisfies HPO completion.

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

Display numeric metrics in this order: **MAPE (%, assessment only), MAE (MW, primary objective), DR-NMAE (%, named reference policy)**, followed by RMSE, bias, P95 absolute error, skill against the corrected incumbent/persistence, and overstatement measures. Risk measures remain incident recall at budget, false alarms/day, warning lead, precision, Brier score and log loss; MAPE is not a classification metric. Capacity overstatement uses positive `prediction − actual` after directional normalization.

Define ordinary MAPE as `100 × mean(abs(prediction − actual) / abs(actual))`. It is undefined at exactly zero and unstable near zero. Never silently replace zero with machine epsilon, cap errors, or drop difficult outcomes from MAE/risk scoring. Report ordinary MAPE on nonzero observations, with its nonzero denominator count, and label the full-population ordinary MAPE undefined if zero observations occur. Negative-limit rows use an absolute denominator and receive a separate forced-direction slice.

The displayed assessment percentage metric is explicitly labelled **MAPE, |actual| ≥50 MW**. Show its eligible count and coverage beside it, plus 25/100 MW threshold sensitivities. This is a conditional MAPE, not full-population MAPE, and it is never an optimization, early-stopping, routing or promotion objective. Fix the 50 MW threshold before fitting; all models use the same actual-based eligibility mask. Make near-zero/zero counts, their MAE and their overstatement rates visible alongside it. The numerical concern is documented in [scikit-learn's MAPE reference](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_absolute_percentage_error.html).

Main point-model optimization and selection minimize `MAE_MW = sum(w × abs(prediction−actual))/sum(w)` over all target-eligible observations, including zero, near-zero and negative directional limits. Retain the existing origin-balanced training weights and equal inner-block objective aggregation; publish both policy-weighted and ordinary row-weighted assessment metrics. MAPE coverage never changes the primary objective or removes rows from it. Preserve conditional incident MAE, WIS and interval coverage/width. The earlier MAPE optimization eligibility rule and its MAE fallback are superseded.

#### Directional-reference percentage-error challenger

Test `DR-NMAE (%) = 100 × sum(w × abs(prediction−actual)/C)/sum(w)`, where C is a positive, versioned **direction-specific capacity reference available at forecast issue time**. This measures forecast error relative to the directional IC limit reference; it is not ordinary MAPE. Dividing by the future realised directional limit would simply reproduce MAPE and is not admitted as a new objective. Keep the target and final forecast in MW; this is an alternative loss, not a forecast of future error.

Use two diagnostic denominator definitions without creating an unrestricted new search axis:

* **Fixed reference:** a verified positive directional engineering limit effective and known at issue time, where recoverable; otherwise a clearly labelled training-only median absolute nonzero directional limit as a statistical scale. Freeze the reference within the study for this control. If C is constant within a separately fitted connector/direction cell, DR-NMAE is just rescaled MAE and cannot change the optimum. Compute it for assessment without duplicating HPO. A future pooled model may change cell weighting; treat that as a separately declared pooling experiment.
* **Time-varying reference:** the magnitude of the latest admissible observed limit for the same connector/direction at the origin, floored at the training-only 10th percentile of positive absolute observed directional limits: `C(origin)=max(abs(last_known_limit(origin)), floor_train)`. Profile the floor, denominator distribution, resulting weights and effective origin/day support inside each inner training split, then refit the rule on outer training. Use 5th/20th-percentile floors only as prespecified sensitivity diagnostics, not extra outcome-selected objective variants. This floor is a robust training-derived scale, not a physical minimum capacity. If positive reference support is absent, the challenger is unavailable. For missing/stale observed references, use the frozen training median and record fallback frequency; apply the same observed-data freshness contract as the base predictor. Never substitute a future actual, model prediction or future NOS-derived derating into C.

The time-varying version deliberately gives more weight to errors when known directional capability is low. It can therefore favour different operating regimes from MW-MAE; quantify this using per-period, contraction, zero/near-zero, forced-direction and reference-fallback slices. Negative known limits use their absolute magnitude with a separate sign flag. Preserve every target-eligible row through the declared denominator fallback and use identical reference arrays for all compared models. Store source timestamp, floor, denominator and reference-policy ID with predictions.

For native absolute-error estimators, fit with weights proportional to `w/C`, normalizing total training weight to preserve regularization conventions, and tune on held-out DR-NMAE. Audit realized effective weights and block support before admitting the study. Squared-loss families may be DR-NMAE-tuned surrogate challengers, explicitly labelled; do not claim their weighted squared fitting loss equals this objective. Compare each challenger with its matched MAE-tuned counterpart on the same folds, features, rows and compute policy, showing MAE, DR-NMAE, assessment MAPE and risk guardrails. Record fitting loss, HPO loss, final policy-selection loss and reference provenance in each model bundle. Retrain neither on assessment MAPE nor on evaluation errors.

The main recommended point policy remains selected by MAE and the frozen promotion gates. A DR-NMAE challenger may become the main choice only if it also wins that MAE-based selection and passes the same gates. If it improves relative-capacity error but worsens MAE, report the tradeoff as an alternative, not an automatic replacement. Use matched ablations to distinguish denominator weighting from calendar/NOS feature gains.

For warning-rate denominators, use eligible observation exposure in 24-hour equivalents: eligible half-hour issue count /48. Also show the legacy distinct-calendar-day denominator for reconciliation. Apply the exposure convention to controls and challengers alike, and use common directional eligibility when enforcing the joint budget. Data gaps cannot create apparently cheap alarms by counting a partially observed day as a full day.

Retain exact lead results. The first-band pooled score averages five representative leads and must not be labelled performance at every half-hour lead. Evaluate all 336 curve steps at the first eligible issue of each evaluation day for shortlisted finalists, and report horizon-boundary jumps separately from time-period boundaries.

### 6.2 Statistical comparison

Use 2,000 paired moving-block bootstrap replicates with seven-day calendar blocks, retaining all directions, leads and candidates together. For incident summaries attach the complete match result to incident onset day and unmatched alarms to issue day; never rematch duplicated synthetic timelines. Repeat with 14-day blocks. Run leave-one-major-outage-chain-out influence summaries as diagnostics to identify gains dominated by a single episode.

For confirmatory numeric claims, use a prespecified Holm correction jointly across the eight hypotheses from four primary connector-direction cells against two baselines. Use a separate two-connector family for risk claims. Report effect sizes and paired intervals; exploratory period/family slices are labelled exploratory. No fixed-plus-rolling pooling, row-level independent bootstrap or post-evaluation model replacement is permitted.

Apply Holm jointly to the eight primary numeric candidate-minus-baseline hypotheses (four cells × two controls), rather than treating the two controls as independent chances to claim success. The headline compares the selection-frozen policy, not whichever evaluated family ranks first. For a broad exploratory leaderboard, also report a 90% Model Confidence Set per cell using matched daily losses and the same dependence-block sensitivity; freeze membership before evaluation and label the result development-only. MCS does not remove tuning or repeated-look bias and does not replace prospective confirmation. No applicable repository/ancestor `AGENTS.md` requiring MCS was found in this review; this conditional reporting requirement is methodological, not an attributed repository rule. See [Hansen, Lunde and Nason (2011)](https://doi.org/10.3982/ECTA5771).

### 6.3 Explicit default gates

These are proposed engineering thresholds, frozen before the new campaign; they are not literature-derived universal cutoffs.

| Selection | Required evidence |
|---|---|
| Accuracy finalist | At least 5% first-band minimum-limit MAE improvement over the corrected incumbent; beats persistence on MAE on identical target-eligible rows; positive paired MAE improvement evidence after the declared multiplicity rule. MAPE is assessment-only; a DR-NMAE challenger must meet these same MAE gates for main-policy promotion |
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
| A2. Data profile and tuning pilots | Fold-local design profiler and search-space builder | Measured origin/episode support, weighted spectra, dependence and fit costs; justified ranges and adaptive trial budgets before full search |
| B. Calendar experiments | `nemic/experiments/data.py`, `models.py`, runner/config | T0–T6, chronological residual correction and period fallback with fold-local selection |
| C. NOS store | New outage ingestion/as-of module plus existing parser/store | Hashed snapshot inventory, compact revisions, coverage and temporal negative controls |
| C2. Pre-model outage impact analysis | New episode/matched-control analysis and impact-report modules | §3.6 asset/set/family rankings, typical/tail/cumulative effects, regime/overlap diagnostics and training-only feature manifest, completed before NOS-aware fitting |
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

Link the §3.6 pre-model outage impact report and carry its supported highest-impact asset/set/family tables into the final report. Beside each observed-impact finding show whether the corresponding feature subsequently improved held-out forecasts, its permutation/SHAP evidence and its retain/revise/remove verdict. Preserve rare-severe and insufficient-support cases separately; do not substitute model feature importance for an outage impact estimate.

Include a model catalogue listing every baseline, tuned family, specialist, blend/fallback policy and event model that entered evaluation. Identify feature blocks, target, training window, search objective, initial/refined search bounds, trial budget consumed, best trial, exact parameters, effective tree count, runtime, convergence and eligibility. Each range and allocation must link to its measured data profile and pilot evidence, including normalized-to-raw parameter translation and stopping reason. Show fixed/default and optimized results separately. Hyperparameter trials appear in an appendix; do not misrepresent every trial as an independently tested model.

For every evaluated candidate policy, give MAPE-first/MAE-second tables by connector, direction, minimum/mean limit target, exact lead/band, period and rolling fold. Include counts, percentage-metric coverage, paired differences against controls, intervals, risk measures and failed/unavailable cells. Save evaluation predictions for **every evaluated candidate policy**, not merely the winner; retain trial-level validation summaries for unselected hyperparameter trials. Store compressed partitions and budget them before launch.

### 9.2 Actual-versus-forecast limit graphs with aligned tables

Provide both (a) a fixed-issue forecast curve over delivery time and (b) a rolling forecast trace at one fixed lead. Never silently splice different leads or forecasts issued after delivery. Overlay actual limits, selected model, incumbent/persistence and selected quantile bands; allow comparison with any evaluated model. Keep signed negative limits and missing-data gaps visible. Show issue time, NEM delivery time, lead, model/version and scheduled outage transitions known at that issue.

Place a metrics table directly below each chart, computed on exactly its plotted, matched observations: qualified MAPE and its coverage, ordinary nonzero MAPE, MAE, RMSE, bias and >100/>200 MW overstatement. Keep full-period metrics in a separate table. Show interval coverage/width when enough observations exist; otherwise show sample size and insufficient support.

Include the first eligible full issue day of every evaluation month as prespecified ordinary examples, the existing daily 336-step finalist curves, and the up-to-20 diagnostic event cases per connector. For every non-finalist candidate, retain enough fixed-lead traces and configured-lead curves to support actual-versus-forecast inspection. Charts of sparse configured leads must display their actual points and identify any connecting lines as interpolation. Missing model coverage is shown explicitly.

### 9.3 Feature importance for every evaluated model

Use held-out grouped permutation importance as the common performance-based measure. Rank numeric-model permutation importance by full-population MAE degradation; also report DR-NMAE and qualified assessment MAPE changes, and Brier/log loss for risk models, with week-block uncertainty. Use five deterministic whole-day block permutations on a shared evaluation sample. Move correlated feature groups together; recompute derived interactions, routing and persistence anchors when their source group changes. For daily calendar importance, apply a seeded nonzero circular phase offset of 1–47 half-hours independently to each complete day, move sine/cosine and period columns coherently, and recompute routing/interactions. Whole-day shifts alone would leave hour-of-day unchanged. Label all perturbations as model-sensitivity diagnostics.

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

End with a clear decision table: recommended point model per connector/direction/target/band, recommended contraction model, exact parameter-set ID, MAPE and MAE versus both controls, risk guardrails, source eligibility, fallback and artifact path. Explain why the closest alternatives lost. If DR-NMAE and MW objectives disagree, show the tradeoff and retain MAE-based main-policy selection. Assessment MAPE cannot select or promote a model. Report a single model of choice only where one model genuinely wins the required cells; otherwise deliver an explicit routed collection.

Separate “best tested historical model” from “eligible for live use” and “prospectively validated.” A no-improvement result still requires a trained incumbent/fallback handoff and a clear verdict. No blanket winner may be selected using evaluation scores and then presented as if chosen before those scores.

Require a three-part diurnal attribution table for every primary cell: **mean shape** (T1 minus T0 with the same drivers), **driver sensitivity** (T2/T3 minus T1 with matched additive calendar basis, feature support and tuning policy), and **uncertainty** (period-conditioned minus pooled calibration applied to the identical frozen point model and residual history). If existing recipes do not nest, add the matched control explicitly to the bounded manifest. Report paired MAPE/MAE changes for point components and WIS/coverage/width for uncertainty, including no gain/inconclusive outcomes. Explain any further residual-specialist or boosting gain separately. These are incremental predictive ablations, not causal physical decompositions; never call a mean-shape-only improvement evidence of changing driver sensitivities. Include the conditional NOS/forward-fundamentals verdict and historical support gate alongside the model-choice table.

Binding/non-binding status is a diagnostic operating-regime slice, not a label-validity rule. Targets are AEMO's reported calculated directional limits; flow not reaching a limit does not invalidate that target. Preserve checks for missing/invalid records, sign conversion and timestamp alignment. Do not filter valid non-binding observations or substitute realised flow for capacity. See [AEMO dispatch interconnector fields](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_127.htm).

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

Before delivery, test reload/prediction parity, missing/stale NOS fallbacks, required-column/schema rejection, signed import conversion and calibration/feature-order integrity. Validate Optuna resume and cutoff isolation; MAE objective and promotion wiring; fixed-reference DR-NMAE equivalence to scaled MAE; time-varying reference as-of isolation, training-only floors, weight normalization and stale/missing fallback; MAPE zero/negative/tiny-limit assessment behaviour and denominator parity; SHAP reconstruction and output units; and chart/table row alignment. Open and visually verify the offline report, selectors, waterfalls and downloadable chart assets. Verify that every model in the catalogue has a result section and explanation, or a concrete unavailable/failed status with reason. Link the final report, trained bundles and exact parameter files in the handoff response.
