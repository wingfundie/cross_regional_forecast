# nemic-regimes

Portable conditional analogue estimates of AEMO-reported interconnector dispatch limits. Requires a separately supplied, hash-verified research bundle. Does not deploy models or activate forecasting schedules.

```python
from nemic_regimes import load_bundle

bundle = load_bundle("path/to/extracted/bundle")
profile = bundle.profile(1, {
    "connector": "VNI", "direction": "forward", "era": "pre_pec_market",
    "sink_residual": {"min": 7000}, "required_sets": ["N-CNLT_07"],
    "scenario_name": "corridor_assumption",
})
bundle.export(profile, "selected_limits.csv")
```

Calendar quarter 1 means Jan–Mar. It is a general conditioning category. Half-hour 0 ends at 00:00 NEM time, half-hour 47 at 23:30. The main target is the complete six-observation half-hour mean; `target="tight"` selects the minimum. Negative directional values remain negative.

`era="current"` uses the bundle's stated as-of date. If the requested era is absent, the result is unavailable. A quarter outside the observed era can yield a broader reference with quarter explicitly relaxed. No incompatible-era borrowing is hidden.

Available operations: `load_bundle`, `select`, `profile`, `explain`, and `bundle.export`. Batch inputs can be lists of dictionaries or DataFrames. Numeric conditions accept exact-value similarity requests or `{"min": ..., "max": ...}` ranges. `required_sets` and `required_assets` are subset requirements; add `exact_sets=true` for a complete specified set combination. `excluded_sets` forbids listed sets. Blank/omitted numeric inputs are unspecified, not normal.

Methods: `table` (strict conditional static table), `auto`/`analogue`, `unweighted`, `baseline`, `additive`, `boosting`. Table mode uses all exact-condition quarter/half-hour observations with the same quantile convention as the exported catalogue. It returns supported/indicative table status and does not silently broaden a missing case. Models require the `models` installation extra and explicit `allow_extrapolation=True`. Supported analogue, broader analogue, modelled extrapolation and unavailable are distinct result statuses. A modelled interval is not a verified tail probability.

```text
nemic-regimes serve --bundle path/to/bundle --port 8061
nemic-regimes profile --bundle path/to/bundle --quarter 1 --conditions scenario.json --output profile.csv
nemic-regimes select --bundle path/to/bundle --conditions query.json --output evidence.json
```

The browser interface binds to localhost and calls the same package. It can collect new public observed-grid and explicit weather-run suggestions on demand. Applying current observations to a future period is a named scenario. New requests record actual receipt; they do not repair historical receipt gaps.

`mode="asof"` requires timezone-aware origin and delivery, a bundle whose training cutoff precedes the origin, and eligible input records for every supplied operating condition. Records require source, product, run/vintage, issue, received/completed receipt, delivery, value, hash and evidence class. Coherent run groups cannot mix vintages. User assumptions require a named scenario. Even valid inputs do not change the bundle's conditional-research training claim.

Only load trusted local model artifacts. Bundle hashes detect changes but are not cryptographic signatures of an external publisher.
