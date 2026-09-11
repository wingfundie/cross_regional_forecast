# INTERFLOW — NEM interconnector conditional backtest

Executed 2026-09-11 01:21 UTC. Local dashboard: http://127.0.0.1:8050

## What was completed

- September 2023 through August 2026: 36 complete months, all six historical NEM interconnectors.
- 315,648 connector/half-hour observations and 1,893,888 retained five-minute observations. No missing flow or limit targets.
- Five targets: signed dispatch flow, average export/import directional limits and tightest five-minute export/import limits within each half-hour.
- 17,467,632 test origin/lead pairs; 87,338,160 target forecasts. Every available half-hour origin and all leads 30 minutes through seven days are covered. Origins near the dataset end have appropriately truncated horizons.
- P10/P50/P90, calibrated restriction probabilities, per-link/per-horizon model comparisons, seven-day block uncertainty estimates, original-vintage AEMO comparison, and a runnable seven-day scenario example.

## Results

The selected and calibrated forecasts beat persistence on MAE in **92 of 120 connector/target/lead-band cells**. This count weights every cell equally; it is not a portfolio performance measure. Some cells can lose even though the underlying method was selected on validation. The detailed score table retains all losses.

The sample-weighted empirical coverage of the nominal 80% intervals is **72.3%**. Check individual target/horizon coverage in the dashboard: aggregate coverage can hide undercoverage. Uncertainty intervals are marginal; they do not guarantee simultaneous coverage across all 336 horizons or all connectors.

### Test MAE, MW

| Interconnector | Target | 0–6h | 6–24h | Days 2–3 | Days 4–7 |
| --- | --- | --- | --- | --- | --- |
| QNI | flow | 206.5 | 234.2 | 234.4 | 234.0 |
| QNI | export | 121.9 | 180.3 | 227.9 | 311.6 |
| QNI | import | 123.9 | 189.5 | 223.0 | 254.7 |
| QNI | export_tight | 131.0 | 189.7 | 237.2 | 257.4 |
| QNI | import_tight | 132.5 | 201.5 | 235.0 | 267.4 |
| Directlink | flow | 34.3 | 35.1 | 37.0 | 37.6 |
| Directlink | export | 28.3 | 31.4 | 33.6 | 63.0 |
| Directlink | import | 33.4 | 37.1 | 38.5 | 39.1 |
| Directlink | export_tight | 32.4 | 66.2 | 66.9 | 68.2 |
| Directlink | import_tight | 34.8 | 38.5 | 39.6 | 39.5 |
| VNI | flow | 248.7 | 271.4 | 269.0 | 266.2 |
| VNI | export | 231.5 | 254.0 | 254.7 | 255.3 |
| VNI | import | 186.3 | 200.7 | 205.2 | 206.3 |
| VNI | export_tight | 246.2 | 272.6 | 273.3 | 274.1 |
| VNI | import_tight | 198.6 | 214.1 | 218.9 | 218.0 |
| Heywood | flow | 132.9 | 132.7 | 132.9 | 132.5 |
| Heywood | export | 118.4 | 140.9 | 151.7 | 159.3 |
| Heywood | import | 157.7 | 201.8 | 212.0 | 216.2 |
| Heywood | export_tight | 136.0 | 152.5 | 162.1 | 168.0 |
| Heywood | import_tight | 177.0 | 214.0 | 224.3 | 229.8 |
| Murraylink | flow | 49.6 | 59.4 | 60.0 | 60.8 |
| Murraylink | export | 44.8 | 57.9 | 58.4 | 59.5 |
| Murraylink | import | 51.2 | 57.0 | 57.4 | 57.5 |
| Murraylink | export_tight | 50.8 | 64.6 | 65.0 | 66.1 |
| Murraylink | import_tight | 51.1 | 58.2 | 58.4 | 58.7 |
| Basslink | flow | 95.0 | 138.1 | 142.5 | 173.3 |
| Basslink | export | 97.0 | 145.5 | 153.8 | 186.9 |
| Basslink | import | 107.1 | 144.9 | 145.4 | 184.6 |
| Basslink | export_tight | 97.4 | 148.4 | 156.6 | 192.4 |
| Basslink | import_tight | 112.8 | 150.4 | 150.8 | 151.3 |

### Restriction detection

A flag means the directional limit is below **50% of its training-only seasonal median of positive directional limits**. Forced-flow and zero outcomes remain in the target and can be flagged. Alert probability thresholds were tuned on February validation data to maximise F2, giving recall greater weight than precision. These are reported-limit restrictions, not classifications of line outages or maximum secure physical capability.

| Interconnector | Direction | Recall | Precision | Event pairs | False alerts |
| --- | --- | --- | --- | --- | --- |
| QNI | export | 52.9% | 50.2% | 1,283,273 | 674,268 |
| QNI | import | 54.5% | 39.4% | 742,297 | 622,286 |
| Directlink | export | 75.2% | 33.6% | 957,772 | 1,421,669 |
| Directlink | import | 87.7% | 27.5% | 491,919 | 1,139,763 |
| VNI | export | 72.2% | 73.1% | 671,670 | 178,540 |
| VNI | import | 89.9% | 21.1% | 503,860 | 1,693,799 |
| Heywood | export | 85.3% | 37.9% | 869,572 | 1,214,653 |
| Heywood | import | 96.4% | 49.8% | 1,432,306 | 1,394,208 |
| Murraylink | export | 76.4% | 56.4% | 1,149,244 | 679,320 |
| Murraylink | import | 87.9% | 68.6% | 1,589,319 | 639,566 |
| Basslink | export | 91.9% | 78.2% | 1,970,267 | 503,439 |
| Basslink | import | 99.5% | 72.2% | 2,057,740 | 788,167 |

Counts are forecast-origin/lead pairs, not unique physical events. Repeated forecasts of the same restriction are intentionally retained in rolling-origin evaluation. Per-band metrics, stressed intervals, seasonal slices, Brier scores and five-minute observations are available in the dashboard and CSVs.

## AEMO benchmark

Matched **2,876,052** original AEMO predispatch origin/delivery pairs. Available matched leads span 0.5–39 hours. Original file creation times plus a one-minute ingestion buffer determine the first eligible half-hour origin; no forecast issued after that origin is used. Monthly predispatch snapshots were not treated as complete forecast-vintage archives.

This comparison is deliberately asymmetric: AEMO used forecast inputs, while our experiment is supplied with realised future demand, renewables and weather. It measures conditional explanatory skill, **not operational superiority over AEMO**. Standard predispatch does not provide a comparable seven-day series throughout this sample, and has no target equivalent to the tightest five-minute limit within a half-hour.

## Design and leakage controls

See the [improvement roadmap](docs/IMPROVEMENT_ROADMAP.md) for prioritised additional data and untested modelling proposals, with evaluation requirements.

See [Results, data and feature engineering](docs/RESULTS_DATA_AND_FEATURES.md) for the complete feature inventory, network-state construction and audit of diurnal, seasonal, duck-curve and ramp handling.

For the full research rationale, model specifications and data definitions, see [Methods and research](docs/METHODS_AND_RESEARCH.md). For exact split boundaries, metrics, benchmark alignment and reproduction steps, see [Backtest protocol](docs/BACKTEST_PROTOCOL.md).

1. **Train:** September 2023–August 2025. Fit models, scales, categorical encodings and seasonal references exclusively here.
2. **Select:** September–November 2025. Choose a method separately for each connector, target and lead band on MAE.
3. **Calibrate:** December 2025–January 2026. Estimate the selected method's residual distribution; P10/P50/P90 are its empirical quantiles added to the base prediction.
4. **Alert tuning:** February 2026. Choose probability cutoffs using F2. A cell without validation events retains an explicitly labelled default cutoff.
5. **Test:** March–August 2026. Frozen models, references, calibration and thresholds. No training target crosses its boundary. Validation subperiods also exclude crossing origin/target windows.

The static boosted ablations use one observation per delivery state. The direct network model uses a reproducible random lead from each of four bands at every eligible training origin: roughly 832,000 pooled origin/lead examples per target. In contrast, the final test is exhaustive across all 336 half-hour leads. Boosting uses 180 trees, 23 leaves, absolute-error loss, regularisation and a fixed seed. Baselines include persistence and the same slot one week earlier; at the exact seven-day endpoint, the seasonal baseline uses an earlier observable week rather than the unavailable issue interval.

Future allowed inputs: regional demand, cleared semi-scheduled wind and solar, rooftop PV, and weather reanalysis. A separate availability ablation substitutes UIGF availability for cleared renewables. Origin features include lagged limits/flows, limit setters, local constraint/outage flags, generator availability and other connector flows. A 30-minute observation delay applies; late-published dispatch observations are additionally censored. The timestamp audit found and handled one late half-hour across six links in September 2024.

**Excluded future inputs:** prices, actual future interconnector flows, future realised constraint setters and future thermal availability. Prices are used only for descriptive regional spread analysis.

## Data and interpretation

- Market timestamps are fixed UTC+10 NEM time, without daylight saving. Half-hours are interval-ending; each target uses exactly six five-minute observations.
- Physical intervention runs are preferred when present. Price context uses the pricing run. Raw alternatives are retained in source archives.
- Import direction is minus AEMO's signed IMPORTLIMIT; negative directional values are preserved. Taking absolute values would misrepresent forced-flow states.
- TOTALDEMAND is already affected by behind-the-meter generation. Rooftop is not subtracted a second time. Semi-scheduled wind/solar are clearly distinguished from nonscheduled generation.
- Weather: hourly Open-Meteo ERA5 at 15 demand, corridor and renewable-area locations. Temperature, wind, cloud and humidity are interpolated to half-hours; hourly mean radiation is assigned to the two contained half-hours to preserve energy. This is a sparse regional proxy, not a full transmission line thermal model.
- 34 regional rooftop feature cells remain missing across the complete sample; the trees handle these as missing. Other model drivers are complete. No missing targets were filled synthetically.
- Archived actuals may contain retrospective revisions. Realised renewable dispatch is endogenous to congestion. These limitations prevent interpreting the experiment as a genuinely issue-time operational backtest.
- Future planned-outage schedules are not reconstructed. The network model uses delayed observed constraint regimes and generator availability. Unexpected topology changes can therefore cause large errors.
- EnergyConnect is not fabricated as a seventh three-year series. Existing-link changes are part of the recorded history; standalone new-link forecasts require a commissioning/scenario treatment and subsequent data.
- The final six-month test covers autumn/winter and an endpoint, not a complete seasonal year. Validation has additional seasons, but is not an independent full-year test. Seven-day block bootstrap intervals are approximate under overlapping forecasts and regime shifts.
- Regional price-spread charts establish associations, not the causal price effect of a changed transfer limit. No bidding strategy or trading P&L is claimed.

## Use the dashboard and scenario runner

Run `python app.py` in this folder, then open http://127.0.0.1:8050. Select a connector, historical origin, target and horizon. Forecast shows realised outcomes, P10/P50/P90, persistence, restriction probabilities and five-minute detail. Backtest provides baselines, coverage, recall/precision and matched AEMO results. Drivers isolates feature contributions; Price context shows historical spreads. Scenarios accepts 336 half-hour input rows and exports results for all connectors.

The supplied `results/scenario_template.csv` is a historical example, not a live weather forecast. Use `python -m nemic.scenario --origin "2026-08-24 00:00" --input your_inputs.csv --output scenario_results.csv` for a custom path. For an origin at the final observed timestamp, supply a complete future input path; the code does not invent missing network history for later issue dates.

Run `python run_pipeline.py` to execute the full pipeline. Downloads and fitted models are cached. Test prediction signatures check selected dependencies; they are not complete automatic cache invalidation. Follow the cache guidance in the backtest protocol when changing data, features or settings. Local data and model caches are excluded from Git by default. Package versions are recorded in `results/environment.json`.

## Evidence and files

- `data/manifest.json`: 541 source archives, 8.30 GB compressed, with URLs and SHA-256 checksums.
- `data/weather_manifest.json`: coordinates, variables, native resolution, request parameters and checksums.
- `results/data_audit.json`, `split.json`, `training_proof.json`, `test_proof.json`, `completion_audit.json`: coverage, timing and completeness evidence.
- `results/scores.csv`, `validation_leaderboard.csv`, `skill_confidence.csv`, `aemo_scores.csv`: reusable score tables.
- `results/predictions/`: exhaustive per-origin predictions; `models/selection.json`: frozen selected methods, residual quantiles and alert cutoffs.
- `results/scenario_example.csv`: executed scenario forecasts for every connector and all 336 leads.

## Research and UI references

- [AEMO: reported interconnector limits, Appendix A](https://aemo.com.au/-/media/files/electricity/nem/market_notices_and_events/power_system_incident_reports/2024/final-report---loss-of-moorabool---sydenham-500-kv-lines-on-13-feb-2024.pdf): post-dispatch reported limits are not maximum secure capability.
- [AEMO constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq): constraint equations and binding conditions.
- [Abdel-Khalek et al., capacity forecasting](https://d-nb.info/1204086990/34): public-data forecasting and the importance of persistence benchmarks; European results are not proof of NEM skill.
- [Congestion probability using boosted trees](https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2024.1351306/full): supports testing nonlinear congestion models; this project is not a reproduction of its physical optimisation model.
- [Forecasting: Principles and Practice, rolling origins](https://otexts.com/fpp3/tscv.html): chronological multi-step evaluation.
- [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api): reanalysis data and native temporal definitions.
- [TradingView layouts](https://www.tradingview.com/support/solutions/43000746975-tradingview-layouts-a-quick-guide/) and [Bloomberg Launchpad](https://professional.bloomberg.com/products/bloomberg-terminal/): chart-first layout and compact linked monitors, adapted to the local dark dashboard skill without copied branding.
