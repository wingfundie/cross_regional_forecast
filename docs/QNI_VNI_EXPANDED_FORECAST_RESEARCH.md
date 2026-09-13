# From constraint studies to better QNI and VNI forecasts

Expanded research and implementation methodology · 13 September 2026 · Study population: 1 September 2024–31 August 2026 · NEM timestamps use fixed UTC+10

## 1. Decision and scope

The recommended approach is a compact, quality-aware network-state layer feeding several forecast tasks: signed flow, directional capacity, contraction probability, setter-switch probability and forced-direction probability. Begin with persistence, AEMO forecast correction, regularised linear regression and calibrated logistic regression. Retain shallow boosting as a serious challenger, particularly for VNI at short horizons. Select models separately by task and horizon; the evidence does not support one universal winner.

This conclusion combines the repository's two-year QNI/VNI studies and event atlases, the existing forecasting implementation, an earlier simple-model experiment, a new expanded numerical experiment, and a wider review of operational interconnector forecasting, optimisation, electricity forecasting, ramp prediction, uncertainty and evaluation. The priority is balanced flow accuracy and useful contraction/direction warnings. Market and weather context should follow the network-mechanism layer, while forecast-time availability governs every layer.

The expanded experiment produced **144 regression score rows, 20 event-probability score rows, 48 monthly feature audits and two selected-case attribution audits**. It read 100 existing local inputs with approximately 121.88 MB of file sizes in total; this is a file inventory, not peak memory. No new market-data files were downloaded. Full settings, input hashes and results accompany this report.[^28]

There are promising findings and substantive qualifications:

| Finding | Consequence for implementation |
|---|---|
| VNI 30-minute flow MAE falls from 155.45 MW with persistence to 142.73 MW with the full shallow L1 boosting model | Test shallow boosting alongside simple models for this task |
| Only 1.21 MW of that improvement is the increment over the same boosting model without the topology block | Do not attribute the entire 12.72 MW gain to generator features |
| At 24 hours, VNI base ridge achieves 332.05 MW versus 341.99 MW for full boosting | More features and more flexibility can hurt; horizon-specific selection matters |
| QNI import-contraction probability has Brier score 0.1949 with full logistic regression versus 0.2053 with full boosting | Preserve a simple classification pathway |
| QNI's 92 selected cases have median complete-generator-term share 0 and only 31 cases with all steps exactly version matched | Separate statistical predictors from trustworthy generator explanations |
| AEMO changed its minimum LHS factor threshold within the study period | Treat equation representation as a changing measurement system |

These are development findings, not demonstrated live forecast improvements. The March–August 2026 evaluation period has already been examined in earlier work. Some retained topology fields use solved dispatch or availability information whose historical public release has not been established. The new experiment includes no realised future fundamentals, but a 30-minute lag alone does not prove public availability. No production model was replaced.

## 2. Research design and evidence hierarchy

This is an expanded integrative review, not a claim that every publication or proprietary industry model has been examined. Search scope was deliberately widened beyond interconnector flow to congestion and active constraints, generator movement, electricity price extremes, wind ramps, correlated spatial flows, statistical learning, additive models, boosting, calibration and temporal validation. The accompanying [research log](QNI_VNI_EXPANDED_RESEARCH_LOG.md) records exact query batches, access limitations and screening decisions.

Evidence is used in four distinct ways. Repository results establish what happened in this dataset. Primary AEMO documents establish market definitions and data contracts. Direct interconnector research offers modelling precedents. Adjacent academic work informs methods without supplying a transferable QNI/VNI uplift percentage. Papers on simulated optimal power flow and planning surrogates are not treated as operational forecast validations.

The literature supports testing an ordered model portfolio rather than choosing complexity by fashion:

| Evidence | Retained lesson | Transfer limitation |
|---|---|---|
| Paretkar's intertie ARIMA thesis | Direct intertie forecasting has a statistical time-series precedent | Historical daily Pacific Northwest setting differs from five-minute NEM events[^14] |
| Lago et al., electricity-price review and benchmark | A regularised autoregressive benchmark is an essential comparator | Price forecasts do not establish flow performance[^15] |
| Gaillard et al., GEFCom additive models | Structured nonlinear and quantile models can be strong without unrestricted interactions | Publisher abstract/introductory material accessed; not a complete reproduction[^16] |
| Statnett, operational mFRR flow forecasting | Flow uncertainty depends on capacity and market state; compare point and uncertainty methods | HVDC balancing flows and ATC differ from NEM AC dispatch limits[^29] |
| Ng et al.; Deka and Misra, active-set OPF learning | Small sets of operating regimes motivate piecewise or regime-conditioned models | Optimisation/control experiments, not public-input NEM forecasting[^30][^31] |
| Liu et al., NEM extreme-price occurrence | Logistic regression is a credible simple event-probability baseline | Accepted-manuscript abstract accessed; operational input timing not independently verified[^32] |
| Schäfer et al., European physical-flow patterns | Cross-border flows can share low-dimensional structure | Descriptive PCA can miss rare constraint mechanisms[^33] |
| Worsnop et al., wind-ramp scenarios | Joint trajectories matter for events defined across time | Wind-ramp results do not prove interconnector-contraction skill[^34] |
| General tabular benchmark and European flow surrogate | Tree ensembles and neural surrogates deserve consideration where justified | Neither establishes that neural models beat this repo's engineered simple models[^18][^19] |

Statnett's 2026 account is unusually relevant industry evidence. For its mFRR flow problem, plain split conformal achieved 80% coverage with interval score 300; normalised conformal scored 269 at 78% coverage, while quantile boosting scored 218 at 80% coverage. The useful lesson is conditional uncertainty and empirical comparison, not a promise of those scores here. Its known ATC bounds cannot simply be substituted for NEM's dispatch-dependent reported limits.[^29]

The broader evidence also provides counterweights. Elastic net is useful when predictors are correlated, rather than treating unstable individual coefficients as reliable rankings. Forecast-combination research motivates testing a simple blend before estimating elaborate ensemble weights. An explainable boosting machine is an additive boosted model: “simple” and “boosting” are not mutually exclusive categories.[^35][^36][^37]

NESO's congestion-forecasting programme also identifies the practical importance of available network and forecast information. It supplies an industry problem framing, not a measured QNI/VNI uplift. The implementation proposed here therefore treats source access and reconstruction quality as model-design inputs rather than postponing them until deployment.[^17]

## 3. What the existing model does and does not establish

The current implementation pools six interconnectors and fits direct LightGBM forecasts for five targets across 30 minutes to seven days. It uses flow and capacity history, cross-regional information, calendar terms and demand, renewable and weather inputs. The saved historical run is conditional on realised future fundamentals for part of its design. That experiment is valuable as a conditional benchmark, but it is not the same task as forecasting with only information actually available at issue time.[^1][^2][^3]

The saved backtest reports gains over persistence in 92 of 120 selected cells, an equal-cell comparison rather than a portfolio-weighted gain. Its residual-based nominal 80% interval coverage is approximately 72.3%. The existing restriction detector also differs from sharp contraction: a low level relative to a seasonal reference is not necessarily a sudden fall. VNI import restriction recall of approximately 89.9% accompanies precision of only 21.1%, so alert usefulness must be measured explicitly rather than inferred from recall alone.[^3][^24]

The original AEMO comparison uses approximately 2.88 million matched pairs out to 39 hours. It does not establish like-for-like seven-day performance. AEMO's PD7DAY products deserve a separate, issue-vintage audit for the longer horizon: public documentation identifies constraint and interconnector solutions, and a market notice describes extending the prior five-day report to seven days in October 2025. Do not assume homogeneous seven-day forecast coverage for the whole two-year study.[^38][^39]

The target contract must distinguish dispatch `MWFLOW` from metered physical flow. Keep the current dispatch target for a controlled comparison, and evaluate a separate metered-flow target only with its own timing, losses and measurement definition. Never silently switch targets while reporting uplift.[^2]

## 4. Integrating the user's studies

Both studies cover 210,240 five-minute intervals: two complete September–August cycles. That gives two observations of each annual season, not many independent seasonal regimes. The event atlases screen the full period and retain selected detailed cases; the selected cases are diagnostic material, not an unbiased training sample.[^5][^6][^7][^8]

| Existing study output | VNI | QNI | Forecasting implication |
|---|---:|---:|---|
| DUIDs identified in the broad study | 232 | 238 | Too many to add blindly as individual predictors |
| Equation versions examined | 20,827 | 15,010 | Version identity matters; constraint ID alone is insufficient |
| Sharp-contraction detections | 7,486 | 7,430 | Interval/event definitions must be retained |
| Grouped incidents | 5,379 | 5,445 | Incidents are the preferred operational warning unit |
| Detailed selected cases | 91 | 92 | Suitable for mechanism audits, not event-frequency estimation |
| Contractions followed by MPC in the next hour | 13 | 5 | Too few for an ambitious standalone MPC classifier |
| Matched descriptive price-jump estimate | $94.98/MWh | $15.67/MWh | VNI association is clearer; neither is a causal effect |
| Reported 95% interval for that price-jump estimate | $58.27–136.83/MWh | −$26.73–53.33/MWh | QNI estimate is compatible with no positive association |

The broad VNI exposure list includes MURRAY, LIMOSF11, TUMUT3, SUNRSF1, UPPTUMUT, DARLSF1, STWF1 and MUWAWF1. QNI's list includes NEWENSF2, NEWENSF1, SAPHWF1, WRWF1, METZSF1, TUMUT3, BW01 and GNNDHSF1. These are hypotheses for grouping and monitoring. A large exposure score does not mean a generator causes every contraction, nor that its future movement is predictable.[^5][^6]

The selected-case accounting gives TUMUT3 approximately 35,037.5 MW of summed tightening contributions in VNI and 12,233.8 MW in QNI. Corresponding UPPTUMUT sums are 9,712.73 and 3,132.48; LIMOSF11 contributes 9,211.01 in VNI, while STAN2 and STAN1 contribute 4,679.85 and 4,044.73 in QNI. These are sums of stepwise MW accounting quantities across selected windows. They are not MWh, an individual event's capacity loss, population causal shares or a trading rule.[^7][^8]

The new audit is more diagnostic than merely repeating those rankings:

<!-- ATTRIBUTION_TABLE -->

| ic | cases | exact_share_median | cases_all_exact | cases_no_exact | complete_terms_share_median | cases_with_switch_component |
| --- | --- | --- | --- | --- | --- | --- |
| VNI | 91 | 1.0000 | 87 | 1 | 0.8000 | 62 |
| QNI | 92 | 0.6667 | 31 | 20 | 0.0000 | 24 |

<!-- END_ATTRIBUTION_TABLE -->

A version-matched step can still have incomplete terms. A numerical residual that closes an accounting identity does not prove all physical drivers were observed. Consequently, each event explanation should show observed capacity movement, same-equation generator contribution, RHS movement, other observed terms, a switch component, unresolved movement and provenance. Never relabel unresolved movement as generation.

The monthly feature-pipeline audit is also distinct from the broad study's reconstruction summary. It measures the features actually supplied to these experiments, with their own eligibility and matching rules. QNI's median monthly upper/lower reconstruction MAEs are about 364.69/199.71 MW, compared with approximately 0/1.63 MW for VNI; some VNI months are much worse than those medians. High candidate coverage can coexist with a poor chosen equation.[^28]

<!-- QUALITY_TABLE -->

| ic | exact_version_match_fraction | upper_reconstruction_mae_mw | lower_reconstruction_mae_mw | upper_setter_match_fraction | lower_setter_match_fraction |
| --- | --- | --- | --- | --- | --- |
| QNI | 0.6809 | 364.6893 | 199.7144 | 0.2146 | 0.2964 |
| VNI | 0.9366 | 0.0000 | 1.6300 | 0.9747 | 0.9851 |

<!-- END_QUALITY_TABLE -->

## 5. The mathematical representation

For a versioned equation involving interconnector signed flow F, generator quantities P and remaining terms Z, write:

```text
a_c F + sum_g(b_cg P_g) + Z_c <= R_c
B_c = (R_c - sum_g(b_cg P_g) - Z_c) / a_c
s_cg = -b_cg / a_c
```

For positive a, B is an upper candidate bound; for negative a the inequality reverses and B is a lower candidate bound. Canonicalise greater-than equations first. Treat equality constraints, ineligible equations and zero IC factors separately. Candidate bounds are conditional on the other quantities; the envelope is not a complete independent network transfer capability. Reported limit-setter rules and other dispatch restrictions must be respected.[^9][^10]

Within a fixed equation with fixed coefficients:

```text
Delta B_c = sum_g(s_cg Delta P_g) + Delta R_c/a_c - Delta Z_c/a_c
```

A generator's ramp can tighten one direction while relieving another. Use directional capacity C_plus = U and C_minus = -L, where U and L are signed upper and lower bounds. Define generator tightening as minus its contribution to directional capacity. For the upper direction this is -s times Delta P; for the lower direction it is +s times Delta P. Negative directional capacities must remain negative because they can encode forced direction. Do not clip them to zero during feature creation.

The sign convention in this repository is positive VNI flow from Victoria to NSW and positive QNI flow from NSW to Queensland. Confirm it at the adapter boundary and display both origin and destination regions. “Export” without a named origin is ambiguous.[^2]

### Candidate competition and switching

For upper candidates, the smallest eligible B sets the candidate envelope; the second-smallest is the nearest competitor. Lower candidates use the largest and second-largest. Keep each candidate's identity, version, evidence quality and distance to the winner. Near-binding equations matter because they can become setters after relatively small changes, but a constraint's native LHS slack is not interchangeable with IC-equivalent MW headroom.

A compact switching feature can be derived directly. If two candidate bounds have different sensitivities to a generator's movement:

```text
B_1 + s_1 Delta P = B_2 + s_2 Delta P
required Delta P to tie = (B_2 - B_1)/(s_1 - s_2)
```

For an illustrative upper-envelope example, B1=500 MW, B2=540 MW, s1=−0.2 and s2=−0.6 give a 100 MW increase before the candidates tie at 480 MW. This is a constructed example, not a measured Tumut coefficient. Restrict the stress calculation to plausible ramp direction, unit capability and a declared fixed-RHS assumption. Mark tiny denominators or unavailable capability as missing. The feature is a proximity-to-switch measure, not a forecast that the generator will move.

A related forced-direction stress is the movement required to drive a selected bound through zero, Delta P=−B/s. Once other equations switch, the original single-equation result may cease to apply. Report the calculation's validity domain rather than presenting a universal sensitivity.

### Why a small regime model is plausible

DC optimal-power-flow research shows how a fixed active basis supports an affine response, with different bases covering different operating regions. Active-set classification offers a related decomposition into identifying the regime and predicting within it.[^30][^31] The proposed application is an inference: small observed-regime linear experts may capture useful conditional behaviour without a large generic model. NEM co-optimisation, nonlinear security formulations, changing RHS inputs and missing data prevent treating this theory as an exact NEM forecasting solution.

## 6. Compact feature dictionary

Begin with a core network block of roughly 16–24 numeric features per interconnector, plus explicit missingness/quality indicators. The exact count should be chosen through ablation. Keep a richer evidence table for explanations without forcing every field into the model. The following is a proposed production design; only the smaller retained block described in Section 10 has been tested here.

| Family | Proposed representation | Typical dimensions | Why it belongs |
|---|---|---:|---|
| Directional state | Upper/lower capacity, signed room to flow, recent capacity change | 4–6, excluding duplicates already in base model | Describes current position and movement |
| Competition | Upper/lower runner-up gaps; number of eligible near candidates | 4 | Encodes sensitivity to switching |
| Generator pressure | Gross tightening and gross relief in each direction | 4 | Retains opposing contributions hidden by net sums |
| Forecast pressure | Signed expected pressure in each direction | 2 | Connects mechanism to future movement |
| Ramp feasibility | Achievable tightening/relief, or required-ramp-to-switch ratios | 2–4 | Distinguishes exposure from plausible movement |
| Persistence/regime | Setter age, recent switches, small family category | 2–4 | Represents stable versus changing operating conditions |
| Quality | Exact-version share, complete-term share, reconstruction discrepancy, source age | 4 | Prevents unsupported precision |

Do not simply total the dimension column: several state fields duplicate existing flow/capacity lags, and alternative feasibility summaries should compete rather than all being included. Reserve separate feature budgets for later additions and publish the final raw and expanded column counts.

For each candidate equation, compute positive tightening contributions T_cg and positive relief contributions R_cg. Aggregate with training-specified candidate weights that decline with IC-equivalent distance to the envelope. Normalise weights to sum to one within direction so duplicated candidates cannot mechanically inflate the score. Alternatively retain the current setter and nearest competitor as two separate summaries. Compare these formulations: a sum across every binding equation can double-count essentially the same restriction.

An influence ranking for feature selection should combine exposure frequency, absolute normalised sensitivity, plausible movement, proximity to setting and out-of-sample predictability of movement. Rank by direction and family. Distinguish four lists: frequent exposure, large historical accounting contribution, high prospective pressure and verified incremental forecast value. They answer different questions.

### Generator grouping and joint QNI/VNI structure

Use signed sensitivity vectors across equation families and directions to define groups. Geographic or fuel groups may be useful priors, but shared coal/hydro labels do not guarantee shared network effects. Keep tightening and relieving groups separate. Fit groups only on the training period, freeze them during evaluation and provide an unknown/new-unit path.

A generator can have a four-component exposure vector: VNI upper, VNI lower, QNI upper and QNI lower. Shared NSW pressure can then be represented with a few physical groups or a training-only low-rank projection. European cross-border-flow PCA provides descriptive evidence for shared structure; it does not establish that the highest-variance factors preserve rare contractions.[^33] Validate compression on event recall and direction errors, not only explained variance.

Avoid adding both dozens of individual units and all their group sums without regularisation. Preserve TUMUT3 and other selected units as explanation drill-downs even when the forecast uses a group sum. For a newly appearing unit, use its known coefficient vector and fuel/region fallback rather than assigning the entire population a new unconstrained feature.

The appropriate graph, if one is useful, is a generator–constraint–interconnector incidence graph. Constraint coefficients are not automatically physical bus-to-line PTDFs, and that graph does not require a graph neural network. Sparse matrix multiplication already implements the core pressure aggregation.

## 7. Forecasting generator pressure

Historical contribution is insufficient: a unit must move in a forecastable way to add predictive value. Build increasingly informed movement forecasts and compare the resulting pressure, keeping the same downstream model where possible.

| Movement model | Inputs allowed at issue time | Role |
|---|---|---|
| No movement | Last eligible unit state | Essential mechanism baseline |
| Bounded ramp persistence | Recent public SCADA ramps, capacity and ramp bounds when available | Short-horizon baseline; clips to plausible movement rather than extrapolating indefinitely |
| Group ARX or ridge | Lagged group generation, forecast net demand and public availability information | Parsimonious group movement forecast |
| Weather-linked renewable model | Issue-specific wind/irradiance forecasts and observed generation | Future VRE pressure; uncertainty must propagate |
| AEMO dispatch/region guidance | Only legally accessible, timestamped forecasts for the applicable horizon | Useful where historical public availability can be verified |
| Small boosted group model | Same eligible inputs plus validated interactions | Challenger when ramp errors remain nonlinear |

Use out-of-fold movement predictions when training the flow model. Feeding fitted movement estimates into the training sample and genuine forecasts at inference creates a mismatch. Benchmark an oracle movement track separately to estimate the maximum value of better generator forecasts without claiming that value is presently achievable.

Tumut requires explicit treatment of pumping and generation identities. AEMO's predispatch information calls out SNOWYP/Tumut 3 pumps and special reporting behaviour; a generator-only extraction can miss the load side.[^40] The adapter must retain DUID identity, direction of consumption/injection, effective registration dates and bidirectional-unit conventions. Do not infer pumping from a missing generation observation.

FCAS terms, other interconnector flows and regional terms also affect equations. Start with a transparent energy-term model and label omissions. Expand only when the required terms and release times can be reconstructed. A fitted RHS forecast may absorb missing generation effects; it should not be labelled an independent physical explanation for those effects.

## 8. Data contracts and historical availability

Every predictor row needs a forecast origin, delivery interval, source issue/run time, first observed publication time, effective/version time, retrieval time and transformation version. These timestamps answer different questions. `LASTCHANGED` is not universal proof of public publication. Effective date determines equation applicability; first publication determines whether the forecaster could know it.

| Data layer | Minimum useful content | Availability rule | Fallback |
|---|---|---|---|
| Interconnector state | Signed flow, directional limits, setters, intervention/run fields | Latest public record received before origin | Persistence with age flag |
| Equation definition | IC, connection-point and regional factors; type; version; effective dates; set membership | Version applicable at delivery and known by issue time | Unknown family or no mechanical estimate |
| Constraint solution | RHS, LHS, marginal value, violation and run/interval | Dispatch observations or an admissible predispatch vintage | Statistical state model |
| Generator observation | SCADA and identity mapping | Use source-specific release, not another feed's delay | Missing observation, never silent zero |
| Solved unit target/availability | Cleared generation, capability, FCAS where needed | Historical public/participant access must be established per field | Exclude from strict public track |
| Future demand/VRE | Forecasts with preserved run time and horizon | Latest eligible issue, never final realised value | Seasonal or persistence forecast |
| Outages and capacity | Known schedules, expected return, current online evidence | Version known at issue; actual outage is a later outcome | Explicit unknown status |
| Weather | Temperature, wind, irradiance, uncertainty and issue time | Individual historical forecast run where available | Restricted-horizon or statistical fallback |
| Price and scarcity | Observed lagged prices; eligible price/reserve forecasts | Realised future price is a label/context only | Separate price-risk model |

AEMO's public SCADA definition and unit-solution visibility distinctions require field-level treatment; solved dispatch targets are not interchangeable with start-of-interval measurements.[^11][^12] The current predispatch procedure is version 19, effective 1 April 2026; archive the applicable procedure and schema version when reviewing earlier periods.[^41]

PD7DAY is a potentially valuable expansion beyond the original benchmark horizon. First enumerate report types and schema transitions, sample the minimum necessary files, then measure available issue/delivery coverage. The documented public tables include run timestamps and constraint solutions; the non-data-model loading guide also shows interconnector solution fields. Publication and archive coverage must be demonstrated rather than inferred from current documentation.[^38][^39]

Historical weather observations, reanalysis and stitched forecast series are useful for explanation but cannot substitute uncritically for the individual forecasts available at issue time. Open-Meteo explicitly distinguishes historical forecast products and individual runs, with model-dependent coverage.[^13] Begin with a small set of load-weighted regional temperature summaries and renewable-relevant zones instead of a dense national grid.

## 9. Model portfolio, from simple to boosting

| Stage | Candidate | Appropriate use | Main failure mode | Advancement test |
|---|---|---|---|---|
| 0 | Persistence, daily/weekly seasonal naive | All tasks as reference; recent state often strong | Misses changing regimes | Always retain scores and operational fallback |
| 1 | AEMO forecast plus rolling bias correction | Flow/limits where eligible issue vintages exist | Inherited forecast errors and unavailable horizon | Beat raw AEMO on identical issue/target pairs |
| 2 | Ridge/elastic-net ARX residual model | Compact lags, pressures and forecast innovations | Misses switching interactions; unstable extrapolation | Stable seasonal gain over Stage 0/1 |
| 3 | Penalised logistic regression | Contractions, direction and switch probabilities | Calibration drift, omitted thresholds | Better Brier/AP and incident warnings at fixed burden |
| 4 | Low-degree GAM or selected hinge terms | Smooth weather/calendar effects and explicit thresholds | Excess basis expansion with weak signal | Beat linear model with same input vintages |
| 5 | Small regime-conditioned linear experts | Within-regime flow or capacity response | Wrong regime assignment; tiny training groups | Improvement persists for new and rare regimes |
| 6 | Quantile linear/GAM or conditional residual bins | Asymmetric uncertainty and tail warnings | Sparse tails, quantile crossing | Better proper score at acceptable coverage |
| 7 | Additive boosting/EBM | Nonlinear main effects with a few inspectable interactions | Flexible functions still overfit and need calibration | Outperform simpler additive specification |
| 8 | Shallow LightGBM, L1/L2/quantile/classification | Interactions between pressure, headroom and economic state | Spurious thresholds, extrapolation and source dependence | Robust gain on matched public-input tests |
| 9 | Blends of simple and boosted forecasts | Complementary errors | Weight estimation noise | Beat best component after weight selection is frozen |
| Deferred | Sequence neural models, GNNs, OPF surrogates | Large verified datasets or specific residual failure | Complexity before information quality | Demonstrable need beyond the above portfolio |

Ridge should normally be the first linear model when pressure components are correlated. Elastic net adds controlled sparsity and grouped retention, but its selected coefficient is a predictive parameter rather than a physical sensitivity.[^35] Use horizon-specific residual targets, such as actual flow minus persistence or an eligible AEMO forecast. Direct models avoid accumulating recursive errors, while a pooled lead-time model can reduce estimator count; compare both under equal information.

The earlier local spline experiment was usually worse than its base model. That is evidence against the particular broad spline expansion, not against all GAMs. Use a few predeclared terms—room, pressure, net demand, hour—before adding interactions. Explainable boosting machines offer another additive option, but should be counted as boosted models in the complexity audit.[^23][^37]

For regimes, prefer observable families such as stable upper setter, stable lower setter, near switch, uncertain equation state and forced direction. Fit a pooled ridge with a few interactions before separate experts. If separate experts are used, shrink small groups toward the pooled forecast, predict regime probabilities using eligible inputs and mix their predictions. Never assign the future observed setter at prediction time.

LightGBM is already present in the repository, so the practical question is where to retain it and how to improve its information. Compare L1, L2 and quantile objectives rather than attributing a loss-function benefit entirely to architecture. Constrain leaf count and depth, use large leaf support, tune on chronological validation and log all tried configurations. Avoid universal monotonic constraints on a generator: its network effect changes with direction and equation family.[^20]

The tabular benchmark supports trees as a credible alternative to deep learning, while the European interconnector surrogate addresses simulated planning flows. Neither requires a neural upgrade here.[^18][^19] Temporal Fusion Transformers remain an optional later experiment if a large archive of genuinely available multi-horizon covariates exposes a sequence-specific deficiency.[^21]

## 10. New numerical experiments and results

The new experiment is a bounded comparison on retained data, not a replacement for the full seven-day production backtest. It tests flow and both directional tight-capacity targets at 30 minutes, three hours and 24 hours for QNI and VNI. It also tests probability of a new sharp contraction in the next hour.[^28]

### Regression design

The base has 17 raw predictors: three target series with lags of 1, 48 and 336 half-hour steps, three recent changes and five calendar terms. The state block adds eight features: two rooms, two switch gaps, two candidate counts, partial-candidate share and pressure-completeness share. The pressure block adds eight: gross tightening/relief in both directions, two pressure-change fields and two available-relief summaries. Full means 33 raw predictors before missingness indicators.

The retained topology is sampled from native five-minute states at minutes 00 and 30, then shifted one half-hour. It is not a half-hour average. The existing pressure-change columns are changes in the pressure series, not simply the underlying generator ramp; preserve that distinction when reimplementing. Two constant envelope-persistence fields included in the earlier probe are excluded from this experiment. The two probes therefore do not have identical full feature sets.[^4][^23][^28]

Train on origins from 8 September 2024 whose deliveries precede 1 September 2025. Select hyperparameters using September–November 2025, keeping deliveries inside that partition. Evaluate March–August 2026, with delivery no later than 31 August 23:30. Models are not refitted through the calibration months. All observations use the origin-minus-30-minute anchor; a nominal 30-minute lead therefore predicts an outcome 60 minutes after that anchor.

Ridge uses training-only 0.1/99.9-percentile clipping, mean imputation with missing indicators, standardisation and alpha selected from 10/100/1000. Boosting uses 150 trees, learning rate 0.04, minimum child support 150, L2 leaf regularisation 10 and 7/15 leaves selected by validation MAE. It retains native missing values without clipping. Consequently, comparisons across architectures also compare preprocessing pipelines. Within-family base/full ablations are more controlled. L1 versus L2 boosting provides a separate loss comparison; the experiment does not isolate every source of gain.

<!-- REGRESSION_SUMMARY -->

| ic | horizon_minutes | boost_l1_base | boost_l1_full | boost_l2_full | persistence | ridge_base | ridge_full | ridge_pressure | ridge_state |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| QNI | 30 | 113.2686 | 112.2667 | 113.6160 | 115.2887 | 117.4117 | 116.7886 | 117.4399 | 116.6482 |
| QNI | 180 | 212.1230 | 210.5661 | 214.7486 | 211.8380 | 219.0993 | 219.8993 | 219.2390 | 220.5401 |
| QNI | 1440 | 249.8766 | 247.3361 | 249.5930 | 271.5475 | 247.6914 | 246.4789 | 247.7435 | 246.7317 |
| VNI | 30 | 143.9491 | 142.7349 | 144.3364 | 155.4543 | 156.4172 | 154.8913 | 155.3504 | 156.0741 |
| VNI | 180 | 253.7697 | 253.9124 | 257.1998 | 317.5577 | 277.0724 | 278.7179 | 276.1986 | 280.7570 |
| VNI | 1440 | 340.0298 | 341.9872 | 356.0472 | 377.3347 | 332.0478 | 341.3433 | 332.3201 | 340.3967 |

<!-- END_REGRESSION_SUMMARY -->

Full L1 boosting improves over its own base in **12/18** target–IC–horizon cells and beats persistence in **15/18**. Full ridge improves over base ridge in **10/18**. Counts weight cells equally and are not an overall percentage improvement. The full block includes network state and quality as well as generator pressure, so these gains cannot all be assigned to generators.

VNI's 30-minute full-boost flow improvement over its own base is 1.21 MW, with an exploratory seven-day block-bootstrap interval of 0.63–1.87 MW. QNI's corresponding increment is 1.00 MW, interval 0.42–1.61 MW. At three hours, the topology increment is −0.14 MW for VNI and +1.56 MW for QNI, with intervals crossing zero in both cases. At 24 hours, base ridge is the best listed VNI flow model, while full ridge narrowly beats the other listed QNI flow models.

The confidence intervals use 300 non-circular seven-day origin-block resamples with seed 741. They are exploratory paired uncertainty estimates, not multiple-comparison-corrected significance claims. Repeated use of the evaluation period and upstream retrospective data issues remain even when an interval excludes zero.

### Contraction-probability design

The repository's event detector and general event methodology provide the retrospective reference definition; the prospective experiment below deliberately freezes its thresholds using training data.[^22]

For this prospective-label experiment, define a positive 30-minute directional-capacity fall at each five-minute interval. Fit a month-of-year 90th percentile of positive falls using only the first study year, then freeze those 12 thresholds. A sharp interval requires a positive fall at least as large as its frozen monthly threshold. An onset occurs when the sharp indicator changes from false to true. Require a complete seven-observation window for the fall and complete future observations for the prediction label.

The target is any new onset in the next 60 minutes after each half-hour forecast origin. These windows overlap. The original atlas's historical detector and the new training-frozen detector serve different purposes; counts are not directly interchangeable. The monthly thresholds are included in the evidence file. For example, VNI upper March is approximately 257.53 MW and upper December 451.57 MW. A single fixed “sharp = 100 MW” rule was not used.

Logistic base/full models select C from 0.01/0.1/1 using validation log loss. Shallow boosted base/full classifiers use the same small leaf grid as regression. Sigmoid calibration is fit during December 2025–January 2026; alert cutoffs are selected from February negative-origin probabilities at the 95th percentile, using a strict greater-than comparison. This targets at most 5% false-positive rate on that tuning sample, not a guaranteed future rate.

<!-- EVENT_TABLE -->

| ic | direction | model | brier | average_precision | recall | precision | false_positive_rate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VNI | export | climatology | 0.1414 | 0.1704 | 0.0000 | 0.0000 | 0.0000 |
| VNI | export | logistic_base | 0.1372 | 0.3015 | 0.2086 | 0.3046 | 0.0979 |
| VNI | export | boost_base | 0.1303 | 0.3750 | 0.2266 | 0.4541 | 0.0560 |
| VNI | export | logistic_full | 0.1331 | 0.3611 | 0.1814 | 0.4604 | 0.0437 |
| VNI | export | boost_full | 0.1311 | 0.3789 | 0.1615 | 0.4812 | 0.0358 |
| VNI | import | climatology | 0.0892 | 0.0960 | 0.0000 | 0.0000 | 0.0000 |
| VNI | import | logistic_base | 0.0892 | 0.2232 | 0.4198 | 0.1898 | 0.1904 |
| VNI | import | boost_base | 0.0860 | 0.2674 | 0.2913 | 0.2869 | 0.0769 |
| VNI | import | logistic_full | 0.0858 | 0.2468 | 0.3031 | 0.2286 | 0.1086 |
| VNI | import | boost_full | 0.0835 | 0.2873 | 0.3007 | 0.3418 | 0.0615 |
| QNI | export | climatology | 0.1089 | 0.1242 | 0.0000 | 0.0000 | 0.0000 |
| QNI | export | logistic_base | 0.1101 | 0.1884 | 0.2343 | 0.2030 | 0.1305 |
| QNI | export | boost_base | 0.1027 | 0.2915 | 0.3355 | 0.3361 | 0.0940 |
| QNI | export | logistic_full | 0.1059 | 0.2192 | 0.1522 | 0.2485 | 0.0653 |
| QNI | export | boost_full | 0.1060 | 0.3072 | 0.3920 | 0.3375 | 0.1091 |
| QNI | import | climatology | 0.2232 | 0.2973 | 0.0000 | 0.0000 | 0.0000 |
| QNI | import | logistic_base | 0.1971 | 0.4570 | 0.3375 | 0.5160 | 0.1339 |
| QNI | import | boost_base | 0.2059 | 0.4390 | 0.1371 | 0.5121 | 0.0553 |
| QNI | import | logistic_full | 0.1949 | 0.4727 | 0.3341 | 0.5147 | 0.1333 |
| QNI | import | boost_full | 0.2053 | 0.4551 | 0.1147 | 0.5172 | 0.0453 |

<!-- END_EVENT_TABLE -->

Full logistic improves Brier score over its own base in all four IC/direction tasks. Full boosting improves over its own base in only two. For QNI import, logistic full has Brier 0.1949 and average precision 0.4727, versus boosting full at 0.2053 and 0.4551. For VNI export, boosting base has slightly better Brier than boosting full despite the latter's slightly better ranking score. Probability calibration and ranking are different objectives.

Alert cutoffs do not transfer perfectly. QNI import full logistic has evaluation false-positive rate about 13.33%, far above the February target, while full boosting is about 4.53%. Their recalls are approximately 33.41% and 11.47%, respectively. It would be misleading to declare either an operational winner without comparing deduplicated incidents at a common acceptable alert burden. Recalibration and explicit burden constraints are therefore implementation requirements, not decorative metrics.

The new classifier experiment predicts positive origin windows, not independently matched incidents. It does not measure event lead time, one-warning-per-incident recall, MPC prediction skill or generator-level causal attribution. These are specified as next-stage tests. No event-score confidence interval was computed in this run; rare-event and overlapping-window uncertainty must remain visible.

## 11. Event forecasting, price volatility and explanations

Use separate target families rather than letting a single regression carry all warning objectives: capacity level, contraction onset, contraction severity, setter switch, actual flow reversal and a bound forcing direction. A flow reversal can occur for economic reasons without a limit contraction; a contraction can occur while flow remains far from the affected bound. Predict and evaluate these distinctions explicitly.

For operational incident scoring, freeze the threshold and incident-merging rules before evaluation. Match an alarm only to the next eligible incident in a declared lead window, credit each incident once, suppress repeated alarms for a documented refractory period and report late detections separately. Measure recall, precision, false alarms per day, median and lower-decile advance lead, severity-weighted misses and time spent under warning. Retain origin-level Brier/log loss/AP for probability assessment; do not confuse them with incident metrics.

Price impact should be a second layer. Model price-spread or extreme-price risk conditional on network state, predicted contraction, available reserves and market conditions, with a control model omitting contraction features. Separate: contraction without volatility, volatility without contraction, contraction followed by volatility and common-cause events such as regional scarcity. Exact MPC uses the applicable historical cap schedule, not today's cap imposed on both years.

The NEM logistic-price paper makes a simple event model credible, but the accessible abstract does not settle historical availability of all its predictors or its exact temporal split.[^32] The local atlas has only 13 VNI and five QNI contraction-to-MPC observations. Start with a broader predeclared high-price or large-spread threshold and use exact MPC cases as audited case studies. Keep price-only controls; avoid oversampling rare cases before the time split or presenting balanced-sample probabilities as market frequencies.

An event explanation should contain three explicitly labelled layers. **Observed mechanism accounting** shows versioned equations and measured terms. **Forecast contribution** shows how the model's prediction changes when a feature group is removed or replaced with its admissible baseline. **Counterfactual hypothesis** describes a plausible unit or RHS change under stated fixed conditions. SHAP or a coefficient plot does not by itself prove what a generator physically caused; the causal-interpretation literature makes the observational/interventional distinction explicit.[^42]

For switch events, keep a composite switch contribution unless a consistent old/new-equation decomposition has been justified. Report attribution sensitivity to decomposition order where applicable. Include unmatched versions and incomplete FCAS/other terms in the uncertainty panel, rather than excluding the most difficult events silently.

## 12. Market, seasonal and diurnal context

The first feature tests should use network state and pressure. Then add market conditions in controlled layers, so their incremental contribution and confounding role are visible.

| Context layer | Compact representation | Interpretation guard |
|---|---|---|
| Demand | Regional forecast demand, net demand, ramp and percentile relative to training season/hour | Do not subtract rooftop solar twice from a demand definition that already excludes it |
| Renewables | Forecast wind, utility solar and rooftop solar shares; expected ramp; uncertainty | Actual output is retrospective context unless already observed |
| Coal | Publicly supported online capacity, observed online count, forecast availability, time since start/stop | Zero generation does not prove an outage; unit maximum is not assured available capacity |
| Hydro/storage | Observed generation/pumping, available public capability, mode transition | Reservoir/state-of-charge knowledge may be incomplete |
| Transmission outages | Known schedule, active equation-family proxy, time to planned return | Actual future outage status is not an admissible issue-time predictor |
| Weather | Load-weighted temperature, hot/cold departure, regional wind/irradiance forecast summaries | Weather is context and a forecast driver, not automatic proof of a network cause |
| Economic conditions | Lagged regional spread, forecast reserve margin, admissible AEMO price forecast | Future realised price cannot explain a prediction made earlier |

Seasonal reporting should show each of the eight season-years separately, then an explicitly labelled pooled seasonal summary. Use occurrence rates per eligible hour, not only event counts. For diurnal comparisons show NEM half-hour or hourly bins, separating weekdays/weekends only when support permits. Keep denominator coverage alongside each heatmap or table, because a missing-source pattern can look like a seasonal network effect.

Two years allow descriptive seasonal comparison, but only two winters do not establish a stable winter law. The new model experiment evaluates autumn and winter 2026 only; a full two-year input window is not a full two-year out-of-sample model evaluation. Use expanding-window development folds for additional seasons where training support permits, and reserve future data for the final operational assessment.

A specific within-study structural break is now documented: AEMO's December 2025 formulation guideline changes the minimum LHS factor threshold from 0.07 to 0.15 and describes normalisation and moving remaining small terms to the RHS.[^43] This can change an observed LHS exposure list without removing a generator's physical relevance. Audit feature distributions, family matching and RHS residuals across the effective date. The research has not established that this change caused the QNI reconstruction errors.

Project EnergyConnect adds another reason to version network configuration. AEMO's current FAQ discusses planned October/November 2026 operational and settlement changes and distinguishes loop equations from reported limit setters.[^27] Follow actual implementation notices rather than hardcoding a future date or retaining a six-interconnector assumption indefinitely.

## 13. Probabilistic forecasts and joint scenarios

Improve uncertainty alongside the point forecast. Begin with residual distributions stratified by direction, headroom and a small quality/regime grouping, pooling sparse bins. Compare linear quantile regression, a small quantile GAM and quantile boosting. Report 50/80/95% coverage, interval width and proper interval or weighted interval score; a very wide interval can achieve coverage while being unhelpful.[^25]

Conformalised quantile regression is a candidate calibration layer, not a guarantee that arbitrary nonstationary NEM data will have exact conditional coverage. Time-series conformal methods address dependence under their own assumptions. Evaluate calibration by season, near-bound state, switch status and missingness, with calibration data strictly preceding scored outcomes.[^44][^26]

Preserve signed distributions near zero and allow skew. Do not force normality or clip flow forecasts to realised future limits. Even predicted reported bounds may be conditional and inconsistent; start with a diagnostic consistency penalty and publish raw versus adjusted scores. Use hard physical projection only when the feasible set and its information timing are defensible.

Contractions are path events. Independent draws from five-minute marginal quantiles destroy temporal dependence and can produce implausible switching frequency. Start with whole residual-block resampling conditioned on broad regime, retaining correlated QNI/VNI residuals and consistent demand/VRE scenarios. Wind-ramp scenario research supports the need for temporal structure, while also finding method performance depends on the available forecast information.[^34]

A two-component blend of simple and boosted forecasts is worth testing after their individual evaluation. Select a fixed or slowly varying weight on validation, then freeze it; avoid tuning weights on reported test events. For probabilistic forecasts, averaging quantiles is not the same as mixing predictive distributions. Compare the actual combined distribution using the same proper score.[^36]

## 14. Validation that can support a deployment decision

Create three separate data tracks: **strict public issue-time inputs**, **retrospective mechanism reconstruction**, and **oracle future fundamentals**. The first estimates implementable performance; the second investigates how equations behaved; the third bounds the value of better upstream forecasts. Their rows, labels and claims must never be blended into one headline score.

Temporal evaluation literature supports realistic chronological assessment and warns about flawed preprocessing and benchmark design; some stationary settings admit other resampling methods, but this network's changing equations and overlapping events make chronological replay the appropriate default.[^45][^46]

Use an experiment ladder that isolates information value:

| Experiment | What changes | Question answered |
|---|---|---|
| E0 | Eligible persistence and seasonal references | What is the minimum useful benchmark? |
| E1 | Same rows plus AEMO forecast and bias correction | How much can a simple official-forecast correction achieve? |
| E2 | Add current state/competition/quality only | Does state help without generator pressure? |
| E3 | Add observed pressure only | Does generator history add beyond state? |
| E4 | Add out-of-fold forecast pressure | Is future movement predictability valuable? |
| E5 | Add regime interactions or small experts | Does setter switching explain residual errors? |
| E6 | Add market and forecast-weather layers one at a time | What is their incremental value? |
| E7 | Compare matched ridge/GAM/boost pipelines and losses | Is model complexity justified? |
| E8 | Add calibration and joint scenarios | Are warning probabilities and paths reliable? |
| E9 | Prospective shadow replay | Does the benefit survive real publication delays? |

For each fold, fit scalers, thresholds, groupings, imputers, candidate weighting parameters, feature selection and model settings inside its training/validation windows. Purge training labels that extend into a later split. Event-calibration and alert-tuning windows must also be disjoint and mature. Report the row intersection used for each model comparison and separately report performance on all rows where each model operates.

Use flow/capacity MAE, RMSE, bias and large-error quantiles, plus sign accuracy outside a predeclared near-zero band. For events use both proper probability scores and incident metrics. For forced direction, report upper-negative and lower-positive cases separately and audit inconsistent envelopes. Use seasonal, diurnal, family, quality and contraction-severity slices with sample counts. Avoid MAPE near zero and when signed values change direction.

Use paired day/week blocks for model-error uncertainty and whole incidents for event bootstrap. Check sensitivity to block length. Predeclare the primary outcomes and apply an appropriate multiplicity policy for confirmatory comparisons; label exploratory slices accordingly. The current March–August results remain development evidence even if hyperparameters were selected earlier, because the period has already informed research decisions.

The recommended balanced acceptance contract is provisional: seek at least 5% flow-MAE improvement without material deterioration in contraction warnings, or a material incident-warning gain with no more than 2% flow-MAE deterioration. Define “material warning gain” in advance—for example, a specified recall improvement at the same false alarms per day and minimum lead time. These are engineering targets, not literature-derived universal thresholds. Require calibration, availability and runtime gates as well as accuracy.

Do not wait two more years to start shadow forecasts, but do not call a short shadow run a completed seasonal validation. Start now with timestamped predictions and progressively accumulate unseen conditions.

## 15. Repository implementation and storage plan

Keep the existing model reproducible. Add the new feature adapter, eligibility checks and experiment registry behind explicit configuration. The existing [constraint feature module](../nemic/constraint_features.py), [model module](../nemic/model.py), [preparation module](../nemic/prepare.py) and [event atlas module](../nemic/event_atlas.py) provide the integration points. New module names below are proposed, not implemented production functionality.

| Deliverable | Proposed location or interface | Completion evidence |
|---|---|---|
| As-of source contract | `nemic/source_vintages.py` | Per-field release audit and replay checks |
| IC adapter | Configuration for identity, signs, region mapping and target definitions | Same mechanics pass for QNI/VNI without duplicated logic |
| Compact feature builder | Extend existing constraint feature module with versioned blocks | Algebra and timing checks; feature manifest |
| Forecast pressure | `nemic/pressure_forecast.py` | Out-of-fold group movement predictions and uncertainty |
| Model registry | Configured persistence/ridge/logistic/GAM/boost factories | Identical row/feature eligibility for comparisons |
| Event scorer | Extend event atlas interfaces with prospective onset and incident matching | Deterministic matching and alert-burden report |
| Replay runner | Issue-time snapshots and matured targets | Immutable prediction logs and no future reads |
| Research/report build | Compact score and quality artifacts | Markdown and offline HTML from the same evidence |

The **10 GB limit is a combined working-data budget**, including retained research data allocated to the run, downloads in progress, compressed archives, extraction scratch, parsed partitions and prediction outputs. It is not a per-file allowance. Reserve an additional minimum free-disk floor, proposed at 20 GB, and stop acquisition before either guard is breached. Existing unrelated files must not be deleted to meet the budget.

Before any acquisition, inventory existing partitions and hashes. Specify an allowlist of tables, months, fields, ICs and necessary DUID/constraint joins. An archive may contain a full month; estimate compressed and expanded size before downloading it. If a minimal required archive cannot fit, stream supported records or stop with a concrete capacity requirement. Never fall back to downloading all MMSDM tables.

Process one bounded month or source batch at a time: reserve space, download to a dedicated scratch directory, verify checksum/schema, extract only necessary members, filter/chunk immediately, write an atomic compact partition, validate coverage and then delete that batch's raw scratch. Log source URL, expected and actual bytes, hash, retrieval time, selected members/filters, output hash and deletion completion. Retain provenance and compact results after raw deletion. Redownload is keyed to missing or failed partitions, not repeated automatically.

Before deleting or moving anything, resolve the target path and ensure it lies within that dedicated scratch directory. A failed validation should quarantine only the relevant small evidence or record enough metadata to reproduce it; it should not trigger a second unrestricted acquisition. Restart from a per-month status ledger with states such as planned, downloaded, filtered, validated and cleaned.

Keep high-volume input snapshots and per-origin predictions outside Git. Commit code, methodology, compact aggregate metrics and provenance manifests. Do not retain every model candidate binary. Keep the selected model and necessary rollback predecessor, and prune only artifacts explicitly owned by the run. Estimate output growth as origin count × horizons × targets × model count before choosing to save all predictions; use partitioned compressed columns and retain only selected candidates after scoring.

## 16. Tests, diagnostics and report structure

Test the mechanics that could reverse the interpretation: positive/negative IC factor, inequality reversal, upper/lower directional signs, zero factor, near-zero denominator, negative capacity, equation switch and scaling invariance. Multiplying the full equation by a positive constant must leave B and normalised sensitivity unchanged. Exact-version joins must exclude future definitions and distinguish missing coefficients from true zero coefficients.

Test time boundaries with deliberately late publications, corrections, duplicate runs and missing observations. Assert every feature's availability is no later than forecast issue. A future actual deliberately introduced into a fixture should be rejected. Verify target delivery and event look-ahead cannot cross training/calibration boundaries. Fit transformations on training only and check their hashes remain unchanged when evaluation outcomes are altered.

For event scoring, test onset versus persistent sharp state, two incidents inside one horizon, repeated alarms for one incident, missing five-minute observations, midnight/month thresholds and MPC schedule changes. Confirm that incident and origin-window counts are reported separately. For model integration, verify fallback predictions exist when topology fails and that a source-age warning does not expose an unexplained zero as a physical measurement.

The final operational report should have a top-level skill and data-quality overview, seasonal/diurnal performance, mechanism groups, warning performance and a searchable event atlas. Each detailed event should align: flow and directional limits; forecast issued before onset; uncertainty band; equation identity and switch timeline; generator ramps and signed pressure; RHS/other/unresolved accounting; regional price/spread; and a secondary market-context panel. Display the selected issue time and data vintage prominently.

Recommended visuals for the implementation stage are an IC-by-horizon model-skill heatmap, a state-versus-pressure ablation plot, reliability and precision–recall plots, incident recall versus false alarms/day, eight season-year panels, diurnal occurrence rates with eligible-hour denominators, a candidate-gap/pressure phase plot, and version-quality timelines around formulation changes. This research edition provides numerical tables, including all regression and event scores, rather than claiming those full operational plots have been generated.

## 17. Prioritised delivery sequence and unresolved questions

**First, repair the evidence boundary.** Audit QNI candidate eligibility, setter matching, version joins, omitted terms and the worst monthly discrepancies. Confirm whether each proposed feature is public at issue time. Retain useful QNI statistical state forecasts while disabling unsupported precise mechanical explanations. VNI also needs month-level quality checks despite stronger median reconstruction.

**Second, build the compact baseline portfolio.** Persistence, eligible AEMO correction, ridge and logistic should share one source contract. Introduce state and pressure separately. Match preprocessing and loss where feasible before attributing differences to architecture. Use the new shallow-boost results to prioritise VNI near-term experiments, while keeping ridge and logistic strong candidates elsewhere.

**Third, add forecast movement and switching.** Implement a small group movement model, candidate competition and one regime-interaction model. Demonstrate that future-pressure predictions add beyond current state. Then add demand, renewables, availability and weather as separate ablations. Fit source-specific uncertainty rather than assuming forecast inputs are exact.

**Fourth, finish operational event evaluation and shadow delivery.** Calibrate, deduplicate alarms, measure lead time and burden, and issue timestamped forecasts before observing outcomes. Introduce a price-risk layer only after contraction forecasts work acceptably. A full causal dispatch replay, unseen multi-season validation and reliable seven-day unit-level public inputs remain separate investigations.

The central unresolved issues are the cause of QNI reconstruction failures, complete historical public availability of unit/FCAS and outage inputs, availability of consistent PD7DAY vintages across schema changes, and whether the modest pressure gains persist with those strict inputs. The strongest current conclusion is that the studies supply useful **feature structure and event hypotheses**, while model selection must remain task-specific and empirically tested.

## 18. Complete numerical appendix

All numbers below come from the expanded experiment, using its fixed partitions and retrospective limitations. Autumn and winter refer to forecast-origin season in March–August 2026. They are not eight-season model results. The machine-readable evidence also contains settings, exact detector thresholds, paired uncertainty estimates and all input hashes.[^28]

### All regression scores

<!-- ALL_REGRESSION -->

| ic | target | horizon_minutes | model | n | mae_mw | rmse_mw | bias_mw | autumn_mae_mw | winter_mae_mw |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VNI | flow | 30 | persistence | 8831 | 155.4543 | 225.7835 | -0.0513 | 154.6743 | 156.2345 |
| VNI | flow | 30 | ridge_base | 8831 | 156.4172 | 209.1968 | 0.9845 | 156.5007 | 156.3337 |
| VNI | flow | 30 | ridge_state | 8831 | 156.0741 | 208.2712 | 14.8595 | 155.5691 | 156.5793 |
| VNI | flow | 30 | ridge_pressure | 8831 | 155.3504 | 207.8997 | 1.4320 | 155.3756 | 155.3252 |
| VNI | flow | 30 | ridge_full | 8831 | 154.8913 | 207.2029 | 18.4312 | 153.3416 | 156.4414 |
| VNI | flow | 30 | boost_l1_base | 8831 | 143.9491 | 201.4633 | -11.6384 | 138.8502 | 149.0493 |
| VNI | flow | 30 | boost_l1_full | 8831 | 142.7349 | 200.1496 | -12.8319 | 137.7497 | 147.7212 |
| VNI | flow | 30 | boost_l2_full | 8831 | 144.3364 | 199.7523 | -15.5952 | 138.8085 | 149.8656 |
| VNI | export_tight | 30 | persistence | 8831 | 150.6695 | 237.4092 | 0.0071 | 144.9239 | 156.4164 |
| VNI | export_tight | 30 | ridge_base | 8831 | 152.9035 | 212.3886 | 8.7115 | 148.3663 | 157.4418 |
| VNI | export_tight | 30 | ridge_state | 8831 | 154.0095 | 213.1215 | 13.7286 | 149.8116 | 158.2085 |
| VNI | export_tight | 30 | ridge_pressure | 8831 | 150.2494 | 209.0998 | 9.5291 | 145.3311 | 155.1689 |
| VNI | export_tight | 30 | ridge_full | 8831 | 152.1367 | 210.7762 | 15.9662 | 147.5674 | 156.7069 |
| VNI | export_tight | 30 | boost_l1_base | 8831 | 133.4303 | 199.6624 | 6.5741 | 123.2147 | 143.6481 |
| VNI | export_tight | 30 | boost_l1_full | 8831 | 130.4804 | 195.3094 | 12.4529 | 120.7384 | 140.2245 |
| VNI | export_tight | 30 | boost_l2_full | 8831 | 134.7369 | 196.5372 | 0.5229 | 125.5664 | 143.9094 |
| VNI | import_tight | 30 | persistence | 8831 | 114.1010 | 204.8323 | 0.0070 | 100.8246 | 127.3803 |
| VNI | import_tight | 30 | ridge_base | 8831 | 132.5464 | 201.0022 | -21.0667 | 119.8026 | 145.2931 |
| VNI | import_tight | 30 | ridge_state | 8831 | 133.0398 | 199.6780 | -30.6919 | 119.6971 | 146.3855 |
| VNI | import_tight | 30 | ridge_pressure | 8831 | 133.7833 | 199.7733 | -23.6459 | 121.9428 | 145.6264 |
| VNI | import_tight | 30 | ridge_full | 8831 | 134.0661 | 198.7016 | -34.1801 | 120.6182 | 147.5169 |
| VNI | import_tight | 30 | boost_l1_base | 8831 | 109.5657 | 191.6259 | 0.3169 | 94.0390 | 125.0960 |
| VNI | import_tight | 30 | boost_l1_full | 8831 | 106.5268 | 187.4831 | -2.9920 | 92.3583 | 120.6986 |
| VNI | import_tight | 30 | boost_l2_full | 8831 | 119.9630 | 190.4981 | -28.4767 | 107.7596 | 132.1692 |
| VNI | flow | 180 | persistence | 8826 | 317.5577 | 431.0281 | -0.0424 | 334.0335 | 301.0594 |
| VNI | flow | 180 | ridge_base | 8826 | 277.0724 | 341.1462 | -12.4000 | 285.1817 | 268.9520 |
| VNI | flow | 180 | ridge_state | 8826 | 280.7570 | 346.0384 | -41.0182 | 290.4306 | 271.0702 |
| VNI | flow | 180 | ridge_pressure | 8826 | 276.1986 | 340.5368 | -12.7799 | 285.3144 | 267.0703 |
| VNI | flow | 180 | ridge_full | 8826 | 278.7179 | 344.0435 | -34.1083 | 288.4137 | 269.0088 |
| VNI | flow | 180 | boost_l1_base | 8826 | 253.7697 | 329.3373 | -25.5152 | 256.9514 | 250.5837 |
| VNI | flow | 180 | boost_l1_full | 8826 | 253.9124 | 329.2883 | -20.3970 | 255.7670 | 252.0552 |
| VNI | flow | 180 | boost_l2_full | 8826 | 257.1998 | 331.2614 | -31.4256 | 257.9008 | 256.4978 |
| VNI | export_tight | 180 | persistence | 8826 | 351.1355 | 492.8219 | -0.3421 | 352.3370 | 349.9324 |
| VNI | export_tight | 180 | ridge_base | 8826 | 271.7169 | 344.4055 | 13.3164 | 274.0260 | 269.4047 |
| VNI | export_tight | 180 | ridge_state | 8826 | 276.5161 | 348.8328 | 16.9898 | 275.3083 | 277.7255 |
| VNI | export_tight | 180 | ridge_pressure | 8826 | 273.5680 | 345.4062 | 17.9551 | 274.0861 | 273.0492 |
| VNI | export_tight | 180 | ridge_full | 8826 | 276.6299 | 349.0065 | 17.3777 | 275.4792 | 277.7820 |
| VNI | export_tight | 180 | boost_l1_base | 8826 | 246.8880 | 329.3969 | 38.5283 | 233.0956 | 260.6991 |
| VNI | export_tight | 180 | boost_l1_full | 8826 | 250.0354 | 333.5252 | 59.9893 | 239.0347 | 261.0511 |
| VNI | export_tight | 180 | boost_l2_full | 8826 | 254.6767 | 337.2582 | 26.0918 | 247.9291 | 261.4335 |
| VNI | import_tight | 180 | persistence | 8826 | 233.2976 | 351.5904 | 0.2278 | 204.1692 | 262.4656 |
| VNI | import_tight | 180 | ridge_base | 8826 | 215.8341 | 293.9872 | -48.3774 | 194.9782 | 236.7184 |
| VNI | import_tight | 180 | ridge_state | 8826 | 225.3537 | 298.3344 | -76.8832 | 201.2427 | 249.4974 |
| VNI | import_tight | 180 | ridge_pressure | 8826 | 217.0437 | 295.5661 | -51.0881 | 196.1764 | 237.9394 |
| VNI | import_tight | 180 | ridge_full | 8826 | 230.0650 | 302.5473 | -87.7381 | 206.3425 | 253.8199 |
| VNI | import_tight | 180 | boost_l1_base | 8826 | 200.8672 | 289.9526 | -7.8642 | 168.7252 | 233.0530 |
| VNI | import_tight | 180 | boost_l1_full | 8826 | 201.2949 | 288.6396 | -27.5359 | 172.4606 | 230.1685 |
| VNI | import_tight | 180 | boost_l2_full | 8826 | 222.0981 | 299.4319 | -77.0107 | 200.6751 | 243.5502 |
| VNI | flow | 1440 | persistence | 8784 | 377.3347 | 489.9916 | 3.8533 | 372.5968 | 382.1246 |
| VNI | flow | 1440 | ridge_base | 8784 | 332.0478 | 405.2785 | -19.9082 | 321.6327 | 342.5773 |
| VNI | flow | 1440 | ridge_state | 8784 | 340.3967 | 415.8874 | -44.9615 | 331.5923 | 349.2978 |
| VNI | flow | 1440 | ridge_pressure | 8784 | 332.3201 | 406.0287 | -18.3027 | 321.1806 | 343.5819 |
| VNI | flow | 1440 | ridge_full | 8784 | 341.3433 | 417.5028 | -49.2370 | 331.9634 | 350.8264 |
| VNI | flow | 1440 | boost_l1_base | 8784 | 340.0298 | 419.3290 | -29.7475 | 326.7294 | 353.4764 |
| VNI | flow | 1440 | boost_l1_full | 8784 | 341.9872 | 426.4691 | -92.9265 | 332.7951 | 351.2804 |
| VNI | flow | 1440 | boost_l2_full | 8784 | 356.0472 | 436.6515 | -121.9191 | 337.8636 | 374.4305 |
| VNI | export_tight | 1440 | persistence | 8784 | 281.1089 | 381.1926 | 0.8224 | 261.2161 | 301.2204 |
| VNI | export_tight | 1440 | ridge_base | 8784 | 249.2648 | 321.9317 | 16.5826 | 238.3707 | 260.2786 |
| VNI | export_tight | 1440 | ridge_state | 8784 | 255.0623 | 326.6830 | 16.0280 | 247.8179 | 262.3864 |
| VNI | export_tight | 1440 | ridge_pressure | 8784 | 249.3352 | 321.8705 | 16.0774 | 238.5257 | 260.2635 |
| VNI | export_tight | 1440 | ridge_full | 8784 | 255.6470 | 327.1143 | 12.2019 | 248.6728 | 262.6978 |
| VNI | export_tight | 1440 | boost_l1_base | 8784 | 257.7983 | 337.8393 | 59.9466 | 245.6292 | 270.1011 |
| VNI | export_tight | 1440 | boost_l1_full | 8784 | 265.6266 | 349.2831 | 86.7372 | 264.3834 | 266.8835 |
| VNI | export_tight | 1440 | boost_l2_full | 8784 | 264.6405 | 343.7408 | 53.0629 | 262.2734 | 267.0336 |
| VNI | import_tight | 1440 | persistence | 8784 | 244.3027 | 358.9214 | 0.1017 | 208.9941 | 279.9993 |
| VNI | import_tight | 1440 | ridge_base | 8784 | 218.7551 | 297.3329 | -50.6680 | 200.9177 | 236.7884 |
| VNI | import_tight | 1440 | ridge_state | 8784 | 217.8406 | 298.3836 | -42.4311 | 192.4263 | 243.5342 |
| VNI | import_tight | 1440 | ridge_pressure | 8784 | 218.9039 | 299.3079 | -49.2004 | 200.2305 | 237.7825 |
| VNI | import_tight | 1440 | ridge_full | 8784 | 216.5694 | 299.0942 | -35.2784 | 190.5987 | 242.8255 |
| VNI | import_tight | 1440 | boost_l1_base | 8784 | 208.8322 | 296.2532 | -4.4548 | 183.7660 | 234.1738 |
| VNI | import_tight | 1440 | boost_l1_full | 8784 | 207.0468 | 295.1078 | -0.8414 | 182.3260 | 232.0393 |
| VNI | import_tight | 1440 | boost_l2_full | 8784 | 220.7533 | 302.1130 | -48.8505 | 194.0983 | 247.7012 |
| QNI | flow | 30 | persistence | 8831 | 115.2887 | 167.0135 | 0.2080 | 108.5274 | 122.0515 |
| QNI | flow | 30 | ridge_base | 8831 | 117.4117 | 162.2504 | 10.3128 | 111.9315 | 122.8931 |
| QNI | flow | 30 | ridge_state | 8831 | 116.6482 | 161.1668 | 0.8678 | 111.1104 | 122.1872 |
| QNI | flow | 30 | ridge_pressure | 8831 | 117.4399 | 162.3029 | 9.5560 | 111.9080 | 122.9732 |
| QNI | flow | 30 | ridge_full | 8831 | 116.7886 | 161.2695 | -0.6606 | 111.1960 | 122.3825 |
| QNI | flow | 30 | boost_l1_base | 8831 | 113.2686 | 158.1143 | 6.5374 | 106.9966 | 119.5419 |
| QNI | flow | 30 | boost_l1_full | 8831 | 112.2667 | 156.8579 | 4.7424 | 106.4660 | 118.0687 |
| QNI | flow | 30 | boost_l2_full | 8831 | 113.6160 | 155.9866 | 2.1341 | 107.3795 | 119.8539 |
| QNI | export_tight | 30 | persistence | 8831 | 62.7511 | 124.9644 | -0.0165 | 50.2682 | 75.2368 |
| QNI | export_tight | 30 | ridge_base | 8831 | 79.1992 | 124.8601 | 15.8279 | 75.3241 | 83.0751 |
| QNI | export_tight | 30 | ridge_state | 8831 | 72.7139 | 121.0437 | 13.3263 | 65.2898 | 80.1397 |
| QNI | export_tight | 30 | ridge_pressure | 8831 | 76.2286 | 123.1332 | 11.3316 | 71.1276 | 81.3307 |
| QNI | export_tight | 30 | ridge_full | 8831 | 70.8761 | 120.1281 | 9.1836 | 62.6746 | 79.0795 |
| QNI | export_tight | 30 | boost_l1_base | 8831 | 62.5222 | 118.4614 | 12.3852 | 53.2464 | 71.8002 |
| QNI | export_tight | 30 | boost_l1_full | 8831 | 60.2340 | 118.2855 | 9.9823 | 50.1504 | 70.3199 |
| QNI | export_tight | 30 | boost_l2_full | 8831 | 67.3405 | 116.7294 | 5.9870 | 61.1647 | 73.5177 |
| QNI | import_tight | 30 | persistence | 8831 | 68.0066 | 116.0884 | -0.0338 | 75.8878 | 60.1236 |
| QNI | import_tight | 30 | ridge_base | 8831 | 76.6890 | 114.8202 | 14.2026 | 87.4731 | 65.9024 |
| QNI | import_tight | 30 | ridge_state | 8831 | 73.2124 | 110.1988 | -0.5981 | 82.6639 | 63.7588 |
| QNI | import_tight | 30 | ridge_pressure | 8831 | 75.2331 | 113.4659 | 11.4954 | 85.6644 | 64.7995 |
| QNI | import_tight | 30 | ridge_full | 8831 | 72.5896 | 109.7384 | -1.5270 | 82.0674 | 63.1096 |
| QNI | import_tight | 30 | boost_l1_base | 8831 | 67.2820 | 111.0200 | 6.9943 | 76.3016 | 58.2603 |
| QNI | import_tight | 30 | boost_l1_full | 8831 | 65.7739 | 110.1693 | 2.2489 | 74.3023 | 57.2436 |
| QNI | import_tight | 30 | boost_l2_full | 8831 | 87.9965 | 131.7850 | 18.1244 | 103.6709 | 72.3185 |
| QNI | flow | 180 | persistence | 8826 | 211.8380 | 290.7721 | 0.7689 | 199.5601 | 224.1326 |
| QNI | flow | 180 | ridge_base | 8826 | 219.0993 | 277.7489 | 52.9254 | 211.7574 | 226.4512 |
| QNI | flow | 180 | ridge_state | 8826 | 220.5401 | 279.0170 | 62.1876 | 214.5178 | 226.5706 |
| QNI | flow | 180 | ridge_pressure | 8826 | 219.2390 | 278.0598 | 50.2393 | 211.9472 | 226.5408 |
| QNI | flow | 180 | ridge_full | 8826 | 219.8993 | 278.5323 | 56.6357 | 214.1026 | 225.7040 |
| QNI | flow | 180 | boost_l1_base | 8826 | 212.1230 | 277.1336 | 25.0163 | 195.0600 | 229.2093 |
| QNI | flow | 180 | boost_l1_full | 8826 | 210.5661 | 273.3029 | 26.7814 | 197.7037 | 223.4459 |
| QNI | flow | 180 | boost_l2_full | 8826 | 214.7486 | 274.6439 | 49.1396 | 204.6857 | 224.8252 |
| QNI | export_tight | 180 | persistence | 8826 | 133.2221 | 217.8516 | -0.0574 | 115.2582 | 151.2105 |
| QNI | export_tight | 180 | ridge_base | 8826 | 158.7250 | 209.7944 | 39.3353 | 158.7622 | 158.6877 |
| QNI | export_tight | 180 | ridge_state | 8826 | 148.5466 | 202.1579 | 36.5579 | 143.7886 | 153.3110 |
| QNI | export_tight | 180 | ridge_pressure | 8826 | 152.7197 | 205.8531 | 29.8170 | 149.4644 | 155.9793 |
| QNI | export_tight | 180 | ridge_full | 8826 | 146.0693 | 200.7717 | 29.9711 | 139.5009 | 152.6466 |
| QNI | export_tight | 180 | boost_l1_base | 8826 | 145.4319 | 204.1523 | 69.1276 | 147.6724 | 143.1884 |
| QNI | export_tight | 180 | boost_l1_full | 8826 | 139.6678 | 202.6150 | 63.3478 | 138.9787 | 140.3577 |
| QNI | export_tight | 180 | boost_l2_full | 8826 | 155.6200 | 207.7388 | 46.1460 | 156.6769 | 154.5616 |
| QNI | import_tight | 180 | persistence | 8826 | 132.9465 | 201.2179 | -0.1185 | 148.4234 | 117.4486 |
| QNI | import_tight | 180 | ridge_base | 8826 | 148.7343 | 198.8612 | 54.6800 | 176.6759 | 120.7548 |
| QNI | import_tight | 180 | ridge_state | 8826 | 146.2597 | 196.4929 | 62.7804 | 172.3831 | 120.1008 |
| QNI | import_tight | 180 | ridge_pressure | 8826 | 143.7537 | 193.1846 | 45.7684 | 170.1447 | 117.3268 |
| QNI | import_tight | 180 | ridge_full | 8826 | 143.9191 | 193.8726 | 59.2461 | 169.1035 | 118.7005 |
| QNI | import_tight | 180 | boost_l1_base | 8826 | 153.9396 | 224.3318 | 82.9659 | 193.3912 | 114.4344 |
| QNI | import_tight | 180 | boost_l1_full | 8826 | 133.8758 | 195.3569 | 54.2646 | 165.0579 | 102.6512 |
| QNI | import_tight | 180 | boost_l2_full | 8826 | 159.6218 | 241.1689 | 70.2421 | 200.3482 | 118.8401 |
| QNI | flow | 1440 | persistence | 8784 | 271.5475 | 364.3705 | 3.6092 | 269.4043 | 273.7142 |
| QNI | flow | 1440 | ridge_base | 8784 | 247.6914 | 315.6057 | 26.0925 | 242.1381 | 253.3057 |
| QNI | flow | 1440 | ridge_state | 8784 | 246.7317 | 315.0424 | 20.4462 | 243.3557 | 250.1449 |
| QNI | flow | 1440 | ridge_pressure | 8784 | 247.7435 | 315.7974 | 24.6843 | 242.0525 | 253.4970 |
| QNI | flow | 1440 | ridge_full | 8784 | 246.4789 | 315.1135 | 15.5912 | 242.9466 | 250.0501 |
| QNI | flow | 1440 | boost_l1_base | 8784 | 249.8766 | 320.6256 | 5.6556 | 247.2111 | 252.5713 |
| QNI | flow | 1440 | boost_l1_full | 8784 | 247.3361 | 319.3993 | -4.2774 | 247.0799 | 247.5951 |
| QNI | flow | 1440 | boost_l2_full | 8784 | 249.5930 | 316.8574 | 9.8129 | 248.0780 | 251.1247 |
| QNI | export_tight | 1440 | persistence | 8784 | 173.6716 | 274.3471 | 0.2825 | 176.5990 | 170.7120 |
| QNI | export_tight | 1440 | ridge_base | 8784 | 197.9389 | 254.0960 | 50.9611 | 220.1955 | 175.4377 |
| QNI | export_tight | 1440 | ridge_state | 8784 | 191.8361 | 250.8463 | 56.7646 | 214.0400 | 169.3881 |
| QNI | export_tight | 1440 | ridge_pressure | 8784 | 190.4376 | 249.0280 | 41.6696 | 209.2452 | 171.4234 |
| QNI | export_tight | 1440 | ridge_full | 8784 | 188.5858 | 247.8292 | 45.5087 | 208.0275 | 168.9305 |
| QNI | export_tight | 1440 | boost_l1_base | 8784 | 184.6712 | 254.7723 | 69.6407 | 207.4952 | 161.5964 |
| QNI | export_tight | 1440 | boost_l1_full | 8784 | 184.9431 | 254.1294 | 75.8856 | 208.4264 | 161.2018 |
| QNI | export_tight | 1440 | boost_l2_full | 8784 | 209.3881 | 266.4220 | 86.4217 | 238.9574 | 179.4938 |
| QNI | import_tight | 1440 | persistence | 8784 | 187.7241 | 290.4422 | -0.9755 | 229.7917 | 145.1943 |
| QNI | import_tight | 1440 | ridge_base | 8784 | 192.3097 | 274.1957 | 69.0842 | 237.8857 | 146.2328 |
| QNI | import_tight | 1440 | ridge_state | 8784 | 193.5418 | 276.4301 | 80.8541 | 241.8209 | 144.7321 |
| QNI | import_tight | 1440 | ridge_pressure | 8784 | 190.7507 | 272.6659 | 64.8360 | 235.5538 | 145.4553 |
| QNI | import_tight | 1440 | ridge_full | 8784 | 192.9404 | 276.3490 | 82.3062 | 240.7460 | 144.6095 |
| QNI | import_tight | 1440 | boost_l1_base | 8784 | 188.4752 | 277.4840 | 72.0399 | 233.6359 | 142.8182 |
| QNI | import_tight | 1440 | boost_l1_full | 8784 | 186.1093 | 275.6570 | 63.6367 | 230.1719 | 141.5624 |
| QNI | import_tight | 1440 | boost_l2_full | 8784 | 232.4421 | 321.6546 | 133.1902 | 296.1510 | 168.0331 |

<!-- END_ALL_REGRESSION -->

### All event probability scores

<!-- ALL_EVENTS -->

| ic | direction | model | n | positives | base_rate | brier | log_loss | average_precision | threshold | tp | fp | fn | recall | precision | false_positive_rate | false_positive_origins_per_day |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VNI | export | climatology | 8830 | 1505 | 0.1704 | 0.1414 | 0.4568 | 0.1704 | 0.1636 | 0 | 0 | 1505 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| VNI | export | logistic_base | 8830 | 1505 | 0.1704 | 0.1372 | 0.4419 | 0.3015 | 0.1879 | 314 | 717 | 1191 | 0.2086 | 0.3046 | 0.0979 | 3.8967 |
| VNI | export | boost_base | 8830 | 1505 | 0.1704 | 0.1303 | 0.4190 | 0.3750 | 0.2451 | 341 | 410 | 1164 | 0.2266 | 0.4541 | 0.0560 | 2.2283 |
| VNI | export | logistic_full | 8830 | 1505 | 0.1704 | 0.1331 | 0.4303 | 0.3611 | 0.2308 | 273 | 320 | 1232 | 0.1814 | 0.4604 | 0.0437 | 1.7391 |
| VNI | export | boost_full | 8830 | 1505 | 0.1704 | 0.1311 | 0.4235 | 0.3789 | 0.2641 | 243 | 262 | 1262 | 0.1615 | 0.4812 | 0.0358 | 1.4239 |
| VNI | import | climatology | 8830 | 848 | 0.0960 | 0.0892 | 0.3269 | 0.0960 | 0.1447 | 0 | 0 | 848 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| VNI | import | logistic_base | 8830 | 848 | 0.0960 | 0.0892 | 0.3226 | 0.2232 | 0.2462 | 356 | 1520 | 492 | 0.4198 | 0.1898 | 0.1904 | 8.2609 |
| VNI | import | boost_base | 8830 | 848 | 0.0960 | 0.0860 | 0.3085 | 0.2674 | 0.3113 | 247 | 614 | 601 | 0.2913 | 0.2869 | 0.0769 | 3.3370 |
| VNI | import | logistic_full | 8830 | 848 | 0.0960 | 0.0858 | 0.3106 | 0.2468 | 0.2675 | 257 | 867 | 591 | 0.3031 | 0.2286 | 0.1086 | 4.7120 |
| VNI | import | boost_full | 8830 | 848 | 0.0960 | 0.0835 | 0.2956 | 0.2873 | 0.3554 | 255 | 491 | 593 | 0.3007 | 0.3418 | 0.0615 | 2.6685 |
| QNI | export | climatology | 8830 | 1097 | 0.1242 | 0.1089 | 0.3756 | 0.1242 | 0.1330 | 0 | 0 | 1097 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| QNI | export | logistic_base | 8830 | 1097 | 0.1242 | 0.1101 | 0.3699 | 0.1884 | 0.2972 | 257 | 1009 | 840 | 0.2343 | 0.2030 | 0.1305 | 5.4837 |
| QNI | export | boost_base | 8830 | 1097 | 0.1242 | 0.1027 | 0.3538 | 0.2915 | 0.3463 | 368 | 727 | 729 | 0.3355 | 0.3361 | 0.0940 | 3.9511 |
| QNI | export | logistic_full | 8830 | 1097 | 0.1242 | 0.1059 | 0.3599 | 0.2192 | 0.3082 | 167 | 505 | 930 | 0.1522 | 0.2485 | 0.0653 | 2.7446 |
| QNI | export | boost_full | 8830 | 1097 | 0.1242 | 0.1060 | 0.3583 | 0.3072 | 0.3575 | 430 | 844 | 667 | 0.3920 | 0.3375 | 0.1091 | 4.5870 |
| QNI | import | climatology | 8830 | 2625 | 0.2973 | 0.2232 | 0.6510 | 0.2973 | 0.1778 | 0 | 0 | 2625 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| QNI | import | logistic_base | 8830 | 2625 | 0.2973 | 0.1971 | 0.5851 | 0.4570 | 0.3416 | 886 | 831 | 1739 | 0.3375 | 0.5160 | 0.1339 | 4.5163 |
| QNI | import | boost_base | 8830 | 2625 | 0.2973 | 0.2059 | 0.6302 | 0.4390 | 0.3923 | 360 | 343 | 2265 | 0.1371 | 0.5121 | 0.0553 | 1.8641 |
| QNI | import | logistic_full | 8830 | 2625 | 0.2973 | 0.1949 | 0.5777 | 0.4727 | 0.3456 | 877 | 827 | 1748 | 0.3341 | 0.5147 | 0.1333 | 4.4946 |
| QNI | import | boost_full | 8830 | 2625 | 0.2973 | 0.2053 | 0.6189 | 0.4551 | 0.4340 | 301 | 281 | 2324 | 0.1147 | 0.5172 | 0.0453 | 1.5272 |

<!-- END_ALL_EVENTS -->

### All monthly feature audits

<!-- ALL_QUALITY -->

| ic | month | five_minute_rows | exact_version_match_fraction | upper_coverage | lower_coverage | upper_reconstruction_mae_mw | lower_reconstruction_mae_mw | upper_setter_match_fraction | lower_setter_match_fraction |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VNI | 2024-09 | 8640 | 0.8454 | 0.9469 | 0.8775 | 167.7148 | 10.3326 | 0.8556 | 0.9624 |
| VNI | 2024-10 | 8928 | 0.9505 | 0.9999 | 0.9999 | 0.0000 | 94.2450 | 0.9517 | 0.8702 |
| VNI | 2024-11 | 8640 | 0.9486 | 0.9999 | 0.9999 | 0.0096 | 124.8088 | 0.9170 | 0.8492 |
| VNI | 2024-12 | 8928 | 0.9529 | 0.9999 | 0.9999 | 0.0000 | 99.0346 | 0.9331 | 0.8555 |
| VNI | 2025-01 | 8928 | 0.9480 | 0.9999 | 0.9999 | 0.0000 | 75.0571 | 0.9123 | 0.8936 |
| VNI | 2025-02 | 8064 | 0.9408 | 0.9999 | 0.9999 | 1.5490 | 35.5056 | 0.9056 | 0.9257 |
| VNI | 2025-03 | 8928 | 0.9437 | 0.9999 | 0.9999 | 0.0000 | 20.8556 | 0.9556 | 0.9647 |
| VNI | 2025-04 | 8640 | 0.9414 | 0.9999 | 0.9999 | 0.1354 | 17.8876 | 0.9538 | 0.9703 |
| VNI | 2025-05 | 8928 | 0.9350 | 0.9999 | 0.9999 | 0.0000 | 20.5938 | 0.9715 | 0.9611 |
| VNI | 2025-06 | 8640 | 0.9367 | 0.9999 | 0.9999 | 0.9439 | 0.1311 | 0.8494 | 0.9946 |
| VNI | 2025-07 | 8928 | 0.9431 | 0.9999 | 0.9999 | 1.8315 | 0.3684 | 0.8640 | 0.9929 |
| VNI | 2025-08 | 8928 | 0.9366 | 0.9999 | 0.9999 | 0.7659 | 2.8916 | 0.9168 | 0.9861 |
| VNI | 2025-09 | 8640 | 0.9382 | 0.9999 | 0.9999 | 0.0000 | 0.0212 | 0.9848 | 0.9914 |
| VNI | 2025-10 | 8928 | 0.9387 | 0.9999 | 0.9999 | 0.0000 | 28.4557 | 0.9803 | 0.9635 |
| VNI | 2025-11 | 8640 | 0.9446 | 0.9999 | 0.9999 | 0.0000 | 9.4537 | 0.9809 | 0.9841 |
| VNI | 2025-12 | 8928 | 0.9001 | 0.9999 | 0.9999 | 0.0000 | 0.0307 | 0.9873 | 0.9950 |
| VNI | 2026-01 | 8928 | 0.8932 | 0.9999 | 0.9999 | 0.0000 | 0.0171 | 0.9887 | 0.9952 |
| VNI | 2026-02 | 8064 | 0.8939 | 0.9999 | 0.9999 | 0.0000 | 0.0000 | 0.9883 | 0.9989 |
| VNI | 2026-03 | 8928 | 0.8901 | 0.9999 | 0.9999 | 0.0000 | 0.0000 | 0.9880 | 0.9992 |
| VNI | 2026-04 | 8640 | 0.8926 | 0.9999 | 0.9999 | 0.0000 | 0.0000 | 0.9900 | 0.9970 |
| VNI | 2026-05 | 8928 | 0.8782 | 0.9999 | 0.9999 | 0.0000 | 0.0000 | 0.9867 | 0.9998 |
| VNI | 2026-06 | 8640 | 0.8821 | 0.9999 | 0.9999 | 0.0000 | 0.0000 | 0.9830 | 0.9954 |
| VNI | 2026-07 | 8928 | 0.9038 | 0.9999 | 0.9999 | 0.0000 | 0.0000 | 0.9816 | 0.9934 |
| VNI | 2026-08 | 8928 | 0.9153 | 0.9999 | 0.9999 | 0.0000 | 0.0000 | 0.9778 | 0.8414 |
| QNI | 2024-09 | 8640 | 0.3498 | 0.9411 | 0.9426 | 732.6370 | 477.7453 | 0.0049 | 0.2154 |
| QNI | 2024-10 | 8928 | 0.3399 | 0.9999 | 0.9999 | 902.6803 | 910.5964 | 0.0081 | 0.1323 |
| QNI | 2024-11 | 8640 | 0.5040 | 0.9999 | 0.9999 | 559.7120 | 520.7206 | 0.1850 | 0.1795 |
| QNI | 2024-12 | 8928 | 0.6392 | 0.9999 | 0.9999 | 301.4803 | 220.8253 | 0.3137 | 0.4123 |
| QNI | 2025-01 | 8928 | 0.6410 | 0.9999 | 0.9999 | 473.8342 | 219.4888 | 0.0783 | 0.3150 |
| QNI | 2025-02 | 8064 | 0.7060 | 0.9999 | 0.9999 | 362.3464 | 145.3115 | 0.2115 | 0.3991 |
| QNI | 2025-03 | 8928 | 0.6890 | 0.9999 | 0.9999 | 359.5248 | 214.6600 | 0.1824 | 0.2180 |
| QNI | 2025-04 | 8640 | 0.7212 | 0.9999 | 0.9999 | 565.3472 | 95.1345 | 0.0171 | 0.3236 |
| QNI | 2025-05 | 8928 | 0.7112 | 0.9999 | 0.9999 | 797.8768 | 130.2202 | 0.0742 | 0.2672 |
| QNI | 2025-06 | 8640 | 0.7280 | 0.9999 | 0.9999 | 191.3071 | 55.9618 | 0.4418 | 0.4418 |
| QNI | 2025-07 | 8928 | 0.7408 | 0.9999 | 0.9999 | 272.3948 | 102.9147 | 0.2845 | 0.2901 |
| QNI | 2025-08 | 8928 | 0.7385 | 0.9999 | 0.9999 | 260.0689 | 74.4199 | 0.3842 | 0.5197 |
| QNI | 2025-09 | 8640 | 0.5823 | 0.9999 | 0.9999 | 761.4277 | 432.9377 | 0.1016 | 0.2416 |
| QNI | 2025-10 | 8928 | 0.5827 | 0.9999 | 0.9999 | 511.9869 | 511.9831 | 0.1118 | 0.1921 |
| QNI | 2025-11 | 8640 | 0.6727 | 0.9999 | 0.9999 | 270.2982 | 276.6127 | 0.3195 | 0.2930 |
| QNI | 2025-12 | 8928 | 0.7130 | 0.9999 | 0.9999 | 153.8013 | 46.7613 | 0.2178 | 0.6015 |
| QNI | 2026-01 | 8928 | 0.7573 | 0.9999 | 0.9999 | 52.0630 | 76.5651 | 0.3797 | 0.4865 |
| QNI | 2026-02 | 8064 | 0.7683 | 0.9999 | 0.9999 | 33.6920 | 68.4152 | 0.4764 | 0.4700 |
| QNI | 2026-03 | 8928 | 0.6142 | 0.9999 | 0.9999 | 454.3968 | 184.7687 | 0.2287 | 0.2250 |
| QNI | 2026-04 | 8640 | 0.6211 | 0.9999 | 0.9999 | 407.8432 | 232.8310 | 0.1904 | 0.2639 |
| QNI | 2026-05 | 8928 | 0.6611 | 0.9999 | 0.9999 | 339.4036 | 259.9537 | 0.1697 | 0.2648 |
| QNI | 2026-06 | 8640 | 0.6515 | 0.9999 | 0.9999 | 367.0323 | 121.9529 | 0.2596 | 0.2999 |
| QNI | 2026-07 | 8928 | 0.7792 | 0.9999 | 0.9999 | 572.1263 | 506.8830 | 0.3085 | 0.4444 |
| QNI | 2026-08 | 8928 | 0.7679 | 0.9999 | 0.9999 | 128.0182 | 65.5150 | 0.2729 | 0.4805 |

<!-- END_ALL_QUALITY -->

## Sources

Source access date is 13 September 2026 unless stated otherwise. Numbered references distinguish repository evidence, primary market documents, academic papers and operator accounts. Access level is recorded where full text was unavailable. Search-engine crawl dates are not treated as publication dates. The earlier report is preserved as [the first research edition](QNI_VNI_FORECAST_MODEL_IMPROVEMENT_PLAN.md); its untrained-boosting statement applies to that earlier experiment, not this expanded run.

<!-- SOURCES -->

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

[^28]: INTERFLOW. [Expanded model evidence](data/qni_vni_expanded_model_evidence.json), generated 13 September 2026 by [the expanded research experiment](../scripts/research_expanded_models.py). Local primary evidence: 144 regression scores, 20 event scores, 48 monthly audits, two attribution audits and 100 input hashes. Retrospective development assessment; no new market downloads.

[^29]: Daniel Hjertholm / Statnett. [Quantifying uncertainty in forecasts – methods and lessons from mFRR flow prediction](https://datascience.statnett.no/2026/03/11/quantifying-uncertainty-in-forecasts-m/), 11 March 2026. Primary transmission-operator article, full article text examined; accessed 13 September 2026. Direct balancing-flow application, not NEM validation.

[^30]: Yeesian Ng, Sidhant Misra, Line A. Roald and Scott Backhaus. [Statistical Learning For DC Optimal Power Flow](https://arxiv.org/abs/1801.07809), 23 January 2018 preprint. Primary paper examined; accessed 13 September 2026. Affine basis policies and active operating regimes in DC-OPF.

[^31]: Deepjyoti Deka and Sidhant Misra. [Learning for DC-OPF: Classifying active sets using neural nets](https://arxiv.org/abs/1902.05607), February 2019 preprint. Primary paper examined; accessed 13 September 2026. Optimisation active-set classification, not chronological interconnector forecasting.

[^32]: Luyao Liu, Feifei Bai, Chenyu Su, Cuiping Ma, Ruifeng Yan, Hailong Li, Qie Sun and Ronald Wennersten. [Forecasting the occurrence of extreme electricity prices using a multivariate logistic regression model](https://research-repository.griffith.edu.au/bitstreams/f003c844-829c-4db6-8257-47538355a229/download), Energy 247, 123417, 2022; DOI 10.1016/j.energy.2022.123417. Primary institutional accepted-manuscript abstract accessed through indexed text on 13 September 2026; direct full-text retrieval failed. Input timing and complete validation design were not independently established.

[^33]: Schäfer, Hofmann, Abdel-Khalek and Weidlich. [Principal Cross-Border Flow Patterns in the European Electricity Markets](https://arxiv.org/abs/1908.02848), August 2019 preprint. Primary paper examined; accessed 13 September 2026. Descriptive physical-flow PCA; training-only adaptation proposed here.

[^34]: Worsnop et al. [Generating wind power scenarios for probabilistic ramp event prediction](https://wes.copernicus.org/articles/3/371/2018/wes-3-371-2018.pdf), Wind Energy Science 3, 371–393, 2018. Primary full paper examined; accessed 13 September 2026. Joint scenarios and ramp-event forecasts; results depend on data and forecast setting.

[^35]: Hui Zou and Trevor Hastie. [Regularization and variable selection via the elastic net](https://web.stanford.edu/~hastie/Papers/elasticnet.pdf), Journal of the Royal Statistical Society Series B 67(2), 301–320, 2005. Author-hosted manuscript (revision August 2004) examined; accessed 13 September 2026.

[^36]: Xiaoqian Wang, Rob J. Hyndman, Feng Li and Yanfei Kang. [Forecast combinations: an over 50-year review](https://arxiv.org/abs/2205.04216), preprint 2022, International Journal of Forecasting 2023. Primary review examined; accessed 13 September 2026. Simple and estimated combinations; not a specific QNI/VNI ensemble result.

[^37]: InterpretML contributors. [Explainable Boosting Machine](https://interpret.ml/docs/ebm.html), undated official documentation, accessed 13 September 2026. Full documentation page examined. Describes additive boosted functions and selected interactions; software description, not local performance evidence.

[^38]: AEMO. [Electricity Data Model 5.3](https://tech-specs.docs.public.aemo.com.au/Content/TSP_EMMSDM53_April2024/Electricity_Data_Model_5.3.htm), April 2024, PD7DAY table definitions; and [Loading data from non-data-model tables](https://di-help.docs.public.aemo.com.au/Content/Data_Subscription/Loading_data_from_non-data_model_tables.htm), undated public documentation. Primary indexed table/field excerpts accessed 13 September 2026; some direct retrievals failed. Historical report availability still requires audit.

[^39]: AEMO. [Market notice CHG0106323, change to Extended Pre-Dispatch report to extend to seven-day period](https://www.aemo.com.au/Market-Notices?MarketNoticeList=15&fromdate=&marketNoticeFacets=VOLL%2CPOWER+SYSTEM+EVENTS%2CMPDI%2CMARKET+SYSTEMS%2CLOR1+ACTUAL%2CLOR3+ACTUAL&marketNoticeQuery=&todate=), October 2025, stated change window 23–24 October 2025. Primary indexed notice text accessed 13 September 2026. Notice-list URL is mutable; search by change number if the visible page advances.

[^40]: AEMO. [Pre-dispatch market data](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/pre-dispatch), undated public information page, accessed 13 September 2026. Primary description examined, including SNOWYP/Tumut 3 pump reporting and forecast horizons.

[^41]: AEMO. [SO_OP_3704 – Predispatch](https://www.aemo.com.au/-/media/files/electricity/nem/security_and_reliability/power_system_ops/procedures/so_op_3704-predispatch.pdf), final version 19, effective 1 April 2026. Primary current procedure examined; accessed 13 September 2026. Earlier superseded draft excluded.

[^42]: Dominik Janzing, Lenon Minorics and Patrick Bloebaum. [Feature relevance quantification in explainable AI: A causal problem](https://proceedings.mlr.press/v108/janzing20a.html), AISTATS, PMLR 108:2907–2916, 2020. Primary proceedings abstract examined; accessed 13 September 2026. Used only for the observational/interventional interpretation distinction.

[^43]: AEMO. [Constraint Formulation Guidelines](https://www.aemo.com.au/-/media/files/electricity/nem/security_and_reliability/congestion-information/2025/constraint-formulation-guidelines.pdf), effective 2 December 2025, especially section 2.6.1 and change history; [final consultation page](https://www.aemo.com.au/consultations/current-and-closed-consultations/isf-consultation-of-constraint-formulation-guidelines), 30 October 2025. Primary final document and page examined; accessed 13 September 2026. Changes minimum LHS factor threshold from 0.07 to 0.15.

[^44]: Yaniv Romano, Evan Patterson and Emmanuel J. Candès. [Conformalized Quantile Regression](https://arxiv.org/abs/1905.03222), May 2019 preprint. Primary abstract examined in this pass; accessed 13 September 2026. Candidate heteroscedastic calibration method; no claim that its finite-sample assumptions hold automatically in this application.

[^45]: Vitor Cerqueira, Luis Torgo and Igor Mozetič. [Evaluating time series forecasting models: An empirical study on performance estimation methods](https://arxiv.org/abs/1905.11744), 2019 preprint, published 2020. Primary paper examined; accessed 13 September 2026. Empirical distinction between stationary and real nonstationary evaluation settings.

[^46]: Hansika Hewamalage, Klaus Ackermann and Christoph Bergmeir. [Forecast evaluation for data scientists: common pitfalls and best practices](https://link.springer.com/article/10.1007/s10618-022-00894-5), published online 2 December 2022, Data Mining and Knowledge Discovery 37:788–832, 2023. Primary full paper examined; accessed 13 September 2026.

<!-- END_SOURCES -->
