# Valuing interregional spreads and settlement residue units in the NEM

## Executive overview and analytical scope

This research report examines how interregional electricity price spreads and Settlements Residue Auction (SRA) units are valued, priced, and hedged in Australia's National Electricity Market (NEM). Version 3 supersedes the version 2 archive by reorganising the analysis in first-principles order, resolving legacy carry-overs from the initial September 2026 design note, and integrating nine new empirical studies built directly from the repository's five-minute market panel, settled residue ledgers, auction bid stacks, and constraint archives.

- **Market and time convention:** Australian National Electricity Market, aligned strictly to fixed NEM time (UTC+10) using interval-ending five-minute timestamps across all five mainland and Tasmanian regions.
- **Empirical window:** 517,248 five-minute intervals spanning October 2021 to June 2026 (19 complete calendar quarters from 2021 Q4 through 2026 Q2), capturing the entire post-five-minute-settlement era.
- **Units and sign convention:** Wholesale energy prices, regional spreads, and cap payouts are expressed in AUD per MWh; SRA clearing prices and realised distributions are expressed in AUD per unit per delivery quarter. A positive spread always indicates that the destination region settled at a higher price than the origin region.
- **Reproducibility guarantee:** Every statistic in this document is injected directly from the audited summary ledger at build time, with zero manually transcribed figures.

> [!TAKEAWAY] Core Empirical Conclusions for the Desk and Quant Team
> Across 1,332 delivered auction tranches, SRA holders received 1.51 times the clearing price on a units-sold-weighted basis (95% quarter-cluster interval 1.28 to 1.81), and that discount persists outside the 2022 energy crisis at 1.37 (1.20 to 1.55). Clearing prices nonetheless outperform simple historical rules out of sample, indicating a persistent risk, capital, and regime premium rather than participant ignorance. Against a 1 MW flat futures spread, hedge firmness varies sharply by corridor: northward VNI units hedge sub-$300 energy congestion reasonably well but fail during New South Wales scarcity, whereas northward QNI units retain firmness under stress. From November 2026 onward, the AEMC net-trade loop rule and the 2027 Q2 QNI unit expansion structurally reprice forward categories even before physical EnergyConnect dispatch changes take hold.

To serve both commercial trading review and quantitative system implementation without forcing either audience through irrelevant detours, the document is organised into four sequential parts plus three technical reference appendices:

1. Part I (Chapters 1 to 3): Physical and institutional settlement plumbing, covering contract definitions, exact price accounting, pre-loop asset pooling, and the November 2026 loop and Basslink regime breaks.
2. Part II (Chapters 4 to 6): Baseline empirical structure across nineteen complete quarters, including moving-block uncertainty, statutory cap and cumulative-price-threshold interactions, diurnal operating regimes, loss-versus-congestion shares, counter-price flows, and binding constraint attribution.
3. Part III (Chapters 7 to 9): Market valuation and hedging evidence, evaluating auction clearing prices, term-structure drift, credit-support carry, weekly and quarterly hedge replication, two-instrument SRA-plus-cap frontiers, walk-forward benchmarks, and an interactive desk workbench.
4. Part IV (Chapters 10 to 12): Complete implementation blueprint, documenting the five-layer system architecture, four-time-axis data contracts, an exhaustive paper-by-paper literature synthesis translated into modelling choices, explicit dual entropy-pooling mathematics, and validation acceptance gates.

## 1 Instruments, time semantics, and exact price accounting

Valuation in the National Electricity Market begins with contract mechanics rather than statistical price models. A regional base future, a $300 cap future, and a Settlements Residue Auction unit reference the same underlying five-minute regional reference prices, yet they map those prices into cashflows through fundamentally different mathematical operators. Treating an SRA unit as a leveraged proxy for an interregional futures spread, or treating a $300 cap spread as a direct measure of one-sided physical shortage, introduces systematic valuation error before any forecasting model is fitted.

### 1.1 The six questions a quarterly valuation framework must answer

For any ordered region pair, delivery quarter, and valuation date, a rigorous interregional valuation system must produce quantitative answers to six distinct questions:

1. What is the expected time-weighted regional price spread across the delivery quarter, and what is its full predictive distribution?
2. How much of that spread originates in the sub-$300 capped-energy component versus the excess above $300/MWh?
3. How frequently does only one region experience a high-price episode, how long do multi-interval episodes persist, and how severe is the conditional price excess?
4. What physical transfer flows, marginal losses, and contractual settlement allocations occur inside those exact same intervals?
5. Which changes in scarcity arrival, cross-regional dependence, or transmission availability are required to reconcile physical model expectations with observed futures, cap, and auction clearing prices?
6. Which combination of base futures, $300 caps, and directional SRA units best expresses a directional view or hedges a portfolio exposure once transaction slippage, funding carry, margin calls, and tail risk are accounted for?

Answering these six questions requires separating three concepts that are frequently conflated in electricity commentary. Generation adequacy refers to available local and deliverable supply relative to operational demand. Transfer capability refers to the feasible network movement of megawatts across transmission boundaries subject to thermal, voltage, and stability constraints. Scarcity value refers to the high-price premium embedded in regional clearing prices and captured directly by a $300 cap contract. An SRA unit is strictly a contractual entitlement to a defined fraction of allocated settlement residue; it does not confer physical firm transmission rights or guaranteed megawatt transfer during stress. Likewise, a spot price exceeding $300/MWh is a precise financial contract boundary rather than proof of physical involuntary load shedding, and prices below $300/MWh still embed substantial congestion rents and thermal opportunity costs.

Scope boundaries matter equally for prospective modelling. Initial implementation focuses on the Victoria to New South Wales corridor (VNI) and the Queensland to New South Wales corridor (QNI) in both directions, while ensuring that the southern scenario engine explicitly models South Australia and Project EnergyConnect. Because the November 2026 net-trade loop settlement rule pools residues jointly across New South Wales, Victoria, and South Australia, a standalone two-region VNI model cannot compute valid post-2026 payouts. Heywood, Murraylink, Terranora, and Basslink must therefore enter through effective-dated physical and contractual mappings rather than static historical interconnector identifiers.

### 1.2 Contract payoffs and exchange conventions

Let $A$ denote the origin region and $B$ denote the destination region. In every five-minute interval $t$, the signed spot price spread is defined as $S_t = P_{B,t} - P_{A,t}$, so a positive spread means the destination region settled at a higher price than the origin. A long interregional spread position is long the destination regional future and short the origin regional future for matched delivery hours and megawatt volume.

With five-minute interval duration $\Delta t = 1/12$ hour and quarterly delivery length $H = \sum_{t \in Q} \Delta t$ (2,160 hours for a 90-day quarter, 2,184 hours for a 91-day quarter, and 2,208 hours for a 92-day quarter), the quarterly regional settlement averages for base and $300 cap contracts are:

$$
\bar P_r = \frac{1}{H}\sum_{t \in Q} \Delta t \, P_{r,t}, \qquad
\bar C_r = \frac{1}{H}\sum_{t \in Q} \Delta t \, \max(P_{r,t} - K, 0), \qquad K = 300.
$$

For a flat $m$-megawatt long spread entered at forward spread $F_B - F_A$, terminal economic profit before funding, variation margin, and brokerage costs is linear in the time-weighted quarterly spread:

$$
\Pi^{\text{fut}} = m \, H \left[(\bar P_B - \bar P_A) - (F_B - F_A)\right].
$$

By contrast, a pre-loop directional SRA unit on corridor $A \to B$ with effective-dated unit proportion $\theta_Q$ pays a contractual fraction of the sum of interval-level positive residues:

$$
\Pi^{\text{SRA}} = \theta_Q \sum_{t \in Q} \max\left(R_t^{A \to B}, 0\right) - \text{clearing price} - \text{fees},
$$

where $R_t^{A \to B}$ is the settled inter-regional residue generated across the pooled regulated assets of that directional interconnector (derived formally in Chapter 2). The futures spread is linear in a time-weighted price difference; the SRA unit is a convex strip of positive parts applied to a flow-weighted, loss-adjusted price difference.

| Instrument | Economic exposure | Natural reporting unit | Payoff geometry |
|---|---|---|---|
| Regional base future | Quarterly arithmetic mean of five-minute regional spot price | AUD per MWh | Linear in regional price |
| Matched interregional futures legs | Difference between destination and origin quarterly means | AUD per MWh and AUD per MW-quarter | Linear two-sided spread |
| Regional $300 cap future | Quarterly mean positive excess of five-minute spot price above $300 | AUD per MWh | Convex call strip at $300 |
| Difference of regional caps | Difference between destination and origin scarcity payouts | AUD per MWh | Long destination call, short origin call |
| Base spread less cap spread | Difference between regional prices clipped above at $300 | AUD per MWh | Capped linear energy spread |
| Directional SRA unit | Contractual share of positive directional or loop-allocated residue | AUD per unit per quarter | Nonlinear flow-weighted call strip |

Exchange and settlement specifications require strict verification before execution. The ASX Australian Electricity Derivatives fact sheet (June 2025) defines one-megawatt base contracts settled on five-minute arithmetic averaging across all relevant intervals since October 2021, with cap payouts averaging positive excess above $300/MWh across every base interval in the quarter [S01]. ASX's listed interregional spread launch notice specifies that buying a displayed spread buys the second, dominant leg and sells the first, meaning screen labels cannot be read casually as left-minus-right subtraction; every executable order must be mapped explicitly into long and short regional legs and verified against current exchange and broker specifications [S02].

Equally critical is keeping three distinct averaging weights separate. A time-weighted quarterly base future averages prices equally across every five-minute interval. A retailer's customer exposure is load-weighted, multiplying regional prices by stochastic regional demand and introducing strong positive price-volume covariance that a flat 1 MW spread does not replicate. An SRA unit is flow-weighted and gated on transfer direction and loss allocation. Matching quarterly arithmetic means across these three quantities does not imply hedge equivalence.

> [!CONTEXT] Five-Minute Resolution vs. Half-Hour Averaging Convexity
> Because the cap payoff $\max(P - 300, 0)$ is convex, computing cap settlements on half-hour-averaged prices systematically understates actual five-minute settlement whenever prices cross $300 within a half-hour block. In New South Wales during 2024 Q4, five-minute settlement produced a $47.355/MWh cap payout compared with $46.505/MWh on half-hour averages, an understatement of $0.850/MWh or $1,878 per MW-quarter. All nonlinear cap, loss, and SRA residue calculations must therefore remain at native five-minute resolution until terminal quarterly aggregation.

### 1.3 Exact energy, scarcity, loss, and congestion accounting

Every regional five-minute spot price splits algebraically at the $300/MWh cap strike into a capped-energy price and a scarcity excess:

$$
E_{r,t} = \min(P_{r,t}, K), \qquad C_{r,t} = \max(P_{r,t} - K, 0), \qquad P_{r,t} = E_{r,t} + C_{r,t}.
$$

Subtracting origin region $A$ from destination region $B$ yields an exact additive spread identity that holds both in every five-minute interval and across quarterly averages by linearity of the arithmetic mean:

$$
S_t = \underbrace{(E_{B,t} - E_{A,t})}_{\text{capped energy spread}} + \underbrace{(C_{B,t} - C_{A,t})}_{\text{scarcity excess spread}}.
$$

Two subtle accounting conventions deserve precision. First, negative wholesale prices remain fully inside the capped-energy component $E_{r,t}$, and an interval clearing at exactly $300/MWh contributes zero to scarcity. Second, during a price spike, the first $300/MWh remains in $E_{r,t}$ while only the excess above $300/MWh enters $C_{r,t}$. This identity is mathematically distinct from averaging prices conditionally over sub-$300 intervals only, which alters the sample denominator whenever spike frequency shifts.

On the market side, matched base futures $F_r$ and $300 cap futures $G_r$ for identical delivery quarters and quote timestamps reproduce the exact same split:

$$
F_B - F_A = \underbrace{(F_B - G_B) - (F_A - G_A)}_{\text{market capped-energy spread}} + \underbrace{(G_B - G_A)}_{\text{market scarcity spread}}.
$$

To expose cross-regional coincidence, classify every interval into one of four mutually exclusive joint exceedance states $z_t \in \{\text{neither}, \text{destination only}, \text{origin only}, \text{both}\}$ depending on whether $P_{A,t}$ and $P_{B,t}$ exceed $K$. Dividing each state's summed spread by total quarter hours $H$ ensures exact additivity across states:

$$
\bar S = \sum_z \frac{1}{H}\sum_{t \in Q} \Delta t \, S_t \, \mathbf{1}\{z_t = z\} = \sum_z \Pr(z) \, \mathbb{E}[S \mid z].
$$

A second orthogonal split separates physical transmission losses from network congestion. Whenever an interconnector does not bind against an operational constraint, AEMO's dispatch engine couples regional prices through the interconnector's dynamic marginal loss factor $\lambda_t$, setting the importing region's price equal to $\lambda_t P_{\text{from},t}$. Defining the loss-coupled reference price $P_t^{*} = \lambda_t P_{\text{from},t}$ splits any signed spread exactly into a loss component and a congestion component:

$$
P_{\text{to},t} - P_{\text{from},t} = \underbrace{(P_t^{*} - P_{\text{from},t})}_{\text{loss component}} + \underbrace{(P_{\text{to},t} - P_t^{*})}_{\text{congestion component}}.
$$

Applying the $K = 300$ clipping operator to the three ordered prices $P_{\text{from},t}$, $P_t^{*}$, and $P_{\text{to},t}$ yields a four-cell $2 \times 2$ decomposition across energy versus scarcity and loss versus congestion:

$$
\text{energy loss} = \min(P_t^{*}, K) - \min(P_{\text{from},t}, K), \qquad
\text{energy congestion} = \min(P_{\text{to},t}, K) - \min(P_t^{*}, K),
$$

with scarcity loss and scarcity congestion defined as the exact remainders $(P_t^{*} - P_{\text{from},t}) - \text{energy loss}$ and $(P_{\text{to},t} - P_t^{*}) - \text{energy congestion}$. All four components sum to the realised five-minute and quarterly spread to machine precision.

> [!MECHANISM] Why the Loss-versus-Congestion Split Governs Relative Value
> A linear futures spread receives 100% of the loss-driven spread $(P_t^{*} - P_{\text{from},t})$ in every coupled interval. An SRA unit, however, earns settlement residue proportional to metered received energy minus exported energy. Under standard quadratic transmission losses $L = k F^2$, marginal losses equal twice average losses ($\lambda - 1 \approx 2 k F$), so in a coupled interval the settlement residue captures only the quadratic loss surplus $P L$, roughly half of the apparent flow-times-loss-spread product $F (P_t^{*} - P_{\text{from},t})$. Only when a network constraint binds and prices separate beyond $\lambda_t$ does the SRA capture the full congestion rent $F (P_{\text{to},t} - P_t^{*})$. Chapter 5 quantifies this structural wedge across all mainland links.

## 2 Physical flows, marginal losses, and the pre-loop settlement ledger

Between the regional reference price spread and the dollars deposited into an SRA holder's settlement account sits a chain of physical metering, quadratic loss allocation, asset pooling, and asymmetric sign rules. Traders who price SRA units by multiplying an expected regional spread by nominal transfer capacity skip four mechanical adjustments that collectively move per-unit payoffs by ten to twenty-five percent on major corridors and invert the sign of cashflows during counter-price events. Rebuilding the exact pre-loop ledger from five-minute telemetry establishes both the ground truth for empirical analysis and the settlement layer required for any forward simulation engine.

### 2.1 From Five-Minute Metered Energy to Asset Residue

In the National Electricity Market, interregional power transfers are not priced at a single border point. Energy leaves the exporting regional reference node at the origin regional reference price $P_{\text{from},t}$, incurs marginal transmission losses along the regulated corridor, and arrives at the importing regional reference node priced at the destination regional reference price $P_{\text{to},t}$. Under the pre-loop settlement methodology maintained by AEMO [S03], the settlement surplus generated on an individual regulated interconnector asset $a$ during five-minute interval $t$ depends on the metered energy flow $F_{a,t}^{\text{met}}$ (expressed in MW, converted to MWh via $\Delta t = 1/12$ hour), the marginal loss factor $\text{MLF}_{a,t}$, and the dated from-region loss share $s_{a,t}$:

$$r_{a,t} = \Delta t \cdot F_{a,t}^{\text{met}} \left[ P_{\text{to},t}\bigl(1 - (1 - s_{a,t})(\text{MLF}_{a,t} - 1)\bigr) - P_{\text{from},t}\bigl(1 + s_{a,t}(\text{MLF}_{a,t} - 1)\bigr) \right]$$

When $F_{a,t}^{\text{met}} > 0$ (power flows in the canonical asset direction from origin to destination) and $\text{MLF}_{a,t} > 1$, marginal losses cause the exporting region to inject more megawatts than the importing region receives, shrinking the settlement residue below the naive lossless quantity $\Delta t \cdot F_{a,t}^{\text{met}} (P_{\text{to},t} - P_{\text{from},t})$. Conversely, when power reverses ($F_{a,t}^{\text{met}} < 0$), the flow sign flips and the marginal loss factor drops below unity in the canonical convention, reversing which region absorbs the marginal loss wedge.

Two operational subtleties make the difference between an approximate research backcast and a bankable settlement calculation. First, AEMO settles interregional residues on metered energy flows rather than five-minute dispatch targets. Dispatch targets reflect the linear programme solution at the end of the interval, whereas metered flows integrate actual physical transfers across the full five minutes, including governor response, frequency control movements, and ramping trajectories. Second, the loss share parameter $s_{a,t}$ is effective-dated rather than constant across all interconnectors and years. Applying a fixed 0.50 loss share across the entire nineteen-quarter window introduces systematic drift whenever AEMO updates regional loss equations at financial-year boundaries.

Once five-minute asset residues are calculated, the pre-loop rules group individual physical assets into directional SRA pools rather than paying out asset by asset [S03, R1]:

- **Victoria to New South Wales (`VICNSW`) and reverse (`NSWVIC`):** Governed solely by the Victoria to New South Wales regulated interconnector (`VIC1-NSW1`), with northbound positive intervals feeding `VICNSW` and southbound positive intervals feeding `NSWVIC`.
- **Queensland to New South Wales (`QLDNSW`) and reverse (`NSWQLD`):** Pools the main Queensland to New South Wales interconnector (`NSW1-QLD1`) together with the regulated Terranora link (`N-Q-MNSP1`, formerly Directlink). Both assets contribute to the same directional residue bucket before unit allocation.
- **Victoria to South Australia (`VICSA`) and reverse (`SAVIC`):** Pools the Heywood AC interconnector (`V-SA`) together with the regulated Murraylink HVDC asset (`V-S-MNSP1`).

Within each directional pool, the sign rule introduces a hard one-sided option truncation at the five-minute interval level. When the pooled residue for a direction is positive, it accumulates into the distributable SRA pool for that quarter. When the pooled residue is negative, typically because a binding thermal or stability constraint forces power from a dearer region into a cheaper region, the negative amount is NOT charged back to SRA unit holders. Under pre-loop settlement rules, negative residues are recovered through transmission network service provider adjustments in the importing region, and AEMO's automated Negative Residue Management procedure begins clamping interconnector flow once accumulated negative residues reach $-\$100{,}000$ [R5, S14]. Only positive interval residues flow through to unit holders, scaled by each unit's effective-dated proportional entitlement $1 / U_{d,q}$ and net of auction fees.

### 2.2 Reconciling the Four-Step Settlement Waterfall

Measuring the exact magnitude of each simplification step requires comparing four progressively stricter reconstructions of total nineteen-quarter positive directional residue (`2021 Q4` to `2026 Q2`) against AEMO's published interregional settlement surplus ledger:

1. **Lossless dispatch proxy:** Multiplies positive five-minute dispatch flow by the raw regional price spread, ignoring marginal losses, metering differences, and loss-share splits.
2. **Loss-adjusted dispatch:** Introduces the full marginal loss equation and effective-dated loss shares while retaining five-minute dispatch targets.
3. **Loss-adjusted metered:** Replaces dispatch targets with metered energy flows while keeping the dated loss-share formula intact.
4. **AEMO settled surplus:** The authoritative settlement ledger published by AEMO after market clearing and metering reconciliation.

Across the four largest directional pools, the naive lossless dispatch proxy systematically overstates realised SRA cashflows (Exhibit 2.1). Over the nineteen complete quarters, ignoring marginal losses inflates reconstructed positive residue by 10% on `VICNSW`, 7% on `QLDNSW`, 14% on `VICSA`, and 25% on `NSWQLD`. Because marginal loss factors rise quadratically with flow, the lossless bias is steepest precisely during heavy transfer periods when a desk expects its SRA units to generate the largest cashflows.

Adding the dated marginal loss equation closes almost the entire gap, and switching from dispatch targets to metered flows brings the reconstruction into tight operational agreement with AEMO's settled ledger on the three primary corridors:

| Directional pool | 19-quarter settled positive residue | Lossless proxy error vs. settled | Loss-adjusted dispatch vs. settled | Loss-adjusted metered vs. settled | 19-quarter mean payoff per unit | 19-quarter median payoff per unit |
|---|---:|---:|---:|---:|---:|---:|
| `VICNSW` | \$730.9m | +10% | -5.4% | 0.0% | \$25,642 | \$21,897 |
| `QLDNSW` | \$643.5m | +7% | -2.8% | -1.5% | \$28,222 | \$23,915 |
| `VICSA` | \$374.8m | +14% | 0.5% | 2.9% | \$22,418 | \$18,757 |
| `NSWQLD` | \$127.5m | +25% | 1.5% | 6.1% | \$12,201 | \$10,915 |
| `NSWVIC` | \$93.5m | n/a | n/a | n/a | \$3,787 | \$1,788 |
| `SAVIC` | \$91.6m | n/a | n/a | n/a | \$6,263 | \$5,255 |

At the individual interconnector level, metered reconstruction reconciles to 0.03% on northbound VNI, -0.09% on southbound QNI (`QLD` into `NSW`), and 2.9% on westbound Heywood (`VIC` into `SA`). The one glaring historical outlier is northbound QNI (`NSW` into `QLD`), where the asset-level metered proxy exceeds AEMO's settled interconnector surplus by 42% over the nineteen-quarter aggregate, even though the pooled `NSWQLD` directional total reconciles to within 6.1% once Terranora and directional sign rules are aggregated.

> [!NOTE]
> **Diagnostic Audit: Why Asset-Level Northbound QNI Overstates Settled Surplus During Crisis Quarters**
> Isolating the asset-level gap on northbound QNI (`NSW1-QLD1`, importing into Queensland) across every quarter reveals that the 42% cumulative overstatement is heavily concentrated in the 2022 energy crisis rather than steady-state accounting error. During `2022 Q1`, `2022 Q2`, and `2022 Q3`, when administered pricing, market suspension, and extreme northbound congestion dominated Queensland settlement, the asset-level formula overstated settled surplus by 63%, 185%, and 111% respectively, contributing $33.2 million of the cumulative discrepancy. Across the five most recent quarters (`2025 Q2` to `2026 Q2`), the asset-level metered discrepancy compressed to between 3.3% and 9.7%. Neither sub-50 MW near-zero transfers (0.6% of computed value) nor five-minute sign flips between dispatch and metered flow (0.8%) explain the main-line crisis wedge. By contrast, on the small parallel Terranora link (`N-Q-MNSP1`, \$5.1m settled total), small flows below 50 MW account for 45% to 92% of computed positive intervals, making Terranora uniquely sensitive to metering noise and loss-factor rounding. Because AEMO's published settled surplus captures all crisis-period clamping, intervention pricing, and administered settlement adjustments directly, all historical revenue, hedging, and auction-premium analytics in this study anchor strictly to AEMO-settled payouts rather than asset-level approximations.

### 2.3 Realised Per-Unit Payoffs and Dispersion Across Nineteen Quarters

Dividing quarterly settled pools by each quarter's effective-dated maximum unit count produces the exact realised dollar payout per SRA unit across all six mainland auction directions. Across the nineteen complete quarters, unit counts are not static: AEMO adjusts maximum unit allocations by category and quarter via formal unit-category notices [S05, R3], with 56 historical category-quarter rows requiring fallback to the nearest effective-dated allocation where older notices were unavailable in the public archive.

Realised per-unit payouts exhibit pronounced right-skewness and multi-fold quarter-to-quarter regime swings (Exhibit 2.2). On `QLDNSW`, mean quarterly payoff reaches \$28,222 per unit (median \$23,915), ranging from \$1,949 in `2022 Q1` up to \$85,873 in `2024 Q2` and $76,576 in `2025 Q2` when New South Wales winter price spikes met sustained southward exports from Queensland. On `VICNSW`, payoffs are markedly more stable in percentage terms: the mean is \$25,642 and median \$21,897, spanning a floor of \$10,623 (`2024 Q2`) to a peak of \$60,577 (`2022 Q2`). `VICSA` combines a moderate median (\$18,757) with sharp upside bursts, peaking at \$64,479 in `2026 Q1` during South Australian heatwave separation.

The minor reverse directions tell an equally instructive story for portfolio construction. `NSWVIC` averages \$3,787 per unit with a median of only \$1,788, yet surged to \$15,078 in `2024 Q1` during the February 2024 Victorian transmission-tower collapse and Loy Yang A trip. `SAVIC` averages \$6,263 per unit (median \$5,255), surging to \$15,957 in `2024 Q3`. Meanwhile, cumulative nineteen-quarter negative residues reached −\$255.4m across the mainland, with −\$169.8m concentrated on `NSWVIC` alone, confirming that pre-loop negative-residue protection is not an obscure edge case but a dominant feature of southbound Victoria-New South Wales settlement.

### 2.4 Decomposing Realised SRA Payoffs: Coupled Losses, Energy Congestion, and Scarcity

Chapter 1 proved that a linear futures spread decomposes cleanly into clipped energy below $300/MWh and scarcity cap payouts above $300/MWh. An SRA unit, however, is a flow-weighted physical settlement claim, not a linear spread swap. To understand what a desk actually owns when it buys a unit on each corridor, every five-minute interval of realised positive SRA payoff must be split into three mutually exclusive economic drivers that sum identically to the realised per-unit payout:

1. **Coupled-network loss surplus:** Positive residue earned when the interconnector is unconstrained (zero binding congestion rent) and the price difference reflects purely marginal transmission losses between regional reference nodes.
2. **Sub-$300 energy congestion:** Positive residue earned during constrained intervals where neither regional reference price exceeds $300/MWh, capturing chronic thermal, voltage, and stability congestion during normal dispatch.
3. **Scarcity regime residue (above $300/MWh):** Positive residue earned in intervals where at least one regional reference price exceeds $300/MWh, further auditable by whether only the destination spikes, only the origin spikes, or both regions spike simultaneously.

This three-way SRA payoff decomposition uncovers the sharpest structural divide in the Australian interregional market (Exhibit 2.3). Not all SRA units are scarcity instruments, and treating them as homogeneous congestion options leads directly to hedging failure.

| Direction | Mean settled payoff ($/unit) | Coupled loss surplus ($/unit, %) | Sub-$300 energy congestion ($/unit, %) | Scarcity >$300 regime ($/unit, %) | Fixed-flow clipped energy ($/unit) | Fixed-flow scarcity increment ($/unit) | Primary economic identity |
|---|---:|---:|---:|---:|---:|---:|---|
| `VICNSW` | \$25,642 | \$1,737 (7%) | \$20,584 (80%) | \$3,321 (13%) | \$22,938 | \$2,712 | Chronic sub-$300 energy corridor |
| `QLDNSW` | \$28,222 | \$2,644 (9%) | \$11,189 (40%) | \$14,389 (51%) | \$14,128 | \$13,669 | Hybrid energy + NSW scarcity option |
| `VICSA` | \$22,418 | \$1,647 (7%) | \$7,808 (35%) | \$12,964 (58%) | \$11,069 | \$12,002 | Scarcity-dominated SA tail option |
| `NSWQLD` | \$12,201 | \$520 (4%) | \$5,198 (43%) | \$6,483 (53%) | \$6,677 | \$6,264 | Summer evening QLD scarcity option |
| `SAVIC` | \$6,263 | \$522 (8%) | \$4,685 (75%) | \$1,056 (17%) | \$5,349 | \$991 | Midday solar surplus export link |
| `NSWVIC` | \$3,787 | \$239 (6%) | \$2,348 (62%) | \$1,200 (32%) | \$2,822 | \$1,136 | Contingent backup + shock tail |

On `VICNSW`, **80%** of realised per-unit cashflow (\$20,584 out of \$25,642) comes from routine sub-$300 energy congestion, supplemented by 7% (\$1,737) from coupled marginal loss surplus. Only 13% (\$3,321) derives from intervals above $300/MWh, and almost all of that scarcity share occurred in just two anomalous quarters (`2022 Q2` at $28,007/unit and `2024 Q4` at $10,824/unit). In `2025 Q3`, `2025 Q4`, `2026 Q1`, and `2026 Q2`, scarcity contributed less than 4% of `VICNSW` unit value (zero in `2026 Q2`). By contrast, on `VICSA` (58%), `NSWQLD` (53%), and `QLDNSW` (51%), more than half of realised per-unit dollars are earned during >$300/MWh scarcity regimes.

The fixed-flow counterfactual columns confirm the same economic split from a second angle: holding actual metered five-minute flows fixed and capping regional prices at $300/MWh preserves \$22,938 per unit on `VICNSW` (leaving only \$2,712 of scarcity increment), whereas on `QLDNSW` and `VICSA` capping prices at $300/MWh destroys half of unit value. This single table previews the entire hedging conclusion of Part III: `VICNSW` units behave primarily as a flow-weighted sub-$300 energy spread instrument that requires paired destination caps to hedge scarcity, whereas `QLDNSW` and `VICSA` units carry genuine embedded scarcity convexity.

### 2.5 Execution Cashflow Mechanics, Credit Support, and Revision Timing

Turning a theoretical per-unit valuation into a trading desk P&L forecast requires tracking the exact operational cashflow timeline governed by AEMO's Settlements Residue Auction Rules [S04]:

1. **Auction commitment and credit exposure (Up to 36 months pre-delivery):** AEMO conducts quarterly auctions up to twelve quarters ahead of delivery, selling each quarter's directional units across twelve tranches (Tranches 1 through 12). Winning a tranche creates an immediate binding contractual commitment to pay the auction clearing price, backed by participant credit support and prudential margining across the entire pre-delivery holding period. Across the nineteen-quarter sample, the median lag from auction date to cash settlement is **538 days** overall and **911 days** on nine-to-twelve-quarter forward tranches.
2. **Purchase-price instalment timing:** Unlike exchange futures settled daily via variation margin, SRA auction purchase obligations are invoiced in the settlement cycle preceding or entering delivery, producing a short median gap of **49 days** between direct cash outflow and weekly residue receipt. Valuation models must therefore distinguish between funded cash working capital (approximately seven weeks) and balance-sheet credit-support carry (up to 2.5 years on distant tranches).
3. **Weekly distribution and settlement revisions:** During the delivery quarter, AEMO distributes accrued positive directional residues weekly alongside standard NEM settlement statements. Initial preliminary and final statements (roughly four weeks after each billing week) are subsequently subject to 20-week and 30-week metering and settlement revisions, as well as deduction of AEMO's auction administrative fee and minimum distribution thresholds [S04, S10].
4. **No negative cash calls, but real prudential friction:** Although unit holders never pay into negative-residue intervals, capital remains encumbered by AEMO prudential guarantees until purchase obligations settle, and any cross-hedge held in ASX base or cap futures incurs daily mark-to-market variation margin. A desk comparing an SRA unit against an equivalent ASX spread position must price this funding asymmetry explicitly before declaring a valuation edge.

## 3 Loop settlement, unit dilution, and regulated Basslink

Every settled dollar analysed in Chapter 2 was generated on an open-tree mainland network where Victoria sat as a radial junction between New South Wales and South Australia. Between October 2026 and June 2028, three simultaneous structural regime breaks rewrite the mapping from physical flows to SRA unit cashflows: the closure of the NSW-Victoria-South Australia transmission loop via Project EnergyConnect, the expansion of maximum QNI unit counts in `2027 Q2`, and the transition of Basslink from a market network service provider to a regulated interconnector carrying auctioned `VICTAS` and `TASVIC` units. A valuation framework calibrated naively to 2021–2026 unit payoffs will systematically misprice post-2026 auctions on all three fronts.

### 3.1 Project EnergyConnect and the AEMC Net-Trade Loop Rules

Project EnergyConnect creates a direct 330 kV transmission link between Robertstown in South Australia and Wagga Wagga in New South Wales, closing the mainland southern transmission ring (`NSW1–VIC1–SA1–NSW1`). Once a transmission loop closes, Kirchhoff's laws allow power scheduled between any two regions to split across parallel physical paths. Under the legacy single-asset settlement methodology, parallel loop flows create a severe accounting distortion: power moving from South Australia to New South Wales can flow physically through Victoria, generating positive settlement residue on `SAVIC` and `VICNSW` while simultaneously generating negative residue on the direct `SANSW` arm if regional prices do not align monotonically around the ring.

To eliminate cross-subsidies and whole-loop negative-residue distortions, the Australian Energy Market Commission's final determination `ERC0386` (25 September 2025) replaces asset-by-asset pooling on the southern triangle with a net-trade loop settlement regime [S06, R19]. AEMO's Project EnergyConnect Market Integration schedule fixes 1 October 2026 as the dispatch representation effective date and 1 November 2026 as the settlement effective date for loop residue allocation, accompanied by whole-loop negative residue management [S07, S08, S09].

The loop calculation executes in four deterministic steps during every five-minute interval $t$ across the three southern loop regions (`NSW1`, `VIC1`, `SA1`):

1. Arm-level residue and net loop pool: Compute the standard loss-adjusted settlement residue on each of the three triangle arms (`VIC1-NSW1`, `V-SA` plus `V-S-MNSP1`, and the new `NSW1-SA1` EnergyConnect arm). Sum all three signed arm residues to obtain the total net loop residue $R_{\text{loop},t}$. If $R_{\text{loop},t} \le 0$, no positive residue is distributed to any loop SRA category; the net deficit is recovered through importing-region network charges under whole-loop negative residue management.
2. Net regional trade balance: Calculate each loop region's net export position across the two arms connected to it. When one region acts purely as a pass-through conduit (for example, importing 400 MW from South Australia and simultaneously exporting 400 MW into New South Wales), its net regional trade is zero. Under the new rule, only regions with nonzero net exports and nonzero net imports generate notional directional trade allocations.
3. Provisional directional split: Assign notional interregional trade strictly from net exporting regions to net importing regions, weight each notional trade by its regional price spread, and scale the provisional allocations proportionally so they sum identically to the positive net loop residue $R_{\text{loop},t}$.
4. Secondary netting across loop arms: If any provisional directional allocation is negative (for instance, because a net exporter exports into a lower-priced net importer on one leg while the triangle as a whole remains net positive), that negative provisional amount is deducted proportionally from the positive provisional allocations on the remaining loop arms rather than funded by network customers. SRA unit holders still never face a negative cash call, but positive loop arms absorb the internal cross-arm deficit before distribution.

This four-step algorithm is implemented and verified bit-for-bit against AEMC `ERC0386` Figure 3.1 and Appendix B Example 4 inside the repository's settlement test suite.

### 3.2 Three-Way Attribution Waterfall: Where the Legacy Pool Goes

Applying the verified AEMC loop algorithm directly to the nineteen historical quarters (`2021 Q4` to `2026 Q2`) while holding historical prices and flows fixed (zero physical EnergyConnect transfer) isolates the pure accounting-rule shock before any physical dispatch response occurs. Separating the transition from status-quo payouts into three sequential accounting stages shows exactly which mechanism drives the repricing of existing units:

- Stage 1 (Negative-residue netting across arms): Netting simultaneous negative arms inside the loop against positive arms before distribution, rather than charging negative arms separately to networks.
- Stage 2 (Pass-through reallocation): Stripping pass-through volume out of `VICNSW`, `NSWVIC`, `VICSA`, and `SAVIC` and crediting it directly to the two new `NSWSA` and `SANSW` categories whenever Victoria sits in the middle of a `SA ↔ NSW` transfer.
- Stage 3 (Secondary netting): Absorbing residual negative provisional allocations inside positive loop arms.

Holding historical dispatch fixed, pass-through reallocation accounts for the overwhelming majority of the redistribution (Exhibit 3.1 and Exhibit 3.2). Across the nineteen quarters, Victoria acted as a pass-through region in 46% of all five-minute intervals, secondary netting triggered in 20% of intervals, and the whole loop finished net-negative in 12% of intervals.

| Loop category | Status quo 19q total | Stage 1: Neg. arm netting | Stage 2: Pass-through reallocation | Stage 3: Secondary netting | Post-loop 19q total | Aggregate change | Quarterly haircut range (min / med / max) | Status quo $/unit | Post-loop $/unit |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `VICNSW` | \$730.9m | −\$9.1m | −\$164.7m | −\$1.1m | \$556.0m | -24% | -35% / -24% / -11% | \$25,642 | \$19,506 |
| `NSWVIC` | \$93.5m | −\$2.5m | −\$32.9m | \$1.5m | \$59.6m | -36% | -76% / -42% / -8% | \$3,787 | \$2,413 |
| `VICSA` | \$374.8m | −\$4.9m | −\$70.9m | \$0.7m | \$299.7m | -20% | -61% / -18% / -7% | \$22,415 | \$17,924 |
| `SAVIC` | \$91.7m | −\$4.7m | −\$48.6m | \$0.2m | \$38.7m | -58% | -82% / -63% / -17% | \$6,266 | \$2,645 |
| `NSWSA` | \$0.0m | \$0.0m | \$98.2m | \$0.1m | \$98.3m | New pool | n/a | \$0 | \$6,469 |
| `SANSW` | \$0.0m | \$0.0m | \$218.9m | −\$1.4m | \$217.5m | New pool | n/a | \$0 | \$14,310 |

The table exposes three critical valuation consequences for trading desks:

1. **Legacy unit haircuts are large and quarter-dependent:** Even before EnergyConnect carries a single megawatt of physical power, the accounting rule cuts `VICNSW` by -24% in aggregate (reducing mean per-unit value from \$25,642 to \$19,506), with individual quarterly haircuts ranging from -11% to -35%. `VICSA` drops -20% (ranging -7% to -61%), `NSWVIC` drops -36%, and `SAVIC` suffers a severe -58% collapse (up to -82% in quarters dominated by South Australian solar transit through Victoria toward New South Wales).
2. **Pass-through reallocation creates a $315.8m synthetic pool on day one:** Reallocating pass-through flows creates \$315.8m of combined nineteen-quarter residue for the two new EnergyConnect categories (`SANSW` at \$217.5m and `NSWSA` at \$98.3m, equivalent to \$14,310 and \$6,469 per unit at an illustrative 800-unit baseline). Negative-arm netting (`−$21.2m` across all four legacy links) and secondary netting (`$0.0m` net across the ring, shifting small amounts across arms) are second-order compared with pass-through reallocation (`$317.1m` shifted out of the four Victorian arms into `NSWSA`/`SANSW`).
3. **Post-loop hedge firmness degrades on legacy Victorian links:** Stripping pass-through volume out of `VICNSW` and `VICSA` weakens their linear correlation with regional spreads. As detailed in Chapter 8, post-loop weekly variance explained falls from `20%` to 14% on `VICNSW` (with stress-period MW equivalent dropping from `0.15` to 0.11 MW per unit) and from `58%` to 48% on `VICSA`. Meanwhile, the synthetic `NSWSA` and `SANSW` categories start at just 14% and 14% weekly $R^2$ under fixed dispatch because their notional pool activates only when Victoria is in pass-through state rather than continuously.

### 3.3 Parametric EnergyConnect Transfer and Spread-Compression Sensitivities

The fixed-dispatch counterfactual above intentionally holds physical EnergyConnect flow at zero (`0 MW`) and regional prices unchanged. In live operation, EnergyConnect ramps first through its Stage 1 commissioning release (approximately `150 MW` transfer capability) toward its full Stage 2 rated capacity (`800 MW` nominal transfer capability). Adding physical parallel transfer between South Australia and New South Wales pulls in two opposing directions: higher physical megawatts transferred across the `NSW1–SA1` border expand the gross loop residue pool, while relieving south-to-north congestion simultaneously compresses regional price spreads across `SA1`, `VIC1`, and `NSW1`.

Because a full security-constrained economic dispatch counterfactual requires a nodal network model (built in Stage 3 of the Chapter 12 roadmap), a transparent parametric stress grid bounds the valuation envelope across EnergyConnect transfer capability (`0 MW`, `150 MW`, `800 MW`, dispatched proportionally to the signed `NSW − SA` spread) crossed with uniform loop spread compression (`0%` and `20%`):

| Parametric PEC scenario | `VICNSW` 19q total | `VICSA` 19q total | `NSWSA` 19q total | `SANSW` 19q total | Economic interpretation |
|---|---:|---:|---:|---:|---|
| Status quo (pre-loop baseline) | \$730.9m | \$374.8m | \$0.0m | \$0.0m | Historical open-tree settlement |
| 0 MW PEC, 0% compression (pure rule) | \$556.0m | \$299.7m | \$98.3m | \$217.5m | Pure accounting pass-through shift |
| 150 MW PEC, 0% compression | \$609.2m | \$387.7m | \$191.7m | \$399.4m | Stage 1 physical flow without price relief |
| 150 MW PEC, 20% spread compression | \$566.5m | \$349.8m | \$152.8m | \$322.5m | Stage 1 with realistic congestion relief |
| 800 MW PEC, 0% compression (upper bound) | \$638.8m | \$546.9m | \$798.5m | \$1,508.6m | Non-equilibrium capacity upper bound |
| 800 MW PEC, 20% spread compression | \$571.0m | \$485.3m | \$625.1m | \$1,189.8m | Stage 2 with moderate spread compression |

Two structural insights emerge immediately from the parametric grid. First, even at `150 MW` of direct transfer with `20%` spread compression, `VICNSW` remains deeply impaired (\$566.5m versus \$730.9m status quo, a `−22%` reduction), showing that Stage 1 physical relief does not bail out legacy `VICNSW` unit holders. Second, under full `800 MW` transfer, the gross `SANSW` and `NSWSA` pools expand dramatically, **only** if spreads do not collapse faster than flow grows; under `40%` spread compression at `800 MW`, `VICNSW` drops further to `$504.8m` and `SANSW` falls from `$1,508.6m` to `$872.0m`. Desks bidding on post-November 2026 `NSWSA`, `SANSW`, `VICNSW`, and `VICSA` tranches should treat the `0 MW` pure-rule figure as a lower structural bound for EnergyConnect categories and the `800 MW / 0%` column strictly as an unachievable upper ceiling until Stage 3 dispatch simulations quantify actual congestion relief.

### 3.4 Live Catalyst 1: 2027 Q2 QNI Unit-Count Dilution

Loop settlement is not the only structural discontinuity embedded in the live 2026–2028 auction forward curve. Effective **`2027 Q2`**, AEMO's revised unit-category schedule increases maximum auctioned unit counts on the Queensland-New South Wales interconnector to reflect QNI Minor upgrade transfer capacity [S05, R3]:

- **`NSWQLD` (northbound into Queensland):** Maximum units increase from **550 units** to **750 units** (+36.4% more units sharing the same directional pool), imposing a pure mechanical per-unit dilution of **-26.7%** holding total residue fixed.
- **`QLDNSW` (southbound into New South Wales):** Maximum units increase from **1,200 units** to **1,300 units** (+8.3% more units), imposing a mechanical per-unit dilution of **-7.7%**.

Cross-checking AEMO's live forward auction clearing prices before and after the `2027 Q2` boundary tests whether market participants have already priced this dilution into the forward strip or left a structural mispricing on the table:

| QNI direction | Pre-`2027 Q2` max units | Post-`2027 Q2` max units | Mechanical dilution | Mean price (`2026 Q2–2027 Q1`) | Mean price (`2027 Q2+`) | Same-season Q2 check (`2026 Q2` vs. `2027–28 Q2`) |
|---|---:|---:|---:|---:|---:|---:|
| `NSWQLD` | 550 | 750 | -26.7% | \$7,981 | \$6,051 | $4,569 vs. $3,408 (−25.4%) |
| `QLDNSW` | 1,200 | 1,300 | -7.7% | \$25,997 | \$24,929 | $32,196 vs. $30,042 (−6.7%) |

The live market pricing check delivers a remarkably clean verdict. Comparing identical Q2 autumn delivery quarters across the step change removes seasonal confounding: `NSWQLD` clearing prices step down by `−25.4%` (`$4,569` in `2026 Q2` to `$3,408` across `2027 Q2` and `2028 Q2`) against a `−26.7%` mechanical dilution, while `QLDNSW` steps down by `−6.7%` (`$32,196` to `$30,042`) against a `−7.7%` mechanical dilution. Market participants have already priced the denominator expansion almost to the percentage point. Consequently, any valuation model that feeds historical `2021–2026` per-unit QNI payoffs directly into a `2027 Q2+` forecast without rescaling by the effective-dated unit denominator ($U_{d,q}^{\text{hist}} / U_{d,q}^{\text{target}}$) will generate a spurious `+36%` apparent buy signal on `NSWQLD` and `+8%` on `QLDNSW` that is pure denominator error.

### 3.5 Live Catalyst 2: Regulated Basslink Pro-Forma Backcast

On 30 April 2026, AEMO finalised expedited rules introducing two brand-new regulated SRA categories across Bass Strait: **`VICTAS`** (southbound from Victoria into Tasmania) and **`TASVIC`** (northbound from Tasmania into Victoria), each structured around a 500-unit nominal allocation, with initial forward tranches appearing in the June 2026 auction report [S10, S11]. Because Basslink operated as an unregulated market network service provider (`MNSP`) throughout the `2021 Q4–2026 Q2` historical window, AEMO's settled SRA ledger records **$0** of historical SRA distributions for `VICTAS` and `TASVIC` (\$0.0m and \$0.0m).

To give trading desks a disciplined empirical anchor for early Basslink auctions without pretending that historical MNSP behaviour equals future regulated dispatch, we construct a **pro-forma regulated Basslink backcast** across all nineteen complete quarters using actual five-minute `T-V-MNSP1` dispatch and metered flows, dated Basslink marginal loss equations, and a 500-unit allocation:

| Pro-forma Basslink direction (500 units) | 19-quarter pro-forma positive residue | Mean quarterly value ($/unit) | Median quarterly value ($/unit) | Peak quarter ($/unit) | Trough quarter ($/unit) |
|---|---:|---:|---:|---:|---:|
| `VICTAS` (VIC → TAS) | \$344.4m | \$36,257 | \$33,018 | $102,299 (`2025 Q1`) | $9,445 (`2022 Q2`) |
| `TASVIC` (TAS → VIC) | \$200.7m | \$21,123 | \$14,052 | $61,764 (`2023 Q2`) | $1,537 (`2026 Q1`) |

> [!WARNING]
> **Critical Caveat: MNSP Bidding Behaviour Versus Regulated Free-Flow Dispatch**
> The pro-forma Basslink numbers above (\$36,257 mean on `VICTAS` and \$21,123 mean on `TASVIC`) are an **indicative historical scale check, not a direct regulated forecast**. Under MNSP operation, Basslink bid strategically into NEMDE to maximise its own merchant arbitrage revenue, deliberately withholding capacity during low-spread or negative-residue hours and keeping counter-price losses near zero. Once converted to a regulated interconnector, Basslink dispatches automatically down to zero marginal spread subject to thermal and dynamic cable limits, which will simultaneously increase flow volume during moderate-spread hours (raising gross transfer energy), tighten regional price convergence between Victoria and Tasmania (compressing spreads), and expose the link to occasional counter-price negative residues subject to NRM clamping. Treat the pro-forma backcast strictly as a starting diagnostic while calibrating explicit regulated dispatch elasticity in Stage 3.

## 4 Empirical baseline, statistical fragility, CPT truncation, and diurnal regimes

An interregional valuation model is only as honest as the historical telemetry it rests upon. Short sample windows in the Australian National Electricity Market create a classic trap: two or three calm quarters make regional spreads look mean-reverting and Gaussian, while a single heatwave or coal-unit trip flips a corridor's quarterly sign overnight. Before decomposing physical loss and constraint mechanisms, we establish the full nineteen-quarter five-minute empirical baseline (`2021 Q4` to `2026 Q2`), audit statutory price flags, measure finite-sample fragility, evaluate the interaction between rising market price caps and the cumulative price threshold, and map exactly when during the 24-hour solar-and-ramp cycle SRA dollars are actually earned.

### 4.1 Nineteen Quarters of Five-Minute Telemetry and Price-Flag Audit

The core evidence panel spans 19 complete delivery quarters from 2021 Q4 through 2026 Q2, encompassing 517,248 five-minute dispatch intervals across all five NEM regions (`NSW1`, `QLD1`, `SA1`, `VIC1`, `TAS1`). Every interval in the nineteen complete quarters carries firm settlement status (0 non-firm rows). To eliminate the ambiguity created by conflating administered pricing, market price caps, and interregional loss-factor scaling, every five-minute price record is audited using AEMO's explicit bit-mask specification [R2]:

- Administered Price Cap (`APC`) binding: 1,883 region-intervals, concentrated primarily in the June 2022 eastern-states energy crisis.
- Market Price Cap (`MPC`) binding: 1,589 region-intervals where regional dispatch hit the statutory ceiling in effect for that financial year (`$15,100/MWh` in FY2022 rising in annual steps to `$20,300/MWh` in FY2026 and `$23,200/MWh` in FY2027 [S28]).
- Interregional loss-factor (`IRLF`) adjustment flags: 5,201 region-intervals recording active interregional scaling under extreme price-cap or floor conditions.
- Market suspension pricing (June 2022): 13,524 region-intervals. Sensitivity testing confirms that excluding versus retaining market-suspension pricing alters quarterly mean spreads by at most $5.59/MWh in `2022 Q2` and leaves all other eighteen quarters completely unaffected.

Across the nineteen complete quarters, the four canonical signed regional price spreads exhibit sharply distinct averages, dispersion, and range reversals:

| Canonical regional pair | 19-quarter mean spread ($/MWh) | Quarterly SD ($/MWh) | Minimum quarter ($/MWh) | Maximum quarter ($/MWh) | Structural directional bias |
|---|---:|---:|---:|---:|---|
| `NSW − VIC` | $39.01 | $20.50 | $12.92 (`2025Q3`) | $97.75 (`2024Q4`) | Persistent NSW premium in all 19 quarters |
| `QLD − NSW` | $-3.37 | $28.79 | $-72.53 (`2024Q2`) | $62.42 (`2022Q1`) | Structural regime flip: QLD dearer in 2022, NSW dearer in 2024–2026 |
| `SA − VIC` | $20.19 | $17.30 | $-0.08 (`2025Q4`) | $53.60 (`2024Q3`) | Persistent SA premium except flat `2025 Q4` |
| `VIC − TAS` | $-14.04 | $20.76 | $-52.21 (`2025Q1`) | $24.56 (`2023Q2`) | Hydro-driven swings; TAS dearer on average in 2024–2026 |

The interactive Historical Explorer below allows direct inspection of every quarter's exact additive split into clipped energy below $300/MWh and scarcity excess above $300/MWh, the four joint exceedance states, single-region scarcity concentration, and the consolidated nineteen-quarter cross-link heatmap (defaulting to the flagship `VIC → NSW` corridor).

Two headline patterns stand out immediately inside the Explorer. First, **`NSW − VIC` is the only mainland pair that stayed strictly positive across all nineteen consecutive quarters** (floor `$12.92/MWh` in `2025Q3`, ceiling `$97.75/MWh` in `2024Q4`), underpinned by chronic Victorian brown-coal and renewable surplus exporting into higher-cost New South Wales thermal marginal units. Second, **`QLD − NSW` inverted completely across the five-year sample**: Queensland traded sharply above New South Wales during `2021 Q4–2022 Q2` (peaking at `+$62.42/MWh` in `2022Q1`), before surging Queensland rooftop and utility solar combined with New South Wales coal retirements (Liddell) and winter scarcity pushed New South Wales sharply above Queensland (`$-72.53/MWh` in `2024Q2` and `−$39.80/MWh` in `2025 Q2`). Any static long-run mean model applied to `QLD − NSW` averages two opposite physical regimes into a meaningless near-zero number (`$-3.37/MWh`).

### 4.2 Finite-Sample Fragility, Day-Level Concentration, and Tail Persistence

Because electricity prices exhibit multi-day serial correlation driven by weather fronts and generator outages, standard independent-interval confidence intervals severely understate estimation error on quarterly means. Moving-block bootstrap resampling using **seven-day contiguous blocks** (preserving synoptic weather and outage persistence) reveals just how noisy realised quarterly means truly are.

Across all seventy-six pair-quarters, the median 95% moving-block bootstrap confidence interval width on a realised quarterly spread is $26.89/MWh (Exhibit 4.1). On high-scarcity quarters such as `QLD − NSW` in `2024 Q2` or `SA − VIC` in `2026 Q1`, uncertainty intervals stretch beyond `$80/MWh`. A leave-one-day-out fragility test sharpens the warning (Exhibit 4.2): removing a single calendar day flips the algebraic sign of the entire quarterly average spread in 3 of 76 pair-quarters. In the sharpest example, `SA − VIC` in `2025Q4` recorded a realised quarterly spread of `$-0.08/MWh`, yet removing a single day drives the quarter down to `$-1.14/MWh`. In the Regional Explorer above, `80%` to `100%` of quarterly `$300` cap payout regularly concentrates inside just five calendar days. Valuation models that evaluate point errors without modelling discrete multi-day scarcity clusters will mistake single-day luck for structural alpha.

Tail clustering operates not only within one region over consecutive hours, but across interconnected regions simultaneously. Computing empirical cross-regional extremograms at the $300/MWh threshold confirms strong lag-0 contemporaneous co-exceedance between electrically adjacent pairs (`NSW1` and `QLD1`, `VIC1` and `SA1`) alongside a pronounced 24-hour diurnal echo at lag +288 five-minute intervals (Exhibit 4.3, consistent with Han, Cribben, and Truck [S19]). Because multi-day heatwaves and low-wind doldrums sweep eastward across South Australia, Victoria, and New South Wales over 24 to 72 hours, Stage 2 scenario generators in Part IV must sample multi-day spatially coherent weather blocks rather than independent daily draws.

### 4.3 Statutory Regime Shifts: FY2027 Market Price Cap and Cumulative Price Threshold

Between FY2022 and FY2027, the AEMC Reliability Panel increased the NEM Market Price Cap from `$15,100/MWh` to \$23,200/MWh (`+53.6%`), while simultaneously raising the seven-day rolling Cumulative Price Threshold (`CPT`, summed over 2,016 five-minute intervals) from `$1,359,100` to \$2,225,900 (`+63.8%`) and doubling the Administered Price Cap (`APC`) from `$300/MWh` to \$600/MWh [S28]. Valuing FY2027+ contracts from 2021–2026 history requires adjusting historical at-cap intervals to the new statutory rules without introducing upward bias from unconstrained linear rescaling.

Testing both linear MPC rescaling and full sequential rolling seven-day CPT truncation across all nineteen historical quarters yields two nuanced empirical results (Exhibit 4.4):

1. **Material scarcity uplift under FY2027 MPC:** Rescaling historical at-cap dispatch intervals proportionally to the \$23,200/MWh FY2027 ceiling lifts realised quarterly scarcity spreads by up to $9.06/MWh (`QLD − NSW` in `2022 Q1`, rising from `$45.69/MWh` raw to `$54.75/MWh` rescaled), with `+4.73/MWh` uplift on `NSW − VIC` in `2024 Q4` (`$47.21` to `$51.94/MWh`) and `+4.03/MWh` in `2024 Q2`. Failing to normalise historical cap intervals biases trailing scarcity estimates systematically downward against FY2027+ contracts.
2. **Why zero additional historical CPT breaches trigger, and why forward simulation still needs an explicit CPT gate:** On the rescaled nineteen-quarter history, applying the FY2027 rolling 2,016-interval CPT of \$2,225,900 triggers 0 additional capped intervals in NSW, 0 in QLD, and 0 in SA (`0.00 $/MWh` max trim). The mechanical reason is subtle and essential: the one genuine multi-day crisis in the historical sample (June 2022) was *already* truncated in real time at the old `$300/MWh` APC once regions crossed the much lower FY2022 CPT (`$1,359,100`), so historical June 2022 prices contain `$300` administered rows rather than uncapped spikes. Outside June 2022, because the FY2027 CPT rose `63.8%` alongside the MPC, no other historical week accumulated enough at-cap intervals to cross \$2,225,900.

For forward simulation (Part IV), however, omitting the CPT gate remains a dangerous mistake. At \$23,200/MWh, a region breaches the \$2,225,900 seven-day CPT after just 96 five-minute intervals at cap (`$2,225,900 / $23,200 = 95.9` intervals, or 8.0 cumulative hours within any rolling seven-day window). Once breached, prices drop from `$23,200/MWh` down to the \$600/MWh APC for the remainder of the administered price period. Any Monte Carlo generator that draws heavy-tailed severity clusters without an explicit rolling 2,016-interval CPT circuit breaker will produce physically impossible $300 cap valuations on tail paths.

### 4.4 Diurnal Operating Regimes and Negative-Price Loss Inversion

Quarterly averages conceal *when* during the 24-hour dispatch cycle interregional cashflows actually accrue. Partitioning all `517,248` five-minute intervals into three operationally distinct Australian grid regimes (Solar Midday `09:00–15:00` NEM time, Evening Ramp `16:00–21:00`, and Overnight and Shoulder `22:00–08:00`) reveals that different SRA corridors are effectively bets on completely different parts of the daily load-and-solar curve.

| SRA direction | Solar Midday (`09:00–15:00`) residue share | Evening Ramp (`16:00–21:00`) residue share | Overnight & Shoulder (`22:00–08:00`) residue share | Dominant physical driver |
|---|---:|---:|---:|---|
| `VICNSW` | 18% | 26% | 56% | Persistent overnight coal/wind export + evening thermal spread |
| `QLDNSW` | 42% | 38% | 20% | Midday QLD solar surplus exported south + winter evening NSW peaks |
| `VICSA` | 14% | 43% | 44% | Evening/overnight SA gas dependence when wind and solar drop |
| `NSWQLD` | 19% | 57% | 23% | Summer evening QLD air-conditioning ramps (57% of total pool) |
| `NSWVIC` | 57% | 13% | 30% | Midday solar export reversals and occasional daytime outages |
| `SAVIC` | 59% | 24% | 17% | Midday SA solar saturation pushing negative-priced power east |

The diurnal profile carries immediate practical implications for hedging and fundamental forecasting (Exhibit 4.5). Over 56% of `VICNSW` positive residue accrues overnight and in early shoulder hours (`22:00–08:00`), whereas 59% of `SAVIC` and 57% of `NSWVIC` accrue strictly during midday solar hours (`09:00–15:00`), and 57% of `NSWQLD` accrues during the five-hour evening ramp (`16:00–21:00`). Forecasting a single daily-average spread misses the structural divergence between midday solar-curtailment spreads and evening firming spreads.

A second physical mechanism makes midday solar intervals mathematically distinct in the NEM settlement formula: **negative-price loss-factor inversion**. Under the coupled-network pricing relation $P_{\text{to}} = P_{\text{from}} \cdot \text{MLF}$, the marginal loss wedge equals $P_{\text{from}}(\text{MLF} - 1)$. Whenever $P_{\text{from}} > 0$ and power flows north on VNI ($\text{MLF} > 1$), losses add a positive price wedge (`\$5.66/MWh` mean across non-negative Victorian intervals). When Victorian rooftop and utility solar drive $P_{\text{VIC}} < 0$, however, multiplying a negative origin price by $(\text{MLF} - 1) > 0$ inverts the sign of the loss term (`−\$2.98/MWh` mean across negative Victorian intervals, flipping sign in 85.0% of negative-origin intervals). Even more strikingly, because Victorian negative prices occur precisely when Victorian surplus pushes hard against northbound VNI limits (`20.6%` of all complete-quarter intervals, rising to `64.2%` of Spring Solar Midday intervals), the average `NSW − VIC` spread during negative Victorian intervals jumps to \$86.31/MWh and generates 34.0% of total nineteen-quarter `VICNSW` settled residue. On `QLD − NSW`, negative origin intervals occur in 7.3% of intervals and generate 12.4% of residue (mean spread \$16.55/MWh, loss term flipping from −\$2.82 to \$1.11/MWh). Any lognormal model or non-negative price transformation breaks on the exact midday intervals that generate a third of Victoria-to-New South Wales SRA revenue.

## 5 Loss-driven versus congestion-driven spreads and flow–spread dependence

Separating ordinary transmission losses from binding network congestion, and measuring how interconnector transfer behaves as regional price spreads widen, exposes two structural wedges that govern relative value between futures spreads and SRA units. The first wedge is physical and predictable: losses scale quadratically with flow and invert sign when exporting regions clear below zero. The second wedge is operational and asymmetric: flow and spread move together during ordinary hours but diverge sharply during destination scarcity on constrained links.

### 5.1 Separating transmission losses from binding congestion

In every five-minute interval where an interconnector clears strictly inside its export and import limits, AEMO's dispatch engine couples the importing region's price to the exporting region's price through the link's marginal loss factor $\lambda_t$. Defining the coupled reference price $P_t^{*} = \lambda_t P_{\text{from},t}$ splits the signed spread cleanly into a loss term $(P_t^{*} - P_{\text{from},t})$ and a congestion term $(P_{\text{to},t} - P_t^{*})$, each of which splits further at the $300/MWh strike into capped energy and scarcity (Chapter 1.3).

Across the nineteen complete quarters from October 2021 to June 2026, mainland interconnectors sat coupled at their marginal loss factor in half to nearly two-thirds of all five-minute intervals:

| Corridor (destination minus origin) | Mean loss part (AUD/MWh) | Mean congestion part (AUD/MWh) | Coupled intervals at loss factor | Largest quarterly loss share |
|---|---:|---:|---:|---:|
| NSW minus VIC | 3.88 | 35.13 | 49% | 29% |
| QLD minus NSW | -2.53 | -0.84 | 65% | 65% |
| SA minus VIC | 2.81 | 17.38 | 61% | 92% |

Although the average loss component appears modest relative to total congestion across multi-year horizons, it can dominate quiet quarters: losses accounted for up to 29% of the absolute spread components on New South Wales minus Victoria, 65% on Queensland minus New South Wales, and 92% on South Australia minus Victoria. Basslink is reported in aggregate spread tables but excluded from loss-versus-congestion attribution because, operating as a market network service provider until July 2026, it cleared on its own commercial offers rather than sitting passively at its inter-regional marginal loss factor (0% coupled).

Because marginal loss factors are smooth, increasing functions of physical transfer (alongside regional demand terms specified in AEMO's annual loss-factor equations), the loss component is the most structurally forecastable element of an interregional spread. It scales directly with both transfer flow and the underlying wholesale price level.

> [!MECHANISM] Structural Wedge Between Futures and SRA Units on Losses
> A linear interregional futures spread receives 100% of the loss spread $P_{\text{from},t}(\lambda_t - 1)$ across every coupled interval. An SRA unit receives only the metered quadratic loss surplus $P_t L_t$. Because quadratic transmission losses $L = k F^2$ imply marginal losses $\lambda - 1 \approx 2 k F$ equal to twice average losses, an SRA captures only about half of the loss spread in coupled intervals while capturing the full congestion rent $F_t (P_{\text{to},t} - P_t^{*})$ whenever constraints bind. In quiet, heavily coupled quarters, futures spreads therefore earn a structural loss premium that SRA units do not replicate.

### 5.2 Negative-price regimes and loss-sign inversion

Daytime rooftop and utility-scale solar generation has made negative regional reference prices a permanent structural feature of the NEM. When an exporting region clears below zero while the importing region stays positive, regional spreads widen sharply inside the sub-$300 capped-energy bucket with zero $300 cap payout, and marginal transmission losses invert sign.

| Corridor | Origin below $0 share | Mean spread when origin below $0 | Mean loss term when origin below $0 | Mean loss term when origin non-negative | Share of forward SRA residue earned while origin below $0 |
|---|---:|---:|---:|---:|---:|
| NSW minus VIC | 20.6% | \$86.31/MWh | −\$2.98/MWh | \$5.66/MWh | 34.0% |
| QLD minus NSW | 7.3% | \$16.55/MWh | \$1.11/MWh | −\$2.82/MWh | 12.4% |
| SA minus VIC | 20.6% | \$-0.05/MWh | \$2.11/MWh | \$2.98/MWh | 5.9% |

Victoria cleared below $0/MWh in 20.6% of all five-minute intervals across the nineteen-quarter window. During those negative Victorian intervals, the New South Wales minus Victoria spread averaged \$86.31/MWh, generating 34.0% of all settled northward VNI residue across the entire five-year sample. Simultaneously, the marginal loss term $P_{\text{from},t}(\lambda_t - 1)$ inverted from an average of \$5.66/MWh when Victoria was non-negative to −\$2.98/MWh when Victoria was negative. Physically, pushing power across a lossy line out of a negatively priced region consumes excess zero- or negative-cost generation in line losses, reducing the price gap required to couple the two nodes rather than widening it. Valuation models that treat the loss spread as a fixed positive markup misprice daytime solar-export quarters systematically.

### 5.3 Why expected flow and expected spread cannot be multiplied mechanically

For a directional transfer $F^{+} = \max(F, 0)$ and positive price spread $S^{+} = \max(S, 0)$, the gross lossless revenue expectation decomposes as:

$$
\mathbb{E}[F^{+} S^{+}] = \mathbb{E}[F^{+}] \, \mathbb{E}[S^{+}] + \operatorname{Cov}(F^{+}, S^{+}).
$$

Conditioning on direction, loss treatment, and allocation gates introduces further state dependence, while quarterly net average flows frequently conceal large bidirectional diurnal swings. Three distinct physical regimes illustrate why average flow and average spread cannot be multiplied to estimate SRA value:

1. **Unconstrained arbitrage:** With spare transfer headroom, increased flow displaces dearer generation in the importing region and compresses price separation toward the marginal loss band.
2. **High-flow binding congestion:** When an import limit binds at high physical throughput while destination demand is tight, elevated flows and wide price spreads coexist, generating peak SRA unit payouts.
3. **Outage or stability contraction:** When a transmission outage, voltage constraint, or transient-stability equation cuts transfer capability sharply during destination scarcity, regional price spreads can surge to the market price cap while transferable megawatts collapse. This third state pays a linear futures spread in full while starving a flow-linked SRA unit of volume.

A subtle statistical pitfall must be avoided when measuring this covariance. Version 1 computed its independence benchmark using a flow variable already gated by the positive-spread indicator $\mathbf{1}\{S > 0\}$. Sharing that indicator between flow and spread injects a mechanical positive bias even if flow and spread were statistically independent:

$$
\operatorname{Cov}\left(F \mathbf{1}\{S > 0\}, \, S^{+}\right) = \operatorname{Cov}(F^{+}, S^{+}) + \mathbb{E}[F^{+}] \, \mathbb{E}[S^{+}] \frac{1 - \Pr(S > 0)}{\Pr(S > 0)}.
$$

Correcting that benchmark to ungated positive flow on the original two-year window lowers northward VNI's apparent covariance from $883/hour to $239/hour, and conditional on a positive spread the covariance turns sharply negative at $-4,172/hour. Across the full nineteen-quarter window, northward VNI displays a positive conditional Spearman rank correlation of 0.28 alongside a deeply negative conditional linear covariance of $-3,454/hour. Ordinary intervals exhibit positive co-movement as rising New South Wales demand draws Victorian exports, whereas extreme New South Wales scarcity intervals experience flow contraction that drives linear covariance negative. On northward QNI, by contrast, the conditional Spearman correlation reaches 0.61 and flow expands under New South Wales scarcity.

### 5.4 Non-monotone capacity responses and dispatch limits

Even in a simplified two-region network, expanding interconnector transfer capability does not raise SRA residue monotonically. Additional transfer megawatts let lower-cost generation displace peak local offers, shrinking the price spread and lowering scarcity arrival probabilities; the volume gain can be more than offset by spread compression. Prospective valuation sensitivities must therefore evaluate full capacity-response curves rather than assuming that a 10% limit increase raises SRA value by 10%.

Equally important, AEMO's reported dispatch import and export limits are endogenous outputs of solved dispatch equations in which other generators and parallel interconnectors appear on the left-hand side [S12, L02]. Treating each reported directional limit as an independent physical pipe capacity can construct physically impossible multi-region states. Meaningful valuation sensitivities specify a concrete physical perturbation, such as a 100 MW shift in an identified constraint right-hand side, one additional day of a named transmission outage, a battery endurance reduction, or a wind-output shock, and state explicitly whether dispatch was re-optimised, offers held fixed, topology modified, or only a conditional statistical distribution perturbed.

## 6 Counter-price flows, binding constraints, outage plans, and physical triggers

Regional price spreads and SRA payouts do not emerge from abstract stochastic noise; they arise from identifiable combinations of network security constraints, thermal plant outages, renewable output ramps, battery energy depletion, and dispatch rules governing negative settlement residues. Tracing how those physical triggers propagate through dispatch clearing into contract cashflows is essential both for evaluating the November 2026 loop regime and for designing the Stage 2 and Stage 3 valuation models of Part IV.

### 6.1 Counter-price flows and forced negative residue

Pre-loop, a negative inter-regional residue arises whenever power flows from a higher-priced region toward a lower-priced region. Across all six mainland directional interconnectors over nineteen complete quarters, settled negative residue totalled −\$255.4m. Crucially, 91% of that counter-price total occurred while the interconnector was physically forced by a binding security equation: a negative export limit pushing flow in reverse or a positive import limit forcing forward transfer toward the cheaper node.

New South Wales to Victoria alone generated −\$171.0m of settled negative residue, overwhelmingly driven by emergency and security constraints during New South Wales scarcity events:

- 99% of New South Wales to Victoria negative residue occurred under forced southward flow (a negative northward export ceiling on VNI);
- 48% occurred while New South Wales prices exceeded $300/MWh;
- automated negative-residue management (NRM) was active across 7,497 five-minute intervals in the post-August 2024 period for which public activation flags exist.

Under pre-loop rules, negative residues never reduce SRA unit payouts directly because they are recovered weekly from the importing region's transmission network service provider (NER 3.6.5(a)(4)) [R1]. Under AEMO's pre-loop NRM automation, clamping triggers on an individual link once accumulated negative residue reaches -$100,000 [R5, S14]. From November 2026 onward, however, whole-loop settlement nets negative arm allocations directly against positive loop arms before unit distribution, and automated loop NRM clamps only when the net loop residue itself turns negative [S09, R5]. Forced southward flows during New South Wales spikes therefore shift from a transmission-network cost recovery item into a direct payout drag on Victoria-connected SRA holders. Historical individual-link clamping patterns documented in practitioner analyses [S14] cannot be extrapolated mechanically into the post-EnergyConnect loop regime.

### 6.2 Which constraints drive regional price separation

Attributing the congestion component of each five-minute spread ($P_{\text{to},t} - \lambda_t P_{\text{from},t}$) to the binding constraint equation reported as setting the interconnector limit reveals which physical limits actually generate interregional value. Using AEMO's standard constraint-naming convention (thermal, voltage stability, transient stability, and system-normal versus outage equations; exact identifier rules in Appendix B), congestion on New South Wales minus Victoria averages:

- **Transient stability equations:** $13.67/MWh;
- **Thermal equations:** $10.50/MWh;
- **Voltage stability equations:** $9.67/MWh;
- **Network state split:** $16.21/MWh from system-normal equations versus $17.49/MWh from outage and abnormal-network equations.

Beneath the family aggregates, a compact set of recurring named equations accounts for a disproportionate share of multi-year congestion value across each mainland corridor:

| Corridor | Leading recurring limit-setting equations (19-quarter mean contribution) | Dominant family and state |
|---|---|---|
| NSW minus VIC | Top voltage-stability normal equations (`V^^N_NIL_1` at $3.83/MWh across 28,556 intervals; `N^^N_NIL_3` at $3.82/MWh) alongside transient outage equations (`N::N_CTYS_2` at $2.77/MWh) and thermal normal equations (`N>>NIL_970_051` at $2.15/MWh) | Mixed system-normal voltage/thermal plus high-impact transient outage sets |
| QLD minus NSW | Voltage outage equation (`N^^Q_LS_VC_B1` at $3.64/MWh across 4,015 intervals) offset by southward thermal normal limits (`N>>NIL_964_84_S` at -$2.80/MWh) and northward thermal limits (`N>>NIL_33_34` at $2.27/MWh) | Bidirectional thermal normal plus Queensland voltage outage constraints |
| SA minus VIC | Transient outage equation (`V::S_SETB_TBSE_2` at $3.42/MWh across 4,831 intervals) alongside Heywood dynamic transfer limits (`VS_600_TEST` at $2.65/MWh, `VS_050_DYN` at $2.09/MWh) | Outage-driven transient stability and Heywood dynamic operational limits |

*(Note: exact constraint identifiers in the summary table above are retained as proper AEMO equation names to support direct cross-reference against the repository's network-outage constraint studies; full naming-heuristic definitions sit in Appendix B.)* Because naming conventions are a heuristic classification rather than a full left-hand-side coefficient decomposition, equation-level sensitivity modelling should reference the repository's dedicated constraint-coefficient studies alongside this attribution.

### 6.3 Pre-auction outage plans as an information signal

Because SRA tranches are auctioned prior to delivery while transmission network service providers submit planned outage schedules months in advance, planned outage hours known before the auction constitute a testable ex-ante information signal. Counting only outage-to-constraint-set hours timestamped strictly prior to each delivery quarter's Tranche 12 notification date (from 2023 Q1 onward, spanning 15 quarters where outage-to-set mappings exist) yields positive rank correlations with the realised share of separated intervals across all three mainland corridors:

| Corridor | Spearman correlation (pre-auction set hours vs. realised separation share) | Quarters observed |
|---|---:|---:|
| NSW minus VIC | 0.35 | 15 |
| QLD minus NSW | 0.38 | 15 |
| SA minus VIC | 0.60 | 15 |
| VIC minus TAS | -0.54 | 15 |

Positive mainland correlations (reaching 0.60 on South Australia minus Victoria, where planned Heywood outage sets tighten transfer directly) indicate that pre-auction network outage plans carry genuine forward information. With only 15 quarterly observations, however, this relationship is suggestive rather than definitive; as Chapter 9 confirms, translating raw outage hours into a linear dollar adjustment without controlling for weather and scarcity regime noise still underperforms clearing prices out of sample.

### 6.4 Exploratory offer-curve steepness diagnostic (scoped four-day pilot)

Economic theory predicts that binding import constraints can alter local generator offer behaviour by isolating importing-region residual demand from external competition [R16]. To test whether public offer stacks exhibit steeper local supply curves when imports bind, an exploratory pilot examined energy offer bands across the highest-separation days per importing region, measuring the price rise required to dispatch an additional 200 MW above the cleared regional stack.

> [!RISK] Strict Scope Boundary on the Exploratory Offer-Curve Pilot
> Four of the six targeted archive months lacked public bid-per-offer files during automated extraction (leaving zero Queensland coverage and only 4 calendar days in total: two days in New South Wales in November 2024 and two days in South Australia in January 2026, totalling 1,152 five-minute intervals). Results are therefore reported strictly as a narrow diagnostic rather than a generalisable empirical finding.

Across those four calendar days, median offer-stack steepness pointed in opposite directions across the two observed regions (NSW: \$0.19 per MW with imports binding (325 intervals) against \$0.52 otherwise (251 intervals); SA: \$0.56 per MW with imports binding (299 intervals) against \$0.08 otherwise (277 intervals)). Measuring local offer slope alone does not identify strategic intent, and a full market-power study would require multi-year offer coverage, rebid timing forensics, and portfolio contract positions.

### 6.5 Compound physical triggers, accessible supply margin, and dual attribution ledgers

Individual grid stresses rarely produce extreme spreads in isolation. A coal unit trip during mild Spring demand with strong wind behaves entirely differently from the identical outage during a hot evening with low wind, a binding import constraint, and depleted battery storage. Prospective valuation must model triggers as compound states, separating the arrival probability of a trigger combination from the conditional severity of price separation given that trigger.

| Physical trigger mechanism | Ex-ante observable information | Transmission pathway into spread and SRA value |
|---|---|---|
| High residual demand | Joint weather, demand, rooftop solar, and VRE scenarios | Moves regional clearing onto steep thermal and gas-peaker offer bands and lifts import demand |
| Thermal outages or derating | Issue-dated availability submissions, outage notices, ambient heat | Shrinks local accessible supply; price impact depends on replacement plant and import headroom |
| Transmission outage or security constraint | Published outage plans, generic constraint sets, credible contingencies | Caps imports, triggers separation beyond losses, or alters loop net-trade allocation |
| Multi-region wind drought | Spatial weather ensembles and low-wind duration | Erodes geographic diversity across mainland regions and elevates simultaneous scarcity risk |
| Evening solar ramp | Sunset timing, temperature persistence, thermal ramp limits | Creates sharp short-duration flexibility premiums during 16:00–21:00 intervals |
| Battery and hydro depletion | Sequential state-of-charge tracking, MWh capacity, efficiency | Suppresses early peak hours but allows sustained high prices once storage energy exhausts |
| Midday renewable surplus | High available solar/wind, low operational demand, minimum synchronous load | Drives negative regional prices, export congestion, and loss-sign inversion inside capped energy |
| Offer and rebid shifts | Historical offer bands, fuel costs, water/gas opportunity costs | Steepens effective supply curves even when physical megawatt availability is unchanged |
| FCAS and system security | Co-optimised energy-FCAS availability and local inertia rules | Constrains generator energy headroom and alters interconnector limits |
| Statutory interventions and price caps | Effective market price cap, rolling 7-day CPT, administered caps | Truncates multi-day extreme tails and governs suspension pricing |

Direct forensic evidence from the AER's Q2 2026 significant-price reports confirms how South Australian scarcity episodes combined cold-driven demand, multi-hour wind lulls, cascading battery state-of-charge depletion, network limits, and rebidding [S13]. Such regulator incident reports are invaluable for building falsifiable mechanism hypotheses, though they remain selected extreme case studies rather than unbiased frequency samples.

To operationalise compound triggers in Stage 2 and Stage 3 models, construct an explicit **accessible supply margin** per region combining locally deliverable thermal generation, available renewable output (distinct from curtailed dispatch), feasible battery discharge bounded by remaining megawatt-hour endurance, demand response, and jointly feasible imports, minus operational demand (avoiding double-counting rooftop solar already netted out of operational demand). Tracking both megawatt headroom and megawatt-hour endurance prevents treating a 500 MW battery with 20 minutes of charge remaining as sustained multi-hour cover.

Finally, maintain strict discipline between predictive screening and causal attribution by keeping two separate ledgers:

- **Event ledger (predictive):** Records overlapping physical conditions (such as low wind plus coal outage plus binding VNI transient constraint) alongside sample counts, confidence intervals, lead times, and strict verification that every predictor was knowable at issue time.
- **Value ledger (causal):** Assigns dollar contributions via declared dispatch counterfactuals (rerunning clearing with one physical mechanism altered, or using Shapley allocations across paired scenarios with an explicit residual) so identical spread dollars are never triple-counted across correlated causes. Unresolved episodes should be stored openly rather than forced into ad-hoc explanations.

## 7 SRA auction clearing prices, term premia, convergence, and execution slippage

Having established how physical flows and settlement rules generate SRA unit cashflows, this chapter tests what market participants actually paid for those entitlements across every public auction since October 2021. Joining all 1,332 delivered auction tranches to their exact AEMO-settled quarterly payoffs answers four commercial questions: whether SRA units cleared at a systematic discount, whether that discount survives outside the 2022 energy crisis, how much of the apparent return is absorbed by multi-year credit-support carry, and how much clearing-price slippage a desk incurs when bidding for size.

### 7.1 Realised payoffs against clearing prices across 1,332 tranches

For any set of delivered tranches $\mathcal{T}$ with units sold $n_i$, the units-sold value-weighted realised-to-price ratio is:

$$
\rho(\mathcal{T}) = \frac{\sum_{i \in \mathcal{T}} n_i \, \text{payoff}_i}{\sum_{i \in \mathcal{T}} n_i \, \text{price}_i}.
$$

Because all twelve tranches of a given delivery quarter share one realised outcome, 95% confidence intervals are computed by quarter-cluster bootstrapping (2,000 replicates resampling complete delivery quarters rather than individual tranches).

Across all 1,332 delivered tranches spanning October 2021 to June 2026, SRA buyers received 1.51 times their purchase price (95% interval 1.28 to 1.81), with realised payoffs exceeding clearing prices in 63% of tranches and a mean undiscounted premium of \$5,815 per unit. Total public auction proceeds were \$1,366.5m against \$2,068.1m distributed to unit holders, meaning consumers (via transmission network tuition offsets) captured 66% of the residue value sold.

### 7.2 Separating structural risk premia from the 2022 crisis shock

A critical challenge to any historical auction-premium study spanning 2021–2026 is sample contamination from the 2022 Australian energy crisis, when tranches auctioned in 2020 and 2021 settled into unprecedented coal outages, global fuel spikes, and the June 2022 market suspension. Re-estimating the value-weighted ratio across four explicit sub-samples separates crisis windfalls from persistent market structure:

| Sample window | Quarters | Tranches | Value-weighted realised ÷ price | 95% quarter-cluster CI |
|---|---:|---:|---:|---|
| Full window (2021 Q4 to 2026 Q2) | 19 | 1,332 | 1.51 | 1.28–1.81 |
| Excluding 2022 crisis (drops 2022 Q2 and Q3) | 17 | 1,194 | 1.37 | 1.20–1.55 |
| Early window (2021 Q4 to 2023 Q4) | 9 | 612 | 1.79 | 1.32–2.46 |
| Recent window (2024 Q1 to 2026 Q2) | 10 | 720 | 1.35 | 1.12–1.60 |

Removing 2022 Q2 and 2022 Q3 lowers the aggregate realised-to-price ratio from 1.51 to 1.37, yet the 95% confidence interval (1.20 to 1.55) remains strictly above 1.0, and the recent ten-quarter post-2024 window stays virtually identical at 1.35 (1.12 to 1.60). The horizon gradient also survives cleanly outside the 2022 crisis, rising from 1.18 (1.01–1.39) one to two quarters ahead to 1.68 (1.40–2.05) nine to twelve quarters ahead.

| Direction | Full 19-quarter ratio | 95% CI (full) | Time to delivery | Full-window ratio | Ex-2022 ratio |
|---|---:|---|---|---:|---:|
| VICNSW | 1.42 | 1.10–1.84 | 1–2 quarters | 1.28 | 1.18 |
| NSWVIC | 1.57 | 0.94–2.37 | 3–4 quarters | 1.32 | 1.18 |
| QLDNSW | 1.51 | 1.09–1.98 | 5–8 quarters | 1.52 | 1.35 |
| NSWQLD | 1.68 | 1.10–2.51 | 9–12 quarters | 1.85 | 1.68 |
| VICSA | 1.81 | 1.26–2.50 | | | |
| SAVIC | 1.16 | 0.85–1.50 | | | |

Beneath the aggregate stability, directional pricing shifted meaningfully after 2023. On northward VNI (VICNSW), the realised-to-price ratio dropped from 1.97× in 2021 Q4–2023 Q4 to 1.02× (95% interval 0.80–1.25) across the ten quarters of 2024 Q1–2026 Q2 as bidders bid up near-term VNI units sharply; by contrast, QLDNSW remained strongly discounted at 1.65×, NSWVIC rose to 2.11×, and VICSA stayed at 1.42× in the post-2024 window. Treating the five-year aggregate ratio as a uniform corridor-blind alpha would therefore misprice northward VNI today.

### 7.3 Tranche convergence and auction-to-cash credit-support carry

Tracking clearing prices across Tranches 1 through 12 for identical delivery quarters isolates term-structure drift from ex-post weather surprises. Relative to the final Tranche 12 clearing price of the same delivery quarter, Tranche 1 units cleared at a median discount of -29% (and Tranche 4 at -20%), yielding a value-weighted realised-to-price ratio of 1.89 at Tranche 1 versus 1.28 at Tranche 12.

A realistic assessment of those returns must account for capital lockup. Measuring cashflow timing solely from the calendar payment date (shortly after delivery begins) to value-weighted weekly settlement receipts (assuming a 21-day settlement lag) produces a short cash duration of 49 days, a median holding-period return of 28%, and a tranche loss rate of 37%. Yet a participant buying Tranche 1 commits balance-sheet risk capacity and prudential credit support nearly three years before receiving cash. Measuring the full auction-to-cash exposure window and deducting illustrative annualised funding/credit-support carry rates tests whether the term discount merely compensates for capital lockup:

| Horizon to delivery | Median days (payment to cash) | Median days (auction to cash) | Value-weighted gross HPR | Carry drag at 8% p.a. | Net excess HPR at 8% p.a. | Net excess HPR at 12% p.a. |
|---|---:|---:|---:|---:|---:|---:|
| 1–2 quarters | 49 | 129 | 28% | 2.8% | 25% | 24% |
| 3–4 quarters | 49 | 312 | 32% | 6.8% | 25% | 22% |
| 5–8 quarters | 49 | 585 | 52% | 12.8% | 39% | 32% |
| 9–12 quarters | 49 | 911 | 85% | 20.0% | 66% | 56% |
| All tranches | 49 | 538 | 51% | 11.8% | 40% | 34% |

Even across a median 911-day exposure window on 9–12 quarter tranches, an 8% p.a. credit-support charge absorbs 20.0%, leaving 66% in net value-weighted excess return (56% at 12% p.a.). Carry alone therefore explains only a fraction of the term discount; the balance reflects risk aversion to single-day tail concentration (Chapter 4), limited bidder participation, and forward topology uncertainty. These findings mirror the empirical transmission-right auction literature in New York [R11], US FTR auctions [R12–R14], and European long-term rights [R4].

Quarter-by-quarter outcomes nevertheless remain highly dispersed across corridors, with extended clusters of buyer losses whenever anticipated scarcity fails to materialise.

### 7.4 Auction microstructure, unsold capacity, and bid-stack slippage

Public anonymised bid stacks reveal a median bid-to-offer ratio of 5.8, yet 34.0% of offered units went unsold across the window because low-priced bids sit below AEMO reserve thresholds or marginal clearing steps. For a trading desk seeking to execute commercial size, marginal clearing-price impact varies dramatically across corridors. Simulating an additional aggressive desk buy order of 25, 50, or 100 units against the latest public Tranche 12 aggregate demand curves quantifies execution depth directly:

| Latest Tranche 12 contract | +25 unit slippage ($ / %) | +50 unit slippage ($ / %) | +100 unit slippage ($ / %) |
|---|---:|---:|---:|
| VICNSW (250 offered, 125 sold) | \$0 (0.0%) | \$0 (0.0%) | \$0 (0.0%) |
| QLDNSW (175 offered, 100 sold) | \$0 (0.0%) | \$0 (0.0%) | \$10 (0.1%) |
| VICSA (120 offered, 77 sold) | \$0 (0.0%) | \$274 (1.9%) | \$2,108 (14.6%) |

Where significant tranche capacity went unsold (VICNSW and QLDNSW), moderate desk orders of 25 to 50 units clear with negligible immediate price impact against the observed stack. On tighter or smaller-offering corridors such as VICSA (and especially NSWQLD, where 75 units were offered and a 50-unit order pushes clearing prices up nearly 59%), execution slippage rapidly erodes apparent theoretical valuation edge and must enter portfolio sizing constraints explicitly.

## 8 Hedging futures spreads with SRA units: firmness, loop impact, and cap combinations

A core commercial question for any NEM trading or retail portfolio desk is whether directional SRA units can substitute for interregional ASX futures spreads, how many units replicate one megawatt of flat spread exposure, and what happens to that hedge during extreme price separation and under the November 2026 loop rules. This chapter evaluates hedge performance across both weekly and quarterly settlement horizons, separates sub-$300 capped-energy replication from $300 scarcity-tail replication, tests post-loop hedge firmness, and introduces a two-instrument SRA-plus-cap frontier.

### 8.1 Converting unit prices into spread equivalents

An SRA clearing price in dollars per unit cannot be compared directly with a futures spread in dollars per megawatt-hour without translating contractual pool share into effective megawatt transfer. With dated unit proportion $\theta_Q$, quarterly delivery hours $H$, and an assumed effective positive-spread transfer $\bar F$, the breakeven flow-weighted spread implied by a unit clearing price is:

$$
\text{required flow-weighted spread} = \frac{\text{clearing price}}{\theta_Q \, H \, \bar F}.
$$

For illustration, with $\theta_Q = 1/1{,}500$, $H = 2{,}160$ hours, and $\bar F = 500$ MW, a $15,000 unit price requires a flow-weighted positive spread of $20.83/MWh. Because physical transfer $\bar F$ varies systematically with the price spread, empirical hedging replaces assumed megawatts with the measured minimum-variance hedge ratio $n^{*}$ against a 1 MW flat spread. Comparing unit payoff $U_w$ against the 1 MW flat spread P&L $S_w = \sum_{t \in w} \Delta t (P_{B,t} - P_{A,t})$ across all 256 complete weeks gives:

$$
n^{*} = \frac{\operatorname{Cov}(S_w, U_w)}{\operatorname{Var}(U_w)}, \qquad
R^2 = 1 - \frac{\operatorname{Var}(S_w - n^{*} U_w)}{\operatorname{Var}(S_w)} = \operatorname{Corr}(S_w, U_w)^2.
$$

The implied empirical relative-value parity between SRA units and futures spreads is therefore:

$$
\text{SRA cost per MW-equivalent} = n^{*} \times \text{clearing price} \quad \text{versus} \quad H \times (\text{futures spread}),
$$

evaluated jointly with the stress MW-equivalent ratio $\sum_{w \in \text{top } 10} U_w / \sum_{w \in \text{top } 10} S_w$ across the ten highest-spread weeks to verify how much replication survives during market stress.

### 8.2 Weekly versus quarterly effectiveness and energy-versus-cap replication

Hedge performance differs sharply across interconnectors and across underlying price components. Measuring both weekly and quarterly settlement horizons eliminates the concern that weekly variance reduction might merely penalise intra-quarter timing mismatch.

| Direction | Min-variance units per MW ($n^{*}$) | Weekly $R^2$ (total spread) | Quarterly $R^2$ (total spread) | Weekly $R^2$ (capped energy) | Weekly $R^2$ ($300 cap tail) | Stress MW-equiv. (top 10 weeks) |
|---|---:|---:|---:|---:|---:|---:|
| VICNSW | 2.5 | 19% | 26% | 39% | 5% | 0.15 |
| QLDNSW | 1.6 | 52% | 68% | 16% | 48% | 0.66 |
| VICSA | 2.1 | 59% | 70% | 10% | 56% | 0.29 |
| NSWQLD | 3.3 | 39% | 67% | 30% | 30% | 0.26 |
| NSWVIC | 3.5 | 11% | 6% | 6% | 7% | 0.33 |
| SAVIC | 3.1 | 6% | 5% | 15% | 2% | 0.30 |

Separating capped-energy exposure from $300 cap exposure uncovers the precise physical mechanism behind VNI's low headline hedge score. On VICNSW, weekly $R^2$ against the total spread is 19% (rising only modestly to 26% on quarterly settlement), while weekly $R^2$ against the sub-$300 capped-energy spread doubles to 39% and collapses to 5% against the $300 scarcity cap spread (2% quarterly). When New South Wales clears above $300/MWh, mean northward VNI flow drops from 391 MW to 364 MW as thermal, voltage, and transient-stability limits bind, cutting one unit's effective transfer from 0.41 MW on average down to 0.15 MW in the ten worst weeks.

By contrast, QLDNSW and VICSA function as credible scarcity-tail hedges. When New South Wales clears above $300/MWh, northward QNI transfer expands from 315 MW to 439 MW, lifting QLDNSW weekly $R^2$ to 52% (68% quarterly), preserving 48% weekly $R^2$ on the $300 cap spread (65% quarterly), and holding stress-week equivalence at 0.66 MW per unit. Similarly, VICSA reaches 59% weekly $R^2$ (70% quarterly) and 56% weekly cap-spread $R^2$ (67% quarterly), though its stress-week equivalence still softens to 0.29 MW as Heywood transfer constraints tighten during South Australian peaks.

### 8.3 Post-loop hedge firmness across the NSW–Victoria–South Australia triangle

Evaluating the identical 256-week and 19-quarter hedge regressions against five-minute payouts generated under the AEMC net-trade loop rule (holding physical dispatch fixed) demonstrates that loop settlement further weakens standalone VIC-side hedging:

| Loop direction | Pre-loop weekly $R^2$ | Post-loop weekly $R^2$ | Post-loop quarterly $R^2$ | Post-loop $n^{*}$ (units/MW) | Post-loop stress MW-equiv. |
|---|---:|---:|---:|---:|---:|
| VICNSW | 19% | 14% | 19% | 2.6 | 0.11 |
| VICSA | 59% | 48% | 65% | 2.0 | 0.24 |
| NSWSA (indicative 800 units) | Not applicable | 14% | 6% | 5.6 | 0.06 |
| SANSW (indicative 800 units) | Not applicable | 14% | 8% | 4.2 | 0.10 |

Under the loop rule, VICNSW weekly variance reduction falls from 19% to 14% and stress-week MW-equivalence drops from 0.15 to 0.11 MW, because forced southward NSW-to-VIC counter-price residues now net directly against the shared loop pool during New South Wales scarcity events. Meanwhile, the new NSWSA and SANSW categories exhibit low standalone variance reduction (14% and 14% weekly) prior to physical EnergyConnect operation, because they receive payouts only during the 46% of intervals when Victoria acts as a pass-through region.

### 8.4 Repairing tail firmness: the two-instrument SRA plus $300 cap frontier

Because an SRA unit's payout is right-skewed and its firmness failure on VNI occurs specifically during destination prices above $300/MWh, evaluating tail risk requires Conditional Value at Risk (CVaR) rather than variance alone. For a desk short 1 MW of flat regional spread hedged with $n$ SRA units bought at quarterly clearing prices plus $m_{\text{cap}}$ MW of a destination $300 cap future, the 95% CVaR of weekly loss $\ell$ is minimised via the Rockafellar-Uryasev formulation [R18]:

$$
\operatorname{CVaR}_{0.95}(\ell) = \min_{c} \left\{ c + \frac{1}{0.05} \mathbb{E}\left[(\ell - c)^{+}\right] \right\}.
$$

To illustrate two-instrument replication before licensed ASX cap quotes are ingested, the destination $300 cap is priced at an illustrative 1.15 times its historical realised mean payout (explicitly a parametric loading assumption, not observed market pricing).

| Short 1 MW spread | Unhedged CVaR95 weekly loss | Best SRA-only CVaR95 (units) | Best SRA + 1 MW dest. cap CVaR95 (SRA units) | Total CVaR95 reduction (mix) |
|---|---:|---:|---:|---:|
| NSW minus VIC (via VICNSW) | \$32,683 | \$25,170 (5.2) | \$13,084 (1.8) | 60% |
| NSW minus QLD (via QLDNSW) | \$25,157 | \$7,575 (2.2) | \$8,258 (0.4) | 67% |
| SA minus VIC (via VICSA) | \$33,975 | \$14,206 (5.3) | \$9,428 (1.8) | 72% |

Pairing VICNSW units with a destination New South Wales $300 cap fundamentally transforms the risk profile: unhedged 95% weekly tail loss of \$32,683 falls modestly to \$25,170 with SRA units alone, but drops sharply to \$13,084 (a 60% reduction) once 1 MW of New South Wales $300 cap absorbs the scarcity tail while fewer SRA units (1.8 units) hedge the remaining sub-$300 energy divergence. That composite structure directly matches the physical mechanics of VNI.

### 8.5 Missing market leg: AER and ASX futures premia

> [!CONTEXT] Unobserved Futures and $300 Cap Quotes (Conditional Module Ready)
> Public Australian Energy Regulator (AER) base-futures chart series are currently not observed in this build because the AER web server blocks automated retrieval. Once the manual AER exports listed in the repository external-data guide are placed locally, the build pipeline automatically computes ex-post regional and spread premia $\pi_{r,Q}^{\text{fut}} = F_{r,Q}(\tau) - \bar P_{r,Q}$ (using the final pre-delivery quote), activates the futures-scaled walk-forward benchmark, and renders the futures-path and premium exhibits. Because AER exports exclude $300 cap quotes, empirical decomposition of observed market prices into capped energy versus scarcity still requires licensed ASX historical settlement data [S31].

Published empirical research finds positive, seasonal, cross-correlated risk premia in Australian base futures [R7] and significant area-price risk premia in Nordic locational spread contracts [R9, R10]. Before treating the SRA auction discount of Chapter 7 as pure relative-value cheapness against futures, a desk must compare the SRA discount per MW-equivalent directly against the matched futures spread premium, four-leg bid-ask execution costs, and daily ASX variation-margin funding risk.

## 9 Walk-forward benchmarks, option Greeks, and the valuation workbench

A trading desk should never adopt a complex structural valuation model until it demonstrates measurable out-of-sample skill against simpler, strictly causal benchmarks on identical auction dates. Chapters 7 and 8 established that SRA auctions clear at a persistent discount to realised cashflows and that unit hedging firmness varies sharply across links. This chapter puts simple forecasting rules, reduced-form option formulas, and relative-value spread arithmetic through a strict causal audit, correcting the look-ahead regime flaw identified in Version 2 and culminating in the worked 90-day NSW−VIC valuation example synced directly to the interactive Desk Workbench.

### 9.1 Strictly Causal Walk-Forward Evaluation Across 612 Tranches

To prevent any forward-looking leakage, every historical forecasting rule is evaluated under a strict as-of settlement cutoff: when forecasting the per-unit payoff of a tranche auctioned on date $\tau$, a candidate rule may access only quarters whose final delivery date finished at least 28 days prior to $\tau$ (reflecting AEMO's settlement publication lag). Requiring at least four settled prior quarters per direction restricts the scored walk-forward panel to 612 auction tranches spanning 2022-12-15 through 2026-03-16, explicitly excluding the 720 earlier tranches from the full 1,332-tranche auction record that fell inside the four-quarter warm-up window.

Version 3 expands the benchmark suite beyond raw trailing averages by adding three economically motivated causal challengers:

1. Debiased clearing price (ex-ante): Multiplies the live auction clearing price by the strictly causal trailing value-weighted realised-to-clearing ratio observed on previously settled tranches in the same horizon band (clamped to `[0.7, 2.0]` to avoid small-sample outliers).
2. MPC-rescaled trailing 4 quarters: Scales the trailing four-quarter realised payoff upward by a 35% scarcity-weighted ratio of the delivery quarter's statutory Market Price Cap to the trailing four-quarter mean MPC.
3. Outage-adjusted Tranche 12 (ridge-shrunk): For the `36` Tranche 12 contracts (`2024-12-16` to `2026-03-16`) where as-of planned transmission outage hours exist prior to bidding, adjusts the trailing mean using a ridge-shrunk linear slope on scheduled outage hours.

The out-of-sample verdict is unambiguous and sobering (Exhibit 9.1): **the raw auction clearing price beats every single statistical and mechanical challenger on Mean Absolute Error**, even though it carries a systematic downward risk-premium bias of −\$3,130 per unit.

| Causal forecasting rule | Scored tranches ($n$) | Mean bias ($/unit) | MAE ($/unit) | MAE (% of realised mean) | MAE skill vs. clearing price |
|---|---:|---:|---:|---:|---:|
| **Auction clearing price (benchmark)** | **612** | **−\$3,130** | **\$7,586** | **47%** | **0.0%** |
| Trailing 4 quarters | 612 | \$968 | \$9,954 | 62% | −31.2% |
| Trailing 8 quarters | 612 | \$746 | \$9,997 | 62% | −31.8% |
| Trailing 12 quarters | 612 | $666 | $10,132 | 62.9% | −33.6% |
| MPC-rescaled trailing 4 quarters | 612 | \$1,925 | \$10,430 | 65% | −37.5% |
| Trailing same-season mean | 612 | $1,116 | $10,695 | 66.4% | −41.0% |
| Debiased clearing price (ex-ante) | 612 | \$5,906 | \$10,995 | 68% | −45.0% |
| Prior settled quarter | 612 | $792 | $11,500 | 71.4% | −51.6% |
| *Matched T12 subset: Clearing price* | *36* | *−\$1,188* | *\$6,041* | *41%* | *0.0% (subset)* |
| *Matched T12 subset: Outage-adjusted T12* | *36* | *\$7,892* | *\$14,181* | *95%* | *−134.7% (subset)* |

Why did naive ex-ante debiasing perform 45% worse than raw clearing prices (\$10,995 MAE versus \$7,586), flipping bias from −\$3,130 to +\$5,906? The failure exposes the danger of backward-looking multiplier rules across regime shifts. Tranches settled during 2022 and 2023 realized massive payoff-to-price ratios (`1.79×` overall) because the June 2022 crisis surprised pre-crisis auctions. Multiplying 2024–2026 clearing prices by that trailing crisis ratio pushed forecasts far above realised payoffs precisely as market participants had already repriced the post-crisis forward curve downward (`1.35×` recent ratio, `1.02×` on `VICNSW`). Similarly, raw outage-hour scaling on Tranche 12 deteriorated sharply to \$14,181 MAE versus \$6,041 for clearing prices on the exact same 36 rows because total planned outage hours lump benign overnight maintenance together with daytime binding limits.

### 9.2 Disaggregated Accuracy by Direction and Horizon

Pooling all six directions hides huge cross-corridor differences in forecastability. Disaggregating the 612 walk-forward tranches by direction and by horizon band shows exactly where the auction market is already sharp and where systematic valuation opportunities reside:

| Direction ($n=102$ each) | Mean realised ($/unit) | Clearing price MAE ($/unit, %) | Clearing price bias ($/unit) | Debiased price MAE ($/unit) | Trailing 4q MAE ($/unit) |
|---|---:|---:|---:|---:|---:|
| `VICNSW` | $20,342 | \$6,022 (30%) | −\$914 | \$14,048 | $11,091 |
| `QLDNSW` | $34,598 | \$16,741 (48%) | −\$11,402 | \$18,087 | $19,715 |
| `VICSA` | $23,854 | \$12,681 (53%) | −\$6,711 | \$17,083 | $12,907 |
| `NSWQLD` | $8,532 | \$4,324 (51%) | \$1,500 | \$8,899 | $8,407 |
| `NSWVIC` | $4,494 | \$2,878 (64%) | −\$1,702 | \$2,713 | $3,383 |
| `SAVIC` | $4,825 | \$2,867 (59%) | \$446 | \$5,141 | $4,218 |

Across horizons, clearing-price MAE rises modestly from `$7,140` (`43.9%` of mean) at 1–2 quarters to `$7,721` at 3–4 quarters and `$8,077` at 5–8 quarters before settling at `$7,153` on the 9–12 quarter band, whereas debiased clearing prices degrade monotonically from `$8,667` at 1–2 quarters to `$12,868` (`87.6%` of mean) at 9–12 quarters. On `VICNSW`, clearing prices achieve an impressive 30% relative MAE (\$6,022) with minimal bias (−\$914), proving that the auction market already embeds forward outage and seasonal information far better than backward-looking rules. By contrast, `QLDNSW` (−\$11,402 bias) and `VICSA` (−\$6,711 bias) retain large negative pricing biases driven by heavy unhedged scarcity tails, while `NSWVIC` is the sole corridor where naive debiasing marginally beat raw clearing prices (\$2,713 versus \$2,878).

Sensitivity analysis across fundamental valuation drivers explains *why* simple autoregressive averages lose to the auction market (Exhibit 9.2). Changes in conditional scarcity severity, directional flow firmness during binding constraints, and forward outage schedules move per-unit value by thousands of dollars per quarter, reflecting information that auction participants observe ex-ante from MT PASA, outage plans, and ASX futures curves, and that Part IV's Stage 2–3 structural model is designed to ingest explicitly.

### 9.3 Strictly Ex-Ante Bachelier Spread-Option Fix and Valuation Greeks

Standard textbook commodity desks frequently approximate an SRA unit as a strip of Bachelier (normal) spread options, multiplying expected positive directional flow by a normal call option on the regional price spread $\mathbb{E}[(P_B - P_A)^+]$, because normal models gracefully accommodate negative electricity prices where lognormal Margrabe formulas [R17] fail. Yet Version 2 demonstrated that even a regime-conditioned Bachelier model overstated realised per-unit payouts by 2.30 times. A critical audit of Version 2's benchmark script uncovered a subtle look-ahead flaw: while mean and volatility parameters were trained strictly on the prior four quarters, the test quarter's value was summed across the test quarter's *realised* flow-direction regimes rather than ex-ante regime probabilities.

Version 3 removes that look-ahead peek completely. For every test quarter from `2022 Q4` through `2026 Q2`, the ex-ante benchmark conditions strictly on calendar season and four-hour time-of-day blocks (quantities known with 100% certainty before the auction), weighting each flow-direction regime by its training-window empirical transition probability $P(\text{flow regime} \mid \text{season, 4-hour block})$.

Eliminating the look-ahead peek does not rescue the independent spread-option approximation (Exhibit 9.3). Across all 90 direction-quarters evaluated (`2022 Q4–2026 Q2`), the strictly ex-ante Bachelier benchmark overstates realised aggregate per-unit payouts by 2.40 times, slightly *more* than Version 2's 2.30 times. Three physical omissions create that massive 2.4× structural gap:

1. Ignoring within-regime flow-spread negative covariance: Multiplying average positive flow by average call payoff assumes flow holds steady when spreads widen sharply, missing the firmness collapse documented in Chapter 5.
2. Omitting quadratic marginal losses: Pricing raw spreads $(P_B - P_A)^+$ ignores the 7% to 25% loss wedge established in Chapter 2.
3. Omitting five-minute negative-residue netting and loop rules: A call option on the spread assumes zero loss from counter-price clamping or pass-through reallocation.

Even though a reduced-form Bachelier proxy cannot price absolute unit levels accurately, its partial derivatives, namely Vega (sensitivity to spread volatility/severity scaling) and arrival-rate sensitivity (sensitivity to spike frequency scaling), provide clean local risk Greeks across corridors (Exhibit 9.4). Evaluating `2026 Q2` ex-ante sensitivities across `0.5×` to `2.0×` multipliers exposes a sharp asymmetry between volatility and frequency risk:

| Direction (`2026 Q2` ex-ante proxy) | Baseline `1.0×` value ($/unit) | `2.0×` Spread volatility (Vega stress) | Volatility sensitivity (`1× → 2×`) | `2.0×` Spike frequency stress | Frequency sensitivity (`1× → 2×`) |
|---|---:|---:|---:|---:|---:|
| `VICNSW` | \$17,211 | \$23,241 | +35% | \$17,327 | +1% |
| `QLDNSW` | \$90,839 | \$164,715 | +81% | \$99,003 | +9% |
| `VICSA` | \$31,089 | \$53,952 | +74% | \$34,102 | +10% |

Doubling spread volatility raises the ex-ante proxy by +35% on `VICNSW`, +74% on `VICSA`, and +81% on `QLDNSW`, whereas doubling spike-regime frequency shifts value by only +1%, +10%, and +9% inside the Gaussian-regime proxy. Notice the operational warning inside that contrast: because Gaussian option formulas pack tail value into continuous variance ($\sigma$) rather than discrete jump arrivals ($\lambda$), they misattribute jump-frequency risk into continuous volatility risk. Proper tail Greeks in Part IV require separating Poisson/Hawkes arrival intensity ($\lambda$) from conditional tail severity ($s$) directly on five-minute simulation paths.

### 9.4 Worked Desk Valuation Example and Interactive Workbench

To bridge empirical evidence directly into daily desk execution, consider a 90-day (`2,160`-hour) `NSW − VIC` quarterly evaluation using matched timestamped ASX base futures, $300 cap futures, and an upcoming `VICNSW` SRA auction tranche. All inputs below match the default parameters pre-loaded in the interactive Workbench directly underneath this walkthrough:

- **Matched futures quotes (origin `VIC = A`, destination `NSW = B`):** Origin base future $F_{\text{VIC}} = \$76.00/\text{MWh}$, destination base future $F_{\text{NSW}} = \$110.00/\text{MWh}$, origin $300 cap future $C_{\text{VIC}} = \$9.00/\text{MWh}$, and destination $300 cap future $C_{\text{NSW}} = \$25.00/\text{MWh}$.
- **Step 1 (Market-implied spread decomposition):** Applying the exact identity from Chapter 1 yields a market total base spread of $\$110.00 - \$76.00 = \$34.00/\text{MWh}$. Splitting at the $300 strike gives market-implied clipped energy spreads of $(\$110 - \$25) - (\$76 - \$9) = \$85.00 - \$67.00 = \$18.00/\text{MWh}$, and a market-implied scarcity cap spread of $\$25.00 - \$9.00 = \$16.00/\text{MWh}$. Over 2,160 delivery hours, a 1 MW linear base spread represents $\$73{,}440$, of which $\$38{,}880$ is clipped energy and $\$34{,}560$ is scarcity excess.
- **Step 2 (Cap-implied scarcity hours sanity check):** Suppose the desk's physical model estimates conditional mean excess above $300/MWh in New South Wales at $s_{\text{NSW}} = \$2{,}500/\text{MWh}$ with zero cap risk-premium loading ($\rho = 0$). The market's $\$25.00/\text{MWh}$ NSW cap price then implies $H_{\text{NSW}} = (25 / 2{,}500) \times 2{,}160 = 21.6\text{ hours}$ above $300/MWh in the quarter (roughly 259 five-minute intervals). If the desk instead assumes a 20% cap risk premium ($\rho = 0.20$), physical implied hours drop to $18.0$ hours. Comparing implied scarcity hours against the historical frequency distribution in the Chapter 4 Explorer immediately flags whether destination caps are rich or cheap relative to thermal outage and weather risk.
- **Step 3 (Physical versus market relative value):** If the desk's physical model (Stage 2–3 distribution $\mathbb{P}$) projects a total `NSW − VIC` spread of $\$30.00/\text{MWh}$ against the $\$34.00/\text{MWh}$ market base spread, the physical-minus-market edge is −$4.00/MWh (market expensive by `$8,640` per MW-quarter), signalling a potential short base-spread trade only if the desk agrees with the market's scarcity versus energy split.
- **Step 4 (SRA unit margin net of fees, carry, and model reserve):** Now evaluate a `VICNSW` SRA tranche trading at $\$15{,}000/\text{unit}$ against a discounted physical expected unit payoff of $\$20{,}000/\text{unit}$ (already adjusted for post-November 2026 loop pass-through haircuts if applicable). Subtracting $\$200/\text{unit}$ in auction fees and prudential carry plus a $\$750/\text{unit}$ model and liquidity reserve leaves an expected net economic margin of $\$4{,}050/\text{unit}$ (`+27.0%` return on purchase price). Before executing, the desk checks bid-stack slippage from Chapter 7 (`0%` up to 100 units on `VICNSW`) and sizes paired NSW $300 caps from Chapter 8 (`1.8` SRA units plus `1.0` MW NSW cap per MW of spread exposure) so tail risk stays inside risk limits.

Adjust any quote, severity assumption, risk-premium loading, or SRA unit input below to stress-test the exact relative-value arithmetic live.

## 10 System architecture, data contracts, and existing integration

Turning historical valuation evidence into a repeatable quarterly decision engine requires disciplined software boundaries. A valuation model that mixes realised future demand into historical backtests, silently blends incompatible forecast vintages across regions, or couples price generation directly into hard-coded pre-loop payoff arithmetic will produce optimistic validation scores and break on the first structural rule change. This chapter defines the five-layer system architecture, the four-time-axis vintage contract, the effective-dated rule dispatcher, and the exact boundary between what is already built in the repository valuation package and what remains to be engineered.

### 10.1 Five-layer valuation architecture

Every valuation run should execute as a deterministic pipeline across five decoupled layers, each exposing an explicit data contract and an independently inspectable output table.

**Layer 1: Information snapshot available at the valuation date.** Freeze a point-in-time snapshot containing issue-dated weather and demand ensembles, medium-term generator availability and outage submissions, planned network outage sets, committed transmission and generation milestones, statutory reliability settings, contract unit allocations, and timestamped market reference quotes. Every external record must carry both its source issue timestamp and its actual receipt or publication timestamp. A recently archived public table can embed late revisions that were unknowable on the historical auction date; enforcing strict as-of availability on both issue and receipt timestamps eliminates look-ahead leakage before any model runs.

**Layer 2: Joint fundamental scenario generation.** Draw spatially coherent multi-region weather trajectories, map them onto operational demand and available wind and solar profiles under the future asset fleet, sample forced thermal outages and restoration durations, sample network constraint states, and evolve storage and hydro energy inventories sequentially. Trajectories must remain intact across multi-day horizons so that a three-day cold, low-wind evening sequence preserves its cumulative battery depletion and thermal outage overlap.

**Layer 3: Network clearing and regional price formation.** Two complementary engines occupy this layer. The baseline statistical engine combines a feasible network-state distribution with a conditional clipped-energy price model and a four-state joint spike occurrence, duration, and severity process. The structural challenger clears regional supply curves subject to shared generic constraints, dynamic marginal loss curves, generator ramp limits, and intertemporal storage state. In both engines, regional prices and interconnector transfers must share common physical states and shocks. Sampling six interconnector forecasts independently is invalid because independent draws violate nodal power balance and shared security equations.

Whenever a statistical ensemble is projected onto a feasible transfer polytope, retain both the raw and projected paths and measure the resulting dollar shift in expected cap and SRA payoffs. Post-hoc projection can clip extreme flows or distort flow-spread covariance; it must be audited transparently rather than used to manufacture superficially coherent scenarios.

**Layer 4: Effective-dated settlement and contractual payoffs.** Evaluate every contract strictly at native five-minute resolution on each simulated trajectory before aggregating to weekly or quarterly totals. Compute linear regional base averages, $300 cap excesses, metered loss-adjusted asset residues, effective-dated pre-loop directional pooling or post-November 2026 net-trade loop allocations, dated unit proportions, auction fees, and payment-to-distribution cashflow schedules. Effective dates must be applied inside a delivery quarter whenever a rule transition occurs mid-quarter (as occurs in 2026 Q4, where pre-loop settlement governs October and net-trade loop settlement governs November and December).

**Layer 5: Physical valuation, market calibration, and portfolio risk.** Produce physical expected outcomes ($\mathbb{P}$), sampling and model uncertainty intervals, market-calibrated scenario weights ($\mathbb{Q}^{*}$), expected trading profit net of fees and carry, and portfolio conditional value at risk across candidate instrument mixes. Keep Monte Carlo simulation noise separate from structural parameter uncertainty: expanding the path count from 2,000 to 20,000 reduces simulation variance but never corrects a misspecified outage hazard or an omitted loop-allocation rule.

Every internal scenario record must therefore be keyed by valuation snapshot identifier, model version, scenario index, five-minute delivery interval, region or directional corridor, network topology version, and settlement-rule version, alongside stored random seeds and scenario weights.

### 10.2 Four-time-axis data architecture and source controls

Historical and prospective valuation datasets require four distinct time axes stored explicitly alongside every observation: physical delivery interval end (aligned strictly to fixed NEM time, UTC+10), source issue time, actual receipt or publication time, and record revision timestamp. Exchange trading timestamps for ASX derivatives, which follow daylight-saving market hours in Sydney, must be converted explicitly and never conflated with fixed UTC+10 delivery intervals.

| Dataset family | Primary valuation role | Required timing and quality controls |
|---|---|---|
| Five-minute regional reference prices and status flags | Exact base, $300 cap, and spread settlement | Decode price-cap, administered-price, and scaling bit flags; verify firm status; isolate market-suspension sensitivities |
| Dispatch and metered interconnector flows and losses | Network state, loss curves, and residue reconstruction | Preserve flow sign, dated from-region loss shares, physical-versus-pricing run selection, and parallel regulated link pooling |
| Generic security constraints and versions | Feasible transfer envelope and congestion attribution | Retain effective dates, left-hand-side coefficients, right-hand-side limits, and public-release timing |
| Demand and renewable availability forecasts | Issue-time fundamental price drivers | Separate rooftop solar already embedded in operational demand; distinguish available renewable capacity from curtailed dispatch |
| Generator availability and outage plans | Supply margin and forced-outage risk | Separate planned submissions from forced trips; preserve revision histories and unit restoration durations |
| Storage and hydro operational characteristics | Multi-hour endurance and ramp suppression | Track megawatt limits, megawatt-hour energy capacity, round-trip efficiency, and competing ancillary-service commitments |
| Spatial weather histories and ensembles | Joint multi-day fundamental scenarios | Preserve cross-regional temperature, wind, and solar correlation and calendar-day alignment |
| SRA notices, auction results, bid stacks, and distributions | Contract mapping, premia, and slippage analysis | Retain quarter, tranche, dated unit proportion, maximum unit count, fees, payment dates, and settlement revisions |
| Base and $300 cap market quotes | Market energy/scarcity split and entropy pooling | Match exact timestamps across legs; store bid, ask, traded volume, liquidity depth, and quote age |
| Market rules and transmission commissioning milestones | Effective-dated structural regimes | Distinguish final statutory rules from draft consultations and announced project timelines |

Public AEMO data-model documentation identifies the auction, contract, and unit-allocation tables while distinguishing publicly published aggregate clearing records from participant-private billing statements [S29]. Aggregate clearing prices, bid stacks, and settled inter-regional residues are publicly reproducible; participant-specific fee rebates, credit-support postings, and executable OTC quote histories require proprietary or licensed data feeds [S31]. External regulator publications, including AEMO Quarterly Energy Dynamics workbooks and AER significant-price incident reports, serve as reconciliation checks and mechanism libraries rather than replacements for a complete five-minute population census [S13, S30].

> [!MECHANISM] Why Settlement Reconciliation Must Follow a Stepwise Waterfall
> Reconciling an aggregate quarterly dollar total alone can conceal offsetting errors across directions, hours, or parallel assets. Every settlement verification should step sequentially from single-asset lossless flow-times-spread, to dated loss-share adjustment, to metered-versus-dispatch energy alignment, to parallel-link pooling, to positive-part or loop net-trade allocation, to dated unit proportions, and finally to fees and settlement-revision adjustments (at 20-week and 30-week revision runs). Recording the exact unexplained difference at every rung exposes subtle metering anomalies such as the small-flow sign-reversal bias documented on southbound QNI in Chapter 2.

### 10.3 Built-versus-unbuilt inventory and repository integration

The IC Flow Forecasting repository maintains three strictly separate model stacks that must never be conflated: the original six-interconnector conditional backtest (which uses realised future weather and demand as conditional research), the newer QNI and VNI diurnal, constraint, and network-outage research campaigns, and the offline production routing scaffold [L02, L03, L04]. The valuation stack sits cleanly alongside those forecasting modules as an independent research package rather than relabelling existing short-horizon flow targets.

Short-horizon flow-prediction skill does not automatically translate into quarterly price-spread or SRA valuation skill, and curated event atlases remain mechanism libraries rather than unbiased frequency samples. Reusable repository assets include canonical connector identities, hash-verified vintage contracts, constraint-to-outage set mappings from the network-outage campaign, and the offline report-verification harness.

| Engineering pillar | Current status in repository valuation package | Remaining build work for full live valuation |
|---|---|---|
| Five-minute price and flow panel | Complete (19 complete quarters, five regions, six interconnectors, decoded price flags, bit-exact v1 regression) | Automated incremental monthly ingestion and live issue-time vintage snapshots |
| Pre-loop and loop settlement engine | Complete (dated loss shares, parallel pooling, AEMO settled reconciliation, tested AEMC net-trade loop calculator, CPT-aware cap rescaling) | Verify $10 minimum distribution clause from final SRA Rules PDF; integrate 20-week/30-week revision deltas and post-2026 unit registries |
| Market auction and hedging analytics | Complete on SRA side (1,332 tranches, ex-2022 splits, T1–T12 drift, credit carry, weekly/quarterly/loop/SRA+Cap hedging, bid slippage) | Ingest manual AER base futures or licensed ASX base and $300 cap histories to activate joint futures-versus-SRA premia |
| Quarter scenario and price models | Baselines only (walk-forward historical rules, debiased clearing price, outage-adjusted benchmark, ex-ante Bachelier option proxy) | Build Stage 2 statistical scenario engine (7-day weather blocks, clipped-energy GAM/GBDT, 4-state spike hazard/duration/GPD) and Stage 3 structural challenger |
| Market calibration and portfolio optimisation | Specified mathematically (Chapter 11 dual entropy pooling and constrained CVaR sizing) | Implement Stage 4b Lagrange solver on live base/cap quotes and Stage 5 frozen prospective scoring ledger |

For structural event reconstructions and post-EnergyConnect dispatch counterfactuals in Stage 3, the open-source Nempy dispatch package offers a documented Python starting point covering NEM energy clearing, interconnector loss curves, ramp limits, generic constraints, and co-optimised ancillary services [S32]. Any adoption of Nempy must pin an exact release version, validate current EnergyConnect loop constraints and storage bidding mechanics against AEMO dispatch outputs, and treat it strictly as a structural dispatch challenger rather than a turnkey quarterly forecasting engine.

## 11 Modelling playbook, exhaustive literature synthesis, and calibration mathematics

Designing a quarterly interregional valuation model requires balancing physical realism against parameter parsimony. With nineteen complete five-minute quarters in the modern settlement era, overfitting flexible nonlinear architectures to a handful of extreme price days is a far greater danger than under-parameterising ordinary energy hours. This chapter first synthesises every relevant academic and institutional study paper by paper to establish what published evidence genuinely supports and where transfer to the current NEM requires caution. It then translates those lessons into concrete engineering specifications for quarterly horizon blending, clipped-energy pricing, four-state joint scarcity dynamics, explicit dual entropy-pooling calibration, and multi-instrument portfolio optimisation.

### 11.1 Exhaustive synthesis of academic and institutional research

Published power-market research supports combining structural market reasoning, regime-conditioned dependence, and disciplined contract-level benchmarking. It does not establish that any single complex black-box architecture dominates on current NEM quarters. Every transfer noted below is a deliberate research choice accompanied by explicit scope boundaries.

#### Regional spatial equilibrium and structural coupling

**Smith and Shively (2018) [S15]** develop an econometric model of regional Australian electricity spot prices grounded in spatial equilibrium with constrained interregional trade, layering a copula structure over regime-conditioned regional prices. Their core insight is that regional price dependence is not stationary across grid states: cross-regional co-movement behaves differently when transmission links are unconstrained versus when import or export constraints bind. For this project, their framework motivates explicitly separating unconstrained, export-constrained, import-constrained, and abnormal-network regimes before fitting residual copula dependence, while recognising that the NEM's generic multi-term security equations and forthcoming three-region loop topology are substantially richer than a two-region equilibrium model.

**Alasseur and Feron (2017, 2018) [S16]** formulate a structural coupled-market model with multiple generation fuel technologies and finite interconnector transfer capacity, applying it directly to electricity derivative and transmission-right valuation. Their contribution motivates building a reduced-form regional supply-curve challenger that clears regional prices and cross-border flows simultaneously from shared underlying demand and availability drivers. Before applying such an architecture to NEM SRA valuation, however, it must be extended to include quadratic marginal losses, generic security constraints, intertemporal battery storage state of charge, and effective-dated settlement rules; analytic tractability in stylised coupled markets does not demonstrate that five-minute NEM tails can be valued accurately without path simulation.

**Fuss, Mahringer, and Prokopczuk (2015) [S17]** demonstrate that incorporating forward-looking demand and available generation-capacity information directly into electricity derivative pricing improves valuation accuracy whenever fundamentals govern price sensitivity. In the NEM context, their findings support updating quarterly scenario distributions at each auction date using issue-dated medium-term availability submissions and planned outage schedules rather than relying on unconditional historical price processes. Crucially, their forward-looking framework applies strictly to information knowable at the valuation origin and never justifies substituting realised future demand or retrospectively observed constraints into an ex-ante backtest.

#### Multivariate price spikes, persistence, and extremal dependence

**Manner, Turk, and Eichler (2016) [S18]** model multivariate electricity price spikes in Australia using joint binary spike indicators linked through dynamic dependence and copula constructions. Their work provides a direct empirical precedent for estimating the four joint $300 exceedance states (neither, destination only, origin only, both) jointly rather than multiplying independent marginal regional spike probabilities. Implementation should begin with a well-calibrated multinomial logistic or shared-factor hazard model and introduce time-varying copula parameters only when out-of-sample log scores and cap-spread calibration improve on identical test quarters.

**Han, Cribben, and Truck (2022, 2025) [S19]** apply cross-regional extremograms to Australian electricity markets to measure the lag-by-lag persistence and cross-border transmission of extreme price episodes. Their diagnostic methodology directly informs our Chapter 4 extremogram analysis, establishing empirical event-clustering windows and providing a crisp falsification test for whether simulated scenario ensembles reproduce observed multi-hour persistence and regional contagion. Because their historical sample predates five-minute settlement and the current grid-scale battery fleet, this project reuses the extremogram diagnostic methodology rather than importing their historical parameter estimates.

**Liu and colleagues (2022) [S20]** estimate extreme-price occurrence probabilities using a multivariate logistic framework incorporating regional demand, reserve capacity, renewable penetration, interconnector flow, and lagged prices. Based on the accessible manuscript record, the study motivates adopting a transparent, regularised multivariate event classifier as an interpretable benchmark for Stage 2 scarcity arrival, with the critical modification that contemporaneous realised interconnector flow must be replaced by an issue-dated forecast or jointly simulated network state to prevent leakage.

#### Probabilistic forecasting and evaluation discipline

**Cornell, Dinh, and Pourmousavi (2023) [S21]** examine probabilistic NEM price forecasting through forecast combinations, explicit spike treatment, and quantile regression across models trained on differing historical window lengths. Their results highlight the value of combining longer stable training windows with shorter adaptive windows inside a rapidly decarbonising power system undergoing coal retirements and battery expansion. For derivative and SRA valuation, however, any spike filtering applied during base-model training must be reversed through an explicit conditional tail-severity model; improving median-price error by suppressing tail mass systematically destroys $300 cap and SRA payoff accuracy.

**Lago, Marcjasz, De Schutter, and Weron (2021) [S22]** establish rigorous benchmarking standards for electricity price forecasting: strong simple baselines, multi-market or multi-regime testing, substantial out-of-sample horizons, proper probabilistic scoring rules, and formal statistical significance tests. Transferred to interregional valuation, this discipline dictates scoring every candidate architecture at the contract-payoff level (quarterly spread bias, cap CRPS, SRA unit MAE, and stress-week hedge shortfall) rather than celebrating lower five-minute average price or flow MAE that degrades quarterly tail calibration.

#### Forward risk premia, transmission-right auctions, and market power

**Bessembinder and Lemmon (2002) [S23]** derive an equilibrium pricing model linking electricity forward premia directly to the variance and positive skewness of spot price distributions alongside asymmetric hedging demand from generators and retailers. Their theory explains why forward curves need not equal physical expected spot prices and why risk premia flip sign across seasons as skewness changes. Rather than assuming a single static risk loading across the NEM, equilibrium reasoning requires estimating premium uncertainty separately by region, season, product (base versus cap), and time to delivery.

**Handika and Truck (2013) [R7]** document statistically significant, positive, seasonal, and cross-regionally correlated risk premia in interconnected Australian electricity futures markets, while **Flottmann and colleagues (2024) [R8]** survey contemporary Australian electricity derivatives and hedging practices across generators and retailers. Together with adjacent New Zealand evidence from **Bevin-McCrimmon, Diaz-Rainey, and Sise (2016, 2018) [S24]** showing time-varying premia and liquidity effects in longer-dated futures, these studies underscore the importance of recording bid-ask spreads, traded volume, and quote age alongside price levels before concluding that an apparent SRA discount represents pure arbitrage against futures.

**Marckhoff and Wimschulte (2009) [R9]** and **Kristiansen (2004) [R10]** examine Nordic Electricity Price Area Differentials (EPADs), exchange-traded locational spread contracts directly analogous to NEM interregional spreads, finding material, time-varying spread risk premia tied to hydro-reservoir conditions and congestion asymmetry.

For centrally auctioned transmission rights specifically, five studies frame the exact empirical discount measured in Chapter 7. **Leslie (2021) [R11]** shows that New York Transmission Congestion Contracts cleared systematically below realised congestion payoffs, transferring substantial rents from ratepayers to financial bidders. **Stiewe (2026) [R4]** documents persistent shortfalls between European long-term transmission-right auction prices and forward-market spreads. On auction mechanism design, **Opgrand, Preckel, Gotham, and Liu (2022) [R12]**, **Deng, Oren, and Meliopoulos (2010) [R13]**, and **Adamson, Noe, and Parker (2010) [R14]** demonstrate that simultaneous feasibility constraints, limited bidder participation, risk aversion, and capital requirements can wedge auction clearing prices persistently below expected payoffs even when bidders possess accurate forecasts. Within Australia, the **CEPA review for the AEMC (2024) [R1]** confirms parallel-asset pooling, documents pre-loop negative-residue recovery from transmission networks, and explicitly questions whether excluding negative residues improves hedging firmness. Finally, **Joskow and Tirole (2000) [R16]** analyse how holdings of transmission rights interact with local generator market power when interconnector import limits bind, motivating controlled offer-steepness diagnostics rather than assuming competitive price-taking bids under congestion.

#### Quantitative tail, option, and portfolio calibration methods

**Margrabe (1978) [R17]** provides the classic closed-form lognormal exchange-option formula for the positive part of a spread between two strictly positive assets. Because NEM regional prices frequently clear below zero during midday solar surpluses, lognormal spread-option formulas are mathematically undefined across a large fraction of intervals; Chapter 9 therefore adopts a normal (Bachelier) regime benchmark as the reduced-form diagnostic while demonstrating why even Bachelier overstates payoffs when flow-spread independence is assumed.

**Heffernan and Tawn (2004) [S25]** introduce a semiparametric conditional-extremes model that characterises the joint distribution of companion variables given that a single conditioning variable exceeds a high threshold, without requiring all variables to be asymptotically dependent simultaneously. This aligns closely with NEM interregional stress, where New South Wales or South Australia may spike to the market price cap while Victoria sits near ordinary energy levels and VNI transfer contracts. Any Stage 3 implementation must apply temporal declustering, threshold stability diagnostics, and statutory price-cap truncation before fitting.

**Meucci (2008, 2010) [S26]** formalises entropy pooling as a convex optimisation procedure that adjusts prior scenario probabilities to satisfy market pricing views while minimising Kullback-Leibler divergence from the physical prior distribution. **Rockafellar and Uryasev (2000) [R18]** establish the linear-programming representation of conditional value at risk (CVaR), allowing exact convex optimisation of multi-instrument hedge portfolios (combining base futures, $300 caps, and directional SRA units) under skewed tail payouts.

### 11.2 Stage-by-stage modelling progression

| Modelling stage | Candidate specification | Primary economic purpose | Key failure mode to guard against |
|---|---|---|---|
| Benchmark | Seasonal empirical blocks, debiased clearing price, and simple regressions | Establish reproducible payoff, frequency, and MAE baselines | Cannot extrapolate cleanly to EnergyConnect, Basslink, or new unit counts |
| Stage 2 statistical baseline | Clipped-energy GAM/GBDT plus 4-state joint spike hazard, duration, and GPD tail | Interpretable conditional distribution of spreads, caps, and residues | Incoherent pairwise identities or uncalibrated multi-day clustering |
| Stage 2/3 joint scenario engine | Regime-conditioned prices and constrained transfers on 7-day spatial weather blocks | Coherent joint distribution of price spreads and flow-weighted SRA payoffs | Post-hoc feasibility projection distorting tail covariance |
| Stage 3 structural challenger | Regional supply curves, generic constraints, loss curves, and storage dispatch (Nempy) | Causal counterfactuals for EnergyConnect, outages, and battery depletion | Strategic bidding departures from technical marginal cost |
| Stage 4b/advanced additions | Dual entropy pooling, conditional extremes, and CVaR portfolio sizing | Market-consistent $\mathbb{Q}^{*}$ calibration and multi-instrument hedging | Overfitting rare episodes or collapsing effective scenario count $N_{\text{eff}}$ |

### 11.3 Forecasting a full quarter rather than extending short-range flows

Short-horizon interconnector models predict flows and limits hours to days ahead using observed initial grid conditions. Valuing a quarterly contract sold one to twelve quarters ahead requires full probability distributions over weather, plant outages, and dispatch regimes across 90 to 92 days. Implementation should blend three information horizons with a validated seasonal weighting rule rather than extrapolating short-range models linearly:

- **Near-delivery horizon (0 to 7 days):** Use issue-dated numerical weather and operational demand ensembles, active network outage schedules, and current storage and thermal plant status.
- **Medium horizon (8 to 30 days):** Blend progressively toward calibrated subseasonal temperature and wind anomalies only where historical skill beats seasonal climatology.
- **Seasonal balance of quarter (beyond 30 days):** Sample spatially coherent 7-day or 14-day multi-region weather blocks conditioned on season and future asset buildout, preserving cross-regional correlation between heatwaves, wind droughts, rooftop solar generation, and evening demand persistence.

Renewable capacity additions cannot be modelled by scaling historical output linearly with nameplate megawatts, because new wind and solar farms alter spatial diversity, local thermal congestion, and midday curtailment. Map historical weather into location-specific available renewable capacity before dispatch clearing, and attach commissioning-delay probabilities to announced transmission and generation projects rather than assuming full commercial operation on earliest announced dates.

Separate planned maintenance (sourced from issue-dated availability submissions and outage plans) from forced thermal outages and deratings. Model forced outages using unit-class hazard and restoration-duration distributions incorporating common-cause factors for extreme ambient temperature and fleet ageing; independent interval-by-interval Bernoulli draws severely understate multi-day outage duration. Preserve table-specific MT PASA horizons and vintage boundaries rather than treating all availability products as uniform three-year forecasts [S27].

For grid-scale batteries and hydro reservoirs, evolve stored megawatt-hours sequentially with round-trip efficiency, power limits, and ancillary-service reservations. Perfect-foresight battery optimisation suppresses simulated evening price spikes unrealistically; benchmark imperfect-foresight and forecast-responsive dispatch policies explicitly alongside stress-conservative policies where batteries enter evening peaks partially depleted. Begin Monte Carlo ensembles at 2,000 to 5,000 quarterly trajectories and expand until expected cap payouts and 95% CVaR stabilise across random seeds, using explicit likelihood weights whenever importance sampling is applied to rare joint-outage paths.

### 11.4 Forecasting clipped energy and four-state scarcity dynamics

**Capped-energy component ($E_{r,t} = \min(P_{r,t}, 300)$).** Fit regional clipped prices jointly on residual demand, regional net-demand differentials, seasonal gas and coal fuel references, available thermal capacity, storage headroom, planned outage flags, hour of day, and network regime. Start with a regularised linear model and a generalised additive model (GAM), testing shallow gradient boosting as a challenger. Model regional prices coherently inside a shared scenario representation so that pairwise spread identities hold exactly by construction:

$$
(E_{\text{NSW},t} - E_{\text{VIC},t}) + (E_{\text{VIC},t} - E_{\text{SA},t}) = E_{\text{NSW},t} - E_{\text{SA},t}.
$$

Negative wholesale prices require explicit multi-regime structure rather than a single Gaussian error term around clipped prices. Partition sub-$300 outcomes into negative-price regimes (driven by midday solar surplus and export congestion), ordinary positive-price regimes, and $300-boundary states, preserving negative-price duration and cross-regional coincidence. Where supply-curve fuel and heat-rate estimates are used as a structural challenger, calibrate observed offer markups empirically rather than treating technical short-run marginal cost as the clearing bid.

**Scarcity occurrence, duration, and severity ($C_{r,t} = \max(P_{r,t} - 300, 0)$).** Decompose tail events into three linked sub-models:

1. **Episode arrival (occurrence):** Estimate entry probabilities into the four joint $300 exceedance states conditional on pre-event accessible reserve margin (both MW headroom and MWh battery endurance), net-demand ramp, import headroom, and outage coincidence using a calibrated multinomial logistic or shared-factor hazard model. Score strictly with Brier score, log score, and reliability curves rather than raw classification accuracy.
2. **Episode persistence (duration):** Fit a semi-Markov exit-hazard model conditioned on elapsed episode duration, ambient temperature persistence, remaining battery state of charge, and expected outage restoration time. Validate simulated episode-length distributions and multi-day clustering against the empirical extremograms of Chapter 4.
3. **Conditional excess (severity):** Model positive excess above $300 conditional on active state using empirical quantile mixtures or a Generalised Pareto Distribution (GPD) above a statistically validated threshold (noting that the contractual $300 strike need not coincide with the optimal asymptotic GPD threshold), paired with an explicit point mass at the effective statutory market price cap and sequential enforcement of the rolling 7-day Cumulative Price Threshold and $600/MWh administered price cap [S28].

Summing simulated episodes directly avoids the approximation bias of multiplying unconditional frequency, mean duration, and mean severity when duration and severity are positively correlated. Note also a critical distinction between linear and nonlinear contracts: expected quarterly cap spread $\mathbb{E}[\bar C_B - \bar C_A]$ depends strictly on the two marginal regional expectations, whereas spread variance, destination-only episode probability, and every flow-weighted SRA payoff depend directly on cross-regional tail dependence.

### 11.5 Worked dual entropy-pooling mathematics and portfolio CVaR optimisation

Keep the physical predictive distribution $\mathbb{P}$ (represented by $S$ simulated quarterly scenarios with prior weights $p_s$, typically uniform $p_s = 1/S$) strictly separate from a market-calibrated pricing distribution $\mathbb{Q}^{*}$ with posterior weights $q_s$. Because electricity markets are incomplete, $\mathbb{Q}^{*}$ is never unique; its analytical purpose is to measure the minimal distributional distortion required to reconcile physical scenarios with liquid market quotes.

Given $K$ liquid calibration instruments (regional base futures $F_r$ and $300 cap futures $G_r$, explicitly holding SRA clearing prices out of the calibration set so they remain an independent relative-value test) with scenario payoff matrix $X \in \mathbb{R}^{S \times K}$, mid-market quotes $\bar{q} \in \mathbb{R}^{K}$, and executable half-spreads $\delta \in \mathbb{R}_{+}^{K}$, minimum relative-entropy calibration solves:

$$
\min_{q \in \mathbb{R}_{+}^{S}} \sum_{s=1}^{S} q_s \log \frac{q_s}{p_s}
\quad \text{subject to} \quad
\sum_{s=1}^{S} q_s = 1, \qquad
\left\lvert \sum_{s=1}^{S} q_s X_{s,k} - \bar{q}_k \right\rvert \le \delta_k \quad \forall k = 1, \dots, K.
$$

> [!MECHANISM] Explicit Dual Solver and Diagnostics for Implementation
> Rather than optimising over $S \ge 2{,}000$ primal weights directly, solve the unconstrained $K$-dimensional strictly convex dual problem over Lagrange multipliers $\lambda \in \mathbb{R}^K$ (where $K$ is typically only 4 to 8 regional base and cap contracts):
>
> $$
> \min_{\lambda \in \mathbb{R}^{K}} \mathcal{L}(\lambda) = \log \left( \sum_{s=1}^{S} p_s \exp\left( - \sum_{k=1}^{K} \lambda_k X_{s,k} \right) \right) + \sum_{k=1}^{K} \lambda_k \bar{q}_k + \sum_{k=1}^{K} \lvert \lambda_k \rvert \delta_k.
> $$
>
> Once optimal multipliers $\lambda^{*}$ are found (via quasi-Newton or L-BFGS-B in under 20 milliseconds for $S = 5{,}000$), posterior scenario weights follow in closed form via log-sum-exp normalisation:
>
> $$
> q_s^{*} = \frac{p_s \exp(-\lambda^{*\top} X_s)}{\sum_{j=1}^{S} p_j \exp(-\lambda^{*\top} X_j)}.
> $$
>
> **Mandatory engineering guardrails:** (1) Check convex-hull feasibility first: if $\bar{q}_k - \delta_k > \max_s X_{s,k}$ or $\bar{q}_k + \delta_k < \min_s X_{s,k}$, the physical ensemble lacks support for the market quote and the problem is infeasible, signalling a missing physical tail regime rather than a numerical error. (2) Monitor the effective scenario count $N_{\text{eff}} = 1 / \sum_{s=1}^{S} (q_s^{*})^2$ and relative effective fraction $N_{\text{eff}} / S$. Whenever $N_{\text{eff}} / S < 0.10$, market calibration is concentrating almost all probability mass onto a tiny handful of paths, rendering held-out SRA valuations unstable and requiring either prior-model revision or explicit ambiguity reporting.

**Instrument selection and constrained portfolio CVaR optimisation.** Select instruments by matching risk decomposition to contract payoff geometry: express pure sub-$300 energy-price divergence through capped-energy combinations (base minus $300 cap legs), express differential tail-scarcity views through cap spreads, and express deliverable congestion-transfer views through directional SRA units. For a cross-regional retail or generation portfolio with scenario exposure vector $L_s$, assemble the scenario cashflow matrix $M \in \mathbb{R}^{S \times J}$ across all candidate instruments $j$ (regional base futures, $300 caps, and directional SRA units net of clearing prices, fees, and credit-support carry) and solve the Rockafellar-Uryasev convex CVaR problem [R18]:

$$
\min_{w, \, c, \, u \ge 0} \; c + \frac{1}{(1 - \alpha) S} \sum_{s=1}^{S} u_s + \gamma \| w \|_2^2
\quad \text{subject to} \quad
u_s \ge (L_s - M_s w) - c, \qquad w \in \mathcal{W},
$$

where $\mathcal{W}$ encodes position limits, auction tranche depth ceilings (bounded by the bid-stack slippage curves of Chapter 7), and funding/variation-margin constraints, and $\gamma \| w \|_2^2$ applies light ridge regularisation so estimation noise never generates extreme offsetting positions. Terminal payoff optimisation must always be paired with separate liquidity stress tests measuring peak pre-delivery ASX variation-margin calls alongside upfront SRA credit-support requirements, and portfolio stress tables reporting residual loss under single-region scarcity, common scarcity, interconnector outages, prolonged wind droughts, battery depletion, and post-November 2026 loop settlement.

## 12 Validation protocol, acceptance gates, and staged build roadmap

An interregional valuation engine earns commercial trust only when its out-of-sample contract payoffs beat simple transparent benchmarks on identical historical origins without look-ahead leakage. Because nineteen complete five-minute quarters supply fewer than five independent realisations of each Australian season, rigorous validation requires chronological freezing, stress-regime ablations, block-bootstrap uncertainty intervals, and explicit separation between diagnostic research and live trading readiness.

### 12.1 Chronological backtest origins and mandatory benchmarks

Freeze every model parameter, feature transformation, seasonal reference, and external input vintage at each historical SRA auction date and at representative futures valuation horizons (one, three, six, and twelve months ahead of delivery), plus an in-quarter update test at mid-quarter. Retrain solely on quarters fully settled at least 28 days prior to each origin date, score against realised terminal settlements, and reserve an untouched prospective holdout window once model specifications are frozen. Earlier two-year repository windows have already informed feature exploration and constraint studies across the wider project and must never be relabelled as pristine out-of-sample holdouts [L03].

Every candidate valuation model must be benchmarked on identical historical auction tranches against five nested baselines:

1. **Historical resampling baseline:** Trailing four-quarter and same-season empirical block averages.
2. **Market clearing-price baselines:** Both the raw auction clearing price (current MAE \$7,586 per unit across 612 tranches) and the strictly causal debiased clearing price (MAE \$10,995 per unit).
3. **Simple fundamental-statistical baseline:** Clipped-energy regression paired with a four-state logistic scarcity arrival model.
4. **Market base-and-cap decomposition baseline:** Matched regional base and $300 cap futures quotes once AER or ASX histories are ingested.
5. **Existing flow-model hybrid:** Repository interconnector flow forecasts (strictly within their valid issue-time horizons) paired with an empirical conditional price layer.

Complex structural challengers incorporating detailed generic constraints, storage dynamics, or Nempy dispatch clearing must additionally be tested against stripped-down variants without those layers so their incremental payoff accuracy is measured directly.

### 12.2 Contract-level scorecards and paired ablations

Evaluate full predictive distributions separately from point expectations. A model can achieve low median error while severely underpricing $300 cap tails; conversely, a single extreme scarcity day can dominate sample means and widen estimation noise.

| Valuation target | Statistical scoring metrics | Economic and operational tests |
|---|---|---|
| Network regime and transfer flow | MAE, pinball quantile loss, feasibility residuals | Transfer error specifically during high-spread intervals |
| Four-state spike occurrence | Brier score, log score, reliability calibration curves | Missed high-value separation episodes and false-alarm hedging cost |
| Episode duration and tail severity | Survival calibration, upper-tail quantiles, CPT breach rate | Quarterly $300 cap bias and top-five-day concentration match |
| Joint multi-region scenarios | Cross-regional extremograms, energy score, variogram score | Spread variance calibration and stress-week hedge failure rate |
| Quarterly price spread | Mean bias, 90%/95% interval coverage, CRPS | Realised spread P&L after bid-ask execution and margin carry |
| SRA unit payoff | Stepwise settlement reconciliation error, distribution coverage | Payout shortfall, downside tranche loss rate, and CVaR reduction |
| Market calibration ($\mathbb{Q}^{*}$) | Held-out SRA price error, effective scenario count $N_{\text{eff}}$ | Incremental relative value beyond fitted base/cap instruments net of slippage |

To expose false complexity and isolate true economic drivers, run six paired ablation experiments holding random seeds and test origins fixed:

1. Remove planned outage and topology information available at the auction date.
2. Remove battery storage state-of-charge tracking (comparing finite MWh endurance against unconstrained megawatt capacity).
3. Shuffle regional price trajectories independently across regions while preserving marginal distributions (quantifying cross-regional tail dependence).
4. Shuffle flow and spread paths independently within calendar regimes (quantifying within-regime flow-spread firmness collapse).
5. Aggregate simulated prices to half-hour averages prior to applying the $300 cap and SRA positive-part operators (quantifying temporal convexity bias).
6. Apply pre-loop directional settlement versus November 2026 AEMC net-trade loop settlement to identical physical trajectories (isolating rule-driven repricing from physical EnergyConnect dispatch changes).

Whenever an ablation or experiment uses realised future weather, demand, or retrospectively observed constraints, label it explicitly as a conditional diagnostic rather than a tradable forecast improvement.

### 12.3 Acceptance gates and the five-stage build roadmap

Progression from retrospective research to prospective decision support is governed by five non-negotiable acceptance gates:

- **Gate 1 (Accounting and lineage):** Exact algebraic closure of capped-energy plus scarcity, loss plus congestion, and SRA state attribution to machine precision, backed by content-addressed input hashes and zero look-ahead leakage.
- **Gate 2 (Settlement reconciliation):** Automated unit tests passing every CEPA and AEMC worked example, plus documented stepwise reconciliation against AEMO settled residues within investigated metering tolerances.
- **Gate 3 (Calibration and out-of-sample skill):** Competitive probability calibration and contract-payoff CRPS/MAE against the five mandatory baselines across multiple seasons, with block-bootstrap confidence intervals reported alongside point metrics.
- **Gate 4 (Economic survival net of frictions):** Apparent expected trading margin survives auction bid-stack slippage (Chapter 7), credit-support carry over the full auction-to-cash window, ASX bid-ask costs, and reasonable parameter sensitivities.
- **Gate 5 (Prospective freeze):** At least two consecutive forward quarters executed under a frozen specification with logged issue-time revisions before any live capital allocation. Commercial hurdle thresholds must be set from desk risk appetite rather than inferred from historical research alone.

**Current programme status at Version 3:** Stage 1 (the 19-quarter five-minute panel, reconciled pre-loop settlement ledger, CPT-aware cap normalization, and unit-tested AEMC loop calculator) is complete. Stage 4a (full public SRA auction history, ex-2022 premia, carry analysis, slippage, and weekly/quarterly/loop/SRA+Cap hedge effectiveness) is complete and awaiting AER or licensed ASX base and cap quote files to complete Stage 4b. Stages 2, 3, and 5 remain to be built following the specifications in Chapters 10 and 11; an indicative engineering window for a small quant team with data access in place is eight to twelve weeks, paced primarily by quote-vintage integration and structural dispatch validation rather than model training runtime.

### 12.4 Standardised quarterly decision sheet

Every future production run should emit a single standardised decision sheet per corridor and delivery quarter containing six fixed blocks:

1. Contract header: Ordered region pair, explicit sign convention, delivery quarter and hours, valuation issue timestamp, active settlement regime (pre-loop versus loop net-trade), and effective unit proportion.
2. Expected value decomposition: Physical expected total spread split into capped energy, scarcity excess, loss, and congestion alongside 90% uncertainty intervals and matched market base/cap quotes; SRA expected distribution in dollars per unit beside clearing price, fees, and credit-support carry.
3. Tail and firmness anatomy: Expected hours and episode counts across all four joint $300 exceedance states, conditional severity, top-five-day concentration share, expected transfer flow during destination scarcity, and battery endurance in critical paths.
4. Market reconciliation ambiguity: Explicit statement of which physical assumptions (destination-only arrival rate, common tail dependence, transfer firmness under stress, or hedging-demand risk loading) must shift to match market quotes, displaying ambiguity openly whenever multiple explanations fit equally well.
5. Portfolio and instrument action: Optimal mix across base futures, $300 caps, and directional SRA units under CVaR and slippage constraints, paired with peak variation-margin and credit-support funding estimates.
6. Revision bridge and invalidation scenarios: Attribution of valuation changes since the prior issue date (new outage submissions, weather shifts, unit-count notices, or market moves) paired with the explicit physical scenarios that would invalidate the position.

### 12.5 Consolidated evidence limits and open questions

Six material boundaries govern how the empirical findings of Version 3 should be interpreted today:

- **Unobserved futures and $300 cap quotes:** Automated retrieval from the AER website remains blocked, and AER exports exclude $300 cap quotes. Relative value between SRA units and futures is therefore quantified through hedge equivalence, SRA auction premia, and illustrative cap-loading frontiers until manual AER or licensed ASX histories are loaded.
- **Fixed-dispatch loop counterfactual and parametric EnergyConnect bounds:** Both the rule-only loop counterfactual and the parametric 150 MW / 800 MW EnergyConnect sensitivities hold regional dispatch logic stylised rather than re-solving full AC/DC optimal power flow with whole-loop NRM clamping.
- **Heuristic constraint attribution:** Chapter 6 classifies limit-setting equations via AEMO's naming convention rather than full left-hand-side equation coefficients; equation-level sensitivity belongs to the repository's dedicated network-outage constraint studies.
- **Exploratory four-day offer-steepness diagnostic:** Missing archived bid-per-offer files limited the strategic pilot to 4 calendar days (two in New South Wales, two in South Australia, and zero in Queensland); no generalisable market-power inference is claimed.
- **Early unit-registry fallbacks and unverified $10 rule clause:** Fifty-six early quarter-directions prior to the archived allocation register use published maximum unit counts, and verbatim verification of the $10 minimum SRDA distribution clause awaits manual download of the August 2026 SRA Rules PDF.
- **Persistence of the auction discount post-loop:** While the auction discount survives outside the 2022 crisis and after illustrative credit-support carry, its exact structural split between risk aversion, bidder concentration, and regime-break expectations remains an open empirical question as the market transitions into loop settlement from November 2026.

## Appendix A Mathematical and formula reference

This reference consolidates every accounting identity, settlement equation, statistical estimator, and optimisation formulation used across Chapters 1 through 12, paired with the implementing module inside the repository valuation package.

| Quantity | Formula | Implementing module / stage |
|---|---|---|
| Quarterly arithmetic mean | $\bar X = \frac{1}{H}\sum_{t \in Q}\Delta t \, X_t$, with $\Delta t = \frac{1}{12}\text{ h}$, $H = \sum_{t \in Q}\Delta t$ | `nemic/valuation/baseline.py` |
| Capped energy and scarcity excess | $E_{r,t} = \min(P_{r,t}, K)$, $C_{r,t} = \max(P_{r,t} - K, 0)$, $K = 300$ | `nemic/valuation/baseline.py` |
| Market energy / scarcity split | $F_B - F_A = [(F_B - G_B) - (F_A - G_A)] + (G_B - G_A)$ | `nemic/valuation/market.py` |
| Frequency times severity | $\bar C_r = p_r \, m_r$, where $p_r = \Pr(P_r > K)$ and $m_r = \mathbb{E}[P_r - K \mid P_r > K]$ | `nemic/valuation/baseline.py` |
| Joint four-state contribution | $\bar S = \sum_z \frac{1}{H}\sum_{t \in Q}\Delta t \, S_t \mathbf{1}\{z_t = z\}$ | `nemic/valuation/baseline.py` |
| Loss and congestion split | $P_{\text{to},t} - P_{\text{from},t} = (P_t^{*} - P_{\text{from},t}) + (P_{\text{to},t} - P_t^{*})$, $P_t^{*} = \lambda_t P_{\text{from},t}$ | `nemic/valuation/evidence.py` |
| Single-asset five-minute residue | $r_{a,t} = \frac{\Delta t}{1\text{ h}}\left[P_{\text{to},t}(F_{a,t} - (1 - s_a)L_{a,t}) - P_{\text{from},t}(F_{a,t} + s_a L_{a,t})\right]$ | `nemic/valuation/settlement.py` |
| Pre-loop directional unit payoff | $\Pi_Q^{\text{unit}} = \theta_Q \sum_{t \in Q}\max\left(\sum_a r_{a,t}\mathbf{1}\{\sum_a F_{a,t} > 0\}, 0\right)$ | `nemic/valuation/settlement.py` |
| AEMC net-trade loop allocation | $a_k = q_k(P_{\text{imp}(k)} - P_{\text{exp}(k)})$, $\tilde a_k = R^{\text{loop}} \frac{a_k}{\sum_j a_j}$, $\text{payout}_k = R^{\text{loop}} \frac{\max(\tilde a_k, 0)}{\sum_j \max(\tilde a_j, 0)}$ | `nemic/valuation/loop.py` |
| Mechanical unit-count dilution | $\Delta \text{per unit} = \theta_{\text{new}} / \theta_{\text{old}} - 1 = U_{\text{old}} / U_{\text{new}} - 1$ | `nemic/valuation/v3_analytics.py` |
| Rolling 7-day CPT truncation | $P_{r,t}^{\text{CPT}} = \min(P_{r,t}^{\text{MPC}}, P_{\text{APC}})$ if $\sum_{u=t-2015}^{t-1} P_{r,u}^{\text{CPT}} + P_{r,t}^{\text{MPC}} > \text{CPT}$ | `nemic/valuation/v3_analytics.py` |
| Value-weighted auction ratio | $\rho(\mathcal{T}) = \frac{\sum_{i \in \mathcal{T}} n_i \, \text{payoff}_i}{\sum_{i \in \mathcal{T}} n_i \, \text{price}_i}$ | `nemic/valuation/market.py` |
| Credit-support carry drag | $\text{net HPR} = (\rho - 1) - r_{\text{carry}} \cdot \frac{\text{days}_{\text{auction}\to\text{cash}}}{365}$ | `nemic/valuation/v3_analytics.py` |
| Minimum-variance hedge ratio | $n^{*} = \frac{\operatorname{Cov}(S_w, U_w)}{\operatorname{Var}(U_w)}$, variance removed $= \operatorname{Corr}(S_w, U_w)^2$ | `nemic/valuation/market.py` |
| Conditional value at risk (CVaR) | $\operatorname{CVaR}_{\alpha}(\ell) = \min_c \left\{ c + \frac{1}{1-\alpha}\mathbb{E}[(\ell - c)^{+}] \right\}$ | `nemic/valuation/v3_analytics.py` |
| Ungated flow–spread covariance | $\mathbb{E}[F^{+} S^{+}] = \mathbb{E}[F^{+}]\mathbb{E}[S^{+}] + \operatorname{Cov}(F^{+}, S^{+})$ | `nemic/valuation/baseline.py` |
| Cross-regional extremogram | $\hat{\pi}_{ij}(h) = \widehat{\Pr}(P_{j,t+h} > K \mid P_{i,t} > K)$ | `nemic/valuation/evidence.py` |
| Moving day-block bootstrap | $\bar S^{(b)} = \frac{1}{D}\sum_{d \in \mathcal{B}^{(b)}} \bar S_d$, contiguous 7-day blocks | `nemic/valuation/evidence.py` |
| Ex-ante Bachelier regime call | $\mathbb{E}[S^{+}] = \sigma \varphi(\mu / \sigma) + \mu \Phi(\mu / \sigma)$ weighted by training calendar weights $w_{\text{train}}$ | `nemic/valuation/v3_analytics.py` |
| Ensemble CRPS | $\text{CRPS}(F, y) = \frac{1}{M}\sum_i \lvert x_i - y \rvert - \frac{1}{2M^2}\sum_{i,j} \lvert x_i - x_j \rvert$ | `nemic/valuation/valuation_tests.py` |
| In-quarter remaining implied average | $\bar P^{\text{remaining}} = \frac{F - w \bar P^{\text{elapsed}}}{1 - w}$ | Interactive Workbench |
| Destination cap-implied hours | $h = \frac{H \, G}{(1 + \rho_{\text{risk}}) \, m}$ | Interactive Workbench |
| Dual entropy-pooling objective | $\mathcal{L}(\lambda) = \log \sum_s p_s \exp(-\lambda^{\top} X_s) + \lambda^{\top} \bar{q} + \sum_k \lvert \lambda_k \rvert \delta_k$, $N_{\text{eff}} = 1 / \sum_s q_s^2$ | Stage 4b specification (Ch. 11) |

## Appendix B Technical schema, AEMO table mapping, and reproducibility

To keep Chapters 1 through 12 free of raw database codes and file paths, this appendix maps every plain-English institutional reference in the main narrative to its exact AEMO MMSDM table, local evidence file, configuration contract, and command-line reproduction workflow.

### B.1 AEMO MMSDM source table mapping

| Plain-English reference in narrative | AEMO MMSDM table | Key fields used | Local archive coverage |
|---|---|---|---|
| Five-minute regional reference prices and status flags | `DISPATCHPRICE` | `SETTLEMENTDATE`, `REGIONID`, `RRP`, `INTERVENTION`, `PRICE_STATUS`, `APCFLAG`, `MARKETSUSPENDEDFLAG` | 90 monthly parquet partitions |
| Five-minute interconnector flows, limits, losses, and setters | `DISPATCHINTERCONNECTORRES` | `INTERCONNECTORID`, `MWFLOW`, `METEREDMWFLOW`, `MWLOSSES`, `MARGINALLOSS`, `EXPORTLIMIT`, `IMPORTLIMIT`, `EXPORTGENCONID`, `IMPORTGENCONID` | 90 monthly parquet partitions |
| Published AEMO settled inter-regional residue | `SETIRSURPLUS` | `SETTLEMENTDATE`, `SETTLEMENTRUNNO`, `PERIODID`, `INTERCONNECTORID`, `REGIONID`, `MWFLOW`, `LOSSFACTOR`, `SURPLUSVALUE` | 59 monthly files (latest run selected) |
| Dated interconnector loss shares | `INTERCONNECTORCONSTRAINT` | `INTERCONNECTORID`, `EFFECTIVEDATE`, `VERSIONNO`, `FROMREGIONLOSSSHARE` | 59 monthly files |
| Statutory market price cap, floor, and CPT schedule | `MARKET_PRICE_THRESHOLDS` | `EFFECTIVEDATE`, `VERSIONNO`, `VOLL`, `MARKETPRICEFLOOR`, `ADMINISTERED_PRICE_THRESHOLD` | 59 monthly files |
| Negative residue management activation flags | `NEGATIVE_RESIDUE` | `SETTLEMENTDATE`, `NRM_DATETIME`, `DIRECTIONAL_INTERCONNECTORID`, `NRM_ACTIVATED_FLAG` | 25 monthly files (from Aug 2024) |
| Public SRA tranche clearing results | `RESIDUE_PUBLIC_DATA` | `CONTRACTID`, `INTERCONNECTORID`, `FROMREGIONID`, `UNITSOFFERED`, `UNITSSOLD`, `CLEARINGPRICE`, `RESERVEPRICE` | 27 monthly files |
| Dated unit proportions, maximum units, and fees | `AUCTION_IC_ALLOCATIONS` | `CONTRACTYEAR`, `QUARTER`, `INTERCONNECTORID`, `FROMREGIONID`, `MAXIMUMUNITS`, `PROPORTION`, `AUCTIONFEE`, `VERSIONNO` | 40 monthly files |
| Auction dates, notification dates, and payment calendar | `RESIDUE_CONTRACTS`, `AUCTION_TRANCHE`, `AUCTION_CALENDAR` | `CONTRACTID`, `AUCTIONDATE`, `NOTIFYDATE`, `PAYMENTDATE`, `STARTDATE` | 23–42 monthly files |
| Anonymised aggregate auction bid stacks | `RESIDUE_PRICE_FUNDS_BID` | `AUCTIONID`, `CONTRACTID`, `INTERCONNECTORID`, `FROMREGIONID`, `UNITS`, `BIDPRICE`, `LINKEDBIDFLAG` | 21 monthly files |
| Generator energy offers (exploratory 4-day pilot) | `BIDPEROFFER_D`, `BIDDAYOFFER_D` | `DUID`, `BIDTYPE`, `PRICEBAND1..10`, `BANDAVAIL1..10`, `MAXAVAIL` | Streamed on demand (4/6 months absent) |

### B.2 Price flag bitmask decoding and constraint naming heuristic

AEMO's `APCFLAG` column encodes bit flags rather than a single status string [R2]: bit 1 (`1`) indicates an administered price cap or floor binding (1,883 rows); bit 2 (`2`) indicates VOLL override (10 rows); bit 4 (`4`) indicates market price cap or floor binding (1,589 rows); bit 8 (`8`) indicates manual override (87 rows); and bit 16 (`16`) indicates inter-regional loss-factor price scaling (5,201 rows). All complete quarters contain 0 non-firm rows (`PRICE_STATUS = FIRM`).

Constraint-family attribution in Chapter 6 applies AEMO's standard identifier convention: `>>` denotes thermal limits, `^^` denotes voltage stability, `::` denotes transient stability, `<<` denotes oscillatory stability, `NRM` prefixes denote automated negative residue management, `#` denotes manual or ramp constraints, and `NIL` designates system-normal equations rather than outage-specific constraint sets.

### B.3 Version 3 evidence inventory and module ownership

| Evidence file (under `reports/interregional_valuation_research_v3/evidence/`) | Generating module | Primary chapter |
|---|---|---|
| `sra_ledger_quarterly.csv`, `sra_reconciliation.csv`, `sra_unit_registry.csv` | `nemic.valuation.settlement` | Ch. 2 |
| `sra_payoff_decomposition.csv`, `qni_south_reconciliation_diag.csv` | `nemic.valuation.v3_analytics` | Ch. 2 |
| `loop_counterfactual.csv`, `loop_diagnostics.csv`, `loop_attribution_waterfall.csv`, `loop_parametric_pec.csv`, `qni_dilution_check.csv`, `basslink_proforma_backcast.csv` | `nemic.valuation.mechanisms`, `v3_analytics` | Ch. 3 |
| `spread_decomposition.csv`, `regional_decomposition.csv`, `joint_regimes.csv`, `bootstrap_quarterly.csv`, `leave_one_day_out.csv`, `extremogram.csv`, `mpc_cpt_normalised.csv`, `diurnal_profile.csv`, `diurnal_regime_summary.csv` | `nemic.valuation.baseline`, `evidence`, `v3_analytics` | Ch. 4 |
| `loss_congestion_quarterly.csv`, `loss_curve_fits.csv`, `mlf_flow_sample.csv`, `flow_diagnostics_full.csv`, `tail_dependence.csv`, `negative_price_mechanics.csv` | `nemic.valuation.evidence`, `v3_analytics` | Ch. 5 |
| `counterprice_quarterly.csv`, `counterprice_days.csv`, `constraint_attribution.csv`, `constraint_top_setters.csv`, `outage_plan_predictive.csv`, `strategic_pilot.csv` | `nemic.valuation.mechanisms`, `valuation_tests` | Ch. 6 |
| `auction_panel.csv`, `auction_vs_realised.csv`, `auction_regime_sensitivity.csv`, `auction_tranche_drift.csv`, `auction_carry_returns.csv`, `auction_premium_heatmap.csv`, `auction_proceeds_vs_residue.csv`, `auction_microstructure.csv`, `auction_bid_curve_latest.csv`, `bid_stack_slippage.csv` | `nemic.valuation.market`, `v3_analytics` | Ch. 7 |
| `hedge_effectiveness.csv`, `hedge_weekly_points.csv`, `hedge_quarterly_and_components.csv`, `hedge_two_instrument_frontier.csv`, `loop_hedge_effectiveness.csv`, `futures_status.json` | `nemic.valuation.market`, `v3_analytics` | Ch. 8 |
| `walk_forward_v3_forecasts.csv`, `walk_forward_v3_scores.csv`, `walk_forward_by_direction.csv`, `walk_forward_by_horizon.csv`, `scenario_sensitivity.csv`, `scenario_registry.json`, `option_benchmark_v3.csv`, `option_sensitivity_v3.csv` | `nemic.valuation.valuation_tests`, `mechanisms`, `v3_analytics` | Ch. 9 |
| `headline_numbers.json`, `data_audit.json`, `mpc_schedule.json` | `nemic.valuation.v3_summary`, `evidence` | All chapters |

### B.4 Complete rebuild and verification commands

From the repository root, run the cached Tier A analytics, rebuild the summary ledger, and execute the full test suite:

```bash
python -m nemic.valuation all               # optional: rebuild cached v2 panel and base tables
python -m nemic.valuation.v3_analytics      # compute all 9 Tier A v3 tables into v3/evidence/
python -m nemic.valuation.v3_summary        # regenerate v3/evidence/headline_numbers.json
python -m pytest -q                         # verify settlement, evidence, v3, and repo tests
```

From `reports/interregional_valuation_research_v3/`, build the offline HTML report, run the browser QA suite, and verify Virtual Barrels prose lint:

```bash
python build_html.py
node qa_report.cjs
```

To enable the unobserved AER base-futures exhibits (`futures_paths.csv` and `futures_premia.csv`), save the manual AER chart exports documented in `data/external/README.md` into `data/external/aer_futures/`, then re-run `python -m nemic.valuation market`, `python -m nemic.valuation.v3_analytics`, and `python build_html.py`. Raw AEMO archives remain local under `data/` and are excluded from version control.

## Appendix C Sources, evidence hierarchy, and audit changelog

Sources are organised following the Virtual Barrels evidence hierarchy: Tier 1 covers statutory market rules, official system-operator procedures, exchange product specifications, and primary telemetry; Tier 2 covers peer-reviewed academic research and institutional regulatory studies; Tier 3 covers original practitioner forensic analyses used solely for hypothesis generation and dispatch verification. Local repository evidence entries document internal reproducibility trails. Dates distinguish publication dates from regulatory effective dates.

### C.1 Tier 1: Primary statutory rules, system-operator disclosures, and exchange specifications

[S01] ASX. Australian Electricity Derivatives fact sheet, June 2025. Base and $300 cap specifications, pp. 7–8 and 12–13. [Primary product document](https://www.asx.com.au/content/dam/asx/markets/trade-our-derivatives-market/derivatives-market-overview/energy-derivatives/australian-electricity-fact-sheet.pdf). Governs payoff definitions; exchange operating rules take precedence.

[S02] ASX Energy. Australian Electricity New listed Interregional spreads, 11 August 2014. [Exchange notice](https://www.asxenergy.com.au/newsroom/industry_news/australian-electricity---new-). Establishes historical leg-sign conventions; confirm active broker conventions before execution.

[S03] AEMO. Methodology for the allocation and distribution of settlements residue, 2 June 2024. [Primary methodology](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/methodology_for_the_allocation_and_distribution_of_settlements_residue.pdf). Pre-loop loss and allocation methodology.

[S04] AEMO. Settlements Residue Auction Rules, effective 7 August 2026. [Final rules and participation agreement](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/2026/settlements-residue-auction-rules-7-aug-2026.pdf). Sections 4 and 15 and Schedule 1 section 9 govern unit entitlements, fees, and minimum distributions; direct automated PDF download was restricted and requires manual clause verification.

[S05] AEMO. Unit Category Data Q2 2028, revised May 2026. [Quarter-specific unit notice](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/auction-notices/2025/unit-category-data-2028q2---revised.pdf). Illustrates quarter-specific maximum unit counts and proportional entitlements.

[S06] AEMC. Interregional settlements residue arrangements for transmission loops, final determination (ERC0386), 25 September 2025. [Final determination](https://www.aemc.gov.au/sites/default/files/2025-09/Final%20determination-%20ERC0386.pdf). Establishes net-trade allocation, loss reconciliation, and secondary netting.

[S07] AEMO. Project EnergyConnect Market Integration stakeholder reference paper, May 2026. [Reference paper and worked examples](https://www.aemo.com.au/-/media/files/initiatives/project-energyconnect/pec-mi-settlements---stakeholder-reference-paper.pdf). Sets out the 1 October 2026 dispatch representation date, 1 November 2026 settlement effective date, and worked loop examples.

[S08] AEMO. Methodology for the Allocation, Distribution and Recovery of Settlements Residue consultation, initiated 16 September 2026. [Consultation page](https://www.aemo.com.au/consultations/current-and-closed-consultations/methodology-for-the-allocation-distribution-and-recovery-of-settlements-residue). Draft procedural consultation at the research cutoff.

[S09] AEMO. EnergyConnect Market Integration frequently asked questions. [Operational FAQ](https://www.aemo.com.au/initiatives/major-programs/nem-reform-program/nem-reform-program-initiatives/project-energyconnect-market-integration-project/frequently-asked-questions). Confirms whole-loop negative residue management from the operational transition.

[S10] AEMO. Final expedited consultation report for Basslink SRA rules, 30 April 2026. [Final report](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/2026/final-report-expedited-consultation-for-the-nem-basslink-30-april-2026.pdf). Introduces VICTAS and TASVIC categories and updates auction fee rules.

[S11] AEMO. Auction Report 2026 Quarter 2, dated 4 August 2026, published 18 August 2026. [Auction results](https://www.aemo.com.au/-/media/files/electricity/nem/settlements_and_payments/settlements/auction-reports/2026/auction-report-2026-quarter-2.pdf). Records June 2026 clearing prices including initial Basslink tranches.

[S12] AEMO. Constraint Frequently Asked Questions. [Constraint documentation](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq). Primary operational authority on interpreting generic constraints and reported limits.

[S27] AEMC. Improving transparency and extending duration of MT PASA, 2020. [Rule-change record](https://www.aemc.gov.au/rule-changes/improving-transparency-and-extending-duration-mt-pasa). Defines MT PASA submission and publication horizons.

[S28] AEMC. Schedule of reliability settings 2026–27 financial year. [Primary settings schedule](https://www.aemc.gov.au/media/105056). Establishes the FY2027 market price cap of $23,200/MWh and associated cumulative price threshold.

[S29] AEMO. MMS Data Model IRAUCTION package. [Data-model documentation](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_162.htm). Schema reference for public versus participant-private SRA tables.

[S30] AEMO. Quarterly Energy Dynamics. [Reports and workbooks](https://www.aemo.com.au/energy-systems/major-publications/quarterly-energy-dynamics-qed). External quarterly reconciliation benchmark.

[S31] ASX Energy. Australian Electricity products and intraday trades API documentation. [Product information](https://www.asxenergy.com.au/products/au_electricity) and [data interface](https://www.asxenergy.com.au/docs/api/intraday_trades). Reference for licensed historical futures ingestion.

[R2] AEMO. MMS Data Model Report, DISPATCHPRICE table. [Data model](https://visualisations.aemo.com.au/aemo/nemweb/MMSDataModelReport/Electricity/MMS%20Data%20Model%20Report_files/MMS_130.htm). Defines APCFLAG bit masks and firm settlement price conventions.

[R3] AEMO. Unit category data notices and MMS auction allocation records. Documents dated maximum unit counts including the 2027 Q2 QNI unit count changes.

[R5] AEMO. Automation of Negative Residue Management (2021) and transmission loop NRM consultation (2025). [Consultation](https://www.aemo.com.au/consultations/current-and-closed-consultations/automation-of-negative-residue-management-for-the-implementation-of-transmission-loops). Defines the -$100,000 clamping threshold and whole-loop clamping rule.

[R19] AEMC. Inter-regional settlements residue arrangements for transmission loops, rule determination ERC0386, 25 September 2025. [Determination](https://www.aemc.gov.au/sites/default/files/2025-09/Final%20determination-%20ERC0386.pdf). Primary source for Figure 3.1 and Appendix B Example 4 unit tests.

### C.2 Tier 2: Peer-reviewed academic research and institutional regulatory studies

[S13] AER. Reports on significant electricity prices for Q2 2026, 31 August 2026. [Regulator findings](https://www.aer.gov.au/news/articles/communications/aer-reports-significant-electricity-prices-q2-2026). Forensic mechanism evidence for multi-hour storage depletion and interacting network limits.

[S15] Smith, M. S., and T. S. Shively. Econometric Modeling of Regional Electricity Spot Prices in the Australian Market, April 2018 working paper. [Full paper](https://arxiv.org/pdf/1804.08218). Spatial equilibrium, constrained trade, and copula dependence.

[S16] Alasseur, C., and O. Feron. Structural price model for electricity coupled markets, 2017 preprint (Energy Economics, 2018). [Author preprint](https://arxiv.org/abs/1704.06027). Multi-fuel coupled supply-curve valuation for derivatives and transmission rights.

[S17] Fuss, R., S. Mahringer, and M. Prokopczuk. Electricity derivatives pricing with forward-looking information. Journal of Economic Dynamics and Control 58, 34–57, 2015. DOI 10.1016/j.jedc.2015.05.016. [Institutional record](https://research.uni-hannover.de/en/publications/electricity-derivatives-pricing-with-forward-looking-information/). Abstract and publication record reviewed.

[S18] Manner, H., D. Turk, and M. Eichler. Modeling and forecasting multivariate electricity price spikes. Energy Economics 60, 255–265, 2016. DOI 10.1016/j.eneco.2016.10.006. [Publisher record](https://www.sciencedirect.com/science/article/pii/S0140988316302870). Joint binary spike indicators with dynamic copula dependence.

[S19] Han, L., I. Cribben, and S. Truck. Extremal Dependence in Australian Electricity Markets, 2022 preprint (Journal of Commodity Markets, 2025). [Author paper](https://arxiv.org/abs/2202.09970). Cross-regional extremograms and persistence of extreme prices.

[S20] Liu, L., and colleagues. Forecasting the occurrence of extreme electricity prices using a multivariate logistic regression model. Energy 247, 123417, 2022. DOI 10.1016/j.energy.2022.123417. [Institutional record](https://research-repository.griffith.edu.au/server/api/core/bitstreams/f003c844-829c-4db6-8257-47538355a229/content). Indexed manuscript metadata reviewed.

[S21] Cornell, C., N. T. Dinh, and S. A. Pourmousavi. A probabilistic forecast methodology for volatile electricity prices in the Australian National Electricity Market, 2023 preprint. [Author paper](https://arxiv.org/abs/2311.07289). Probabilistic combinations, spike handling, and adaptive training windows.

[S22] Lago, J., G. Marcjasz, B. De Schutter, and R. Weron. Forecasting day-ahead electricity prices: A review of state-of-the-art algorithms, best practices and an open-access benchmark. Applied Energy 293, 116983, 2021. [Author manuscript](https://arxiv.org/abs/2008.08004). Benchmark rigor and evaluation discipline.

[S23] Bessembinder, H., and M. L. Lemmon. Equilibrium Pricing and Optimal Hedging in Electricity Forward Markets. Journal of Finance 57, 1347–1382, 2002. DOI 10.1111/1540-6261.00463. [Publisher abstract](https://onlinelibrary.wiley.com/doi/abs/10.1111/1540-6261.00463). Equilibrium link between skewness, hedging demand, and forward premia.

[S24] Bevin-McCrimmon, F., I. Diaz-Rainey, and G. Sise. Liquidity and Risk Premia in Electricity Futures. USAEE working paper 16-291, December 2016 (later 2018 journal article). [Working-paper record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2885453). Adjacent New Zealand evidence on time-varying premia and liquidity.

[S25] Heffernan, J. E., and J. A. Tawn. A conditional approach for multivariate extreme values. Journal of the Royal Statistical Society B 66, 497–546, 2004. [Research paper](https://www.d.umn.edu/~yqi/mydownload/heffemantawn.pdf). Conditional multivariate tail modelling without requiring simultaneous extremity.

[S26] Meucci, A. Fully Flexible Views: Theory and Practice, 2008 (arXiv 2010). [Author paper](https://arxiv.org/abs/1012.2848). Minimum relative-entropy scenario reweighting.

[S32] Gorman, N., and colleagues. Nempy: A Python package for modelling the Australian National Electricity Market dispatch procedure. Journal of Open Source Software 7(70), 3596, 2022. [Repository](https://github.com/UNSW-CEEM/nempy). Open-source structural dispatch modelling tool.

[R1] Cambridge Economic Policy Associates for the AEMC. Settlements Residue Auction and Modified Load Export Cost processes, final report, 24 May 2024. [Report](https://www.aemc.gov.au/sites/default/files/2024-06/cepa_report_-_sra_and_mlec.pdf). Confirms asset pooling, pre-loop negative residue treatment, and firmness issues.

[R4] Stiewe, C. Arbitrage and rents in European long-term transmission rights. arXiv:2607.28790, July 2026. [Paper](https://arxiv.org/abs/2607.28790). Empirical evidence on European transmission-right auction discounts.

[R7] Handika, R., and S. Truck. Risk Premiums in Interconnected Australian Electricity Futures Markets. SSRN 2279945, 2013. [Paper](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2279945). Positive, seasonal, cross-correlated NEM base-futures premia.

[R8] Flottmann, J. H., P. Wild, and N. Todorova. Derivatives and hedging practices in the Australian National Electricity Market. Energy Policy 189, 114114, 2024. Survey of Australian electricity hedging practice.

[R9] Marckhoff, J., and J. Wimschulte. Locational price spreads and the pricing of contracts for difference: evidence from the Nordic market. Energy Economics 31(2), 257–268, 2009. Area-price CfD risk premia.

[R10] Kristiansen, T. Pricing of Contracts for Difference in the Nordic market. Energy Policy 32(9), 1075–1085, 2004. Locational spread contract pricing.

[R11] Leslie, G. Who benefits from ratepayer-funded auctions of transmission congestion contracts? Evidence from New York. Energy Economics, 2021. [Abstract](https://www.sciencedirect.com/science/article/abs/pii/S0140988320303650). Ratepayer transfers in centrally auctioned transmission rights.

[R12] Opgrand, J., P. V. Preckel, D. J. Gotham, and A. L. Liu. Price formation in auctions for financial transmission rights. The Energy Journal 43(3), 2022. FTR auction clearing mechanics.

[R13] Deng, S.-J., S. Oren, and A. P. Meliopoulos. The inherent inefficiency of simultaneously feasible financial transmission rights auctions. Energy Economics 32(4), 2010. Structural inefficiency of periodic FTR auctions.

[R14] Adamson, S., T. Noe, and G. Parker. Efficiency of financial transmission rights markets in centrally coordinated periodic auctions. Energy Economics 32(4), 2010. Auction efficiency under participant risk aversion.

[R16] Joskow, P., and J. Tirole. Transmission rights and market power on electric power networks. RAND Journal of Economics 31(3), 450–487, 2000. Interaction of transmission rights with local market power.

[R17] Margrabe, W. The value of an option to exchange one asset for another. Journal of Finance 33(1), 177–186, 1978. Lognormal exchange-option benchmark (inapplicable under negative prices).

[R18] Rockafellar, R. T., and S. Uryasev. Optimization of conditional value-at-risk. Journal of Risk 2(3), 21–41, 2000. Convex CVaR portfolio formulation.

### C.3 Tier 3: Practitioner analyses and local repository evidence

[S14] WattClarity. Interconnector intricacies: double and triple auto-clamping of negative residues, January 2025. [Practitioner analysis](https://wattclarity.com/articles/2025/01/interconnector-intricacies-double-and-triple-auto-clamping-of-pesky-negative-residues/). Operational interpretation of pre-loop negative-residue clamping.

[L01] Version 1 descriptive audit and price-decomposition baseline (18 September 2026). Preserved untouched as the bit-exact regression baseline on the two-year window.

[L02] Repository methodology documentation covering conditional-input experiments, five-minute aggregation, flow targets, and reported-limit interpretation.

[L03] Repository expanded QNI/VNI forecast research documentation recording inspected historical test windows and constraint-reconstruction limitations.

[L04] Repository offline production pipeline guide defining immutable model packages and issue, receipt, and delivery vintage contracts.

[L05] Version 2 and Version 3 valuation packages and audited evidence tables documenting every settled, auction, hedging, loop, CPT, and walk-forward calculation.

### C.4 Audit changelog: Version 1 to Version 2 to Version 3

| Milestone | Scope and methodological additions | Audit status |
|---|---|---|
| Version 1 (18 Sep 2026) | Conceptual valuation design, 7-quarter descriptive price/flow baseline, illustrative workbench, 32 external references. | Frozen baseline; reviewed in 21-item peer audit (C-01, M-01–M-10, m-01–m-10). |
| Version 2 (26 Sep 2026) | 19-quarter panel, AEMO-settled residue ledger, 1,332 auction tranches, weekly hedging, loss/congestion 2×2 split, AEMC loop counterfactual, walk-forward rules, 27 Plotly exhibits, KaTeX formulas. | Frozen baseline; responded to all 21 review items but retained 56.3% verbatim v1 splices and split exhibit gallery from prose. |
| Version 3 (Current) | Full mechanics-first Virtual Barrels rewrite (12 chapters, 4 parts, 3 appendices); inline exhibits; 9 Tier A analytical upgrades (SRA $/unit split, ex-2022 & carry tests, 3-way loop waterfall & loop hedging, quarterly & SRA+Cap frontier, diurnal residue & negative-price loss inversion, disaggregated walk-forward + 3 baselines, QNI 2027 Q2 dilution & pro-forma Basslink, MPC×CPT truncation, bid-stack slippage); 4 script fixes (ex-ante option benchmark, transparent 4-day pilot scope, explicit walk-forward window, active CPT cap); build-ready Part IV engineering spec & exhaustive paper-by-paper literature review. | Verified via automated unit tests, Virtual Barrels prose lint, and offline Playwright browser QA. |
