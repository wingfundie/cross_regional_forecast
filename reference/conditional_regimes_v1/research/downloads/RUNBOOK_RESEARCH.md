# Research execution and recovery

## Purpose and interpretation

This campaign builds conditional distributions of AEMO-reported dispatch limits. It estimates limits under specified conditions. It does not assume those conditions can be forecast across the quarter, and it does not estimate maximum secure physical transfer capability.

## Inputs and ownership

Use the repository environment and requirements. The authoritative configuration is `configs/experiments/conditional_regimes_v1.json`; methodology and event definitions live alongside this guide. Runtime data are in `data/forecast_experiments/conditional_regimes_v1` and remain local.

Before resuming, inspect the campaign `ledger.json` and `owner.json` and the named process. A healthy owner is identified by both PID and process creation time. The runner refuses overlapping owners. A stale lock is reconciled only when that exact process is absent. Never start a second copy just because no new progress line has appeared.

```text
python scripts/run_conditional_regimes.py --stage status
```

Stages are `inventory`, `acquire`, `events`, `prepare`, `pilot`, `evaluate`, `assess`, `bundle`, `report`, `validate`. Run a specific stage with `--stage NAME`; `--stage all --resume` reuses verified artifacts. Evaluation folds additionally carry narrow signatures of their data, fitting code, configuration and protocol. A changed dependency invalidates the relevant fitted checkpoint; report formatting alone is not a modelling dependency. The assessment stage applies each saved fold's alert policy and conservative independent-day risk diagnostics; its contract is in ASSESSMENT.md.

## Acquisition and preparation

Inventory first verifies retained inputs and records hashes. Acquisition requests only required monthly tables and missing current-period dispatch originals. It records source URLs, bytes, retrieval chronology, hashes, parsed-output hashes and gaps. Daily archives and current reports are deduplicated. A current dispatch archive is not presumed to contain an invocation or outage booking feed.

Weather extension is realised/reanalysis research. An explicit single-run forecast is a different information class. Do not splice later weather runs or revised outage schedules into a historical as-of feature row.

Preparation preserves physical run selection, raw source timestamps, fixed UTC+10 and complete six-observation half-hours. Import direction is minus raw IMPORTLIMIT; signed negative limits are valid outcomes. TOTALDEMAND is already net of rooftop PV. The August 2026 data-anomaly day is retained in source data but quarantined from the primary inference/evaluation panel for QNI and VNI.

The engineering lookup is frozen on the first training end, before selection/evaluation. The archive contains changing standing records, so coverage is explicit. Group dispatch is unavailable if required unit observations are missing. Do not replace missing DUIDs with zero.

## Pilot and modelling

The VNI/Heywood pilot chooses among the declared half-hour radii and neighbour-day counts using pre-evaluation rows. The same grid is used for the other links. Models are fitted inside compatible eras. Additive fitting uses a smaller deterministic sample cap, L2 shrinkage and a convergence-checked smooth-pinball optimiser. The exact initial linear programme was replaced after the timing pilot. Targets and same-interval reported setters are excluded from model/distance features.

Chronological folds allocate training, selection, quantile calibration, alert tuning and evaluation separately. Incidents crossing a boundary are removed from its earlier partition. Every retained prediction records the fold and method. Final full-history bundle fits are never included in the historical scorecard.

The modelling process has a 48-hour cap, two numerical threads and at most two workers. Check memory and free disk when changing data breadth. A cap failure leaves the campaign incomplete and retains finished fold checkpoints. Resume the exact failed stage after resolving the condition; do not invent completion from partial scores.

## Cached reporting and handoff

```text
python scripts/run_conditional_regimes.py --stage report
python scripts/run_conditional_regimes.py --stage validate
```

Report rebuilds load saved tables and the bundle. They do not retrain. The report stage creates the workbook's typed JSON payload; the documented spreadsheet builder creates the XLSX. Rebuild reports after that export to include its verified download and hash. A source acquisition gap or unavailable as-of evaluation remains visible in the reports even when the usable conditional package is delivered.

Completion requires the package/wheel, bundle, selector, workbook, three reports and Markdown companions, four runbooks, compact evidence, source/report verification, package installation checks, full repository tests and visual QA. Publication, route promotion and recurring scheduling require separate user instructions.
