# 10 October 2026 study — execution summary

The local investigation and report are complete with the coverage limitations below. Open [the offline report and explorer](reports/index.html), or [the Markdown companion](reports/REPORT.md). Keep `reports/downloads/` beside the HTML for the downloadable evidence.

- Scope: NSW, QLD and VIC coal, gas and battery energy offers; 288 five-minute trading-day intervals.
- Coverage: 117 identifiable plants, 188 registered DUIDs, and 11,624 post-signal DUID/direction revisions changing future delivery intervals.
- Reconstruction: zero missing accepted-offer links and zero band-volume/maximum-availability discrepancies against dispatch-effective Bidmove records. Effective daily price ladders also reconcile.
- Verification: all 27 evidence/report validation gates and 21 offline browser checks passed. Desktop and mobile screenshots were reviewed, including horizontal scrolling of dense charts and the ten-portfolio summary. The full repository suite passed: 229 tests, with 12 existing numerical warnings; the nine study tests also passed separately.

The opening portfolio digest now covers AGL, EnergyAustralia, Origin, Alinta, Delta, CleanCo, Stanwell, Snowy, CS Energy and Callide Trading. It contains 22 selected rebid examples with native prices, MW changes, exact reasons and explorer links, followed by physical highlights and portfolio implications. Corporate and contractual asset links are explicit; Callide Trading is separate from CS Energy and Loy Yang B is not presumed to share Alinta bidding control.

Mount Piper 1 explicitly cited the VOLL event in its 07:17:45 rebid. It shifted existing capability into lower-priced bands without increasing declared maximum availability. The spike interval's dispatch target preceded that revision. Tallawarra A's afternoon return was already present in the pre-signal AEMO projection, so total generation cannot all be classified as a new response to the morning spike. The report separates that existing projected path from additional output and simultaneous portfolio replacement.

Registration uses retained AEMO July tables and September-effective unit details because the identified 9 October workbook could not be downloaded from the AEMO website. New or unmapped assets and changed trading rights remain a coverage limitation. SCADA is complete for 149 DUIDs, partial for one, and absent for 38; absent observations are not zero. Historical dissemination/receipt times are unverified, FCAS is excluded, and neither causal effects nor private financial hedge positions are estimated.

Machine-readable execution evidence is in `state/validation.json`, `state/browser_qa.json`, `state/repository_tests.json`, `state/reconstruction.json`, and `state/report_manifest.json`. Source URLs, hashes, native reasons and analytical evidence are retained in the local downloads and data directories. No publication was performed.
