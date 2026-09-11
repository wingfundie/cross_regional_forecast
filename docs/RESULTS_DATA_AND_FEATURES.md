# Results, data and feature engineering

This document describes the experiment that was actually completed. It was audited against the implementation and saved outputs on 11 September 2026. It focuses on what the results mean, how raw data became modelling inputs, how network state was represented, and which seasonal and ramp features were or were not present.

Read it with the [backtest protocol](BACKTEST_PROTOCOL.md), [research and model specification](METHODS_AND_RESEARCH.md), [improvement roadmap](IMPROVEMENT_ROADMAP.md), and [generated results report](../BACKTEST_REPORT.md).

## 1. Result scope

The model forecasts six historically observed NEM interconnectors: QNI, Directlink, VNI, Heywood, Murraylink and Basslink. It produces five half-hour targets for each link: signed average dispatch flow, average export and reverse-direction import limits, and the tightest five-minute export and import limits occurring within each half-hour.

The test ran from March through August 2026. Every half-hour was used as a forecast origin, with all available leads from 30 minutes through seven days. The final origins have progressively fewer valid leads because observations end at 1 September 2026. The completed audit contains 17,467,632 connector/origin/lead pairs and 87,338,160 target forecasts.

The principal experiment is conditional on future realised regional demand, renewable generation and ERA5 weather. Its scores answer: “How well can limits and flows be estimated when the future fundamental path is supplied?” They do not represent the accuracy of a live system that must forecast those inputs. Future realised limits, flows, constraint setters, prices and thermal availability were excluded.

## 2. Main results already obtained

The system selected a method separately for 6 connectors × 5 targets × 4 lead bands, creating 120 decisions. The selected, residual-adjusted forecast beat persistence on final-test MAE in 92 of those 120 cells.

| Target | Weighted persistence MAE | Weighted selected P50 MAE | Approximate reduction | Cells beating persistence |
|---|---:|---:|---:|---:|
| Flow | 248.9 MW | 147.9 MW | 40.6% | 20/24 |
| Average export limit | 209.4 MW | 158.7 MW | 24.2% | 16/24 |
| Average import limit | 194.0 MW | 151.9 MW | 21.7% | 20/24 |
| Tight export limit | 222.4 MW | 163.5 MW | 26.5% | 15/24 |
| Tight import limit | 202.9 MW | 155.8 MW | 23.2% | 21/24 |

These pooled MAEs weight every available forecast pair. They are descriptive summaries, not substitutes for per-connector and per-horizon results. A MW error has different operational significance on links of different sizes. Exact cell scores, counts, RMSE and bias are in `results/scores.csv` and the report/dashboard.

Validation selected the network model in 46 cells, persistence in 25, fundamentals in 25, weather in 15, renewable availability in 6 and the weekly seasonal baseline in 3. By target:

| Target | Network | Persistence | Fundamentals | Weather | Availability | Weekly seasonal |
|---|---:|---:|---:|---:|---:|---:|
| Flow | 3 | 5 | 13 | 2 | 0 | 1 |
| Export | 8 | 7 | 2 | 6 | 0 | 1 |
| Import | 14 | 4 | 3 | 1 | 2 | 0 |
| Tight export | 7 | 7 | 6 | 0 | 3 | 1 |
| Tight import | 14 | 2 | 1 | 6 | 1 | 0 |

This pattern matters. Regional fundamentals were frequently sufficient for flow, while the network-enhanced model was selected much more often for import and tight-import limits. A single method should not be called “the best model” for the entire system.

Nominal P10–P90 intervals achieved 72.3% weighted coverage, below their 80% target. They should be treated as under-calibrated empirical intervals. Restriction recall was often high, but precision varied materially; the report contains the connector/direction results. Counts are repeated forecast-origin/lead pairs rather than unique restriction episodes.

## 3. Raw data and target construction

The source window is `(2023-09-01 00:00, 2026-09-01 00:00]` in fixed UTC+10 NEM market time. It contains 1,893,888 five-minute interconnector rows, 52,608 interval-ending half-hours and 315,648 connector/half-hour target rows. Every target half-hour has six distinct five-minute observations.

| NEMWEB table | Main fields used | Role |
|---|---|---|
| `DISPATCHINTERCONNECTORRES` | `MWFLOW`, metered flow, export/import limits, setter IDs, locally-constrained flags, intervention, violation degree and `LASTCHANGED` | Flow/limit targets and delayed network state |
| `DISPATCHREGIONSUM` | Total demand, cleared wind/solar, wind/solar UIGF, available generation/load and dispatchable load | Regional fundamentals and origin availability |
| `ROOFTOP_PV_ACTUAL` | Regional power, type and change time | Separate rooftop PV feature |
| `DISPATCHPRICE` | Regional RRP from pricing run | Descriptive price context only |
| Original predispatch archives | Issue time, delivery time, interconnector flow and limits | Matched AEMO benchmark |

Duplicate physical records were sorted by interval, identifier, intervention run, run number and last-changed time. Intervention run 1 was preferred where it existed; otherwise run 0 supplied the physical outcome. Price context used pricing run 0.

Raw `MWFLOW` is the signed forecast target. Export is raw `EXPORTLIMIT`. Directional import is **minus raw `IMPORTLIMIT`** so it is expressed in the reverse direction. Negative limits were preserved because they can represent forced-flow states; taking an absolute value would change their meaning.

For each half-hour, flow and directional limits are the arithmetic mean of six five-minute outcomes. Tight limits are the minimum of the same six directional values. The import-tight calculation is equivalent to minus the maximum raw signed `IMPORTLIMIT`. Tight export and tight import can come from different five-minute intervals and do not define a jointly feasible physical envelope.

## 4. Regional and weather feature engineering

Five-minute regional quantities were averaged into complete half-hours. For each of NSW, Queensland, South Australia, Tasmania and Victoria, the candidate delivery-time fundamentals were total demand, semi-scheduled cleared wind and solar, rooftop PV, and residual demand = total demand − cleared wind − cleared solar. In the availability ablation, UIGF wind/solar replaced cleared wind/solar and residual demand was recalculated.

`TOTALDEMAND` already reflects behind-the-meter generation, so rooftop PV was retained separately and was not subtracted a second time. Residual demand is a useful balance proxy, but not a complete system net-load measure: it does not enumerate all nonscheduled renewables, storage behaviour, bids, losses or unit-level thermal dispatch.

Hourly ERA5 weather came from 15 representative locations—three in each NEM region—chosen as demand, corridor and renewable-area proxies. Each site supplied temperature at 2 m, wind speed at 100 m, shortwave radiation, cloud cover and relative humidity, adding 75 features. Temperature, wind, cloud and humidity were interpolated to half-hours. The preceding-hour mean radiation value was assigned to both contained half-hours to preserve its source meaning.

The sites are a sparse proxy rather than a transmission thermal model. No conductor temperature, dynamic line rating, high-resolution topology or weather-weighted asset exposure was used. Thirty-four rooftop cells remained missing; LightGBM handled them as missing. Other model drivers and all targets were complete.

## 5. How network state was captured

The network model represents the most recently observable dispatch regime while keeping future network outcomes out of its inputs. Its 141 columns were:

| Feature group | Count | Timing and meaning |
|---|---:|---|
| Delivery-time fundamentals, calendar and weather | 106 | Realised future demand, renewables and weather plus time features |
| Connector identity | 1 | Categorical identifier pooling all six links |
| Forecast lead | 2 | Half-hour lead and `log(1 + lead)` |
| Target history | 15 | All five targets at lags 1, 48 and 336 half-hours |
| Current-link dispatch regime | 6 | Export/import locally-constrained flags, intervention, violation degree, and encoded export/import setter IDs |
| Regional available generation | 5 | One delayed origin value per region |
| NEM interconnector flow state | 6 | One delayed origin flow for each connector |
| **Total** | **141** | Direct lead-conditioned model input |

The lag choices are the latest half-hour, the same time one day earlier and the same time one week earlier. They apply to flow, export, import, tight export and tight import. Simultaneous flows on all six links allow the trees to learn broad cross-link patterns; five regional available-generation values provide a coarse supply-state indicator.

For the forecasted connector, the preceding-half-hour snapshot contains whether export/import was locally constrained, intervention status, maximum constraint violation degree, and latest export/import generic-constraint setter identifiers. Setter values were encoded from training only; unseen or missing setters become `-1`. These IDs are useful regime labels, but they do not parse the constraint equation, RHS drivers, contingency, outage or physical cause.

Every origin observation has a nominal 30-minute delay. The implementation also checks `LASTCHANGED`: if an archived dispatch record was published after the forecast origin, the affected feature is missing. Other-link flows are censored link by link. Regional available generation is conservatively censored when any connector publication check is late at that origin, serving as a common-dispatch-publication proxy. The audit handled a late 13:30 interval on 5 September 2024 changed at 14:10:07 and unavailable to a 14:00 origin.

Persistence normally uses origin minus one half-hour and falls back one more interval when that record is late. At the seven-day endpoint, weekly persistence uses two weeks earlier because the immediately previous weekly slot would be the not-yet-observable issue interval.

This observed-state design can learn persistence of a binding regime, forced-flow condition, availability shift or correlated NEM flow pattern. It does **not** contain future outage schedules, future constraint-set activation, generic-equation/RHS forecasts, unit-level availability paths, topology, dynamic ratings or a power-flow solution. Unexpected topology changes are consequently a major risk.

## 6. What feature importance says

Gain importance from the pooled network regressors consistently placed connector identity, setter IDs, recent target lags and regional residual demand near the top:

- Flow: connector, export setter, one-step flow lag, Victoria/South Australia residual demand, import setter, Queensland residual demand, South Australia wind and annual sine/cosine.
- Export and tight export: export setter, one-step export lag, connector, Victoria residual demand, import setter, one-step tight-export lag and South Australia residual demand.
- Import and tight import: connector, one-step import/tight-import lags, export/import setters, trend, Victoria wind and residual demand. Lag-48 tight import also appears among leading tight-import features.

This supports the hypothesis that current constraint regime and recent limits matter. It does not establish causality. Gain can be split among correlated variables and belongs to the pooled network model even where validation selected another method. Magnitudes should not be compared across separately fitted target models without normalisation.

## 7. Seasonal, diurnal and duck-curve audit

| Behaviour | Implemented? | Exact representation | Assessment |
|---|---|---|---|
| Time of day / diurnal shape | Yes, broadly | Sine/cosine of fractional hour with a 24-hour period | Smooth circular clock representation avoids a midnight discontinuity. Trees can interact it with region, demand, solar and weather. It does not encode separate learned 48-bin shapes. |
| Day of week | Yes | Integer weekday 0–6 | Allows weekday differences, although treated as numeric rather than categorical/cyclic. No holiday feature was included. |
| Annual seasonality | Yes, smoothly | Sine/cosine of day-of-year divided by 365.25 | Represents one annual cycle. It cannot alone express sharp seasonal boundaries or separate daily shapes by month. |
| Summer/autumn/winter/spring | Partly | Four seasons used for training-only restriction references and reporting slices | Season was not a separate model input. The independent test mainly covers autumn/winter, so full-year robustness was not established. |
| Weekly behaviour | Yes | Same half-hour one week earlier and a 336-half-hour network lag | Strong explicit weekly history. Weekly baseline was selected in only 3/120 validation cells. |
| Duck curve / solar-shaped net demand | Implicitly | Delivery demand, cleared solar, rooftop PV, residual demand, radiation and clock | Trees can learn low-midday and higher-evening balance conditions. There is no named duck-curve feature, sunset alignment, trough depth or evening-ramp feature. |
| Renewable ramps | **No explicit ramps** | Delivery levels plus target history | Wind/solar Δ30m, Δ1h, forecast ramps and spatial ramp coherence were not calculated. |
| Demand/residual-demand ramps | **No explicit ramps** | Delivery levels only | The model sees future level and clock position, but not slope, acceleration, daily trough or evening peak gradient. |
| Sunrise/sunset and daylight length | No | Radiation/solar provide indirect information | No solar elevation, sunrise-relative time, daylight duration or regional solar clock. |
| Temperature-load nonlinearity | Implicit | Delivery demand and temperatures | Trees can learn nonlinear splits, but no cooling/heating degree or thermal-accumulation features were engineered. |
| Seasonal ramp interactions | No explicit terms | Possible implicit tree interactions | No winter/summer × hour, season × ramp or daylight interaction was constructed. |

The model has legitimate basic seasonality, but not a comprehensive power-system shape library. Its strongest duck-curve information comes from supplying realised delivery demand/solar. This makes the conditional experiment easier than an operational seven-day forecast in which levels and ramps must first be forecast.

## 8. Recommended feature additions

The next version should test explicit shape features in controlled ablations:

1. Renewable ramps: 30-minute, 1-hour, 3-hour and 6-hour changes in regional wind, solar and UIGF; cross-region sums, dispersion and ramp flags.
2. Residual-demand shape: change, acceleration, rolling minimum/maximum, distance from the daily trough, expected evening peak, and ramp to/from delivery.
3. Solar geometry: solar elevation, daylight flag, minutes from sunrise/sunset and daylight length at representative coordinates.
4. Seasonal interactions: month/meteorological season, hour × season, weekend/holiday indicators and training-only region-specific diurnal profiles.
5. Weather stress: cooling/heating degrees, temperature extremes, recent temperature history and corridor weather differences.
6. Network regime dynamics: time since setter/state change, trailing constrained fraction, limit/flow ramp and volatility, trailing directional minima and duration below threshold.

For origin `o` and delivery `v`, future-input ramps may use only values available in the declared forecast path up to `v`; historical-state ramps must end before `o` at the publication-aware cutoff. In the realised-input research track, future ramps remain realised and must be labelled accordingly. An operational track must derive them from archived issue-time forecast vintages.

Assess each addition on identical pairs by connector, target and horizon. For restrictions, compare event recall at a fixed false-alert burden and add episode warning time and missed MW-hours. March–August 2026 has already been inspected, so it can support exploratory paired comparisons but chosen changes require confirmation on a newly accumulated untouched period.

## 9. Reproducibility and interpretation boundaries

Models used LightGBM absolute-error regression with 180 trees, 23 leaves, learning rate 0.055, minimum child samples 120, column fraction 0.9, L2 regularisation 5 and seed 741. Training ended on 1 September 2025. Selection used September–November, residual calibration December–January, alert tuning February, and final evaluation March–August 2026.

Selected P50 adds the median calibration residual to the raw winner. P10/P90 use empirical residual quantiles within connector, target and lead band. Restriction probability comes from the same residual distribution rather than a dedicated classifier. The intervals are marginal rather than physically coherent multivariate paths.

The AEMO comparison used 2,876,052 matched original predispatch origin/delivery pairs over 0.5–39 hours. It is asymmetric because AEMO used forecast inputs while this model received realised fundamentals/weather. It cannot support a claim of operational superiority.

Reported dispatch limits depend on the solved NEM constraint system. Separate predicted limits are not guaranteed simultaneously feasible, and price-spread associations are not causal price impacts. The outputs support restriction awareness and regional-balance research; they do not replace NEMDE, security assessment or network engineering limits.
