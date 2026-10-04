# QNI/VNI long-range forecast improvement results

> historical development using original-vintage publication proxies; prospective confirmation required

Completed cells: 10. Improvement demonstrated: 0. Baseline retained: 10.

| Connector | Target | Winner | Skill vs calendar | Skill vs persistence | Positive bounds vs both | Decision |
|---|---|---|---:|---:|---|---|
| VNI | export_tight | calendar | 0.00% | 25.66% | False | retain_baseline |
| VNI | import_tight | boosting | -1.29% | 29.32% | False | retain_baseline |
| VNI | export | boosting | -4.19% | 29.26% | False | retain_baseline |
| VNI | import | calendar | 0.00% | 22.88% | False | retain_baseline |
| VNI | flow | boosting | 3.01% | 22.32% | False | retain_baseline |
| QNI | export_tight | boosting | 17.85% | -42.71% | False | retain_baseline |
| QNI | import_tight | ridge | 36.88% | 9.58% | False | retain_baseline |
| QNI | export | boosting | 7.69% | -50.11% | False | retain_baseline |
| QNI | import | ridge | 39.25% | 12.19% | False | retain_baseline |
| QNI | flow | ridge | 6.47% | -26.26% | False | retain_baseline |

## Methods and limitations

Daily 08:00 fixed-NEM-time origins use coherent original-vintage MT PASA publication proxies. Training, selection, calibration and evaluation are chronological and delivery-maturity purged. VNI is evaluated before QNI under the same frozen procedure.

The primary score weights days 1–7 at 75% and days 8–14 at 25%. A challenger is accepted only with at least 2% weighted MAE skill against both the seasonal calendar model and target persistence, plus positive seven-day moving-block confidence bounds against both baselines in both primary lead bands. Intervals are labelled calibrated only at held-out coverage of at least 77% and 92% for nominal 80% and 95% intervals.

These are historical development results using publication-time proxies. They do not establish live issue-time performance, and no model is promoted by this campaign.
