## 7 SRA auction clearing prices, term premia, convergence, and execution slippage

Having established how physical flows and settlement rules generate SRA unit cashflows, this chapter tests what market participants actually paid for those entitlements across every public auction since October 2021. Joining all {{auction_tranches}} delivered auction tranches to their exact AEMO-settled quarterly payoffs answers four commercial questions: whether SRA units cleared at a systematic discount, whether that discount survives outside the 2022 energy crisis, how much of the apparent return is absorbed by multi-year credit-support carry, and how much clearing-price slippage a desk incurs when bidding for size.

### 7.1 Realised payoffs against clearing prices across 1,332 tranches

For any set of delivered tranches $\mathcal{T}$ with units sold $n_i$, the units-sold value-weighted realised-to-price ratio is:

$$
\rho(\mathcal{T}) = \frac{\sum_{i \in \mathcal{T}} n_i \, \text{payoff}_i}{\sum_{i \in \mathcal{T}} n_i \, \text{price}_i}.
$$

Because all twelve tranches of a given delivery quarter share one realised outcome, 95% confidence intervals are computed by quarter-cluster bootstrapping (2,000 replicates resampling complete delivery quarters rather than individual tranches).

Across all {{auction_tranches}} delivered tranches spanning October 2021 to June 2026, SRA buyers received {{auction_ratio}} times their purchase price (95% interval {{auction_ratio_lo}} to {{auction_ratio_hi}}), with realised payoffs exceeding clearing prices in {{auction_share_above}} of tranches and a mean undiscounted premium of {{auction_mean_premium}} per unit. Total public auction proceeds were {{proceeds_total}} against {{distributed_total}} distributed to unit holders, meaning consumers (via transmission network tuition offsets) captured {{proceeds_share}} of the residue value sold.

{{exhibit:n3}}

### 7.2 Separating structural risk premia from the 2022 crisis shock

A critical challenge to any historical auction-premium study spanning 2021–2026 is sample contamination from the 2022 Australian energy crisis, when tranches auctioned in 2020 and 2021 settled into unprecedented coal outages, global fuel spikes, and the June 2022 market suspension. Re-estimating the value-weighted ratio across four explicit sub-samples separates crisis windfalls from persistent market structure:

| Sample window | Quarters | Tranches | Value-weighted realised ÷ price | 95% quarter-cluster CI |
|---|---:|---:|---:|---|
| Full window (2021 Q4 to 2026 Q2) | 19 | {{auc_tr_full_19q}} | {{auc_ratio_full_19q}} | {{auc_lo_full_19q}}–{{auc_hi_full_19q}} |
| Excluding 2022 crisis (drops 2022 Q2 and Q3) | 17 | {{auc_tr_ex_2022_crisis}} | {{auc_ratio_ex_2022_crisis}} | {{auc_lo_ex_2022_crisis}}–{{auc_hi_ex_2022_crisis}} |
| Early window (2021 Q4 to 2023 Q4) | 9 | {{auc_tr_early_2021q4_2023q4}} | {{auc_ratio_early_2021q4_2023q4}} | {{auc_lo_early_2021q4_2023q4}}–{{auc_hi_early_2021q4_2023q4}} |
| Recent window (2024 Q1 to 2026 Q2) | 10 | {{auc_tr_recent_2024q1_2026q2}} | {{auc_ratio_recent_2024q1_2026q2}} | {{auc_lo_recent_2024q1_2026q2}}–{{auc_hi_recent_2024q1_2026q2}} |

Removing 2022 Q2 and 2022 Q3 lowers the aggregate realised-to-price ratio from {{auc_ratio_full_19q}} to {{auc_ratio_ex_2022_crisis}}, yet the 95% confidence interval ({{auc_lo_ex_2022_crisis}} to {{auc_hi_ex_2022_crisis}}) remains strictly above 1.0, and the recent ten-quarter post-2024 window stays virtually identical at {{auc_ratio_recent_2024q1_2026q2}} ({{auc_lo_recent_2024q1_2026q2}} to {{auc_hi_recent_2024q1_2026q2}}). The horizon gradient also survives cleanly outside the 2022 crisis, rising from {{auc_ex22_h12}} ({{auc_ex22_h12_lo}}–{{auc_ex22_h12_hi}}) one to two quarters ahead to {{auc_ex22_h912}} ({{auc_ex22_h912_lo}}–{{auc_ex22_h912_hi}}) nine to twelve quarters ahead.

| Direction | Full 19-quarter ratio | 95% CI (full) | Time to delivery | Full-window ratio | Ex-2022 ratio |
|---|---:|---|---|---:|---:|
| VICNSW | {{ratio_VICNSW}} | {{ratio_VICNSW_lo}}–{{ratio_VICNSW_hi}} | 1–2 quarters | {{ratio_h12}} | {{auc_ex22_h12}} |
| NSWVIC | {{ratio_NSWVIC}} | {{ratio_NSWVIC_lo}}–{{ratio_NSWVIC_hi}} | 3–4 quarters | {{ratio_h34}} | 1.18 |
| QLDNSW | {{ratio_QLDNSW}} | {{ratio_QLDNSW_lo}}–{{ratio_QLDNSW_hi}} | 5–8 quarters | {{ratio_h58}} | 1.35 |
| NSWQLD | {{ratio_NSWQLD}} | {{ratio_NSWQLD_lo}}–{{ratio_NSWQLD_hi}} | 9–12 quarters | {{ratio_h912}} | {{auc_ex22_h912}} |
| VICSA | {{ratio_VICSA}} | {{ratio_VICSA_lo}}–{{ratio_VICSA_hi}} | | | |
| SAVIC | {{ratio_SAVIC}} | {{ratio_SAVIC_lo}}–{{ratio_SAVIC_hi}} | | | |

Beneath the aggregate stability, directional pricing shifted meaningfully after 2023. On northward VNI (VICNSW), the realised-to-price ratio dropped from 1.97× in 2021 Q4–2023 Q4 to 1.02× (95% interval 0.80–1.25) across the ten quarters of 2024 Q1–2026 Q2 as bidders bid up near-term VNI units sharply; by contrast, QLDNSW remained strongly discounted at 1.65×, NSWVIC rose to 2.11×, and VICSA stayed at 1.42× in the post-2024 window. Treating the five-year aggregate ratio as a uniform corridor-blind alpha would therefore misprice northward VNI today.

{{exhibit:n4}}

### 7.3 Tranche convergence and auction-to-cash credit-support carry

Tracking clearing prices across Tranches 1 through 12 for identical delivery quarters isolates term-structure drift from ex-post weather surprises. Relative to the final Tranche 12 clearing price of the same delivery quarter, Tranche 1 units cleared at a median discount of {{drift_t1_vs_t12}} (and Tranche 4 at {{drift_t4_vs_t12}}), yielding a value-weighted realised-to-price ratio of {{drift_t1_ratio}} at Tranche 1 versus {{drift_t12_ratio}} at Tranche 12.

A realistic assessment of those returns must account for capital lockup. Measuring cashflow timing solely from the calendar payment date (shortly after delivery begins) to value-weighted weekly settlement receipts (assuming a 21-day settlement lag) produces a short cash duration of {{days_to_cash}} days, a median holding-period return of {{hpr_median}}, and a tranche loss rate of {{hpr_share_loss}}. Yet a participant buying Tranche 1 commits balance-sheet risk capacity and prudential credit support nearly three years before receiving cash. Measuring the full auction-to-cash exposure window and deducting illustrative annualised funding/credit-support carry rates tests whether the term discount merely compensates for capital lockup:

| Horizon to delivery | Median days (payment to cash) | Median days (auction to cash) | Value-weighted gross HPR | Carry drag at 8% p.a. | Net excess HPR at 8% p.a. | Net excess HPR at 12% p.a. |
|---|---:|---:|---:|---:|---:|---:|
| 1–2 quarters | {{carry_days_pay_h12}} | {{carry_days_auc_h12}} | {{carry_vwhpr_h12}} | {{carry_drag8_h12}} | {{carry_net8_h12}} | {{carry_net12_h12}} |
| 3–4 quarters | {{carry_days_pay_h34}} | {{carry_days_auc_h34}} | {{carry_vwhpr_h34}} | {{carry_drag8_h34}} | {{carry_net8_h34}} | {{carry_net12_h34}} |
| 5–8 quarters | {{carry_days_pay_h58}} | {{carry_days_auc_h58}} | {{carry_vwhpr_h58}} | {{carry_drag8_h58}} | {{carry_net8_h58}} | {{carry_net12_h58}} |
| 9–12 quarters | {{carry_days_pay_h912}} | {{carry_days_auc_h912}} | {{carry_vwhpr_h912}} | {{carry_drag8_h912}} | {{carry_net8_h912}} | {{carry_net12_h912}} |
| All tranches | {{carry_days_pay_all}} | {{carry_days_auc_all}} | {{carry_vwhpr_all}} | {{carry_drag8_all}} | {{carry_net8_all}} | {{carry_net12_all}} |

Even across a median {{carry_days_auc_h912}}-day exposure window on 9–12 quarter tranches, an 8% p.a. credit-support charge absorbs {{carry_drag8_h912}}, leaving {{carry_net8_h912}} in net value-weighted excess return ({{carry_net12_h912}} at 12% p.a.). Carry alone therefore explains only a fraction of the term discount; the balance reflects risk aversion to single-day tail concentration (Chapter 4), limited bidder participation, and forward topology uncertainty. These findings mirror the empirical transmission-right auction literature in New York [R11], US FTR auctions [R12–R14], and European long-term rights [R4].

{{exhibit:v3}}

Quarter-by-quarter outcomes nevertheless remain highly dispersed across corridors, with extended clusters of buyer losses whenever anticipated scarcity fails to materialise.

{{exhibit:n5}}

### 7.4 Auction microstructure, unsold capacity, and bid-stack slippage

Public anonymised bid stacks reveal a median bid-to-offer ratio of {{bid_to_offer}}, yet {{unsold_share}} of offered units went unsold across the window because low-priced bids sit below AEMO reserve thresholds or marginal clearing steps. For a trading desk seeking to execute commercial size, marginal clearing-price impact varies dramatically across corridors. Simulating an additional aggressive desk buy order of 25, 50, or 100 units against the latest public Tranche 12 aggregate demand curves quantifies execution depth directly:

| Latest Tranche 12 contract | +25 unit slippage ($ / %) | +50 unit slippage ($ / %) | +100 unit slippage ($ / %) |
|---|---:|---:|---:|
| VICNSW (250 offered, 125 sold) | {{slip_25_dol_VICNSW}} ({{slip_25_pct_VICNSW}}) | {{slip_50_dol_VICNSW}} ({{slip_50_pct_VICNSW}}) | {{slip_100_dol_VICNSW}} ({{slip_100_pct_VICNSW}}) |
| QLDNSW (175 offered, 100 sold) | {{slip_25_dol_QLDNSW}} ({{slip_25_pct_QLDNSW}}) | {{slip_50_dol_QLDNSW}} ({{slip_50_pct_QLDNSW}}) | {{slip_100_dol_QLDNSW}} ({{slip_100_pct_QLDNSW}}) |
| VICSA (120 offered, 77 sold) | {{slip_25_dol_VICSA}} ({{slip_25_pct_VICSA}}) | {{slip_50_dol_VICSA}} ({{slip_50_pct_VICSA}}) | {{slip_100_dol_VICSA}} ({{slip_100_pct_VICSA}}) |

Where significant tranche capacity went unsold (VICNSW and QLDNSW), moderate desk orders of 25 to 50 units clear with negligible immediate price impact against the observed stack. On tighter or smaller-offering corridors such as VICSA (and especially NSWQLD, where 75 units were offered and a 50-unit order pushes clearing prices up nearly 59%), execution slippage rapidly erodes apparent theoretical valuation edge and must enter portfolio sizing constraints explicitly.

{{exhibit:n26}}
