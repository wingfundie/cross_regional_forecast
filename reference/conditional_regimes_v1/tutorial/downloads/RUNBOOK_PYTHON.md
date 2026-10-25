# Python installation and integration

## Install and load

Install the supplied wheel into the consuming project's environment. The core analogue functions require pandas, NumPy and PyArrow; model extrapolation additionally requires scikit-learn, LightGBM and joblib.

```text
python -m pip install "nemic_regimes-0.1.0-py3-none-any.whl[models]"
```

Extract the separately supplied inference bundle to a local directory. Keep its manifest, panel and model files together. The manifest identifies schema, bundle identity, input cutoff, compatible eras and artifact hashes.

The `models` extra pins the saved estimators' compatible scikit-learn, LightGBM and joblib versions. A clean-install check found that scikit-learn 1.9 could not load the 1.6 fitted imputer contract. Use the supplied `requirements-bundle-v1.txt` when reproducing the full tested environment; do not upgrade saved-model dependencies independently.

```python
from nemic_regimes import load_bundle

bundle = load_bundle("regime_bundle")
profile = bundle.profile(1, {
    "connector": "VNI",
    "direction": "forward",
    "era": "pre_pec_market",
    "sink_residual": {"min": 7000},
    "scenario_name": "high_nsw_residual",
})
bundle.export(profile, "profile.csv")
```

The example explicitly selects a historical era. For current configuration requests use `era="current"` and inspect support/relaxed conditions. Four calendar quarters describe repeated seasonal conditioning, not a dated year-ahead weather forecast.

## Public contract

`select` accepts a dictionary, a list of dictionaries, or a DataFrame. Required query fields are connector, quarter and half_hour; direction defaults to forward, target to average and era to current. `profile` generates all 48 half-hours for supplied quarter/conditions. `explain` returns the same evidence-rich result as a single selection. `bundle.export` writes CSV or JSON; nested evidence is best retained as JSON.

Supported connector names and existing AEMO identifiers are accepted. Direction is forward/reverse following the bundle mapping, not the sign of today's observed flow. Half-hour 0 ends 00:00, 1 ends 00:30 and 47 ends 23:30 NEM time. Inspect the schema rather than assuming direction means the same region pair on every link.

Conditions support numeric values or min/max bounds. `required_sets`/`required_assets` require listed components; unlisted concurrent sets are permitted unless `exact_sets=True` is specified. `excluded_sets` forbids listed families. `outage_state="clear"` means no mapped relevant set invoked, not proof every line is in service. Omitted fields remain unspecified.

Methods are `table`, `auto`, `analogue`, `unweighted`, `baseline`, `additive`, `boosting`. Table mode reproduces the strict static catalogue definition using all matching quarter/half-hour observations and returns unavailable if no exact case exists. Analogue mode can return a labelled broader reference. Explicit models require `allow_extrapolation=True`. An unseen combination of known components may be modelled; an unknown structural era or unrecognised component cannot silently borrow another topology. Missing model conditions are training-imputed assumptions, so supply important expected conditions explicitly.

Results include P10/P50/P90 MW, target, era, method, evidence status, exact/selected days, linked outage episodes, outside-support conditions, relaxed conditions, analogue dates and stress examples. `supported_analogue`, `broader_analogue`, `modelled_extrapolation` and `unavailable` are materially different states. Negative values are preserved. Weighted historical frequencies are not unconditional future event probabilities.

## Dated inputs and overrides

`mode="asof"` additionally requires timezone-aware `origin`, `delivery` and `inputs`. Delivery must agree with the quarter/half-hour. Every supplied operating condition needs a matching evidence record or a named user assumption. Source records need variable/value, source, product, run_id, issue, received, receipt_completed, delivery, SHA-256 and measured-receipt evidence. Records must be eligible at origin and coherent by run group. The bundle training cutoff must precede origin.

Applying current observed demand/VRE to another delivery time is a scenario, not an issued forecast. Preserve the machine suggestion and separately name an override. The supplied bundle remains conditional research even if a new request has valid receipt evidence. The separate historical as-of scorecard currently identifies the absence of eligible replay rows.

## Local service and command line

```text
nemic-regimes serve --bundle regime_bundle --port 8061
nemic-regimes profile --bundle regime_bundle --quarter 4 --conditions scenario.json --output profile.json
nemic-regimes select --bundle regime_bundle --conditions one_interval.json --output result.json
nemic-regimes collect-grid --connector QNI --direction reverse --output new_inputs
nemic-regimes collect-weather --connector VNI --run 2026-10-24T00:00:00Z --delivery 2026-10-25T12:00:00+10:00 --output new_inputs
```

The service binds to localhost. `/api/select` and `/api/profile` accept the same query schema. `/api/catalogue` exposes available conditions, eras and units. Public collection is user-triggered, never a recurring schedule. A failed provider call leaves the previous named scenario intact.
