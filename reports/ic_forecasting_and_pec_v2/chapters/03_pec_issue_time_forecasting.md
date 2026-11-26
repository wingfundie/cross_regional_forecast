## Chapter 3 · Issue-Time Forecasting Audit on Project EnergyConnect

EnergyConnect provides a rare natural laboratory for testing genuine issue-time interconnector limit forecasting: every Predispatch and Short-Term PASA (ST PASA) vintage was archived strictly as published, preserving exact issue times, anchor timestamps, and AEMO's own forecast limits alongside observed five-minute tight half-hour targets (`nsw_sa_tight` and `sa_nsw_tight`, defined strictly as the minimum across the six five-minute dispatch intervals). Across 48,336 Predispatch forecast rows and 17,808 ST PASA rows (1 October to 23 November 2026), five distinct models were evaluated on identical as-of rows: `Persistence` (holding the latest pre-issue tight limit), `Delivery-Period Baseline` (time-of-day historical benchmark), `AEMO Issued Forecast` (official Predispatch or ST PASA interconnector limit), `Regional Forecast` (statistical model using issued regional demand/VRE forecasts), and `Regional + Constraints` (adding forecast constraint RHS and binding indicators).

### 3.1 Predispatch and ST PASA accuracy across directions and lead bands

| Product & direction | Lead band | Best model (MAE MW) | Persistence MAE (MW) | Delivery-Period MAE (MW) | AEMO Issued MAE (MW) | Regional + Constraints MAE (MW) | Best skill vs Persistence (%) |
|---|---|---|---:|---:|---:|---:|---:|
| Predispatch · NSW to SA | Intraday | Persistence (100.9) | 100.9 | 117.9 | 140.9 | 179.4 | 0.0% |
| Predispatch · NSW to SA | 6-24h | Delivery-Period (127.5) | 144.8 | 127.5 | 181.8 | n/a | +11.9% |
| Predispatch · NSW to SA | Day 2-3 | Delivery-Period (122.7) | 134.0 | 122.7 | n/a | n/a | +8.4% |
| Predispatch · NSW to SA | Day 4-7 | Delivery-Period (129.7) | 141.5 | 129.7 | n/a | n/a | +8.3% |
| Predispatch · SA to NSW | Intraday | Delivery-Period (109.3) | 121.4 | 109.3 | 109.8 | 140.9 | +9.9% |
| Predispatch · SA to NSW | 6-24h | Delivery-Period (104.6) | 234.1 | 104.6 | 106.3 | n/a | +55.3% |
| ST PASA · NSW to SA | 6-24h | AEMO Issued (105.5) | 144.8 | 127.5 | 105.5 | n/a | +27.1% |
| ST PASA · NSW to SA | Day 2-3 | Delivery-Period (122.7) | 134.0 | 122.7 | 130.5 | 153.6 | +8.4% |
| ST PASA · NSW to SA | Day 4-7 | Delivery-Period (129.7) | 141.5 | 129.7 | 137.2 | 205.5 | +8.3% |
| ST PASA · SA to NSW | 6-24h | AEMO Issued (93.3) | 234.1 | 104.6 | 93.3 | n/a | +60.1% |
| ST PASA · SA to NSW | Day 2-3 | AEMO Issued (95.2) | 223.9 | 113.0 | 95.2 | 154.4 | +57.5% |
| ST PASA · SA to NSW | Day 4-7 | AEMO Issued (98.1) | 232.8 | 117.8 | 98.1 | 209.1 | +57.8% |

{{exhibit:c5}}

Three sharp, counter-intuitive lessons emerge directly from this issue-time audit:

1. **AEMO ST PASA delivers strong multi-day accuracy on SA to NSW reverse limits (+57.5% to +60.1% skill over persistence):** Because SA to NSW persistence suffers severe diurnal swings (MAE 223.9 to 234.1 MW across 6-24h through day 4-7 as daytime solar pushes reverse limits down and nighttime relieves them), AEMO's official ST PASA solver cuts MAE cleanly down to 93.3 to 98.1 MW across all multi-day bands, outperforming both Delivery-Period baselines (104.6 to 117.8 MW) and statistical challengers (154.4 to 209.1 MW). Even on NSW to SA at 6-24h, AEMO ST PASA leads all models at 105.5 MW (+27.1% vs persistence).
2. **Simple baselines beat statistical regressions during discrete commissioning step-changes:** Across every single Predispatch and ST PASA cell where `Regional Forecast` and `Regional + Constraints` were scored, both statistical models lost decisively to `Persistence`, `Delivery-Period Baseline`, and `AEMO Issued Forecast` (for example, 179.4 MW vs 100.9 MW on intraday NSW to SA, and 205.5 MW vs 129.7 MW on ST PASA day 4-7). That negative result is one of the most informative lessons in the entire repository: during an active 53-day commissioning programme where AEMO steps the corridor discretely across `0 MW`, `150 MW`, and `350 MW` testing regimes, complex regression weights fitted on last week's 150 MW regime systematically overfit and extrapolate poorly the morning AEMO switches to 350 MW or locks the line to 0 MW.
3. **Intraday Predispatch AEMO limits lag simple persistence on NSW to SA (140.9 MW vs 100.9 MW):** Why did intraday Predispatch AEMO limits lose to persistence on NSW to SA? Because during staged commissioning tests, intraday discretionary caps (`NS_150_DYN_TEST`, `NS_350_DYN_TEST`, `NRM_NSW1_SA1`, and forced negative voltage stability bounds `N^^N_NIL_LTWG`) often enter the live five-minute dispatch engine faster than Predispatch updates propagate across all 48 half-hours, giving latest-observed `own_anchor` persistence a temporary short-horizon edge.

### 3.2 Severe prediction-interval under-coverage during regime transitions

Checking empirical interval coverage against the nominal 80% target exposes an equally important risk-management warning.

{{exhibit:c6}}

Across Predispatch lead bands, empirical interval coverage sits far below 80% for every single model: `Delivery-Period Baseline` reaches just 44.8% to 57.2%, `Persistence` reaches 34.8% to 53.5%, and `Regional + Constraints` collapses to 15.0% to 45.9% at day 2-7 horizons under ST PASA. Whenever an interconnector undergoes structural commissioning step-changes (jumping 150 MW or 200 MW overnight upon test-stage sign-off), rolling residual radii estimated on pre-transition history systematically understate real uncertainty.

### 3.3 Anatomy of a commissioning step-change miss and live desk playbook

To understand why `Regional + Constraints` lost by 78.5 MW on intraday NSW to SA (179.4 MW vs 100.9 MW) and by 111.0 MW on day 4-7 SA to NSW (209.1 MW vs 98.1 MW), trace what happens inside a chronological walk-forward regression across a commissioning step date.

During Weeks 1 through 4 of the observation window, EnergyConnect sat primarily inside the `150 MW commissioning` envelope (`NS_150_DYN_TEST` and `SN_150_DYN_TEST`), interspersed with `NS_ZERO` outage blocks. Any regression trained strictly on pre-origin history observes a bounded target capped at +150 MW and assigns non-zero slopes to issued SA solar, NSW demand, and forecast constraint RHS variables to explain intraday variation between -100 MW and +150 MW. The morning AEMO approves the `350 MW testing` step, two things break simultaneously:
- **Linear and tree extrapolation fails across unseen regime caps:** Tree models (`GBDT`) cannot extrapolate above the maximum target observed in training (+150 MW), capping their predictions at 150 MW on days when realised tight limits reach 350 MW (an instant 200 MW bias). Linear/ridge models extrapolate the RHS slope linearly, often overshooting wildly into +450 MW or -400 MW when a new `350_DYN_TEST` equation replaces `150_DYN_TEST`.
- **AEMO's ST PASA solver natively knows the scheduled test step:** Unlike a statistical model that has to infer structural regime changes backward from realised lags, AEMO's ST PASA engine incorporates the scheduled commissioning constraint set (`SN_350_DYN_TEST`, `N>>6CGH_060_051`, and booked `6F`/`6C` outage constraints) directly into its forward optimisation. That structural information advantage explains why ST PASA holds 93.3 to 98.1 MW MAE across Days 1 through 7 on SA to NSW while every statistical challenger deteriorates beyond 150 MW.

Until EnergyConnect completes Stage 2 commissioning and accumulates at least one full four-season steady-state dispatch year, trading desks should route short-horizon reference bounds strictly according to the empirical hierarchy below:

| Direction | Forecast horizon | Recommended desk reference | Audited MAE (MW) | Why it leads during commissioning |
|---|---|---|---|---|
| NSW to SA | Intraday (0-6h) | Latest-anchor Persistence | 100.9 | Captures live `NS_ZERO`, `NRM`, and `LTWG` shifts before Predispatch catches up |
| NSW to SA | 6-24h | AEMO ST PASA Issued | 105.5 | Incorporates scheduled commissioning test envelopes (+27.1% vs persistence) |
| NSW to SA | Day 2-7 | Delivery-Period Baseline (+ AEMO ST PASA cross-check) | 122.7 - 129.7 | Avoids regression extrapolation while tracking diurnal solar-voltage rhythm |
| SA to NSW | Intraday (0-6h) | Delivery-Period / AEMO Predispatch blend | 109.3 - 109.8 | Nearly identical accuracy (+9.9% vs persistence) with stable diurnal tracking |
| SA to NSW | 6h to Day 7 | AEMO ST PASA Issued | 93.3 - 98.1 | Dominates all baselines and regressions by +57.5% to +60.1% vs persistence |

> [!TAKEAWAY] Operational Rule for Forecasting Commissioning Interconnectors
> Never deploy regression-based statistical limit models trained on short commissioning histories onto a newly energised link while AEMO is stepping discretionary test ceilings. Use AEMO ST PASA for multi-day SA to NSW guidance (93 to 98 MW MAE), Delivery-Period plus latest-anchor Persistence for short-term NSW to SA reference bounds, and treat probabilistic interval widths as strictly uncalibrated until EnergyConnect completes Stage 2 commissioning and enters steady-state system-normal operation.

Use the searchable scorecard below to inspect every product, direction, lead band, and model across all 54 audited EnergyConnect forecast cells.

{{interactive:pecForecastDirectory}}

Part II now broadens the forecasting verdict from EnergyConnect's 53-day commissioning window back to the mature VNI and QNI spines, evaluating whether long-range 1-to-90-day MT PASA models and regime-clustering architectures clear genuine out-of-sample promotion gates.
