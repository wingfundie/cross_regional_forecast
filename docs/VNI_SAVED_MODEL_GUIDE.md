# Using the saved VNI forecasting models

## Where the models are

The ready-to-load bundle catalogue is:

`data/forecast_experiments/vni_diurnal_nos_v2/final/catalogue.json`

It indexes 16 saved bundles: four targets × four forecast-lead bands. Each bundle folder contains:

- `model.joblib` — fitted point model and residual interval calibration;
- `manifest.json` — exact feature schema, parameters, package versions, hash and status;
- `example_features.parquet` — 20 correctly ordered input rows;
- `example_predictions.parquet` — reload-parity reference predictions.

The targets are `export_tight`, `import_tight`, `export`, and `import`. Leads are measured in half-hour intervals and route automatically to bands 1–12, 13–48, 49–144, and 145–336.

## Run a saved model immediately

Install the repository dependencies, then run the supplied band-0 example:

```powershell
python -m nemic.experiments forecast-vni `
  --features data/forecast_experiments/vni_diurnal_nos_v2/final/band0/export_tight/example_features.parquet `
  --target export_tight `
  --output local_exports/vni_export_tight_example.csv `
  --allow-research
```

The output contains the routed band and model, `forecast_mw`, calibrated 2.5%, 10%, 50%, 90%, and 97.5% estimates, and the interval-calibration basis. Without a `delivery` timestamp the command uses pooled residual calibration. When `delivery` is supplied, it uses the bundle's delivery-period calibration.

The loader verifies every model against the SHA-256 value in `catalogue.json`, enforces the saved feature names and order, requires a finite issue-known `own_anchor`, and rejects leads outside 1–336 half-hours.

## Use the Python API

```python
import pandas as pd
from nemic.experiments.vni_forecast import VniBundleRepository

features = pd.read_parquet(
    "data/forecast_experiments/vni_diurnal_nos_v2/final/"
    "band0/export_tight/example_features.parquet"
)

models = VniBundleRepository()
forecast = models.forecast(features, "export_tight", allow_research=True)
print(forecast[["lead", "model", "forecast_mw", "p10_mw", "p90_mw"]])
```

One input table may contain leads from multiple bands. The repository routes each row to the appropriate saved bundle.

## Required input features

The exact schema is stored in every bundle's `manifest.json`. The current bundles require 41 numeric columns covering:

- recent flow and directional-limit levels and changes;
- daily and weekly lags;
- delivery hour, annual phase, weekend and forecast lead;
- reconstructed network room, switch gaps, candidate counts and setter age;
- aggregate generator tightening, relief and pressure changes;
- reconstruction completeness flags;
- `own_anchor`, the latest admissible directional limit known at forecast issue time.

Start from `example_features.parquet`, or inspect `manifest.json` before connecting a new feature producer. Extra metadata columns such as `origin` and `delivery` are accepted; required model columns must still be present.

## Status and practical limitation

These bundles are immediately usable for research forecasts from a correctly constructed feature table. They are deliberately marked `operationally_eligible=false` because their network inputs were reconstructed retrospectively and a live, receipt-time-verified feature feed has not yet been validated. The command therefore requires `--allow-research`.

For a live deployment, the remaining task is to connect the same 41-column contract to issue-time AEMO data, record actual receipt timestamps, run prospective shadow forecasts, and promote only after the documented performance and data-quality gates pass. The saved model files do not include NOS features because the historical NOS ablation did not improve the default point forecast consistently.

## Refit or replace the bundles

Recreate all 16 frozen-procedure bundles from the completed run with:

```powershell
python -m nemic.experiments refit-diurnal --config configs/experiments/vni_diurnal_nos_v2.json
```

This is a model-training operation. Ordinary forecasting uses `forecast-vni` and does not refit anything.
