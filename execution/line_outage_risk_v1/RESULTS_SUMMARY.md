# Completed line-outage research

The September 2024-August 2026 public-data campaign is complete. Read the [offline HTML atlas](../../reports/line_outage_risk_v1/index.html) or [Markdown report](../../reports/line_outage_risk_v1/REPORT.md). [completion.json](completion.json) records the final ledger, artifact hashes and evidence gates.

The report contains 50 line profiles, ten deep dives and 29 selected cases, including Capital-Canberra line 6 and Dapto-Marulan line 8. It retains all six interconnectors and all five regional prices at native five-minute resolution: 210,240 intervals per series and 730 complete NEM days per region. There are 631 merged asset-level outage events in the selected cohort; events across assets can refer to the same multi-equipment outage.

## Measured results

- Line 6 has two verified primary-equipment events. Its linked binding equations include Murray and Darlington Point voltage protection and a Snowy-NSW transient stability requirement. Line 8 has eight events; its observed mechanisms include Murray voltage protection and thermal protection involving other NSW circuits. These internal NSW lines influence interregional dispatch through coupled security equations.
- Own-set binding is observed for 27 selected assets. The audit retains 688 direct asset-set links and 7,375 equation links, including 1,144 unresolved definition links. Recovering a family somewhere in the archive does not resolve its historical membership at every event: 149 direct links lack recovered membership at their start. Another 4,128 of 7,572 event/interconnector/direction rows have unresolved own-set membership, including events without a verified direct set.
- All 3,500 regional price comparisons and 3,600 network associations are retained. No independent numerical price estimate passes the declared display gates; no primary price-movement test passes both chronological phases. In the confirmation year, no test meets combined event-count, matching and balance support. This does not establish zero physical or price effect.
- The highest NSW RRP across the retained line 6/8 events is A$317.33/MWh. Negative prices also occur. These descriptive measurements test the proposition that an outage necessarily creates an extreme regional price spike; they do not isolate a causal contribution or describe prices in every other region.
- All 40 required monthly bid-table archives parsed successfully, retaining 1,796,966 native selected records and 488 unit-case summaries. Twenty-six of 29 cases have sampled unit records; three have no mapped sampled DUID. Offers and rebid reasons are descriptive. Exact dispatch-stack attribution remains withheld.
- The frozen NOS snapshot contains 69 eligible bookings across the 90-day outlook and annual watchlist. Historical booking replay retains 659 rows, and the conditional price-risk probe retains 249 rows. Current numerical price probabilities are withheld because historical receipt provenance and independent calibration are unverified.

## Verification and permitted use

All twelve campaign stages are complete and their cached outputs were verified. Report validation passes native grids, signed reverse limits, source/output hashes, suppressed unsupported estimates, anchors, local downloads and offline dependencies. Chromium rendered all 13 charts without browser errors or document-wide overflow at 1440 x 1000 and 390 x 844. All 22 recorded screenshots were inspected, including horizontal scrolling on mobile. The Markdown companion renders 233 tables and preserves native text separators.

The final repository test run passes 220 tests with 12 existing valuation warnings; see [test_evidence.json](test_evidence.json). The report's visual evidence is recorded in [report_qa.json](report_qa.json).

Use this as retrospective mechanism research and a conditional booking-screening guide. Reported limits are dispatch-solution outputs, not maximum secure physical transfer capability. Importance selection is provisional corridor screening, not a verified engineering-criticality ranking. Exact switching configurations, full physical network-security counterfactuals, isolated causal price contributions and live calibrated price-risk probabilities are not established. No production forecast bundle or route was promoted, and no Git publication or deployment was performed.
