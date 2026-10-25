# From grid assumptions to directional limits

A practical tutorial for `nemic-regimes` version 0.1.0. You supply the calendar quarter, half-hour, direction, compatible network era and measurable assumptions. The package reads a saved historical bundle and returns P10/P50/P90 estimates of **AEMO-reported dispatch limits**, together with matching evidence. It does not calculate maximum secure physical capability or forecast the conditions you leave unspecified.

Repository readers: the `downloads/` links below belong to the generated offline tutorial directory. Published copies are under `reference/conditional_regimes_v1/tutorial/`, including the inference bundle and example outputs. Use `packages/nemic-regimes/examples/tutorial.py` and `docs/CONDITIONAL_REGIMES_DEVELOPMENT.md` for source-checkout instructions.

The worked example asks: **at 18:30 in Q1, with warm NSW conditions and high Queensland residual demand, what ranges have been reported for QNI in each direction?** The same physical assumptions are translated correctly when the direction reverses.

## 1. Install and find the bundle

If you downloaded the tutorial archive, extract it and open PowerShell in the folder containing `index.html`. Python 3.10 or later is required. These commands create a separate environment; activation is unnecessary:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install "./downloads/nemic_regimes-0.1.0-py3-none-any.whl"
Expand-Archive -LiteralPath ./downloads/nemic_regimes_bundle_v1.zip -DestinationPath ./regime_bundle
.\.venv\Scripts\python.exe ./downloads/tutorial.py --bundle ./regime_bundle --output ./my_outputs
```

The wheel contains the Python engine. The bundle ZIP contains `manifest.json`, `panel.parquet`, model files and supporting metadata. Keep the extracted directory intact. Point `load_bundle` to the directory containing `manifest.json`, rather than to the ZIP or manifest file itself. The normal analogue/table operations need no internet after installation and extraction.

For the existing repository, an alternative is `python -m pip install ./packages/nemic-regimes` from the project root, then load `data/forecast_experiments/conditional_regimes_v1/bundle`. There is no need to acquire data or retrain models to use the existing bundle.

## 2. Load once, query many times

Run this in your Python script, notebook or console. The remaining examples assume `bundle` has been loaded:

```python
from nemic_regimes import load_bundle

bundle = load_bundle("regime_bundle")
print(bundle.metadata["bundle_id"])
print(bundle.metadata["training_cutoff"])
print(bundle.metadata["current_eras"])
```

Loading checks the bundle's declared file hashes by default and reads its retained historical panel. It does not download the latest data. Reuse this object for subsequent queries; optional model files are loaded when needed. A new selection does not change the saved bundle.

For this tutorial the bundle is `conditional-regimes-v1-b3352cb955ecbeb0`, with observations through **2026-10-25 00:00 NEM time**. `era="current"` means current at the bundle's stated as-of date, not automatically current at the date you run the code.

## 3. Specify the interval and direction

Calendar quarters are Q1 Jan–Mar, Q2 Apr–Jun, Q3 Jul–Sep and Q4 Oct–Dec. A delivery half-hour is identified by its **ending time**, using fixed NEM time, UTC+10:

| Ending time | `half_hour` | Ending time | `half_hour` |
|---|---:|---|---:|
| 00:00 | 0 | 12:00 | 24 |
| 00:30 | 1 | 18:00 | 36 |
| 06:00 | 12 | 18:30 | 37 |
| 09:30 | 19 | 23:30 | 47 |

The interval ending 18:30 contains the six five-minute limits ending 18:05, 18:10, 18:15, 18:20, 18:25 and 18:30. Quarter and day labels follow the interval-ending timestamp, including midnight and quarter boundaries.

```python
import pandas as pd

delivery = pd.Timestamp("2026-01-15T18:30:00+10:00")
nem_delivery = delivery.tz_convert("Australia/Brisbane")
assert nem_delivery.minute in (0, 30) and nem_delivery.second == 0
quarter = nem_delivery.quarter                         # 1
half_hour = nem_delivery.hour * 2 + nem_delivery.minute // 30  # 37
```

Convert timestamps before deriving these keys. For example, 18:30 Singapore time is 20:30 NEM time. The runnable example includes a stricter `interval_keys` helper that also rejects naive timestamps and fractional seconds. In a general scenario the date above supplies calendar keys only; it is not a historical issue-time replay.

A calendar date does not restrict the sample to that one historical day. Add `daytype="weekday"` or `daytype="weekend"` explicitly if you want that extra filter; the simple quarter/half-hour example pools both.

| Connector | Forward: source → sink | Reverse: source → sink | AEMO identifier |
|---|---|---|---|
| QNI | NSW → QLD | QLD → NSW | `NSW1-QLD1` |
| Directlink | NSW → QLD | QLD → NSW | `N-Q-MNSP1` |
| VNI | VIC → NSW | NSW → VIC | `VIC1-NSW1` |
| Heywood | VIC → SA | SA → VIC | `V-SA` |
| Murraylink | VIC → SA | SA → VIC | `V-S-MNSP1` |
| Basslink | TAS → VIC | VIC → TAS | `T-V-MNSP1` |

Both names and these identifiers are accepted. Forward/reverse follows this mapping even when the observed flow is going the other way.

## 4. Start with the quarter/half-hour reference

```python
base_query = {
    "connector": "QNI",
    "direction": "forward",       # NSW to QLD
    "quarter": 1,
    "half_hour": 37,              # ending 18:30 NEM
    "era": "current",
    "target": "average",
    "method": "table",
    "mode": "scenario",
    "scenario_name": "qni_q1_evening_reference",
}
reference = bundle.select(base_query)
print({k: reference.get(k) for k in
       ["p10_mw", "p50_mw", "p90_mw", "status", "analogue_days"]})
```

With no operating conditions supplied, table mode returns the compatible quarter/half-hour reference. `target="average"` is the mean of all six native five-minute directional limits. It is not the average across a whole day. Unknown fields should be omitted or explicitly `None`; a missing temperature is not a temperature of zero.

## 5. Add the conditions you mean

Suppose your scenario assumes the NSW temperature feature is at least 25°C and Queensland residual demand is at least 5,000 MW:

```python
conditions = {
    **base_query,
    "scenario_name": "warm_nsw_high_qld_residual",
    "source_temperature": {"min": 25},
    "sink_residual": {"min": 5000},
}
result = bundle.select(conditions)
print(result["p10_mw"], result["p50_mw"], result["p90_mw"])
print(result["status"], result.get("analogue_days"))
```

Bounds are inclusive. Use `{"min": 25, "max": 35}` for a band or `{"max": 1000}` for an upper bound. In **table mode**, every retained observation meets the supplied bounds, quarter and half-hour. No match returns `unavailable` rather than silently broadening the request.

A scalar such as `source_temperature=30` means an approximate similarity request, using the saved feature scale. It does not require a historical measurement of exactly 30.000°C. For a genuinely narrow filter, supply explicit min/max bounds. You can inspect the tolerance used for this bundle:

```python
scale = bundle.metadata["settings"]["QNI/forward"]["scales"]["source_temperature"]
print(scale)   # includes scale and historical support bounds
```

Add conditions gradually and compare the range and support with `reference`. More fields can make a case more relevant while leaving too little independent history. Omitted conditions remain unspecified, rather than being assumed normal.

## 6. Ask for the reverse limit for the SAME grid state

For QNI reverse, Queensland becomes the source and NSW becomes the sink. Therefore the two physical assumptions must move to different input names:

```python
reverse_conditions = {
    **base_query,
    "direction": "reverse",       # QLD to NSW
    "scenario_name": "warm_nsw_high_qld_residual",
    "sink_temperature": {"min": 25},    # still NSW
    "source_residual": {"min": 5000},   # still QLD
}
forward = result
reverse = bundle.select(reverse_conditions)

for label, r in [("NSW to QLD", forward), ("QLD to NSW", reverse)]:
    print(label, r["p10_mw"], r["p50_mw"], r["p90_mw"], r["status"])
```

Build reverse queries from `base_query`, as above, to avoid accidentally retaining the forward-only source/sink fields. Merely changing `direction` while keeping every `source_*` and `sink_*` input unchanged usually describes a different grid state. The downloadable script's `directional_conditions` helper maps region-keyed assumptions into either direction. Electrical positive/negative group features also swap when reversing; source-minus-sink VRE and sink-minus-source residual differences change sign for the same physical state.

**How to read the signs:** the package's forward limit comes from the reported export limit. Its reverse directional capacity is `-IMPORTLIMIT`. A negative directional value is retained because it can encode forced flow. Do not take absolute values or replace negatives with zero.

If you want an illustrative signed-flow band in the link's forward coordinate, the median endpoints are `lower=-reverse["p50_mw"]` and `upper=forward["p50_mw"]`. These are independent directional medians, not a jointly secure or calibrated interval. If they cross, flag the case rather than sorting or clamping them. When negating a whole distribution the quantile ordering reverses: P10 of a negated variable is minus the original P90.

<!-- WORKED_RESULTS -->

## 7. Inspect the evidence before using a number

```python
for field in ["bundle_id", "method", "status", "exact_days", "analogue_days",
              "outage_episodes", "relaxed_conditions", "outside_support",
              "known_outage_state_share", "low_support_reason", "reason"]:
    print(field, result.get(field))

historical_examples = pd.DataFrame(result.get("analogues", []))
restrictive_cases = pd.DataFrame(result.get("stress_examples", []))
print(historical_examples)
print(restrictive_cases)
```

P10/P50/P90 describe the returned conditional reported-limit distribution. Lower limits are generally the restrictive side. They are not guaranteed physical bounds or unconditional probabilities for a future day.

| Status | How to use it |
|---|---|
| `supported_table` | Strict table with the declared minimum historical support; calibration is still a separate question. |
| `indicative_table` | Matching observations exist, but independent-day/episode support is below the convention. |
| `supported_analogue` | Weighted analogue selection meets its support convention without declared relaxation. |
| `broader_analogue` | Broader, out-of-support or insufficiently repeated comparison. Read `relaxed_conditions`, `outside_support` and the support reason. |
| `reference` | Quarter/diurnal baseline. |
| `modelled_extrapolation` | Fitted model estimate; the query's tail calibration is not established. |
| `unavailable` | No usable result for this request. Quantiles can be `None`; do not convert them to zero. |

The current support convention is 20 independent exact-condition days and, for outage-specific cases, five linked episodes. Counts are not evidence that rare-event probabilities are calibrated. `outage_episodes` for an unconditioned case can count background episodes; inspect `requested_episode_counts` for an explicitly requested component. Stress rows are observed examples without invented occurrence probabilities.

## 8. Compare tables, analogues and tight restrictions

```python
analogue = bundle.select({**conditions, "method": "analogue"})
tight = bundle.select({**conditions, "target": "tight"})

print(analogue["method"], analogue["status"], analogue.get("relaxed_conditions"))
print("Average-limit P10:", result["p10_mw"])
print("Tight-limit P10:", tight["p10_mw"])
```

The analogue method weights nearby historical cases and can use neighbouring delivery half-hours. If it returns a broader comparison, the result explains the relaxation. A known incompatible network era or a required topology component is not removed to manufacture a match. `unweighted` is an alternative analogue comparator; `baseline` is the explicit quarter/diurnal comparator.

`target="tight"` changes the target to the minimum of the six five-minute limits. The `tight_p10_mw` field accompanying an average query is also a risk diagnostic, but it does not supply the full tight-target distribution. Request the tight target for its P10/P50/P90.

## 9. Generate a profile or a batch

```python
profile_conditions = {k: v for k, v in conditions.items()
                      if k not in {"quarter", "half_hour"}}
profile = bundle.profile(1, profile_conditions)
assert len(profile) == 48
print(profile[["half_hour", "p10_mw", "p50_mw", "p90_mw", "status"]])

# A list of dictionaries returns a list of evidence-rich dictionaries.
requests = [conditions, reverse_conditions]
both = bundle.select(requests)

# A DataFrame returns a DataFrame. Different directional fields create missing
# cells; replace pandas NaN with None before calling this version of the package.
batch_inputs = pd.DataFrame(requests).astype(object)
batch_inputs = batch_inputs.where(batch_inputs.notna(), None)
batch = bundle.select(batch_inputs)
```

`profile` holds your supplied scenario conditions fixed while changing the 48 ending periods. It does not generate a weather or demand path. To vary assumptions by delivery period, create one query dictionary per interval and call `select` on that list. A list is particularly convenient when different rows supply different fields.

## 10. Export and integrate

```python
from pathlib import Path
import json

bundle.export(result, "my_outputs/one_interval.json")
bundle.export(profile, "my_outputs/q1_profile.csv")
bundle.export(both, "my_outputs/both_directions.json")

Path("one_interval_conditions.json").write_text(
    json.dumps(conditions, indent=2), encoding="utf-8")
saved_conditions = json.loads(Path("one_interval_conditions.json").read_text(encoding="utf-8"))
same_result = bundle.select(saved_conditions)
```

JSON preserves nested evidence, requested conditions and stress rows. CSV suits summary tables and Excel. Keep the request JSON and bundle identity with each exported result so that a later refresh does not silently change the meaning of an old number. `bundle.explain(conditions)` returns the same evidence-rich selection; it does not run a separate causal model.

The same calculation is available through the command line:

```powershell
.\.venv\Scripts\python.exe -m nemic_regimes select --bundle ./regime_bundle --conditions ./one_interval_conditions.json --output ./my_outputs/cli_result.json
.\.venv\Scripts\python.exe -m nemic_regimes serve --bundle ./regime_bundle --port 8061
```

The second command opens the local service at `http://127.0.0.1:8061`. It stays running until you stop that process. If another selector is already using that port, reuse it or choose another port such as `--port 8064`. It does not create a recurring schedule.

## 11. Full input reference

You submit conditions as a Python dictionary, JSON object, list of such objects, or a prepared pandas DataFrame. The engine reads its saved Parquet history internally. It does not directly read arbitrary Excel workbooks or convert raw AEMO CSV columns into conditions for you. For CSV integration, read your CSV with pandas, map its columns to these fields, and prepare missing values as shown above.

### Query controls

| Field | Accepted meaning |
|---|---|
| `connector` | One of the six names or mapped AEMO IDs. Supply it explicitly. |
| `direction` | `forward` or `reverse`; default forward. |
| `quarter` | Integer 1–4. Required for `select`; positional first argument for `profile`. |
| `half_hour` | Integer 0–47. Required for `select`; generated by `profile`. |
| `era` | `current` or an explicit compatible era listed below. |
| `target` | `average` or `tight`; default average. |
| `method` | `table`, `analogue`, `unweighted`, `baseline`, `auto`, `additive`, `boosting`. Select explicitly for reproducibility. |
| `daytype` | `weekday` or `weekend`, or omit. |
| `regime` | A saved named condition, or `reference`. Discover definitions from metadata. Explicit fields override the named definition. |
| `required_sets` | List of mapped constraint-set IDs that must be present; other concurrent sets are allowed. |
| `excluded_sets` | List of mapped set IDs that must be absent. |
| `required_assets` | List of historical mapped equipment IDs; not free-text equipment names. |
| `exact_sets` | `True` requires the entire mapped set combination to match `required_sets`. |
| `outage_state` | `any`, `clear`, `invoked` or `partial`. `clear` means no mapped relevant invocation, not proof all equipment is available. |
| `scenario_name` | Your own label, retained with the request. |
| `mode` | `scenario` for general assumptions; `asof` for dated input validation. |
| `allow_extrapolation` | Explicit opt-in to fitted model use; does not grant historical support. |
| `origin`, `delivery`, `inputs` | Additional dated-selection fields described in section 13. |

### Numeric conditions

All these fields accept a finite scalar or inclusive `min`/`max` bounds. Regional demand, VRE and available-generation features in the historical panel are complete half-hour averages. MW ramps are the value minus the value one hour earlier, not a per-minute rate.

| Field(s) | Units | What to supply |
|---|---|---|
| `source_temperature`, `sink_temperature` | °C | Mean 2 m temperature across the three configured sites in that region. |
| `temperature_max` | °C | Maximum 2 m temperature across the six configured sites of the region pair. Not a daily maximum. |
| `humidity_mean` | % | Mean relative humidity across the configured pair's sites. |
| `source_vre`, `sink_vre` | MW | Regional cleared wind plus utility-scale solar. Rooftop PV is not added to this measure. |
| `source_demand`, `sink_demand` | MW | AEMO TOTALDEMAND basis, already net of rooftop PV. |
| `source_residual`, `sink_residual` | MW | The matching regional demand minus the matching VRE field. Do not subtract rooftop PV again. |
| `vre_difference` | MW | Source VRE minus sink VRE. |
| `residual_difference` | MW | Sink residual demand minus source residual demand. Note the opposite subtraction convention. |
| `source_vre_ramp_1h`, `sink_vre_ramp_1h` | MW | Regional VRE now minus one hour earlier. |
| `residual_difference_ramp_1h` | MW | Change in the sink-minus-source residual difference over one hour. |
| `source_available_generation`, `sink_available_generation` | MW | AEMO regional AVAILABLEGENERATION basis. |
| `electrical_positive_mw`, `electrical_negative_mw` | MW | Frozen sensitivity-weighted DUID group dispatch measures, with direction-specific grouping. These are not simple regional generation totals. |
| `corridor_wind_ms` | m/s | Mean 100 m wind speed at the pair's configured corridor sites. |
| `corridor_radiation_wm2` | W/m² | Mean shortwave radiation at those corridor sites, preserving the source radiation-hour convention. |
| `corridor_cloud_pct` | % | Mean cloud cover at those corridor sites. |

The configured site groups are NSW: Sydney/Armidale/Dubbo; QLD: Brisbane/Millmerran/Rockhampton; VIC: Melbourne/Heywood/Horsham; SA: Adelaide/Robertstown/Jamestown; TAS: Hobart/George Town/Woolnorth. The middle site in each group is the corridor site. A single airport temperature or arbitrary regional wind index is not automatically the same feature.

Electrical-group membership and weights are in the research package's `electrical_groups.csv`. Reproduce that definition before supplying these specialist measures; otherwise omit them. Battery dispatch is not stored energy. A storm condition is not proof of a contingency reclassification. Unknown inputs remain unavailable or unspecified.

## 12. Outage IDs, named conditions and structural eras

Discover saved named conditions before using them:

```python
definitions = bundle.metadata["settings"]["QNI/forward"]["regimes"]["1"]
print(definitions)  # name -> measurable condition definition
```

For historical component IDs, inspect the compatible slice of the bundle's diagnostic panel:

```python
history = bundle.panel
era = bundle.metadata["current_eras"]["QNI"]
history = history[(history.connector == "QNI") &
                  (history.direction == "forward") & (history.era == era)]
known_sets = sorted({token for text in history.active_sets.dropna()
                     for token in text.split("|") if token})
known_assets = sorted({token for text in history.active_assets.dropna()
                       for token in text.split("|") if token})
print(known_sets)
print(known_assets)
```

This is a list of historical mapped components, not a live outage schedule. After verifying the relevant ID and interpretation, add `required_sets=[verified_id]` or `required_assets=[verified_asset_id]` to a scenario. Some sets are background or system-normal sets, so presence alone does not mean an equipment outage. Keep booked, invoked, binding and reported-limit-setting states distinct. `exact_sets=True` is demanding and can leave little support. Unknown or unmapped configurations can return unavailable.

| Connector group | Saved eras in this bundle |
|---|---|
| QNI, Directlink | `qni_existing` |
| VNI, Heywood, Murraylink | `pre_pec_market`, `pec_market` (market change boundary 1 October 2026) |
| Basslink | `mnsp`, `regulated` (boundary 1 July 2026) |

PEC is conditioning context, not a seventh output. A Q1 request in the current PEC era has no same-era Q1 history in this bundle. Strict tables can therefore return unavailable; analogues may return a within-era broader comparison with quarter relaxed. Do not choose the old era merely to make a present-era query look supported. Use old eras explicitly for historical-comparison scenarios.

## 13. Automatic inputs and dated selections

Ordinary scenario queries require no fabricated source receipts. If you want machine suggestions, collection is an explicit separate action:

```python
from nemic_regimes.collect import latest_grid, weather

# Makes a public network request and retains its payload/receipt evidence.
snapshot = latest_grid(connector="QNI", direction="forward", output="new_inputs")
suggested_scenario = {**base_query, **snapshot["conditions"],
                      "scenario_name": "latest_observed_grid_assumption"}
suggested_result = bundle.select(suggested_scenario)
```

This uses the latest observed regional dispatch values as assumptions for your chosen general scenario. They are not automatically forecasts for its delivery half-hour. Preserve `snapshot["inputs"]` and the original suggestion separately from any edited scenario. The weather collector additionally requires a timezone-aware explicit model `run` and `delivery`; it retrieves a coherent six-site run and returns `conditions` plus provenance. Provider availability and historical coverage can fail; the tutorial script makes no network calls.

For `mode="asof"`, supply `origin`, `delivery` and `inputs`, with quarter/half-hour matching delivery. Each supplied operating condition needs a matching eligible record or an explicitly named user assumption. Machine records require source, product, run ID, issue time, measured received/completed times, delivery, value, hash, canonical units and correct regional coverage. Coherent input groups must not mix runs. The bundle's training cutoff must precede origin. A currently downloaded historical archive cannot substitute for a receipt measured at the historical origin.

The [Python runbook](downloads/RUNBOOK_PYTHON.md) describes this advanced contract. General scenarios are the appropriate starting point for this tutorial. Historical as-of performance has zero eligible rows in this research campaign; valid new provenance does not turn its conditional estimates into a validated forecast service.

## 14. Optional fitted models and common mistakes

The two challengers require the model installation extra, which pins compatible saved-estimator dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install "./downloads/nemic_regimes-0.1.0-py3-none-any.whl[models]"
```

```python
model_result = bundle.select({
    **conditions,
    "source_temperature": 28,       # explicit point assumptions for the model
    "sink_residual": 5500,
    "method": "additive",          # or boosting
    "allow_extrapolation": True,
})
print(model_result["method"], model_result["status"])
print(model_result.get("model_request_status"))
```

Supply point assumptions for model queries: this version converts bounds to their mean supplied endpoint(s); it does not integrate over every value inside a band. Missing model inputs are training-imputed assumptions. A model cannot represent every specific asset/set/feature request; inspect the actual returned method and status because a labelled analogue reference can be returned instead. No historical challenger passed every calibration and risk gate, so a model result is an explicitly separate exploratory estimate.

| Symptom | What to check |
|---|---|
| `ModuleNotFoundError` | Install into the interpreter you are actually running; prefer `python -m pip`. |
| Missing manifest / hash mismatch | Extract the bundle correctly and keep its files intact. Do not bypass a failed hash check. |
| `Non-finite ...` | Replace DataFrame missing cells with `None`, or use a list of dictionaries that omits unspecified fields. |
| No strict-table observations | Inspect era/quarter, units and condition specificity. An unavailable result is useful information. |
| Broad analogue despite many rows | Inspect exact days, requested-outage repetitions, outside-support fields and relaxed conditions. |
| Negative result | Check direction/sign semantics and stress evidence; preserve the sign. |
| Different results after reversing | Verify the physical inputs were remapped, rather than only the direction label changed. |
| A full profile appears too constant in its inputs | `profile` reuses your assumptions; create separate interval queries for a changing demand/weather path. |
| Saved model dependency error | Use the pinned `models` extra or `requirements-bundle-v1.txt`; the saved 1.6 estimators are not compatible with every later scikit-learn release. |

## Downloads and reproducibility

[Runnable tutorial script](downloads/tutorial.py) · [Actual worked outputs](downloads/summary.json) · [Forward/reverse comparison](downloads/both_directions.csv) · [Forward full profile](downloads/forward_profile.csv) · [Reverse full profile](downloads/reverse_profile.csv) · [Method comparison](downloads/method_comparison.csv) · [Python runbook](downloads/RUNBOOK_PYTHON.md) · [Installable wheel](downloads/nemic_regimes-0.1.0-py3-none-any.whl) · [Saved bundle](downloads/nemic_regimes_bundle_v1.zip) · [Pinned research runtime](downloads/requirements-bundle-v1.txt).

The worked outputs are produced by the accompanying script against the identified bundle. Their limits are conditional historical estimates, not operational recommendations. The original research findings and failed historical risk/calibration gates remain unchanged. This tutorial adds usage material; it does not retrain, promote or schedule anything.
