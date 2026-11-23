# Frozen methodology — line outage risk v1

## Time, assets and treatment

Window `(2024-09-01 00:00, 2026-09-01 00:00]`, fixed NEM UTC+10, interval-ending. Selection is before 2025-09-01; confirmation is after. Native five-minute prices, dispatch and constraint observations are retained. Half-hours require six observations; daily price summaries require 288. Dispatch movement across a missing interval is missing. Equipment treatment is `(actual start, actual end]`; set invocation is inclusive at both interval-ending endpoints. These different conventions are deliberate.

Use every line equipment row linked to an outage, rather than only the old primary asset. Match equipment by ELEMENTID and effective validity; retain aliases and parallel circuits. Administrative successors are already collapsed by the base episode builder. Withdrawn, cancelled, secondary and scheduled-only records remain in the audit but cannot establish physical line unavailability. Overlapping or five-minute-adjacent verified windows are one independent event. Multi-equipment events are flagged: the observed response cannot be assigned exclusively to one line.

## Selection

Mandatory lines 6/8, up to 24 more documented important corridors, 12 additional large selection-period volatility associations, then geographic/mechanism coverage to 50. Outcome selection uses year 1 only. Assets lacking a resolved region or identity remain in the audit. Eight additional deep dives use four importance and four empirical selections. If evidence is sparse, retain a case-study tier rather than replacing the two mandatory lines.

## Price and network outcomes

Absolute five-minute RRP change; daily standard deviation and P95–P5 range; interval shares above $300/$1,000 and below $0/−$100; historical region/season P99/P1 thresholds fitted in selection only; tail duration and severity. RRP is used for market prices, physical dispatch uses the inherited constraint-study run selection, and intervention/price overrides are flagged. No log returns or clipping. Interconnector flow, IMPORTLIMIT and EXPORTLIMIT preserve their native signs; reverse capacity = −IMPORTLIMIT. Limits are dispatch outputs, not secure physical transfer capability. Marginal values are never summed as outage price impacts.

## Comparisons and evidence

The primary matched comparison requires the same five-minute time of day, weekday/weekend type, season and study year, within ±21 days, the same signature of other verified high-voltage equipment outages in the affected region, and demand, available VRE and temperature within selection-period bins. Available VRE is a sensitivity covariate: an outage may affect reported availability, so the primary model uses demand and temperature, with pre-event available generation documented separately. Do not match on binding, flow, dispatched generation or realised prices. Select up to five deterministic nearest controls. Relaxed co-outage-count matching is sensitivity only. Configuration changes and multi-asset events are disclosed; any unresolved material change prevents a causal interpretation.

Estimate treated-minus-control means for movement and tail flags, with independent-event bootstrap confidence intervals (1,000 replicates). Reused controls and long events are disclosed; five-minute rows are not independent observations. Minimum numerical support: five verified independent episodes, 24 treated hours, 60% matching, maximum absolute standardised mean difference ≤0.2. Apply shifted ±7-day placebo, pretrend, leave-one-event-out and strict-versus-relaxed checks. Apply Benjamini–Hochberg adjustment to the declared primary movement tests. Confirmation-period results are never combined with the selection screen to claim validation. Failed gates withhold numerical headline effects; descriptive event measurements remain available and labelled.

## Mechanics, event studies and bids

Keep linked NOS sets, invoked membership, binding and limit-setting separate. Effective-date/version joins are mandatory; unresolved membership is recorded. LHS terms, RHS/LHS, marginal values, monitored element/contingency descriptions and conditional interconnector sensitivities explain mechanics. Conditional bounds are not physical branch-flow simulations. Connection-point terms are mapped to DUIDs only within DUDETAILSUMMARY validity. Retain unmatched terms. For each deep dive choose maximum stress, median stress and minimum stress events, or all available events where fewer than three. The selection is descriptive, not confirmatory. Include 48-hour pre/post timelines and restoration evidence.

Offer analysis retains all energy offer revisions for selected dates and affected DUIDs. Match price-band and volume-band records by the native offer identity and publication/effective timing, never by the last offer of the day. Where identity or receipt provenance is unavailable, report revisions and reasons descriptively and withhold a dispatch-stack counterfactual. No inference about strategic intent.

## Outlook and limits of claims

Newest verified snapshot, generation time and actual download receipt are retained. Horizons 0–7/8–30/31–90/91–365 days. Historical snapshots establish publication-time replay only unless actual historical receipt is archived. No historical price-risk probabilities pass a live-use gate without reception provenance, chronological evaluation and calibration. Bookings without direct asset mappings get an explicit unresolved state. Overlapping outage effects are not additive. Outlook prose states conditional mechanisms and suppresses unvalidated numerical probabilities. The report does not substitute realised future fundamentals for forecasts.

## Provenance and verification

Hash all consumed local inputs and source references. Persist stage ownership, checkpoints and coverage diagnostics. Source/definition/parameter/code changes invalidate dependent caches. Download only required tables or event windows; retain source hashes and coverage before deleting temporary files. Verify source identities, timestamp rules, signed limits, missing data, intervention, version joins, negative tests, deterministic selection, offline dependencies, anchors, downloads, full pytest and desktop/mobile layouts. Record incomplete work in the ledger and report rather than declaring an unverified stage complete.
