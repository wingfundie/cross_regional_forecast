# NOS outage regime research — execution plan (v1)

**Status:** complete (2026-09-24). All six connectors are analysed and the report section is published and validated. See [`RESULTS_SUMMARY.md`](RESULTS_SUMMARY.md). The execution log is authoritative.
**Owner documents:** this plan (what and when), [`METHODOLOGY.md`](METHODOLOGY.md) (definitions and formulas), [`EXECUTION_LOG.md`](EXECUTION_LOG.md) (every execution).
**Design history:** [`docs/NOS_OUTAGE_REGIME_RESEARCH_DESIGN.md`](../../docs/NOS_OUTAGE_REGIME_RESEARCH_DESIGN.md) holds the original proposal, grilling rounds 1–2 and the 2026-09-24 feasibility assessment. Where it conflicts with this plan, this plan wins.
**Base report:** [`reports/all_interconnector_regime_research_20260921/`](../../reports/all_interconnector_regime_research_20260921/METHODOLOGY.md).

## 1. Goal

Add an **outage regime** layer to the all-interconnector regime report. For all six interconnectors, it describes how dispatch limits, headroom and flow behave, together with weather, VRE, demand, constraint leaders and DUID pressure, **given a specific NOS outage**. Results are available at several levels of specificity:

> "When the 99J line out of Yanco is out, VNI import capacity typically falls by X MW in winter evening peaks. The outage invokes set family N-XXXX, whose equations are most sensitive to generators A and B in the same sub-region."
> *(Illustrative sentence only. No result exists yet.)*

This is **knowledge only**: a retrospective description with no forecast features and no model fitting.

## 2. Decisions

| # | Decision | Answer | Source |
|---|---|---|---|
| G1 | Product | Pooled outage-regime analysis as the backbone, plus a **specific outage lookup** gated on evidence | User, round 1 |
| G2 | Connectors | All six: QNI, Directlink, VNI, Heywood, Murraylink, Basslink | User, round 1 |
| G3 | Window | `(2024-09-01 00:00, 2026-09-01 00:00]` NEM time. Year 1 outages come from MMSDM (final state). Year 2 comes from the weekly NOS snapshots | User, round 1 |
| G4 | Home | A new section plus downloads in `reports/all_interconnector_regime_research_20260921` | User, round 1 |
| G5 | Purpose | Knowledge only. Realised outage times and invocations may be used | User, round 1 |
| G6 | Outage definition | The **constraint-set family is invoked** (after the relevance filter). Booked-only and leading are reported as separate states | Default, applied (user asked to proceed) |
| G7 | Lookup key | **Multi-level location key.** Every episode carries: set family + NOS asset (specific line/equipment) + substation + sub-region/area + electrically and geographically nearby generators. See §4 | **User, 2026-09-24** |
| G8 | Support gate | Two tiers (supported / indicative), applied **at each key level**, with back-off to the most specific supported level | Default, applied (user asked to proceed) |
| G9 | Matching | Same connector-direction, season, half-hour, day type and weather/VRE/residual-demand tercile, within ±21 days of the same year, **plus the same set of other active relevant set families** | Default, implemented as a three-rung ladder (E026) |
| G10 | Report integration | Add in place, versioned: archive the v1 manifest and hash-check that existing tables are unchanged | Default, applied (user asked to proceed) |
| G11 | Booking reliability | Keep a short descriptive panel (year 2 only) | Default, applied (user asked to proceed) |
| G12 | Unbooked invocations | Their own state under the redefined rule (METHODOLOGY §3.4), excluded from class effects | Default, implemented (METHODOLOGY §3.4) |
| G13 | Headline metrics | Directional capacity change (MW and % of seasonal median) plus at-limit share | Default, applied (user asked to proceed) |

Defaults can be changed until stage S4 starts. Record any change in §2 and in the execution log.

## 3. Feasibility facts that shape the plan (2026-09-24, log E001–E003)

- All 90 VNI-linked and 98 QNI-linked NOS set IDs appear in `GENCONSETINVOKE`, so the booked → invoked join works.
- Connector-mapped outage sets are invoked in **75–80% of half-hours**, with a median of 3–4 sets at once. A binary "outage vs clear" contrast is therefore not usable. The primary contrast is **set family on vs off, matched on the other active sets**.
- `SYSTEMNORMAL` is almost never 1, so it cannot identify unplanned outages.
- Invocations are short (median 1.5–4 h), so event studies align on invocations, not on NOS episodes.
- NOS asset fields provide `SUBSTATIONID`, `EQUIPMENTTYPE`, `EQUIPMENTID` and `ELEMENTID` (e.g. `YANCO / LINE / 99J / 3929`). Descriptions, voltage and line end-points need `NETWORK_EQUIPMENTDETAIL` and `NETWORK_SUBSTATIONDETAIL` (MMSDM, confirmed present for 2024-09).

## 4. The specific outage key (G7)

The key has five levels, **all attached to every episode**. Results are published at the most specific level that passes the support gate, and each level up is also shown.

| Level | Key | Built from | Example shape |
|---|---|---|---|
| K1 Asset | `SUBSTATIONID/EQUIPMENTTYPE/EQUIPMENTID` (+ `ELEMENTID`) | NOS OUTAGEDETAIL, plus EQUIPMENTDETAIL for description, voltage and line end-points | `YANCO/LINE/99J` · 132 kV · Yanco–X |
| K2 Constraint-set family | `GENCONSETID` (+ family stem, METHODOLOGY §4.2) | OUTAGECONSTRAINTSET, GENCONSETINVOKE | `N-XXXX` |
| K3 Substation | `SUBSTATIONID`, with name, region and TNSP | SUBSTATIONDETAIL | Yanco, NSW1, TransGrid |
| K4 Area | ISP sub-region, plus a descriptive area label (e.g. "north-west Sydney") from coordinates | Substation coordinates (public GA dataset + versioned crosswalk), ISP sub-region map | SNSW · "Riverina, south-west NSW" |
| K5 Nearby generators | (a) **electrically near:** DUIDs in the invoked set's equations ranked by \|sensitivity\|; (b) **geographically near:** DUIDs within a radius of the substation | SPDCONNECTIONPOINTCONSTRAINT + DUDETAILSUMMARY; GA power-station locations | "electrically near: DUID A (0.42), DUID B (0.31); geographically: within 50 km: C, D" |

**As implemented** (see METHODOLOGY §4 and §9):
- Coordinates come from OpenStreetMap, because the GA services were blocked.
- K4 is a place + compass-octant area rather than an ISP sub-region.
- K5 geographic lists OSM plant names.
- K1 also keys `N/A` assets by element (`EL<ELEMENTID>`) using the EQUIPMENTDETAIL description.
- No family stem pooling was applied.

Rules:
- One outage can have several assets, such as a line plus its circuit breakers. The **primary asset** is chosen by type order LINE > TRANS > BUS > reactive plant > CB > other. All assets are retained.
- Secondary-equipment outages (`N/A` asset) have no K1 or K3. Their location comes only from K2 set equations (K4/K5 via DUIDs) and is flagged `location_source = set_only`.
- Every location attribute carries a `method` and a `confidence` (exact ID match / name match / manual crosswalk / inferred). **Electrical proximity is the primary meaning of "near".** Geographic proximity is used for labelling.
- The crosswalk from AEMO substation IDs to coordinates is a versioned CSV committed under `execution/nos_outage_regime_v1/reference/`. Unmatched substations stay unmatched and are never guessed.

## 5. Stages and gates

| Stage | Work | Output (local, ignored by Git unless noted) | Gate to proceed |
|---|---|---|---|
| **S-1 Pilot** (VNI + Heywood) | Download the four MMSDM network tables (small); relevance filter; per-family on/off base rates; match success under G9; lookup support counts per key level; K1–K5 coverage for pilot assets | `data/nos_regime_v1/pilot/*.parquet`, `execution/nos_outage_regime_v1/pilot_summary.md` (committed) | ≥10 families per connector reach "supported" with ≥60% matched support; ≥80% of pilot primary assets resolve to K3; K4 resolution rate reported. **User review before S0** |
| S0 Acquire | MMSDM `NETWORK_OUTAGEDETAIL`, `OUTAGECONSTRAINTSET`, `EQUIPMENTDETAIL`, `SUBSTATIONDETAIL` for 2024-09 → 2026-08; GA substation and power-station layers; ISP sub-region reference | `data/nos_regime_v1/raw/` with hashes in `sources.json` (committed) | Every month present or explicitly listed as missing |
| S1 Episodes | A NEM-wide deduplicated outage-episode table: MMSDM for year 1, weekly NOS for year 2, resubmission chains collapsed | `episodes.parquet` | Year-1/year-2 overlap month reconciles (Aug 2025 counts compared) |
| S2 Location key | K1–K5 attributes with method and confidence | `outage_keys.parquet`, `reference/substation_crosswalk.csv` (committed) | K3 ≥ 90% of primary assets; unresolved assets listed |
| S3 Mapping + relevance | Versioned set→equation→connector mapping for all six connectors (generalised `MappingHistory`); relevance filter | `set_relevance.parquet` | Relevance filter documented and applied identically to all connectors |
| S4 State panel | A 5-minute state per connector-direction and family (METHODOLOGY §3); joined to envelope leaders; half-hour join to the regime panel | `state_5min/`, `panel_30min.parquet` | No `unknown` merged into `clear`; completeness per half-hour matches the report rule |
| S5 Comparisons | Descriptive tables, matched on/off effects, invocation event studies, placebo tests, spillover, booking reliability, lookup at each key level | `tables/*.parquet` (content-addressed) | Placebo effect CIs include 0 for ≥90% of supported families; balance diagnostics published |
| S6 Report | New report section plus downloads, rendered from cached tables only; v2 manifest | report folder (committed) | Hashes verified; existing tables unchanged |
| S7 Validation | Report validator, offline check, desktop/mobile screenshots, `python -m pytest -q` | `report_visual_qa.json` | All pass; anything not verified is stated |

Code lives under `nemic/experiments/nos_regime/` (`episodes.py`, `keys.py`, `relevance.py`, `state.py`, `compare.py`), with `scripts/run_nos_regime.py --stage <id>` and `scripts/build_nos_regime_section.py`. Tests go in `tests/test_nos_regime_*.py` and cover state precedence, key back-off, crosswalk no-guess behaviour, matching determinism and the placebo pipeline.

## 6. Execution protocol (wired to the log)

1. **Every execution gets a log entry**: stage runs, downloads, pilot checks, report builds, test runs, and ad-hoc analysis that informs a decision. Use
   `python scripts/nos_regime_log.py start --stage <id> --command "<cmd>" [--note ...]` before running, and
   `python scripts/nos_regime_log.py finish <entry-id> --status completed|failed|partial --artifacts <paths> --note "<result>"` afterwards.
   The helper appends to `EXECUTION_LOG.md` (human-readable) and `execution_log.jsonl` (machine-readable).
2. Before starting any stage, read the log. If an entry for that stage is `started` with no finish, check whether its process is still running before doing anything else. Never run two owners of one stage.
3. A stage is **complete** only when its gate in §5 is met and the finishing log entry cites the evidence.
4. Changes to a decision in §2 or to METHODOLOGY definitions get a log entry of type `decision` and invalidate the cached outputs of downstream stages.
5. Status reports quote the log: completed, active and remaining stages.

## 7. Deliverables

- Report section "Outage regimes" in the regime report: landscape, outage-family effects, timing, weather/VRE interaction, flow response, constraint and DUID mechanics, spillover, booking reliability, event studies, falsification tests, the **specific outage lookup** (cards at K1 → K5 back-off), and limitations.
- Downloads: `outage_episodes.csv`, `outage_keys.csv`, `set_relevance.csv`, `outage_state_coverage.csv`, `outage_matched_effects.csv`, `outage_diurnal_profiles.csv`, `outage_weather_vre_interaction.csv`, `outage_flow_response.csv`, `outage_leader_transitions.csv`, `outage_duid_pressure.csv`, `outage_spillover_matrix.csv`, `booking_reliability.csv`, `outage_event_study.csv`, `outage_placebo_checks.csv`, `outage_lookup.csv`.
- Updated report `METHODOLOGY.md` section plus a pointer to this folder.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Outages are scheduled for low-impact times | Matching, placebo tests, "as scheduled" wording |
| Most time has some outage active | Family on/off contrast conditioned on other active families |
| Substation → location crosswalk is incomplete | No guessing; confidence column; K3 fallback |
| Year-1 NOS is final-state only | Booking reliability is year 2 only; year label kept on every episode |
| Always-invoked or configuration sets distort results | Relevance filter; exclusion list for `#…_RAMP` and long-standing `*-NIL_*` sets, reviewed in the pilot |
| Adding to a published report | Versioned manifest; v1 archived; hash check of unchanged tables |
