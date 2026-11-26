# Interregional valuation research, version 3

Open `Interregional_Valuation_Research_v3.html` in a modern browser. It is completely self-contained and works offline with zero external network requests:

- Plotly and KaTeX (with inlined WOFF2 fonts) are embedded directly in the page;
- every exhibit is woven inline beneath the chapter prose explaining its physical or economic mechanism, with zero stacked three-chart walls;
- interactive Historical Explorer (Chapter 4), Flow–Spread Bridge (Chapter 5), Payoff Geometry (Chapter 1), and Desk Valuation Workbench (Chapter 9) run client-side;
- every exhibit's underlying CSV and JSON data can be downloaded directly from the page.

Version 3 reorganises and rewrites the version 2 research (`../interregional_valuation_research_v2/`, left untouched as the frozen baseline) in the calm, mechanics-first Virtual Barrels editorial standard while adding nine Tier A valuation upgrades and fixing four subtle methodological issues audited in `nemic/valuation/`.

## What is new in version 3

- **Unified mechanics-first structure.** Consolidates 37 fragmented chapters and removes all 18 verbatim version 1 carry-over splices (eliminating internal contradictions) into 12 cohesive chapters across four parts (Plumbing, Empirical Structure, Market Valuation, Implementation Blueprint) plus three reference appendices.
- **SRA dollar-payoff decomposition (Chapter 2, Exhibit 2.3).** Splits settled per-unit payoffs into coupled loss surplus, sub-$300 energy congestion, and >$300 scarcity states alongside fixed-flow clipped-price counterfactuals.
- **Loop haircut attribution, post-loop hedging, QNI dilution, and Basslink backcast (Chapter 3, Exhibit 3.2).** Decomposes the AEMC net-trade loop impact into negative-loop netting, Victoria pass-through reallocation, and secondary netting; recomputes hedge ratios post-loop; adds parametric 150 MW / 800 MW EnergyConnect transfer bounds; tests live 2027 Q2 QNI unit-count dilution pricing; and computes a caveated pro-forma regulated Basslink residue backcast.
- **CPT-aware FY2027 cap rescaling & diurnal residue profiling (Chapter 4, Exhibit 4.4).** Simulates sequential rolling 7-day Cumulative Price Threshold breaches ($600/MWh APC) alongside the $23,200/MWh FY2027 cap, and splits settled SRA dollars across Solar Midday, Evening Ramp, and Overnight operating blocks plus negative-price loss-sign inversion (Chapter 5).
- **Ex-2022 auction split, tranche drift, credit carry, and slippage (Chapter 7, Exhibit 7.3).** Verifies the auction discount outside the 2022 crisis and post-2024, tracks T1–T12 convergence, deducts multi-year auction-to-cash credit-support carry, and measures 25/50/100-unit bid-stack clearing slippage.
- **Quarterly & component hedging plus two-instrument SRA+Cap frontier (Chapter 8, Exhibit 8.3).** Adds quarterly settlement $R^2$, separates capped-energy hedging from $300 cap replication, and quantifies how pairing a New South Wales $300 cap repairs VICNSW tail firmness.
- **Disaggregated walk-forward scoring & fixed ex-ante option benchmark (Chapter 9, Exhibits 9.1, 9.3, 9.4).** Disaggregates walk-forward MAE by direction and horizon, tests debiased clearing price and pre-auction outage baselines, removes the version 2 in-sample test-quarter flow-regime peek from the Bachelier benchmark, and plots ex-ante Vega and spike-frequency Greeks.
- **Build-ready Part IV implementation specification & exhaustive paper-by-paper literature synthesis (Chapters 10–12).** Provides five-layer module contracts, four-time-axis vintage schemas, explicit dual Lagrange-multiplier entropy-pooling mathematics, Stage 2–3 modelling recipes, and five go/no-go acceptance gates.

## Rebuild

From the repository root:

```bash
python -m nemic.valuation.v3_analytics
python -m nemic.valuation.v3_summary
python -m pytest -q tests/test_valuation_settlement.py tests/test_valuation_evidence.py tests/test_valuation_v3.py
```

From this folder:

```bash
python build_html.py
node qa_report.cjs
```

## Status

Research evidence and quantitative implementation specification, not a live trading signal or deployed forecast service. AER base futures remain unobserved until manual chart exports are placed in `data/external/aer_futures/`.
