## 4 Empirical baseline, statistical fragility, CPT truncation, and diurnal regimes

An interregional valuation model is only as honest as the historical telemetry it rests upon. Short sample windows in the Australian National Electricity Market create a classic trap: two or three calm quarters make regional spreads look mean-reverting and Gaussian, while a single heatwave or coal-unit trip flips a corridor's quarterly sign overnight. Before decomposing physical loss and constraint mechanisms, we establish the full nineteen-quarter five-minute empirical baseline (`2021 Q4` to `2026 Q2`), audit statutory price flags, measure finite-sample fragility, evaluate the interaction between rising market price caps and the cumulative price threshold, and map exactly when during the 24-hour solar-and-ramp cycle SRA dollars are actually earned.

### 4.1 Nineteen Quarters of Five-Minute Telemetry and Price-Flag Audit

The core evidence panel spans {{complete_quarters}} complete delivery quarters from {{first_quarter}} through {{last_quarter}}, encompassing {{intervals}} five-minute dispatch intervals across all five NEM regions (`NSW1`, `QLD1`, `SA1`, `VIC1`, `TAS1`). Every interval in the nineteen complete quarters carries firm settlement status ({{not_firm_complete}} non-firm rows). To eliminate the ambiguity created by conflating administered pricing, market price caps, and interregional loss-factor scaling, every five-minute price record is audited using AEMO's explicit bit-mask specification [R2]:

- Administered Price Cap (`APC`) binding: {{apc_binding_rows}} region-intervals, concentrated primarily in the June 2022 eastern-states energy crisis.
- Market Price Cap (`MPC`) binding: {{mpc_binding_rows}} region-intervals where regional dispatch hit the statutory ceiling in effect for that financial year (`$15,100/MWh` in FY2022 rising in annual steps to `$20,300/MWh` in FY2026 and `$23,200/MWh` in FY2027 [S28]).
- Interregional loss-factor (`IRLF`) adjustment flags: {{irlf_rows}} region-intervals recording active interregional scaling under extreme price-cap or floor conditions.
- Market suspension pricing (June 2022): {{suspension_rows}} region-intervals. Sensitivity testing confirms that excluding versus retaining market-suspension pricing alters quarterly mean spreads by at most ${{suspension_max_change}}/MWh in `2022 Q2` and leaves all other eighteen quarters completely unaffected.

Across the nineteen complete quarters, the four canonical signed regional price spreads exhibit sharply distinct averages, dispersion, and range reversals:

| Canonical regional pair | 19-quarter mean spread ($/MWh) | Quarterly SD ($/MWh) | Minimum quarter ($/MWh) | Maximum quarter ($/MWh) | Structural directional bias |
|---|---:|---:|---:|---:|---|
| `NSW − VIC` | ${{mean_spread_nsw_vic}} | ${{sd_spread_nsw_vic}} | ${{min_spread_nsw_vic}} (`{{minq_spread_nsw_vic}}`) | ${{max_spread_nsw_vic}} (`{{maxq_spread_nsw_vic}}`) | Persistent NSW premium in all 19 quarters |
| `QLD − NSW` | ${{mean_spread_qld_nsw}} | ${{sd_spread_qld_nsw}} | ${{min_spread_qld_nsw}} (`{{minq_spread_qld_nsw}}`) | ${{max_spread_qld_nsw}} (`{{maxq_spread_qld_nsw}}`) | Structural regime flip: QLD dearer in 2022, NSW dearer in 2024–2026 |
| `SA − VIC` | ${{mean_spread_sa_vic}} | ${{sd_spread_sa_vic}} | ${{min_spread_sa_vic}} (`{{minq_spread_sa_vic}}`) | ${{max_spread_sa_vic}} (`{{maxq_spread_sa_vic}}`) | Persistent SA premium except flat `2025 Q4` |
| `VIC − TAS` | ${{mean_spread_vic_tas}} | ${{sd_spread_vic_tas}} | ${{min_spread_vic_tas}} (`{{minq_spread_vic_tas}}`) | ${{max_spread_vic_tas}} (`{{maxq_spread_vic_tas}}`) | Hydro-driven swings; TAS dearer on average in 2024–2026 |

The interactive Historical Explorer below allows direct inspection of every quarter's exact additive split into clipped energy below $300/MWh and scarcity excess above $300/MWh, the four joint exceedance states, single-region scarcity concentration, and the consolidated nineteen-quarter cross-link heatmap (defaulting to the flagship `VIC → NSW` corridor).

{{interactive:historicalExplorer}}

Two headline patterns stand out immediately inside the Explorer. First, **`NSW − VIC` is the only mainland pair that stayed strictly positive across all nineteen consecutive quarters** (floor `${{min_spread_nsw_vic}}/MWh` in `{{minq_spread_nsw_vic}}`, ceiling `${{max_spread_nsw_vic}}/MWh` in `{{maxq_spread_nsw_vic}}`), underpinned by chronic Victorian brown-coal and renewable surplus exporting into higher-cost New South Wales thermal marginal units. Second, **`QLD − NSW` inverted completely across the five-year sample**: Queensland traded sharply above New South Wales during `2021 Q4–2022 Q2` (peaking at `+${{max_spread_qld_nsw}}/MWh` in `{{maxq_spread_qld_nsw}}`), before surging Queensland rooftop and utility solar combined with New South Wales coal retirements (Liddell) and winter scarcity pushed New South Wales sharply above Queensland (`${{min_spread_qld_nsw}}/MWh` in `{{minq_spread_qld_nsw}}` and `−$39.80/MWh` in `2025 Q2`). Any static long-run mean model applied to `QLD − NSW` averages two opposite physical regimes into a meaningless near-zero number (`${{mean_spread_qld_nsw}}/MWh`).

### 4.2 Finite-Sample Fragility, Day-Level Concentration, and Tail Persistence

Because electricity prices exhibit multi-day serial correlation driven by weather fronts and generator outages, standard independent-interval confidence intervals severely understate estimation error on quarterly means. Moving-block bootstrap resampling using **seven-day contiguous blocks** (preserving synoptic weather and outage persistence) reveals just how noisy realised quarterly means truly are.

{{exhibit:n14}}

{{exhibit:n15}}

Across all seventy-six pair-quarters, the median 95% moving-block bootstrap confidence interval width on a realised quarterly spread is ${{boot_median_width}}/MWh (Exhibit 4.1). On high-scarcity quarters such as `QLD − NSW` in `2024 Q2` or `SA − VIC` in `2026 Q1`, uncertainty intervals stretch beyond `$80/MWh`. A leave-one-day-out fragility test sharpens the warning (Exhibit 4.2): removing a single calendar day flips the algebraic sign of the entire quarterly average spread in {{sign_flips}} of {{pair_quarters}} pair-quarters. In the sharpest example, `{{frag_pair}}` in `{{frag_quarter}}` recorded a realised quarterly spread of `${{frag_spread}}/MWh`, yet removing a single day drives the quarter down to `${{frag_without}}/MWh`. In the Regional Explorer above, `80%` to `100%` of quarterly `$300` cap payout regularly concentrates inside just five calendar days. Valuation models that evaluate point errors without modelling discrete multi-day scarcity clusters will mistake single-day luck for structural alpha.

{{exhibit:n16}}

Tail clustering operates not only within one region over consecutive hours, but across interconnected regions simultaneously. Computing empirical cross-regional extremograms at the $300/MWh threshold confirms strong lag-0 contemporaneous co-exceedance between electrically adjacent pairs (`NSW1` and `QLD1`, `VIC1` and `SA1`) alongside a pronounced 24-hour diurnal echo at lag +288 five-minute intervals (Exhibit 4.3, consistent with Han, Cribben, and Truck [S19]). Because multi-day heatwaves and low-wind doldrums sweep eastward across South Australia, Victoria, and New South Wales over 24 to 72 hours, Stage 2 scenario generators in Part IV must sample multi-day spatially coherent weather blocks rather than independent daily draws.

### 4.3 Statutory Regime Shifts: FY2027 Market Price Cap and Cumulative Price Threshold

Between FY2022 and FY2027, the AEMC Reliability Panel increased the NEM Market Price Cap from `$15,100/MWh` to {{mpc_target}}/MWh (`+53.6%`), while simultaneously raising the seven-day rolling Cumulative Price Threshold (`CPT`, summed over 2,016 five-minute intervals) from `$1,359,100` to {{cpt_target}} (`+63.8%`) and doubling the Administered Price Cap (`APC`) from `$300/MWh` to {{apc_fy27}}/MWh [S28]. Valuing FY2027+ contracts from 2021–2026 history requires adjusting historical at-cap intervals to the new statutory rules without introducing upward bias from unconstrained linear rescaling.

{{exhibit:n21}}

Testing both linear MPC rescaling and full sequential rolling seven-day CPT truncation across all nineteen historical quarters yields two nuanced empirical results (Exhibit 4.4):

1. **Material scarcity uplift under FY2027 MPC:** Rescaling historical at-cap dispatch intervals proportionally to the {{mpc_target}}/MWh FY2027 ceiling lifts realised quarterly scarcity spreads by up to ${{mpc_max_uplift}}/MWh (`QLD − NSW` in `2022 Q1`, rising from `$45.69/MWh` raw to `$54.75/MWh` rescaled), with `+4.73/MWh` uplift on `NSW − VIC` in `2024 Q4` (`$47.21` to `$51.94/MWh`) and `+4.03/MWh` in `2024 Q2`. Failing to normalise historical cap intervals biases trailing scarcity estimates systematically downward against FY2027+ contracts.
2. **Why zero additional historical CPT breaches trigger, and why forward simulation still needs an explicit CPT gate:** On the rescaled nineteen-quarter history, applying the FY2027 rolling 2,016-interval CPT of {{cpt_target}} triggers {{cpt_capped_nsw}} additional capped intervals in NSW, {{cpt_capped_qld}} in QLD, and {{cpt_capped_sa}} in SA (`{{cpt_max_trim}} $/MWh` max trim). The mechanical reason is subtle and essential: the one genuine multi-day crisis in the historical sample (June 2022) was *already* truncated in real time at the old `$300/MWh` APC once regions crossed the much lower FY2022 CPT (`$1,359,100`), so historical June 2022 prices contain `$300` administered rows rather than uncapped spikes. Outside June 2022, because the FY2027 CPT rose `63.8%` alongside the MPC, no other historical week accumulated enough at-cap intervals to cross {{cpt_target}}.

For forward simulation (Part IV), however, omitting the CPT gate remains a dangerous mistake. At {{mpc_target}}/MWh, a region breaches the {{cpt_target}} seven-day CPT after just 96 five-minute intervals at cap (`$2,225,900 / $23,200 = 95.9` intervals, or 8.0 cumulative hours within any rolling seven-day window). Once breached, prices drop from `$23,200/MWh` down to the {{apc_fy27}}/MWh APC for the remainder of the administered price period. Any Monte Carlo generator that draws heavy-tailed severity clusters without an explicit rolling 2,016-interval CPT circuit breaker will produce physically impossible $300 cap valuations on tail paths.

### 4.4 Diurnal Operating Regimes and Negative-Price Loss Inversion

Quarterly averages conceal *when* during the 24-hour dispatch cycle interregional cashflows actually accrue. Partitioning all `517,248` five-minute intervals into three operationally distinct Australian grid regimes (Solar Midday `09:00–15:00` NEM time, Evening Ramp `16:00–21:00`, and Overnight and Shoulder `22:00–08:00`) reveals that different SRA corridors are effectively bets on completely different parts of the daily load-and-solar curve.

{{exhibit:n22}}

| SRA direction | Solar Midday (`09:00–15:00`) residue share | Evening Ramp (`16:00–21:00`) residue share | Overnight & Shoulder (`22:00–08:00`) residue share | Dominant physical driver |
|---|---:|---:|---:|---|
| `VICNSW` | {{diur_midday_VICNSW}} | {{diur_evening_VICNSW}} | {{diur_overnight_VICNSW}} | Persistent overnight coal/wind export + evening thermal spread |
| `QLDNSW` | {{diur_midday_QLDNSW}} | {{diur_evening_QLDNSW}} | {{diur_overnight_QLDNSW}} | Midday QLD solar surplus exported south + winter evening NSW peaks |
| `VICSA` | {{diur_midday_VICSA}} | {{diur_evening_VICSA}} | {{diur_overnight_VICSA}} | Evening/overnight SA gas dependence when wind and solar drop |
| `NSWQLD` | {{diur_midday_NSWQLD}} | {{diur_evening_NSWQLD}} | {{diur_overnight_NSWQLD}} | Summer evening QLD air-conditioning ramps (57% of total pool) |
| `NSWVIC` | {{diur_midday_NSWVIC}} | {{diur_evening_NSWVIC}} | {{diur_overnight_NSWVIC}} | Midday solar export reversals and occasional daytime outages |
| `SAVIC` | {{diur_midday_SAVIC}} | {{diur_evening_SAVIC}} | {{diur_overnight_SAVIC}} | Midday SA solar saturation pushing negative-priced power east |

The diurnal profile carries immediate practical implications for hedging and fundamental forecasting (Exhibit 4.5). Over {{diur_overnight_VICNSW}} of `VICNSW` positive residue accrues overnight and in early shoulder hours (`22:00–08:00`), whereas {{diur_midday_SAVIC}} of `SAVIC` and {{diur_midday_NSWVIC}} of `NSWVIC` accrue strictly during midday solar hours (`09:00–15:00`), and {{diur_evening_NSWQLD}} of `NSWQLD` accrues during the five-hour evening ramp (`16:00–21:00`). Forecasting a single daily-average spread misses the structural divergence between midday solar-curtailment spreads and evening firming spreads.

A second physical mechanism makes midday solar intervals mathematically distinct in the NEM settlement formula: **negative-price loss-factor inversion**. Under the coupled-network pricing relation $P_{\text{to}} = P_{\text{from}} \cdot \text{MLF}$, the marginal loss wedge equals $P_{\text{from}}(\text{MLF} - 1)$. Whenever $P_{\text{from}} > 0$ and power flows north on VNI ($\text{MLF} > 1$), losses add a positive price wedge (`{{pos_loss_nsw_vic}}/MWh` mean across non-negative Victorian intervals). When Victorian rooftop and utility solar drive $P_{\text{VIC}} < 0$, however, multiplying a negative origin price by $(\text{MLF} - 1) > 0$ inverts the sign of the loss term (`{{neg_loss_nsw_vic}}/MWh` mean across negative Victorian intervals, flipping sign in 85.0% of negative-origin intervals). Even more strikingly, because Victorian negative prices occur precisely when Victorian surplus pushes hard against northbound VNI limits (`{{neg_share_nsw_vic}}` of all complete-quarter intervals, rising to `64.2%` of Spring Solar Midday intervals), the average `NSW − VIC` spread during negative Victorian intervals jumps to {{neg_spread_nsw_vic}}/MWh and generates {{neg_res_share_nsw_vic}} of total nineteen-quarter `VICNSW` settled residue. On `QLD − NSW`, negative origin intervals occur in {{neg_share_qld_nsw}} of intervals and generate {{neg_res_share_qld_nsw}} of residue (mean spread {{neg_spread_qld_nsw}}/MWh, loss term flipping from {{pos_loss_qld_nsw}} to {{neg_loss_qld_nsw}}/MWh). Any lognormal model or non-negative price transformation breaks on the exact midday intervals that generate a third of Victoria-to-New South Wales SRA revenue.
