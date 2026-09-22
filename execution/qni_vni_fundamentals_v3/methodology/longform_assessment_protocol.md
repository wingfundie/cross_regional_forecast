# VNI and QNI long-form assessment protocol

Written before report implementation, 2026-09-22. This is a diagnostic extension of the frozen balanced-v1 study, not a new model-selection or promotion run.

## Evidence and chronology

Process VNI before QNI. Read only balanced-v1 discovery, frozen choices, confirmation, ECMWF sensitivity, horizon and risk artifacts. Keep pilot experiments out of headline scores. Use saved primary confirmation predictions for all headline metrics; preserve all source artifacts. Hash input artifacts and record report work in the dedicated execution directory and ledger. Never call training or source acquisition from the report builder.

The global frozen choice uses early and late discovery folds. Earlier confirmation history therefore is not a wholly untouched chronological test of the entire selection procedure, even though each fitted estimator uses chronological training partitions. Describe the results as historical development evidence. Quantify discovery dates and mature confirmation coverage. Do not convert cached Holm or risk results into a new approval.

## Metrics, plots and condition diagnostics

Report each target separately at literal 24, 48 and 168 hours (leads 48, 96 and 336). Mark literal 336 hours unavailable. Calculate MAE, RMSE, signed bias (prediction minus actual), median/P90/P95/P99 absolute error, descriptive R-squared, and model/network/persistence/daily/weekly controls on identical finite rows. Publish sample size, unique origins and days. Do not blend unlike targets into a headline metric. Weight each saved prediction equally at a fixed target/horizon; other all-band summaries are labelled as sampled-lead summaries.

Compare the saved unadjusted point forecast and the already-saved calibration-adjusted q0.5 median without selecting a new winner. Measure 80% and 95% empirical coverage, width, and interval crossing. Distribution plots retain full-range summary statistics; any display clipping is labelled. Case studies at 24 hours use the best, median and worst delivery day by model MAE, explicitly selected after outcomes. They illustrate behavior rather than independent validation.

Join selected forecast-condition columns to predictions one-to-one on origin/delivery/lead. Fail on duplicate or missing joins. Use 24-hour diagnostics for endpoint demand, renewable availability, coal availability, absolute endpoint residual difference, local forecast temperature, hour, season, recent constraint switching, and magnitude of actual movement from persistence. Quartile boundaries are descriptive cut points computed within this retrospective evaluation, not deployable thresholds. Mark outcome-derived diagnostics explicitly. Publish finite/missing support and numeric ranges, and do not infer causality. Keep weather availability and its absence from the primary estimator explicit.

## Selection and feature importance

Extract actual discovery screening records, ablation scores, frozen feature counts, Jaccard overlap of early/late selected recipe sets, and missing interaction-parent audits. Report code behavior, including that the endpoint recipe excludes cross_region/weather_cross/nem_context groups but may retain other regional main effects and interactions. Do not call it strictly local-only. Show inner selection loss curves as selection evidence rather than held-out gains.

Load the saved final confirmation-fold bundles only. Report normalized LightGBM training split gain or absolute standardized ridge coefficient share separately by estimator type and target/band; these are model sensitivities, not causal attribution. Verify sample prediction reload parity. Add a bounded descriptive grouped day-block permutation check for the latest fold's 24-hour flow model: at most 2,400 chronological rows, three non-zero day-block rotations, include dependent interactions with each perturbed group. Report mean/min/max MAE change without interpreting the rotation spread as a confidence interval. Never use this post-hoc evaluation importance to change the current models.

## Deliverables and validation

Create one substantial prose HTML report for VNI and one for QNI, each with tables and real graphs in every analytical section: scope, features, selection, performance, paths, error distributions, conditions, importance, calibration, weather sensitivity, risk/uncertainty, and improvements. Graphs use embedded static images so the reports require no browser JavaScript or external runtime. Publish downloadable CSV/JSON evidence and prose Markdown companions. Embed methodology within each report and copy readable methodology alongside it. Distinguish suggestions, measured evidence and unexecuted experiments.

Validate all statistics against source counts and cached checkpoints, input/output hashes, local links, finite metrics, and chapter chart/table coverage. Inspect generated chart images. Browser layout inspection is a separate check: the previously returned browser security policy blocks opening local reports and must not be bypassed through another browser surface or local-server workaround. If no permitted renderer is available, deliver the usable artifacts with browser visual QA explicitly unverified; do not mark research complete on that basis.
