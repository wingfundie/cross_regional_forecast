## Appendix B · Data Schema, Archive Lineage, and Reproducible Build Commands

All local parquet caches, upstream report exports, and repository code paths used in Wave 3 are listed here to keep Chapters 1 through 6 free of raw filenames while preserving deterministic auditability.

### B.1 Local archive inputs (zero new NEMWEB downloads)

| Analytical module | Local repository path | Coverage & provenance |
|---|---|---|
| C10a observed PEC telemetry | `data/pec_limits_v1/dispatch_interconnectorres.parquet` & `half_hour.parquet` | 15,264 five-minute intervals / 2,544 half-hours (`NSW1-SA1`, 1 Oct to 23 Nov 2026) |
| C10b loop settlement panel | `data/valuation_v2/panel/{prices,interconnectors}.parquet` + `nemic/valuation/loop.py` | 210,240 five-minute intervals (`2024-09-01` to `2026-08-31`) across NSW1, VIC1, SA1, VNI, Heywood, Murraylink |
| C10c PEC issue-time forecasts | `data/pec_limits_v1/forecast_rows_{predispatch,stpasa}.parquet` | 48,336 Predispatch rows + 17,808 ST PASA rows across 5 models and 4 lead bands |
| Long-range 50-band verdict | `reports/forward_forecasting_verdict_20261005/downloads/{band_metrics,cell_results}.csv` | 50 horizon-band evaluations and 10 cell promotion decisions (`qni_vni_longrange_v1`) |
| Leakage-controlled clustering | `reports/qni_vni_clustering_v1/downloads/{forecast_effects,state_stability}.csv` | 362 fold-band-target-control effects (241 seven-day block rows) and 227 stability runs |
| Three-stack register | `docs/RESEARCH_REGISTER.json` | 10 registered workstreams across `original`, `experiments`, `valuation`, and `production` stacks |

### B.2 Generated compact evidence files (`reports/ic_forecasting_and_pec_v2/evidence/`)

1. `pec_observed_configs.csv` (4 rows): observed EnergyConnect commissioning regimes, time shares, tight limit quantiles, empirical utilisation ratios, and forced-negative rates.
2. `pec_southern_ring_coupling.csv` (13 rows): 5-minute setter equation taxonomy across NSW to SA and SA to NSW directions.
3. `pec_loop_settlement_bridge.csv` (4 rows): exact AEMC `ERC0386` net-trade loop settlement totals across all 6 directional SRA buckets for 0, 150, 350, and 800 MW PEC regimes.
4. `pec_issue_time_forecast_scores.csv` (54 rows): MAE, skill vs persistence, skill vs AEMO, and empirical interval coverage across Predispatch and ST PASA.
5. `longrange_band_verdict.csv` (50 rows): complete 50-band long-range MT PASA horizon scorecard.
6. `longrange_cell_decisions.csv` (10 rows): official baseline-retention verdicts across all 10 VNI/QNI targets.
7. `clustering_vs_controls.csv` (29 rows): aggregated seven-day block-bootstrap clustering MAE effects and Holm-Bonferroni significance counts.
8. `clustering_stability_summary.csv` (22 rows): mean `seed_ari` and `block_ari` across $k = 1 \dots 8$ for K-means and GMM on VNI and QNI.
9. `model_stack_governance_register.csv` (10 rows): clean architectural status and unresolved gates across all three stacks.
10. `headline_numbers.json`: 41 verified macro strings checked by unit tests.

### B.3 Deterministic rebuild and verification commands

```powershell
# 1. Recompute all C10 and forecasting/clustering synthesis CSVs
python -m nemic.experiments.ic_forecasting_pec_v2

# 2. Assemble Flagship Edition C self-contained HTML + SHA-256 build manifest
python reports/ic_forecasting_and_pec_v2/build_html.py

# 3. Run Wave 3 unit tests and full repository regression suite
python -m pytest -q tests/test_ic_forecasting_pec_v2.py
python -m pytest -q

# 4. Run headless Playwright desktop/mobile QA
node reports/ic_forecasting_and_pec_v2/qa_report.cjs
```
