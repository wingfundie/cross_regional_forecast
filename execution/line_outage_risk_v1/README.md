# Transmission-line outage risk research

This implements the agreed public-data campaign: September 2024–August 2026, up to 50 line profiles, ten deep dives including Capital–Canberra line 6 and Dapto–Marulan line 8, all six interconnectors, five regional prices, and a 90-day outlook plus annual watchlist.

The completed run is documented in [RESULTS_SUMMARY.md](RESULTS_SUMMARY.md), with its final artifact hashes and evidence gates in [completion.json](completion.json). Open the [HTML report](../../reports/line_outage_risk_v1/index.html) or [Markdown companion](../../reports/line_outage_risk_v1/REPORT.md).

Run `python scripts/run_line_outage_research.py --stage all`. Each stage is owned in `ledger.sqlite`; a healthy owner prevents duplicate execution. Manifests hash source, configuration, methodology, inputs and outputs. `--stage report` rebuilds presentation from cached evidence. `--force` invalidates the named stage deliberately.

Generated interval panels, offers, checkpoints and reports remain local. No production bundles or routes are modified. Read [METHODOLOGY.md](METHODOLOGY.md) for estimands and evidence gates. The generated report is `reports/line_outage_risk_v1/index.html` with its Markdown companion and evidence downloads. Completion requires the campaign ledger, source audit, statistical checks, full repository tests and report validation; execution of the runner alone is not sign-off.

Install report dependencies with `python -m pip install -r requirements-line-outages.txt`; install the headless renderer with `python -m playwright install chromium` if needed. Run `python scripts/verify_line_outage_report.py`, inspect the desktop/mobile screenshots in the report's `qa` directory, then record that completed inspection with `--record-inspection`. Run the campaign `validate` stage after recording it. QA is tied to the HTML hash; changing the report invalidates that inspection.

The equipment audit verifies exact NOS keys and ELEMENTID validity throughout each window. Concurrent-equipment controls include identified high-voltage lines, transformers, buswork and reactive plant. Constraint membership uses all 24 study-month changes and a bounded lookback to September 2022; remaining gaps are disclosed in `supplement_sources.json`. Importance screening is provisional corridor selection, not a verified physical-criticality ranking. The historical price-risk probe is conditional research and does not publish current numerical probabilities.
