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

{{interactive:payoffGeometry}}

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
