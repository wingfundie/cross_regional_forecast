# Backtest protocol and reproduction

This is the protocol actually executed, documented on 11 September 2026. It complements the [methods and research](METHODS_AND_RESEARCH.md) and [results report](../BACKTEST_REPORT.md). All timestamps below are fixed UTC+10 NEM time and interval-ending. An origin is the issue time; delivery = origin + lead × 30 minutes.

## 1. Chronological partitions

| Stage | Exact time rule | What can be learned |
|---|---|---|
| Training | Targets after 2023-09-01 00:00 and at or before 2025-09-01 00:00 | Regressors, target scales, setter encodings and positive seasonal references |
| Method selection | Validation origins at or after 2025-09-01 00:00; deliveries at or before 2025-12-01 00:00 | Lowest raw MAE among six candidates per connector/target/band |
| Residual calibration | Origins at or after 2025-12-01 00:30; deliveries at or before 2026-02-01 00:00 | Empirical residual distributions for the selected candidates |
| Alert tuning | Origins at or after 2026-02-01 00:30; deliveries at or before 2026-03-01 00:00 | F2 probability cutoff per limit target/connector/band |
| Final test | Origins from 2026-03-01 00:00 through 2026-08-31 23:30; deliveries at or before 2026-09-01 00:00 | Evaluation only; all fitted choices remain frozen |

The 00:30 starts in calibration and alert tuning follow the implemented right-sided timestamp indexing. A boundary delivery at 00:00 represents the preceding half-hour. Training observations before a test origin may be used as lagged inputs; this is legitimate historical information. Origin/target paths crossing a fitting or validation subperiod boundary are excluded. This is not a blanket seven-day embargo, a shuffled split or repeated rolling refitting.

Lead bands are 1–12, 13–48, 49–144 and 145–336 half-hours: 0.5–6, 6.5–24, 24.5–72 and 72.5–168 hours. Display shorthand such as “6–24h” refers to those discrete bands.

## 2. Step-by-step execution

1. Download and retain public source archives with URLs/checksums. Extract versioned table records and preserve source weather JSON.
2. Select physical dispatch records, apply sign conventions and aggregate six observations per half-hour. Prepare regional drivers, prices and weather. Audit missingness, complete grids and connector identifiers.
3. Compute training-only scales, category encodings and positive seasonal reference limits. Save dates and audit evidence.
4. Fit the 15 static and five network regressors. Network origins begin only when all requested lag positions exist; the earliest saved training origin is 2023-09-08 01:00. Seed 741 samples one lead from each band per eligible training origin. Discard samples whose delivery exceeds the training boundary.
5. Generate validation predictions at every eligible half-hour origin for **14 leads**, in half-hours: `1, 2, 4, 8, 12, 24, 48, 72, 96, 144, 192, 240, 288, 336`. Validation is not exhaustive over 336 leads.
6. Use September–November deliveries to select the lowest raw MAE candidate for each of 120 cells (6 connectors × 5 targets × 4 bands). Exact ties use candidate order: persistence, seasonal, fundamentals, weather, availability, network.
7. Use December–January origin/target paths to estimate selected-model residual distributions. Each cell requires at least 100 residual observations. Add empirical residual quantiles to predictions.
8. Use February origin/target paths to select restriction alert cutoffs by F2. Freeze `models/selection.json`, including candidate, residual quantiles, event counts and cutoff/default note. Do not refit using validation.
9. Evaluate all available half-hour test origins and every lead 1–336 whose delivery is in the test window. Store seven-day origin chunks. The last origins have fewer valid leads because observations stop at the data endpoint; future outcomes are not filled.
10. Aggregate forecast errors and restriction metrics by connector, target, band, method and slice. Compute approximate block-bootstrap uncertainty for selected-versus-baseline MAE improvements.
11. Match original AEMO predispatch vintages to identical origin/delivery pairs and calculate separate comparison scores.
12. Run the scenario example, integrity tests and completion audit; generate the report from saved result tables.

Validation samples lead positions sparsely whereas the final test weights every lead equally within its available range. Thus validation selection/calibration and test have different lead mixtures. That is a limitation of this implementation, especially for broad long-horizon bands.

## 3. Information controls and their limits

Network features normally observe no later than origin minus 30 minutes. Target lags at 1, 48 and 336 half-hours, current setter/regime fields, other-link flows and available generation are historical only. Archived `LASTCHANGED` values later than the origin censor the affected dispatch features. One late half-hour on 5 September 2024 affected all six links: the 13:30 record changed at 14:10:07 and is unavailable to the 14:00 origin.

Origin regional generation availability is masked when the connector publication check indicates late dispatch data; this is a common-publication proxy, not an independent regional vintage archive. Persistence falls back one additional half-hour when its usual record is late; the code does not implement an unlimited search through older publications. At lead 336, weekly seasonal persistence uses the same slot two weeks earlier because the one-week reference would otherwise equal the unavailable issue interval.

Future realised flow, limits, constraint setters, thermal availability and prices are excluded from features. Future realised demand, renewables and weather are explicitly allowed. Therefore the run has chronological model-selection safeguards but is **not a fully issue-time operational backtest**. Archived actuals can include later revisions, and timestamp censoring does not reconstruct all superseded records.

The final test must remain untouched for selecting changes. Any new tuning motivated by these test results should be assessed on a new held-out period. Reusing March–August 2026 to choose improvements would turn it into further validation.

## 4. Metrics and denominators

For each forecast pair, define error = prediction − actual, in MW. Raw candidates use their point predictions; `selected` uses the residual-adjusted P50.

| Metric | Calculation / interpretation |
|---|---|
| MAE | Mean absolute error; main point-forecast selection criterion |
| RMSE | Square root of mean squared error; increases emphasis on large misses |
| Bias | Mean signed error; positive means overprediction |
| 80% coverage | Fraction with P10 ≤ actual ≤ P90, endpoints included |
| Interval width | Mean P90 − P10, MW |
| Pinball | Average loss over q = 0.1, 0.5, 0.9, where loss is q(actual−forecast) for nonnegative residual, otherwise (q−1)(actual−forecast) |
| Recall | TP/(TP+FN): fraction of actual restricted forecast pairs flagged |
| Precision | TP/(TP+FP): fraction of flagged pairs actually restricted |
| F2 | 5TP/(5TP+4FN+FP), placing extra weight on missed restrictions |
| Brier | Mean squared difference between restriction probability and the binary event |

For the four limit targets, actual event = limit < seasonal threshold; predicted event = probability ≥ frozen cutoff. Undefined ratios are missing rather than evidence of perfect performance. Flow has no restriction classifier score. Interval/probability metrics apply to the selected calibrated forecast, not to every raw candidate.

Scores use origin/lead pairs, not unique delivery intervals or distinct outage episodes. The same actual half-hour can appear against many issue times. Long events can therefore contribute many observations. Aggregate TP/FP/FN before computing pooled precision or recall; do not average cell ratios without considering denominators. Weighted coverage uses forecast counts.

Slices are: all observations; restricted observations (either **average** directional actual limit below its threshold, shared across targets); intervention half-hours; and delivery season. Season is assigned from the interval-ending timestamp, so the 2026-09-01 00:00 endpoint receives a spring label even though its half-hour falls on 31 August. The independent test otherwise covers autumn and winter, not a full seasonal year.

## 5. Approximate uncertainty in baseline skill

For each connector/target/band, daily absolute-error sums and counts are grouped by **origin date**. The bootstrap draws contiguous seven-day blocks, concatenates them and truncates to the original number of days. Blocks are non-circular; possible starts run from the first day to the last complete seven-day block. There are 400 replicates with seed 741.

For each replicate, improvement = baseline MAE − selected MAE, using resampled error sums divided by resampled counts. Positive values favour selected. `skill_confidence.csv` records the mean bootstrap improvement and the 2.5th/97.5th percentiles. Its improvement column is the bootstrap mean, not necessarily the exact observed MAE difference from `scores.csv`.

Blocks partially address dependence from overlapping forecasts. They do not eliminate regime changes, long events or dependence beyond seven days. The intervals are approximate, with no multiple-comparison adjustment across 120 cells. They are uncertainty intervals for aggregate skill differences, distinct from the per-forecast P10–P90 intervals.

## 6. AEMO comparison

Original predispatch archives preserve issue vintages. File creation time is used as issue time; add a one-minute ingestion allowance and round upward to the first eligible half-hour origin. This is an assumed availability buffer, not measured network latency. Within duplicate origin/delivery/connector records, the latest issue and physical intervention preference determine the retained row. Require issue time before origin and delivery after origin.

Match one-to-one with the stored test predictions on origin and delivery, and compare flow, average export and average import in MW. Import uses the same sign transformation. Available matched leads span 0.5–39 hours; no seven-day AEMO forecast or five-minute tight-limit forecast is fabricated. Saved matched files support reproduction of matched-pair MAE/RMSE.

This is an asymmetric benchmark: AEMO used forecast inputs, while INTERFLOW receives future actual fundamentals/weather. It cannot establish operational superiority over AEMO. Nor is AEMO's predispatch point quantity necessarily identical in temporal construction to a mean of subsequent five-minute dispatch targets.

## 7. Completed evidence

The saved completion audit reports:

- Six connectors, each with 8,832 origins, all 336 lead values represented and 2,911,272 available origin/lead pairs.
- 17,467,632 pairs overall and 87,338,160 target forecasts.
- Finite, ordered P10/P50/P90 values and all candidate methods scored.
- A 2,016-row scenario example, six connectors × 336 leads.

The selected forecast beat persistence in 92/120 connector/target/band cells. Weighted nominal 80% coverage was 72.3%. There were 2,876,052 matched AEMO pairs. These are completed-run results, not acceptance thresholds or evidence that every connector is ready for operational use. Detailed errors and restriction performance are in the [generated report](../BACKTEST_REPORT.md).

Eight integrity tests passed in `tests_final.log`: complete target grids; raw signs/aggregation; training and forecast timing; isolation from future network outcomes and prices; delayed-publication censoring; training-only positive references; rejection of invalid scenario grids; and rejection of future scenario origins lacking observed history. `scripts/verify_complete.py` separately checks exhaustive output coverage. These checks do not constitute exhaustive desktop UI testing, physical network validation or verification of every source-data revision.

## 8. Reproduction and cache handling

Run from the project directory with the package versions recorded in `results/environment.json` where possible:

```powershell
python -m pip install -r requirements.txt
python run_pipeline.py
```

`requirements.txt` is the installation specification; the environment artifact records the versions actually used. Retaining raw responses is important because public archives or reanalysis can later be revised.

| Step | Command run by the pipeline | Output purpose |
|---|---|---|
| 1 | `python -m nemic.ingest` | NEMWEB actual archives and extracted tables |
| 2 | `python -m nemic.weather` | ERA5 source and transformed weather |
| 3 | `python -m nemic.prepare` | Targets, drivers, seasonal references, split/data audits |
| 4 | `python -m nemic.model` | Fitted regressors and training proof |
| 5 | `python -m nemic.model validate` | Validation predictions and frozen selections/calibration |
| 6 | `python -m nemic.backtest` | Exhaustive predictions, scores and skill intervals |
| 7 | `python -m nemic.benchmark_download` | Original AEMO predispatch archives |
| 8 | `python -m nemic.aemo_benchmark` | Matched vintages and comparison scores |
| 9 | `python -m nemic.scenario` | Historical scenario template/example |
| 10 | `python -m unittest discover -s tests -v` | Integrity tests |
| 11 | `python scripts/verify_complete.py` | Completion audit |
| 12 | `python -m nemic.report` | Generated report and summary |

`python run_pipeline.py --from-step N` resumes at step N and executes every subsequent step. It is not a command to execute only one step. To regenerate only the report, run `python -m nemic.report`.

Downloads, extracted tables and fitted models are cached. Model reuse is largely based on existing files, with an additional safety marker for network models. Test partitions have a signature covering selected configuration, processed targets/drivers, model source and network model files. This is **not complete automatic dependency invalidation**: not every static-model/cache dependency is covered. A plain rerun is suitable for resuming this retained experiment, but does not guarantee a fresh fit after changing inputs or settings.

For a new experiment, use a separate project/output copy, preserve this run's evidence, and begin with empty model and derived-result caches. Preserve original downloads only when their dates/schema are appropriate. Then rebuild preparation through reporting. Do not mix old fitted artifacts with a changed split, feature set or target definition. No destructive cache-cleanup command is supplied here.

The executed preparation also used `scripts/complete_rooftop.py` to supplement a weekly archive edge and `scripts/refresh_reference.py` to correct the reference definition. Their retained source additions remain in this workspace. Current `prepare.py` implements the corrected positive-reference rule. For reconstruction from a completely empty data directory, inspect the missingness audit and supplemental archive logic rather than assuming the standard sequence alone will necessarily reproduce the same rooftop cells.

## 9. Audit trail and reviewing outputs

The [improvement roadmap](IMPROVEMENT_ROADMAP.md) defines proposed follow-up experiments, event-level metrics and protection of a new untouched evaluation period. These additions are not part of the completed backtest described here.

| Artifact | What to check |
|---|---|
| `data/manifest.json`, `data/weather_manifest.json` | Original URLs, weather coordinates/parameters and checksums |
| `results/data_audit.json`, `split.json` | Completeness, signs, missing drivers and dates |
| `results/training_proof.json` | Training pair count, maximum target, seed and pair hash |
| `models/selection.json` | All 120 choices, calibration quantiles and cutoff defaults |
| `results/validation_leaderboard.csv` | Candidate MAEs used for selection |
| `results/predictions/`, `test_proof.json` | Forecast-pair evidence and test coverage |
| `results/scores.csv` | Raw and selected scores with counts and slices |
| `results/daily_errors.csv`, `skill_confidence.csv` | Bootstrap inputs and approximate skill intervals |
| `results/aemo_vintages.parquet`, `aemo_audit.json`, `aemo_matched/`, `aemo_scores.csv` | Issue-time alignment and matched comparison |
| `results/completion_audit.json`, `environment.json` | Completion status and runtime package versions |
| `results/scenario_template.csv`, `scenario_example.csv` | Input structure and executed all-connector example |

Review performance per connector, direction and lead band before using pooled summaries. Check missed restrictions, false alerts, bias and coverage together. Seven-day forecasts remain conditional on supplied future paths; there is no live input forecast collection or scheduled operational refresh in this build.
