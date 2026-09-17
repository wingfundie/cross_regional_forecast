# QNI saved-model guide

The completed QNI campaign writes sixteen target × lead-band research bundles to `data/forecast_experiments/qni_diurnal_nos_v2/final/`. The catalogue records the selected model, bundle path and SHA-256 digest. Bundles are historical-development artifacts and remain `operationally_eligible: false`.

## Reproduce a forecast

Prepare a CSV or Parquet feature table that follows the exact ordered schema in the selected bundle. Include `lead` as an integer number of half-hours from 1 through 336. Include `delivery` to use delivery-period interval calibration; without it, pooled calibration is used.

```powershell
python -m nemic.experiments forecast-model `
  --config configs/experiments/qni_diurnal_nos_v2.json `
  --features path/to/qni_features.parquet `
  --target export_tight `
  --output local_exports/qni_export_tight.csv `
  --allow-research
```

The loader verifies catalogue completeness and bundle hashes, validates required columns, routes each row to the correct lead band, and returns the point forecast plus calibrated 2.5%, 10%, 50%, 90% and 97.5% estimates.

## Status

These bundles use reconstructed historical network inputs. They are not live-eligible until every input has verified receipt-time lineage and the frozen policy passes a prospective shadow evaluation. Persistence should remain the operational fallback during that work.

Rebuild the model and NOS report suite with `python scripts/build_qni_report_suite.py` after the campaign stages complete.
