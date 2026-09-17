# QNI diurnal and NOS execution

The QNI v2 campaign mirrors the completed VNI protocol without copying VNI conclusions. It uses `NSW1-QLD1`, the two-year QNI constraint reconstruction and QNI event atlas, while preserving the same targets, folds, lead bands, model ladder, MAE selection rule, DR-NMAE challenger, NOS gates, resource limits, explanations and bundle checks.

## Complete resumable run

```powershell
python scripts/run_qni_diurnal_nos_campaign.py
```

Configuration: `configs/experiments/qni_diurnal_nos_v2.json`. Fixed-split sensitivity: `configs/experiments/qni_diurnal_nos_v2_fixed.json`. Resume at a named stage with `--from-stage`; each underlying command still validates its own artifact hashes before using a cache.

The ordered stages are rolling primary models, NOS inventory/recovery/audit/impact/feasibility gates, fixed primary and extensions, rolling extensions, point-risk models, paired statistics, full curves, legacy bridge, final refits, explanations, NOS point/risk models, refinements, report generation/publication and the full test suite.

## Outputs

- Local run artifacts: `data/forecast_experiments/qni_diurnal_nos_v2/`
- Report centre: `data/forecast_experiments/qni_diurnal_nos_v2/report/index.html`
- Tracked report copy: `reports/qni_diurnal_nos_v2/index.html`
- Saved bundles: `data/forecast_experiments/qni_diurnal_nos_v2/final/`
- Stage status: `data/forecast_experiments/qni_diurnal_nos_v2/campaign_status.json`
- Stage logs: `data/forecast_experiments/qni_diurnal_nos_v2/campaign_*.log`

## Interpretation

All outcomes through August 2026 were available during model development. Reconstructed network inputs do not have verified first-receipt lineage. The results and saved bundles are therefore historical research evidence and remain ineligible for operational promotion until a prospective shadow period is completed.
