## Appendix B · Data Schema, NOS Lineage, and Reproducible Build Commands

All raw AEMO Network Outage Scheduler (NOS) files, local parquet caches, and repository module filenames are consolidated in this technical appendix while preserving clean institutional prose in Chapters 1 through 7.

### B.1 Local archive inputs (zero new NEMWEB downloads)

| Analytical module | Local repository path | Upstream source & coverage |
|---|---|---|
| C7a matched pairs (6 links) | `data/nos_binding_v1/pairs__{VIC1-NSW1,NSW1-QLD1,V-SA,N-Q-MNSP1,V-S-MNSP1,T-V-MNSP1}.parquet` | Exact `kind == 'actual'`, `level == 'K2'` treated-control half-hour matches (`2024-09` to `2026-08`) |
| C7a baseline MW & MV tables | `reports/nos_outage_regime_research_20260924/downloads/{nos_family_effects,nos_binding_marginal_value,nos_booking_reliability}.csv` | Compact audited outputs from `scripts/run_nos_regime.py` and `scripts/run_nos_binding.py` |
| C7b walk-forward outlook panel | `data/nos_binding_v1/outlook/backtest_scored.parquet` | 126,582 scored rows across 12 chronological monthly origins (`2025-09-12` to `2026-08-14`), 2 layers, 4 lead bands, 6 links x 2 directions |
| C7b live forward snapshot | `reports/nos_outage_regime_research_20260924/downloads/{nos_outlook_outages.csv.gz,nos_outlook_weekly.csv}` | Latest forward NOS booking snapshot (`PUBLIC_NETWORK_20260911000007`) |
| C8 family occupancy matrix | `data/nos_regime_v1/family_coverage_30min.parquet` | 35,040 half-hours x 237 constraint-set families across the 24-month panel |
| C9 50-line cohort & events | `reports/line_outage_risk_v1/downloads/{cohort,events,event_summary,mechanism_summary,falsification,interconnector_event_response}.csv` | 50 monitored transmission lines (631 verified outage events) across NSW1, VIC1, QLD1, SA1, TAS1 |
| Regional prices, IC limits & SRA residues | `data/valuation_v2/panel/{prices,interconnectors}.parquet`, `data/valuation_v2/settlement/directional_5min.parquet` | Native five-minute `DISPATCHPRICE`, `DISPATCHINTERCONNECTORRES`, and settled directional SRA residue ledger |

### B.2 Generated compact evidence files (`reports/outage_risk_handbook_v2/evidence/`)

1. `nos_economic_effects.csv` (697 rows): matched `$/MWh` spread, `$/day` SRA residue, 7-day block-bootstrap 95% CIs, MW capacity effects, binding `|MV|`, and `well_supported` flag.
2. `nos_outlook_calibration.csv` (96 rows): per-cell (`layer x lead_band x link x direction`) OOS Brier scores, Brier skill vs normal/last-year, and raw vs calibrated skilful indicators.
3. `nos_reliability_curves.csv` (32 rows): raw vs calibrated reliability curves across 8 probability bins for both binding and setter layers.
4. `nos_live_outlook_calibrated.csv` (150 rows): top forward outage weeks ranked by full-history isotonic-calibrated binding probability.
5. `nos_n11_superadditivity.csv` (338 rows): tested concurrent family pairs across all 6 links with standalone, additive, observed joint, and super-additive MW & spread deltas + 95% CIs.
6. `line_corridor_pooled_risk.csv` (8 rows): hierarchical corridor-level Empirical-Bayes capacity, price, spread, and binding `|MV|` summaries.
7. `line_50_directory.csv` (50 rows): complete 50-line directory comparing raw vs Empirical-Bayes corridor-pooled risk and shrinkage weights.
8. `line_deep_dives_6_8.csv` (5 rows): Southern NSW 330 kV peer benchmark for `CANBERRA/LINE/6` and `DAPTO/LINE/8` including event-aligned VNI flow and limit shifts.
9. `nos_booking_reliability_summary.csv` (12 rows): withdrawal, invocation, start/end drift, early-return, and overrun rates across 6 links x 2 study years.
10. `headline_numbers.json`: 53 single-source-of-truth macro numbers checked by unit tests.

### B.3 Deterministic rebuild and verification commands

```powershell
# 1. Recompute all C7-C9 compact CSVs and headline numbers
python -m nemic.experiments.outage_risk_v2

# 2. Assemble Flagship Edition B self-contained HTML + SHA-256 build manifest
python reports/outage_risk_handbook_v2/build_html.py

# 3. Run Wave 2 unit and accounting-invariant tests
python -m pytest -q tests/test_outage_risk_v2.py

# 4. Run headless Playwright desktop/mobile QA
node reports/outage_risk_handbook_v2/qa_report.cjs
```
