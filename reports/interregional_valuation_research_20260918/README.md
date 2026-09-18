# Quarterly interregional valuation research

Open `Quarterly_Interregional_Valuation_Research.html` in a modern browser. It is the final deliverable. Charts, styles, JavaScript, research text and six data/text downloads are embedded, so the report works offline. External academic and market-rule links require an internet connection.

The presentation adapts the navy title band, white research pages, compact side notes and numbered exhibits of the two PDFs supplied by the user. It does not reproduce the reference issuers' identities or their oil research.

## Scope and dates

- Research cutoff: 18 September 2026.
- Historical archive: five-minute intervals ending after 1 September 2024 00:00 and through 1 September 2026 00:00, fixed NEM time (UTC+10).
- Interactive historical exhibits: seven complete quarters, 2024 Q4 through 2026 Q2. September 2024 and July–August 2026 partial quarters remain explicitly identified in the downloadable data.
- Quotes in the research retain their observation dates. The interactive valuation workbench starts with hypothetical inputs and is not connected to a live market feed.
- The historical flow diagnostic is not an SRA settlement calculation. No future quarterly valuation model or trading strategy has been fitted or backtested as part of this research document.

## Rebuild the HTML from frozen results

Run from this directory:

```text
python build_html.py --node PATH_TO_NODE --marked PATH_TO_MARKED_ESM
```

Python requires Plotly and Beautiful Soup. The defaults locate the Codex bundled Node and Marked runtime on this computer. `report_theme.py` and `report.css` are project-local copies of the editorial report helper; `institutional.css` adapts the layout to the user-supplied references. `report_interactions.js` implements the three exhibits and research navigation. The build does not acquire new prices or update research claims.

`report_manifest.json` records the build time, research/data cutoffs, input hashes, output hash and dependencies. `research_report.md` is the full research source. `analyse_history.py` calculates the historical results from the existing project price and flow archives; it additionally requires pandas and pyarrow. Review its repository input paths before running it on another machine.

## Verification

`qa_report.cjs` uses Playwright to check the offline report, all six directions across seven quarters, region controls, payoff identities, sensitivity calculations, input errors/reset, citation navigation, full-text chapter search, embedded downloads and desktop/mobile overflow. It saves screenshots and `qa/browser_checks.json`. The QA PDF is only a print-layout check; the requested final deliverable is HTML.

```text
node qa_report.cjs PATH_TO_NODE_MODULES
```

The layout must also be visually reviewed. The report includes the full research, rather than only a chart dashboard or summary. Existing production forecasting code and datasets are unchanged.
