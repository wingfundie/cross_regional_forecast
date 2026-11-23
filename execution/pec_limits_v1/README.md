# Reproduce the EnergyConnect directional-limit study

The run is complete when the dated dispatch window has an explicit gap audit, the two directional targets and their equation evidence reconcile, the as-of replay accounts for every origin and lead, and the report, lookup tables, and three scenario modes pass verification.

1. Acquire the original five-minute dispatch reports and reconcile any retained extracts.
2. Match reported setters to dispatch equation versions, constraint sets, outage records, and market notices. Check reconstructed limits against AEMO's reported limits.
3. Evaluate chronological forecast baselines and challengers where issue and publication evidence permit. Count the requested rows that remain unsupported.
4. Build the report, conditional tables, and scenario tool from the checked data. Check file hashes, links, offline use, and desktop and mobile layouts.

From the repository root, run `python -m nemic.experiments.pec.campaign --end-day 2026-11-22`. On Windows, use `python3.11` if that is the installed launcher. Omit `--end-day` to use the previous calendar day in fixed UTC+10. NEMWEB's current directories rotate. Retain the downloaded files and metadata to reproduce the exact original vintages.

The study writes native dispatch evidence and source archives under `data/pec_limits_v1`. Open `local_exports/pec_limits_v1/index.html` for the report or `local_exports/pec_limits_v1/scenario.html` for the scenario tool. Relative download links resolve against the adjacent `downloads` directory. Both pages run offline.

Use `--stage acquire` for dispatch, monthly standing data, and network records. `--stage observations` rebuilds the directional series and constraint evidence from the retained files. `--stage issued` collects and normalizes original forecast files and the separately labelled predispatch archive replay. Run `--stage forecast`, `--stage scenario`, and `--stage report` to rebuild the corresponding products. The daily outlook covers 168 hours. The coverage table records gaps beyond an AEMO product's last available delivery interval.

In the scenario tool, choose an observed configuration and NEM delivery period. Leave regional MW values blank for the configuration reference, fill them for a historical comparison, or use an observed day. Use the CSV template or export a historical day to supply a half-hour path. The tool displays sample counts, observed setters, quantiles, and day-block confidence intervals where supported. A historical comparison describes AEMO's dispatch limits in the observed sample. Secure physical transfer capability requires separate power-system analysis.

Run `python -m pytest -q` and `python -m nemic.experiments.pec.campaign --stage verify` for the repository and evidence checks. Run `python -m nemic.experiments.pec.verify_report --browser` with Playwright and an available Chromium browser for visual and offline checks. The local decision trail is in `data/pec_limits_v1/decisions.tsv`.

Read the [results summary](RESULTS_SUMMARY.md) for the executed study and its published aggregate evidence.
