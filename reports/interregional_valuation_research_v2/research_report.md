# Valuing interregional spreads and settlement residue units in the NEM

## Research purpose and the answer for the desk

Prepared for the IC Flow Forecasting project as version 2 of the 18 September 2026 research. It responds in full to the review in `reports/interregional_valuation_research_20260918/review.md`.

- **Market:** Australian National Electricity Market.
- **Units:** prices in AUD per MWh unless stated; settlement residue auction (SRA) prices and payoffs in AUD per unit per quarter.
- **Time:** fixed NEM time (UTC+10), interval-ending five-minute timestamps.
- **Evidence window:** 517,248 five-minute intervals, 2021 Q4 to 2026 Q2, which is 19 complete quarters.

Every number in this document is generated from the evidence files in `evidence/` by the build. None is typed by hand.

Version 1 designed a valuation. Version 2 carries it out on history, and it answers the desk's question directly.

**SRA units have been cheap relative to what they paid.** Across 1,332 auction tranches whose delivery quarter has settled, holders received 1.51 times the clearing price, weighted by units sold. The 95% interval is 1.28–1.81, from a cluster bootstrap over delivery quarters. Realised payoff exceeded the price in 63% of tranches. The discount grows with time to delivery:

| Sold ahead of delivery | Realised ÷ price | 95% interval |
|---|---:|---|
| 1–2 quarters | 1.28 | 1.07–1.50 |
| 9–12 quarters | 1.85 | 1.51–2.34 |

Auction proceeds were \$1,366.5m against \$2,068.1m distributed to the holders of the units sold. Consumers, through their transmission networks, therefore received 66% of the value they sold.

**The auction price is still the best available forecast of the payoff.** Scored at every auction date with only information available then, the clearing price had a mean absolute error of \$7,586 per unit. The best rule built from settled history had \$9,954. The clearing price was biased low by −\$3,130. Auction prices therefore contain real information and a systematic discount; the discount is a premium, not ignorance. It is consistent with the transmission-right literature for New York [R11], US FTR auctions [R12–R14] and European long-term rights [R4]. Part of it may be the market pricing regime change, which Chapter 12 addresses.

**An SRA unit is not a futures spread, and the difference depends on direction.** Against a 1 MW flat futures-style spread position, over 256 full weeks:

| Unit | Min-variance units per MW | Variance of 1 MW spread removed | MW per unit (regression, $1/n^{*}$) | MW-equivalent, ten highest-spread weeks |
|---|---:|---:|---:|---:|
| VICNSW | 2.5 | 19% | 0.41 | 0.15 |
| VICSA | 2.1 | 59% | 0.47 | 0.29 |
| QLDNSW | 1.6 | 52% | 0.63 | 0.66 |

The hedge weakens in exactly the weeks it is needed.

**The loop rule changes who is paid.** Applying the AEMC net-trade rule to settled history, holding dispatch fixed:

- VICNSW's payout pool changes by -24%.
- SAVIC's changes by -58%.
- The new NSW–SA and SA–NSW categories receive \$315.8m.
- 46% of intervals have Victoria as a pass-through region.

Historical per-unit values for the VIC-connected units cannot be carried into quarters from November 2026 without adjustment.

**Futures are the missing leg.** The public AER futures series is not observed in this build: the AER website refuses automated retrieval. The futures premium and futures-scaled valuation chapters are built and run as soon as the chart exports are placed in `data/external/aer_futures/`. The capped-energy and scarcity market decomposition of Chapter 3 still needs $300 cap quotes, which AER data do not include.

The recommendation of version 1 stands. Value spreads and SRA units on a joint scenario model with a separate contract-settlement layer. Keep a physical distribution distinct from a market-calibrated one. Version 2 adds the empirical anchor that the design lacked: a reconciled settlement ledger, an auction-by-auction premium history and direction-specific hedge ratios.

## 1 The questions the model must answer

For each region pair, direction, delivery quarter and valuation date, the model should answer six questions:

1. What is the expected time-weighted regional price difference, and its distribution?
2. How much comes from the capped energy component and from the excess above $300?
3. How often does only one region spike, how long do episodes last, and how severe are they?
4. What flows and settlement allocations occur in those same episodes?
5. What assumptions about scarcity, dependence and transmission availability would reconcile model values with market prices?
6. Which instrument best expresses or hedges the exposure after transaction costs, margin requirements and downside risk?

Use three separate meanings of capacity. **Generation adequacy** concerns available supply relative to demand. **Transfer capability** concerns the feasible network movement of power. **Scarcity value** is the high-price premium paid in energy prices and captured by a cap contract. An SRA is an entitlement to allocated residue; it is not ownership of physical transfer capacity. A $300 exceedance is a useful financial definition, but does not establish a physical shortage or a particular bidding mechanism. Prices below $300 can still contain congestion rents or scarcity-related opportunity costs.

The first implementation should cover QNI and VNI in both directions, but the VNI scenario engine must include South Australia and EnergyConnect. A two-region VNI model cannot represent the forthcoming three-region loop settlement allocation. Add Heywood, Murraylink and Basslink through effective-dated physical and contractual mappings. Do not infer settlement treatment solely from historical interconnector identifiers.

## 2 Instruments and the object being valued

Let $A$ be the origin region and $B$ the destination. The signed spot spread is $S_t = P_{B,t} - P_{A,t}$; a positive spread means the destination is dearer. A long spread position is long the destination regional future and short the origin regional future, with matched hours and MW.

With interval length $\Delta t$ (one twelfth of an hour) and quarter length $H=\sum_t \Delta t$, the settlement quantities are:

$$
\bar P_r=\frac{1}{H}\sum_t \Delta t\,P_{r,t},\qquad
\bar C_r=\frac{1}{H}\sum_t \Delta t\,\max(P_{r,t}-K,0),\qquad K=300 .
$$

A flat $m$ MW long spread bought at forward spread $F_B-F_A$ has terminal profit, before funding and costs:

$$
\Pi^{\text{fut}} = m\,H\left[(\bar P_B-\bar P_A)-(F_B-F_A)\right].
$$

A pre-loop SRA unit on direction $A\to B$ with unit proportion $\theta$ pays:

$$
\Pi^{\text{SRA}} = \theta\sum_{t\in Q}\max\!\left(R^{A\to B}_t,0\right) - \text{price} - \text{fees},
$$

where $R^{A\to B}_t$ is the settled inter-regional residue of the directional interconnector (Chapter 6). The first payoff is linear in a time-weighted spread. The second is a sum of positive parts of a flow-weighted, loss-adjusted spread.

### 2.1 Instrument notes carried from version 1

Let A be the origin region and B the destination. Define the signed spot spread as P_B minus P_A. A positive spread means the destination is more expensive. A long spread position means long the destination regional future and short the origin regional future, with matched delivery hours and MW exposure.

| Instrument | Economic exposure | Natural reporting unit |
|---|---|---|
| Regional base future | Quarterly arithmetic mean of regional spot price | AUD per MWh |
| Matched interregional futures legs | Difference between two regional quarterly means | AUD per MWh and AUD per MW-quarter |
| Regional $300 cap future | Average positive excess of spot price over $300 | AUD per MWh |
| Difference of regional caps | Difference between regional scarcity-excess payouts | AUD per MWh |
| Base spread less cap spread | Difference between prices clipped above at $300 | AUD per MWh |
| Directional SRA unit | Contractual fraction of distributable directional residue | AUD per unit |

ASX's June 2025 fact sheet specifies one MW base exposure and five-minute averaging for relevant contracts from October 2021. Quarterly hours vary with calendar length: 2,160, 2,184 or 2,208. The cap settlement calculation averages the positive excess above $300 over all base intervals. Contract rules and rounding must be implemented as specified for the delivery product. [S01]

ASX's published interregional spread convention deserves special attention: its 2014 launch notice states that buying a displayed spread buys the second, dominant leg and sells the first. Therefore the screen label can be misleading if read as ordinary subtraction. Map an executable order into explicit long and short regional legs; confirm the current broker and exchange convention before implementation. [S02]

A time-weighted quarterly future differs from a load-weighted customer exposure and from a flow-weighted residue. Keep all three quantities separate. A retailer's exposure may require multiplying regional prices by stochastic load, which introduces additional price-volume dependence. It cannot be hedged precisely by a flat one-MW spread merely because average prices match.

For a flat m-MW long spread, terminal economic profit before funding and costs is m times H times the difference between realised quarterly spread and entry spread. Futures are margined through time, so this terminal identity does not describe the path of liquidity requirements. An SRA unit instead requires its own purchase, payment, fee and distribution cashflow schedule.

## 3 The exact energy, scarcity, loss and congestion decomposition

### 3.1 Energy and scarcity

For each regional price define

$$
E_{r,t}=\min(P_{r,t},K),\qquad C_{r,t}=\max(P_{r,t}-K,0),\qquad P_{r,t}=E_{r,t}+C_{r,t}.
$$

The spread then splits exactly:

$$
S_t=\underbrace{(E_{B,t}-E_{A,t})}_{\text{capped energy}}+\underbrace{(C_{B,t}-C_{A,t})}_{\text{scarcity excess}} .
$$

The same identity holds for quarterly means because the averaging operator is linear. Negative prices stay in the energy term, and at exactly $300 the excess is zero. The first $300 of a spike stays in energy. This is not the same as averaging only the sub-$300 intervals, which would change the sample whenever spike frequency changes.

The market analogue uses base futures $F_r$ and $300 cap futures $G_r$ on matched quarters and timestamps:

$$
F_B-F_A=\underbrace{(F_B-G_B)-(F_A-G_A)}_{\text{market capped-energy spread}}+\underbrace{(G_B-G_A)}_{\text{market scarcity spread}} .
$$

### 3.2 Four joint price states

Let $z_t\in\{\text{neither},\text{destination only},\text{origin only},\text{both}\}$ classify each interval by which regions exceed $K$. State contributions use all quarter hours as the denominator, so they sum to the quarterly mean:

$$
\bar S=\sum_{z}\frac{1}{H}\sum_t\Delta t\,S_t\,\mathbf 1\{z_t=z\}=\sum_z \Pr(z)\,\mathbb E[S\mid z].
$$

### 3.3 Loss and congestion (new in version 2)

In any interval where the interconnector does not bind, AEMO's dispatch sets the importing region's price at the exporting region's price times the interconnector's marginal loss factor $\lambda_t$ (the `MARGINALLOSS` field). Define the coupled reference price $P^{*}_t=\lambda_t P_{\text{from},t}$. The spread then splits exactly into a loss part and a congestion part:

$$
P_{\text{to},t}-P_{\text{from},t}=\underbrace{(P^{*}_t-P_{\text{from},t})}_{\text{loss part}}+\underbrace{(P_{\text{to},t}-P^{*}_t)}_{\text{congestion part}} .
$$

Applying the $K$ operator to each piece gives the $2\times2$ decomposition used in Exhibit N8:

$$
\text{energy loss}=\min(P^{*},K)-\min(P_{\text{from}},K),\qquad
\text{energy congestion}=\min(P_{\text{to}},K)-\min(P^{*},K),
$$

The scarcity pieces are the remainders. All four sum to the spread.

The loss part matters for relative value. A futures spread carries it in full. In a coupled interval with quadratic losses $L=kF^2$, the settlement residue earns only about $P\,L$, roughly half of $F\,(P^{*}-P_{\text{from}})$. Chapter 10 measures it.

## 4 The evidence base, 2021 Q4 to 2026 Q2

Version 1 used three event datasets covering two years (seven complete quarters). The repository already held more. Version 2 rebuilds the evidence from the project's AEMO MMS dispatch tables, back-filled to October 2021 (the start of five-minute settlement) and covering all five regions and all six interconnectors. The resulting panel has 517,248 intervals with no missing prices or flows and no conflicting price versions.

Every interval in a complete quarter has `PRICE_STATUS = FIRM`; there are 0 non-firm rows there. The ported version 1 script reproduces the version 1 CSVs bit-for-bit on the version 1 window. That is a regression test in `nemic.valuation.baseline`.

Price flags are now decoded using AEMO's data model [R2]. Over the window there are:

- 1,883 regional rows with the administered price cap or floor binding (APCFLAG bit 1);
- 1,589 with the market price cap or floor binding (bit 4);
- 5,201 with inter-regional loss factor price scaling (bit 16);
- 13,524 with a non-zero market-suspension flag, including the June 2022 suspension.

Version 1 described its flagged rows as "administered-price flags". They were cap-binding and price-scaling rows. Excluding suspension-flag intervals changes any pair's quarterly spread by at most \$5.59/MWh.

### 4.1 Nineteen quarters of spreads

Exhibits 1–8 below now default to the full window, with a control to return to the version 1 window. Exhibit N13 shows all pairs and quarters, including VIC − TAS for the Basslink units that exist from July 2026.

| Pair (destination − origin) | Mean of quarters | Standard deviation | Lowest | Highest |
|---|---:|---:|---|---|
| NSW − VIC | 39.01 | 20.50 | 12.92 (2025Q3) | 97.75 (2024Q4) |
| QLD − NSW | -3.37 | 28.79 | -72.53 (2024Q2) | 62.42 (2022Q1) |
| SA − VIC | 20.19 | 17.30 | -0.08 (2025Q4) | 53.60 (2024Q3) |
| VIC − TAS | -14.04 | 20.76 | -52.21 (2025Q1) | 24.56 (2023Q2) |

![Figure 1 Quarterly spread decomposition, 2021 Q4 to 2026 Q2](figures/quarterly_spreads.png)

### 4.2 How reliable is one quarter?

A realised quarter is one draw of weather, outages and bidding. For each complete quarter, a moving-block bootstrap resamples 7-day blocks of days with 2,000 replicates. The median width of the 95% interval for a quarter's mean spread is \$26.89/MWh (Exhibit N14).

Removing the single most influential day reverses the sign of the quarterly spread in 3 of 76 pair-quarters (Exhibit N15). The most extreme case is SA − VIC in 2025Q4: \$-0.08/MWh with every day, \$-1.14/MWh without its largest day. Historical quarter means are therefore weak guides to a single future quarter. Valuation must be distributional.

## 5 SRA settlement mechanics and the 2026 transition

### Start with a settlement function

Define an effective-dated function S that maps interval prices, relevant flows, losses, topology, allocation rules, unit entitlements and fees into participant cashflows. An SRA value is the expected discounted cashflow produced by S, adjusted for the required compensation for risk and financing. The model must price the contract actually purchased rather than a convenient physical proxy.

For an elementary directional transfer, raw residue has the form received energy times destination price minus exported energy times origin price. In a lossless illustration this becomes transferred MWh times the regional price difference. Actual AEMO residue incorporates the applicable loss and allocation methodology; it is not safely reconstructed from a single MWFLOW column and a price difference. Historical negative residues were recovered through the relevant network arrangements rather than simply charged to SRA holders as a signed spread obligation. [S03]

The 7 August 2026 SRA Rules specify units, proportional entitlements, distribution instalments, fees and reconciliation. Their unit definition and payment provisions include nonnegative distributions and a minimum SRDA distribution mechanism. Implement the exact clauses, including the $10-per-allocated-unit minimum where applicable, rather than applying a generic positive-part operation to a quarterly sum. Twelve auction tranches do not make one unit a claim on only one-twelfth of delivery-quarter hours. [S04]

Unit counts are financial allocation parameters, not a guarantee of transfer. A 2028 Q2 unit-category notice, for example, lists different maximum counts for NSWQLD, QLDNSW, NSWVIC and VICNSW, and 500 in each Basslink direction. Notices can be revised. Preserve the published proportional entitlement, maximum units, quarter and notice version; do not use the number sold in one auction as the denominator for a unit's share. [S05]

### EnergyConnect changes the mapping from physical flow to payout

The September 2025 AEMC final determination adopts a net-trade approach for the NSW-SA-VIC loop. The loop's loss-adjusted residue is pooled; allocation then depends on regional net trade and price differences. Positive and negative legs are netted through the prescribed calculation. Thus physical use of VNI does not by itself establish the amount distributed to VICNSW units. [S06]

In AEMO's May 2026 stakeholder reference paper, the intended operational dates are 1 October 2026 for loop dispatch representation and 1 November 2026 for the new settlement calculations. The paper distinguishes those dates explicitly. It also provides worked allocation and secondary-netting examples, including cases where some directional units receive no payout despite physical flow elsewhere in the loop. Treat the October transition as a distinct settlement regime and verify final implementation notices. [S07]

The implementation pattern should be:

1. Calculate raw, loss-adjusted amounts for all relevant loop arms for each settlement interval.
2. Calculate the net loop amount. Route negative-loop treatment and special cases through the applicable rules.
3. Derive regional net export/import quantities and the eligible notional trade directions.
4. Calculate notional trade values, loss reconciliation and secondary netting using the exact rule version.
5. Apply unit entitlements, fees, timing and reconciliation to the allocated results.

AEMO opened a consultation on the merged residue allocation, distribution and recovery methodology on 16 September 2026, with submissions due 29 September. As at this report date it is a draft consultation, not a final implemented procedure. It states that interconnectors outside the loop retain the existing methodology. The settlement engine therefore needs a rule-version registry with effective dates, rather than one universal equation. [S08]

AEMO's current EnergyConnect FAQ says negative residue management is assessed at whole-loop level from the October operational transition. This changes possible dispatch outcomes as well as financial allocation. Do not copy historical individual-link clamping patterns into a loop scenario without adjustment. [S09]

### Basslink and new categories

AEMO's April 2026 final consultation report adds VICTAS and TASVIC categories in preparation for Basslink's regulated conversion from July 2026 and changes the auction fee method. Its June auction report contains Basslink prices. Consequently, older descriptions that categorically exclude Basslink from SRAs are unsuitable for prospective valuation. Treat the conversion as a data and contract regime break, with registration and settlement mapping checked at the relevant dates. [S10, S11]

### Decomposing an SRA into energy and scarcity

For a fixed-flow, linear raw-residue calculation, replace each price by E plus C and allocate the two contributions algebraically. Once flooring, netting and loop allocation apply, the contract function can be nonlinear. Two separately calculated positive payouts will generally not sum to the actual payout.

Use one of two clearly labelled views. **Historical state attribution** assigns each actual interval's allocated payout to its observed price state; it sums to the total and requires no counterfactual. **Fixed-flow price decomposition** calculates S using the observed flows and clipped prices, then defines the tail increment as S at actual prices minus S at clipped prices. This also sums exactly, but the tail increment can be negative and is order-dependent. It is an accounting counterfactual, not an estimate of what dispatch would have been without scarcity.

For an economic scarcity counterfactual, rerun dispatch with the relevant scarcity or availability mechanism altered, then rerun settlement. This changes both flows and prices. If several mechanisms interact, use paired scenarios and an explicitly defined Shapley allocation over a small set of mechanisms, retaining a reconciliation residual. Do not call the fixed-flow result causal.

## 6 Realised SRA payoffs: the settlement ledger

### 6.1 From flow × spread to settled residue

For each physical asset $a$ with flow $F_{a,t}$ (positive from → to), losses $L_{a,t}$ and from-region loss share $s_a$ (AEMO `FROMREGIONLOSSSHARE`), the interval residue is:

$$
r_{a,t}=\frac{\Delta t}{1\,\text{h}}\Big[P_{\text{to},t}\big(F_{a,t}-(1-s_a)L_{a,t}\big)-P_{\text{from},t}\big(F_{a,t}+s_aL_{a,t}\big)\Big].
$$

A directional interconnector pools its regulated assets: VNI; QNI with Terranora; Heywood with Murraylink [R1]. Direction follows the sign of net flow. Before the loop rule, holders receive the positive part in each interval, and negative residue is recovered from the importing region's transmission network (NER 3.6.5(a)(4)) [R1]:

$$
R^{A\to B}_t=\sum_{a}r_{a,t}\,\mathbf 1\Big\{\sum_a F_{a,t}>0\Big\},\qquad
\text{payoff per unit}=\theta_Q\sum_{t\in Q}\max(R^{A\to B}_t,0).
$$

Here $\theta_Q$ is the unit proportion for the delivery quarter, from AEMO's `AUCTION_IC_ALLOCATIONS` table (for example, one VICNSW unit is 1/1,500 of the pool). For 56 early quarter-directions the table predates the download window, so the published maximum units are used.

### 6.2 Reconciliation to AEMO settlement

AEMO publishes settled residue per interconnector, region and interval (`SETIRSURPLUS`). The residue sits in the exporting region's row. Its flow and loss fields are metered interval energy in MWh, not dispatch targets.

Computed from metered flows with dated loss shares, the engine reproduces the settled positive residue to:

- 0.03% on VNI northbound;
- -0.09% on QNI northbound (QLD→NSW);
- 2.9% on Heywood VIC→SA.

It is 42% away on QNI southbound (NSW→QLD), where counter-price and small reversed metered flows dominate. For realised payoffs the report therefore uses AEMO's settled residue directly. The computed engine is kept for sensitivities and for the loop counterfactual.

The version 1 proxy was lossless, positive-only, single-link and dispatch-based. Relative to settled payoffs it overstates:

| Direction | Lossless overstatement | Dispatch-flow difference | Metered-flow difference |
|---|---:|---:|---:|
| VICNSW | 10% | -5.4% | 0.0% |
| QLDNSW | 7% | -2.8% | -1.5% |
| VICSA | 14% | 0.5% | 2.9% |
| NSWQLD | 25% | 1.5% | 6.1% |

### 6.3 What units paid

| Unit | Mean per quarter | Median | Lowest | Highest | Positive residue, all quarters | Negative residue recovered from TNSPs |
|---|---:|---:|---:|---:|---:|---:|
| VICNSW | \$25,642 | \$21,897 | \$10,623 | \$60,577 | \$730.9m | −\$11.9m |
| NSWVIC | \$3,787 | \$1,788 | \$228 | \$15,078 | \$93.5m | −\$169.8m |
| QLDNSW | \$28,222 | \$23,915 | \$1,949 | \$85,873 | \$643.5m | −\$30.2m |
| NSWQLD | \$12,201 | \$10,915 | \$803 | \$43,129 | \$127.5m | −\$3.6m |
| VICSA | \$22,418 | \$18,757 | \$7,852 | \$64,479 | \$374.8m | −\$23.9m |
| SAVIC | \$6,263 | \$5,255 | \$782 | \$15,957 | \$91.6m | −\$11.9m |

Basslink was a market network service provider until July 2026, so it has no SRA settlement history. Its historical spread and flow evidence is in Chapters 4 and 13.

## 7 Auction prices against realised payoffs

AEMO's public auction tables (`RESIDUE_PUBLIC_DATA`, `RESIDUE_CONTRACTS`, `AUCTION_TRANCHE`, `AUCTION_CALENDAR`) give every tranche's clearing price, units offered and sold, auction date and payment date. Each tranche was joined to the settled payoff of its delivery quarter, giving 1,332 delivered tranches.

The value-weighted ratio for a set of tranches $\mathcal T$ is:

$$
\rho(\mathcal T)=\frac{\sum_{i\in\mathcal T} n_i\,\text{payoff}_i}{\sum_{i\in\mathcal T} n_i\,\text{price}_i},
$$

where $n_i$ is units sold. Confidence intervals resample delivery quarters rather than tranches, because every tranche of a quarter shares one realised outcome.

| Direction | Realised ÷ price | 95% interval |
|---|---:|---|
| VICNSW | 1.42 | 1.10–1.84 |
| NSWVIC | 1.57 | 0.94–2.37 |
| QLDNSW | 1.51 | 1.09–1.98 |
| NSWQLD | 1.68 | 1.10–2.51 |
| VICSA | 1.81 | 1.26–2.50 |
| SAVIC | 1.16 | 0.85–1.50 |

| Time to delivery | Realised ÷ price | 95% interval |
|---|---:|---|
| 1–2 quarters | 1.28 | 1.07–1.50 |
| 3–4 quarters | 1.32 | 1.09–1.61 |
| 5–8 quarters | 1.52 | 1.25–1.88 |
| 9–12 quarters | 1.85 | 1.51–2.34 |

Four explanations compete, and the evidence can partly separate them:

1. **Compensation for risk and capital.** Units are paid for up front and pay out over a quarter with extreme concentration (Chapter 4.2). Bidders are few, and the bid-to-offer ratio has a median of 5.8. The horizon gradient fits a term premium.
2. **Regime and topology expectations.** Price declines for far tranches could reflect expected transmission build and the loop rule, which sold tranches could not observe ex post. The walk-forward test in Chapter 14 shows a systematic low bias even at short horizons. Expectations are unlikely to explain all of it.
3. **Proxy error.** Payoffs here are AEMO-settled, not modelled. Fees in the allocation table are zero for most quarters. This explanation is weak.
4. **Sample.** The window includes the 2022 energy crisis. Per-direction intervals are wide and sometimes include 1 (NSWVIC, SAVIC). The aggregate and the horizon gradient remain significant.

## 8 SRA units against futures spreads

### 8.1 Hedge effectiveness

The desk comparison is between a unit's payoff $U_w$ and the P&L of a 1 MW flat spread $S_w=\sum_{t\in w}\Delta t\,(P_{B,t}-P_{A,t})$, week by week. The minimum-variance number of units per MW of spread and its variance reduction are:

$$
n^{*}=\frac{\operatorname{Cov}(S_w,U_w)}{\operatorname{Var}(U_w)},\qquad
1-\frac{\operatorname{Var}(S_w-n^{*}U_w)}{\operatorname{Var}(S_w)}=\operatorname{Corr}(S_w,U_w)^2 .
$$

The stress MW-equivalent is $\sum_{w\in\text{top}}U_w\big/\sum_{w\in\text{top}}S_w$ over the ten weeks with the largest spread P&L.

| Unit | $n^{*}$ units per MW | Variance removed | Stress MW-equivalent |
|---|---:|---:|---:|
| VICNSW | 2.5 | 19% | 0.15 |
| QLDNSW | 1.6 | 52% | 0.66 |
| VICSA | 2.1 | 59% | 0.29 |
| NSWQLD | 3.3 | 39% | 0.26 |
| NSWVIC | 3.5 | 11% | 0.33 |
| SAVIC | 3.1 | 6% | 0.30 |

The mechanism is visible in the flows. When NSW is above $300, mean northward VNI flow is 364 MW, against 391 MW otherwise: the interconnector does not deliver more when it matters. On QNI, northward flow rises from 315 MW to 439 MW when NSW is scarce, and QLDNSW units hedge accordingly better.

Exhibit N12 turns this into a cost–risk frontier. A desk short 1 MW of spread buys units at each quarter's clearing price. The 95% conditional value at risk (CVaR) of the weekly loss $\ell$ is minimised over the number of units:

$$
\operatorname{CVaR}_{0.95}(\ell)=\min_{c}\Big\{c+\frac{1}{0.05}\,\mathbb E\big[(\ell-c)^{+}\big]\Big\}.
$$

This is the Rockafellar–Uryasev form. It is evaluated on a grid of unit holdings because there is only one instrument.

### 8.2 Futures premia (AER public data)

The AER series is not observed in this build (Exhibits N6–N7). When supplied, the ex-post premium for region $r$ and quarter $Q$ is:

$$
\pi^{\text{fut}}_{r,Q}=F_{r,Q}(\tau)-\bar P_{r,Q}
$$

This uses the last price $F_{r,Q}(\tau)$ observed before delivery. Spread premia are computed on matched pairs.

Published evidence finds positive, seasonal and cross-correlated premia in NEM base futures [R7], and significant risk premia in Nordic area-price spread contracts [R9, R10]. The SRA discount in Chapter 7 should be compared with those premia, per MW-equivalent, before concluding that one instrument is cheap against the other.

## 9 Why expected flow alone cannot determine value

The identity is:

$$
\mathbb E[F^{+}S^{+}]=\mathbb E[F^{+}]\,\mathbb E[S^{+}]+\operatorname{Cov}(F^{+},S^{+}).
$$

Version 1 computed the benchmark with a flow already gated by $\mathbf 1\{S>0\}$. That shared indicator adds a mechanical positive term:

$$
\operatorname{Cov}\big(F\mathbf 1\{S>0\},S^{+}\big)=\operatorname{Cov}(F^{+},S^{+})+\mathbb E[F^{+}]\,\mathbb E[S^{+}]\,\frac{1-\Pr(S>0)}{\Pr(S>0)}\ \ \text{(for independent $F$ and $S$).}
$$

On the version 1 window, VNI northbound's reported covariance of 883 $/h falls to 239 $/h against the ungated benchmark. Conditional on a positive spread it is -4,172 $/h.

Version 2 reports rank dependence as well. For VNI northbound on the full window, the conditional Spearman correlation is 0.28 while the conditional covariance is -3,454 $/h. Flow and spread move together in ordinary intervals and apart in the extreme ones. That is precisely the firmness failure measured in Chapter 8.

### 9.1 Mechanism notes carried from version 1

The useful identity is E[flow times spread] = E[flow] times E[spread] plus Cov(flow, spread). Conditioning on direction, allocation gates and market regime adds further dependence. Quarter-average net flow can also hide large movement in both directions.

Three states illustrate the economics. With spare transfer capability, arbitrage tends to reduce price separation. With a binding import constraint and a tight importing region, high flows and large spreads may coexist. With an interconnector outage or severe restriction, regional separation can become extreme while the transferable volume collapses. The third state can be attractive for a regional spread position and poor for a physical-flow-linked residue entitlement.

In a lossless two-region model, increasing transfer capability initially lets more cheap generation displace expensive local generation. It may reduce the price spread, reduce scarcity probability, change flow, or all three. The effect on total residue need not be monotone: more MWh can be offset by a smaller spread. Evaluate an entire capacity-response curve rather than assume that a 10% capacity increase means 10% more SRA value.

Reported dispatch import and export limits are themselves functions of restrictive equations and the solved dispatch. Other generators and interconnectors appear in those equations. Treating each reported limit as an independent physical capacity can produce an impossible multi-region state. Preserve constraint coefficients, direction, effective versions and forced-flow cases. The existing project documentation already identifies this interpretation issue. [S12, L02]

Useful valuation sensitivities are a 100 MW change in an identified constraint RHS, one additional day of a named outage, a change in deliverable battery energy, or a renewable-output shock. Each sensitivity should state whether dispatch was reoptimised, bids held fixed, topology altered, or only a statistical conditional distribution changed. These are different experiments.

## 10 Loss-driven and congestion-driven spread

Over the full window, the average spread splits into:

| Pair | Loss part | Congestion part | Intervals coupled at the loss factor | Largest loss share in a quarter |
|---|---:|---:|---:|---:|
| NSW − VIC | 3.88 | 35.13 | 49% | 29% |
| QLD − NSW | -2.53 | -0.84 | 65% | 65% |
| SA − VIC | 2.81 | 17.38 | 61% | 92% |

The loss part is small on average but can dominate quiet quarters. It is also structural: it scales with flow (Exhibit N9) and with the price level. Basslink's prices almost never sit at its loss factor because, as a market network service provider (MNSP), it was dispatched on its own offers. VIC − TAS is therefore reported but not decomposed.

For valuation, a futures spread holds the whole loss part. An SRA holder earns the loss surplus $P\,L$ in coupled intervals, which is roughly half of it, plus the full congestion rent $F\,(P_{\text{to}}-P^{*})$ when separated.

## 11 Counter-price flows, negative residue management, constraints and outage plans

### 11.1 Counter-price residue

Negative settled residue totalled −\$255.4m across all directions. 91% of it arose while the interconnector was forced: a negative export limit or positive import limit pushed flow toward the cheaper region.

NSW→VIC alone carried −\$171.0m:

- 99% of it under forced southward flow;
- 48% while NSW was above $300;
- negative-residue management (NRM) was active in 7,497 intervals (flags from `NEGATIVE_RESIDUE`, available from August 2024).

Pre-loop, these amounts are recovered from the Victorian network and never reach unit holders. Under the loop rule, negative net loop residue is netted before payment, and NRM clamps only when the net loop residue is negative [R5]. Forced counter-price flow in NSW scarcity therefore becomes a direct risk to VIC-side units.

### 11.2 Which constraints separate the regions

The congestion part of each spread is attributed to the constraint AEMO reports as setting the binding interconnector limit. It is classified by AEMO's naming convention: `>>` thermal, `^^` voltage stability, `::` transient stability, and `NIL` for system-normal equations.

For NSW − VIC, the average congestion contribution splits into:

- transient stability, \$13.67/MWh;
- thermal, \$10.50/MWh;
- voltage stability, \$9.67/MWh.

By network state it is \$16.21/MWh for system-normal equations against \$17.49/MWh for outage and other equations. This naming heuristic is stated as such; the constraint-coefficient work in the NOS campaign is the rigorous companion.

### 11.3 Were outage plans informative before the auction?

For each delivery quarter from 2023 Q1, the analysis counts constraint-set hours already submitted to AEMO before the quarter's tranche-12 notification date, using the NOS campaign's outage-to-set mapping. The Spearman correlations with the realised share of separated intervals, over 15 quarters, are:

| Pair | Spearman correlation |
|---|---:|
| NSW − VIC | 0.35 |
| QLD − NSW | 0.38 |
| SA − VIC | 0.60 |
| VIC − TAS | -0.54 |

Positive correlations mean known outages were an information source available at the auction. With only 15 quarters this is suggestive, not proof.

## 12 The loop rule applied to history

The AEMC's final rule (ERC0386, 25 September 2025) settles the NSW–SA–VIC loop on net trade [R19]. For a net-positive loop interval:

1. The net loop residue is the sum of the arm allocations.
2. Net regional exports $x_r$ determine which arms carry net trade $q_k$, from net exporters to net importers.
3. The residue is then distributed in two steps:

$$
a_k=q_k\,(P_{\text{imp}(k)}-P_{\text{exp}(k)}),\qquad
\tilde a_k=R^{\text{loop}}\frac{a_k}{\sum_j a_j},\qquad
\text{payout}_k=R^{\text{loop}}\frac{\max(\tilde a_k,0)}{\sum_j\max(\tilde a_j,0)} .
$$

If the net loop residue is not positive, units receive nothing and it is recovered from networks by regional demand. The implementation passes the determination's Figure 3.1 and Appendix B Example 4 as unit tests.

Holding settled allocations and flows fixed from October 2021 to June 2026 gives a rule-only counterfactual:

| Unit category | Existing rules | Net-trade rule | Change |
|---|---:|---:|---:|
| VICNSW | \$730.9m | \$556.0m | -24% |
| NSWVIC | \$93.5m | \$59.6m | -36% |
| VICSA | \$374.8m | \$299.7m | -20% |
| SAVIC | \$91.7m | \$38.7m | -58% |
| NSWSA | — | \$98.3m | new |
| SANSW | — | \$217.5m | new |

Victoria is a pass-through region in 46% of intervals. Secondary netting applies in 20%. The loop is net negative in 12%.

EnergyConnect will change dispatch as well as settlement, so this is a lower bound on the structural break, not a forecast. It shows that value per VIC-side unit falls under the new rule even with unchanged physics.

## 13 Market settings, time of day and extremal dependence

**Market settings.** Intervals at the market price cap are rescaled to the FY2027 cap of \$23,200 from AEMO's `MARKET_PRICE_THRESHOLDS`. That changes a quarter's scarcity component by at most \$9.06/MWh (Exhibit N21). A forward valuation should load the delivery-year cap and cumulative price threshold, not the historical mix.

**Time of day.** Hour-by-season profiles (Exhibit N22) separate the midday renewable-surplus regime, where negative prices and export congestion sit, from the evening ramp, where scarcity and import limits coincide.

**Extremal dependence.** The cross-regional extremogram (Exhibit N16) estimates:

$$
\Pr\big(P_{j,t+h}>K\mid P_{i,t}>K\big)
$$

It measures common spikes at lag 0 and their persistence, the dependence the joint scenario model must reproduce [S19].

## 14 Valuation benchmarks and measured sensitivities

**Walk-forward baselines.** At each of 612 tranche–direction auctions with a settled delivery quarter, frozen rules forecast the payoff per unit using only quarters settled at least 28 days before the auction:

| Rule | Mean absolute error | Bias |
|---|---:|---:|
| Clearing price | \$7,586 | −\$3,130 |
| Trailing 4 quarters | \$9,954 | \$968 |
| Trailing 8 quarters | \$9,997 | \$746 |
| Trailing 12 quarters | \$10,132 | \$666 |
| Same season | \$10,695 | \$1,116 |
| Last quarter | \$11,500 | \$792 |

Any model proposed in Chapters 19–26 must beat the clearing price on identical tranches. A futures-scaled rule is added automatically when AER data exist.

**Spread-option benchmark.** Treating each interval as a Bachelier call on the spread gives:

$$
\mathbb E[S^{+}]=\sigma\,\varphi(\mu/\sigma)+\mu\,\Phi(\mu/\sigma)
$$

This is applied within season × 4-hour × flow-direction regimes and multiplied by the regime's mean flow. It overstates realised payoffs by a factor of 2.3 out of sample (Exhibit N25). The independence assumption is the error: within-regime flow collapses when spreads spike. Margrabe's lognormal exchange-option formula [R17] is not usable here because regional prices are often negative.

**Scenario registry.** `evidence/scenario_registry.json` dates the loop settlement start, Basslink regulation, every unit-count change found in AEMO's allocation table, and announced transmission projects. Project timelines are marked "announced" and are unverified. Exhibit N24 shows how an eight-quarter baseline value moves under each measured alternative: flow definition, loss share, lossless residue and the loop rule.

## 15 Auction microstructure and returns

Public bid stacks (`RESIDUE_PRICE_FUNDS_BID`) show a median bid-to-offer ratio of 5.8. 34.0% of units offered went unsold across the window (Exhibit N26).

Paying the clearing price on the calendar payment date and receiving weekly distributions with an assumed 21-day settlement lag gives:

- a median holding-period return of 28% per tranche;
- a loss in 37% of tranches;
- about 49 days to the value-weighted mean cash receipt.

Annualised figures are reported in the CSV but not headlined, because compounding a seven-week holding exaggerates them.

## 16 Strategic behaviour at interconnector limits (pilot)

On the highest-separation days per importing region (NSW1, SA1; 1,152 intervals), the price rise needed to call a further 200 MW of energy offers above the cleared stack has these medians, in \$/MWh: NSW: \$0.19 per MW with imports binding (325 intervals) against \$0.52 otherwise (251 intervals); SA: \$0.56 per MW with imports binding (299 intervals) against \$0.08 otherwise (277 intervals). The regions point in opposite directions. This measures offer-curve steepness; it does not identify intent. A full study would need all days, rebid timing and portfolio positions [R16].

## 17 Triggers and how to establish their importance

Model triggers as combinations of conditions. A coal outage during mild demand and high wind is different from the same outage during a hot evening with low wind, an import constraint and depleted batteries. Separate the probability of a trigger from the probability and value of a price event conditional on that trigger.

| Mechanism | Information available before delivery | Expected transmission to value |
|---|---|---|
| High residual demand | Joint weather, demand, rooftop PV and VRE scenarios | Moves dispatch onto steeper offers and increases import requirement |
| Thermal outages or derating | MT PASA vintage, outage notices, temperature, unit history | Reduces accessible supply; severity depends on replacement capacity |
| Network outage or security constraint | Published outage plan, constraint sets, credible contingencies | Limits imports or changes the feasible dispatch and loop allocation |
| Low wind across several regions | Spatial weather ensembles and low-wind duration | Weakens geographic diversity and raises simultaneous scarcity risk |
| Evening ramp | Sunset, temperature persistence, wind ramps and unit ramp capability | Creates short periods when flexibility is more valuable than average energy |
| Storage depletion | Simulated charging history, MWh capacity, efficiency and competing uses | Sustains high prices after initially suppressing them |
| Renewable surplus | High available VRE, low operational demand, minimum generation | Creates negative prices and export constraints within the energy component |
| Offer and rebid changes | Publicly available offer history, fuel and opportunity costs | Changes the effective supply curve even when physical MW is unchanged |
| FCAS and system security | Joint energy-FCAS availability, local service requirements | Can restrict energy dispatch or support and alter regional prices |
| Market interventions and price rules | Known market notices and effective settings | Alters observed settlement and caps sustained tail outcomes |

The AER's Q2 2026 significant-price report summary identifies SA events involving cold-driven demand, very low wind, cascading battery state-of-charge reductions, network limitations and rebidding. This is direct evidence for modelling multi-hour energy depletion and interacting constraints. Its selected incidents are mechanism studies, not a random sample from which to estimate event frequency. [S13]

WattClarity's January 2025 analysis of multiple auto-clamping episodes provides an operational explanation of counter-price flows and negative-residue management. Use such original expert analyses to create falsifiable event hypotheses and check dispatch reconstructions. Do not turn historical clamping descriptions into permanent rules after the EnergyConnect transition. [S14]

### An accessible supply margin

Construct a region's supply margin from locally deliverable generation, available VRE, storage discharge feasible given state of charge, demand response and jointly feasible imports, less operational demand and relevant obligations. Track both MW headroom and MWh endurance. A 500 MW battery with little remaining energy cannot be treated as 500 MW of sustained support throughout a cold, low-wind evening.

Avoid double counting rooftop PV already embedded in an operational demand definition. Likewise, distinguish VRE availability from realised dispatch: curtailed generation is partly an outcome of congestion. Use historical available forecasts for predictive inputs; actual dispatch remains an explanatory outcome or an explicitly labelled conditional input.

### Predictive explanation and causal explanation

For predictive screening, fit simple conditional frequency tables, a logistic model or an additive model with predeclared interactions. Report sample counts, confidence intervals, lead time and whether every predictor was knowable at issue time. Evaluate variables such as accessible reserve margin, net-demand difference, import headroom, outage coincidence and storage endurance.

For causal analysis, reconstruct a selected event and rerun dispatch after changing one physical mechanism. Removing a transmission outage while freezing future prices is not a dispatch counterfactual. Historical matching can support a diagnostic comparison, but weather, bids and outages can confound associations. Feature importance and SHAP values explain the fitted model, not necessarily the power system's causal mechanism.

Use two ledgers for trigger attribution. The **event ledger** identifies overlapping descriptions such as low wind plus coal outage plus constraint. The **value ledger** assigns contributions using a declared counterfactual method so the same dollars are not counted three times. Store unresolved events explicitly instead of forcing every spike into a named cause.

## 18 What academic research contributes

The literature supports a combination of structural market reasoning, calibrated regime probabilities and joint scenario simulation. It does not establish that one complex architecture will dominate on current NEM quarters. The following transfers are proposed research choices, not replications or guarantees of published performance.

### Regional equilibrium and structural coupling

Smith and Shively's 2018 Australian study motivates a regional price model from spatial equilibrium with constrained trade and multiple price regimes, then captures additional dependence through a copula construction. Its useful lesson is to condition price separation on the state of interregional trade. For this project, implement unconstrained, export-constrained, import-constrained and abnormal-network regimes, while recognising that the NEM's generic constraints and loop topology are richer than a simple two-region equilibrium. [S15]

Alasseur and Feron's structural coupled-market model represents multiple production fuels and limited interconnection, with pricing applications to derivatives and transmission rights. It motivates a reduced regional supply-curve model that clears prices and flows together. Extend that architecture with NEM loss treatment, generic security constraints, storage and effective market rules before using it for SRAs. Analytic tractability in the paper is not evidence that current NEM tails can be valued without simulation. [S16]

Füss, Mahringer and Prokopczuk's 2015 work incorporates forward-looking demand and available-capacity information into derivatives pricing. The reported benefit is especially relevant when those fundamentals drive price sensitivity. This supports using issue-dated outage and demand information to update quarter scenarios, rather than estimating every quarter from an unconditional historical price process. It does not justify using future realised demand in an ex ante backtest. [S17]

### Spike occurrence and dependence

Manner, Türk and Eichler's 2016 study models Australian price-spike indicators jointly, with dynamic dependence and a copula representation. It provides a direct precedent for estimating the four joint spike states rather than multiplying independent regional spike probabilities. Start with a calibrated multinomial or shared-factor model and use more flexible dependence only if out-of-sample scores improve. [S18]

Han, Cribben and Trück's extremal-dependence work uses extremograms to measure persistence and transmission of Australian extreme prices. Apply the same diagnostic idea to choose event grouping windows and to test whether simulated spikes cluster correctly across regions and time. Its historical sample predates the present storage fleet and five-minute settlement regime; reuse the method, not the estimated historical dependence coefficients. [S19]

Liu and colleagues' 2022 extreme-price study uses a multivariate logistic approach with demand, reserve capacity, renewable share, interconnector flow and historical prices. The accessible primary manuscript record establishes the model and feature family; this report does not independently reproduce its operational timing or reported accuracy. It motivates a transparent event classifier as a benchmark, with future flow replaced by a forecast or joint scenario variable. [S20]

### Probabilistic forecasting and disciplined benchmarking

Cornell, Dinh and Pourmousavi propose probabilistic NEM forecasting using forecast combinations, spike treatment and quantile regression, including models with different training lengths. This suggests combining stable and adaptive windows in a market undergoing rapid change. However, filtered spikes must be restored through an explicit tail model for valuation: improving median-price accuracy while removing tail mass would damage cap and SRA estimates. [S21]

Lago, Marcjasz, De Schutter and Weron's forecasting review argues for strong simple benchmarks, multiple markets and substantial test periods, appropriate metrics and significance testing. Apply that discipline at the contract-payoff level. A lower average price MAE or flow MAE is not sufficient if the model worsens quarterly cap bias or understates downside hedge failures. [S22]

### Risk premia and adjacent financial methods

Bessembinder and Lemmon's equilibrium model links power forward premia to hedging demand and the price distribution. It provides a theoretical reason why forward prices need not equal physical expected spot prices. Do not import one sign or fixed premium into every NEM quarter; estimate premium uncertainty by region, season, product and time to delivery. [S23]

The Bevin-McCrimmon, Diaz-Rainey and Sise working paper on New Zealand futures finds time-varying premia and a role for liquidity, particularly in longer-dated contracts. This is adjacent-market evidence for preserving bid-ask spreads, trading activity and quote age in the valuation dataset. It is not a calibrated Australian premium model. [S24]

Heffernan and Tawn's conditional-extremes framework models the other variables when one variable is extreme, without requiring all variables to become extreme together. It offers a useful advanced model for the distribution of neighbouring prices and transfer availability conditional on an NSW or SA spike. Fit it only after declustering, threshold diagnostics and sensitivity to the statutory price bounds. [S25]

Meucci's entropy-pooling framework changes scenario probabilities to incorporate views while remaining close to an initial distribution. Adapt it to create a market-consistent scenario distribution from the physical ensemble. Matching liquid base and cap quotes then reveals what scarcity weighting is needed; keeping SRA prices out of that calibration preserves an independent SRA valuation test. [S26]

### Methods to test in order

| Stage | Candidate | Primary purpose | Main limitation |
|---|---|---|---|
| Benchmark | Seasonal empirical blocks and simple regressions | Establish reproducible value and frequency baselines | Weak extrapolation to new assets and topology |
| Statistical model | Additive energy model plus spike occurrence and severity | Interpretable conditional price distribution | Requires coherent regional and temporal dependence |
| Joint scenario model | Regime-conditioned prices and constrained flows | Price spread, cap and residue distributions together | Feasibility and calibration must be checked |
| Structural model | Regional supply curves and network dispatch | New topology, outage and storage counterfactuals | Offer behaviour and detailed constraints are difficult |
| Advanced additions | Conditional extremes, dynamic copulas, online ensembles | Address specific residual tail or adaptation failures | Easily overfit with few independent stress events |

### 18.1 Transmission-right auction pricing (new in version 2)

The closest analogue to the Chapter 7 result is the literature on centrally auctioned transmission rights:

- **New York.** Transmission congestion contracts cleared systematically below realised congestion payoffs, transferring value from ratepayers to financial participants [R11]. Siddiqui and co-authors raised efficiency concerns earlier.
- **Mechanism design.** Price formation in FTR auctions depends on bid-quantity limits and simultaneous feasibility, which can separate clearing prices from expected payoffs even with good forecasts [R12–R14].
- **Europe.** Long-term transmission right prices have fallen short of forward-market price spreads [R4].
- **Nordic area-price contracts.** The Nordic CfD (EPAD) literature finds significant risk premia in exchange-traded spread contracts [R9, R10].
- **NEM futures.** Positive, seasonal risk premia exist in NEM futures [R7]. Australian hedging practice is surveyed in [R8].

The AEMC's consultant review of the SRA confirms the pooling of parallel links and the pre-loop treatment of negative residue. It also questions whether excluding negative residue improves hedging [R1].

## 19 The recommended model architecture

### Layer 1 Information available at the valuation date

Freeze a snapshot containing forecast vintages, outage plans, committed projects, market settings, contract specifications and executable or timestamped reference quotes. Every field needs issue time, receipt time and delivery time. Use both issue and receipt time to establish availability. A recently archived file can contain revisions that were unavailable on the historical auction date.

### Layer 2 Joint fundamental scenarios

Draw spatially coherent weather sequences, translate them into demand and available wind/solar, sample generation outages and network availability, and evolve storage state. Calendar and asset changes map historical weather into the future quarter. Keep full trajectories so a three-day low-wind event remains three days long.

### Layer 3 Network and price formation

The minimal viable model combines a network-state distribution with a conditional energy-price model and a joint spike process. A more structural challenger clears regional offers subject to shared constraints, loss curves, ramp limits and intertemporal storage. In either case, prices and flows need a common state and shared shocks. Sampling six connector forecasts independently is unacceptable if it violates regional balance or a shared constraint.

Use regional demand balance and active constraint residuals as feasibility diagnostics. Where a statistical ensemble is projected onto a feasible region, preserve the original and adjusted trajectories and measure the change in value. Projection is a modelling operation that can distort the tails; it should not silently manufacture coherent-looking scenarios.

### Layer 4 Settlement and contractual payoffs

On each scenario calculate total spread, capped-energy spread, cap spread, losses, raw residues, allocated residues and unit-level cashflows. Apply effective dates within a quarter. Keep five-minute detail until all nonlinear payoffs are calculated, then aggregate.

### Layer 5 Valuation and decisions

Produce physical expected outcomes, uncertainty intervals, market-calibrated values, expected trading P&L and portfolio hedge metrics. Keep model uncertainty separate from scenario uncertainty. More Monte Carlo paths reduce simulation noise but do not correct a wrong outage model or a missing scarcity regime.

A useful internal scenario record is identified by valuation snapshot, model version, scenario, interval, region or connector, topology version and settlement-rule version. Store random seeds and scenario weights. Reproducing a valuation requires all of these, not just a saved estimator.

## 20 Forecasting a quarter rather than extending a short forecast

The existing project forecasts flows and reported limits from short horizons out to days. A quarter requires distributions over weather, outages and dispatch states that cannot be supplied by simply extending the last short-range forecast. Use three information horizons with a tested blending rule.

Near delivery, use issue-dated weather and demand ensembles and operational network information. At medium horizons, gradually shift toward calibrated subseasonal distributions where they demonstrate local skill. For the rest of the quarter, use seasonally conditioned weather-year and outage scenarios with the future asset fleet. Any 7-day or 14-day boundary is a design starting point, not a universal meteorological rule; validate the blend by variable and season.

### Weather and structural change

Sample multi-day or multi-week blocks jointly across regions, not independent regional hours. Preserve temperature, wind, solar and demand dependence, including demand persistence after hot afternoons and cold evenings. Apply calendar corrections and regional renewable buildout. If climatic outlooks alter scenario weights, record the source vintage and backtest that weighting against climatology.

Historical power output cannot be scaled blindly with nameplate capacity. New renewable projects can change spatial diversity, congestion and curtailment. Use location and availability before applying the dispatch and constraint model. Include commissioning uncertainty instead of counting every announced project as fully available from its expected date.

### Outages and restoration

Separate planned outages, forced outages, derating and commissioning. Planned work comes from the information available at the valuation date. Forced outages need unit- or fleet-level hazard and restoration distributions, with common-cause factors for heat, fuel constraints or correlated plant conditions. Independent Bernoulli outages generally miss restoration duration and simultaneous stresses.

MT PASA is an important forward input, but submission horizons and model-output horizons differ. The AEMC's duration reform and AEMO's process description distinguish generator availability information from reliability assessments. Preserve table-specific horizons and vintage coverage; do not assume every MT PASA product gives an equally detailed three-year dispatch forecast. [S27]

### Storage and hydro

Evolve stored energy using charging, discharging, efficiency and operational limits. Represent participation in FCAS and uncertainty in opportunity-cost bidding. A perfect-foresight battery schedule can suppress simulated scarcity too aggressively. Compare imperfect foresight, forecast-responsive and stress-conservative dispatch policies. Hydro requires water budgets and opportunity costs, not just installed MW.

### Simulating enough tails

Start with a manageable ensemble, such as a few thousand quarter trajectories, and increase it until key expected payoffs and tail-risk statistics stabilise across seeds. This is a proposed engineering range, not a precision guarantee. Use importance sampling for rare joint outages or severe weather only with explicit likelihood weights. Avoid presenting a 99th percentile as stable when it comes from a handful of effectively independent stress paths.

## 21 Forecasting the energy component

Fit E_r = min(P_r, 300), or the corresponding regional energy spreads, using residual demand, regional net-demand differences, fuel costs, available generation, storage, outages, time of day and network regime. Begin with a regularised linear model and a generalised additive model. Test shallow boosting as a challenger.

A direct spread model concentrates on the target, while separate regional models support coherent valuation across several pairs. Prefer a shared regional-price representation with pairwise calibration checks: predicted NSW-VIC plus VIC-SA must equal NSW-SA when formed from the same regional scenarios. Independently fitted pair models can violate that identity.

Negative-price observations deserve their own diagnostics. Their frequency, depth, duration and spatial coincidence affect energy spreads and raw residues. A model that treats all sub-$300 prices as one Gaussian regime can miss daytime export congestion. Consider negative, ordinary nonnegative and capped-at-$300 states, with continuous distributions within states.

Include seasonal fuel and offer-curve uncertainty. The fuel and heat-rate work already in the repository can support supply-curve scenarios, but technical marginal cost is not the same as an observed offer price. Opportunity costs, hedges, startup costs and strategic behaviour can all alter bidding. Use the structural model as a mechanism-based challenger and calibrate discrepancies rather than declaring its costs to be the true market price.

## 22 Forecasting scarcity occurrence duration and severity

### Occurrence

Estimate the probability of entering a spike episode conditional on the pre-event state. A logistic or additive hazard model is a strong starting point. Predict the four regional-pair states jointly, or simulate a shared regional shock model, to preserve simultaneous scarcity. Use proper probability scores and calibration plots rather than classification accuracy, which can be high simply by predicting no spikes.

### Duration

Use a separate exit hazard or semi-Markov duration model. Its inputs can include elapsed event time, persistent weather, outage restoration, remaining storage energy and expected import capability. Compare the simulated distribution of event lengths, quiet gaps and clustered days with history. A self-exciting process is a possible challenger when residual clustering remains after physical covariates, but should not substitute for modelling sustained low wind or a known outage.

### Severity

Model positive excess above $300 conditional on an event and its state. Begin with empirical or quantile-based severity, allowing a separate probability mass at the applicable market cap. A generalised Pareto tail can be tested above a higher statistical threshold; $300 is the contractual threshold and need not be the best threshold for asymptotic tail fitting. Respect the effective price cap, administered pricing and any relevant interventions.

Market settings change over time. The AEMC schedule gives a 2026-27 market price cap of $23,200/MWh. Store settings by effective date, including floor, cumulative-price threshold and administered-price provisions, rather than retaining one constant cap from the historical sample. The $300 cap strike is a different quantity from the market price cap and administered price cap. [S28]

For a region, expected quarterly cap excess is the sum over intervals of event probability times conditional mean excess, divided by the interval count. For episode models, it is expected total episode excess-energy divided by quarter hours. Frequency times mean duration times mean severity is only a rough factorisation when those quantities are dependent. Prefer summing simulated episodes directly.

### Dependence changes what can be priced

The expected difference of two cap payouts depends on the two marginal expectations, even without knowing their dependence. Dependence is nevertheless crucial for the distribution of that difference, the frequency of destination-only scarcity, and every payoff involving flows or allocation gates. This distinction prevents using SRA dependence arguments where simple linearity already answers the expected futures-spread question.

Keep a scorecard of interval exceedance rates, episode arrival rates, duration, conditional excess, cap-hit frequency, regional co-exceedance, and cap/spread covariance. Matching only the regional cap means can leave all other tail properties wrong.

## 23 Turning forecasts into a market comparison

Keep two distributions. The physical distribution $\mathbb P$ is the best forecast of outcomes. A pricing distribution $\mathbb Q^{*}$ is one set of scenario weights consistent with quotes. Markets are incomplete, so $\mathbb Q^{*}$ is not unique. For a future, the estimated premium is the quote minus the physical expected settlement. For an SRA unit, it is the discounted physical expected payoff minus price and fees.

For a partially delivered quarter with elapsed fraction $w$ and realised average $\bar P^{\text{elapsed}}$, the market-implied remaining average is:

$$
\bar P^{\text{remaining}}=\frac{F-w\,\bar P^{\text{elapsed}}}{1-w}.
$$

The same formula applies to cap excess.

For a cap priced at $G$ with an assumed mean excess $m$ during scarcity, the pricing-weighted scarcity hours are:

$$
h=\frac{H\,G}{m},
$$

For example, $H=2{,}160$, $G=12$ and $m=4{,}000$ give $6.48$ hours. The same price fits many frequency–severity pairs, and a cap spread $G_B-G_A$ does not identify destination-only probability. The workbench below computes both the destination-cap and cap-spread versions.

Entropy pooling reweights physical scenarios $p_s$ to $q_s$, subject to pricing constraints on payoffs $X_s$ [S26]:

$$
\min_{q}\sum_s q_s\log\frac{q_s}{p_s}\quad\text{s.t.}\quad q_s\ge0,\ \ \sum_s q_s=1,\ \ \Big|\sum_s q_sX_{k,s}-\text{quote}_k\Big|\le\text{half-spread}_k .
$$

Calibrate to base and cap quotes and hold SRA prices out as a test. Monitor the effective scenario count, $1/\sum_s q_s^2$.

## 24 Comparing SRA prices with futures prices

A unit price is not a $/MWh spread. The conversion needs the unit proportion $\theta$, the quarter length $H$ and an effective positive-spread flow $\bar F$:

$$
\text{required flow-weighted spread}=\frac{\text{price}}{\theta\,H\,\bar F}.
$$

For example, with $\theta=1/1{,}500$, $H=2{,}160$ and $\bar F=500$ MW, a $15,000 price requires $20.83/MWh. Chapter 8 replaces the assumed $\bar F$ with the measured hedge ratio $n^{*}$, the number of units that best replicate one MW of spread. The empirical relative-value statement is therefore:

$$
\text{SRA cost per MW-equivalent}=n^{*}\times\text{clearing price}\quad\text{vs}\quad H\times(\text{futures spread}),
$$

together with the stress ratio in Exhibit N11, which shows how much of that equivalence survives in the weeks that matter.

## 25 Data architecture and source requirements

| Dataset | Main use | Required timing or quality control |
|---|---|---|
| Regional five-minute RRP and flags | Energy, cap and spread payoffs | Revisions, intervention/pricing runs and market suspension |
| Interconnector dispatch and metered flows | Dispatch state and residue reconciliation | Flow sign, losses, identifier changes and physical versus pricing runs |
| Generic constraints and versions | Feasible transfers and mechanisms | Effective date, LHS/RHS, active equation and public-release timing |
| Demand and VRE forecasts | Issue-date conditional price drivers | Forecast issue and receipt; availability versus dispatch |
| Generator availability and outage plans | Supply distribution | Planned versus forced; update history and restoration uncertainty |
| Storage and hydro characteristics | Multi-hour flexibility | MW, MWh, efficiency, energy state and opportunity cost |
| Weather histories and ensembles | Joint future scenarios | Spatial coherence, calendar mapping and vintage coverage |
| SRA notices, results and distributions | Contract mapping and value backtest | Quarter, tranche, entitlement, units, fees and reconciliation |
| Base and cap market quotes | Market energy/scarcity decomposition | Same timestamp, bid-ask, profile, liquidity and quote age |
| Rules and asset commissioning | Structural regimes | Effective dates within delivery quarter |

AEMO's public data-model documentation identifies the auction, contract and unit-allocation tables, while distinguishing participant-specific information. Do not assume that every documented table or bid is public. Public reports can support clearing-price and aggregate-payout research; participant cashflows and executable quote histories may require additional access. [S29]

Use AEMO's Quarterly Energy Dynamics reports and the AER's incident reports as external reconciliation and mechanism checks. Their aggregate statistics and selected examples should complement a complete five-minute event census, not replace it. ASX lists public product information and data interfaces; actual historical market-data access and usage rights need to match the intended ingestion method. [S30, S31]

Store four time axes where relevant: physical interval end, source issue time, receipt time and record revision time. For the historical study use fixed UTC+10 and interval-ending conventions. Distinguish an ASX trading timestamp, which can follow daylight-saving exchange hours, from NEM delivery time.

A settlement reconciliation should progress from raw residue to positive/negative treatment, loop allocation, unit entitlement, fees and billed cashflows. Record the unexplained difference at each step. An aggregate quarterly match alone can hide offsetting directional or interval errors.

## 26 Validation that reflects the trading objective

### Historical origins

Freeze models and information at each historical auction date and representative futures valuation dates, such as one, three, six and twelve months before delivery. Include an in-quarter update experiment. Retrain only on information available at the origin and assess the delivered quarter afterwards. Use an untouched final period after the model design is fixed.

The current two-year local price panel supplies only seven complete quarters. Thousands of five-minute observations do not create thousands of independent quarterly stress samples. The project's existing test periods have already informed model development, so they should not be relabelled as a pristine final holdout. Expand history across multiple stress regimes, retaining five-minute settlement and structural-break distinctions. [L03]

### Scores and economic tests

| Target | Statistical test | Economic or operational test |
|---|---|---|
| Flow and network regime | MAE, quantile loss, feasibility residuals | Error during valuable spread intervals |
| Spike probability | Brier score, log score, reliability curves | Missed high-value episodes and false-alarm cost |
| Event duration and severity | Survival calibration and tail quantiles | Cap mean bias and concentration in largest days |
| Joint regional scenarios | Co-exceedance and variogram/energy scores | Spread variance and hedge failure in common stress |
| Quarterly spread | Mean bias, interval coverage, CRPS | Realised spread P&L after execution costs |
| SRA payout | Reconciliation error and distribution coverage | Payout shortfall, downside loss and hedge effectiveness |
| Market calibration | Held-out price error and weight stability | Value beyond fitted instruments and liquidity cost |

Evaluate full distributions and the expected payoff separately. A model can predict the median well and materially underprice a cap. Conversely, one rare episode can dominate an unbiased sample mean and produce wide estimation uncertainty. Report block-bootstrap intervals grouped by stress days or episodes and, where possible, by quarter or year.

Test at least five baselines: same-season historical resampling; simple conditional energy plus logistic scarcity; market base-and-cap decomposition; the existing flow model with an empirical joint price layer; and the proposed hybrid model. For the structural challenger, compare against a simpler version without detailed network/FCAS features to quantify their incremental value.

### Ablations that expose false improvements

Run paired experiments removing topology information, storage energy state, regional tail dependence, future asset changes and forward outage information. Compare five-minute payoffs with half-hour-averaged payoffs. Compare jointly simulated flow-price paths with shuffled paths to quantify covariance importance. Compare historical and new loop settlement on identical physical scenarios.

For each comparison report both average performance and stress-regime performance. Keep input-vintage failures separate from model failures. If an improvement relies on realised future demand or a retrospectively observed constraint, label it a conditional experiment rather than a tradable forecast gain.

### Proposed acceptance gates

Require exact algebraic decomposition and reproducible data lineage. Require contract settlement to reconcile within an explicitly investigated rounding/revision tolerance. Require probability calibration and quarterly payoff performance to be competitive with simple baselines across more than one season. Require apparent expected P&L to survive bid-ask, fees, financing and plausible model sensitivities. Numerical commercial thresholds should be set from desk risk appetite and model uncertainty; they cannot be inferred from this literature review.

## 27 A worked quarterly valuation example

These numbers are illustrative, not current quotes. Take a 90-day quarter ($H=2{,}160$) with destination NSW and origin VIC. The physical expectations are capped-energy prices of $85 and $65 and cap excesses of $18 and $8. The market quotes are base futures of $110 and $76 and caps of $25 and $9.

| Quantity | Physical expectation | Market | Market − physical |
|---|---:|---:|---:|
| Base spread $F_B-F_A$ | 30 | 34 | +4 |
| Cap spread $G_B-G_A$ | 10 | 16 | +6 |
| Capped-energy spread | 20 | 18 | −2 |

Buying the capped-energy combination (long NSW base, short NSW cap, short VIC base, long VIC cap) has expected terminal P&L $2\times2{,}160=4{,}320$ dollars per MW before costs and funding.

For an SRA illustration, take a hypothetical direction with $\theta=1/1{,}500$ and an expected distributable residue of $30m. The expected payoff is $20,000 per unit against a $15,000 price, a $5,000 undiscounted margin. Chapter 7 shows that realised history has delivered margins of this kind on average, with wide dispersion and a strong horizon gradient.

## 28 Portfolio use and instrument selection

Choose the instrument according to the risk being expressed. An ordinary energy-price divergence belongs naturally in a capped-energy spread. A view about differential high-price excess belongs in a cap spread. A view about deliverable transfer during price separation and contractual allocation belongs in an SRA. An outright regional spread combines energy and scarcity.

For a cross-region retail or generation exposure, evaluate hedge performance on the joint portfolio. An SRA can be a poor standalone value purchase yet a useful hedge in particular scenarios, or the reverse. Estimate the covariance with the exposure, then test expected shortfall of the residual loss. A minimum-variance ratio is a diagnostic, not a sufficient hedge prescription for skewed payouts.

Use constrained scenario optimisation to minimise expected shortfall or a utility-based loss measure subject to position, liquidity and funding limits. Include base futures, cap futures and the available SRA directions as distinct columns of the scenario cashflow matrix. Regularise positions so small estimation changes do not generate extreme offsetting trades.

Capital and liquidity risk require separate treatment. Regional futures can create variation-margin calls before delivery even when the eventual hedge works. SRA payment timing and cash-security provisions create another funding profile. A terminal payoff simulation alone cannot estimate peak cash needs; simulate market revaluation paths or apply explicit funding stresses.

Report portfolio sensitivity to one-region scarcity, common scarcity, interconnector loss, simultaneous outages, prolonged low wind, storage depletion and new loop allocation. A hedge that works only in the average scenario has not addressed the intended risk.

## 29 Integration with the existing IC project

The repository already contains flow/limit models, constraint studies, event reconstructions and an offline production scaffold. Reuse connector identity, input-vintage contracts, data hashes, model registries and diagnostic reports. The existing scaffold supports portable model packages but is documented as an offline-first scaffold, not a deployed live service. [L04]

The existing research also distinguishes dispatch MWFLOW from metered physical flow, and conditional experiments using realised future fundamentals from operational forecasts. Preserve those distinctions in the valuation work. Short-horizon improvements do not demonstrate quarterly price or SRA skill. Selected event atlases are valuable mechanism libraries but are not a population sample for frequency estimation. [L02, L03]

Create new modules alongside the forecasting code rather than relabelling old targets. Suggested responsibilities are a contracts and rules registry; five-minute price decomposition; event census; scenario generation; network and price models; SRA settlement; market calibration; and valuation backtesting. Each module should expose a data contract and an independently inspectable output.

For structural event reconstructions, Nempy is a relevant open-source research starting point. Its authors document energy dispatch, interconnectors, losses, ramping, generic constraints and FCAS features. Validate its coverage of the required current rule and bidding features, and pin the version. It provides a dispatch-modelling tool, not a ready-made quarterly forecasting or SRA valuation model. [S32]

The new descriptive script and CSVs in this report folder can seed the event and payoff layer. They do not change any production model, fetch market quotes or implement exact SRA settlement. Their immediate value is an audited target definition and a baseline description of the economic quantities the next model must predict.

Version 2 implements the suggested modules as `nemic/valuation/` (config, acquisition, panel, baseline, settlement, loop, evidence, market, mechanisms, valuation tests, summary), driven by `configs/valuation/interregional_valuation_v2.json` and run with `python -m nemic.valuation <stage>`. It is a research stack, separate from the forecasting campaigns and the production scaffold.

## 30 Research programme and deliverables

### Stage 1 Establish the economic ledger

Build a full five-minute price and flow census with effective-dated contract metadata. Reproduce regional energy/cap identities and joint-state contributions. Implement pre-loop and loop SRA settlement fixtures using official worked examples, then reconcile actual public distributions. Deliver a historical ledger with a visible reconciliation waterfall. Stop treating gross flow-times-spread as a settlement target once the contractual engine exists.

### Stage 2 Build credible physical baselines

Create seasonal block scenarios and the simple conditional energy/occurrence/severity model. Fit dependence and duration diagnostics. Connect existing flow forecasts only where their input timing and horizon are suitable. Deliver forecast distributions and a transparent scorecard, with separate quarterly and short-horizon results.

### Stage 3 Add structural changes and tail mechanisms

Implement future asset and topology scenarios, storage energy dynamics, generation outage duration and relevant network regimes. Use selected historical episodes to verify mechanisms. Develop a structural dispatch challenger and compare economic targets, not just price MAE. Deliver a set of reproducible stress scenarios and sensitivity curves.

### Stage 4 Join market prices and test relative value

Ingest timestamped base and cap quotes and SRA tranche results. Decompose the market's energy and scarcity price, run market-consistent scenario calibration, and hold out instruments for validation. Deliver a quarter-by-direction valuation sheet with physical expectation, market price, uncertainty, implied stress assumptions and portfolio impacts.

### Stage 5 Freeze and evaluate prospectively

Freeze the chosen design and run new quarters without retrospective feature changes. Track forecast revisions, realised events, model explanations and executed or realistically executable costs. Only then assess whether the approach provides reliable decision value. A suggested initial build window is roughly eight to twelve weeks for a small team with the data already accessible; exact duration depends primarily on settlement reconciliation and historical quote/vintage access, not model training speed.

Status at version 2: Stage 1 (ledger and reconciliation) is complete. Stage 4 is complete on the auction side and waits on futures data. Stages 2, 3 and 5 remain as designed.

## 31 The quarterly decision document

The production output should begin with the region pair, delivery quarter, issue timestamp, sign convention and applicable settlement regimes. Present the expected total spread with capped-energy and scarcity components; show their uncertainty and the corresponding market combinations. Present SRA expected distribution and price separately in dollars per unit.

Then show the four joint spike states, expected hours and episode counts, conditional severity, high-value trigger combinations, flow during those episodes, and the fraction of value attributable to the largest stress days. Include effective import capability and storage endurance in the critical scenarios.

The market interpretation should state which assumptions must change to reconcile the physical model with quotes. For example, the market may require more destination-only scarcity, a larger common tail, weaker transfer availability during stress or a premium for hedging demand. If several explanations fit, display that ambiguity instead of selecting one with false precision.

End with a reconciliation of model changes since the last valuation: new information, changed scenario weights, parameter updates, contract/rule changes and market movement. Every claimed opportunity should be accompanied by the scenarios that would invalidate it and the cost of expressing it through the available instruments.

## 32 Evidence limits and unresolved questions

- **Futures.** No futures or cap quotes are in this build. The SRA-versus-futures relative value is therefore measured as hedge equivalence and SRA premia, not as a joint premium comparison.
- **Loop counterfactual.** It holds dispatch fixed. EnergyConnect will change flows.
- **Constraint attribution.** It uses AEMO's naming convention, not equation coefficients.
- **Strategic analysis.** It is a pilot.
- **Early unit counts.** For 56 early quarter-directions, unit proportions use published maxima.
- **Auction premium drivers.** The auction premium's decomposition into risk, capital and expectations is not identified. The open question is whether the discount persists in quarters settled under the loop rule.

## 33 Sources and reading guide

Sources were reviewed on 18 September 2026. Official specifications govern contractual claims; academic and practitioner findings motivate model design. Some publisher pages supplied abstracts or selected accessible text rather than complete methods. Those access limits are recorded where material. The review is an extensive targeted synthesis, not a claim to have systematically screened every publication. Dates below distinguish working-paper versions from market-rule effective dates.

### Market contracts and current rules

[S01] ASX. Australian Electricity Derivatives fact sheet, June 2025. Base and $300 cap specifications, pp 7-8 and 12-13. [Primary product document](https://www.asx.com.au/content/dam/asx/markets/trade-our-derivatives-market/derivatives-market-overview/energy-derivatives/australian-electricity-fact-sheet.pdf). Read for payoff definitions; applicable operating rules take precedence.

[S02] ASX Energy. Australian Electricity New listed Interregional spreads, 11 August 2014. [Exchange notice](https://www.asxenergy.com.au/newsroom/industry_news/australian-electricity---new-). Historical launch and leg-sign convention, not evidence of current execution liquidity.

[S03] AEMO. Methodology for the allocation and distribution of settlements residue, 2 June 2024. [Primary methodology](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/methodology_for_the_allocation_and_distribution_of_settlements_residue.pdf). Historical loss and allocation basis; apply later effective changes where relevant.

[S04] AEMO. Settlements Residue Auction Rules, effective 7 August 2026. [Final rules and participation agreement](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/2026/settlements-residue-auction-rules-7-aug-2026.pdf). Sections 4 and 15 and Schedule 1 section 9 are central to implementation.

[S05] AEMO. Unit Category Data Q2 2028, revised May 2026. [Quarter-specific unit notice](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/auction-notices/2025/unit-category-data-2028q2---revised.pdf). An example of entitlement and fee metadata, not a universal set of unit counts.

[S06] AEMC. Interregional settlements residue arrangements for transmission loops, final determination, 25 September 2025. [Final determination](https://www.aemc.gov.au/sites/default/files/2025-09/Final%20determination-%20ERC0386.pdf). Relevant indexed primary text includes section 3.2.3 and the treatment of losses and secondary netting; direct retrieval was intermittently restricted.

[S07] AEMO. Project EnergyConnect Market Integration stakeholder reference paper, May 2026. [Reference paper and worked examples](https://www.aemo.com.au/-/media/files/initiatives/project-energyconnect/pec-mi-settlements---stakeholder-reference-paper.pdf). Read pp 4-5 for operational/settlement dates and pp 7-20 for examples.

[S08] AEMO. Methodology for the Allocation Distribution and Recovery of Settlements Residue consultation, initiated 16 September 2026. [Consultation and draft documents](https://www.aemo.com.au/consultations/current-and-closed-consultations/methodology-for-the-allocation-distribution-and-recovery-of-settlements-residue). Draft status at the research cutoff is material.

[S09] AEMO. EnergyConnect Market Integration frequently asked questions. [Current operational FAQ](https://www.aemo.com.au/initiatives/major-programs/nem-reform-program/nem-reform-program-initiatives/project-energyconnect-market-integration-project/frequently-asked-questions). Whole-loop negative-residue management and implementation distinctions.

[S10] AEMO. Final expedited consultation report for Basslink SRA rules, 30 April 2026. [Final report](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/2026/final-report-expedited-consultation-for-the-nem-basslink-30-april-2026.pdf). New categories and per-unit fee methodology.

[S11] AEMO. Auction Report 2026 Quarter 2, dated 4 August 2026, published 18 August. [Auction results](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/auction-reports/2026/auction-report-2026-quarter-2.pdf). June 15 auction; Table 4 on p 7 contains the cited Q4 2026 tranche prices.

[S12] AEMO. Constraint Frequently Asked Questions. [Constraint documentation](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq). Source for interpreting constraints and reported interconnector capability, together with the repository's documented methodology.

### Market mechanisms and original expert analysis

[S13] AER. Reports on significant electricity prices for Q2 2026, 31 August 2026. [Regulator findings](https://www.aer.gov.au/news/articles/communications/aer-reports-significant-electricity-prices-q2-2026). Selected-event mechanism evidence; do not use as an unbiased event-frequency sample.

[S14] WattClarity. Interconnector intricacies double and triple auto-clamping of negative residues, January 2025. [Original practitioner analysis](https://wattclarity.com/articles/2025/01/interconnector-intricacies-double-and-triple-auto-clamping-of-pesky-negative-residues/). Historical operational interpretation.

### Academic methods

[S15] Smith, M. S. and Shively, T. S. Econometric Modeling of Regional Electricity Spot Prices in the Australian Market, April 2018 working paper. [Full paper](https://arxiv.org/pdf/1804.08218). Spatial equilibrium, constrained trade and regional dependence.

[S16] Alasseur, C. and Feron, O. Structural price model for electricity coupled markets, 2017 preprint; related Energy Economics article 2018. [Author preprint](https://arxiv.org/abs/1704.06027). Structural supply curves, multiple fuels and limited interconnection.

[S17] Füss, R., Mahringer, S. and Prokopczuk, M. Electricity derivatives pricing with forward-looking information. Journal of Economic Dynamics and Control 58, 34-57, 2015. DOI 10.1016/j.jedc.2015.05.016. [Authors' institutional record](https://research.uni-hannover.de/en/publications/electricity-derivatives-pricing-with-forward-looking-information/). Abstract and publication record reviewed.

[S18] Manner, H., Türk, D. and Eichler, M. Modeling and forecasting multivariate electricity price spikes. Energy Economics 60, 255-265, 2016. DOI 10.1016/j.eneco.2016.10.006. [Publisher record](https://www.sciencedirect.com/science/article/pii/S0140988316302870). Joint binary spike model; accessible abstract and selected text reviewed.

[S19] Han, L., Cribben, I. and Trück, S. Extremal Dependence in Australian Electricity Markets, 2022 preprint; later Journal of Commodity Markets publication. [Author paper](https://arxiv.org/abs/2202.09970). Persistence, cross-regional extremograms and historical regime dependence.

[S20] Liu, L. and colleagues. Forecasting the occurrence of extreme electricity prices using a multivariate logistic regression model. Energy 247, 123417, 2022. DOI 10.1016/j.energy.2022.123417. [Institutional manuscript](https://research-repository.griffith.edu.au/server/api/core/bitstreams/f003c844-829c-4db6-8257-47538355a229/content). Indexed manuscript information reviewed; full-file access was restricted during retrieval.

[S21] Cornell, C., Dinh, N. T. and Pourmousavi, S. A. A probabilistic forecast methodology for volatile electricity prices in the Australian National Electricity Market, 2023 preprint. [Author paper](https://arxiv.org/abs/2311.07289). Probabilistic forecast combinations and adaptive training windows.

[S22] Lago, J., Marcjasz, G., De Schutter, B. and Weron, R. Forecasting day-ahead electricity prices A review of state-of-the-art algorithms best practices and an open-access benchmark. Applied Energy 293, 116983, 2021. [Author manuscript](https://arxiv.org/abs/2008.08004). Benchmark design and evaluation discipline.

[S23] Bessembinder, H. and Lemmon, M. L. Equilibrium Pricing and Optimal Hedging in Electricity Forward Markets. Journal of Finance 57, 1347-1382, 2002. DOI 10.1111/1540-6261.00463. [Publisher abstract](https://onlinelibrary.wiley.com/doi/abs/10.1111/1540-6261.00463). Equilibrium risk-premium motivation, not a current NEM calibration.

[S24] Bevin-McCrimmon, F., Diaz-Rainey, I. and Sise, G. Liquidity and Risk Premia in Electricity Futures. USAEE working paper 16-291, December 2016. [Author working-paper record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2885453). New Zealand evidence; abstract reviewed. The later 2018 journal article includes an expanded author list.

[S25] Heffernan, J. E. and Tawn, J. A. A conditional approach for multivariate extreme values. Journal of the Royal Statistical Society B 66, 497-546, 2004. [Research paper](https://www.d.umn.edu/~yqi/mydownload/heffemantawn.pdf). General conditional-tail methodology; transfer to NEM requires new estimation.

[S26] Meucci, A. Fully Flexible Views Theory and Practice. Published methodology originating in 2008; arXiv version 2010. [Author paper](https://arxiv.org/abs/1012.2848). Entropy pooling for scenario reweighting; proposed here as a market-calibration method.

### Data and implementation sources

[S27] AEMC. Improving transparency and extending duration of MT PASA, 2020. [Rule-change record](https://www.aemc.gov.au/rule-changes/improving-transparency-and-extending-duration-mt-pasa). Read alongside AEMO's table-specific process descriptions and effective updates.

[S28] AEMC. Schedule of reliability settings 2026-27 financial year. [Primary settings schedule](https://www.aemc.gov.au/media/105056). Indexed primary text verifies the $23,200/MWh cap; other settings must be loaded from the effective schedule.

[S29] AEMO. MMS Data Model IRAUCTION package. [Data-model documentation](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_162.htm). Table discovery; current schema version and public/private visibility require validation before ingestion.

[S30] AEMO. Quarterly Energy Dynamics. [Reports and workbooks](https://www.aemo.com.au/energy-systems/major-publications/quarterly-energy-dynamics-qed). Aggregate reconciliation and current structural context.

[S31] ASX Energy. Australian Electricity products and intraday trades API documentation. [Product information](https://www.asxenergy.com.au/products/au_electricity); [data interface](https://www.asxenergy.com.au/docs/api/intraday_trades). Product definitions and possible licensed ingestion route.

[S32] Gorman and colleagues. Nempy A Python package for modelling the Australian National Electricity Market dispatch procedure. Journal of Open Source Software 7(70), 3596, 2022. [Authors' repository](https://github.com/UNSW-CEEM/nempy). DOI 10.21105/joss.03596.

### Local evidence and reproducibility

[L01] New analysis for this report. analyse_history.py; historical_audit.json; historical_regional_decomposition.csv; historical_spread_decomposition.csv; historical_joint_regimes.csv; historical_flow_diagnostics.csv. The audit records price-source hashes, window, coverage and flags. The flow proxy is explicitly excluded from claims about actual SRA settlement.

[L02] Existing project documentation. docs/METHODS_AND_RESEARCH.md. Conditional-input experiments, data aggregation, flow targets and reported-limit interpretation. Reviewed as project evidence, not independently reproduced in this research task.

[L03] Existing project documentation. docs/QNI_VNI_EXPANDED_FORECAST_RESEARCH.md. Prior experiments, inspected evaluation periods and constraint reconstruction limitations. Used to avoid misrepresenting development evidence as a fresh holdout.

[L04] Existing project documentation. docs/PRODUCTION_PIPELINE_GUIDE.md. Offline scaffold, immutable packages and issue/receipt/delivery input contracts. Basis for the proposed integration plan.

### Sources added in version 2

[R1] Cambridge Economic Policy Associates for the AEMC. Settlements Residue Auction and Modified Load Export Cost processes, final report, 24 May 2024. [Report](https://www.aemc.gov.au/sites/default/files/2024-06/cepa_report_-_sra_and_mlec.pdf). Directional interconnector pooling; treatment of negative residue; SRA structure.

[R2] AEMO. MMS Data Model Report, DISPATCHPRICE table. [Data model](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_130.htm). APCFLAG bit definitions; RRP as the settlement price.

[R3] AEMO. Unit category data notices; MMS table AUCTION_IC_ALLOCATIONS. Maximum units and proportions per quarter and direction.

[R4] Stiewe, C. Arbitrage and rents in European long-term transmission rights. arXiv:2607.28790, July 2026. [Paper](https://arxiv.org/abs/2607.28790).

[R5] AEMO. Automation of Negative Residue Management (2021) and the consultation for transmission loops (2025). [Consultation](https://www.aemo.com.au/consultations/current-and-closed-consultations/automation-of-negative-residue-management-for-the-implementation-of-transmission-loops).

[R7] Handika, R. and Trück, S. Risk Premiums in Interconnected Australian Electricity Futures Markets. SSRN 2279945, 2013. [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2279945).

[R8] Flottmann, J. H., Wild, P. and Todorova, N. Derivatives and hedging practices in the Australian National Electricity Market. Energy Policy 189, 114114, 2024.

[R9] Marckhoff, J. and Wimschulte, J. Locational price spreads and the pricing of contracts for difference: evidence from the Nordic market. Energy Economics 31(2), 257–268, 2009.

[R10] Kristiansen, T. Pricing of Contracts for Difference in the Nordic market. Energy Policy 32(9), 1075–1085, 2004.

[R11] Leslie, G. Who benefits from ratepayer-funded auctions of transmission congestion contracts? Evidence from New York. Energy Economics, 2021. [Abstract](https://www.sciencedirect.com/science/article/abs/pii/S0140988320303650).

[R12] Opgrand, J., Preckel, P. V., Gotham, D. J. and Liu, A. L. Price formation in auctions for financial transmission rights. The Energy Journal 43(3), 2022.

[R13] Deng, S.-J., Oren, S. and Meliopoulos, A. P. The inherent inefficiency of simultaneously feasible financial transmission rights auctions. Energy Economics 32(4), 2010.

[R14] Adamson, S., Noe, T. and Parker, G. Efficiency of financial transmission rights markets in centrally coordinated periodic auctions. Energy Economics 32(4), 2010.

[R16] Joskow, P. and Tirole, J. Transmission rights and market power on electric power networks. RAND Journal of Economics 31(3), 450–487, 2000.

[R17] Margrabe, W. The value of an option to exchange one asset for another. Journal of Finance 33(1), 177–186, 1978.

[R18] Rockafellar, R. T. and Uryasev, S. Optimization of conditional value-at-risk. Journal of Risk 2(3), 21–41, 2000.

[R19] AEMC. Inter-regional settlements residue arrangements for transmission loops, rule determination ERC0386, 25 September 2025. [Determination](https://www.aemc.gov.au/sites/default/files/2025-09/Final%20determination-%20ERC0386.pdf). Net-trade method, secondary netting, loss treatment and worked examples used as tests.

[L05] Version 2 evidence. `nemic/valuation/*`, `evidence/*.csv` and `evidence/data_audit.json`: inputs, hashes, coverage and every computed table.

## Appendix A Formula reference

| Quantity | Definition |
|---|---|
| Quarterly average | $\bar X=\frac{1}{H}\sum_t\Delta t\,X_t$, with $H=\sum_t\Delta t$ |
| Energy and scarcity | $E=\min(P,K)$, $C=\max(P-K,0)$, $P=E+C$, $K=300$ |
| Frequency × severity | $\bar C=p\,m$, with $p=\Pr(P>K)$ and $m=\mathbb E[P-K\mid P>K]$ |
| State contribution | $\frac{1}{H}\sum_t\Delta t\,S_t\mathbf 1\{z_t=z\}$, which sums over $z$ to $\bar S$ |
| Loss / congestion | $S=(\lambda P_{\text{from}}-P_{\text{from}})+(P_{\text{to}}-\lambda P_{\text{from}})$ |
| Asset residue | $r=P_{\text{to}}(F-(1-s)L)-P_{\text{from}}(F+sL)$ per hour |
| Unit payoff (pre-loop) | $\theta_Q\sum_{t\in Q}\max\big(\sum_a r_{a,t},0\big)$ over intervals of net flow $A\to B$ |
| Auction ratio | $\rho=\sum_i n_i\,\text{payoff}_i\big/\sum_i n_i\,\text{price}_i$ |
| Hedge ratio | $n^{*}=\operatorname{Cov}(S_w,U_w)/\operatorname{Var}(U_w)$, variance removed $=\operatorname{Corr}^2$ |
| CVaR | $\operatorname{CVaR}_\alpha(\ell)=\min_c\{c+(1-\alpha)^{-1}\mathbb E(\ell-c)^{+}\}$ |
| Bachelier call | $\mathbb E[S^{+}]=\sigma\varphi(\mu/\sigma)+\mu\Phi(\mu/\sigma)$ |
| CRPS (ensemble) | $\frac1M\sum_i\lvert x_i-y\rvert-\frac{1}{2M^2}\sum_{i,j}\lvert x_i-x_j\rvert$ |
| Block bootstrap | $\bar S^{(b)}=\frac1D\sum_{d\in\mathcal B^{(b)}}\bar S_d$, with $\mathcal B^{(b)}$ contiguous 7-day blocks |
| Loop payout | $R^{\text{loop}}\max(\tilde a_k,0)/\sum_j\max(\tilde a_j,0)$ with $\tilde a_k=R^{\text{loop}}a_k/\sum_ja_j$ |

## Appendix B Research search and screening record

Search themes covered AEMO SRA rules and residue methodology; ASX base and cap specifications and interregional leg conventions; EnergyConnect loop settlement and Basslink conversion; NEM extreme-price mechanisms; structural coupled-market pricing; Australian joint spike and extremal-dependence models; electricity risk premia; conditional extremes; entropy pooling; MT PASA; and open-source NEM dispatch reconstruction.

Representative search strings included “settlement residue auction inter regional residues units negative residues”, “ASX inter-regional futures electricity”, “electricity price forecasting interregional dependence spikes Australia copula regime switching”, “electricity derivatives pricing forward-looking information”, “EnergyConnect settlements residue auction 2026”, “multivariate electricity price spikes”, “Bessembinder Lemmon equilibrium pricing electricity forward markets”, and “Heffernan Tawn conditional multivariate extreme values”. Searches were refined using the official AEMO, AEMC, ASX and AER sites and authors' repositories.

Sources were retained when they established a contract definition, documented an operational mechanism, supplied a directly relevant NEM model, or offered a transferable method with a stated limitation. Generic investment commentary, unsourced forecasts, secondary summaries where primary research was available, and obsolete rules presented without an effective date were not used as authority. Current consultation proposals were kept separate from final rules.

The research combined accessible full documents, official current pages, indexed primary text and publisher abstracts. It did not include expert interviews, proprietary trading models, subscription quote histories or an empirical reproduction of each academic paper. The proposed architecture and implementation sequence are the report's synthesis; published studies do not establish its future commercial performance.

## Appendix C Response to the review

Each item from `review.md` is listed below with the action taken and where it now appears.

| Review item | Action in version 2 | Where |
|---|---|---|
| C-01 no futures, auction history or realised payouts | Settled payoff ledger; every delivered tranche joined to realised payoff; hedge-equivalence against a futures-style spread. AER futures loader built but not observed (AER blocks automated access). | Ch. 6–8, N1–N12 |
| M-01 gated covariance | Ungated and gate-conditional covariance and Spearman correlation; the Exhibit 9 caption is corrected. | Ch. 9, Exhibit 9 |
| M-02 lossless, dispatch flow, single link | Pooled, loss-adjusted, settled residue; reconciliation to SETIRSURPLUS. | Ch. 6, N1 |
| M-03 counter-price flows | Negative residue ledger, forced-flow and NRM tagging. | Ch. 11, N17 |
| M-04 sample length | 19 complete quarters, TAS added. | Ch. 4, N13 |
| M-05 loss vs congestion | Exact 2×2 decomposition and loss curves. | Ch. 3, 10, N8–N9 |
| M-06 no uncertainty | Block bootstrap, leave-one-day-out, extremograms. | Ch. 4.2, 13, N14–N16 |
| M-07 market price cap regime | Rescaled to the FY2027 cap from MARKET_PRICE_THRESHOLDS. | Ch. 13, N21 |
| M-08 unit counts | Dated unit registry from AUCTION_IC_ALLOCATIONS. | Ch. 6, `sra_unit_registry.csv` |
| M-09 literature | Transmission-right auction, EPAD and NEM futures premium literature added. | Ch. 18.1, sources |
| M-10 loop unquantified | Net-trade rule implemented, tested on AEMC examples, applied to history. | Ch. 12, N20 |
| m-01 flag labels | APCFLAG bits decoded. | Ch. 4 |
| m-02 revisions caveat | PRICE_STATUS audited. | Ch. 4, `data_audit.json` |
| m-03 selective table | Full tables and heatmap. | Ch. 4, N13 |
| m-04 flow input hash, run selection | All input folders hashed; physical-run selection documented. | `data_audit.json`, `nemic.valuation.panel` |
| m-05 trivial identity check | Replaced by v1 regression, reconciliation and identity tests. | `tests/test_valuation_*.py` |
| m-06 figure without code | `make_figures.py` generates Figure 1. | `make_figures.py` |
| m-07 manifest hashes | Line-ending-normalised hashes. | `report_manifest.json` |
| m-08 workbench defaults | Aligned with the §27 worked example. | Workbench |
| m-09 $10 minimum clause | Not verified; the SRA Rules PDF blocks automated access and is listed for manual download. | `data/external/README.md` |
| m-10 implied hours from destination cap only | Cap-spread version added to the workbench. | Workbench |
