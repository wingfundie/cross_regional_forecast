# Interregional valuation v2: work history

Campaign: `interregional_valuation_v2`.
- Plan: `C:\Users\HomePC\.claude\plans\create-a-plan-to-tingly-minsky.md`, approved 26 September 2026.
- Review being addressed: `reports/interregional_valuation_research_20260918/review.md`.

Decisions:
- Futures data: public AER only.
- History: October 2021 onward.
- Output: a new v2 folder.
- Maths: KaTeX, rendered server-side.

Machine-readable stage events go to `events.jsonl` and `status.json` in this folder (git-ignored). This file is the human-readable log, updated as work proceeds.

## 2026-09-26 — Phase 0: scaffold

- Created `configs/valuation/interregional_valuation_v2.json` with:
  - the window: 2021-10-01 exclusive to 2026-09-01 inclusive, UTC+10, interval-ending;
  - the pooled directional-interconnector map: VNI; QNI with Terranora; Heywood with Murraylink; Basslink;
  - fallback unit counts, taken from the review;
  - the list of MMSDM tables.
- Created the package `nemic/valuation/`:
  - `config.py`: paths, the stage ledger (`log`), line-ending-normalised hashing, and evidence CSV writer;
  - `acquire.py`: reuses `nemic.ingest` download and caching, plus a generic `extract_all` that keeps every I/D record of an MMSDM table;
  - `panel.py`: price and interconnector panels, with the APCFLAG bits decoded per the MMS data model;
  - `baseline.py`: port of the v1 `analyse_history.py`, extended with the corrected covariance terms;
  - `__main__.py`: the stage CLI.
- KaTeX 0.16.22 and Marked 15.0.12 pinned in `reports/interregional_valuation_research_v2/tools/package.json`, with the lockfile committed and `node_modules` ignored.
- **Regression gate passed.** The ported baseline rebuilds all four v1 CSVs from the v1 inputs with a maximum absolute difference of 0.0. An initial 7e-15 difference in `tail_proxy_pct` came from operation order and was fixed to match v1 exactly.

## 2026-09-26 — Phase 1: acquisition (in progress)

- `python -m nemic.valuation acquire` started. It back-fills DISPATCHPRICE and DISPATCHINTERCONNECTORRES for 2021-10 to 2023-08; September 2023 onward was already local. It also downloads, for 59 months:
  - the settlement residue table SETIRSURPLUS;
  - the SRA tables: RESIDUE_PUBLIC_DATA, AUCTION_IC_ALLOCATIONS, AUCTION_CALENDAR, AUCTION_TRANCHE, RESIDUE_CONTRACTS, RESIDUE_CON_FUNDS, RESIDUE_PRICE_FUNDS_BID, RESIDUE_TRK, AUCTION;
  - the network and settings tables: INTERCONNECTORCONSTRAINT, LOSSMODEL, LOSSFACTORMODEL, MARKET_PRICE_THRESHOLDS;
  - NEGATIVE_RESIDUE, which I found in the listings and added because it gives direct evidence of negative-residue management (NRM).
- **Acquisition complete.** 640 of 640 archive jobs, 0 failures. Tables extracted to `data/valuation_v2/tables/`. Price and flow back-fill for 2021-10 to 2023-08 written to `data/tables/` through `nemic.ingest.process_url`, which records hashes.
- **AER futures are not retrievable automatically.** The servers close the connection even with the project CA bundle. The manual-drop checklist is in `data/external/README.md`, and the loader is `nemic/valuation/aer.py`. The futures sections are labelled "not observed" until files arrive.
- **AEMC loop rule acquired.** The ERC0386 final determination (114 pages) was downloaded from aemc.gov.au into `data/external/aemo_docs/`. The net-trade method (sections 3.2.1–3.2.3) and worked examples (Figure 3.1, Appendix B Example 4) became test fixtures. The AEMC text states Figure 3.1's net loop IRSR as $3,500/h, but its arm allocations and payouts sum to $4,500/h; the tests use $4,500.
- **Panel built.** 517,248 five-minute intervals from 2021-10-01 to 2026-09-01. No price or flow gaps; no conflicting price versions; 305 NOT FIRM rows (August 2026 only); 20,922 physical-run (intervention) interconnector rows.
- **Baseline extended.** 19 complete quarters, 2021 Q4 to 2026 Q2. The v1 regression still gives a 0.0 difference.

## 2026-09-26 — Phase 2: settlement ledger

- Tests: `tests/test_valuation_settlement.py`, 6 passing. They cover the CEPA worked example ($250), the lossless and counter-price signs, AEMC Figure 3.1 (payouts $3,000 and $1,500), AEMC Example 4 secondary netting (VIC-SA $3,150), a net-negative loop paying nothing, and a NSW→VIC→SA pass-through paid to NSW-SA.
- Settlement engine: `nemic/valuation/settlement.py`.
  - The computed residue engine reconciles to AEMO's settled SETIRSURPLUS within 0.2% on the main directions (VIC→NSW, VIC→SA, QLD→NSW).
  - It diverges in counter-price-heavy directions (QNI NSW→QLD +39%, VNI NSW→VIC −26%) and on Terranora (about −120% signed).
- **Diagnosis:**
  - SETIRSURPLUS records the residue in the exporting region's row. MWFLOW there is metered interval energy in MWh, and LOSSFACTOR is losses in MWh.
  - Settlement uses metered energy, not dispatch targets, so the metered variant tracks much more closely: VNI within 0.03–6%, QNI QLD→NSW −0.1%.
- **Decision.** The realised payoff uses AEMO's settled residue directly (variant `settled`), pooled across assets per directional interconnector, taking the positive part per interval. The computed engine (dispatch, metered, loss share 0 or 1, lossless) is kept for counterfactuals and sensitivities.
- **Settled ledger primary.** Settled coverage is 99.94% of intervals. Basslink has no SRA settlement before July 2026. For 56 early quarter-directions, unit proportions fall back to the published maxima; the AUCTION_IC_ALLOCATIONS rows start later.

## 2026-09-26 — Phase 3: evidence base (`nemic/valuation/evidence.py`)

- **Audit** (`evidence/data_audit.json`). APCFLAG bits decoded: 1,883 administered-price-binding rows, 1,589 market-price-cap-binding rows and 5,201 price-scaling rows. 13,524 rows carry the suspension flag, including June 2022; excluding them moves quarterly spreads by at most $5.59/MWh. Input tables are hashed.
- **Loss/congestion.** The 2×2 decomposition is exact.
  - NSW−VIC: loss part $3.88, congestion $35.13/MWh; coupled at the loss factor in 49% of intervals.
  - Basslink (an MNSP) is almost never coupled, so it is reported but not decomposed.
- **Uncertainty.** 7- and 14-day block bootstraps, leave-one-day-out analysis and extremograms.
- **Market price cap.** Normalised to the FY27 cap of $23,200, taken from MARKET_PRICE_THRESHOLDS.
- **Other outputs.** Diurnal profiles and tail dependence.

## 2026-09-26 — Phase 4: market side (`nemic/valuation/market.py`)

- **Auctions against realised payoffs.** 2,040 tranche-direction rows; 1,332 delivered tranches joined to settled payoffs.
  - Value-weighted realised ÷ price is 1.51, with a 95% cluster bootstrap interval of 1.28–1.81.
  - By horizon: 1.28 at 1–2 quarters ahead, rising to 1.85 at 9–12 quarters.
  - Proceeds were $1.37bn against $2.07bn paid out to holders.
- **Hedging.** Over 256 weeks:
  - VICNSW removes 19% of the variance of a 1 MW NSW−VIC spread, and its stress MW-equivalent is 0.15.
  - VICSA removes 59%; QLDNSW removes 52%.
- **AER futures.** Not observed. The loader is ready; the relevant exhibits show a "not observed" panel.
- **Bid stacks.** Median bid-to-offer ratio 5.8; 34% of units offered went unsold.

## 2026-09-26 — Phase 5: mechanisms (`nemic/valuation/mechanisms.py`)

- **Counter-price residue.**
  - NSW→VIC negative residue is $169.8m, of which 98% arose under forced flow and 48% while NSW was above $300.
  - NRM flags come from NEGATIVE_RESIDUE, available from August 2024.
- **Constraint attribution** uses AEMO's naming heuristic. For NSW−VIC, transient-stability constraints are the largest contributor.
- **Outage-plan test.** Spearman correlation across 15 quarters: 0.35 (NSW−VIC), 0.38 (QLD−NSW), 0.60 (SA−VIC). Suggestive only.
- **Loop counterfactual** (dispatch held fixed).
  - VICNSW payout falls from $730.9m to $556.0m; SAVIC from $91.7m to $38.7m.
  - NSW-SA and SA-NSW would receive $315.8m.
  - Victoria is a pass-through region in 46% of intervals.
- **Scenario registry.** Dated structural changes; unit-count changes are taken from AUCTION_IC_ALLOCATIONS; project dates are marked "announced" and unverified.
- **Fix.** The CLI crashed printing a Unicode minus sign to the cp1252 console; it now prints ASCII JSON.

## 2026-09-26 — Phase 6: valuation tests (`nemic/valuation/valuation_tests.py`)

- **Walk-forward** (612 auctions). The clearing price has the lowest mean absolute error ($7,586) but is biased low by $3,130 per unit. Trailing rules score about $10k.
- **Regime Bachelier benchmark.** It overstates realised payoffs 1.5–4× because it treats flow and spread as independent.
- **Strategic pilot** (NSW and SA, 1,152 intervals). The results disagree by region: NSW offer curves are flatter when imports bind, SA's steeper. Reported as exploratory.

## 2026-09-26 — Phase 7: report v2

- **Report source.** `research_report.template.md` is rendered by `build_html.py` into `research_report.md`: version 1 chapters are included, 264 numbers come from `evidence/headline_numbers.json`, and the build fails on any unfilled placeholder.
- **Formulas.** 117 KaTeX formulas, rendered server-side with fonts inlined.
- **Charts.** `charts.py` builds the 27 new exhibits. The v1 exhibits gain a full/v1 window toggle and TAS routes; Exhibit 9 now uses the corrected covariance; the workbench is aligned with §27 and adds a cap-spread implied-hours output.
- **Figure 1.** Produced by `make_figures.py` (fixes m-06).
- **Browser QA** (`qa_report.cjs`) passes:
  - all 36 charts and 5 diagrams render;
  - 117 formulas with no KaTeX errors;
  - no raw `$$` and no unfilled placeholders;
  - 208 window, direction and quarter combinations reconcile;
  - workbench checks pass;
  - no desktop or mobile (390 px) overflow; no browser errors; no external requests.
- **Fixes during QA:**
  - KaTeX's hidden MathML layer overflowed on mobile (pinned left and clipped);
  - the QLDNSW "all weeks" hedge ratio was misleading and was replaced by 1/n*;
  - comma-separated citations are now linked;
  - evidence CSV precision was raised from 6 to 10 significant figures.
- **Tests.** `tests/test_valuation_evidence.py` adds 7 tests (13 valuation tests pass in total).
- **Docs.** v2 README written; one line added to the top-level README.

## 2026-09-26 — Final reproducibility run and close-out

- **Full-pipeline memory fix.** The combined `all` run ran out of memory in settlement: SETIRSURPLUS has 27M text rows. Two fixes:
  - `settlement.settled()` now reads a column subset per monthly part and caches `data/valuation_v2/settlement/settled_compact.parquet`;
  - the CLI runs each stage in its own subprocess when several stages are requested.
- **Rerun complete.** All stages rerun from cached data (exit 0). The headline auction ratio reproduces at 1.5134, with evidence now written at 10 significant figures.
- **Build is deterministic.** Two consecutive `build_html.py` runs give an identical output SHA-256. Browser QA passes. Output: `Interregional_Valuation_Research_v2.html`, 9.26 MB, 37 chapters, 117 formulas, 27 new plus 9 original interactive charts, and 5 diagrams.
- **Tests.** Full repository suite `python -m pytest -q`: 193 passed.
- **Open items:**
  - AER futures chart exports (manual download; see `data/external/README.md`);
  - the SRA Rules clause for the $10 minimum;
  - ASX cap quotes for an empirical market energy/scarcity decomposition.
- **Publication.** Nothing committed or pushed; publication was not requested.
