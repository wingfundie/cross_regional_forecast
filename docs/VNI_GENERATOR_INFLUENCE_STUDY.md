# VNI generator influence study

## Research question and answer

This study asks which generators most often and most strongly moved the constraint-derived Victoria–New South Wales Interconnector (VNI) bounds during February 2026, especially when a limit contracted, flow crossed zero, or a directional capacity became negative.

The evidence supports using two compact representations together:

1. **Network-state aggregates** for the leading upper and lower constraints: bound, headroom, switch gap, net generator pressure and available relief.
2. **A small generator panel** chosen from persistent and event-specific influence: CUSF1, MURRAY, DARLSF1, AVLSF1, LIMOSF11, Walla Walla solar units, Upper Tumut and Tumut 3 are the strongest initial candidates from this month. Forced-direction periods additionally elevate Moorabool-area wind and several western Victorian wind farms.

Tumut 3 is materially important. It ranks 11th of 185 units by persistence-weighted mechanical exposure, 2nd during sharp limit contractions and 10th in forced-direction states. Its average impact is only 44th, showing why a simple average-generation or average-movement screen would miss it.

## Scope

| Item | Value |
|---|---:|
| Study period | 1–28 February 2026 |
| Resolution | 5 minutes |
| Intervals | 8,064 |
| Generators with valid sensitivities | 185 |
| Constraints that led an envelope | 37 |
| Distinct flow reversals | 348 |
| Upper limit contraction intervals / episodes | 403 / 170 |
| Lower limit contraction intervals / episodes | 397 / 138 |
| Negative export-capacity intervals / onsets | 1,670 / 151 |
| Negative import-capacity intervals / onsets | 369 / 33 |

This is a descriptive dispatch-equation study. It measures mechanical contribution under the constraint that led at each observed interval and association with observed limit and flow movement. It does not identify an independent causal effect: generators co-move, dispatch responds to prices and constraints, and the leading constraint can switch at the same time.

## Method

### Exact constraint state

Each `DISPATCHCONSTRAINT` solution is joined to the exact `GENCONID`, effective date and version in the interconnector and connection-point factor tables. The bound and unit sensitivity are

```text
bound_t = flow_t + (RHS_t − LHS_t) / a
sensitivity_i = −b_i / a
30-minute bound impact_i,t = sensitivity_i × (dispatch_i,t − dispatch_i,t−30m)
```

For the upper envelope, capacity impact equals bound impact. For the lower signed bound, import-capacity impact is the negative of bound impact. A positive tightening value always means the available capacity in that direction fell.

### Event definitions

- **Sharp contraction:** a 30-minute directional-limit fall at or above the 90th percentile of positive falls. The thresholds are 252.08 MW for export and 169.31 MW for import. Contiguous qualifying intervals form one episode.
- **Flow reversal:** one change in the last observed non-zero sign of VNI flow. Zeros are carried forward only for sign-state detection. This prevents a single crossing from being counted in six overlapping 30-minute comparisons.
- **Forced direction:** the reported directional capacity is below zero. The study records both all forced intervals and the first interval of each contiguous episode.

Rankings for contractions, reversals and forced states require at least 20 unit-event contribution rows. This removes rankings based on only a handful of coincidences.

### Ranking measures

- **Overall rank** sums absolute 30-minute bound impacts over every active leading-constraint state. The unit is MW-observations, an exposure index rather than energy.
- **Intensity rank** uses mean absolute impact when active.
- **Event ranks** use mean tightening or mean absolute impact within the declared event states.
- **Top-contributor intervals** counts intervals in which the unit had the largest non-zero absolute mechanical contribution for that direction.
- **Spearman association** checks whether the signed mechanical contribution moved with the published limit or flow. It is supporting evidence, not the ranking basis.

## Persistent mechanical influence

| Rank | DUID | Active state rows | Total exposure (MW-observations) | Mean impact | P95 impact | Largest contributor rows |
|---:|---|---:|---:|---:|---:|---:|
| 1 | CUSF1 | 3,903 | 367,031 | 94.04 MW | 367.35 MW | 1,029 |
| 2 | MURRAY | 15,090 | 352,120 | 23.33 MW | 118.25 MW | 3,666 |
| 3 | DARLSF1 | 13,401 | 279,523 | 20.86 MW | 109.40 MW | 997 |
| 4 | AVLSF1 | 3,944 | 207,250 | 52.55 MW | 222.61 MW | 340 |
| 5 | LIMOSF11 | 13,313 | 190,455 | 14.31 MW | 73.43 MW | 605 |
| 6 | WLWLSF2 | 3,941 | 169,377 | 42.98 MW | 167.71 MW | 132 |
| 7 | WLWLSF1 | 3,941 | 164,602 | 41.77 MW | 166.32 MW | 88 |
| 8 | UPPTUMUT | 8,466 | 158,585 | 18.73 MW | 98.28 MW | 1,593 |
| 9 | COLEASF1 | 13,401 | 143,791 | 10.73 MW | 52.63 MW | 256 |
| 10 | SUNRSF1 | 13,313 | 124,105 | 9.32 MW | 49.56 MW | 144 |
| 11 | TUMUT3 | 8,466 | 109,268 | 12.91 MW | 50.70 MW | 425 |
| 12 | GESF1 | 3,903 | 106,656 | 27.33 MW | 117.44 MW | 145 |

The table separates persistence from intensity. MURRAY and DARLSF1 accumulate high exposure through frequent participation. CUSF1 and AVLSF1 combine substantial frequency with larger individual movements. Tumut 3 is persistent and event-relevant even though its average interval effect is less exceptional.

## Event results

### Sharp limit contractions

| Rank | DUID | Contribution rows | Mean tightening | Tightening share |
|---:|---|---:|---:|---:|
| 1 | MORTLK11 | 22 | 150.05 MW | 36.4% |
| 2 | TUMUT3 | 363 | 126.29 MW | 30.0% |
| 3 | GPWFEST1 | 22 | 116.09 MW | 45.5% |
| 4 | GPWFEST2 | 22 | 100.68 MW | 40.9% |
| 5 | AVLSF1 | 350 | 80.96 MW | 70.3% |
| 6 | MURRAY | 660 | 66.32 MW | 46.1% |
| 7 | UPPTUMUT | 363 | 53.52 MW | 49.3% |
| 8 | KESSB1 | 99 | 52.22 MW | 26.3% |
| 9 | DUNDWF1 | 22 | 51.36 MW | 50.0% |
| 10 | DARLSF1 | 643 | 49.93 MW | 58.3% |

Tumut 3 has the strongest robust contraction result: its sample is much larger than the 22-row units above and below it. Its positive-share statistic is only 30%, while its mean tightening is 126 MW. The distribution is asymmetric: fewer, much larger tightening movements outweigh more frequent small relief movements. The appropriate feature therefore preserves signed pressure and tail magnitude rather than a binary “Tumut up means VNI down” rule.

### Flow reversals

| Rank | DUID | Contribution rows | Mean absolute impact | Alignment with 30-minute flow move |
|---:|---|---:|---:|---:|
| 1 | CUSF1 | 281 | 123.46 MW | 42.3% |
| 2 | AVLSF1 | 281 | 85.04 MW | 57.3% |
| 3 | WLWLSF2 | 281 | 56.37 MW | 51.2% |
| 4 | WLWLSF1 | 281 | 54.91 MW | 51.6% |
| 5 | DARLSF1 | 600 | 42.36 MW | 44.8% |
| 6 | HILLSTN1 | 282 | 37.98 MW | 45.4% |
| 7 | MOORAWF1 | 88 | 37.22 MW | 53.4% |
| 8 | GESF1 | 281 | 35.39 MW | 40.6% |
| 9 | BOMENSF1 | 281 | 31.28 MW | 55.5% |
| 10 | LIMOSF11 | 587 | 28.65 MW | 39.0% |

The alignment rates near 50% show that a generator's constraint-bound contribution alone does not determine actual flow direction. Regional balance, other units, losses, demand and constraint switching matter. These unit signals should condition a flow model through aggregate network state rather than directly dictate a reversal forecast.

### Forced-direction states

| Rank | DUID | Contribution rows | Mean absolute impact |
|---:|---|---:|---:|
| 1 | MOORAWF1 | 85 | 274.44 MW |
| 2 | BRYB1WF1 | 85 | 192.23 MW |
| 3 | MORTLK11 | 57 | 162.61 MW |
| 4 | STOCKYD1 | 57 | 162.20 MW |
| 5 | MRTLSWF1 | 85 | 144.82 MW |
| 6 | RYANCWF1 | 85 | 143.89 MW |
| 7 | CRWARP1 | 57 | 126.32 MW |
| 8 | BRYB2WF2 | 85 | 118.82 MW |
| 9 | CUSF1 | 1,642 | 115.95 MW |
| 10 | TUMUT3 | 506 | 115.07 MW |

Several western Victorian wind units have large conditional impacts in forced states but limited event samples. CUSF1 and Tumut 3 combine large effects with much broader exposure, making them stronger candidates for stable model features.

## Constraint regimes

The leading lower constraints were `N^^V_NIL_1` (4,128 intervals) and `N^^V_NIL_ARWBBA` (2,682). The leading upper constraints were `N^^N_NIL_WGLT` (2,442), `V::N_SMSC_V1` (2,205) and `V::N_SMSC_O1` (1,241). `N^^N_NIL_WGLT` accounts for 1,448 of the 1,670 negative export-capacity intervals, so regime identity is essential when interpreting generator effects.

The model should encode the leading constraint through a compact stable representation: hashed or grouped family ID, upper/lower switch gaps, number of near-leading candidates, and aggregate coefficient-weighted generator pressure. A full one-hot column for every constraint version would be sparse and brittle.

## Tumut 3 case study

Tumut 3 appears in 180 exact VNI-linked constraint IDs and 13 constraint versions that led an observed directional envelope during the study. Across its 8,466 active state rows:

| Measure | Tumut 3 result |
|---|---:|
| Overall persistence rank | 11 / 185 |
| Mean-intensity rank | 44 / 185 |
| Sharp-contraction rank | 2 |
| Forced-state rank | 10 |
| Reversal rank | 31 |
| Mean / P95 absolute bound impact | 12.91 / 50.70 MW |
| Largest-contributor rows | 425 |
| Limit-move Spearman association | 0.194 |
| Flow-move Spearman association | 0.117 |

The low unconditional correlations and high contraction rank are compatible. Tumut 3 matters in specific constraint regimes and tails; aggregating across all intervals dilutes that relationship and sometimes flips its sign. A compact Tumut feature should therefore be `s_TUMUT3 × ΔP_TUMUT3`, split into upper/lower tightening and relief, plus its ramp-feasible future range under the current leading constraint. Raw Tumut generation alone loses both coefficient sign and topology regime.

## Recommended forecasting feature set

The initial production candidate can remain below roughly 25 numeric variables:

| Feature block | Suggested variables |
|---|---|
| Directional envelopes | upper bound, lower bound, upper room, lower room |
| Switching risk | upper/lower switch gap, near-leading count |
| Aggregate generator pressure | upper/lower tightening, upper/lower relief, 30-minute pressure change |
| Feasible relief | upper/lower ramp-and-availability-limited relief |
| Quality/state | pressure completeness, crossed-envelope flag, compact constraint-family encoding |
| Selected units | signed coefficient-weighted pressure for 4–8 stable units, beginning with Tumut 3, Upper Tumut, Murray, CUSF1 and Darling solar; freeze selection on training data |

For horizons beyond the latest dispatch interval, replace realised `ΔP` with a dispatch or availability scenario. Produce a base, upward-ramp and downward-ramp pressure path. The resulting envelope range can enter the limit model directly and can gate the flow model when a direction approaches zero.

## Testing path

1. Build three to six additional non-contiguous months chosen for seasonal and outage-regime coverage. Generate a manifest from observed required versions and download only each month’s two interval tables plus missing small standing-data vintages.
2. Freeze unit selection using training months. Require persistence across months and event samples, not a high score in one month.
3. Run ablations: baseline; envelope only; aggregate pressure; selected units; flexibility; full compact set.
4. Use expanding chronological folds and compare against persistence and the existing flow/limit model. Report MAE, tail MAE, sign accuracy, reversal precision/recall, negative-limit onset detection and calibration.
5. Audit publication times and recompute every feature from data available at each origin. The current retrospective `LHS` reconstruction validates the topology and labels; future features must use lagged state plus forecast/scenario dispatch.
6. Hold out the last period once. Do not use it to choose units, thresholds, models or hyperparameters.

## Limitations

- February 2026 is one month and may over-represent its particular outages and constraint invocations.
- Coefficient-based impact is a local mechanical decomposition under the observed leading equation. It does not simulate redispatch, constraint switching or AC power flow after a counterfactual generator change.
- Thirty-minute dispatch changes overlap across adjacent five-minute rows. Overall exposure is an index of repeated observed state, not MWh or an additive physical quantity.
- Event ranks describe conditional magnitude and require at least 20 contribution rows, but some still have limited independent episodes.
- Flow response is endogenous to regional balance and dispatch. Low unit-flow correlations should not be interpreted as evidence that the equation coefficients are wrong.
- The one-month forecast comparison was used during development and must be confirmed prospectively.

## Reproducible outputs

`python run_constraint_pilot.py` produces the ignored local artifacts below:

- `constraint_features_5min.parquet` and `constraint_features_30min.parquet`;
- `unit_sensitivities.parquet` and `unit_movements.parquet`;
- `generator_influence.csv` and `constraint_influence.csv`;
- `influence_events.parquet`, `feature_audit.json`, `influence_summary.json` and `pilot_scores.json`.

The tracked code, configuration and documentation are sufficient to reproduce the study without committing source data or derived interval records to Git.
