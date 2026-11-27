# Forward constraint RHS from regional demand forecasts

## Finding

Regional demand can drive a local-load estimate and a conditional network RHS. Current public predispatch files also contain local demand forecasts for two named inputs. For a custom regional forecast, these offer an electrical starting point. Population is a fallback where a matching load history or issued local forecast is missing.

## Day-ahead results

Mean absolute error in MW across 12 half-hours. The three previous-afternoon forecasts were generated about 16:02 NEM time and the delivery half-hours ended between 10:30 and 12:00 the next day. Leads were 18.5–20 hours to interval end.

| method                              |   Sydney-area load |   Terranora load |   Network RHS |
|:------------------------------------|-------------------:|-----------------:|--------------:|
| Population share                    |              411.6 |            —   |         —   |
| Fixed historical share              |              380.1 |             20.7 |          52.9 |
| Clock and day-type share            |              333.4 |             22.7 |          56.0 |
| Clock and day-type level            |              438.3 |             20.5 |          27.4 |
| Latest public reading               |             1858.4 |             21.3 |          15.5 |
| Latest reading plus regional change |              426.1 |             18.5 |          51.2 |
| Issued AEMO                         |              295.1 |              8.9 |          36.5 |

## Short-horizon results

Mean absolute error in MW on the same deliveries. The 12 P5MIN runs were generated 34–60 minutes before the native five-minute delivery endpoints (rounded). Each group of six predictions came from one coherent run. Scores below use half-hour averages.

| method                              |   Sydney-area load |   Terranora load |   Network RHS |
|:------------------------------------|-------------------:|-----------------:|--------------:|
| Population share                    |              164.1 |            —   |         —   |
| Fixed historical share              |              122.4 |             19.9 |          33.7 |
| Clock and day-type share            |              139.0 |             21.2 |          36.2 |
| Clock and day-type level            |              438.3 |             20.5 |          27.4 |
| Latest public reading               |              183.6 |              4.8 |          11.1 |
| Latest reading plus regional change |              144.6 |              4.6 |          10.1 |
| Issued AEMO                         |              154.6 |              5.1 |          27.9 |

## How the comparisons were made

- Training used the seven prior mornings of 9–15 February 2026. Evaluation used 19, 20 and 22 February. Four complete six-interval blocks were scored on each morning, in fixed NEM time. The 19th revisits a previously identified congestion day. This is an exploratory targeted sample.
- NSW and Queensland forecast inputs are the contemporary AEMO run's TOTALDEMAND. The fixed share is the ratio of total historical local MW to historical NSW MW over the calibration mornings. The matched share and matched level use the same delivery half-hour and weekday/weekend class, with five weekday or two weekend training dates. The fixed share is morning-specific. Additional calibration seasons and hours would be needed for whole-day use.
- The population benchmark uses June 2024 ABS Significant Urban Areas: Sydney 5,143,256, Newcastle–Maitland 534,033, and Wollongong 318,258. The denominator is the NSW and ACT resident population (8,953,169), an approximate geography for NSW1. The fraction is 66.97%. This proxy deliberately tests a geographic approximation to the AEMO three-city signal. No Western Sydney-only electrical boundary was assumed. [ABS source released March 2025](https://www.abs.gov.au/statistics/people/population/regional-population/2023-24)
- Actuals are averages of the six five-minute dispatch RHS values or decoded monitor observations. For the 19th, both load readings and the network RHS were independently cross-checked against the earlier NEMDE replay. The 20th and 22nd use the published monitor signal as reference. These are effective quantities in the market solution.
- The previous-reading alternatives use an original public file created before the forecast was issued. The change method adds the training share times the forecast change in NSW demand to the earlier measured local load. Its network variant anchors to the previously observed RHS, applies the nonlinear formula change, holds interconnector flow at its observed value and treats forecast regional MW changes as approximate R-term changes. It uses no future local reading, flow or LHS.
- For the full N::Q_NIL_KC RHS under regional-only inputs, the fixed-share and matched-share methods use the estimated Terranora load, the average signed initial flow from corresponding training intervals, and forecast NSW and Queensland TOTALDEMAND as approximations for their constraint R terms. Forecasts of scheduled load and network topology were not supplied. Expected flow, the definition of regional demand and local-load error all contribute to full RHS error. The matched-level and previous-reading benchmarks use earlier observed RHS values directly. The issued AEMO comparator uses the same original run as the regional inputs.
- Each source file has a creation stamp and archived file time. Both precede the delivery interval. The original recipient's download time is unknown. Three February mornings cannot establish year-round accuracy, binding precision or a prediction interval. Half-hour average error can hide a five-minute binding event.

## How to drive a calculator

1. Match the dispatch or predispatch version, scope and typed input. In the verified predispatch monitors, `DATASNAP_DFS_NSYD.RHS − 10000` gives the effective entered `N_SYDNEY` value and `DATASNAP_TE_967_1.RHS − 10000` gives `N_TERRANORA`. Preserve the run, delivery interval and version. Each formula has a fallback default. Use the published constraint RHS itself as the benchmark for the unmodified equation. [AEMO predispatch files](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/pre-dispatch) · [Verified program terms](monitor_definitions.csv)
2. Where there is no issued local series, estimate a historical electrical load share by delivery period, weekday/weekend and season. Keep a simpler fixed share as the benchmark. Near dispatch, test the last local reading plus a forecast regional change against persistence. Negative local net flow is possible: Terranora averaged below zero in seven of the twelve evaluated half-hours.
3. When using your own regional forecast with an AEMO base case, try local scenario = AEMO local forecast + historical local response × (your regional forecast − AEMO regional forecast). Fit the response to historical *changes* at matched hours and backtest it. This proposed scenario adjustment was not scored with a private forecast. Use a common regional demand definition and forecast vintage.
4. For a new Western Sydney footprint, use mapped customer connections or population as starting weights for the residential component. Add commercial profiles, explicit large sites and embedded generation to model net draw. Use mapped feeder/substation load to calibrate. Match electrical boundaries before aggregating and check for overlapping meters. A regional forecast already net of rooftop PV requires care to avoid subtracting the same solar generation twice. [Endeavour planning data](https://dapr.endeavourenergy.com.au/) · [CER postcode solar data](https://cer.gov.au/markets/reports-and-data/small-scale-installation-postcode-data)
5. For a missing switch or outage state, evaluate separate state-specific RHS values. For a missing continuous flow or rating, use a historical range conditional on comparable grid conditions. Evaluate the complete equation for each coherent scenario, including nonlinear terms. At longer horizons use held-out forecast residuals by lead and delivery period for calibrated ranges. A binding assessment also requires an invoked equation and a forecast of signed LHS headroom. The results above score RHS and local load only.

[Issued forecast rows](issued_forecasts.csv) · [Dispatch observations](observations.csv) · [Forecast-by-forecast comparisons](predictions.csv) · [Bias, MAE and maximum errors](metrics.csv) · [Source hashes](sources.json) · [Prior reading hashes](origin_sources.json) · [Reproduction script](study.py)
