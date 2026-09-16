# VNI model run and report guide

The completed VNI diurnal and NOS study has one entry point:

`data/forecast_experiments/vni_diurnal_nos_v2/report/index.html`

The Git-tracked rendered copy is `reports/vni_diurnal_nos_v2/index.html`. Refresh it after a local report rebuild with `python scripts/publish_vni_reports.py`.

The complete paper-style study is `reports/vni_diurnal_nos_v2/vni_research_paper.html`; rebuild it from cached run artifacts with `python scripts/build_vni_research_paper.py`.

Saved-model loading and forecasting are covered separately in `docs/VNI_SAVED_MODEL_GUIDE.md`. The bundle catalogue is `data/forecast_experiments/vni_diurnal_nos_v2/final/catalogue.json`.

The index links to focused offline HTML reports for model performance, the cell-level model explorer, feature relevance, NOS outages, contraction risk and refinements, and the final model handoff. It also links to the complete all-in-one report and the focused matched-outage study.

## Model code

| Area | Main implementation |
|---|---|
| Shared data, metrics and folds | `nemic/experiments/core.py`, `diurnal.py` |
| Rolling search and routing | `diurnal_runner.py`, `diurnal_extensions.py` |
| Fixed-split sensitivity | `diurnal_fixed.py` |
| Full 336-step curves | `diurnal_curves.py` |
| Feature importance and SHAP | `diurnal_explain.py`, `nos_explain.py` |
| Statistical comparisons | `diurnal_statistics.py` |
| Base contraction risk | `diurnal_risk.py` |
| NOS ingestion and exposure | `nos.py`, `nos_analysis.py`, `nos_feasibility.py` |
| NOS point and risk models | `nos_runner.py`, `nos_risk.py` |
| Post-selection refinements | `diurnal_refinements.py` |
| Frozen bundle export | `diurnal_export.py` |

All modules are under `nemic/experiments/`. Experiment configurations are under `configs/experiments/`.

## Completed-run artifacts

The model outputs stay under `data/forecast_experiments/vni_diurnal_nos_v2/`. They are excluded from Git because they include source data, fitted models and large prediction files.

| Folder | Contents |
|---|---|
| `diurnal/` | Rolling and fixed model cells, predictions, searches and explanations |
| `curves/` | Frozen 336-step curves and boundary diagnostics |
| `bridge/` | Corrected legacy-policy comparison |
| `risk/` | Base contraction-warning models |
| `nos/` | NOS archive, mapping, exposure and matched-impact evidence |
| `nos_models/` | NOS point-model ablations |
| `nos_risk/` | NOS contraction-risk challengers |
| `refinements/` | Training-window and lead-pressure tests |
| `final/` | Frozen research bundles, parameters, schemas and reload tests |
| `report/` | HTML report suite, downloads, manifests and visual QA |

## Report layout

| Report | Purpose |
|---|---|
| `index.html` | Landing page and directory for the whole run |
| `pages/01_model_performance.html` | Rolling/fixed results, delivery-time performance and full curves |
| `pages/02_model_explorer.html` | Actual-versus-forecast charts, per-cell metrics, tuning and SHAP |
| `pages/03_feature_fundamentals.html` | Feature relevance and fundamentals assessment |
| `pages/04_nos_outages.html` | NOS coverage, models, charts, importance and SHAP |
| `pages/05_risk_and_refinements.html` | Warning models and post-selection refinements |
| `pages/06_model_handoff.html` | Verdict, statistics and trained parameters |
| `full_run/` | Complete report and focused outage-impact report |
| `downloads/` | Model table, build manifests and artifact catalogue |

Rebuild all pages from the cached results with:

```powershell
python scripts/build_vni_report_suite.py
```

This command renders reports only. It does not retrain or alter the completed model run.
