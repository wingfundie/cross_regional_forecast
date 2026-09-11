# NEM Interconnector Forecast Lab — agreed build specification

## Objective and approved scope
Build and run a reproducible three-year conditional backtest and local interactive trading-desk dashboard for every NEM interconnector present in the data. Predict signed dispatch flow, average directional import/export limits, and tightest five-minute directional limits within each half-hour. Refresh forecast origins every 30 minutes; support leads of 30 minutes to seven days. Include P10/P50/P90 where estimable and restriction probabilities. A restriction is a **50% reduction** below a training-only seasonal directional reference. Missing restrictions matters more than false alerts.

Future realised regional demand, wind, solar and weather are explicitly approved inputs for the conditional experiment. Future prices, realised constraint results and interconnector flows are excluded from features. Prices are historical context, not a causal attribution or price forecast. Forecast-input/live operation is a later layer; this deliverable includes a user-input scenario runner.

## Execution plan
1. Audit NEMWEB monthly table archives and choose the latest recoverable 36 complete months. Record URLs, bytes, checksums, schemas, gaps and duplicate/intervention handling. Download only required public tables; retain five-minute originals and reusable columnar data.
2. Collect Open-Meteo weather at demand centres and renewable/corridor locations. Preserve native temporal resolution, record interpolation and geographical aggregation. Identify unit fuels with public NEMWEB metadata; keep utility and rooftop solar distinct and avoid net-demand double counting.
3. Build half-hour targets, regional drivers, known-at-origin lag features and network regime history. A model's information cutoff must be explicit. Future limit setters, future prices and other IC flows are never predictive inputs.
4. Use 24 months initial training, six months chronological validation and six untouched months of rolling-origin test evaluation. Partition by delivery time, embargo crossing target windows up to seven days, and fit all preprocessing, seasonal references, calibration and alert thresholds without test data. Explain seasonal coverage limitations of a six-month final test; use validation folds and seasonal slices as supporting evidence.
5. Compare persistence, same-week seasonal persistence, demand/renewable boosted trees, weather-enhanced trees and network-history-enhanced trees. Model all three primary targets and two tight-limit targets. Fit quantiles and event probabilities; select settings on validation data, then freeze before testing. Do not promise an ML or AEMO win. Audit predispatch availability and run matched AEMO comparisons where defensible; otherwise document concrete missing coverage.
6. Evaluate MAE, RMSE, quantile loss, 80% interval coverage/width, restriction precision/recall/F2 and false alarms by connector, direction, lead band, season and stressed periods. Use day-block uncertainty estimates where suitable. Preserve per-origin predictions and outcome counts, not just aggregate scores.
7. Deliver an interactive dark trading-desk dashboard: connector watchlist, half-hour forecast fan charts, actuals and baselines, 50% restriction thresholds/alerts, lead-band and model comparisons, driver ablations, calibration, five-minute inspection, historical regional price-spread context, data audit and methods. Include downloadable results and a validated seven-day scenario input template/runner.
8. Run the pipeline end to end, verify meaningful data/model/time-split invariants and dashboard callbacks, inspect the rendered layout and interactions, and leave the local dashboard running with reproducible launch instructions and a research/backtest report.

## Scientific and market conventions
- Use NEM market time (fixed UTC+10, no daylight saving); preserve interval-ending semantics.
- Positive direction comes from dated interconnector standing data. Do not assume the sign of reported IMPORTLIMIT without auditing raw values. Present import/export directional capacity magnitudes consistently, preserving signed raw fields and anomalous/forced-flow regimes.
- AEMO reported limits are post-dispatch quantities; neither their averages nor their tightest summaries represent simultaneous secure transfer capability. Do not mechanically clip flow to separately predicted limits.
- Retain and report intervention cases; choose the relevant physical dispatch run consistently and test duplicate handling.
- No fabricated pre-commissioning observations for new connectors. Show coverage and model eligibility. Treat EnergyConnect-related network changes as regime changes and label scenario extrapolation.
- Realised dispatched renewables can themselves reflect congestion. Report this endogeneity and compare with renewable availability where data supports it; conditional performance is not an operational accuracy claim.

## Research and UI references
- AEMO IC limits explanation, Appendix A: https://aemo.com.au/-/media/files/electricity/nem/market_notices_and_events/power_system_incident_reports/2024/final-report---loss-of-moorabool---sydenham-500-kv-lines-on-13-feb-2024.pdf
- AEMO constraint FAQ: https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq
- Capacity forecasting / NARX and persistence: https://d-nb.info/1204086990/34
- Congestion probability and boosted trees: https://www.frontiersin.org/journals/energy-research/articles/10.3389/fenrg.2024.1351306/full
- Rolling origin evaluation: https://otexts.com/fpp3/tscv.html
- NEMWEB historical tables: https://nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM/
- Open-Meteo reanalysis: https://open-meteo.com/en/docs/historical-weather-api
- UI inspiration: TradingView's chart-first dark workspace and Bloomberg Launchpad's compact linked monitors, adapted without branding or copied proprietary assets: https://www.tradingview.com/support/solutions/43000746975-tradingview-layouts-a-quick-guide/ ; https://professional.bloomberg.com/products/bloomberg-terminal/
- Local dashboard UI skill: C:/Users/HomePC/.codex/skills/dashboard-ui-template/SKILL.md

## Completion evidence
Data manifest and audit; dated split manifest; trained model metadata; frozen validation choices; test predictions and score tables for all eligible connectors/targets/leads; scenario example and successful inference; executed tests; successful local app and UI checks; final report with limitations and honest baseline comparisons.
