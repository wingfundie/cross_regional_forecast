## 9 Walk-forward benchmarks, option Greeks, and the valuation workbench

A trading desk should never adopt a complex structural valuation model until it demonstrates measurable out-of-sample skill against simpler, strictly causal benchmarks on identical auction dates. Chapters 7 and 8 established that SRA auctions clear at a persistent discount to realised cashflows and that unit hedging firmness varies sharply across links. This chapter puts simple forecasting rules, reduced-form option formulas, and relative-value spread arithmetic through a strict causal audit, correcting the look-ahead regime flaw identified in Version 2 and culminating in the worked 90-day NSW−VIC valuation example synced directly to the interactive Desk Workbench.

### 9.1 Strictly Causal Walk-Forward Evaluation Across 612 Tranches

To prevent any forward-looking leakage, every historical forecasting rule is evaluated under a strict as-of settlement cutoff: when forecasting the per-unit payoff of a tranche auctioned on date $\tau$, a candidate rule may access only quarters whose final delivery date finished at least 28 days prior to $\tau$ (reflecting AEMO's settlement publication lag). Requiring at least four settled prior quarters per direction restricts the scored walk-forward panel to {{wf3_n_market_clearing_price}} auction tranches spanning {{wf3_first_auction}} through {{wf3_last_auction}}, explicitly excluding the {{wf3_dropped}} earlier tranches from the full {{auction_tranches}}-tranche auction record that fell inside the four-quarter warm-up window.

Version 3 expands the benchmark suite beyond raw trailing averages by adding three economically motivated causal challengers:

1. Debiased clearing price (ex-ante): Multiplies the live auction clearing price by the strictly causal trailing value-weighted realised-to-clearing ratio observed on previously settled tranches in the same horizon band (clamped to `[0.7, 2.0]` to avoid small-sample outliers).
2. MPC-rescaled trailing 4 quarters: Scales the trailing four-quarter realised payoff upward by a 35% scarcity-weighted ratio of the delivery quarter's statutory Market Price Cap to the trailing four-quarter mean MPC.
3. Outage-adjusted Tranche 12 (ridge-shrunk): For the `{{wf3_n_outage_adjusted_t12}}` Tranche 12 contracts (`2024-12-16` to `2026-03-16`) where as-of planned transmission outage hours exist prior to bidding, adjusts the trailing mean using a ridge-shrunk linear slope on scheduled outage hours.

{{exhibit:n23}}

The out-of-sample verdict is unambiguous and sobering (Exhibit 9.1): **the raw auction clearing price beats every single statistical and mechanical challenger on Mean Absolute Error**, even though it carries a systematic downward risk-premium bias of {{wf3_bias_market_clearing_price}} per unit.

| Causal forecasting rule | Scored tranches ($n$) | Mean bias ($/unit) | MAE ($/unit) | MAE (% of realised mean) | MAE skill vs. clearing price |
|---|---:|---:|---:|---:|---:|
| **Auction clearing price (benchmark)** | **{{wf3_n_market_clearing_price}}** | **{{wf3_bias_market_clearing_price}}** | **{{wf3_mae_market_clearing_price}}** | **{{wf3_pct_market_clearing_price}}** | **0.0%** |
| Trailing 4 quarters | {{wf3_n_trailing_4q}} | {{wf3_bias_trailing_4q}} | {{wf3_mae_trailing_4q}} | {{wf3_pct_trailing_4q}} | −31.2% |
| Trailing 8 quarters | {{wf3_n_trailing_8q}} | {{wf3_bias_trailing_8q}} | {{wf3_mae_trailing_8q}} | {{wf3_pct_trailing_8q}} | −31.8% |
| Trailing 12 quarters | 612 | $666 | $10,132 | 62.9% | −33.6% |
| MPC-rescaled trailing 4 quarters | {{wf3_n_mpc_rescaled_trailing_4q}} | {{wf3_bias_mpc_rescaled_trailing_4q}} | {{wf3_mae_mpc_rescaled_trailing_4q}} | {{wf3_pct_mpc_rescaled_trailing_4q}} | −37.5% |
| Trailing same-season mean | 612 | $1,116 | $10,695 | 66.4% | −41.0% |
| Debiased clearing price (ex-ante) | {{wf3_n_debiased_clearing_price}} | {{wf3_bias_debiased_clearing_price}} | {{wf3_mae_debiased_clearing_price}} | {{wf3_pct_debiased_clearing_price}} | −45.0% |
| Prior settled quarter | 612 | $792 | $11,500 | 71.4% | −51.6% |
| *Matched T12 subset: Clearing price* | *{{wf3_n_market_clearing_price_matched_t12}}* | *{{wf3_bias_market_clearing_price_matched_t12}}* | *{{wf3_mae_market_clearing_price_matched_t12}}* | *{{wf3_pct_market_clearing_price_matched_t12}}* | *0.0% (subset)* |
| *Matched T12 subset: Outage-adjusted T12* | *{{wf3_n_outage_adjusted_t12}}* | *{{wf3_bias_outage_adjusted_t12}}* | *{{wf3_mae_outage_adjusted_t12}}* | *{{wf3_pct_outage_adjusted_t12}}* | *−134.7% (subset)* |

Why did naive ex-ante debiasing perform 45% worse than raw clearing prices ({{wf3_mae_debiased_clearing_price}} MAE versus {{wf3_mae_market_clearing_price}}), flipping bias from {{wf3_bias_market_clearing_price}} to +{{wf3_bias_debiased_clearing_price}}? The failure exposes the danger of backward-looking multiplier rules across regime shifts. Tranches settled during 2022 and 2023 realized massive payoff-to-price ratios (`1.79×` overall) because the June 2022 crisis surprised pre-crisis auctions. Multiplying 2024–2026 clearing prices by that trailing crisis ratio pushed forecasts far above realised payoffs precisely as market participants had already repriced the post-crisis forward curve downward (`1.35×` recent ratio, `1.02×` on `VICNSW`). Similarly, raw outage-hour scaling on Tranche 12 deteriorated sharply to {{wf3_mae_outage_adjusted_t12}} MAE versus {{wf3_mae_market_clearing_price_matched_t12}} for clearing prices on the exact same 36 rows because total planned outage hours lump benign overnight maintenance together with daytime binding limits.

### 9.2 Disaggregated Accuracy by Direction and Horizon

Pooling all six directions hides huge cross-corridor differences in forecastability. Disaggregating the 612 walk-forward tranches by direction and by horizon band shows exactly where the auction market is already sharp and where systematic valuation opportunities reside:

| Direction ($n=102$ each) | Mean realised ($/unit) | Clearing price MAE ($/unit, %) | Clearing price bias ($/unit) | Debiased price MAE ($/unit) | Trailing 4q MAE ($/unit) |
|---|---:|---:|---:|---:|---:|
| `VICNSW` | $20,342 | {{wfd_mkt_mae_VICNSW}} ({{wfd_mkt_pct_VICNSW}}) | {{wfd_mkt_bias_VICNSW}} | {{wfd_deb_mae_VICNSW}} | $11,091 |
| `QLDNSW` | $34,598 | {{wfd_mkt_mae_QLDNSW}} ({{wfd_mkt_pct_QLDNSW}}) | {{wfd_mkt_bias_QLDNSW}} | {{wfd_deb_mae_QLDNSW}} | $19,715 |
| `VICSA` | $23,854 | {{wfd_mkt_mae_VICSA}} ({{wfd_mkt_pct_VICSA}}) | {{wfd_mkt_bias_VICSA}} | {{wfd_deb_mae_VICSA}} | $12,907 |
| `NSWQLD` | $8,532 | {{wfd_mkt_mae_NSWQLD}} ({{wfd_mkt_pct_NSWQLD}}) | {{wfd_mkt_bias_NSWQLD}} | {{wfd_deb_mae_NSWQLD}} | $8,407 |
| `NSWVIC` | $4,494 | {{wfd_mkt_mae_NSWVIC}} ({{wfd_mkt_pct_NSWVIC}}) | {{wfd_mkt_bias_NSWVIC}} | {{wfd_deb_mae_NSWVIC}} | $3,383 |
| `SAVIC` | $4,825 | {{wfd_mkt_mae_SAVIC}} ({{wfd_mkt_pct_SAVIC}}) | {{wfd_mkt_bias_SAVIC}} | {{wfd_deb_mae_SAVIC}} | $4,218 |

Across horizons, clearing-price MAE rises modestly from `$7,140` (`43.9%` of mean) at 1–2 quarters to `$7,721` at 3–4 quarters and `$8,077` at 5–8 quarters before settling at `$7,153` on the 9–12 quarter band, whereas debiased clearing prices degrade monotonically from `$8,667` at 1–2 quarters to `$12,868` (`87.6%` of mean) at 9–12 quarters. On `VICNSW`, clearing prices achieve an impressive {{wfd_mkt_pct_VICNSW}} relative MAE ({{wfd_mkt_mae_VICNSW}}) with minimal bias ({{wfd_mkt_bias_VICNSW}}), proving that the auction market already embeds forward outage and seasonal information far better than backward-looking rules. By contrast, `QLDNSW` ({{wfd_mkt_bias_QLDNSW}} bias) and `VICSA` ({{wfd_mkt_bias_VICSA}} bias) retain large negative pricing biases driven by heavy unhedged scarcity tails, while `NSWVIC` is the sole corridor where naive debiasing marginally beat raw clearing prices ({{wfd_deb_mae_NSWVIC}} versus {{wfd_mkt_mae_NSWVIC}}).

{{exhibit:n24}}

Sensitivity analysis across fundamental valuation drivers explains *why* simple autoregressive averages lose to the auction market (Exhibit 9.2). Changes in conditional scarcity severity, directional flow firmness during binding constraints, and forward outage schedules move per-unit value by thousands of dollars per quarter, reflecting information that auction participants observe ex-ante from MT PASA, outage plans, and ASX futures curves, and that Part IV's Stage 2–3 structural model is designed to ingest explicitly.

### 9.3 Strictly Ex-Ante Bachelier Spread-Option Fix and Valuation Greeks

Standard textbook commodity desks frequently approximate an SRA unit as a strip of Bachelier (normal) spread options, multiplying expected positive directional flow by a normal call option on the regional price spread $\mathbb{E}[(P_B - P_A)^+]$, because normal models gracefully accommodate negative electricity prices where lognormal Margrabe formulas [R17] fail. Yet Version 2 demonstrated that even a regime-conditioned Bachelier model overstated realised per-unit payouts by {{opt_v2_peek_mult}} times. A critical audit of Version 2's benchmark script uncovered a subtle look-ahead flaw: while mean and volatility parameters were trained strictly on the prior four quarters, the test quarter's value was summed across the test quarter's *realised* flow-direction regimes rather than ex-ante regime probabilities.

Version 3 removes that look-ahead peek completely. For every test quarter from `2022 Q4` through `2026 Q2`, the ex-ante benchmark conditions strictly on calendar season and four-hour time-of-day blocks (quantities known with 100% certainty before the auction), weighting each flow-direction regime by its training-window empirical transition probability $P(\text{flow regime} \mid \text{season, 4-hour block})$.

{{exhibit:n25}}

Eliminating the look-ahead peek does not rescue the independent spread-option approximation (Exhibit 9.3). Across all 90 direction-quarters evaluated (`2022 Q4–2026 Q2`), the strictly ex-ante Bachelier benchmark overstates realised aggregate per-unit payouts by {{opt_v3_exante_mult}} times, slightly *more* than Version 2's {{opt_v2_peek_mult}} times. Three physical omissions create that massive 2.4× structural gap:

1. Ignoring within-regime flow-spread negative covariance: Multiplying average positive flow by average call payoff assumes flow holds steady when spreads widen sharply, missing the firmness collapse documented in Chapter 5.
2. Omitting quadratic marginal losses: Pricing raw spreads $(P_B - P_A)^+$ ignores the 7% to 25% loss wedge established in Chapter 2.
3. Omitting five-minute negative-residue netting and loop rules: A call option on the spread assumes zero loss from counter-price clamping or pass-through reallocation.

{{exhibit:v4}}

Even though a reduced-form Bachelier proxy cannot price absolute unit levels accurately, its partial derivatives, namely Vega (sensitivity to spread volatility/severity scaling) and arrival-rate sensitivity (sensitivity to spike frequency scaling), provide clean local risk Greeks across corridors (Exhibit 9.4). Evaluating `2026 Q2` ex-ante sensitivities across `0.5×` to `2.0×` multipliers exposes a sharp asymmetry between volatility and frequency risk:

| Direction (`2026 Q2` ex-ante proxy) | Baseline `1.0×` value ($/unit) | `2.0×` Spread volatility (Vega stress) | Volatility sensitivity (`1× → 2×`) | `2.0×` Spike frequency stress | Frequency sensitivity (`1× → 2×`) |
|---|---:|---:|---:|---:|---:|
| `VICNSW` | {{greek_base_VICNSW}} | {{greek_vol2x_VICNSW}} | +{{greek_vol_pct_VICNSW}} | {{greek_frq2x_VICNSW}} | +{{greek_frq_pct_VICNSW}} |
| `QLDNSW` | {{greek_base_QLDNSW}} | {{greek_vol2x_QLDNSW}} | +{{greek_vol_pct_QLDNSW}} | {{greek_frq2x_QLDNSW}} | +{{greek_frq_pct_QLDNSW}} |
| `VICSA` | {{greek_base_VICSA}} | {{greek_vol2x_VICSA}} | +{{greek_vol_pct_VICSA}} | {{greek_frq2x_VICSA}} | +{{greek_frq_pct_VICSA}} |

Doubling spread volatility raises the ex-ante proxy by +{{greek_vol_pct_VICNSW}} on `VICNSW`, +{{greek_vol_pct_VICSA}} on `VICSA`, and +{{greek_vol_pct_QLDNSW}} on `QLDNSW`, whereas doubling spike-regime frequency shifts value by only +{{greek_frq_pct_VICNSW}}, +{{greek_frq_pct_VICSA}}, and +{{greek_frq_pct_QLDNSW}} inside the Gaussian-regime proxy. Notice the operational warning inside that contrast: because Gaussian option formulas pack tail value into continuous variance ($\sigma$) rather than discrete jump arrivals ($\lambda$), they misattribute jump-frequency risk into continuous volatility risk. Proper tail Greeks in Part IV require separating Poisson/Hawkes arrival intensity ($\lambda$) from conditional tail severity ($s$) directly on five-minute simulation paths.

### 9.4 Worked Desk Valuation Example and Interactive Workbench

To bridge empirical evidence directly into daily desk execution, consider a 90-day (`2,160`-hour) `NSW − VIC` quarterly evaluation using matched timestamped ASX base futures, $300 cap futures, and an upcoming `VICNSW` SRA auction tranche. All inputs below match the default parameters pre-loaded in the interactive Workbench directly underneath this walkthrough:

- **Matched futures quotes (origin `VIC = A`, destination `NSW = B`):** Origin base future $F_{\text{VIC}} = \$76.00/\text{MWh}$, destination base future $F_{\text{NSW}} = \$110.00/\text{MWh}$, origin $300 cap future $C_{\text{VIC}} = \$9.00/\text{MWh}$, and destination $300 cap future $C_{\text{NSW}} = \$25.00/\text{MWh}$.
- **Step 1 (Market-implied spread decomposition):** Applying the exact identity from Chapter 1 yields a market total base spread of $\$110.00 - \$76.00 = \$34.00/\text{MWh}$. Splitting at the $300 strike gives market-implied clipped energy spreads of $(\$110 - \$25) - (\$76 - \$9) = \$85.00 - \$67.00 = \$18.00/\text{MWh}$, and a market-implied scarcity cap spread of $\$25.00 - \$9.00 = \$16.00/\text{MWh}$. Over 2,160 delivery hours, a 1 MW linear base spread represents $\$73{,}440$, of which $\$38{,}880$ is clipped energy and $\$34{,}560$ is scarcity excess.
- **Step 2 (Cap-implied scarcity hours sanity check):** Suppose the desk's physical model estimates conditional mean excess above $300/MWh in New South Wales at $s_{\text{NSW}} = \$2{,}500/\text{MWh}$ with zero cap risk-premium loading ($\rho = 0$). The market's $\$25.00/\text{MWh}$ NSW cap price then implies $H_{\text{NSW}} = (25 / 2{,}500) \times 2{,}160 = 21.6\text{ hours}$ above $300/MWh in the quarter (roughly 259 five-minute intervals). If the desk instead assumes a 20% cap risk premium ($\rho = 0.20$), physical implied hours drop to $18.0$ hours. Comparing implied scarcity hours against the historical frequency distribution in the Chapter 4 Explorer immediately flags whether destination caps are rich or cheap relative to thermal outage and weather risk.
- **Step 3 (Physical versus market relative value):** If the desk's physical model (Stage 2–3 distribution $\mathbb{P}$) projects a total `NSW − VIC` spread of $\$30.00/\text{MWh}$ against the $\$34.00/\text{MWh}$ market base spread, the physical-minus-market edge is −$4.00/MWh (market expensive by `$8,640` per MW-quarter), signalling a potential short base-spread trade only if the desk agrees with the market's scarcity versus energy split.
- **Step 4 (SRA unit margin net of fees, carry, and model reserve):** Now evaluate a `VICNSW` SRA tranche trading at $\$15{,}000/\text{unit}$ against a discounted physical expected unit payoff of $\$20{,}000/\text{unit}$ (already adjusted for post-November 2026 loop pass-through haircuts if applicable). Subtracting $\$200/\text{unit}$ in auction fees and prudential carry plus a $\$750/\text{unit}$ model and liquidity reserve leaves an expected net economic margin of $\$4{,}050/\text{unit}$ (`+27.0%` return on purchase price). Before executing, the desk checks bid-stack slippage from Chapter 7 (`0%` up to 100 units on `VICNSW`) and sizes paired NSW $300 caps from Chapter 8 (`1.8` SRA units plus `1.0` MW NSW cap per MW of spread exposure) so tail risk stays inside risk limits.

Adjust any quote, severity assumption, risk-premium loading, or SRA unit input below to stress-test the exact relative-value arithmetic live.

{{interactive:valuationLab}}
