# Constraint-derived network features for interconnector forecasting

Prepared 11 September 2026. **Design proposal: not implemented, backtested or demonstrated to improve forecasts.** All numerical equations involving Tumut 3 below are synthetic illustrations, not verified AEMO equations or coefficients.

This document develops the idea of using generators' participation in constraint equations to represent their influence on interconnector (IC) flows and import/export limits with a small feature set. It covers mathematical interpretation, discovery, data requirements, feature construction, forecast-time operation, model integration and validation.

Related documents: [current features](RESULTS_DATA_AND_FEATURES.md), [improvement roadmap](IMPROVEMENT_ROADMAP.md), [backtest protocol](BACKTEST_PROTOCOL.md), [methods](METHODS_AND_RESEARCH.md).

## 1. Objective and recommended approach

Regional generation totals do not distinguish generation at electrically different locations. Two generators in the same region can have substantially different coefficients in equations that restrict an interconnector. Generation changes can tighten a directional bound, relax it, or move a bound through zero and require flow in the opposite direction.

The proposed representation is:

> Convert generation movements into interconnector-equivalent bound movements using applicable constraint coefficients; combine these with the proximity and identity of competing constraints; expose a compact description of tightening, relief and switching risk to the forecasting model.

Start with VNI and the Tumut 3 hypothesis. Use binding and limit-setting history to discover relevant equations and generator groups, but calculate features over relevant invoked constraints, including near-binding candidates. Keep upper and lower directions separate. Preserve detailed equation-level provenance outside the model matrix.

The recommended first model block contains 16 values per IC, plus a small set of data-quality fields. A later extension adds two generator-driven envelope movements. High-dimensional generator IDs, general graph neural networks and a full network reconstruction are not prerequisites.

Success means improved held-out flow and directional-limit forecasts, particularly around contractions and reversals, at acceptable data coverage and runtime. No numerical gain is assumed.

## 2. Scope: what this represents

These are **constraint-derived network-state features**. Constraint applicability, coefficients, RHS values and dispatch together express operational restrictions associated with network configurations. They do not uniquely identify physical topology or replace a power-flow model.

Keep three quantities distinct:

| Quantity | Meaning | Role here |
|---|---|---|
| Actual IC flow | Dispatch outcome, affected by supply, demand, offers, losses and constraints | Prediction target |
| Reported import/export limit | Published dispatch-dependent directional limit | Prediction target; retain existing repository conventions |
| Reconstructed conditional bound | Bound obtained from an equation with other quantities fixed | Explanatory feature and diagnostic |

A conditional bound is not maximum secure transfer with all generators free to redispatch. A change in a conditional bound is not a causal prediction of the actual flow response.

AEMO describes the LHS as dispatchable quantities and the RHS as the remaining inputs presented to dispatch. The RHS need not equal a physical transmission rating. [AEMO constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq)

## 3. Direction, equation normalisation and sensitivity

### 3.1 One signed-flow convention

Use the source-to-sink convention in `nemic/common.py`. Positive VNI flow is VIC to NSW. Internally, represent its conditional interval as `L <= F <= U`, where L is the lower signed bound and U is the upper signed bound.

When expressing capacities in each direction, the upper-direction capacity is U and the reverse-direction capacity is -L. Both can be negative. Verify the mapping to published fields against the existing target construction before comparing values; never apply an absolute value to make negative limits look positive.

| Conditional interval property | Interpretation |
|---|---|
| U decreases | Upper-direction transfer tightens |
| L increases | Reverse-direction transfer tightens |
| U < 0 | The conditional upper bound requires negative flow |
| L > 0 | The conditional lower bound requires positive flow |
| L > U | Inconsistent conditional interval; investigate data, violations and scenario assumptions |

### 3.2 Canonical equation

Write every inequality in less-than-or-equal form:

```text
a[c,i] * F[i] + sum_g b[c,g] * P[g] + Z[c] <= R[c]
```

Here c is a constraint, i an IC, g a generator, P generator energy dispatch, R the dispatch RHS, and Z every other LHS contribution, including other ICs, loads and relevant ancillary-service terms. Generator energy must not be confused with its FCAS service variables.

Convert greater-than-or-equal equations by multiplying all terms and the RHS by -1. Treat an equality as two inequalities for bound calculations, preserving their shared identity and avoiding double-counting in discovery statistics. Do not flip signs based on coefficients without also transforming the inequality.

For nonzero a:

```text
B[c,i] = (R[c] - sum_g b[c,g] * P[g] - Z[c]) / a[c,i]
s[c,g,i] = -b[c,g] / a[c,i]
```

If a is positive, B is an upper bound; if negative, B is a lower bound. The sensitivity s is MW of signed-bound movement per MW of generator movement, with R and all other terms held fixed.

Ratios are invariant to positive rescaling of an entire equation. Raw coefficient size alone is therefore unsuitable for cross-equation ranking. AEMO coefficients are formulated relative to a reference location, and neighbouring-region generator terms may represent contributions above the interconnector contribution. They should not be interpreted as universal physical flow factors. [AEMO Constraint Formulation Guidelines, section 2.5](https://www.aemo.com.au/-/media/files/electricity/nem/security_and_reliability/congestion-information/2025/constraint-formulation-guidelines.pdf?rev=7c054f0facdb4c6c99b7b0cd538a01b6&sc_lang=en)

If a is zero, the equation cannot be divided into a direct bound on this IC. It may still affect flow indirectly by restricting generation. Retain it for a later indirect-influence block. For very small a, use a documented scale-aware eligibility rule and flag omitted equations; do not silently turn extreme ratios into trustworthy MW sensitivities. Fit any statistical clipping threshold on training data only and retain the unclipped diagnostic values.

### 3.3 Synthetic Tumut 3 example

Assume a hypothetical constraint:

```text
F_north + 0.6 * P_Tumut3 <= 900
```

At P = 500 MW, the northward upper bound is 600 MW. A 100 MW generation increase makes it 540 MW. The northward allowance contracts by 60 MW; actual flow need not fall by 60 MW if it was well below the bound or other dispatch changes offset the effect.

A separate synthetic equation illustrates forced flow:

```text
F_north + 0.6 * P_Tumut3 <= 300
```

Moving P from 400 to 600 MW changes U from +60 to -60 MW. Under these fixed conditions, positive flow is no longer feasible and at least 60 MW southward is required. Restricting exports and forcing reverse flow are different events.

## 4. Find the relevant constraints and generators

### 4.1 Historical discovery

On training history only:

1. Extract reported IC limit setters, binding constraints and their equation versions.
2. Join generator energy coefficients and target-IC coefficients using the correct version keys.
3. Calculate signed sensitivities, participation frequency and observed dispatch variability.
4. Group equations by operational meaning and coefficient structure.
5. Rank generators by directional relevance, sensitivity and realistic movement size.
6. Inspect the leading cases manually, including the Tumut 3 hypothesis.

A candidate ranking is a recency-weighted average of `relevance * abs(sensitivity) * typical_absolute_generator_movement`, calculated within an IC direction and family. This is a discovery heuristic, not an estimated causal effect. Record positive and negative sensitivities separately, sign changes, sample count and concentration in a single outage episode.

Avoid ranking by binding frequency alone: a rare equation can be decisive. Avoid ranking by marginal value alone: it measures economic tightness and is sensitive to price conditions and equation scaling. If marginal-value features are later used, normalise consistently and keep them separate from physical MW-pressure features.

### 4.2 Invocation, binding and setter identity

An invoked equation is applicable to the dispatch interval. A binding equation is economically active in the solution; AEMO indicates binding through nonzero marginal values. Near-zero slack and economic binding are not interchangeable in degenerate solutions. A reported limit setter is a separate published attribution. [AEMO constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq)

For feature construction, use the relevant invoked set known at origin, or an explicitly forecast applicable set. Do not use all equations ever present in the library simultaneously. Preserve rarely binding outage candidates when they are applicable. Deduplicate a constraint invoked through multiple sets.

### 4.3 Constraint families

Candidate families include thermal, voltage stability, transient stability, system strength, outage-related transfer restrictions, ramping and FCAS-related restrictions. Build mappings from metadata plus coefficient structure; names alone are not reliable semantic parsers. An outage may modify applicability within several families.

Version changes with materially different coefficients must remain distinguishable. Unknown families receive a defined unknown category rather than a future-informed mapping.

## 5. Conditional envelope and proximity

For relevant valid upper and lower equations:

```text
U = min(B[c,i] for upper equations)
L = max(B[c,i] for lower equations)
upper_room = U - F_reference
lower_room = F_reference - L
upper_switch_gap = second_smallest_upper_B - U
lower_switch_gap = L - second_largest_lower_B
```

Use the same dispatch reference and timestamp across all terms. A missing direction is missing, not a zero-MW limit. With only one candidate, the switching gap is missing and candidate count explains why. Tied constraints give a zero gap.

Slack in equation units is `R - LHS`; IC-equivalent slack is `(R - LHS) / abs(a)`. It equals directional room for that equation when the reference flow is the same. It measures proximity to the current flow, whereas distance from B to the leading bound measures proximity to becoming the setter. Keep the distinction in diagnostics.

For pressure pooling, one optional weight is:

```text
d[c] = B[c] - U       for upper equations
d[c] = L - B[c]       for lower equations
w[c] proportional to exp(-d[c] / tau), normalised within direction
```

Tau is a positive MW scale selected on training/validation data. Prefer top-k relevant equations or family deduplication before weighting so duplicated constraints do not dominate. Begin with the current leading equation if a simple baseline is needed. Do not take an unrestricted average of all bounds: the envelope is controlled by extrema.

## 6. Compact feature dictionary

Define generator movement relative to the last eligible observed dispatch. For origin-state features, use a declared backward window, initially 30 minutes. For future features, use an origin-available forecast path relative to the same anchor. Encode the window or lead in the schema.

For each generator contribution `delta = s[c,g,i] * delta_P[g]`, define `q = -1` for an upper equation and `q = +1` for a lower equation:

```text
tightening[c] = sum_g max(q * delta, 0)
relief[c] = sum_g max(-q * delta, 0)
```

Pool these within each direction using the same eligibility and weighting policy. Both remain nonnegative. Their difference gives net tightening, but retaining both prevents cancellation from hiding large opposing movements. They are descriptive pressures, not additive independent capacity estimates across constraints.

| Feature | Count | Units and definition |
|---|---:|---|
| `conditional_upper`, `conditional_lower` | 2 | MW; signed U and L |
| `upper_room`, `lower_room` | 2 | MW; room relative to eligible observed F |
| `upper_gen_tightening`, `upper_gen_relief` | 2 | MW; pooled upper-bound movement components |
| `lower_gen_tightening`, `lower_gen_relief` | 2 | MW; pooled lower-bound movement components |
| `upper_switch_gap`, `lower_switch_gap` | 2 | MW; leading versus next candidate |
| `upper_family`, `lower_family` | 2 | Categorical; leading family, training-fitted encoding |
| `upper_available_relief`, `lower_available_relief` | 2 | MW; approximate short-horizon generator flexibility |
| `upper_pressure_change`, `lower_pressure_change` | 2 | MW; change in net pressure over a declared backward window |
| **Core total** | **16** | Before separate quality fields and optional extensions |

Some features are algebraically related and some overlap with lagged published limits. The 16-column design is a candidate budget, not a requirement to retain redundant variables. Use ablations to prune it.

Required quality information includes snapshot age, directional candidate counts and partial-reconstruction status. Store per-term missingness and source lineage outside the model matrix; expose a few aggregate indicators so missing data is not interpreted as an unconstrained network.

### 6.1 Approximate available relief

For each generator, estimate eligible upward/downward movement over horizon h from origin-known availability, operating limits, ramp rates and mode. Select the movement direction that relaxes the equation and multiply the available movement by abs(s). Aggregate at the equation level, then pool by direction.

This is an optimistic local flexibility proxy. Independently available generator movements may not be jointly feasible because of energy balance, other constraints, FCAS, water/energy budgets or operating modes. It must not be added directly to a reported secure limit. Missing operating data yields missing flexibility, not assumed full capacity. Pumping/generation and bidirectional-unit conventions require version-aware mapping.

## 7. Generator-driven envelope recomputation

For every candidate equation, apply an origin-available generation scenario:

```text
B_hat[c,h] = B[c,anchor] + sum_g s[c,g,i] * delta_P_hat[g,h]
U_hat[h] = min(B_hat[c,h] for upper candidates)
L_hat[h] = max(B_hat[c,h] for lower candidates)
upper_envelope_move[h] = U_hat[h] - U[anchor]
lower_envelope_move[h] = L_hat[h] - L[anchor]
```

This adds two features while explicitly allowing a different constraint to take over.

Synthetic example: upper bound A is 500 MW and B is 530 MW. A generation scenario relaxes A by 100 MW but tightens B by 10 MW. The new bounds are 600 and 520 MW, so the envelope expands only 20 MW. A feature based solely on the original setter would imply 100 MW of relief.

### 7.1 Fixed-RHS assumption and a fuller extension

The initial scenario holds RHS, other dispatch terms, coefficients and applicability fixed. It is most useful as a short-horizon perturbation feature, not a seven-day physical forecast.

For unchanged coefficients, the fuller decomposition is:

```text
delta_B = (delta_R - sum_g b[g] * delta_P[g] - delta_Z) / a
```

Do not add a generator effect twice when a forecast RHS already embeds an updated initial operating point. AEMO feedback formulations include measured flow and initial dispatch terms; persistent changes cannot be extrapolated by freezing these inputs indefinitely. [AEMO Constraint Implementation Guidelines, thermal/feedback formulation](https://aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2023/constraints-implementation-guidelines/final-constraint-implementation-guidelines-v3.pdf)

If coefficients or invocation change, rebuild the equation snapshot and evaluate it consistently rather than applying the old derivative across the change. If L exceeds U, emit an inconsistency flag and retain diagnostics; never silently swap the bounds.

## 8. Alternative compression and indirect influence

### 8.1 Electrically similar generator groups

Represent a generator by its signed sensitivity vector over IC directions and constraint families. Cluster those profiles on training data, weighting economically relevant or near-envelope families without discarding rare applicable restrictions. Standardise profiles carefully so frequency and arbitrary equation scaling do not dominate.

Create approximately 3–5 signed, coefficient-weighted generation indices per IC, optionally with ramps. Fix the weights and category handling before evaluation. Allow regime-specific profiles where the same generator changes role across configurations.

Keep a separate Tumut 3 output/ramp feature if its profile is distinctive and the direct-feature ablation supports it. Compression should preserve useful exceptions. Site aggregation is valid only after checking that units and modes have compatible coefficients and timing.

### 8.2 Longer-term options

| Method | Benefit | Main limitation | Priority |
|---|---|---|---|
| Selected generator outputs/ramps | Simple baseline | More variables; weak regime interpretation | First comparator |
| Directional equation pressure | Compact and interpretable | Needs reliable applicable equations | Recommended first block |
| Envelope recomputation | Captures setter switching | Scenario/RHS assumptions | Next extension |
| Signed generator clusters | Captures location beyond regional totals | Weight stability and interpretation | Complementary experiment |
| Low-rank coefficient factors | Compresses many equations | Can hide signs and rare bottlenecks | Later benchmark |
| Generator-constraint-IC graph model | Can learn indirect relationships | More data, complexity and validation burden | Only after simpler gains |
| Joint dispatch/network optimisation | Models feasible coordinated response | Requires substantial additional inputs | Separate research programme |

Constraints with no target-IC coefficient can restrict generators and thereby alter IC flow indirectly. A later extension can summarise those generators' constraint pressure or use a two-step graph. Do not invent a direct MW bound sensitivity by dividing by zero or treating indirect effects as proven causal responses.

## 9. Data contract and historical availability

The following are **candidate MMS data families**, not a claim that their complete public issue-time history has been acquired. Confirm current schema documentation, product versions, keys, access, coverage and publication semantics before implementation.

| Required information | Candidate source families | Essential fields/joins |
|---|---|---|
| Equation definition | `GENCONDATA` and related generic-constraint metadata | Constraint ID, effective/version keys, inequality, description |
| LHS factors | `SPDCONNECTIONPOINTCONSTRAINT`, `SPDINTERCONNECTORCONSTRAINT`, `SPDREGIONCONSTRAINT` | Exact equation version, entity/service, factor; map connection points to DUIDs as applicable |
| Invocation and sets | Generic-constraint set membership and invocation records, including `GENCONSET`/`GENCONSETINVOKE` candidates | Membership version, applicable interval, schedule revision, publication |
| RHS and solution | `DISPATCHCONSTRAINT`, corresponding predispatch/P5MIN products where available | Run identity, interval, RHS, marginal value, violation |
| Generator state | `DISPATCHLOAD`, unit registration/mappings and appropriate forecast/availability products | DUID, service, dispatch, initial output, mode, availability, ramp fields |
| IC reference and target | `DISPATCHINTERCONNECTORRES` and forecast equivalents | Flow, directional limits/setters, intervention/run identity |
| RHS dependencies | RHS descriptions, available network inputs and forecast RHS products | Input semantics, units, reference timestamp and availability |
| Future regime | Archived outage and constraint schedules | Original issue time, planned start/end, revision history |

Never join solely on constraint ID or use the latest equation version across all history. Keep record effective time, dispatch interval, forecast valid time, forecast issue time, observed public availability time and retrieval time distinct. `LASTCHANGED` may support revision checks but is not automatically proof of public release time. A monthly historical archive alone may establish realised history without establishing what a forecaster knew at the time.

All interval handling must use the repository's NEM-time convention consistently. Do not interpret the workstation's local timezone as the market interval timezone. Distinguish interval-start/interval-end and dispatch target/initial values.

## 10. End-to-end pipeline

```text
Versioned source records + publication evidence
    -> normalised equations, entity mappings and invocation snapshots
    -> consistent dispatch/RHS reconstruction and quality checks
    -> IC-equivalent bounds, generator sensitivities and provenance
    -> training-only relevance/family/group discovery
    -> origin-eligible observations and forecast scenarios
    -> compact features per origin, IC and lead
    -> separate flow/limit models and calibrated event forecasts
    -> paired backtests, event diagnostics and operational monitoring
```

Suggested internal tables:

- `equation_versions`: constraint/version identity, inequality, metadata and publication evidence.
- `equation_terms`: equation version, entity type/ID/service and coefficient.
- `equation_snapshots`: interval/run, invocation, RHS and complete reconstruction status.
- `ic_constraint_state`: interval, IC, direction, bound, slack, family and quality.
- `feature_vintages`: origin, lead, IC, anchor time, compact values and transform version.
- `feature_lineage`: source versions and scenario/family/weight hashes used by each batch.

These are proposed local datasets under ignored data directories. They are not new committed raw-data files.

### 10.1 Construction pseudocode

```text
fit discovery mappings and feature hyperparameters on training only
for forecast_origin:
    cutoff = apply source-specific availability rules and observation delay
    records = choose versions demonstrably available by cutoff
    snapshot = align equations, invocation, RHS and dispatch run
    reconstruct all material LHS terms; flag incomplete snapshots
    for interconnector:
        candidates = valid invoked direct equations for this connector
        bounds = normalise_and_isolate(candidates)
        state = calculate_envelope_rooms_gaps_and_families(bounds)
        pressure = project eligible historical generator movements
        for horizon:
            scenario = generation forecast available at forecast_origin
            extension = recompute envelope if scenario is available
            emit state, pressure, optional extension, quality and lineage
```

### 10.2 Reconstruct before compressing

Use a common dispatch run and all material LHS terms to reproduce RHS-minus-LHS slack. Separate intervention from non-intervention solutions. Check active-constraint residuals within tolerances consistent with published precision and violation fields. Negative room is a diagnostic, not automatically bad data: genuine violations and mismatched fixed scenarios must be distinguished.

Compare reconstructed leading bounds with reported limits and setters on matched intervals. Differences must be investigated rather than automatically labelled an algebra error or assumed equivalence: target definitions, run conventions, eligibility and omitted terms can differ. Retain reconstruction coverage and residual distributions by family and IC.

### 10.3 Five-minute to half-hour processing

Reconstruct at native five-minute resolution before half-hour aggregation. The minimum over constraints of an average is generally not the average of interval minima. Compute interval envelopes first, then aggregate to align with the repository's average and tight-limit targets. Only use constituent observations released by origin; a partially available half-hour must not borrow later intervals.

## 11. Forecasting across horizons

| Horizon | Initial practical representation | Main uncertainty |
|---|---|---|
| 30 minutes to 6 hours | Delayed observed envelope, ramps, persistence/available generator forecasts | Dispatch response and emerging setter changes |
| 6 to 24 hours | Issued generation forecasts and known schedule scenarios | Generator commitment, RHS and applicability |
| Days 2–3 | Forecast ensembles and planned regime scenarios | Forecast availability and outage timing |
| Days 4–7 | Probability-weighted regime/scenario summaries | Network state and generator trajectories |

Compute each scenario's envelope before pooling scenarios. `E[min(B)]` is generally not `min(E[B])`. Useful later summaries include envelope quantiles, restriction probability, forced-direction probability and probability of a setter change. They must be labelled scenario-derived rather than measured physical probabilities until calibrated.

For absent generator forecasts, the first deployable baseline is an explicit persistence assumption with forecast age and lead. A future-generator oracle can establish an upper-bound diagnostic on information value, but cannot be presented as an operational result. Historical realised future binding/setter information is also oracle-only.

## 12. Integration into the current repository

Current inspection found that `nemic/model.py` builds lagged flow/limit features, observed setter/network flags, regional available-generation totals and other IC flows. It applies a 30-minute observation delay and publication checks. The present main experiment also supplies realised future demand, renewables and weather, as documented in [README](../README.md).

The proposal adds unit/location-sensitive structure beyond regional totals. It does not claim the current ingestion already contains the complete equation and DUID history needed for reconstruction.

Suggested implementation boundaries, all future work:

| Location | Proposed responsibility |
|---|---|
| `nemic/ingest.py` or a dedicated ingestion module | Version-aware constraint, factor, invocation and unit-state extraction |
| New `nemic/constraint_features.py` | Canonicalisation, reconstruction, bounds, projection and compact features |
| `nemic/prepare.py` | Five-minute alignment, half-hour aggregation and availability controls |
| `nemic/model.py` | Explicit feature blocks, schema/encoder persistence and ablations |
| `nemic/scenario.py` | Origin-stamped generator/regime scenarios and provenance |
| `nemic/backtest.py` | Matched-sample evaluation and event slices |
| `tests/` | Numerical, direction, timing, missingness and version fixtures |

Cache keys must include source versions, equation mappings, discovery-fit period, feature settings and code hashes. The existing extraction cache can return an earlier extraction based on its archive tag; extending requested tables requires explicit invalidation/versioning so missing new tables are not mistaken for completed ingestion.

Predict directional limits and flow separately at first. Feed the compact network block alongside current regional drivers and lags. A subsequent flow model can use out-of-fold limit predictions; in-sample fitted limit predictions would create stacking leakage. Avoid initially clipping flow to independently predicted conditional bounds. Bound coherence and joint scenarios require separate validation.

## 13. Experiment plan and acceptance

### 13.1 VNI pilot

First establish whether Tumut 3 appears in the relevant versioned equations and in which operating modes, signs and regimes. Produce a discovery table and a few fully reconstructed historical intervals before fitting a model. Include both ordinary operation and unusual restrictions where data permits.

| Experiment | Added information | Question |
|---|---|---|
| E0 | Current frozen model and persistence | Reference performance |
| E1 | A few training-selected generator outputs/ramps | Does unit detail alone help? |
| E2 | Directional coefficient-weighted pressure | Does equation structure add value? |
| E3 | E2 plus bounds, switching gaps, families and flexibility | Does network proximity add value? |
| E4 | E3 plus generator-driven envelope recomputation | Does modelling setter switching help? |
| E5 | Signed generator-group indices | Can grouping improve or simplify the block? |
| Oracle diagnostic | Explicit realised future generator paths or regimes | What is lost to input uncertainty? |

Train and evaluate each on identical eligible pairs; report coverage loss from added sources. Compare the current model on the reduced sample as well as its full sample. Keep learner capacity and tuning budget comparable so feature effects are not confused with a larger model search.

### 13.2 Metrics and event slices

Track MAE for flow, average limits and tight limits by direction and lead band; quantile loss and interval coverage; restriction recall at fixed alert burden; and false alerts. Add event-level scoring for abrupt limit contractions, reversals, forced-direction conditions and setter transitions. Define event thresholds using training data or predeclared business rules.

Evaluate rare outage families, unseen setters, near-zero flows, large hydro ramps and weak-data periods separately. Do not report one physical event repeated over hundreds of forecast origins as hundreds of independent successes. Use paired dependence-aware uncertainty estimates, such as the repository's seven-day block approach, and event-level summaries.

The March–August 2026 test has already been examined. Use earlier chronological development folds and reserve a new untouched period with matured seven-day outcomes, as required by the existing [roadmap governance](IMPROVEMENT_ROADMAP.md). Freeze primary metrics, alert burden, guardrails and feature choices before that evaluation. Business tolerances remain to be selected; this document does not invent acceptance thresholds.

### 13.3 Required implementation checks

- Multiplying an equation by a positive constant preserves bounds and sensitivities.
- Converting a greater-than inequality preserves its feasible set.
- Upper/lower tightening signs and crossing-zero examples match the algebra.
- The competing-constraint example yields only 20 MW envelope expansion.
- Missing RHS or material terms cannot silently produce a complete bound.
- Tiny/zero IC coefficients follow the declared handling policy.
- Equation/set versions unavailable at origin never enter a feature.
- Future generator dispatch, setters, RHS and marginal values cannot enter operational features.
- Duplicate invocation, equality expansion, intervention runs and DUID modes remain distinct where needed.
- Native-interval reconstruction precedes half-hour aggregation.
- Frozen group encoders handle new families and units without future fitting.

These are proposed tests for the future implementation, not a claim that a numerical feature pipeline has been tested in this documentation change.

## 14. Risks, fallbacks and monitoring

| Failure mode | Consequence | Handling |
|---|---|---|
| Missing or stale invocation | Wrong candidate envelope | Age/coverage flags; fall back to established features |
| Incomplete RHS/LHS terms | Misleading bound | Mark partial; exclude from trusted reconstruction |
| Coefficient or mapping revision | Wrong sign or scale | Version-aware joins and change diagnostics |
| Multiple opposing generator effects | Net feature hides stress | Preserve tightening and relief separately |
| New constraint takes over | Original-setter projection overstates movement | Candidate envelope and switching gaps |
| Fixed-RHS extrapolation | Long-horizon physical overinterpretation | Label perturbation; add coherent RHS/regime scenarios |
| Endogenous dispatch | Coefficient mistaken for actual causal response | Separate bound mechanics from statistical flow model |
| Unavailable generator flexibility | Invented relief capacity | Missing values and constrained assumptions |
| New topology or commissioning | Learned groups become stale | Unknown categories, drift checks and periodic training-only refits |

Monitor source age, complete-reconstruction rate, residual distributions, coefficient-ratio tails, candidate counts, unknown-family rate, inconsistent-envelope rate and feature drift. Define operational fallback thresholds during development. Falling back to the existing model is preferable to presenting a partial reconstruction as complete.

## 15. Delivery sequence and decision record

1. **Source audit:** document schemas, archive coverage, keys and public-availability evidence.
2. **VNI reconstruction:** validate directions and selected complete equations, then audit Tumut 3's actual participation.
3. **Feature prototype:** build the compact origin-state block with reproducible lineage.
4. **Paired development backtest:** compare E0–E3 and prune redundant columns.
5. **Forecast extension:** add origin-available generator paths and E4, keeping oracle results separate.
6. **Untouched evaluation:** apply frozen acceptance rules and publish positive and negative findings.
7. **Broader rollout:** extend to other ICs with connector-specific direction and formulation checks.

Recommended decisions now: VNI first; direct equations first; separate upper/lower pressure; include near-envelope candidates; retain all material equation terms; maintain a strict feature budget; and defer complex graph/optimisation models.

Open implementation choices are source coverage, generator forecast products, near-envelope weighting scale, family definitions, flexibility assumptions and acceptance tolerances. Resolve them through the source audit and chronological development experiments rather than treating illustrative defaults as validated settings.

## 16. References and interpretation boundary

The equations, pooling rules, feature budget, pipeline and experiments above are proposed engineering design. AEMO sources support the underlying constraint interpretation; they do not endorse this feature architecture or establish its forecast performance.

- [AEMO constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq): LHS/RHS meaning, binding, violations and feedback examples.
- [AEMO Constraint Formulation Guidelines](https://www.aemo.com.au/-/media/files/electricity/nem/security_and_reliability/congestion-information/2025/constraint-formulation-guidelines.pdf?rev=7c054f0facdb4c6c99b7b0cd538a01b6&sc_lang=en): formulation and coefficient reference conventions.
- [AEMO Constraint Implementation Guidelines](https://aemo.com.au/-/media/files/stakeholder_consultation/consultations/nem-consultations/2023/constraints-implementation-guidelines/final-constraint-implementation-guidelines-v3.pdf): implementation and thermal feedback construction.
- [AEMO congestion information resource](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource): entry point for constraint documentation and library information.
- [Repository feature inventory](RESULTS_DATA_AND_FEATURES.md), [backtest protocol](BACKTEST_PROTOCOL.md) and [improvement roadmap](IMPROVEMENT_ROADMAP.md): current implementation and evaluation constraints.
