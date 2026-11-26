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
