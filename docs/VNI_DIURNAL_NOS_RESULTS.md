# VNI diurnal and NOS modelling results

Run date: 16 September 2026. Outcomes extend through August 2026 in NEM time (UTC+10). These are historical development results on reconstructed network information. They are not yet operationally eligible.

## Verdict

Use the MAE-selected calendar policy as the VNI point-forecast model. The shallow boosted absolute-error model (`T6_mae`) is the preferred family for bands 0–2 and for import in band 3. Retain the shared ridge control (`T0_mae`) for band-3 export. Keep persistence and seasonal persistence as validation-selected fallbacks in the rolling routing policy.

Time-of-delivery specialization is predictive. On the primary tight-limit cells, the selection-frozen policy improves origin-balanced MAE over persistence by 108.0 MW for export and 39.7 MW for import, and over shared T0 by 71.1 MW and 31.0 MW respectively. Seven- and fourteen-day moving-block bootstraps exclude zero; Holm-adjusted one-sided p-values are 0.0020. The 90% model confidence set contains only `T6_mae` for both tight directions under both block lengths.

Scheduled NOS features are not admitted to the default point model. Across the six source-common folds, the selection-routed NOS policy changes MAE versus the boosted no-NOS control by +0.39% skill for export and -0.63% for import. Scheduled-outage grouped permutation importance averages -1.27 MW for export and +0.17 MW for import, much smaller than calendar and observed-history effects. NOS remains useful as a risk challenger and for targeted investigation, subject to prospective confirmation and a forward generator-availability stream.

Post-selection refinements are also rejected as default routing. Selection-routed training-window/lead-pressure refinements worsen combined held-out MAE by 1.00% for export and 0.08% for import versus the expanding-history baseline.

## Rolling model results

MAPE is reported only where `|actual| >= 50 MW`; MAE is the optimization and model-selection target.

| Target | Lead band | Selected MAE (MW) | Qualified MAPE (%) | Persistence MAE | Shared T0 MAE | Skill vs persistence | Skill vs T0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| export tight | 1–12 | 216.8 | 62.3 | 324.7 | 287.8 | 33.2% | 24.7% |
| export tight | 13–48 | 280.4 | 77.0 | 483.8 | 377.5 | 42.0% | 25.7% |
| export tight | 49–144 | 284.8 | 77.9 | 447.2 | 360.7 | 36.3% | 21.0% |
| export tight | 145–336 | 272.3 | 72.3 | 339.4 | 299.5 | 19.8% | 9.1% |
| import tight | 1–12 | 192.1 | 55.9 | 231.8 | 223.0 | 17.1% | 13.9% |
| import tight | 13–48 | 240.2 | 69.6 | 320.9 | 299.7 | 25.1% | 19.8% |
| import tight | 49–144 | 239.4 | 69.7 | 325.4 | 303.6 | 26.4% | 21.1% |
| import tight | 145–336 | 241.9 | 71.6 | 310.3 | 290.1 | 22.0% | 16.6% |

The comprehensive HTML report also includes the standard export/import targets, fixed-split sensitivity, delivery-period results, all 208 evaluated cells, and full 336-step curve diagnostics.

## Feature evidence and fundamentals

For the boosted primary cells, calendar perturbation causes the largest mean MAE degradation on export (149.6–170.5 MW). Observed history is the largest group on import (55.7–58.1 MW) and the second-largest group on export (62.5–65.9 MW). Horizon contributes roughly 9.9–18.7 MW. Network state and aggregate generator pressure contribute roughly 1.6–2.7 MW each after the stronger correlated groups are present.

The SHAP decompositions agree with that ordering. The issue-known directional-limit anchor is the largest single contribution, followed by the matching one-step limit lag and hour-of-day terms. Year phase, lead, candidate completeness, room, and generator-pressure variables provide smaller conditional corrections. These are predictive sensitivities, not causal effects.

This supports a fundamentals interpretation in which VNI capability has a strong recurring delivery-time shape, but its realized level remains anchored by the latest admissible limit and recent network state. Generator-pressure features add information at the margin. Their historical version is contemporaneous/lagged aggregate pressure, so a weak NOS result cannot be generalized to a model that also has original-vintage forward unit availability.

## NOS evidence

- The source archive contains 17,800 usable snapshots from 53 weekly bundles. Six expanding monthly folds meet the historical coverage gate in each direction.
- The pre-evaluation design set contains 1,647 export and 938 import contraction incidents across 124 independent scheduled-exposure chains.
- The descriptive outage atlas contains 422 candidate bookings and 1,638 direction-asset records.
- Only 15 direction-level episodes pass the matched-control requirements. No recurring outage entity passes the support, pretrend, placebo, and leave-one-out stability gate. No asset or outage set is therefore labelled as having the “highest adjusted impact.”
- O1 burden, O2 transitions/overlap, O3 mapped mechanism, O4 revision/recall, and restricted OX operating-state interactions are tested cumulatively. Their gains vary by fold and model. They are more visible in regularized linear models and are mostly redundant or unstable once T6 is fitted.
- Five of six NOS risk folds select an outage recipe, but the selected recipe changes by month and the held-out recall/false-alarm trade-off remains unstable. Treat it as historical development evidence.

## Hyperparameter search and trained bundles

Search budgets and ranges are derived inside each fold from observed origin count, pair count, feature rank, target scale, positive-event count, and measured trial runtime. Primary cells use progressive Optuna batches with a chronological inner validation design and a block-noise stopping rule. Extension cells reuse the primary shortlist and parameters, avoiding a fold × target × band × family Cartesian search.

For example, the August export-tight primary cell has 28,798 training origins, 143,968 origin-lead pairs, 41 raw features, expanded rank 43, and rank-99 of 37. Its T6 search completed 15 trials and selected complexity 0.65, three daily harmonics, 42 leaves, minimum child size 561, learning rate 0.0422, and 200 trees. Exact per-cell ranges, completed trials, stop reasons, fitted parameters, and data shapes are in the HTML report.

Sixteen frozen-procedure research bundles were refitted with exact schemas and reload parity checks. T6 is selected for all targets in bands 0–2 and for band-3 import; T0 is selected for band-3 export. The bundle catalogue and manifests are under `data/forecast_experiments/vni_diurnal_nos_v2/final/`.

## Review artifacts

- Report-suite landing page: `data/forecast_experiments/vni_diurnal_nos_v2/report/index.html`
- Focused visual reports: `data/forecast_experiments/vni_diurnal_nos_v2/report/pages/`
- Comprehensive offline report: `data/forecast_experiments/vni_diurnal_nos_v2/report/full_run/vni_diurnal_nos_model_report.html`
- Focused outage-impact report: `data/forecast_experiments/vni_diurnal_nos_v2/report/full_run/nos_outage_impact_analysis.html`
- Machine-readable model table and manifests: `data/forecast_experiments/vni_diurnal_nos_v2/report/downloads/`
- Run and report directory guide: `docs/VNI_MODEL_RUN_GUIDE.md`

The reports contain actual-versus-forecast charts, MAPE-first and MAE-second metric tables, model-by-model results, grouped feature importance, SHAP decompositions, hyperparameter histories, NOS impact evidence, risk results, the model-choice verdict, and the exact trained-bundle parameters.
