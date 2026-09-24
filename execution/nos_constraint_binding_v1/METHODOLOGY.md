# Methodology — NOS outage constraint mechanics and forward outlook (v1)

Plan: [`PLAN.md`](PLAN.md). Execution record: [`EXECUTION_LOG.md`](EXECUTION_LOG.md) (authoritative). Base campaign: [`../nos_outage_regime_v1/METHODOLOGY.md`](../nos_outage_regime_v1/METHODOLOGY.md).

Scope: retrospective, descriptive research on realised invocations, plus a research outlook applied to NOS bookings. No forecasting model is fitted and nothing here is a deployed service. AEMO interconnector limits are dispatch-solution outputs, not maximum secure physical transfer capability.

## 1. Time, window and units

- Fixed NEM time (UTC+10), interval-ending. Window `(2024-09-01 00:00, 2026-09-01 00:00]`. Year 2 starts 2025-09-01.
- The unit of comparison is the v1 matched half-hour: a treated half-hour (all six five-minute intervals inside an invocation of the outage family, linked to a live NOS booking) paired with up to five matched control half-hours (v1 METHODOLOGY §5.2). Constraint statistics are shares of the half-hour's five-minute intervals.

## 2. Matched pairs (A1)

v1 kept only per-unit control medians. The v1 matching (`compare.run_connector`) was replayed with bootstrap intervals switched off and every `run_effect` call captured through an opt-in hook (`compare.PAIR_SINK`), for family (K2), key (K1, K1×K2, K3, K4), state and spillover runs, and for the ±7-day placebo windows. The hook does not change the matching.

**Gate:** replayed per-unit control medians (capacity, headroom, directional flow, at-limit share, control count) and key-level effects must equal v1 exactly. Result: identical for all six links (log E004).

## 3. Constraint layers

| Layer | Five-minute definition | Direction |
|---|---|---|
| Limit-setter | Equation forming the reconstructed tightest upper (forward) or lower (reverse) conditional bound, from the constraint studies' `constraint_features_5min` | upper → forward, lower → reverse |
| Binding (connector) | Equation with a term for the link, \|MARGINALVALUE\| > 1e-9 | factor sign: positive → forward, negative → reverse |
| Near-binding | Equation with a link term and IC-normalised slack `(RHS − LHS)/|factor|` in [0, 50] MW | as binding |
| Binding (system) | Any binding equation in scope, with or without a link term | both directions |

**Run selection** for DISPATCHCONSTRAINT and DISPATCHLOAD follows `nemic.constraint_features._physical`: per interval and key, the last row after sorting by INTERVENTION, RUNNO, LASTCHANGED. This is the base report's rule; the plan's "INTERVENTION = 0" wording was corrected (log E007).

**Equation scope:** union of the six connectors' dependency constraint IDs plus every member equation of a relevant outage set (52,365 equations). Factors are joined by exact version (CONSTRAINTID, EFFECTIVEDATE, VERSIONNO).

**Reconciliation gate (B2):** per connector, month and CONSTRAINTID, binding and near-binding interval counts must equal the constraint studies' `constraint_population_summary`.

## 4. Family statistics (A3, B3)

For layer L, family f, direction d, treated units T and controls C(t):

- `H[t, e]` = share of half-hour t's available intervals in which equation e is active in L.
- Treated share of e: mean over t ∈ T of `H[t, e]`. Control share: mean over t of the mean of `H[c, e]` over c ∈ C(t).
- **Own-set share:** the same with e ranging over all member equations of f (any version of the set).
- **Any-active share:** share of intervals with at least one active equation in L (used for the binding footprint).
- **Differences** are unit-level (treated − control) in percentage points; 95% intervals are day-block bootstrap intervals of the mean (1,000 replicates, NEM date of the interval).
- **Top equations:** union of the 10 largest by max(treated, control) share and the 10 largest by |difference|. The ratio treated/control is reported alongside; the difference is the headline (Q11).
- **Classes:** own set; other outage set (member of any NOS-linked set); FCAS (`F_` prefix); ramp/discretionary (`#` prefix); system-normal/other.
- **Breakdowns:** season, day period, and temperature / VRE-difference / residual-demand-difference bins (v1 P20/P80), weighted by matched units.
- **Transitions (A4):** for each run of consecutive treated half-hours, the setter at the last interval of the last untreated half-hour before the run vs the setter at the last interval of the run's first half-hour. v1's `leader_changed_share` paired every treated half-hour with one "before" value per run and was misaligned; it is corrected in `scripts/build_nos_regime_section.py`.
- **Event study (A5):** own-set share and the family's top control-side equation share from −6 h to +12 h around merged invocation spells of at least 1 h; clean spells have no other relevant family starting or ending within 2 h.
- **Placebo (A7):** the same own-set difference on the v1 ±7-day shifted windows and their matched controls; clean if the 95% interval contains zero.

## 5. Binding-specific tables

- **Layer agreement (B4):** over treated five-minute intervals, shares where the own set binds and sets the limit, binds only, sets only, neither (and the same for controls).
- **Footprint (B5):** any-binding difference on each target link-direction, for families relevant to it and for spillover runs (families relevant elsewhere, v1 spillover matching).
- **As-known split (B6):** year-2 treated half-hours split by whether a linked outage (or a predecessor it resubmits) was present in the NOS state generated 1, 7 or 14 days earlier. NOS state comes from the half-hourly report change log in the weekly archives; half-hours whose reference time precedes the first archived report are excluded.
- **Marginal value (Q10):** for own-set binding intervals, median \|MV\|, share above 100 and 1,000 $/MWh, and share above the equation's own P90 \|MV\| over binding intervals outside this family's treated half-hours. Descriptive only; never summed.
- **Generator-only equations (B0b, B7):** relevant-set members with no definition rows in the window archives were versioned earlier; their definitions are read from the monthly archives of their dispatch version dates. An equation is generator-only when no version has a term for any of the six links. Pressure per DUID is `bᵢ × (Pᵢ[t] − Pᵢ[t − 30 min])` (ENERGY connection-point factors, sign flipped for ≥ constraints), summed per half-hour; treated = family invoked, base = same-month half-hours with the family not invoked.

## 6. Evidence gates

- Family tiers are v1's (`compare.tier`). Headline results use supported families; indicative families are in downloads (Q2).
- The constraint lookup shows supported entries with at least 24 matched hours. Asset-level (K1, K1×K2) binding statements additionally need at least 30 treated five-minute intervals in which the named equation binds; otherwise the family row applies (Q8).

## 7. Outlook (D1)

For a NOS snapshot generated at `as_of`:

1. **Bookings:** live records (not withdrawn, completed or information-only; resubmitted predecessors dropped) ending after `as_of` and starting within 365 days, keyed with the v1 primary-asset rules.
2. **Family:** linked sets from the snapshot's OUTAGECONSTRAINTSET; otherwise the empirical distribution of families in past non-withdrawn episodes (ended before `as_of`) with the same asset, then substation, then area, and the same equipment type (at least two episodes; top three kept with probabilities, flagged `inferred`).
3. **Relevance** is recomputed on pre-`as_of` leading intervals and invocation shares (v1 rule).
4. **Evidence** uses v1 units and A1 pairs with treated half-hours ending at least 21 days before `as_of` (the embargo; controls lie within ±21 days). Tier inputs (episodes, hours, match rate, v1 capacity placebo on the embargoed placebo pairs) are recomputed on that subset.
5. **Prediction:** q = family probability × (1 − family withdrawal rate before `as_of`); P(equation e active) = q × treated share + (1 − q) × matched control share. Limit change is the as-of family effect conditional on invocation, also given as q × effect. The own-set rate is also re-weighted by the booking's season × day-period mix (cells with at least 20 units).
6. **Network change (Q23):** own-set equations no longer in the family's latest set version effective at `as_of` are excluded; equations re-versioned within 180 days before `as_of` are flagged.
7. **Overlaps (Q17):** bookings overlapping on the same link-direction are flagged with their IDs.

## 8. Backtest (D2)

- Origins: the first weekly NOS archive dated in each month from 2025-09 to 2026-08, taking the NOS state at the archive's last complete report.
- Truth: the booking's final record (following resubmission chains). Withdrawn bookings are scored over their booked window; others over the final window. Realised share of e = mean `H[t, e]` over the window's half-hours. Only windows ending by 2026-09-01 are scored.
- Scores by lead band (0–7, 8–30, 31–90, 91–365 days) × link-direction: Brier score of the predicted share against the realised share; reliability bins; alerts for "e active in at least 5% of the outage" with a threshold chosen on the first six origins (maximum F1) and scored on the last six (recall, precision, false alerts); MAE of the limit change against the matched realised change; top-1 / top-3 accuracy of family inference.
- Baselines: (i) the equation's season × half-hour share over all pre-`as_of` half-hours; (ii) the family's statistics from the 12 months before `as_of`.
- Skill gate (Q22): a cell is skilful when it has at least 30 scored rows and a lower Brier score than baseline (i). The live outlook shows baseline (i)'s matched normal share in cells without skill.
- Leakage confirmation (Q28): at two origins the full v1 comparison is re-run with coverage cut at `as_of` and relevance recomputed; supported family effects are compared with the embargoed estimates (agreement = either estimate inside the other's 95% interval).

## 9. Deviations from the plan

| Topic | Planned | Implemented | Log |
|---|---|---|---|
| Run selection | INTERVENTION = 0 | Base report's physical-run rule (exact reconciliation) | E007 |
| DISPATCHLOAD scope | Generator-only DUIDs | All DUIDs (MW only), because generator-only equations were only identifiable after back-filling definitions | E006 |
| Generator-only definitions | From window archives | Back-filled from archives of their version dates (B0b) | E006 |
| Pair replay | Actual pairs | Actual and ±7-day placebo pairs | E003/E004 |

## 10. Limitations

- All historical results are conditional on realised invocations; year-1 outage records are final-state only.
- The outlook assumes past outage behaviour carries forward, relies on asset history for unlinked bookings, and cannot anticipate new network configurations.
- Weather and VRE bins use the base report's full-history percentiles.
- Marginal values scale with prices and bids; they describe how hard an equation binds, not a cost.
- Generator pressure is a decomposition of an active equation, not causal attribution.
