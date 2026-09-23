# Research design — interconnector limits and flow under NOS outage regimes

Status: **superseded design history** (2026-09-24). The active plan, methodology and execution log are in [`execution/nos_outage_regime_v1/`](../execution/nos_outage_regime_v1/PLAN.md). Where this file conflicts with them, they win.

## Decisions log

| # | Decision | Settled answer |
|---|---|---|
| G1 | Product | Both: pooled regime analysis as the backbone, plus a support-gated "given outage X" lookup |
| G2 | Connectors | All six |
| G3 | Window | 24 months, `(2024-09-01, 2026-09-01]`. Sep 2024–Aug 2025 outages come from MMSDM monthly `NETWORK_OUTAGEDETAIL`/`OUTAGECONSTRAINTSET` (final state only). Sep 2025–Aug 2026 comes from the weekly NOS snapshots already recovered |
| G4 | Home | A new outage-regime section inside `reports/all_interconnector_regime_research_20260921` |
| G5 | Purpose | Knowledge only. Retrospective analysis, so realised outage times and invocations may be used freely. No forecast-feature work |

Where §2–§10 below conflict with this log, the log wins. §2's 12-month window is superseded by G3. RQ7 (booking reliability) and the §10 questions are being revisited in round 2.

It extends
`reports/all_interconnector_regime_research_20260921/` (the "regime report") with an
outage dimension, reusing its definitions wherever possible so results are directly comparable.

## 1. What the regime report did, and what this adds

The regime report characterises the six interconnectors descriptively, with no fitted
models:

| Layer | Regime report definition | Reuse here |
|---|---|---|
| Time | Fixed UTC+10, interval-ending, 5-min native, complete half-hour = 6 distinct intervals | Identical |
| Seasons | Australian three-month blocks (Dec→next summer) | Identical, but only one block of each season exists in the NOS window |
| Limits | `forward_capacity = upper_bound`, `reverse_capacity = -lower_bound`, headroom, negative = forced direction, restricted = <50% of connector-direction-season median positive capacity | Identical. The restricted threshold stays fitted on the regime report's full 2023–2026 history so it does not absorb the outage effect |
| Context regimes | Temperature, VRE, residual demand P20/P80 within connector and season | Identical bins, crossed with outage state |
| Day periods | Overnight 21:00–05:59, morning 06:00–08:59, solar 09:00–15:59, evening 16:00–20:59 | Identical |
| Constraints | Reconstructed envelope `flow + (RHS − LHS)/a`, leader vs published setter kept separate, DUID pressure `sᵢ·ΔPᵢ` | Identical, adding a flag for whether the leading equation belongs to an outage-invoked set |

**New:** an *outage state* for every connector-direction and 5-minute interval, plus comparisons
that separate an outage's effect from the season, time-of-day and weather it happens to
coincide with. Outages are planned into shoulder seasons and low-demand hours, so comparing
raw "outage vs no outage" averages would mostly measure *when* outages are scheduled.

## 2. Data available now (no new downloads needed for the core study)

| Source | Local location | Coverage | Notes |
|---|---|---|---|
| NOS snapshots (OUTAGEDETAIL, OUTAGECONSTRAINTSET) | `data/forecast_experiments/{qni,vni}_diurnal_nos_v2/nos/weeks/` (53 weeks, parsed losslessly) | 17,800 snapshots, 2025-08-29 → 2026-09-04 | Parsed rows cover **all NEM outages**, not only QNI/VNI. The two runs hold the same raw weeks. Receipt time is not verified; generation time is known |
| Existing NOS exposure/episodes | same folders: `exposure.parquet`, `episode_revisions.parquet`, `raw_episode_effects.parquet` | QNI 2,589 / VNI 1,816 episode-asset rows | Filtered to QNI/VNI-mapped sets only |
| Constraint-set invocation (actual) | `data/constraint_*_2y/standing/GENCONSETINVOKE.parquet`, all six connectors | Two-year constraint window | Records when a set was *actually invoked*, including `SYSTEMNORMAL` and `INTERVENTION` flags. This is the realised counterpart to NOS bookings |
| Set→equation→interconnector mapping | `standing/GENCONSET`, `GENCONDATA`, `SPDINTERCONNECTORCONSTRAINT` for all six | Versioned | `nos_analysis.MappingHistory` already resolves effective versions |
| Reconstructed envelopes, leaders, DUID pressure | `data/constraint_*_2y/months/YYYY-MM/` | 2024-09 → 2026-08, all six complete | `constraint_features_5min.parquet` has `upper_constraint`/`lower_constraint` leaders |
| Flow/limits, regional demand/VRE, weather | `data/processed/{targets,regional_30min,weather_30min}.parquet` | to 2026-09-01 | Same inputs and hashes as the regime report |

**Study window:** `(2025-09-01 00:00, 2026-09-01 00:00]`, the intersection of all sources.
This gives 12 months and exactly one complete block for each Australian season. NOS
snapshots from 29–31 August 2025 are used only as prior state, so bookings open on 1 September
are already known.

**Evidence from the earlier NOS campaigns:** VNI has 422 raw episodes and 1,638 direction-asset
records, described as "descriptive only; concurrent outages, operating state and matched-control
balance not yet resolved". QNI has 560 bookings, 18 matched direction episodes and **0 supported
recurring entities**. Individual assets therefore usually lack enough repeats for per-asset
conclusions. The design pools outages by class and reports individual assets only when they
pass the support gate.

## 3. Defining an "outage regime"

### 3.1 Three evidence layers, kept separate

1. **Booked**: an NOS OUTAGEDETAIL record with a non-withdrawn status whose OUTAGECONSTRAINTSET
   links to a set mapped to the connector. The window comes from `ACTUAL_STARTTIME/ACTUAL_ENDTIME`
   where reported, and otherwise from the latest pre-interval `STARTTIME/ENDTIME` (flagged
   `window_source = scheduled`).
2. **Invoked**: a linked GENCONSETID is active in GENCONSETINVOKE for the interval. This is the
   strongest evidence that the network actually ran in the outage configuration.
3. **Leading/binding**: an equation from an invoked outage set is the reconstructed envelope
   leader, or is published as binding (marginal value > 1e-9).

Each connector-direction and 5-minute interval then gets one **outage state**:

| State | Meaning |
|---|---|
| `clear` | No booked, invoked or leading outage set mapped to this connector. This is the baseline |
| `booked_only` | Booked, but no linked set invoked. Captures withdrawn or unused bookings and mapping gaps |
| `invoked_nonleading` | Outage set invoked, but a different equation sets the limit |
| `invoked_leading` | An outage-set equation is the reconstructed leader for this direction |
| `invoked_unbooked` | Non-system-normal set invoked with no matching NOS booking. Likely forced or short-notice outages or network reconfiguration |
| `unknown` | Mapping or source gap. Never merged into `clear` |

This separates two questions. **"Did the outage exist?"** is answered by the booked and invoked
layers. **"Did it constrain the connector?"** is answered by the leading layer. Every metric is
reported for each state.

### 3.2 Outage taxonomy (grouping variables)

- **Equipment class:** LINE, CB, BUS, TRANS, reactive plant (REAC/REACT/CAP/SVC), other. In
  current episodes LINE and CB dominate, for example 999 LINE and 430 CB at VNI.
- **Location:** endpoint region, and the substation and its adjacency to the connector
  (substation list per connector, curated once and versioned).
- **Mechanism:** thermal, stability or voltage from the set equations' LIMITTYPE (already
  derived in `MappingHistory`).
- **Direction affected:** upper, lower or both, from the factor sign and inequality.
- **Planning horizon:** booking age at start (<24 h, 1–7 d, >7 d), and whether the outage was
  resubmitted or had its start shifted.
- **Duration:** under 12 h, 12 h to 3 d, over 3 d. Also continuous versus daily (return-to-service
  each night; inferred from invocation gaps and recall times).
- **Concurrency:** single mapped outage versus two or more at once, and the number of
  simultaneously invoked sets.
- **Primary vs secondary** (`ISSECONDARY`).

## 4. Research questions

| # | Question | Main output |
|---|---|---|
| Q1 | How much does each outage class shift forward/reverse capacity, headroom, restricted share and forced-direction share, **relative to matched outage-free conditions**? | Matched-difference table by connector × direction × class, with block-bootstrap CIs |
| Q2 | Does the outage effect depend on time of day and season? (e.g. thermal outages bite hardest in the summer evening peak) | Outage-state diurnal profiles over the four day periods; season × class matrix |
| Q3 | Does the effect grow with temperature, VRE or residual demand? | The regime report's P20/P80 bins crossed with outage state, showing the difference in the difference |
| Q4 | When the limit falls, does flow drop too, or does the connector just run at the limit more often? | Flow change vs capacity change; share at limit (headroom < 5% of capacity or < 10 MW); tight-interval (min-of-six) comparison |
| Q5 | Which equations and DUIDs set the envelope during outages, and whom do they displace? | Leader-transition tables (normal leader → outage leader), DUID pressure ranking in outage vs clear state |
| Q6 | Do outages mapped to one connector change the limits or flow of the others? (e.g. VNI outage → Heywood/Murraylink/QNI) | 6×6 spillover matrix of matched capacity/flow differences |
| Q7 | How reliable are bookings as a forward signal? | Booked → invoked conversion rate; start/end shift distributions; withdrawal rate; share of `invoked_unbooked` time |
| Q8 | Do limits restore symmetrically at outage end, and how quickly? | Start- and end-aligned event-study curves |

Q7 is the bridge to forecasting. It measures what a model with issue-time NOS features could
realistically know ahead of time, without fitting any model.

## 5. Comparison methods

All methods are descriptive or matched comparisons. Consistent with the regime report, no
regressions or model-derived effects are fitted.

### 5.1 Descriptive layer (same style as the regime report)
Distributions (P10/P50/P90), shares and diurnal profiles by outage state, connector-direction,
season and day period. Sample counts are shown next to every cell.

### 5.2 Matched outage-free control (main estimate for Q1–Q4, Q6)
For each `invoked_*` half-hour, draw controls from `clear` half-hours on the same connector and
direction that match on:
- the same Australian season and half-hour of day;
- the same weekday/weekend-holiday class;
- the same temperature, VRE and residual-demand tercile (regime report's P20/P80 bins);
- within ±21 days, to limit drift in plant mix and network state.

The estimate is the median of paired differences, with confidence intervals from a **day-block
bootstrap** because intervals within a day are strongly autocorrelated. Balance diagnostics
(standardised mean differences of the matching variables before and after matching) are
published. An outage cell is **unsupported** if fewer than 60% of its half-hours find a match.

### 5.3 Event study (Q8, and a cross-check on Q1)
Curves are aligned on actual invocation start and on end, from −48 h to +48 h in 30-minute
steps. Capacity is measured against the same-time-of-day median from the 7 prior outage-free
days. Only single (non-concurrent) episodes are used. Start-aligned and end-aligned curves
should mirror each other if the outage alone explains the change.

### 5.4 Negative controls and falsification
- **Placebo starts:** shift every episode ±7 days into `clear` time. The estimated effect
  should be about zero.
- **Withdrawn/cancelled bookings** (`booked_only`): should show no capacity effect.
- **Unmapped outages** in the same region: tests whether the mapping adds information beyond
  "something is out nearby".
- **`SYSTEMNORMAL` invocations:** excluded from outage states and reported separately.

### 5.5 Support gate for naming individual assets or sets
Report an asset or set individually only if it has **≥ 5 distinct episodes, ≥ 24 invoked
hours, ≥ 60% matched support, and a placebo-clean CI**. Otherwise it contributes only to its
class. This replaces "highest-impact" rankings built from raw before/after changes, which the
earlier campaign explicitly rejected.

### 5.6 Concurrency
The primary estimates use single-outage intervals. Concurrent intervals are reported as a
separate stratum by count of simultaneous sets, and are never split between outages.

## 6. Time semantics and provenance

- All timestamps are converted to fixed NEM time. NOS generation time is retained, and the
  report states that receipt time is not verified.
- This study is **retrospective characterisation**. Invocation and actual start/end times are
  realised information and must never flow into forecast features. Q7 is the only as-of view,
  and it uses bookings as known from snapshots generated at or before `origin − 30 min`,
  matching the existing `audit_nos` assumption.
- Mapping uses versioned standing data resolved at each interval (`MappingHistory.at`),
  labelled `retrospective mapping`.
- Missing snapshots, mapping gaps and incomplete half-hours are shown as `unknown` or excluded,
  never filled with zero.
- The manifest records input hashes (NOS week manifests, standing tables, constraint months,
  processed panels) and output hashes.

## 7. Proposed outputs

Report: `reports/nos_outage_regime_research_<date>/` containing Markdown `METHODOLOGY.md`, a
self-contained offline `index.html`, `build_manifest.json` and `downloads/`.

| Download | Content |
|---|---|
| `outage_episodes.csv` | One row per OUTAGEID × connector: taxonomy, booked/actual/invoked windows, revisions, sets, mechanism, direction |
| `outage_state_coverage.csv` | Share of intervals in each state by connector, direction and season |
| `outage_regime_summary.csv` | Q1 descriptive distributions by state/class |
| `outage_matched_effects.csv` | Q1–Q4 matched differences, CIs, n, balance, support flag |
| `outage_diurnal_profiles.csv` | Q2 profiles by state × day period × season |
| `outage_weather_vre_interaction.csv` | Q3 |
| `outage_flow_response.csv` | Q4 flow vs limit response and at-limit share |
| `outage_leader_transitions.csv`, `outage_duid_pressure.csv` | Q5 |
| `outage_spillover_matrix.csv` | Q6 |
| `booking_reliability.csv` | Q7 |
| `outage_event_study.csv` | Q8 curves |
| `outage_placebo_checks.csv` | §5.4 |
| `supported_entities.csv` | Assets/sets that passed §5.5 |

Proposed report sections: executive findings → outage landscape (how often, where, which
classes, per connector) → limit effects (Q1) → timing (Q2) → weather/VRE interactions (Q3) →
flow response (Q4) → constraint and DUID mechanics (Q5) → spillover (Q6) → booking reliability
(Q7) → event studies (Q8) → falsification → per-connector stories → methodology and limitations.

## 8. Build plan

| Stage | Work | Reuse | New code |
|---|---|---|---|
| S0 | Build a connector-agnostic NOS episode table from the parsed weeks, deduplicated across the QNI and VNI copies by week manifest hash | `nos.py` parser outputs | `nemic/experiments/nos_regime/episodes.py` |
| S1 | Map sets to all six connectors (versioned), plus invocation windows from GENCONSETINVOKE | `MappingHistory` (generalised from `connectors[0]`) | `mapping.py` |
| S2 | 5-minute outage-state panel per connector-direction; join envelope leaders | constraint month features | `state.py` |
| S3 | Half-hour panel joined to the regime-report panel (flow, limits, weather, VRE, demand) | `build_all_ic_regime_report.build_panel` | factor it out into an importable module |
| S4 | Descriptive, matched, event-study and placebo tables (cached parquet, content-addressed) | — | `compare.py` |
| S5 | Report rendering from cached tables only | `report_theme` | `scripts/build_nos_outage_regime_report.py` |
| S6 | Validation: manifest hashes, offline HTML, links, desktop/mobile layout, `pytest` | existing validator | `tests/test_nos_regime_*.py` covering state precedence, the no-future-leak rule for Q7, matching determinism and the placebo pipeline |

The work is light compared with the modelling campaigns. It is mostly joins over a year of
5-minute data for six connectors (about 630k intervals each), so it should run as a single
resumable script with per-stage caches rather than a ledger campaign.

## 9. Limitations to state up front

- **One year, one of each season.** Seasonal outage effects cannot be separated from that
  particular year's network build, plant mix and weather. The ENSO context in the window is
  neutral-only.
- **Outages are not random.** Matching reduces confounding but cannot remove it, because TNSPs
  place outages where they expect them to hurt least. The estimates describe typical impact
  *as scheduled*, not the impact the outage would have at an arbitrary time.
- **AEMO limits are dispatch-solution outputs**, not secure physical transfer capability. An
  outage "effect" is the change in the dispatch envelope.
- **Mapping is retrospective.** The time AEMO actually published each set is not proven.
- **Unplanned outages** appear only as `invoked_unbooked`. Their equipment cannot be identified
  from the local data.
- **Receipt time of NOS snapshots** is assumed as generation + 30 min, not observed.

## 10. Decisions for you

1. **Scope:** all six connectors (recommended; the data is already local), or QNI/VNI first?
2. **Window:** 12 months only, or also recover NOS weeks before August 2025 to get two of each
   season? NEMWEB's `ARCHIVE/Network` currently lists only about 13 months, so earlier data
   would need a different source, possibly MMSDM monthly NETWORK_OUTAGEDETAIL.
3. **Outage definition for the main estimate:** invoked (recommended), booked, or leading?
4. **Unit of reporting:** equipment-class pooling with a support-gated asset list
   (recommended), or a per-asset catalogue with lower evidence standards?
5. **Forecasting bridge:** keep Q7 purely descriptive (recommended), or follow on with a
   versioned NOS-regime feature contract and a separately evaluated challenger?

## 11. Plan assessment (2026-09-24, after round 2 review)

The round-2 Lavish session returned only "done, end this". None of G6–G13 were submitted, so they remain open, and the recommended options are provisional defaults.

### Feasibility checks run on local data

| Check | VNI | QNI |
|---|---|---|
| NOS-linked constraint sets found in `GENCONSETINVOKE` | 90 / 90 | 98 / 98 |
| Set families with ≥5 distinct outage IDs (year 2 NOS) | 38 | 54 |
| Share of half-hours with ≥1 NOS-linked set invoked (2 years) | **79.6%** | **75.4%** |
| Median concurrently invoked sets (any, ≤60-day invocations) | 4 | 3 |
| Invocation duration P10 / P50 / P90 (h) | 0.9 / 4.0 / 57.9 | 0.7 / 1.5 / 56.4 |
| `SYSTEMNORMAL = 1` rows | 33 of 2,846 | 4 of 3,444 |

### Findings that change the design

1. **The binary baseline fails.** "Clear" (no mapped outage set invoked) is only about 20–25% of time, and that remainder is unlikely to be representative. The primary contrast should become **"set family X invoked vs not invoked", matched on the other concurrently invoked relevant sets**, not "any outage vs clear". This is also the natural unit for the G1 lookup.
2. **Mapping is too broad.** A set counts as mapped if any equation in it has a non-zero interconnector factor, so families such as `I-BURC` map to both VNI and QNI. Add a **relevance filter** before anything else: for example, the set's equations led or bound the connector's envelope in at least N intervals, or |factor| ≥ a threshold. Then re-measure the always-on share. RQ6 spillover should be defined as outages that are *not relevant* to the target connector.
3. **`SYSTEMNORMAL` cannot identify unplanned outages.** Almost every invocation is flagged non-system-normal. `invoked_unbooked` must be redefined: a relevance-filtered, outage-type set (excluding `#…_RAMP`, discretionary and long-standing `*-NIL_*` configuration sets) with no NOS link within ±1 day.
4. **Short, overlapping invocations weaken the event study.** Median invocations of 1.5–4 h with 3–4 sets active at once leave few isolated "single episode" windows. Use invocation-level alignment, with overlapping activity as a covariate, and accept a smaller supported set.
5. **Lookup support is better than feared, but provisional.** The 38 and 54 families with ≥5 outage IDs overstate true repeats, because resubmitted outages count twice. Count distinct invocation episodes instead.
6. **Year-1 NOS is final-state only, and the existing episode tables are QNI/VNI-filtered.** S0 needs a new NEM-wide extraction plus the MMSDM download.

### Recommended change to the build plan

Insert **S-1: feasibility pilot (VNI and Heywood)** before S0. It builds the relevance filter, per-family on/off base rates, match success rates under G9, and support counts. Proceed to all six connectors only if at least 10 families per connector reach supported status with ≥60% matched support.
