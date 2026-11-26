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
