# Methodology — interconnector limits and flow under NOS outage regimes (v1)

Companion to [`PLAN.md`](PLAN.md). This document defines every quantity. Code must implement these definitions exactly, and any change is logged as a `decision` in [`EXECUTION_LOG.md`](EXECUTION_LOG.md).

## 1. Inherited definitions (unchanged from the regime report)

These come from `reports/all_interconnector_regime_research_20260921/METHODOLOGY.md`:

- **Time:** fixed NEM time UTC+10, interval-ending. The native unit is five minutes. A complete half-hour has six distinct five-minute observations. Missing observations are never zero-filled.
- **Seasons:** Summer Dec–Feb (December belongs to the following year's summer), Autumn Mar–May, Winter Jun–Aug, Spring Sep–Nov. Season blocks are exact three-month blocks.
- **Day periods:** overnight 21:00–05:59, morning 06:00–08:59, solar 09:00–15:59, evening 16:00–20:59.
- **Limits:** signed flow follows each connector's forward orientation. `forward_capacity = upper_bound` and `reverse_capacity = −lower_bound`. Headroom is capacity minus directional flow. Negative capacity is retained and counted as forced direction.
- **Restricted:** capacity below 50% of the connector-direction-season median of strictly positive capacity. The threshold stays fitted on the report's full 2023–2026 history so that outage time doesn't lower its own reference.
- **Weather/VRE regimes:** temperature, regional VRE (wind + solar) and residual demand in low ≤P20, normal P20–P80 and high ≥P80 bins, within connector and season.
- **Constraint envelope:** for `aF + Σ bᵢPᵢ + Z ≤ RHS`, the bound is `F_obs + (RHS − LHS)/a` and DUID sensitivity is `−bᵢ/a`. The minimum upper and maximum lower candidates form the envelope. Leaders and published binding setters are kept separate.
- **DUID pressure:** `sᵢ × (Pᵢ[t] − Pᵢ[t−30m])` under the active leader. Tightening is the positive part of a capacity reduction; relief is the positive part of an increase.

AEMO interconnector limits are dispatch-solution outputs, not maximum secure physical transfer capability. Every "effect" below is a change in the dispatch envelope.

## 2. Study window and sources

- Window: `(2024-09-01 00:00, 2026-09-01 00:00]`. Year 1 is Sep 2024–Aug 2025 and year 2 is Sep 2025–Aug 2026, giving two blocks of each season.
- Outage records: **both years** come from the MMSDM 2026-08 `NETWORK_OUTAGEDETAIL` and `NETWORK_OUTAGECONSTRAINTSET` tables. These are cumulative, final-state tables (`source = mmsdm_final`; decision E012).
  - Reconciliation: all 26,454 year-2 outage IDs seen in the weekly NOS snapshots (`nemic/experiments/nos.py`) are present in the MMSDM table.
  - Booking revisions are therefore not modelled. Final status and actual times are used.
- Invocation: `GENCONSETINVOKE` (all six connector standing folders, deduplicated on `INVOCATION_ID`).
- Mapping: `GENCONSET` membership (the union of all versions across the six standing folders) links equations to families. `SPDINTERCONNECTORCONSTRAINT` and `SPDCONNECTIONPOINTCONSTRAINT` (latest effective version) supply K5 sensitivities. This mapping is retrospective: when AEMO published it is not proven.
- Location: `NETWORK_EQUIPMENTDETAIL`, `NETWORK_SUBSTATIONDETAIL` and `DUDETAILSUMMARY`, plus OpenStreetMap named `power=substation` / `power=plant` elements (ODbL; the snapshot timestamp is recorded in the report manifest). The Geoscience Australia services were not reachable (403/404), and an ISP sub-region reference was not retrieved (decisions E015, E022). Hashes are in `sources.json` and the report manifest.

## 3. Outage episodes and states

### 3.1 Episode
An **episode** is one NOS `OUTAGEID` after collapsing resubmission chains (`RESUBMITOUTAGEID`). The surviving record is the last successor. Episodes with status WDRAWN or CANCELLED are kept with `withdrawn = true`, and they contribute only to `booked_only` and booking-reliability tables.

The episode window is `ACTUAL_STARTTIME–ACTUAL_ENDTIME` where both are present (`window_source = actual`). Otherwise it is the last-known `STARTTIME–ENDTIME` (`window_source = scheduled`).

### 3.2 Invocation spell
An **invocation spell** is one `GENCONSETINVOKE` row covering interval-ending times `STARTINTERVALDATETIME` to `ENDINTERVALDATETIME` inclusive, with open ends clipped at the window end. Overlapping or adjacent spells of a family are merged for coverage.

A spell is **linked** if a non-withdrawn episode lists its family in OUTAGECONSTRAINTSET and the episode window overlaps the spell after widening both by ±24 h. A half-hour is linked when a linked spell covers it.

### 3.3 Relevance filter (per connector)
A family is **relevant** to a connector if, within the window, one of its equations was the reconstructed envelope leader for that connector **while the family was invoked** in at least **12 five-minute intervals**, in either direction. Published-binding flags are not time-resolved in the local archive, so binding is not used (decision E023). No factor-based fallback was needed.

Excluded as configuration rather than outage:
- set IDs beginning `#` (ramp and discretionary sets);
- any family invoked in more than 95% of the window.

NIL-named sets are not excluded by name, because some are listed by NOS outages (e.g. `T-NIL_WCP_CLOSE`); only the 95% rule applies to them. Result: 410 connector-family pairs relevant, 1,678 `#` sets, 65 below the leading threshold and 6 always-on sets excluded (E018).

### 3.4 States (half-hour, per connector-direction)
**Family level.** For a relevant family f in a half-hour: *invoked* = all 6 intervals covered; *off* = 0 covered; *partial* = otherwise (excluded from both treated and control); *leading* = invoked and an f equation led this direction in at least one of the six intervals.

**Connector level** (the landscape chart), with this order of precedence:

| State | Rule |
|---|---|
| `unknown` | Incomplete half-hour (fewer than six observations) |
| `invoked_leading` | Some relevant family is leading |
| `invoked_nonleading` | Some relevant family is invoked, none leading |
| `partial` | Some relevant family is partially invoked only |
| `booked_only` | Inside a live booking window that lists a relevant family, none invoked |
| `clear` | None of the above |

**Family effect states** (falsification and context):
- `invoked_unbooked`: f invoked in half-hours not covered by a linked spell;
- `booked_only`: inside a live booking window listing f, with f off;
- `withdrawn_booking`: inside a withdrawn booking window, with f off.

These are matched in the same way (§5.2, without placebo) and reported separately. They never enter the family effects.

## 4. Specific outage key (K1–K5)

### 4.1 Levels
- **K1 asset:** `SUBSTATIONID/EQUIPMENTTYPE/EQUIPMENTID`, plus `ELEMENTID`. EQUIPMENTDETAIL (effective at the episode start) supplies the description and voltage.
  - When NOS records the asset as `N/A` but EQUIPMENTDETAIL describes the element (e.g. "Dumaresq330-Sapphire 8J 330kV LINE"), the key is `EL<ELEMENTID>` and the equipment type is inferred from the description (decision E036).
  - The primary asset follows the type order LINE > TRANS > BUS > reactive plant > CB > other, with ties broken by highest voltage.
- **K2 set family:** the exact `GENCONSETID`. No stem pooling was applied: variants such as `I-JNWO_63` and `I-JNWO_RADIAL` are reported separately.
- **K3 substation:** `SUBSTATIONID` with name, region and TNSP from SUBSTATIONDETAIL. For `EL…` assets, the leading place name in the description is matched to a unique normalised substation name, with a tie-break on the voltage named in the description (`substation_method = description_parse`, confidence low).
- **K4 area:** from substation coordinates only.
  - `area_label` is the nearest of 58 reference places plus a compass octant and distance, e.g. "north-west of Sydney (35 km)", or "central X" if within 15 km.
  - `area_key` = region + place + octant, and is used for pooling.
  - Coordinates come from the OpenStreetMap name crosswalk: normalised name, same region, candidate spread ≤10 km (confidence medium).
- **K5 nearby generators:**
  - **Electrical:** for each equation in f, DUIDs with |sensitivity| = |bᵢ/a| ≥ 0.05, via the connection-point factors in SPDCONNECTIONPOINTCONSTRAINT mapped to DUIDs through DUDETAILSUMMARY. The top 10 are ranked by the maximum |sensitivity| across f's equations.
  - **Geographic:** named OpenStreetMap power plants within 50 km of the K3 substation. These are plant names, not DUIDs.

### 4.2 Provenance
K3/K4 attributes carry `method` (name_match / unmatched; plus `substation_method` = nos_asset / description_parse / unresolved) and `confidence` (medium for OSM name matches, low for description parses). The AEMO-substation-to-coordinates crosswalk is committed at `execution/nos_outage_regime_v1/reference/substation_crosswalk.csv`, and unmatched rows stay blank. `location_source` is one of asset+coordinates, asset_substation_only, asset_only or set_only (N/A asset with no description). K5 electrical neighbours come from the family's equations and do not depend on location.

### 4.3 Back-off
The lookup publishes a result for a key at the most specific level that passes support. The order is:

K1 asset × K2 family → K1 asset → K2 family → K3 substation → K4 area.

For each (connector, direction, primary asset), the first level with a *supported* row is published. If none exists, the first *indicative* row is published and shown greyed. When several rows qualify at one level, the one with the largest |effect| is shown.

K1, K3 and K4 treatments are defined over the union of the key's live episodes:
- treated = inside an episode window and at least one of the key's relevant families invoked;
- controls = all of those families off and outside the key's episode windows.

Keys with fewer than 3 listed episodes are not evaluated.

## 5. Comparisons

### 5.1 Descriptive
P10/P50/P90 of forward and reverse capacity, headroom, flow, restricted share, forced-direction share and at-limit share. Each is shown by state, connector-direction, season, day period, and weather/VRE regime, with n in every cell.

**At-limit** means directional headroom < max(10 MW, 5% of directional capacity). The at-limit *effect* is the difference in shares over matched units: the mean of the treated at-limit flags minus the mean of the per-unit control medians. A median of 0/1 differences is degenerate and is not reported (decision E047).

### 5.2 Matched on/off effect (primary; RQ1–RQ4, RQ6)
**Treated units** are half-hours on a connector-direction in which family f is invoked for all six intervals.

**Controls** are complete half-hours on the same connector-direction where f is off (0 of 6 intervals invoked), within ±21 days in the same study year. They are chosen by a matching ladder (decision E026); each treated unit uses the first rung that finds a control:
1. **exact:** same season, day type (weekend or public holiday in either endpoint state), temperature, VRE-difference and residual-demand-difference bins (the report's within-season P20/P80), and the **same set of other relevant families invoked**;
2. **count:** as (1), but with the same *number* of other relevant families invoked and the same other-family-leading flag;
3. **coarse:** season, day type, temperature bin and year, plus the same other-family count.

Each rung tries the same half-hour first, then ±1 half-hour. Treated half-hours have f invoked in all six intervals and linked to a live booking (§3.2); partially invoked half-hours are excluded. The rung used is recorded per unit and its share is reported per family.

Sampling rules:
- Up to 5 controls per treated half-hour, chosen deterministically: rung, then same half-hour before ±1, then a fixed hash of (treated time, control time).
- A unit is matched if at least one control exists.
- Match rate = matched ÷ treated.

**Estimate:** the median over treated units of (treated value − median of its controls).
**CI:** 95% day-block bootstrap, 1,000 replicates, resampling treated calendar days.
**Balance:** standardised mean differences for temperature, VRE difference, residual-demand difference, half-hour and other-family count. Before and after matching use the same pre-matching pooled SD.

### 5.3 Event study (RQ8)
- Align on invocation-spell starts and ends of f.
- Window −48 h to +48 h in 30-minute steps.
- Outcome = capacity minus the same-half-hour median from the 7 previous days on which f was off.
- Spells shorter than 1 h, and spells in the first 9 days (no baseline), are skipped.
- Spells with another relevant family starting or ending within ±2 h are flagged not clean. The report plots clean spells of supported families, pooled per connector-direction (median with P25/P75).

### 5.4 Spillover (RQ6)
Apply §5.2 to connector c′ for a family f that is relevant to some other connector but **not relevant** to c′ (requires ≥4 linked invoked half-hours). The signature of other families uses c′'s relevant set. Matrix cell (s, c′) = median effect over supported spillover families that are relevant to s, with the family count and the share of CIs that exclude 0.

### 5.5 Mechanics (RQ5)
- **Leader transitions:** for each run of consecutive matched treated half-hours of a supported family: the leader in the half-hour before the run (skipping treated half-hours, at most 24 h back) and the leaders during the run (top 3 shares); `leader_changed_share` compares them.
- **Pressure:** matched differences of leader-level `gen_tightening` / `gen_relief` (half-hour sums) are reported per family (`effect_tightening`, `effect_relief`).
- **Lead share:** the share of treated half-hours in which f itself leads.
- K5 lists the electrically sensitive DUIDs.

### 5.6 Booking reliability (RQ7, both years, final-state records)
Computed per connector and study year over bookings that list a relevant family:
- withdrawal share;
- share of live bookings whose family was invoked within ±24 h;
- share with actual times;
- median scheduled→actual start and end shifts;
- early-return (>1 h) and overrun (>1 h) shares;
- median lead time (submission to scheduled start).

The share of `invoked_unbooked` time per family is in the states table.

### 5.7 Falsification
- **Placebo:** shift each treated spell by ±7 days into f-off time and apply §5.2. Placebo 95% CIs should include 0.
- **Withdrawn bookings:** these should show no capacity effect.
- **Non-relevant families:** the spillover matrix (§5.4) shows their effects on connectors where they are not relevant. No formal test compares these with relevant-connector effects.

## 6. Support gate (applied at each key level)

| Tier | Rule |
|---|---|
| Supported | ≥5 distinct live episodes whose windows contain treated half-hours, ≥24 treated hours, match rate ≥60%, and a placebo (±7 days, ≥2 matched units) whose 95% CI includes 0 |
| Indicative | Supported except for hours, or 3–4 episodes with at least one matched unit. Shown greyed, never ranked |
| Unsupported | Everything else. Kept in downloads only, with its n |

## 7. Output lineage and provenance

- Each stage writes parquet under `data/nos_regime_v1/` (local, ignored by Git) and is re-run in full when its inputs change. There is no content-addressed cache. The execution log records every run, and the report manifest hashes every input and output.
- The report manifest records the hashes of inputs and outputs.
- Episodes carry `source`, `window_source`, `withdrawn` and `study_year`. Location attributes carry `method` and `confidence`.
- Raw archives stay local and ignored by Git. Only compact aggregates, references and documentation are committed.

## 8. Limitations (reported verbatim in the report)

1. Outages are scheduled where TNSPs expect low impact, so effects are "typical impact as scheduled".
2. Limits are dispatch-solution outputs, not physical capability.
3. Year-1 outage records are final-state only.
4. The set-to-connector mapping is retrospective, so its publication timing is not proven.
5. Two blocks per season cannot separate seasonal effects from changes in the network or plant between years.
6. Substation locations depend on a crosswalk to public datasets, and unmatched assets have no K4 attribute.
7. Flow responds to prices and offers as well as to limits, so the flow results (RQ4) are descriptive.

## 9. Implementation deviations (log references)

| Topic | Planned | Implemented | Log |
|---|---|---|---|
| Year-1/Year-2 sources | MMSDM for year 1, weekly NOS for year 2 | MMSDM final state for both years; weekly NOS used for reconciliation | E012 |
| Location coordinates | Geoscience Australia | OpenStreetMap (GA blocked) | E015 |
| Sub-region | ISP sub-region | Place + octant area key | E022 |
| Matching | Single strict rule | Three-rung ladder, ±1 half-hour | E026 |
| Placebo gate | ≥90% of supported families clean | Holds by construction; the eligible-family clean share is reported | E030 |
| Specific assets | NOS asset only | Plus element-described `EL…` assets | E036 |
| DUID pressure | DUID-level pressure by state | Leader-level tightening/relief aggregates by state + K5 sensitivities | E023 |
