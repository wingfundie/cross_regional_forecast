# QNI diurnal and NOS modelling results

Run date: 16 September 2026. Outcomes extend through August 2026 in NEM time (UTC+10). These are historical development results on reconstructed network information, not prospective performance.

## Verdict

The frozen QNI policy improves band-0 minimum-export MAE by **4.6%** versus persistence and minimum-import MAE by **-8.7%**. Model routing is target- and horizon-specific and is listed below; it is not copied from the VNI verdict.

Scheduled NOS point-model skill is evaluated on the source-common population and remains a separately identifiable challenger. The matched pre-model audit contains **560** candidate bookings, **18** matched direction episodes and **0** supported recurring entities. Unsupported assets or sets are not labelled as highest-impact.

## Rolling model results

MAE is the selection objective. MAPE is assessment-only and is reported where `|actual| ≥ 50 MW`.

| Target         | Band       |   Selected MAE (MW) |   MAPE |actual|≥50 (%) |   Persistence MAE (MW) |   T0 MAE (MW) |   Skill vs persistence (%) |   Skill vs T0 (%) |
|:---------------|:-----------|--------------------:|-----------------------:|-----------------------:|--------------:|---------------------------:|------------------:|
| Export minimum | 0.5–6 h    |               119.4 |                   53.6 |                  125.2 |         123.3 |                        4.6 |               3.1 |
| Export minimum | 6.5–24 h   |               197.3 |                   90.5 |                  192   |         186.3 |                       -2.8 |              -5.9 |
| Export minimum | 24.5–72 h  |               235.3 |                  108.4 |                  230.2 |         221.8 |                       -2.2 |              -6.1 |
| Export minimum | 72.5–168 h |               264.7 |                  134.8 |                  256.7 |         248.4 |                       -3.1 |              -6.5 |
| Import minimum | 0.5–6 h    |               150.3 |                   49.9 |                  138.2 |         136.9 |                       -8.7 |              -9.7 |
| Import minimum | 6.5–24 h   |               223.4 |                   74.9 |                  232.9 |         225.6 |                        4.1 |               1   |
| Import minimum | 24.5–72 h  |               274.8 |                   94.2 |                  270.6 |         258.7 |                       -1.6 |              -6.2 |
| Import minimum | 72.5–168 h |               283.7 |                   92.8 |                  288.1 |         273.4 |                        1.5 |              -3.8 |

## Rolling prediction-interval coverage

Across the twelve rolling monthly folds, delivery-period-calibrated empirical coverage was **71.93%** for the nominal 80% interval and **87.41%** for the nominal 95% interval. Both intervals under-cover, so the empirical uncertainty bands are too narrow for their stated nominal levels. The figures are row-weighted across four targets and four lead bands.

| Calibration     |   Nominal coverage (%) |   Empirical coverage (%) |   Coverage gap (pp) |   Mean width (MW) |   Forecast rows |
|:----------------|-----------------------:|-------------------------:|--------------------:|------------------:|----------------:|
| Delivery period |                     95 |                    87.41 |               -7.59 |             951.8 |          910032 |
| Delivery period |                     80 |                    71.93 |               -8.07 |             565.3 |          910032 |
| Pooled          |                     95 |                    89.91 |               -5.09 |            1002   |          910032 |
| Pooled          |                     80 |                    73.77 |               -6.23 |             577.2 |          910032 |

## Paired statistical evidence

Positive improvement favors the selected policy. Confidence intervals use paired seven-day moving blocks; the run also preserves fourteen-day results and 90% model-confidence sets in `statistics.json`.

| Target         | Control         |   Improvement (MW) | 95% block CI   |   Holm p |
|:---------------|:----------------|-------------------:|:---------------|---------:|
| Export minimum | Persistence     |                5.9 | [-4.2, 16.0]   |   0.5637 |
| Export minimum | T0 shared ridge |                4   | [-5.8, 13.7]   |   0.7211 |
| Import minimum | Persistence     |              -11.8 | [-29.0, 6.2]   |   1      |
| Import minimum | T0 shared ridge |              -13.1 | [-29.7, 4.2]   |   1      |

## Final saved-bundle routing

| Target       | Band       | Winner   |
|:-------------|:-----------|:---------|
| export_tight | 0.5–6 h    | T6_mae   |
| import_tight | 0.5–6 h    | T0_mae   |
| export       | 0.5–6 h    | T6_mae   |
| import       | 0.5–6 h    | T0_mae   |
| export_tight | 6.5–24 h   | T0_mae   |
| import_tight | 6.5–24 h   | T0_mae   |
| export       | 6.5–24 h   | T0_mae   |
| import       | 6.5–24 h   | T0_mae   |
| export_tight | 24.5–72 h  | T0_mae   |
| import_tight | 24.5–72 h  | T0_mae   |
| export       | 24.5–72 h  | T0_mae   |
| import       | 24.5–72 h  | T0_mae   |
| export_tight | 72.5–168 h | T0_mae   |
| import_tight | 72.5–168 h | T0_mae   |
| export       | 72.5–168 h | T0_mae   |
| import       | 72.5–168 h | T0_mae   |

All sixteen bundles have catalogue hashes, exact ordered schemas, fitted parameters, residual calibration and reload-parity checks. They remain `operationally_eligible: false`.

## Feature evidence

The largest average grouped-permutation effect for each primary direction is:

| target       | group            |   MAE degradation (MW) |
|:-------------|:-----------------|-----------------------:|
| export_tight | observed_history |                 110.96 |
| import_tight | observed_history |                 103.19 |

Permutation importance and SHAP are predictive-dependence diagnostics, not causal generator or constraint effects. Full rankings are in the report downloads and cell-level explanation artifacts.

## NOS point-model evidence

| Target       |   Selected NOS MAE (MW) |   T6 O0 MAE (MW) |   Skill vs O0 (%) |   Rows |
|:-------------|------------------------:|-----------------:|------------------:|-------:|
| export_tight |                  115.38 |           116.57 |              1.03 |  43923 |
| import_tight |                  132.33 |           131.81 |             -0.4  |  43923 |

NOS burden, transitions, mapped mechanisms, revisions/recall and restricted operating-state interactions are tested cumulatively only after the historical source and feasibility gates. Risk-model results remain distinct from point forecasts.

## Reproduction and handoff

- Full paper: [QNI research paper](../reports/qni_diurnal_nos_v2/qni_research_paper.html)
- Report centre: [QNI report suite](../reports/qni_diurnal_nos_v2/index.html)
- Execution guide: [QNI execution guide](QNI_DIURNAL_NOS_EXECUTION.md)
- Saved bundles: `data/forecast_experiments/qni_diurnal_nos_v2/final/`
- Configuration: `configs/experiments/qni_diurnal_nos_v2.json`

Re-run the complete resumable workflow with `python scripts/run_qni_diurnal_nos_campaign.py`. Use `python scripts/build_qni_report_suite.py` for report-only rebuilding.
