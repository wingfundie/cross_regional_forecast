# Interregional valuation research, version 2

Open `Interregional_Valuation_Research_v2.html` in a modern browser. It is self-contained and works offline:

- Plotly and KaTeX (with fonts) are embedded;
- all 12 version 1 exhibits are included, plus 27 new exhibits and 2 new diagrams;
- every chart's data can be downloaded from the page.

Version 2 carries out the valuation designed in version 1 and responds to every item in `../interregional_valuation_research_20260918/review.md` (Appendix C of the report). The version 1 folder is left untouched as the reviewed baseline.

## What is new

- **Settlement ledger.** AEMO-settled residue (`SETIRSURPLUS`), pooled per directional interconnector with the positive part taken per interval, converted to $ per unit with dated unit proportions. The computed engine reconciles to AEMO settlement and is used for sensitivities and counterfactuals.
- **Auctions against realised payoffs.** Every public SRA tranche since October 2021 (`RESIDUE_PUBLIC_DATA` and related tables) joined to its settled payoff, with cluster-bootstrap intervals, the horizon term structure, proceeds against distributions, returns and bid stacks.
- **Hedging.** Weekly hedge effectiveness of units against a 1 MW futures-style spread, minimum-variance and CVaR hedge ratios, and stress-week ratios.
- **Evidence base.** 19 complete quarters (2021 Q4 – 2026 Q2), TAS and Basslink included, with:
  - an exact loss/congestion × energy/scarcity decomposition;
  - block-bootstrap intervals, leave-one-day-out fragility and extremograms;
  - restatement at the FY2027 market price cap;
  - diurnal profiles;
  - corrected flow–spread dependence.
- **Mechanisms.** Counter-price and forced-flow residue, negative-residue-management flags, constraint attribution and an outage-plan information test.
- **Loop rule.** The AEMC net-trade rule (ERC0386) is implemented, tested against the determination's worked examples, and applied to history.
- **Valuation tests.** Walk-forward baselines against the clearing price, a regime spread-option benchmark, measured sensitivities, a dated scenario registry, and an offer-curve pilot.
- **Formulas.** Typeset with KaTeX at build time. Every number in the text is generated from `evidence/headline_numbers.json`.

## Not yet observed

AER base-futures data: the AER website refuses automated retrieval. Save the chart exports listed in `data/external/README.md` into `data/external/aer_futures/`, then run:

```text
python -m nemic.valuation market valuation
python build_html.py
```

Exhibits N6 and N7 and the futures-scaled baseline will then populate. $300 cap quotes are not in AER data. The empirical market energy/scarcity decomposition therefore needs licensed ASX data.

## Rebuild

From the repository root:

```text
python -m nemic.valuation all        # acquire (cached), panel, baseline, settlement, evidence, market, mechanisms, valuation
python -m pytest -q tests/test_valuation_settlement.py tests/test_valuation_evidence.py
```

From this folder:

```text
cd tools && npm ci && cd ..          # pinned KaTeX 0.16.22 and Marked 15.0.12
python make_figures.py               # Figure 1
python build_html.py                 # renders research_report.md from the template, then the HTML
node qa_report.cjs [PATH_TO_NODE_MODULES_WITH_PLAYWRIGHT]
```

Other files:

- `report_manifest.json` records line-ending-normalised SHA-256 hashes of the inputs, evidence, code and output.
- `evidence/data_audit.json` records coverage, flags, FIRM status and input-table hashes.
- Raw AEMO archives stay local under `data/` and are not committed.

## Status

This is research evidence, not a live forecast or trading signal. Limits are listed in Chapter 32 of the report.
