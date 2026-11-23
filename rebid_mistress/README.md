# Rebid Mistress

Independent energy-rebid forensic study of the 10 October 2026 NEM trading day, 04:00–04:00 UTC+10. NSW, QLD and VIC; coal, gas and batteries. No forecasting bundles, live service, FCAS analysis, causal estimates or financial hedge estimates.

Open `reports/index.html`; keep `reports/downloads/` beside it for the evidence exports. The HTML itself embeds its charts, styles and searchable revision explorer. `reports/REPORT.md` is the Markdown companion.

The opening **Portfolio highlights** section contains condensed accounts for AGL, EnergyAustralia, Origin, Alinta, Delta, CleanCo, Stanwell, Snowy, CS Energy and Callide Trading. Each separates key rebids (native prices, MW and verbatim reasons), physical output and portfolio implications. Offer links open the matching explorer record. The same accounts appear in the Markdown report, with selected rebids, asset membership, observations and corporate-source links exported beside the report.

`portfolio_digest.py` records the editorial selections and supplementary corporate/contract links. These reading-guide links do not silently expand the later registered-controller replacement pools. Callide Trading remains separate from CS Energy, and Loy Yang B is identified as commercially related to Alinta without asserting common bidding control.

## Run

From the repository root:

```powershell
python rebid_mistress/run.py --stage all
python rebid_mistress/run.py --stage report
python rebid_mistress/browser_qa.py
python rebid_mistress/run.py --stage validate
python -m pytest -q
```

The runner supports acquire, reconstruct, analyse, report and validate. Checkpoints record dependency/output hashes; a process lock prevents concurrent runner ownership. Data are cached locally; report-only work does not acquire or recalculate market data. Browser QA must pass and screenshots must be visually reviewed before the final validation gate can pass. `state/status.json`, stage checkpoints, reconstruction audit, report manifest and validation JSON are the execution evidence.

The initial acquisition reuses retained AEMO registration archives from the parent lab; their hashes and snapshot limitations are recorded. The 9 October registration workbook is identified but its AEMO website download was blocked. Event files are exact AEMO originals, not synthetic examples. Standing inventory freshness is disclosed separately from event-data coverage.

## Structure and interfaces

- `config.json`: fixed study day, signal proxy, regions, dollar thresholds and 5 MW response threshold.
- `core.py`, `acquire.py`, `context.py`: scoped downloads, native CSV/schema reader, local registration evidence, forecasts and notices.
- `reconstruct.py`: full accepted-offer arrays, exact same-delivery revisions, snapshots and dispatch-effective reconciliation.
- `analyse.py`: observed/target/frozen-forecast timelines, unit accounts and region-specific portfolio comparisons.
- `report.py`, `explorer.js`, `theme/`: cached-data report and self-contained interactive explorer.
- `validate.py`, `browser_qa.py`, `tests/`: evidence gates, browser checks and temporal/portfolio tests.

Native records preserve original field names. Derived tables use `DUID`, `direction`, `offer_id`, `offer_time`, `delivery` and explicit `_mw` measures. `offer_id` is a local stable reference into the retained daily header ledger, not an AEMO identifier. `segments` compresses contiguous identical before/after states without discarding changed intervals. Accepted headers and original sparse offers remain downloadable for complete reconstruction.

Data, arrays, generated reports, logs and state stay local under the directory’s `.gitignore`. Source and compact documentation can be version-controlled when publication is requested.

See [METHODOLOGY.md](METHODOLOGY.md) for interpretation rules and limits. A successful execution with disclosed gaps does not establish that all public registry metadata were current or that inferred motives are proven.
