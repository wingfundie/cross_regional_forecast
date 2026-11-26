## 12 Validation protocol, acceptance gates, and staged build roadmap

An interregional valuation engine earns commercial trust only when its out-of-sample contract payoffs beat simple transparent benchmarks on identical historical origins without look-ahead leakage. Because nineteen complete five-minute quarters supply fewer than five independent realisations of each Australian season, rigorous validation requires chronological freezing, stress-regime ablations, block-bootstrap uncertainty intervals, and explicit separation between diagnostic research and live trading readiness.

### 12.1 Chronological backtest origins and mandatory benchmarks

Freeze every model parameter, feature transformation, seasonal reference, and external input vintage at each historical SRA auction date and at representative futures valuation horizons (one, three, six, and twelve months ahead of delivery), plus an in-quarter update test at mid-quarter. Retrain solely on quarters fully settled at least 28 days prior to each origin date, score against realised terminal settlements, and reserve an untouched prospective holdout window once model specifications are frozen. Earlier two-year repository windows have already informed feature exploration and constraint studies across the wider project and must never be relabelled as pristine out-of-sample holdouts [L03].

Every candidate valuation model must be benchmarked on identical historical auction tranches against five nested baselines:

1. **Historical resampling baseline:** Trailing four-quarter and same-season empirical block averages.
2. **Market clearing-price baselines:** Both the raw auction clearing price (current MAE {{wf3_mae_market_clearing_price}} per unit across {{wf3_n_market_clearing_price}} tranches) and the strictly causal debiased clearing price (MAE {{wf3_mae_debiased_clearing_price}} per unit).
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

{{diagram:roadmapPanel}}

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
- **Exploratory four-day offer-steepness diagnostic:** Missing archived bid-per-offer files limited the strategic pilot to {{strategic_days_total}} calendar days (two in New South Wales, two in South Australia, and zero in Queensland); no generalisable market-power inference is claimed.
- **Early unit-registry fallbacks and unverified $10 rule clause:** Fifty-six early quarter-directions prior to the archived allocation register use published maximum unit counts, and verbatim verification of the $10 minimum SRDA distribution clause awaits manual download of the August 2026 SRA Rules PDF.
- **Persistence of the auction discount post-loop:** While the auction discount survives outside the 2022 crisis and after illustrative credit-support carry, its exact structural split between risk aversion, bidder concentration, and regime-break expectations remains an open empirical question as the market transitions into loop settlement from November 2026.
