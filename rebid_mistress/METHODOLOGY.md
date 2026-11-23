# Frozen methodology — 10 October 2026

## Scope and clocks

The 288 five-minute interval endings run from 04:05 on 10 October through 04:00 on 11 October in fixed NEM time (UTC+10). Blocks are morning 04–10, daytime 10–16, evening 16–22 and overnight 22–04, assigning boundary interval endings to the block they finish. The NSW price cap is $23,200/MWh at interval ending 07:20. Original DISPATCHIS file generation at 07:15:13 is the information proxy; actual dissemination and participant receipt remain unverified. Compare revision membership against 07:20 as a timing sensitivity.

SCADA values refer to interval start, despite an interval-end identifier. Preserve the native timestamp and align observed power five minutes earlier. Obtain the 11 October 04:05-labelled SCADA file for the last observation at 04:00. Dispatch targets retain their endpoint timestamps. Neither series is an interval-average energy quantity. All power metrics use MW; block summaries never add MW over time. Native source fields keep their original engineering units, including storage energy; displayed SOC is a percentage only when registered capacity supports it.

## Offers and stacks

Retain both accepted submission time and delivery interval. Full BIDDAYOFFER and BIDOFFERPERIOD_SPARSE reconstruct each complete offer: contiguous period ranges must cover 1–288 exactly once. Key by trading day, DUID, service, direction and offer timestamp, checking header uniqueness and retaining native versions/reference IDs. Pairing failures stop reconstruction. Compare each revision against its predecessor for the same delivery interval and against the frozen pre-signal offer. Original records retain structured event/awareness/decision times as unvalidated participant declarations.

Within-day daily price bands remain fixed. Detect any price-ladder exception rather than forcing this assumption. Changes in availability, ramp, fixed-load, energy/storage limits and start profile are distinct from band-volume movements. For band changes, positive and negative changes identify minimum redistribution, net added offered volume and net removed offered volume; do not claim an exact source-to-destination matching when several bands change.

Generation thresholds are nominal bid prices $0, $100, $300, $1,000 and $10,000/MWh. Charging willingness uses purchase bids at or above a threshold. Raw stacks and availability-limited volume are separate; low-priced volume alone is not a dispatch instruction. Upper permissible unit bid prices can differ from the regional cap because of loss-factor treatment. Report actual native prices, not assumed common band values.

Bidmove/dispatch tracking verifies which accepted offer became effective; accepted future-period revisions remain evidence even when replaced before dispatch. Revised past periods are retained but excluded from claims of prospective positioning. No-op revisions remain in the reason ledger.

## Responses and inference

Freeze the six complete SCADA observations at 06:45–07:10 as the immediate median reference. Missing reference observations produce an unknown baseline. Identify output increases of at least 5 MW, retaining smaller exact bid movements. Show first bid, target and observed-output changes independently. A cheaper offer without later output is a willingness/readiness observation; an output increase before a rebid is not caused by that later rebid. Affected delivery periods must overlap subsequent output when associating the two.

The frozen later-period reference is the last archived original-vintage AEMO predispatch run processed before the signal. Compare only native half-hour target times. It is AEMO projected generation, not a participant’s internal plan. Processing time is an availability proxy, not verified receipt time. Public P5MIN price forecasts supply advance-warning context. Never use a later vintage as evidence available before the signal.

For gas, track transitions across 5 MW, declared start profiles, ramp capability and dispatch targets. Crossing 5 MW is not a verified synchronisation event. Public DISPATCHLOAD ramp rates are MW/hour; five-minute envelopes divide them by 12. Bid ramp rates are MW/min and multiply by five for a displayed five-minute capability. A near-envelope observation does not prove engineering maximum performance.

For batteries, retain signed bidirectional dispatch and separate legacy LOAD/GEN units. −100 to +100 MW is a 200 MW system swing but 100 MW discharge. Initial measured storage and projected ending storage stay distinct. FCAS is deliberately excluded, limiting interpretation of headroom and response shortfalls.

Report grades: observed facts supported by exact source records; strategic explanations plausible when timing and operational evidence fit; unresolved/contradicted where evidence is missing or conflicting. Participant reason text is quoted verbatim with every narrated rebid. Contingency preparation and evening protection are tested hypotheses, never automatic labels for post-event changes.

## Physical portfolios

Use registered participants and sourced corporate operating relationships. Ownership is separate from dispatch control; a PPA alone does not establish complete bidding rights. Unknown rights remain separate. No actual contract or retail exposure is inferred.

Only scheduled, observed, non-duplicated units enter replacement calculations. Coal and gas/battery pools are compared at the same timestamp and within the same region. Coal shortfall is the positive difference between reference and actual aggregate coal MW. Additional replacement is the positive difference between actual and reference aggregate gas/battery net MW. Matched replacement is the smaller amount; residual shortfall is the remainder. Complete constituent coverage is required, and no MW is allocated twice.

Use both the immediate observed reference and frozen forecast endpoints. A separate registered-capacity-minus-offered-availability scenario shows a declared gap; it is not automatically a technical outage or lost expected generation. Existing gas output and incremental gas output answer different questions. Common control, compatible reasons, timing and output can support physical replacement, not establish a financial hedge.

## Coverage and verification

Every identifiable plant has an account even with no offers or missing observations. Gas includes natural gas, coal-seam/mine methane and biogas where AEMO fuel metadata identifies them; solid coal excludes methane and biomass. Non-scheduled auxiliaries do not inflate scheduled-portfolio capacity or output. Standing data age, unmatched participants and source failures remain explicit.

Full accepted-offer and dispatch-effective reconciliation, unique 288-interval price coverage, direction/sign checks, frozen-vintage checks, unit/plant coverage, portfolio identities, reason preservation, report/download hashes, offline dependency checks and desktop/mobile browser QA are completion gates. The repository test suite is required. No historical-control estimates, causal dispatch counterfactuals or financial-hedge quantities are produced.
