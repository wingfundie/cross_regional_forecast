## Chapter 4 · Long-Range 1-to-90-Day Forecasting Verdict Across Fifty Horizon Bands

Trading desks managing quarterly Settlement Residue Auction books and seasonal interstate swap positions routinely ask a tempting question: if short-term diurnal and NOS models add value at 1-to-7-day horizons, can feeding original-vintage Medium-Term PASA (MT PASA) regional availability and demand forecasts into ridge or gradient-boosted trees produce skilful interconnector limit and flow forecasts out to 30, 60, or 90 days?

To answer that question without hindsight contamination, the repository executed a strictly bounded long-range campaign (`qni_vni_longrange_v1`, summarised in the 5 October 2026 *Forward Forecasting Verdict*) using daily 08:00 NEM origins, strictly original-vintage MT PASA inputs, and five separate horizon bands (`1-7`, `8-14`, `15-30`, `31-60`, and `61-90` days) across all five targets (`export_tight`, `import_tight`, `export`, `import`, and `flow`) on both VNI and QNI, producing 50 horizon-band evaluations across 10 connector-by-target cells.

### 4.1 The predictability frontier: why error expands rapidly beyond two weeks

{{diagram:forecastHorizonFrontier}}

Plotting MAE trajectories across all 50 horizon bands on VNI and QNI illustrates exactly how quickly interconnector predictability erodes once initial-state memory and confirmed 7-day NOS bookings expire.

{{exhibit:c7}}

On VNI, export-tight MAE climbs from 304.6 MW in days 1-7 (calendar baseline) to 343.1 MW in days 31-60 and 396.2 MW in days 61-90, while import-tight MAE stays near 210 to 240 MW across intermediate horizons. On QNI, selection-stage ridge and boosting models trimmed raw MAE relative to simple calendar baselines on several bands (bringing QNI import-tight down near 240 MW vs 360 MW calendar), yet exhibited steep degradation relative to persistence on QNI export and wide block-bootstrap uncertainty across origins.

### 4.2 Complete ten-cell promotion verdict: 10 of 10 retained the baseline

Under the repository's strict promotion protocol, a complex challenger model earns promotion only if it beats the simple baseline on identical chronological out-of-sample rows with a statistically positive confidence interval, beats persistence cleanly, and passes interval calibration and prospective receipt-time confirmation. All ten cells were audited against those exact gates:

| Connector | Target | Selection-stage winner | Weighted skill vs calendar baseline (%) | Baseline CI strictly positive? | Weighted skill vs persistence (%) | Persistence CI strictly positive? | Official cell decision |
|---|---|---|---:|---|---:|---|---|
| VNI | `export_tight` | Calendar | 0.0% | No | +25.7% | Yes | **Retain baseline** |
| VNI | `import_tight` | Boosting | -1.3% | No | +29.3% | Yes | **Retain baseline** |
| VNI | `export` | Boosting | -4.2% | No | +29.3% | Yes | **Retain baseline** |
| VNI | `import` | Calendar | 0.0% | No | +22.9% | Yes | **Retain baseline** |
| VNI | `flow` | Boosting | +3.0% | No | +22.3% | No | **Retain baseline** |
| QNI | `export_tight` | Boosting | +17.8% | **Yes** | -42.7% | No | **Retain baseline** |
| QNI | `import_tight` | Ridge | +36.9% | No | +9.6% | No | **Retain baseline** |
| QNI | `export` | Boosting | +7.7% | No | -50.1% | No | **Retain baseline** |
| QNI | `import` | Ridge | +39.2% | No | +12.2% | No | **Retain baseline** |
| QNI | `flow` | Ridge | +6.5% | No | -26.3% | No | **Retain baseline** |

{{exhibit:c8}}

Look closely at why 10 of 10 cells retained the simple baseline despite apparent point-estimate wins on QNI:

1. **VNI challengers failed to beat the calendar baseline out of sample:** Even though VNI's simple calendar baseline outperformed naive persistence by +22.3% to +29.3% across all five targets (with individual band gains ranging from +6.3% to +34.5%), gradient boosting and ridge regression added zero or negative skill relative to the calendar baseline on four of five VNI targets (-4.2% on export, -1.3% on import-tight, 0.0% on export-tight and import, and an insignificant +3.0% on flow). Once seasonal diurnal profiles are captured, 15-to-90-day MT PASA thermal-availability aggregates contain too little spatial resolution to predict which specific 330 kV VNI line constraint will bind weeks later.
2. **QNI challengers failed dual-baseline consistency and CI significance:** On QNI, `export_tight` was the only cell out of ten where a challenger cleared a strictly positive 95% confidence interval versus the calendar baseline (+17.8%), yet on the exact same rows it lost heavily to naive persistence (-42.7% skill vs persistence, and -50.1% on `export`). Meanwhile, QNI `import_tight` (+36.9% vs calendar) and `import` (+39.2% vs calendar) posted promising point skill, yet failed statistical significance (`primary_improvement_ci_positive = False`) across the 56 test origins and showed weak persistence margins (+9.6% to +12.2%, with confidence intervals crossing zero).
3. **Calibration failed on two-thirds of the 50 horizon bands:** Across all 50 evaluated connector-target-band combinations, only 16 of 50 bands (32.0%) passed nominal interval calibration checks (for instance, VNI `export_tight` calibrated in bands 1-7 through 31-60 days with 83.9% to 90.7% empirical coverage at the 80% level, but failed at 61-90 days; VNI `import_tight` failed calibration immediately at 1-7 days with just 67.1% coverage).

### 4.3 Physical anatomy of the 14-day predictability cliff and the QNI persistence trap

Why does a gradient-boosted tree on QNI `export_tight` beat the seasonal calendar baseline by +17.8% with a statistically positive confidence interval while simultaneously losing by -42.7% to simple persistence on the exact same evaluation rows? That apparent paradox reveals a fundamental structural distinction between VNI and QNI physics across multi-week horizons.

On **VNI**, transfer limits are dominated by fast-cycling diurnal solar-voltage patterns and short, frequent transmission switching events across the Victoria–Snowy–Southern NSW mesh. Because VNI limits oscillate strongly between midday solar hours and evening peaks every single day, naive persistence (carrying forward a single origin snapshot for 30 to 60 days) suffers severe phase error, allowing a simple hour-of-day and month-of-year calendar baseline to beat persistence by +22.3% to +29.3%. Once that seasonal diurnal waveform is removed, however, remaining 15-to-90-day variance is driven by synoptic wind/cloud fronts and unscheduled line maintenance that MT PASA regional totals cannot foresee.

On **QNI**, by contrast, major export-limit depressions frequently persist for multi-week stretches during extended Northern NSW 330 kV line works (such as Liddell–Tamworth Line 84 or Armidale–Dumaresq Line 8C) and prolonged Queensland coal-unit maintenance blocks. When a major transmission derating lasts three weeks, a seasonal calendar average reverts immediately back toward the multi-year monthly mean and accumulates large systematic error. Persistence stays anchored inside the active outage state and therefore beats the calendar curve heavily across Days 1 through 30. The boosting challenger partially tracks the regime using MT PASA regional availability, beating the naive calendar baseline (+17.8%), yet still reverts too far toward historical training means relative to the live persistence anchor (-42.7%).

This structural diagnosis leads directly to a practical 15-to-90-day desk workflow that avoids both traps:
- **Do not average point ML predictions across Days 15 to 90:** Point regression forecasts compress tail risk toward the conditional mean and fail interval calibration on 34 of 50 horizon bands.
- **Anchor on calibrated seasonal distributions overlaid with confirmed NOS transmission calendars:** Start from the historical month-by-hour empirical distribution (which captures VNI's +22% to +29% diurnal skill with zero overfitting), then explicitly condition the active weeks on booked transmission outages using the calibrated NOS binding probabilities (`p_cal`) and N-1-1 overlap flags established in Flagship Edition B, discounting tentative 30-to-90-day bookings for the 31% withdrawal rate observed in NOS lifecycle logs.

> [!TAKEAWAY] Commercial Reality of 15-to-90-Day Forecasting
> At horizons beyond 14 days, unbooked transmission maintenance, booking withdrawals (31% in Flagship Edition B), synoptic weather fronts, and coal unit forced outages dominate interconnector transfer variance. Seasonal calendar baselines already capture 22% to 29% of persistence error on VNI without overfitting. Until measured-receipt prospective confirmation proves a multi-month feature set beats both seasonal baselines and persistence simultaneously, desks should anchor 15-to-90-day valuation on calibrated seasonal distributions plus confirmed NOS outage calendars rather than point ML limit forecasts.

Inspect all 50 long-range band evaluations interactively in the searchable ledger below.

{{interactive:longrangeDirectory}}

Before concluding the forecasting audit, one popular machine-learning hypothesis remains to be tested: even if global models struggle across regimes, can unsupervised regime clustering (splitting hours into distinct grid states and fitting local expert models per cluster) unlock hidden forecast skill? Chapter 5 evaluates the complete leakage-controlled clustering campaign.
