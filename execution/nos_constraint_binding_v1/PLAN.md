# NOS outage constraint mechanics and forward outlook — execution plan (v1)

**Status:** complete (2026-09-24). Releases 0, 1 and 2 published; all stages A, B, D and C ran. Decisions were settled in a grilling session (Q1–Q28, §3); deviations are listed in METHODOLOGY §9. See [`RESULTS_SUMMARY.md`](RESULTS_SUMMARY.md); the execution log is authoritative.
**Builds on:** [`execution/nos_outage_regime_v1/`](../nos_outage_regime_v1/PLAN.md) (episodes, families, K1–K5 keys, matched comparison), the six two-year constraint studies (`data/constraint_*_2y/`) and the weekly NOS snapshots (`data/forecast_experiments/*_diurnal_nos_v2/nos/weeks/`).
**Owner documents (created at A0):** this plan, `METHODOLOGY.md`, `EXECUTION_LOG.md` + `execution_log.jsonl`, `sources.json`, `RESULTS_SUMMARY.md`. The execution log is authoritative once work starts.

## 1. Goal

Answer, for every NOS outage family and down to the specific asset where evidence allows:

> "When outage X is on, which constraint equations **bind** and which **set the limit** on each interconnector, how often, and how much more often than in matched outage-free conditions? Does the outage's own set take over or does a system-normal equation become the limit? When does binding start after invocation? Which generators drive it, including on equations that constrain generators only?"

Then apply that evidence **forward**: for the NOS outages booked up to 12 months ahead, state which constraints are likely to bind and set limits, with skill measured by a walk-forward backtest.

The three constraint layers of the all-interconnector regime report are kept separate throughout:

| Layer | Definition (as in the regime report) | NOS v1 status |
|---|---|---|
| Published binding | \|MARGINALVALUE\| > 1e-9, `INTERVENTION = 0` | Missing: only monthly counts exist locally |
| Reconstructed limit-setter | Equation forming the tightest upper/lower conditional envelope | Partial: top-3 per family, no matched control, one bug |
| Generator pressure | `sᵢ × ΔPᵢ` under the active leader | Done for connector leaders (`nos_duid_pressure.csv`) |

AEMO limits are dispatch-solution outputs, not maximum secure physical capability. The historical analysis is conditional research built from realised invocations. The outlook is a research outlook, not a deployed forecast service.

## 2. Structure

| Phase | Content | Release |
|---|---|---|
| R0 | Commit and merge the staged NOS report-sync (`codex/nos-report-sync`) | Release 0 |
| A | Limit-setters from cached data: pair replay, setter tables, bug fix, lookup columns | Release 1 |
| B | Published binding: DISPATCHCONSTRAINT + DISPATCHLOAD, binding panel, binding tables, as-known split, generator-only pressure | — |
| D | Forward outlook: pipeline, 12-snapshot backtest, live outlook from the newest NOS file | — |
| C | Full report chapter, combined-report summary, docs, validation | Release 2 |

Order: R0 → A → Release 1 → B → D → C → Release 2. Phase D needs Phase B. The live outlook is not shown anywhere until its backtest is complete (Q27).

## 3. Decisions (settled 2026-09-24)

| # | Topic | Decision |
|---|---|---|
| Q1 | Purpose | Knowledge first, forecast-ready design: record outage-record vintage and key joins so everything can be rebuilt from as-published snapshots |
| Q2 | Families | Supported families are headline results; indicative families appear in downloads with a flag |
| Q3 | Headline unit | Lookup by physical asset with K1 → K3 → K4 → family back-off; analysis chapters by family |
| Q4 | Equation scope | Dependency equations of all six connectors **plus** member equations of relevant outage sets without an interconnector term; the latter are reported separately and excluded from connector-level lift |
| Q5, Q10 | Marginal value | Descriptive only, never summed: median \|MV\|, share above 100 and 1,000 $/MWh, and share above the equation's own outage-free P90 |
| Q7 | As-known view | Year 2: split every table by whether the outage was booked in the weekly snapshot 1, 7 and 14 days before the interval |
| Q8 | Asset gate | v1 gate plus ≥ 30 treated five-minute intervals in which the named equation binds; otherwise back off |
| Q9, Q18 | Generator-only equations | Report binding and compute generator pressure as slack consumed, `bᵢ × ΔPᵢ`, signed so positive = tightening; needs DISPATCHLOAD |
| Q11 | Headline statistic | Binding lift in percentage points (outage − matched control); ratio in tables |
| Q13, Q19 | Outlook snapshot | Newest weekly NOS file, recorded with publication time and hash; re-run by a manual script (`--latest`) |
| Q14 | Unlinked bookings | Infer family from asset history (K1 → K3 → K4) restricted to the same equipment type; probability and `inferred` flag on every row |
| Q15 | Outlook format | Both per outage × connector-direction and week × connector-direction (§7) |
| Q16 | Backtest | From each monthly year-2 snapshot, scored by lead band and connector-direction |
| Q17 | Overlaps | Joint estimate from historical co-occurrence where supported; otherwise separate rows with an overlap flag |
| Q20 | Outlook publication | Each run writes a dated local folder and rebuilds the local report chapter; nothing is committed unless requested |
| Q21 | Scoring | Brier and reliability for P(bind) and P(sets limit); recall, precision and false alerts for "binds ≥ X % of the outage"; MW error of limit change; family-inference accuracy. Baselines: (i) equation's season × half-hour normal rate, (ii) last year's same-family rate. No pre-dispatch comparison |
| Q22 | No skill | Where the outlook does not beat baseline (i) for a lead band × connector-direction, show the baseline and say so |
| Q23 | Network change | Exclude equations retired before the snapshot; flag rows whose equations or top generators are new or changed since the history window |
| Q24, Q27 | Outlook timing | Outlook ships after Phase B, and only once its backtest is complete |
| Q26 | Wording | Historical-frequency wording with measured skill beside it; "unvalidated" appears only where the baseline is shown instead |
| Q28 | Backtest leakage | Reuse saved matched units with a 21-day embargo (treated half-hours ending ≥ 21 days before the snapshot) and recompute relevance, tiers and binding tables from pre-snapshot data; confirm with full comparison re-runs at two snapshots |
| Q6, Q12 | Home and publishing | Existing standalone NOS report (full chapter) + combined-report summary; each release is a feature branch merged directly into `codex/nem-forecast-lab`; push requires the user's approval |

Fixed rules carried over (not separately asked): binding threshold 1e-9, `INTERVENTION = 0`; near-binding = IC-normalised slack 0–50 MW; aggregate by `CONSTRAINTID` and keep `version_key`; v1 matching, bootstrap and placebo methods; v1 evidence tiers.

## 4. Feasibility facts (checked 2026-09-24)

- **Limit-setters exist at five minutes** for all six connectors (`constraint_features_5min.parquet`). Phase A needs no download.
- **Published binding is not time-resolved locally.** `nemic/constraint_longitudinal.compact_month` keeps monthly per-constraint counts and deletes the filtered DISPATCHCONSTRAINT and DISPATCHLOAD.
- **Download size.** The QNI study ledger records 24 DISPATCHCONSTRAINT archives (4.19 GB compressed; 169–195 MB per month in late 2024) and 24 DISPATCHLOAD archives (2.76 GB), each with a SHA-256. These are NEM-wide archives, so **one pass serves all six connectors**.
- **Filtered volume.** About 0.9–1.2 M equation rows per month for QNI's dependency set; a sparse panel (binding, near-binding or leading rows) is expected to be far smaller.
- **Matched pairs are not saved.** `compare.Context.match` builds `(tp, cp, match_type)` but `units__*.parquet` keeps only control medians, so the pairs must be replayed (A1).
- **Weekly NOS snapshots are local and NEM-wide.** There are 53 files, `PUBLIC_NETWORK_20250829` → `20260828` (about 230 MB, OUTAGEDETAIL + OUTAGECONSTRAINTSET rows as JSON). The newest (2026-08-28) holds about 20,500 detail rows: about 9,200 start after 2026-09-24 and about 2,900 more than six months out, but only 1,680 set-link rows. **Most far-ahead bookings will need family inference (Q14).**
- **Year 1 has no weekly snapshots.** The as-known split (Q7) and the backtest (Q16) are year-2 only.
- **Known bug.** `leader_transitions()` in `scripts/build_nos_regime_section.py` computes `leader_changed_share` from `zip(times, before)`, pairing every treated half-hour with one "before" value per run, so the pairs are misaligned. `during_top3` and `before_top3` are unaffected.

## 5. Historical stages

All data goes to `data/nos_binding_v1/` (ignored). Every stage is resumable and logged with start/finish entries.

### Phase A — limit-setters from cached data

| Stage | Work | Output | Gate |
|---|---|---|---|
| A0 Setup | Folder, log helper, config `configs/experiments/nos_constraint_binding_v1.json` (window, thresholds, §3 decisions) | `execution/nos_constraint_binding_v1/` | Config hash logged |
| A1 Pair replay | Re-run v1 matching without bootstrap, saving `(ic, direction, GENCONSETID, tp, cp, match_type)` | `pairs__<ic>.parquet` | Replayed control medians **equal** v1 `units__*.parquet` for every family; any mismatch stops the campaign |
| A2 Setter panel | Five-minute setter per connector-direction mapped to `CONSTRAINTID`, owning set(s) and class (own set, other outage set, system-normal, ramp/FCAS/other) | `setter_5min__<ic>.parquet` | Reproduces v1 `lead_forward`/`lead_reverse` exactly |
| A3 Family tables | Per family-direction: own-set setting rate; top-10 setters on vs matched off (difference and ratio, day-block CI); displacement; by season, day period, weather/VRE regime | `setter_family`, `setter_topk`, `setter_by_regime` | Shares sum to 1 per unit; CI reproducible under the fixed seed |
| A4 Transitions (fixed) | Setter before each invocation run vs its first half-hour, aligned per run; correct `leader_transitions()` in the v1 builder | `setter_transitions` | Unit test with a synthetic two-run series |
| A5 Timing | Event study of own-set and top system-normal setter probability, −6 h to +12 h around invocation start and end, clean spells | `setter_event_study` | ≥ 5 clean spells per plotted family |
| A6 Lookup | K1 → K4 back-off (v1 rules) for own-set rate and top-3 setters | `setter_lookup` | Supported and ≥ 24 treated hours only |
| A7 Placebo | ±7-day shifted windows for own-set rate and top-setter difference | `setter_placebo` | Clean share reported; failures flagged |
| A8 Release 1 | Phase A cut of the report chapter and lookup columns (§8) | Report + downloads | Validator, renders, pytest |

### Phase B — published binding

| Stage | Work | Output | Gate |
|---|---|---|---|
| B0 Scope | Equation list per Q4: six `dependencies.json` lists + relevant-set members; also the DUIDs and connection points of generator-only equations | `equation_scope.parquet` | Counts and hash logged |
| B1 Acquire | Per month: download DISPATCHCONSTRAINT and DISPATCHLOAD, verify SHA-256 against the constraint-study ledgers, filter to scope, delete the archives | Transient month tables + `sources.json` | Hash match or logged, explained mismatch; every month present or listed missing |
| B2 Binding panel | Join `ic_factor`; IC slack, binding, near-binding, MV; keep rows that bind, near-bind or lead | `binding_5min` (partitioned by month) | **Reproduces each connector's monthly `binding_intervals` and `near_binding_intervals` exactly** for dependency equations |
| B3 Binding tables | Run the A3–A7 builders on the binding layer: lift, top-10 binders, own-set binding rate, near-binding, simultaneous binders, MV summaries (Q10), violations | `binding_family`, `binding_topk`, `binding_by_regime`, `binding_event_study`, `binding_lookup` (Q8 gate), `binding_placebo` | As Phase A |
| B4 Layer agreement | Share of intervals: own set binds and sets / binds only / sets only / neither | `layer_agreement` | Cells sum to 1 |
| B5 Cross-link | Binding lift of each family on other connectors' dependency equations | `binding_footprint` | Supported cells only coloured |
| B6 As-known split | Year 2: tables split by booked in the snapshot 1 / 7 / 14 days before the interval | `binding_asknown` | Snapshot joins use publication time, not file date |
| B7 Generator-only pressure | For generator-only own-set equations: `bᵢ × ΔPᵢ` slack consumption per DUID, treated vs matched control; top DUIDs | `genonly_pressure` | Signs verified on a hand-checked equation |

Disk and runtime: one month at a time (≈ 300 MB compressed, ≤ 3 GB decompressed, within the existing limits); about 7 GB downloaded in total; an estimated **3–5 h** for B1–B2, minutes for B3–B7.

## 6. Phase D — forward outlook and backtest

### D1 Outlook pipeline (`nemic/experiments/nos_regime/outlook.py`, `scripts/run_nos_outlook.py`)
Inputs: one NOS snapshot and an `as_of` cut-off. Everything else is computed only from data before `as_of`.

1. **Parse** the snapshot (OUTAGEDETAIL, OUTAGECONSTRAINTSET), keep bookings starting within 12 months, exclude withdrawn and completed, and record the snapshot ID, publication time and SHA-256.
2. **Key** each booking to K1–K4 with the v1 key builder.
3. **Family:** use the linked set when present. Otherwise infer it (Q14): the empirical distribution of families historically invoked for the same asset, then substation, then area, restricted to the same equipment type. Keep the top 3 with probabilities and an `inferred` flag.
4. **Network change (Q23):** drop equations retired before `as_of` (GENCONDATA effective dates and versions) and flag new or changed equations or top DUIDs.
5. **Evidence join:** attach family/asset results from Phases A and B that were computed on pre-`as_of` data. For each connector-direction this gives the limit-change estimate with CI, top-3 binding equations (historical binding frequency, lift), top-3 setters, own-set binding rate, generator-only equations and top DUIDs, and tier.
6. **Timing adjustment:** weight the historical rates by the booking's seasons and half-hours (Phase A/B by-regime tables).
7. **Booking reliability:** the family's historical withdrawal, early-return and overrun rates.
8. **Overlaps (Q17):** a joint estimate where historical co-occurrence is supported; otherwise an overlap flag.
9. **Skill gate (Q22):** replace the estimate with baseline (i) where the backtest shows no skill for that lead band × connector-direction, and say so.

### D2 Backtest (Q16, Q21, Q28)
- **Snapshots:** the first weekly file of each month in year 2, 12 origins from 2025-09 to 2026-08.
- **Leakage control:** statistics come from saved matched units with treated half-hours ending ≥ 21 days before the origin. Relevance, tiers, setter and binding tables and family-inference distributions are recomputed from pre-origin data.
- **Confirmation:** a full v1 comparison re-run with data cut at two origins (one early, one late). The embargoed statistics must agree within bootstrap CI for supported families, or the embargo method is replaced by full re-runs.
- **Truth:** realised invocations, published binding and setters from Phases A/B over each booking's actual window. Withdrawn bookings count as "did not occur".
- **Scores by lead band** (0–7, 8–30, 31–90, 91–365 days) × connector-direction:
  - Brier score and reliability diagram for P(bind) and P(sets limit)
  - recall, precision and false alerts for "binds ≥ X % of the outage" (X chosen on the first six origins and applied to the last six)
  - MAE of the limit change
  - top-1 and top-3 accuracy of family inference
  - sample counts in every cell
- **Baselines:** (i) the equation's season × half-hour normal binding rate; (ii) last year's same-family rate.
- **Output:** `outlook_backtest_scores`, `outlook_backtest_rows` and the skill table used by D1 step 9.

### D3 Live outlook
Run `python scripts/run_nos_outlook.py --latest`. It fetches the newest weekly NOS file only if it is not already local, builds the outlook with `as_of` = snapshot publication time and writes `data/nos_outlook/<snapshot>/`. It then rebuilds the local report chapter; nothing is committed (Q20). The first live run uses the newest file available at D3 (after 2026-08-28).

## 7. Outlook output format (Q15)

**Per booking × connector-direction** (`nos_outlook_outages.csv`):

`snapshot_id, snapshot_published, snapshot_sha256, outage_id, asset, equipment_type, substation, area, booked_start, booked_end, lead_days, booking_status, family, family_source (linked|inferred), family_probability, ic, direction, limit_change_mw, limit_change_ci_lo, limit_change_ci_hi, bind_eq_1..3, bind_freq_1..3, bind_lift_pp_1..3, setter_eq_1..3, setter_freq_1..3, own_set_bind_rate, genonly_eqs, genonly_top_duids, tier, withdrawal_rate, early_return_rate, overlap_ids, overlap_joint (bool), network_change_flag, skill_status (skilful|baseline_shown), baseline_bind_freq, confidence_note`

**Per week × connector-direction** (`nos_outlook_weekly.csv`): outage count, expected hours with a supported family invoked, the most likely binding equations with frequencies, the largest expected limit reduction, overlap count and skill status.

**Views:** a 12-month calendar by connector, a next-8-weeks table, and an outlook section in the report. Every view shows the snapshot ID and publication time and uses historical-frequency wording (Q26).

## 8. Report (Phase C)

The standalone report `reports/nos_outage_regime_research_20260924` gets a new chapter, "Constraint mechanics during outages", and an "Outage outlook" chapter:

1. The three layers explained: binding, limit-setting and pressure, shown on an outage example.
2. Own-set dominance: own-set setting and binding rates by family (dot plot with CI).
3. What binds during outage X: top-10 binders on vs matched off.
4. Displacement matrix: which system-normal equations lose or gain share.
5. Layer agreement: stacked bars.
6. Timing: event-study curves around invocation start and end.
7. When it binds: 48-half-hour and season heatmaps of lift.
8. Weather/VRE interaction on binding lift.
9. Binding footprint across the twelve link-directions.
10. Marginal value context (Q10) with the price-level caveat.
11. Generator-only equations and their pressure DUIDs.
12. As-known split: booked-in-advance vs not (Q7).
13. Lookup with constraint columns (Q8 gate).
14. Outlook: calendar, next-8-weeks table, per-outage cards.
15. Backtest: skill by lead band and connector-direction, reliability diagrams, family-inference accuracy, and where the baseline is shown.
16. Robustness: placebo results, reconciliation with the regime report, intervention exclusions, embargo confirmation.

The combined report `reports/all_interconnector_regime_research_20260921` gets a summary block and downloads in the Outage regimes section, with a manifest bump and hash checks.

**Downloads** (all prefixed `nos_`):
- setter tables: `setter_family`, `setter_topk`, `setter_transitions`
- binding tables: `binding_family`, `binding_topk`, `binding_by_regime`, `binding_event_study`, `binding_asknown`, `binding_footprint`, `binding_placebo`
- other analysis: `layer_agreement`, `genonly_pressure`, `constraint_lookup`
- outlook: `outlook_outages`, `outlook_weekly`, `outlook_backtest_scores`

## 9. Code layout

- `nemic/experiments/nos_regime/pairs.py`: A1 replay. It reuses `compare.Context` and adds pair saving without changing v1 results.
- `nemic/experiments/nos_regime/setters.py`: A2–A7 builders, written against a generic event layer (setter or binding) and an `as_of` cut-off so B and D reuse them.
- `nemic/experiments/nos_regime/binding.py`: B0–B2 and B7. It reuses `constraint_ingest._table_rows`, `download_entry` and the storage limits.
- `nemic/experiments/nos_regime/outlook.py`: D1–D2.
- Scripts: `scripts/run_nos_binding.py --stage …`, `scripts/run_nos_outlook.py [--latest | --snapshot … --as-of …] [--backtest]`, `scripts/build_nos_constraint_chapter.py`.
- `tests/test_nos_binding.py`, `tests/test_nos_outlook.py`. They cover:
  - pair-replay determinism
  - transition alignment (the bug)
  - binding flag rule
  - reconciliation on a fixture
  - Q8 back-off
  - share sums
  - family inference with the equipment-type restriction
  - retired-equation exclusion
  - `as_of` leakage (no row after the cut-off may influence a statistic)
  - skill-gate fallback
  - snapshot hash and vintage recording

## 10. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Pair replay not deterministic | A1 gate; otherwise a full re-run with pair saving (~40 min), logged as a v1 revision |
| Binding rare, CIs wide | Counts beside every share; tiers; Q8 gate; pooling by family stem where supported |
| Generator-only equations inflate "own-set binding" | Reported separately; excluded from connector lift (Q4) |
| Constraint versions change | Aggregate by CONSTRAINTID; keep `version_key`; retired equations excluded from the outlook (Q23) |
| Far-ahead bookings lack sets | Inference with probability and flag (Q14); inference accuracy scored in the backtest |
| Backtest leakage | 21-day embargo, pre-origin recomputation, two full re-run confirmations (Q28), leakage unit test |
| Only 12 origins, year 2 only | Report counts per cell; no lead band claimed skilful without sufficient rows; year-1 limitation stated |
| NEMWEB archive changed or unavailable | Hash check against the ledgers; stop on unexplained mismatch |
| Final-state history vs as-known outlook | The as-known split (Q7) shows the difference; the outlook uses snapshot data only for bookings |
| Outlook read as an operational forecast | Research-outlook label, snapshot stamp, skill table, baseline fallback (Q22, Q26); not wired into `nemic.production` |
| Binding ≠ physical capability | Regime-report qualification repeated in every chapter |

## 11. Ideas for later (out of scope)

- Compare AEMO pre-dispatch constraint forecasts (PREDISPATCHCONSTRAINT) with actual binding during outages, for the next ~40 h.
- A constraint substitution graph: which equation takes over when an outage set is invoked.
- Binding fingerprints: cluster families by their binding and setter profiles.
- Link binding intervals to regional price separation.
- A scheduled outlook refresh, once there is a production data feed with verified issue-time inputs.

## 12. Estimates

| Phase | Compute | Download |
|---|---|---|
| A | A1 ≤ 40 min; A2–A7 minutes | none |
| B | 3–5 h (B1–B2); minutes for B3–B7 | ≈ 7 GB, one month at a time |
| D | Backtest minutes per origin + 2 × ~40 min confirmations; live run minutes | one weekly NOS file (a few MB) |
| C | Minutes (from cached tables) | none |
