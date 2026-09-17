# Portable interconnector forecasting scaffold

This is an **offline-first scaffold**, not a deployed forecasting service. It supports VNI, QNI, Directlink, Heywood, Murraylink and Basslink through explicit connector identities. VNI's existing research bundles can be imported without retraining. Other connectors and horizons require their own compatible fitted packages; registering a connector does not manufacture a model.

No commands run automatically. The implementation lives in `nemic/production/`; configuration examples are in `configs/production/`.

## Quick start: synthetic demonstration

From the repository root, install `requirements.txt`, then:

```powershell
python -m nemic.production demo --output local_exports/my_scaffold_demo
```

This creates synthetic training data, fits small demonstration packages for VNI and QNI, registers them and generates a multi-connector run. Basslink is intentionally unavailable to demonstrate explicit coverage gaps. Open `local_exports/my_scaffold_demo/run/index.html`. Each `package-*/research_report.html` contains the training comparison. This is a software demonstration, **not evidence of real forecast accuracy**. Use a new output directory for each run.

## Architecture and indexing

`Registry` stores immutable packages and a catalogue. A package manifest declares connector IDs, target, half-hour lead range, recipe, ordered feature schema, estimator adapter, calibration, artifact hashes, dependency versions and eligibility. Paths are relative for portability.

A separate routing policy selects an ordered list: primary model followed by explicitly validated fallbacks. Routes must not overlap for a connector/target/lead. The router checks source availability, schema and eligibility before inference. It never chooses the newest model or compares unrelated MAEs at run time.

```json
{
  "version": "analyst-research-1",
  "routes": [
    {"connector": "VNI", "target": "export", "lead_min": 1,
     "lead_max": 336, "models": ["vni-regional-export@1"]}
  ]
}
```

Use canonical connector names or their AEMO identifiers. Regional endpoints alone are insufficient: QNI and Directlink share endpoints. Each model manifest explicitly lists supported connectors; shared models require validation for all listed connectors.

```powershell
python -m nemic.production register --registry local_exports/registry --package path/to/package
python -m nemic.production list --registry local_exports/registry
python -m nemic.production export --registry local_exports/registry --model vni-regional-export@1 --output local_exports/portable_package
```

Import an exported package with `register`. Only load trusted model packages: joblib serialization is executable Python. Hashes detect changed files; they do not establish publisher identity.

`activate-routes --registry ... --routes ...` records an immutable policy version and changes the active pointer only when every package has approved status and approval evidence. Re-activating an earlier version rolls back the pointer. Forecast commands take an explicit routes file for reproducibility. Approval requires a newly reviewed package/version; training always produces research status.

## Mapping your demand and VRE forecasts

Copy `configs/production/provider_mapping.example.json` and replace source column mappings. The normalized long table has:

| Field | Meaning |
|---|---|
| issue | Actual forecast issue/initialization timestamp |
| received | Time the forecast became available to this system |
| delivery | Interval end, timezone aware |
| region | NEM region, such as VIC1 or NSW1 |
| variable | demand, wind, solar, temperature or mapped variable |
| value | Value converted into the declared canonical units |
| source/member | Provider identity and ensemble member |
| interval_minutes | Original source resolution |

Mappings define source columns, region/variable aliases, timezone, interval start/end and units. Power accepts MW/GW. Naive timestamps require an explicit timezone. Internally delivery is fixed NEM UTC+10. Receipt-before-issue records, duplicates and non-finite data are rejected.

```powershell
python -m nemic.production normalize --input my_forecasts.csv --mapping my_mapping.json --output local_exports/snapshots
```

The command creates a content-addressed Parquet snapshot and hash record. Reimporting identical inputs is idempotent. Forecast selection uses both issue and receipt timestamps, and the package's maximum age. Multiple matching providers require an explicit `sources` mapping.

Hourly power forecasts are treated as interval-average values for their constituent half-hours, with coarse-resolution flags. They are not extrapolated beyond their interval coverage. No implicit 30-day extension exists.

### Weather

`adapters.fetch_open_meteo` is an explicit, optional network operation. Normal forecast and ensemble endpoints are supported, with endpoint horizon checks. `open_meteo_payload` parses cached responses and requires a genuine issue timestamp; retrieval time is not a replacement for initialization time. Specify UTC and m/s when acquiring payloads. Match weather locations to regions through caller configuration. Retain raw responses and model identity with your own archive metadata.

Weather coverage varies by model and variable. The parser preserves ensemble members and missing values do not become zeros. Regional feature recipes calculate ensemble mean/spread; the coarse-resolution flag records the original hourly resolution.

## Features, training and model packaging

`regional-v1` combines delivery calendar with regional demand/VRE/weather, residual demand, regional differences, source ages and optional history. `calendar-v1` supports baselines and the offline example. The ordered manifest feature list determines required inputs. Missing required features make a model ineligible; optional columns do not silently alter a fitted model.

Use `features.training_table` to engineer historical request rows using exactly the inference transformation. Requests supply origin, delivery, connector and actual. Optional history supplies connector, target, interval-ending delivery, received and value. Anchors are target-specific, at or before origin minus 30 minutes; history never supplies future observations.

```powershell
python -m nemic.production features --input normalized_forecasts.parquet --requests historical_requests.parquet --manifest configs/production/model_template.json --output local_exports/training.parquet
python -m nemic.production train --input local_exports/training.parquet --manifest configs/production/model_template.json --output local_exports/vni_package --budget-seconds 120 --max-trials 30
```

Training accepts a prepared feature table as well; provenance then remains the caller's responsibility. Supply enough historical origins for purged training, three rolling validation folds and held-out residual calibration. Thirty-day training requires considerably longer history than the synthetic example.

Candidate methods include median, seasonal calendar, persistence when anchors exist, regularized regression and absolute-error boosting. Default selection minimizes rolling MAE. Optuna search complexity and trial count depend on minimum usable fold size, feature count, independent days and a measured pilot. The timeout governs tuning, not preprocessing or final explanation generation. Search details and parameters are saved. No automatic Cartesian grid across connectors, targets and recipes is launched.

The optional `--objective capacity_normalized_mae` requires a strictly positive `capacity_reference_mw` for each row and `capacity_reference_definition` in the manifest. The reference must be issue-known, not the future realized target. Compare it as a separate package; MAE remains the default. Report MAPE excludes absolute actual limits below 1 MW and reports the excluded count. Diagnostic normalized MAE using development-label magnitude is labelled separately from a physical capacity reference.

Training produces fitted weights, parameters, dependencies, hashes, rolling predictions, metrics, held-out residual calibration, permutation importance and SHAP decomposition. Calibration rows are not an independent coverage test. Models remain research-only until additional validation supports promotion.

After outcomes arrive, use `evaluate --input forecasts.parquet --actuals actuals.parquet --output new_score_folder`. Actuals must be unique on connector, target and delivery, with an `actual` column. Outputs include scorecards by model, connector, target, horizon and NEM delivery period, interval coverage, and actual-versus-forecast reports. Missing predictions remain in the coverage counts. Feature importance and SHAP are generated for every candidate family, not just the selected estimator.

## NOS, constraints and AEMO challengers

`constraints.candidates` replays outage revisions/cancellations as of issue time, intersects schedule windows and effective equipment-to-constraint links, and returns scheduled candidate exposure. A candidate is not an invoked or binding constraint.

`constraints.fit_setter_ranker` trains a candidate-level logistic ranker and returns purged out-of-fold probabilities. Only those OOF predictions may be stacked into training a downstream limit model. It does not claim a regional forecast determines unit dispatch. `equation_bound` requires every non-interconnector term and rejects incomplete equations.

Optional feature context tables:

- `outages` and `links`: schemas documented in `constraints.candidates`.
- `aemo`: connector, target, delivery, issue, received, value.
- `constraint_forecasts`: the same columns, optionally probability.

Pass context through `build`, `training_table` or `forecast`. A manifest can request `nos_outage_count`, `nos_constraint_count`, `aemo_limit`, `constraint_limit` or `constraint_setter_probability`. Keep independent and AEMO-assisted models in separate packages and routes. Counterfactuals must use a separate scenario name.

`rank_effects` summarizes supplied matched-event estimates by outage, connector and target, using independent event counts and standard errors. Below 30 events it explicitly labels associations exploratory. Matching/causal identification is not inferred from raw correlations. Compare otherwise identical recipes with and without NOS using the same folds.

## Forecasting and scenarios

```powershell
python -m nemic.production preview --registry local_exports/registry --routes my_routes.json --input normalized_forecasts.parquet --origin 2026-09-16T00:00:00+10:00 --connectors VNI QNI --days 30 --mode research --output local_exports/routing_preview.csv
python -m nemic.production forecast --registry local_exports/registry --routes my_routes.json --input normalized_forecasts.parquet --origin 2026-09-16T00:00:00+10:00 --connectors VNI QNI --days 30 --mode research --output local_exports/run_20260916
```

The default mode is production and accepts only approved models. Research use requires explicit research mode. Preview validates routing/features without deserializing estimators. Every requested interval has a complete/unavailable status and reason. Half-hour mean and minimum import/export targets are separate. Valid negative limits are preserved. Unsupported models/horizons are never substituted or extrapolated.

`inputs.scenario` applies explicit regional-variable-delivery overrides to a copied input table. Use a non-baseline scenario name; retain the override file and original snapshot. To supply assumptions beyond original coverage, provide a complete scenario input table with explicit provenance. Forecast uncertainty is conditional on those assumptions, not a probability distribution over analyst scenarios.

```python
from nemic.production import Registry, forecast
result = forecast(Registry("local_exports/registry"), policy, normalized_inputs,
                  origin="2026-09-16T00:00:00+10:00", connectors=["VNI"],
                  days=30, mode="research", scenario="baseline")
```

Days 8–30 are labelled outlook and need separately registered coverage. Hourly points average half-hour means and take the lower half-hour minimum. Bounds remain unavailable unless `calibration.fit_hourly` / `apply_hourly` supplies a separate held-out, route-specific calibration valid before the new origin.

## Existing fitted VNI models

```powershell
python -m nemic.production import-vni --source data/forecast_experiments/vni_diurnal_nos_v2/final --registry local_exports/registry --staging local_exports/legacy_import
```

This copies all 16 bundles with unchanged predictions and research status. Supply original prepared feature rows with connector, target, origin and delivery using `--prepared`. The generic regional recipe cannot replace the legacy 41-column contract. Existing `python -m nemic.experiments forecast-vni` remains supported.

## Adding connectors or estimator families

For an existing connector: create its feature configuration, train/validate its targets and horizons, register packages, then add non-overlapping routes. Never reuse VNI weights for another connector without explicit multi-connector training/validation.

For a new estimator serialization, implement a prediction adapter returning point and ordered quantile predictions, add adapter tests, and declare its schema and dependencies. Existing sklearn-compatible estimators can use the bundled sklearn adapter.

## Future operational handoff

Before running on real feeds, audit forecast-vintage coverage, freeze mapping semantics, validate held-out point/interval performance and run prospective shadow forecasts. Record actual receipt times. Establish connector-specific promotion thresholds and review evidence before changing package eligibility. This scaffold intentionally does not invent operating thresholds without that evidence.

Run daily scheduling externally against the same explicit forecast command when ready. Keep immutable input snapshots, model packages, policies, scenario assumptions and run outputs. This implementation does not install a scheduler or start a service.
