# Project agent memory

IC FLOW FORECASTING is a NEM interconnector research and forecasting lab. `README.md` is the current project map; use its linked execution guides and methodology files instead of inferring the active workflow from filenames alone.

## Architecture

- Keep the three model stacks distinct. `run_pipeline.py` and the top-level `nemic` modules implement the original six-interconnector conditional backtest; `nemic.experiments` contains the newer QNI/VNI diurnal, constraint and NOS research campaigns and saved bundles; `nemic.production` is a provider-neutral registry/routing scaffold. Do not mix their feature contracts, bundle identities or performance claims.
- The original six-link system is fundamentals-rich but uses realised future demand, renewables and weather; describe its results as conditional research. The newer QNI/VNI system is network-state-rich but lacks a fully verified live issue-time feature feed. The production scaffold is not a deployed or scheduled forecast service.
- Treat saved QNI/VNI bundles as research-only unless their manifests and a later promotion record explicitly say otherwise. Use `docs/VNI_SAVED_MODEL_GUIDE.md`, `docs/QNI_SAVED_MODEL_GUIDE.md` and `docs/PRODUCTION_PIPELINE_GUIDE.md` for supported inference paths.
- Add forecast fundamentals through a versioned feature contract and a separately evaluated challenger. Never put future demand, VRE, weather or availability values into lag/network columns merely to reuse an existing bundle.

## Data and time semantics

- Preserve raw timestamps and source metadata, but align market calculations to fixed NEM time (UTC+10) and interval-ending conventions. Keep the native five-minute observations; form half-hour targets only according to `nemic/prepare.py` and its tests.
- Directional targets are not interchangeable: import capacity is represented as `-IMPORTLIMIT`, negative directional limits can encode forced flow, tight targets are the minimum across the six five-minute intervals, and `own_anchor` is target-specific at origin minus 30 minutes. Do not silently average incomplete intervals or clamp signed values.
- AEMO reported interconnector limits are dispatch-solution outputs, not maximum secure physical transfer capability. Preserve that qualification in models and reports.
- For forecast-valid experiments, require as-of availability using both issue and actual receipt/publication time. Preserve source, product, run/vintage, delivery interval, receipt time, age and hashes. Do not mix vintages within a coherent regional or cross-regional feature row.
- Never substitute realised future inputs for historical issued forecasts without an explicit conditional-research label and a separate genuinely issue-time evaluation.
- Download only required NEMWEB tables/files. Raw archives, extracted tables, fitted models and large prediction outputs stay local and ignored by Git; commit source, documentation, manifests and compact aggregate evidence. Record source hashes and data coverage before deleting temporary data.

## Modelling and evaluation

- Use chronological train, selection, calibration, alert-tuning and evaluation partitions. Fit seasonal references, contraction thresholds, feature selection and calibration on eligible pre-evaluation history only.
- Benchmark every candidate against persistence, seasonal baselines and matched AEMO vintages where available. Select separately by connector, target and lead band; added complexity must beat the simple alternative on identical rows.
- Use rolling or walk-forward out-of-sample predictions for historical performance. Never score a final fitted model on its training period or feed downstream models realised/fitted QNI/VNI values; use out-of-fold upstream forecasts.
- Report point error, skill versus baseline, event recall/precision and false alerts, interval coverage/width, sample counts and performance by horizon, season and delivery period. High average skill does not override failed risk, calibration or provenance gates.
- Current measured results and limitations belong in the linked result documents, not this file. Check `BACKTEST_REPORT.md`, `docs/RESULTS_DATA_AND_FEATURES.md`, the QNI/VNI execution guides and the relevant report manifest before quoting numbers.

## Long-running campaigns

- Use the campaign config, ledger, manifests and checkpoints as the source of truth. Before resuming, inspect the ledger and process tree; if one healthy worker owns the stage, do not start another. Reconcile stale ownership only when no healthy owner exists, then resume the exact incomplete stage.
- Report status as completed, active and remaining stages backed by artifacts or process evidence. Do not call a campaign complete before model, report, validation and required sign-off stages are actually complete.
- Rebuild reports from cached results when supported; do not retrain models for a presentation-only change. Preserve content-addressed artifacts and invalidate caches when their declared data, code, config or protocol dependencies change.

## Reports and verification

- Research deliverables should contain substantive prose, charts, data tables, methods, limitations, source/provenance notes and downloadable evidence. Produce Markdown plus self-contained offline HTML when the task asks for a readable report.
- Validate report manifests and hashes, offline dependencies, links/anchors and representative desktop/mobile layouts. State plainly when visual browser verification was not possible.
- Run `python -m pytest -q` for repository changes, plus the workflow-specific checks in the relevant execution guide. Use narrower tests during development, then the full suite before declaring an end-to-end campaign complete.

## Git and publication

- Do not commit, push, merge or create a PR unless the user requested publication in the current task. When requested, exclude raw/local data and unrelated working-tree files.
- The repository's default branch has historically been `codex/nem-forecast-lab`; do not assume `main` or `master`. Verify the remote default branch, ancestry and local/remote SHAs. If claiming a merge, distinguish a PR merge from a direct push and verify the requested content exists on the remote branch.

## Maintaining this file

Keep only cross-session guidance that changes future agent behaviour. Point to authoritative code or documents for details, update stale statements when architecture changes, and prefer rewriting or pruning over appending.
