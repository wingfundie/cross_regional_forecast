# Refresh, structural changes and validation

## Refresh inputs with provenance

Use on-demand public collection for new dated observations or issued weather runs. Archive the original payload, source URL, product, run identity, delivery interval, actual receipt chronology and hash. A newly retrieved historical archive does not prove when a user could have received it historically.

For research-history extension, change the requested cutoff in the campaign configuration and run acquisition/preparation explicitly. The source manifest lists gaps. Never fill a missing invocation month from booked outages or infer available storage energy from battery output.

## Structural changes

Treat new market representation, physical circuit commissioning, testing limits and individual outage states separately. Confirm effective identifiers and direction mappings against AEMO documentation and actual data. Add a new compatibility era when the declared mechanism changes; do not relabel older observations into it to create artificial sample size.

PEC affects coupling between existing links even though this product outputs only the original six. Basslink operating-era changes can alter capacity-source semantics. Inspect equation versions, mappings and measured coverage before assuming continuity.

Unknown eras return unavailable. A model may extrapolate operating conditions within a mapped era, but cannot manufacture an unverified topology. Keep old versioned bundles reproducible when producing a replacement.

## Cache and protocol changes

Changing targets, source hashes, modelling features, conditions, chronology or fitting code invalidates downstream fitting checkpoints. Updating presentation alone rebuilds reports from cached scores. Preserve the configuration, methodology, event catalogue, source register, data hash and code signature for each run.

The runner verifies the exact PID/create-time owner before reconciling a stale lock. Do not run duplicate campaign owners. On a resource cap or failure, read the ledger and resume the incomplete stage; partial results are not a completed campaign.

## Acceptance checks

Run focused tests after changing semantics, then the complete repository suite:

```text
python -m pytest -q tests/test_conditional_regimes.py
python -m pytest -q
python scripts/run_conditional_regimes.py --stage validate
```

Verify signed targets, complete half-hours, quarter/time boundaries, exact topology requirements, incident purging, training-only transformations, missing-input behaviour, coherent vintages, immutable named assumptions and hash-verified package loading. Install the wheel in an independent location and test without the repository import path.

Inspect the selector and reports at desktop and narrow widths. Check the hero, a full chart, dense table, interval evidence, controls, empty results and download links. The workbook needs a visual check of every populated sheet and representative value reconciliation. A successful export alone is not visual verification.

## Evidence gates

Review central error, interval coverage/width, capacity overstatement, restriction and forced-flow recall/precision, false alerts, independent incident counts and availability. Use identical rows for comparisons and publish the excluded support. Do not promote a method because it wins average MAE while failing risk or provenance gates.

Historical as-of replay requires original forecast vintages and verified availability. If those are missing, keep that scorecard unavailable and state the conditional claim. New receipt logging supports future confirmation but does not backfill the missing historical evidence. Scheduling, publication and production promotion remain separate user decisions.
