# Interconnector contraction, generator influence and price-event analysis

**Version:** 1.1
**Prepared:** 12 September 2026
**Status:** Reusable methodology and implementation specification. This document proposes an event-analysis extension; it does not claim that the extension, price attribution or dispatch counterfactuals have already been run.
**Initial application:** Australian National Electricity Market (NEM), with connector-specific adapters.
**Default study:** Two explicitly dated years, five-minute resolution, maximum 10 GB of study working storage.

## 1. Purpose and questions

Build a reproducible event atlas that explains rapid changes in interconnector transfer capability, the generator movements and constraint equations associated with them, and their relationship to regional price volatility.

The methodology must answer:

1. When did directional capability contract, by how much, and for how long?
2. Which reported limit-setting equations, binding equations and competing restrictions were present before, during and after the event?
3. Which generator dispatch changes mechanically tightened or relieved those restrictions?
4. How much of the change is consistent with generator movement, RHS movement, other equation terms, or a change in the applicable equation population?
5. Did actual flow respond, reverse, or become forced into a direction?
6. Did the receiving region experience a price jump, sustained price separation, or a market price cap (MPC) event?
7. What distinguishes economically consequential contractions from ordinary ones?
8. Which compact, available-in-advance features improve out-of-sample forecasts?

The analysis has three separate outputs: observed event facts, equation-based mechanical attribution, and evidence about price associations. Stronger causal conclusions require an additional validated counterfactual study.

## 2. Principles and interpretation

- A reported limit, a reconstructed conditional bound and actual flow are different quantities.
- A generator in an equation is not automatically a cause of a contraction. Its movement, coefficient, timing and the equation's relevance must be examined.
- Generators can tighten a limit by ramping up **or down**, depending on coefficient and direction. Pumps, batteries and other controllable loads must be represented correctly.
- A dispatch target is not a measured physical startup. Use “dispatch increased” unless initial MW, metering or other evidence establishes actual operation.
- A leading reconstructed restriction is not automatically a confirmed binding equation.
- Regional prices and dispatch are jointly determined. Temporal ordering helps interpretation but does not remove common causes or establish causality.
- Preserve unknown attribution and reconciliation error. Do not force every contraction into a generator explanation.
- Constraint-derived features describe operational restrictions; they are not a complete reconstruction of physical network topology.
- Missing observations are not zero generation, unconstrained operation or zero price.
- All key assumptions, thresholds, version rules and data exclusions are machine-readable and versioned.

## 3. Generalization through a connector adapter

Keep event detection, attribution, statistical analysis and reporting generic. Isolate market and connector conventions in an adapter.

### 3.1 Required adapter fields

| Field | Requirement |
|---|---|
| Identity | Market, connector ID, display name and effective dates |
| Endpoints | Region A, Region B and any relevant intermediate or external areas |
| Orientation | Positive signed flow means A to B; source-field transformations documented |
| Limits | Transform reported fields into a signed lower bound and upper bound |
| Dispatch granularity | Interval duration, interval-ending convention, timezone and revision rules |
| Constraint model | Inequality directions, coefficient units, applicable versions, invocation rules and supported term types |
| Asset model | Generator/load IDs, connection points, registration changes and station aggregation |
| Price model | Regional prices, currency, units, effective-dated caps and special pricing regimes |
| Connector technology | AC/HVDC, regulated/market-network arrangements, losses and control or availability restrictions |
| Related network | Other connectors, shared equations and parallel transfer paths needed for interpretation |
| Source scope | Allowed tables, archive families, date filters and dependency selection rules |

Never inherit another connector's sign conventions, capacity scale, generator shortlist, applicable equations or reconstruction accuracy without validation. Validate orientation against published definitions and a sample of source records.

### 3.2 Canonical quantities

Let signed flow be `F`, positive from A to B. Normalize the feasible interval to:

```text
lower_bound <= F <= upper_bound
capacity_A_to_B = upper_bound
capacity_B_to_A = -lower_bound
headroom_A_to_B = upper_bound - F
headroom_B_to_A = F - lower_bound
```

Directional capacities are signed. Preserve negative values: a negative upper bound requires flow toward A, while a positive lower bound requires flow toward B. Do not take absolute values or clip these observations to zero. Headroom is slack in the signed feasible interval; negative headroom is a diagnostic requiring review, not a value to hide.

Define the directional price spread as `price_receiving_region - price_sending_region`, using the direction under study. Keep the signed A/B price spread separately for consistent plotting.

For parallel connectors, retain individual reported limits. Do not present their simple sum as jointly feasible corridor capability unless a joint model supports it. Link shared incidents and equation dependencies across connectors.

For controllable links, outages, link availability, control modes, ramping and offer-related limits may explain changes that a generator-coefficient decomposition cannot. Mark unsupported mechanisms explicitly.

## 4. Study specification and defaults

Freeze exact start/end timestamps and the interval ownership rule. For a two-year study, use 24 consecutive complete months where available; do not silently extend to four years. Retrieve small boundary buffers for lag calculations and event recovery, but exclude them from the study denominator.

The following are proposed defaults, not universal physical definitions:

| Parameter | Default and purpose |
|---|---|
| Observation interval | 5 minutes for the NEM |
| Primary contraction horizon | 30 minutes |
| Sensitivity horizons | 5, 15 and 60 minutes |
| Retrospective threshold | 90th percentile of strictly positive 30-minute capacity falls, separately by connector, direction and year-month |
| Absolute severity bins | 250, 500 and 1,000 MW, retained for comparability but supplemented by connector-normalized measures |
| Relative severity bins | 10%, 25% and 50% of a declared positive reference capacity |
| Initial event window | 120 minutes before and 120 minutes after detection |
| Parent-incident grouping | Same connector/direction episodes separated by at most 30 minutes; test 15 and 60 minutes |
| Recovery | At least 90% of incident capability loss restored for three consecutive valid intervals |
| Near-binding / near-setting | Initially 50 MW in IC-equivalent units where meaningful; also test connector-scaled alternatives |
| Near MPC | At least 90% of the applicable MPC; exact hits recorded separately |
| Main price response window | Detection to +60 minutes; also show -60 to 0 and +60 to +120 minutes |
| Storage | 10,000,000,000 bytes peak study working storage; cleanup trigger at 8,000,000,000 bytes |
| Minimum free disk | 20,000,000,000 bytes, configurable before execution |
| Archive concurrency | One archive at a time |

Specify a minimum threshold reference sample, proposed as 100 positive falls. If insufficient, report the percentile detector as unavailable; any fallback reference must be separately named and flagged. Record the empirical quantile interpolation method and software version.

Cross-connector comparisons use both absolute MW and relative measures. A 250 MW cutoff alone is unsuitable for smaller links.

## 5. Data requirements and sufficiency tiers

### 5.1 Minimum source inventory

| Dataset | Required fields or concepts | Purpose |
|---|---|---|
| Interconnector results | Timestamp, flow/target and metered flow where available, directional limits, reported setters, run flags | Observed event detection |
| Regional prices | Five-minute final price, original/adjusted price where available, intervention and administered/suspended status | Price-event screening |
| Regional conditions | Demand, renewable output/forecast, available generation and reserve context where available | Context and matching |
| Generator dispatch | DUID, target MW, initial MW, availability, ramp limits and run identity | Movement reconstruction |
| Constraint solutions | Equation ID/version, RHS, marginal value, violation and LHS or inputs to reconstruct it | Binding and attribution |
| Equation definitions | Effective dates, all supported LHS factors, relation type, description and term units | Sensitivities and reconciliation |
| Constraint sets | Membership and actual invocation/withdrawal history | Operational applicability |
| Asset mappings | Effective-dated connection-point/DUID mapping, station, region and dispatch type | Correct attribution |
| Price settings | Effective-dated MPC and applicable administered/suspension settings | Price classification |
| Optional event evidence | Outages, notices, bids/rebids, link controls, telemetry and forecast vintages | Mechanism review and stronger inference |

For a NEM adapter, start from `DISPATCHINTERCONNECTORRES`, `DISPATCHPRICE`, `DISPATCHREGIONSUM`, `DISPATCHLOAD`, `DISPATCHCONSTRAINT`, `GENCONDATA`, `GENCONSET`, `GENCONSETINVOKE`, `DUDETAILSUMMARY`, `SPDINTERCONNECTORCONSTRAINT` and `SPDCONNECTIONPOINTCONSTRAINT`. Add other factor tables or inputs only when needed to represent the selected equations. Confirm actual schemas and field availability for each historical period.

Applicable dispatch sources are described in [AEMO's dispatch data documentation](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/dispatch). The table list above is a proposed extraction scope, not an instruction to download every record in those tables.

### 5.2 Evidence tiers

| Tier | Available evidence | Permitted output |
|---|---|---|
| A: screening | Limits, flows and price history | Observed event catalogue and price association screening |
| B: mechanical overview | Tier A plus retained sensitivities and generator pressure | Preliminary movement attribution, with reconstruction caveats |
| C: reconstructed case | Full selected-window dispatch, equation solutions and effective versions | Binding timeline and reconciled mechanical decomposition |
| D: corroborated case | Tier C plus relevant external operational evidence | Supported mechanism narrative |
| E: counterfactual | Validated dispatch replay or another defensible causal design | Conditional causal estimates under documented assumptions |

Publish a sufficiency matrix for every event. Price completeness, unit coverage and equation completeness are separate dimensions.

The existing VNI/QNI compact studies are starting points, not a guarantee of Tier C. Audit local inventories first. Retained pressure files may omit raw dispatch trajectories and full interval equation states following cleanup; recover only the selected windows needed to fill those gaps.

## 6. Data normalization and quality audit

1. Inventory local files, schema versions, dates, hashes, sizes and duplicate archive coverage before downloading anything.
2. Normalize timestamps. In the NEM use fixed UTC+10 market time and interval-ending timestamps; optionally display civil time separately with its timezone label.
3. Build exact interval grids. Use timestamp-based lag joins, not six-row shifts unless uninterrupted five-minute spacing is established.
4. Resolve revisions deterministically using market rules and source provenance. Audit conflicting records; retain the chosen record's run and revision identifiers.
5. Distinguish physical dispatch runs from pricing runs. Do not assume intervention flags select the same run for both purposes. Preserve flags and exclude or separately analyze incompatible observations.
6. Preserve raw and normalized limits side by side. Validate orientation, forced-direction cases and reported setter mapping.
7. Join equation versions and asset mappings as of the applicable interval, including invocations that began before the study/window. Log all fallbacks; unknown versions remain unknown.
8. Separate measured MW, initial MW and target MW. Align snapshots to their actual timing.
9. Audit five-minute regional price coverage and revision handling. Do not substitute half-hour averages for MPC detection.
10. Emit coverage counts by connector, direction, month, season, year, hour, source and event window.

Do not interpolate through outages in the data to create event detections. Cross-gap event durations and recovery are censored. Missingness and duplicates must be resolved before denominator calculations.

## 7. Event detection and incident construction

### 7.1 Primary contraction definition

For canonical directional capacity `C_d(t)` and horizon `h`:

```text
drop_d,h(t) = C_d(t-h) - C_d(t)
threshold_ic,d,year-month = Q90({drop_d,30m(t): drop_d,30m(t) > 0})
sharp(t) = valid_pair(t,t-30m) AND drop_d,30m(t) > 0
           AND drop_d,30m(t) >= threshold_ic,d,year-month
```

Ties may make the qualifying share exceed 10% of positive falls. The threshold does not mean 10% of all intervals are events. Save thresholds and reference sample counts.

Define a detection episode as consecutive valid qualifying intervals. Count its first interval as the detection onset. Stitch month boundaries before episode counting; changing monthly thresholds can change classification at a boundary and must be visible.

Retrospective year-month thresholds use information from later in that month. They are valid descriptive labels, but must not be treated as available-at-the-time forecast features. For forecasting, freeze training-only thresholds or compute a trailing reference using only observations available at the forecast origin.

### 7.2 Event landmarks

Store detection onset separately from a retrospective estimate of physical contraction start. A reproducible baseline rule is: choose the latest occurrence of the highest valid directional capacity in the preceding 30 minutes, then identify the first subsequent material decrease. Declare the noise tolerance and flag discontinuous or ambiguous paths. Describe this as an estimated start, not an observed initiating cause.

Find the trough and recovery in the expanded incident window. Recovery is the first sustained crossing of `trough + 0.9 * (baseline - trough)` under the configured persistence rule. If no recovery is observed, label right-censored and report observed duration only. Store detection-time drop and baseline-to-trough drop separately.

Group nearby same-direction episodes into parent incidents without deleting their identities. Transitive grouping can create long incidents; report their duration and constituent count. Opposite-direction and other-connector events receive links rather than being silently collapsed.

### 7.3 Additional event attributes

- Absolute capacity drop, percentage of baseline and percentage of a declared reference capacity.
- Baseline-relative percentages only when the baseline is materially positive; otherwise mark undefined.
- Headroom before/after, loss of headroom, and whether the limit became operationally restrictive.
- Flow change, reversal, forced direction, actual versus scheduled flow differences.
- Duration, recovery time, minimum capability and missing-data censoring.
- Equation switch, set invocation, link-availability change and pricing-regime flags.
- Exposure rates per 1,000 valid hours, not just counts.

Run sensitivity analyses over horizons, percentile cutoffs (for example P85/P90/P95), absolute/relative severity and incident grouping. Keep versions of the event catalogue rather than replacing earlier definitions invisibly.

## 8. Event selection without outcome cherry-picking

Screen the full eligible period cheaply before recovering detailed records.

### 8.1 Network-first selection

Include severe absolute and relative contractions, large headroom losses, forced-direction events, substantial equation switches and a stratified sample of ordinary events across directions, seasons and years.

### 8.2 Price-first selection

Detect all exact MPC and near-MPC episodes in either endpoint region, extreme price changes and exceptional directional spreads independently of contraction detection. Search their surrounding windows for preceding, simultaneous or subsequent network events.

Retain four groups: contraction with price shock; contraction without shock; shock without sharp contraction; and matched periods with neither. “No sharp contraction” does not imply absence of congestion.

Prioritize detailed recovery for all MPC-linked candidates, severe network events and representative comparison cases. If storage or source availability limits coverage, retain the complete screened catalogue and publish the deep-dive selection rule and unresolved queue. Do not imply all events have detailed reconstruction.

Freeze ranking and selection rules before interpreting named generators. Record sampling seeds and inclusion probabilities where appropriate. Population estimates use the full screened population or suitable weights, not an unweighted hand-selected gallery.

## 9. Binding equations and candidate populations

For each selected window, retrieve the union of reported setters, applicable direct-IC equations, binding/near-binding candidates and relevant invoked-set dependencies. Include units outside the connector's endpoint regions when those equations reference them.

Maintain separate indicators for:

| Indicator | Meaning |
|---|---|
| Reported setter | Equation named in the published directional-limit record |
| Reconstructed leading | Equation producing the most restrictive supported conditional bound |
| Economically binding | Non-zero marginal value, subject to a declared numerical tolerance |
| Geometrically tight | LHS close to RHS under the declared scaled tolerance |
| Violated | Non-zero violation under its own tolerance |
| Near-binding | Small feasible slack; not equivalent to economically binding |
| Near-setting | Conditional bound near the leading directional bound |
| Invoked | Active operational applicability established from source records |

AEMO identifies binding constraints through non-zero marginal values; preserve degeneracy and numerical-tolerance distinctions when comparing this with geometric slack. [AEMO constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq)

Do not duplicate contributions across multiple set memberships of the same equation. For equations with no target-IC coefficient, retain contextual relevance but do not invent a direct MW sensitivity. Very small IC factors require numerical diagnostics; report unstable sensitivities rather than silently clipping them.

Candidate-set completeness matters: discovery from historical binding records alone can omit restrictions that become relevant in a counterfactual. Mark such a counterfactual partial.

## 10. Mechanical attribution

### 10.1 Fixed-equation sensitivity

Normalize an inequality to:

```text
a * F + sum(b_i * P_i) + Z <= R
conditional_bound B = (R - sum(b_i * P_i) - Z) / a
sensitivity_i = -b_i / a
```

Here `R` is the RHS; `Z` contains represented non-generator terms, including other ICs or service quantities where relevant. These terms must retain their correct units. If `a > 0`, the equation defines an upper bound; if `a < 0`, it defines a lower bound. Normalize greater-than inequalities first; handle equalities explicitly rather than pretending they are ordinary one-sided restrictions.

With fixed coefficients:

```text
delta_B_generator_i = -(b_i / a) * delta_P_i
delta_B_RHS = delta_R / a
delta_B_other_terms = -delta_Z / a
delta_B = sum(delta_B_generator_i) + delta_B_RHS + delta_B_other_terms
```

Convert bound movement into directional capacity movement: `delta_C = delta_B` for an upper/A-to-B bound and `delta_C = -delta_B` for a lower/B-to-A bound. Tightening is `-delta_C`; relief is the opposite sign.

RHS contribution is not necessarily an independent physical cause: RHS formulations can themselves depend on generation, demand or other system inputs. Without their formulation/input history, call it “RHS movement,” not “network outage effect.” Avoid attributing the same underlying change twice.

### 10.2 Generator contribution metrics

For each unit, equation and step, retain starting/ending dispatch, delta MW, factors, sensitivity, signed bound impact, directional tightening/relief, physical-run provenance and applicability.

Calculate five-minute contributions and telescoping sums within fixed-equation segments. Retain 30-minute impacts as contextual diagnostics. Do not add overlapping rolling 30-minute impacts to estimate one incident's net MW loss. Existing MW-observation totals measure accumulated exposure and are neither MWh nor an event's unique contraction magnitude.

Provide separate unit-level and station-level summaries, with effective-dated mappings. Distinguish generating and consuming modes, particularly for batteries and pumping loads.

### 10.3 Equation switches and coefficient changes

Split the event whenever the relevant equation, version or supported term structure changes. Within a segment, use the fixed-equation identity. Across a switch, use a declared bridge, for example:

```text
B_new(x1) - B_old(x0)
  = [B_new(x1) - B_old(x1)] + [B_old(x1) - B_old(x0)]
```

The second bracket measures movement under the old formulation; the first measures changing formulations at the final input state. This is an accounting convention, not a unique causal allocation. Inputs `x` include the necessary dynamic RHS information. If an old equation's final-state RHS cannot be evaluated, leave the bridge unresolved.

Where both bridges are computable, show sensitivity to using old-state versus new-state ordering. Activation/deactivation, unavailable terms, and version changes are explicitly visible in the bridge.

For a supported candidate set, the upper envelope is the minimum upper bound and the lower envelope the maximum lower bound. Recompute that envelope when testing generator scenarios; changing one generator can cause a different equation to become leading.

### 10.4 Reconciliation and confidence

Use this accounting chain:

```text
observed directional-capacity change
  = reconstructed conditional-envelope change
    + change in observed-minus-reconstructed discrepancy

reconstructed change
  = generator terms + RHS terms + other represented terms
    + switch/version bridge + unresolved components
```

Never label the entire discrepancy as topology, outage or a generator effect. Show net MW, gross tightening and gross relief separately. Gross tightening may exceed net observed contraction when relief offsets it.

Assign an evidence grade using source completeness, exact-version coverage, applicability, price coverage and event-specific reconstruction error. Publish the underlying values. Proposed high-confidence tolerance is `max(10 MW, 5% of observed event loss)` for the absolute event residual, subject to validation for each adapter; it is not a guaranteed accuracy claim.

## 11. Mechanism review and language

Classify units as mechanically tightening, mechanically relieving, responsive, or unresolved. A unit can take different roles in different portions of one event.

Classify event mechanisms as generator-dominant, RHS-dominant, equation-switch-dominant, link-control/availability, mixed, or unresolved. Define dominance thresholds in configuration, apply them only after adequate reconciliation, and retain the full decomposition. A provisional majority-of-gross-tightening rule can be reported as descriptive, not causal.

Build a timestamped evidence sequence: availability/outage or notice; dispatch movement; equation invocation/tightening; constraint binding; loss of headroom; flow response; price response. Five-minute timestamps cannot order processes within the same interval; flag simultaneous observations.

Use “consistent with,” “mechanically contributed under the equation,” and “associated with” according to evidence. Do not infer strategic intent from a rebid, or say a generator caused an MPC event solely from coincident dispatch.

## 12. Price-event methodology

### 12.1 Price integrity and labels

Use interval-level regional prices, retaining adjusted/original price fields and applicable flags. AEMO describes five-minute price records and price adjustments in its [MMS data-model specification](https://www.aemo.com.au/-/media/files/electricity/nem/planning_and_forecasting/solar-and-wind/enablement-of-bid-max-avail-for-semi-scheduled-generators/emms-technical-specification-data-model-v52.pdf?hash=64FD0EEF28D98CA8B97A9256B64A8147&la=en). Validate historical schema changes before implementation.

Join an effective-dated market settings table; do not hard-code one MPC for a multi-year study. Exact MPC uses a declared rounding tolerance. Near-MPC uses a configurable fraction. Keep administered pricing, suspension, intervention and other price adjustments as separate regimes. Reference settings to official [AEMC publications](https://www.aemc.gov.au/); store the supporting publication URL for each effective period.

Define price-jump and spread events with both fixed monetary cutoffs and region/time-specific historical percentiles. Publish all selected cutoffs. Include negative price shocks and sending-region price collapses, as well as receiving-region scarcity.

### 12.2 Outcomes per incident

- Peak and minimum endpoint prices; absolute and baseline-relative changes in currency/MWh.
- Exact/near-MPC interval counts and duration, kept separate from other caps.
- Directional price-spread peak, change and duration.
- Price timing relative to detection and estimated contraction start.
- Flow/headroom alignment: was the restriction on the direction that could supply the stressed region?
- Time-integrated price or spread excess as a descriptive exposure measure; label units carefully. It is not total system cost, welfare loss or trading profit.
- Concurrent changes in demand, renewables, available supply, other ICs and applicable pricing regime.

Do not calculate an “MPC caused by generator” count from association alone. Report mechanically attributed events associated with MPC, including sample sizes and confidence grade.

## 13. Statistical analysis and comparison periods

### 13.1 Matched event study

Match contraction events to candidate controls on pre-event season/year, hour, weekday, demand, renewable output, availability, price, flow, directional headroom and known restriction regime. Do not match on post-event outcomes or variables changed by the event. Define control exclusion windows and record all unmatched events.

Evaluate common support, standardized covariate balance and pre-event trends. Show raw event-time trajectories and matched differences. A price-shock-without-contraction group is an additional diagnostic, not automatically a valid causal control.

For each horizon, estimate price/spread differences and uncertainty. Cluster resampling by parent incident or shared system day, including cross-connector linked incidents, to avoid treating overlapping intervals as independent. State model assumptions and multiple-comparison handling for broad generator screens.

MPC outcomes may be rare: report numerators, denominators and uncertainty, avoid stable-looking rankings from a handful of events, and do not interpret no observed MPC as zero underlying risk.

### 13.2 Optional stronger counterfactuals

First use conditional equation scenarios: hold selected unit dispatch at baseline, recompute supported bounds and their envelope, and quantify conditional capacity differences. These are diagnostic scenarios, not feasible redispatch or price predictions.

A price counterfactual requires a validated dispatch model with adequate offers, demand, losses, ramping, availability, relevant energy/FCAS restrictions and intervention treatment. Demonstrate baseline replication before perturbations. Holding one unit fixed requires feasible balancing redispatch. Publish scenario assumptions and unresolved model differences.

## 14. Seasonal, diurnal and cross-connector assessment

Report each study year separately and pooled. For each direction, show event rates per valid hour, loss magnitude, recovery, forced-flow incidence, generator roles, constraint mechanisms and associated price outcomes.

For a NEM study, use Southern Hemisphere seasons. Define season-year explicitly, with summer spanning December to February. Two calendar years of data do not necessarily contain two complete summers at the endpoints; mark partial seasons rather than describing them as complete replicas.

Diurnal charts use market time, with separate weekday/weekend slices where sample sizes permit. Show counts and exposure denominators in every seasonal/hourly comparison.

Cross-connector comparison requires the same event-definition version, coverage rules and price labels, plus connector-normalized severity. Account for common system incidents and shared constraints. Two years provides repeated seasonal observations, not proof of a stable long-term seasonal law.

## 15. Compact forecasting features and evaluation

Use the atlas to select a small direction-specific block rather than adding every DUID to the model:

| Feature family | Examples |
|---|---|
| Capacity state | Current directional capacity, headroom and lagged contraction |
| Generator pressure | Aggregate recent tightening, relief and net pressure under relevant equations |
| Concentration | Largest contributor share and effective number of contributors |
| Switching | Gap to next candidate, recent setter changes and invoked-family state |
| Constraint stress | Near-binding population and supported slack/marginal-value summaries |
| Flexibility | Available relief from participating units under ramp/availability limits |
| Market stress | Receiving-region supply context and lagged directional price spread |
| Quality | Missing inputs, version match and reconstruction confidence |

Begin with approximately 8–12 scalar features per direction plus a small common quality block; choose the final set through ablation. Fit any generator grouping or encoding on training data only.

For horizon-specific forecasts, retain only fields published by the origin time. Actual future dispatch, RHS, binding status, revised prices and full-month thresholds are unavailable future information. Predict them or use archived forecast vintages; never substitute realized values.

Use chronological training, validation and untouched test periods. Keep related incidents and overlapping labels from leaking across splits, with a purge based on the maximum forecast label horizon. Evaluate against persistence, seasonal and market-context baselines. Use MAE and event-tail errors for limits/flow; precision-recall, calibration, recall at a declared false-alarm rate and usable lead time for contractions/MPC risk. Report economic outcome metrics separately from claims of tradable returns.

## 16. Report architecture and graph specifications

Produce one market-level index and a consistent connector report, with event detail pages generated from compact evidence bundles.

### 16.1 Connector report structure

1. Executive findings, study dates, coverage, evidence status and key limitations.
2. Connector orientation, source definitions and event methodology.
3. Population overview: severity, duration, recurrence and prices.
4. Searchable event catalogue with stable IDs and evidence grades.
5. Representative and consequential event case studies.
6. Generator profiles, with tightening and relief separated.
7. Constraint/equation/set profiles and switching behavior.
8. Seasonal, diurnal and year-to-year analysis.
9. Price-event comparisons and statistical uncertainty.
10. Forecast-feature implications and held-out validation, when run.
11. Data quality, source manifest, exclusions and reproducibility appendix.

### 16.2 Population graphs

| Graph | Required display |
|---|---|
| Event map | Capacity loss versus subsequent price/spread response; color mechanism, size duration, click event |
| Coverage/calendar view | Events and missing intervals by date; linked price-event markers |
| Severity distribution | Absolute and normalized loss, duration and recovery; direction filters |
| Seasonal/hourly heatmap | Rates per valid hour, sample sizes and price-linked subsets |
| Generator ranking | Incident frequency, net/gross tightening and relief; sufficient-sample flags |
| Constraint ranking | Binding/setting recurrence, event severity and evidence coverage |
| Event-time curves | Individual trajectories plus median/quantiles and matched uncertainty |
| Mechanism comparison | Reconciled shares and unresolved fraction, including uncertainty/sample sizes |

Do not rank generators solely by cumulative rolling MW-observations. Provide incident-level intensity and unique-event exposure alongside persistence measures.

### 16.3 Synchronized event page

All time-series panels share zoom, cursor and markers for estimated start, detection, trough, recovery, switches and price events.

| Panel | Content |
|---|---|
| 1. Transfer capability | Signed bounds, dispatch/metered flow where available, reconstructed envelope and headroom |
| 2. Prices | Endpoint five-minute prices, directional spread, effective MPC and regime markers |
| 3. Unit dispatch | Top tightening/relieving units, levels and deltas; distinguish targets from measurements |
| 4. Constraint timeline | Setter identity, binding/near-binding flags, invocation, slack, marginal value and RHS |
| 5. Attribution | Signed waterfall from baseline to trough, plus stepwise contributions and residual |
| 6. System context | Demand, renewable output, availability and relevant other-IC changes |

Below the panels include a timestamped narrative, complete before/after equations, factors and units, dispatch changes by DUID, source-backed external evidence, confidence metrics and limitations.

Each contribution tooltip identifies equation/version, unit, coefficient, IC coefficient, sensitivity, time horizon and whether the calculation spans a switch. A schematic dependency diagram may connect units to equations to the IC, but must be labeled as equation participation rather than a physical grid map.

Use consistent direction names, MW and currency units, legible legends, accessible colors and tabular alternatives. Logarithmic price displays must handle negative values explicitly; retain a linear view. Charts must render locally without an active external data service.

### 16.4 Illustrative interpretation

An example waterfall might read: 400 MW contraction = 180 MW generator tightening - 40 MW relief + 200 MW RHS tightening + 60 MW unresolved. This is an illustration, not an observed result. The generator panel would show the underlying dispatch changes, the constraint panel their applicability, and the price panel any subsequent regional separation. The narrative must not convert this accounting identity into proof that the generators caused a price spike.

## 17. Storage, scoped downloads and cleanup

### 17.1 Mandatory download guard

**Never download the entire MMS database or recursively mirror an archive directory.** Every transfer must be tied to a selected table, bounded date range and required connector/equation/unit dependency, or a documented small full-period screening series.

1. Reuse validated local data and manifests first.
2. Build a download plan listing exact URLs/files, table/date scope, estimated compressed and expanded sizes, justification and expected retained outputs.
3. Group selected event and control windows by source archive to extract them in one pass. Avoid downloading the same month once per event.
4. Prefer the smallest official source unit available. If the source only provides a whole-table monthly archive, download that bounded archive, stream-filter it and log that source granularity prevented narrower transfer.
5. Read only required columns/rows, but include all terms required for selected equations; filtering to endpoint-region generators alone is invalid.
6. Process one archive at a time. Check actual bytes during transfer/extraction because size headers and estimates may be absent or wrong.
7. Include temporary downloads, extracted files, staging, retained event bundles and report build copies in the 10 GB study budget. Track shared reused datasets separately and always enforce system free-space reserve. Do not evade the ceiling by moving study files outside the accounted directory.
8. At the 8 GB trigger, clean only validated disposable study artifacts. If the next operation cannot fit under the hard ceiling, stop it, checkpoint and choose a smaller extraction unit or report the blocking source. Never exceed the cap silently.

Suggested initial per-file compressed guard is 600 MB and per-batch expanded guard is 3 GB, inherited as conservative operational defaults; these are subordinate to the total peak budget. Track cumulative network bytes separately from retained disk bytes.

### 17.2 Durable event bundles

Persist compact Parquet/JSON evidence: selected unit trajectories; applicable equation factors/solutions; IC and price series; context; event metadata; contribution calculations; quality metrics. Deduplicate shared intervals and equation versions across events and connectors.

Only delete a raw archive after validating the extracted output, checking required fields/coverage, recording its checksum and download details, and atomically checkpointing success. Preserve enough filtered evidence to regenerate all charts without another download. Record cleanup time, deleted path/bytes and retained derivatives.

Cleanup is allowlisted and restricted to resolved study-owned paths. Never delete unrelated source data, user files or unvalidated extracts. If the durable result set itself approaches the limit, reduce duplicated storage or predeclared deep-dive scope; do not erase evidence already cited by a report.

## 18. Output contracts and provenance

Use a namespace such as `market/connector/study_id/method_version`. Suggested deliverables:

| Artifact | Minimum content |
|---|---|
| `study_config.json` | Exact dates, adapter, thresholds, sampling, tolerances, limits and code version |
| `event_catalogue.parquet` | Event/incident IDs, landmarks, direction, severity, selection and evidence tier |
| `event_links.parquet` | Parent/child, shared system incident and cross-connector relationships |
| `thresholds.parquet` | References, sample counts, definitions and temporal availability |
| `event_timeseries.parquet` | IC, price, context and source/run identity for selected windows |
| `unit_dispatch.parquet` | Observed/target distinctions, units and effective mappings |
| `constraint_states.parquet` | Equation versions, factors, applicability, RHS, slack, marginal value and violation |
| `contributions.parquet` | Signed step/segment impacts, bridges, residuals and attribution convention |
| `event_outcomes.parquet` | Price/flow outcomes, censoring, regime flags and confidence |
| `controls.parquet` | Matching rules, balance, control IDs, weights and exclusions |
| `generator_summary.csv` | Unique incident counts, intensity, tightening/relief and associated price outcomes |
| `constraint_summary.csv` | Binding/setting distinctions, switches and incident statistics |
| `seasonal_diurnal_summary.csv` | Counts, exposure denominators and uncertainty |
| `source_manifest.jsonl` | Source URLs, hashes, schema, filters, dates, bytes and cleanup lineage |
| `quality_report.json` | Coverage, reconciliation, validation results and unresolved queue |
| `report.md` / `report.html` | Reproducible narrative, tables, charts and linked event pages |

Generate stable event IDs from connector, direction, detection time and detector version; parent incident IDs include the grouping version. Store methodology version and code commit in every report manifest. Configuration changes produce distinguishable runs.

Source manifests also record retrieval time, publication/vintage where available, parser version and whether a field would have been available at forecast time. Publish compact evidence and reports according to repository data policy; keep large raw archives and sensitive credentials out of Git.

## 19. Implementation stages and release gates

| Stage | Work | Gate |
|---|---|---|
| 1. Configure | Validate adapter, dates, definitions and storage inventory | Direction and time conventions verified |
| 2. Screen | Normalize full-period IC/price/context data; detect and link events | Coverage/duplicate audit and stable catalogue |
| 3. Select | Freeze deep-dive and control windows | Transparent selection with all MPC candidates accounted for |
| 4. Recover | Extract scoped dispatch/equation records | Source manifest, storage compliance and complete checkpoints |
| 5. Reconstruct | Reconcile fixed equations and switches | Per-event confidence and unresolved fields visible |
| 6. Pilot pages | At least five diverse cases where available: generator, RHS, switch, price-linked and low-price-response | Manual numerical and visual review passes |
| 7. Expand | Generate selected event atlas and statistical comparisons | Denominators, matching and uncertainty audited |
| 8. Forecast study | Build origin-available compact features and held-out tests | Leakage checks and frozen test evaluation |
| 9. Publish | Build reports and compact supporting files | Reproducible render, link checks and documented limitations |

Forecasting and causal replay are separately labeled extensions. An observational atlas can be complete without them, provided it does not claim their findings. Overall completion means the declared scope has passed its gates, not that a storage/time budget was exhausted.

## 20. Testing and acceptance criteria

### 20.1 Numerical and data tests

- Direction invariance: reversing the adapter orientation exchanges directional labels and preserves physical conclusions.
- Generator sign cases: positive/negative coefficients, ramp up/down, generating/consuming modes and upper/lower bounds.
- Equation identities: fixed-coefficient contributions reconcile exactly on controlled examples; bridge identities reconcile when all inputs are available.
- Candidate switching: a unit scenario can change the leading equation; incomplete candidate sets are flagged.
- Time boundaries: exact lag joins, missing intervals, month changes, leap day, interval-ending ownership and no unintended daylight-saving shift.
- Event semantics: ties, insufficient reference samples, no positive drops, forced negative capacity, duplicate detections and censored recovery.
- Price semantics: changing MPC, rounding tolerance, adjusted prices, intervention, administered regimes and negative prices.
- Asset/version history: connection-point changes, multiple set memberships and absent versions cannot duplicate or fabricate contributions.
- Non-overlap: stepwise impacts telescope; rolling-window exposures are never labeled event totals.
- Storage failures: oversized/unknown-size transfer, insufficient free disk, interrupted extraction, checksum failure and restart do not exceed limits or delete unvalidated evidence.

### 20.2 Statistical and report checks

- Event counts reconcile from interval labels through episodes, incidents and report filters.
- Every rate includes a valid exposure denominator; every sampled analysis identifies its selection scope.
- Matched controls use pre-event information, with balance/common-support diagnostics.
- Related events remain grouped for uncertainty and data splits; future data do not enter forecast features.
- Figures agree with source tables for inspected cases; direction, prices, times and units are consistent.
- Full equations and factors appear for reconstructed cases; unknown cases remain visible.
- Event pages render offline, synchronized panels work, labels are readable and links resolve.
- Rebuilding from durable bundles and the recorded configuration reproduces tables/figures within declared numerical tolerances.

Accept a release only when hard integrity checks pass. Events with incomplete attribution may remain in the observed catalogue but must not enter high-confidence mechanism totals without meeting the declared criteria. Publish observed and reconstructed coverage separately.

## 21. Repository integration and reuse checklist

Use the existing constraint studies as discovery and screening inputs, preserving their original numerical results and definitions. Link this methodology from future event reports. Implement generic modules for normalization, detection, selection, reconstruction, attribution, price outcomes, matching, features and rendering; connector-specific logic belongs in the adapter/configuration.

Before using the method on another interconnector, confirm:

1. Signed orientation and source-limit meanings.
2. Applicable technology, losses and operational controls.
3. Exact two-year window and complete/partial season coverage.
4. Existing local data, remaining gaps and bounded download plan.
5. Equation population, historical versions and all required dependencies.
6. Generator/load identity and effective-date mappings.
7. Local directional thresholds and normalized severity references.
8. Regional prices, effective MPC settings and special pricing regimes.
9. Cross-connector incident links and suitable control population.
10. Adapter tests, event-level reconciliation, report QA and the 10 GB guard.

Related repository documents: [constraint-derived network features](CONSTRAINT_NETWORK_FEATURES.md), [backtest protocol](BACKTEST_PROTOCOL.md), [VNI two-year study](VNI_TWO_YEAR_CONSTRAINT_STUDY.md) and [QNI two-year study](QNI_TWO_YEAR_CONSTRAINT_STUDY.md). This event workflow deliberately retains compact evidence and deletes validated temporary archives; it should not inherit a blanket raw-archive retention rule from an older workflow.

## 22. Required interpretation in every published report

Include a short statement identifying the observation period, event detector version, covered versus missing data, evidence tiers, price regimes, reconstruction error and whether any causal replay or forecasting validation was performed.

The reader must be able to distinguish: **what happened; what the equations mechanically imply; what remains unexplained; what prices did; and what has actually been validated for prediction or causation.**

## 23. Supporting market conditions: context after the core event analysis

### 23.1 Priority and sequence

This is a secondary analytical layer. Its purpose is to explain why an identified contraction had a large or small market consequence, and whether the surrounding system was already stressed. It must not displace the primary investigation of the interconnector, generator movements and constraint equations.

For every event, use this order:

1. Establish the observed limit contraction, flow/headroom response and event landmarks.
2. Identify the applicable equations, binding status, generator tightening/relief, RHS changes and equation switches; reconcile the result or explicitly record why it remains unresolved.
3. Establish the regional price response and its timing, including any MPC or other pricing regime.
4. Layer on demand, renewable output, thermal availability, outages and weather to explain the surrounding conditions and possible amplifiers.
5. Revisit the interpretation only where this additional evidence supports a specific mechanism; preserve the original observations and document the reason for any revised conclusion.

Core pages should be deliverable before optional context enrichment is complete. Missing temperatures or outage classifications do not block observed-event reporting; label those fields unavailable. An unresolved equation analysis also remains visible rather than being replaced by a confident weather or demand explanation.

This sequencing applies to report emphasis and investigation depth. It does not permit omitting confounder checks from a statistical or causal claim. Section 13's matching and interpretation requirements still apply. Likewise, an outage or weather-dependent RHS input needed for equation reconciliation belongs in the core evidence, even though broader outage and weather context is secondary.

### 23.2 Conditions to collect, where available

Collect conditions for both endpoint regions, with additional regions or sites only where the event's equations or supply dependencies justify them. Report the receiving and sending sides explicitly.

| Condition | Event measurements | Interpretation and safeguards |
|---|---|---|
| Demand | Regional MW before/during/after; 5/30/60-minute change; percentile against comparable season/hour; forecast error where archived vintages exist | Distinguish operational demand, underlying demand and residual demand. Name the definition and avoid adding rooftop PV twice |
| Wind and utility solar | Separate MW, regional share under a declared denominator, ramps, available resource/forecast and actual-versus-forecast differences where supported | Distinguish weak resource from curtailment; falling dispatch alone does not establish weather-driven loss of supply |
| Rooftop solar | Estimated regional output and change, source cadence and uncertainty | Keep estimates distinct from dispatchable-unit measurements; align demand accounting before calculating shares or residual demand |
| Coal generation | Output by unit/station/region, online-unit count, changes in output and availability | Separate generating output, declared availability and registered capacity; MW not dispatched is not necessarily unavailable |
| Coal offline/unavailable capacity | Verified offline status, unavailable MW, derating and reason where supported | Use dated unit capacities and status evidence; classify unknown status separately rather than calling zero-output units forced outages |
| Other dispatchable supply | Gas/hydro output and availability, battery generation/charging, relevant storage state where available | Prevent a coal-only explanation of system flexibility; storage state and unit constraints may limit usable response |
| Generator outages | Unit, planned/forced/unknown classification, start/end, MW affected, derating and source | Distinguish announced, expected and realized timings. Record partial outages and avoid double-counting lost capacity across notices |
| Transmission/link outages | Relevant circuits/assets, invocation links, availability/control changes and effective times | Identify a direct equation/set connection where possible. A regional outage count alone does not explain a particular IC restriction |
| Temperature | Representative endpoint-region observations and relevant generation/network-site observations where available; anomaly and daily maximum context | Preserve station location, observation time and quality. One city's temperature is not automatically representative of regional demand or an asset rating |
| Other weather | Wind, irradiance, humidity or other variables only when relevant and available | Use these to investigate a specified demand, renewable or equipment mechanism; do not expand into an unrestricted weather study |
| Supply margin and network support | Declared available supply, demand, reserve indicators and other-IC flows/headroom | Label any constructed margin as a proxy. Sum compatible quantities and do not equate nameplate capacity with deliverable reserve |

Use existing local regional and weather files first. Candidate supplementary sources include official market dispatch/availability records, published operational notices/outage records and official meteorological station observations. Confirm historical access, definitions and spatial/temporal coverage before promising each field. Use a documented gridded-weather fallback only where appropriate; label it as a different observation product and retain its uncertainty.

### 23.3 Coal capacity and outage accounting

Maintain an effective-dated unit inventory with fuel, station, region, registered capacity, dispatch type and retirement/commissioning dates. Define an online threshold and persistence rule in configuration. A telemetry-based online classification is an operational proxy unless independently confirmed; store the underlying evidence.

Report these separately:

- Registered capacity of in-scope coal units, in MW.
- Capacity associated with verified/proxy-online units, clearly labeled as an inventory measure rather than deliverable capacity.
- Capacity associated with verified-offline units, plus a separate unknown-status category.
- Actual or initial-MW output and dispatch targets, with their timing distinguished.
- Declared available MW, explicitly unavailable MW where supported, and known deratings.
- Unused declared availability, such as `max(available MW - comparable output MW, 0)`, labeled as a headroom proxy rather than ramp-feasible reserve.

Validate that online, offline and unknown inventory categories reconcile to the same dated registered-capacity population. Do not require dispatch availability to equal registered capacity; investigate differences and use source-consistent units. A unit may be online and derated, or offline but declared available to start. Do not add offline inventory capacity and unavailable MW as if they were disjoint losses.

Availability reductions inferred from dispatch records should be called availability changes until corroborated. Confirm planned versus forced outage classifications through supporting records when possible. If a trip or derating is a plausible initiating event, move its detailed timing and evidence into the core event narrative.

### 23.4 Event-window comparisons and layered interpretation

For each supported variable, retain its level at the last valid pre-event observation, its pre-event baseline, its event-window change, and its peak/trough. Use the existing two-hour before/after window first, adding a preceding-day context view only where useful. Align these summaries to both detection time and the estimated contraction start; detection may lag the initiating movement.

Proposed summary windows are -60 to -5 minutes for baseline, the estimated physical start to trough for the contraction phase, and 0 to +60 minutes after detection for the main price response. Record overlap explicitly. For slow-cadence variables, select observations consistent with these windows rather than inventing five-minute measurements.

Compare levels with season/hour peers using adequate sample counts. In retrospective descriptive plots, identify the reference period; in forecasts and control matching, use only pre-origin or pre-event information. Distinguish weather forecasts available beforehand from realized weather, and revised outage schedules from the information originally published.

Use a layered analytical comparison where sample size permits:

| Layer | Inputs and question |
|---|---|
| Core mechanism | Contraction severity, lost headroom, equation/constraint changes and mechanically attributed generator movement: what changed at the IC? |
| Supply-demand context | Demand, wind/solar, coal and other supply availability, relevant outages: was the region already vulnerable? |
| Weather context | Temperatures and specific resource/asset weather variables: do these explain the supply-demand state or a supported rating mechanism? |

Show whether the contextual layers change matched comparisons, out-of-sample explanatory performance or uncertainty. Do not interpret a model coefficient as proof of causality. Demand and availability may mediate weather effects; conditioning on them changes the question being estimated. State that question and avoid counting weather, demand and an RHS change as three independent causes when they describe the same pathway.

Suggested conclusions are specific: “the contraction reduced import headroom while receiving-region demand was high and verified coal availability was low,” or “the same-sized contraction had little price effect because local supply headroom remained ample.” These are templates; populate them only with measured event evidence. Avoid unsupported claims that high temperature caused a trip or that low renewable dispatch proves low resource availability.

### 23.5 Additions to the event report and graphs

Place a **Supporting market conditions** section after the core event narrative, equation evidence, generator attribution and observed price response. Keep its initial view compact, with optional detail expansion. The synchronized system-context panel in Section 16 is the entry point rather than a second dominant report.

Include:

1. A before/during/after conditions table with demand, wind, solar, coal output/availability, verified offline coal capacity, relevant outages and temperature. Every row shows units, source, cadence, completeness and reference percentile where valid.
2. A regional demand-and-supply timeline, separating demand, renewable output and dispatchable output. Use an explicit accounting convention; do not imply a stack is balanced if imports, storage, rooftop supply or losses are omitted.
3. A coal availability view showing output versus declared availability, with online/offline/unknown inventory in a separate strip. Annotate unit trips/deratings only to the confidence supported by records.
4. A relevant-outage timeline linked to named units/assets, constraint sets and notices; shade uncertain start/end times.
5. A temperature/context panel for selected representative sites with observed points and anomalies. Do not disguise hourly observations as five-minute measurements or add false precision through interpolation.
6. An optional comparative plot of contraction severity and price response colored by demand percentile or supply-availability regime. Show sample sizes and distinguish a selected case gallery from a population relationship.

End each event's context section with three short statements: conditions supported by observations; how they may amplify or moderate the established event; and missing evidence that limits that interpretation. Keep causal confidence separate from completeness of the context table.

### 23.6 Data, storage and acceptance additions

Extend the durable evidence bundle with `market_context.parquet`, `unit_availability.parquet`, `outage_evidence.parquet` and `weather_context.parquet` where populated. Record units, location/region, measurement versus forecast/estimate, publication vintage, effective times and source lineage. Add `context_status` and per-variable coverage to each event's quality record.

Apply Section 17's existing 10 GB peak ceiling and scoped-download guard. Recover context for selected event/control windows and limited, justified seasonal reference samples; reuse shared regional series. Do not download all historical unit outages, nationwide weather grids or an entire weather/MMS archive for this supporting layer. Batch extraction across nearby events, retain validated compact evidence and delete temporary source files with a cleanup log.

Additional acceptance checks:

- Demand/renewables definitions and shares use compatible denominators without rooftop double-counting.
- Coal status categories, unit mappings and dated capacities reconcile; unknown status is retained.
- Planned, forced, inferred and unknown outages remain distinguishable; overlapping records do not duplicate lost MW.
- Weather stations/grids, measurement cadence, spatial relevance and missingness are visible.
- Pre-event controls and forecast features exclude post-event information and hindsight revisions.
- Primary event findings remain accessible and correctly qualified even when supporting conditions are unavailable.
- Every contextual mechanism claimed in the narrative has evidence beyond simple temporal coincidence, or is explicitly labeled a hypothesis.
