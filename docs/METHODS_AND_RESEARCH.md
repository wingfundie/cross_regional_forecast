# Methods and research

This document describes the implemented INTERFLOW experiment, audited against the source and saved results on 11 September 2026. Read it with the [backtest protocol](BACKTEST_PROTOCOL.md) and [executed results](../BACKTEST_REPORT.md). The [build plan](../BUILD_PLAN.md) records the agreed scope; where a proposal differs from execution, this document and the executable implementation describe the run.

## 1. Question and interpretation

Can public regional demand, renewable generation, temperature/weather and recently observed network conditions predict AEMO's reported interconnector limits and dispatch flows at half-hour resolution, from 30 minutes to seven days ahead?

The main experiment supplies **realised future exogenous inputs**. It tests a conditional relationship: given the future demand, renewable generation and weather path, how well can the model estimate limits and flows? It does not measure the accuracy achievable when those paths must themselves be forecast. Realised renewable dispatch can also respond to congestion, so this experiment is not a clean causal model or a guaranteed operational upper bound.

AEMO's reported limits are calculated from dispatch outcomes and restrictive constraints. They are not standalone transmission ratings or the maximum secure transfer achievable after redispatch. Changing another generator or interconnector can change a reported limit. Consequently, forecasts across connectors and directions are **not a simultaneously feasible network dispatch**. This target interpretation follows [AEMO's February 2024 incident report, Appendix A](https://aemo.com.au/-/media/files/electricity/nem/market_notices_and_events/power_system_incident_reports/2024/final-report---loss-of-moorabool---sydenham-500-kv-lines-on-13-feb-2024.pdf) and its [constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq).

## 2. Research reviewed and how it influenced the implementation

| Source | Relevant finding or method | What this project uses | What it does not establish |
|---|---|---|---|
| Abdel-Khalek, Schäfer, Vásquez, Unnewehr and Weidlich (2019), *Forecasting cross-border power transmission capacities in Central Western Europe using artificial neural networks*, Energy Informatics 2, article 12, DOI 10.1186/s42162-019-0094-y. [Paper](https://d-nb.info/1204086990/34) | Nonlinear autoregressive models with exogenous public generation/load inputs; persistence is a difficult short-horizon benchmark. Future actual inputs make longer-horizon experiments optimistic. | Lagged network state, public fundamentals, persistence comparisons and explicit conditional-input labelling. | We did not reproduce its neural network. European MAXBEX targets are not NEM dispatch limits; its findings do not validate seven-day NEM accuracy. |
| *Calculation of the available transfer capability of trading channels based on power network congestion forecasting* (2024), Frontiers in Energy Research, DOI 10.3389/fenrg.2024.1351306. [Paper](https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2024.1351306/full) | Boosted congestion forecasting is combined with network sensitivity and transfer-capability calculations. | Motivation for testing nonlinear tree models and restriction probabilities. | Our implementation does not reproduce its classifier, physical sensitivity model or available-transfer-capability optimisation. |
| Hyndman and Athanasopoulos, *Forecasting: Principles and Practice*, third edition, [time-series cross-validation](https://otexts.com/fpp3/tscv.html) | Forecast evaluation must preserve time order and can evaluate multiple steps at successive origins. | Chronological training/validation/test boundaries and rolling forecast origins. | The executed test uses frozen models, not repeated refitting at every origin. |
| AEMO [constraint FAQ](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq) and [incident report Appendix A](https://aemo.com.au/-/media/files/electricity/nem/market_notices_and_events/power_system_incident_reports/2024/final-report---loss-of-moorabool---sydenham-500-kv-lines-on-13-feb-2024.pdf) | Constraint equations couple dispatch variables; reported limits depend on the solution and limiting equations. | Preserve signs and forced-flow states; use observed setter/regime information; interpret outputs as reported-limit forecasts. | A reported directional limit is not an independent physical capacity certificate. |
| AEMO MMS [dispatch interconnector schema](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_127.htm) and [regional dispatch schema](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_240_1.htm) | Definitions of dispatch flow, metered flow, limits, intervention runs and regional generation fields. | Targets and regional field mapping below; physical dispatch versus pricing-run distinction. | Metered flow is retained for inspection but is not the trained flow target. |
| Open-Meteo [historical weather API](https://open-meteo.com/en/docs/historical-weather-api) | Hourly reanalysis and variable-specific temporal definitions. | Consistent ERA5 data, explicit UTC conversion and preceding-hour radiation handling. | ERA5 is not weather known at forecast issue time. |
| Open-Meteo [historical forecast](https://open-meteo.com/en/docs/historical-forecast-api), [previous runs](https://open-meteo.com/en/docs/previous-runs-api), and [single runs](https://open-meteo.com/en/docs/single-runs-api) APIs | Forecast archive products differ in coverage and vintage semantics. | Research into a future operational-input extension; exact run and availability timestamps would be needed. | These forecast products were not used in this completed backtest. A stitched series alone does not prove issue-time availability. |

This was a targeted applied literature and industry-documentation review, not a systematic review of every forecasting method. Residual calibration, the four lead bands, fixed tree settings and the 50% restriction rule are project design choices. They are not presented as a verbatim method from the cited papers. The 50% rule reflects the user's requested decision threshold.

## 3. Connectors and five outputs

| MMS identifier | Name | Positive flow / export direction |
|---|---|---|
| NSW1-QLD1 | QNI | NSW to Queensland |
| N-Q-MNSP1 | Directlink | NSW to Queensland |
| VIC1-NSW1 | VNI | Victoria to NSW |
| V-SA | Heywood | Victoria to South Australia |
| V-S-MNSP1 | Murraylink | Victoria to South Australia |
| T-V-MNSP1 | Basslink | Tasmania to Victoria |

Import is the reverse direction in this table. For each interval-ending half-hour, aggregate its six five-minute physical dispatch records:

- `flow`: mean `MWFLOW`, signed in the direction above.
- `export`: mean `EXPORTLIMIT`.
- `import`: mean of **minus `IMPORTLIMIT`**.
- `export_tight`: minimum five-minute `EXPORTLIMIT`.
- `import_tight`: minimum five-minute value of minus `IMPORTLIMIT`.

All outputs are MW. Negative directional limits are preserved: an absolute value would incorrectly turn a forced-flow state into apparently available transfer capacity. The two tightest limits may occur at different five-minute timestamps. They summarise restrictions and need not define a jointly feasible range. Incomplete half-hours are assigned missing targets, never averaged as if complete. None occurred in this run.

These six identifiers cover the observed historical target series. A seventh standalone EnergyConnect three-year record was not invented. Newly represented links would require standing-data review and a separate cold-start/scenario treatment.

## 4. Data processing and provenance

The window is `(2023-09-01 00:00, 2026-09-01 00:00]`, in fixed UTC+10 NEM time without daylight saving. There are 52,608 half-hours, 315,648 connector/half-hour rows and 1,893,888 retained five-minute connector rows.

NEMWEB monthly archives and a daily tail supply `DISPATCHINTERCONNECTORRES`, `DISPATCHREGIONSUM`, `DISPATCHPRICE` and `ROOFTOP_PV_ACTUAL`. The downloader handles archive filename variants, nested ZIPs and table header versions. Original archives, source URLs and SHA-256 checksums are retained in `data/raw/` and `data/manifest.json`. Original predispatch files are separately retained for benchmarking.

For dispatch duplicates, records are ordered by time, identifier, intervention, run number and last-changed time; the final record is selected. Thus physical intervention run 1 takes precedence when present, otherwise run 0. Price context filters to intervention 0. This is an archive-based actuals reconstruction, not a full reconstruction of every record revision as seen live.

Regional five-minute quantities are averaged only when six distinct observations exist. For rooftop PV, measurement records take precedence over other types, then latest change time resolves duplicates. Thirty-four rooftop feature cells remain missing; LightGBM receives missing values directly. Other model drivers and all targets are complete.

| Input | Raw definition | Use |
|---|---|---|
| Demand | `TOTALDEMAND` | Future realised regional demand |
| Wind, solar | `SS_WIND_CLEAREDMW`, `SS_SOLAR_CLEAREDMW` | Future realised semi-scheduled generation |
| Available wind, solar | `SS_WIND_UIGF`, `SS_SOLAR_UIGF` | Alternative availability ablation |
| Rooftop | `ROOFTOP_PV_ACTUAL.POWER` | Separate explanatory input |
| Residual demand | demand minus cleared wind minus cleared solar | Derived regional balance proxy |
| Generator availability | `AVAILABLEGENERATION` | Delayed origin feature only |
| Network state | Local constraint flags, setter IDs, intervention and violation degree | Delayed origin features only |
| Regional price | `DISPATCHPRICE.RRP`, pricing run | Descriptive price spreads only |

TOTALDEMAND already reflects rooftop generation: rooftop is not subtracted again. Semi-scheduled cleared generation does not represent every renewable generator in the NEM.

Weather uses ERA5 at 15 representative sites: Sydney, Armidale, Dubbo; Brisbane, Millmerran, Rockhampton; Melbourne, Heywood, Horsham; Adelaide, Robertstown, Jamestown; Hobart, George Town, Woolnorth. These are demand, corridor and renewable-area proxies, not an optimised spatial weighting or a line-by-line thermal model. Exact coordinates, requests and checksums are in `data/weather_manifest.json` and `nemic/weather.py`.

The five variables are temperature at 2 m (degrees C), wind speed at 100 m (m/s), shortwave radiation (W/m²), cloud cover (%) and relative humidity at 2 m (%). UTC timestamps are shifted by ten hours. Temperature, wind, cloud and humidity are linearly interpolated to half-hours. Each preceding-hour mean radiation value is assigned to both contained half-hours, preserving source hourly energy. This interpolation uses realised weather and is appropriate only to the declared conditional experiment.

## 5. Models actually fitted

Six candidate methods are compared. Five separate targets are predicted; all six connectors are pooled within each fitted regressor using a categorical connector identifier.

| Method | Definition / features | Purpose |
|---|---|---|
| Persistence | Latest eligible half-hour value, normally origin minus 30 minutes | Strong short-horizon reference |
| Weekly seasonal | Same delivery slot one week earlier; use two weeks earlier at exactly lead 336 to keep the observation available | Weekly reference |
| Fundamentals | Delivery-time demand, wind, solar, rooftop and residual demand in all five regions; calendar/trend; connector | Public regional balance relationship |
| Weather | Fundamentals plus 75 site/weather features | Incremental weather information |
| Availability | Weather variant with UIGF replacing cleared wind/solar and corresponding residual demand recalculated | Sensitivity to renewable availability versus cleared output |
| Network | Weather features plus lead and delayed network/history features | Persistence of restrictions and interactions across links |

Static variants use 25 regional features and six calendar/trend features: daily sine/cosine, annual sine/cosine, weekday and elapsed days. Including the connector gives 32 features for fundamentals and 107 for weather/availability. Static predictions depend on delivery conditions, not lead; the same delivery state is reused across forecast origins.

The network model has 141 features: 106 future driver/calendar features, connector ID, lead and log(1+lead), all five target lags at 1/48/336 half-hours, six origin-state fields, five regional generation-availability values and all six origin connector flows. Setter categories are encoded from training only; unseen categories become missing. This is a direct lead-conditioned regressor, not recursive simulation through predicted network states.

Each connector/target label is divided by its training population standard deviation, floored at 10 MW; labels are not demeaned. Predictions are converted back to MW. This reduces domination by high-MW links during pooled fitting.

All fitted models use LightGBM `LGBMRegressor`: absolute-error objective (`regression_l1`), 180 estimators, 23 leaves, learning rate 0.055, minimum child samples 120, column fraction 0.9, L2 regularisation 5, four worker threads, seed 741, deterministic mode and column-wise computation. Other settings use library defaults recorded with the environment. No hyperparameter grid search or neural-network fitting was run.

There are 20 fitted regressors: three static variants plus network, each with five targets. Static training uses 210,528 connector/delivery rows per target. Network training samples one random lead from each of four bands at each eligible origin, then removes targets outside training. The saved run has 831,798 pooled origin/lead rows per target. Validation selects among these models and the two baselines; it does not refit the winners.

## 6. Restrictions and uncertainty

For connector c, direction d and delivery season s, reference R is the median **positive average directional limit** in training. Seasons are December–February, March–May, June–August and September–November. The restriction threshold is T = 0.5 R. A restriction means actual limit < T, strictly. The same reference applies to average and tight targets. Zero/negative observations are excluded only from calculating R; they remain targets and restriction events. References are descriptive seasonal normals, not engineering ratings.

Selection is separate for each connector × target × lead band. After choosing the lowest-MAE candidate, calculate calibration residuals e = actual − raw prediction. Store 501 empirical residual quantiles at probabilities 0, 0.002, …, 1. P10/P50/P90 equal the raw prediction plus the corresponding residual quantile. The selected P50 therefore includes a median residual adjustment and can differ from the raw winner.

Restriction probability approximates F_e(T − raw prediction), interpolating through this residual quantile grid and clipping outside its range to 0/1. It is not a separately trained classifier. A February validation window tunes its alert cutoff to maximise F2 = 5TP/(5TP + 4FN + FP), reflecting the preference to avoid misses. Cutoffs range 0.05–0.80 in steps of 0.025; ties favour the highest cutoff. Cells with no validation events use an explicitly labelled 0.20 default.

These are marginal empirical residual intervals within a connector/target/band, not distribution-free conformal guarantees or joint seven-day trajectories. The completed test's nominal 80% intervals covered only **72.3%** of outcomes when weighted across cells. Undercoverage must be visible when using them. Independent target fits also impose no physical consistency constraint between predicted flow and limits, between mean and tight forecasts, or across connectors.

## 7. Explanation, scenarios and boundaries

Saved tree feature importances and candidate ablations describe model reliance and predictive differences. Correlated demand, renewable and weather variables can share importance; importance does not identify causation. Regional price-spread views show historical associations. There is no causal price model, trading strategy, P&L backtest or redispatch optimisation.

The scenario runner accepts 336 half-hour future input rows and uses observed history at the issue timestamp. Its 2,016-row example covers all six connectors. Scenario changes are conditional model responses; they do not resolve market equilibrium after changed flows. Later issue dates require new observed network history. Future planned outages, bids and thermal availability are not reconstructed.

Operational extensions would require archived issue-time demand/renewable/weather forecasts, publication-aware actuals, outage/constraint information available at each origin, and a new untouched evaluation period. A full-year test and more restriction regimes are needed before claims of seasonal robustness. Multivariate physical consistency, dedicated event-duration evaluation and recalibration under drift are further research tasks, not completed features.

## 8. Implementation map

For prioritised extra data, alternative modelling concepts and how to establish gains, see the [improvement roadmap](IMPROVEMENT_ROADMAP.md). Its recommendations are explicitly untested proposals.

`nemic/ingest.py` downloads/extracts; `weather.py` prepares ERA5; `prepare.py` defines targets and drivers; `model.py` fits/selects/calibrates; `backtest.py` evaluates; `benchmark_download.py` and `aemo_benchmark.py` match AEMO vintages; `scenario.py` runs paths; `report.py` generates results; `app.py` presents the dashboard. Exact backtest timing, metrics and reproduction instructions follow in the [protocol](BACKTEST_PROTOCOL.md).
