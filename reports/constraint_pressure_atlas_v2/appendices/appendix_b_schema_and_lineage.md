## Appendix B · Data Schema, MMS Lineage, and Reproducible Build Commands

All raw AEMO Market Management System (MMS) table names, local archive directory structures, and repository module filenames are consolidated here to keep the analytical prose clean while preserving full engineering auditability.

### B.1 Local archive inputs and AEMO MMS lineage

No new NEMWEB downloads were required for Wave 1. Every table and exhibit in Flagship Edition A and Event Atlases v2 is computed deterministically from verified local archives already retained on disk:

| Analytical domain | Local repository path | Upstream AEMO MMS tables & coverage |
|---|---|---|
| Six-link five-minute constraint attribution | `data/constraint_{vni,qni,vsa,basslink,directlink,murraylink}_2y/months/YYYY-MM/` | Derived from `DISPATCHINTERCONNECTORRES`, `DISPATCHCONSTRAINT`, `DISPATCHLOAD`, `GENCONDATA`, `SPDINTERCONNECTORCONSTRAINT`, and `SPDCONNECTIONPOINTCONSTRAINT` (24 months: `2024-09` through `2026-08`; 7 parquet files per month per link) |
| Standing unit metadata & BESS flags | `data/constraint_vni_2y/standing/DUDETAILSUMMARY.parquet` | AEMO `DUDETAILSUMMARY` (`DISPATCHTYPE == 'BIDIRECTIONAL'` identifies grid-scale BESS; `FUEL_TYPE` / `STATIONNAME` maps hydro, solar, wind, coal, and gas) |
| Regional five-minute dispatch prices | `data/valuation_v2/panel/prices.parquet` | AEMO `DISPATCHPRICE` (2,592,000 region-intervals across `NSW1`, `QLD1`, `SA1`, `TAS1`, `VIC1`) |
| Settled directional SRA residues | `data/valuation_v2/settlement/directional_5min.parquet` | Five-minute interregional settlement residue panel aligned to AEMO SRA settlement buckets (negative residue attribution in Chapter 6) |
| Legacy Event Atlas payloads (read-only inputs) | `docs/html/{vni,qni,vsa}_event_atlas.html` and `reports/{vni,qni,vsa}_event_atlas_v1/` | Unmodified source case payloads compressed into `reports/event_atlases_v2/` |

### B.2 Generated compact evidence files (`reports/constraint_pressure_atlas_v2/evidence/`)

All ten compact CSV tables and the single-source-of-truth headline registry are committed cleanly to Git (raw parquet caches and fitted models remain local and Git-ignored):

1. `six_link_parity_summary.csv` — 12 rows (6 links x 2 directions): capacity quantiles, tight-headroom %, forced-limit %, contraction episodes, reconstruction MAE, mean tight spreads, and binding totals.
2. `parallel_link_cobinding.csv` — 4 rows: simultaneous tight-headroom co-binding for QNI+Directlink and Heywood+Murraylink in forward and reverse directions.
3. `reconstruction_mae_audit.csv` — 134 rows: full MAE decomposition by link, direction, setter family, and exact `setter_matched` status.
4. `diurnal_seasonal_ci_profiles.csv` — 192 rows: 6 links x 2 directions x 4 seasons x 4 diurnal blocks with 7-day block-bootstrap 95% confidence intervals.
5. `contraction_lhs_rhs_switch.csv` — 12 rows: full-population 3-way MW and episode decomposition across all 44,185 sharp contractions.
6. `cross_link_cascades.csv` — 36 rows: complete 6x6 ordered cascade conditional probabilities, baselines, and lift ratios (+/-30 min window).
7. `nrm_clamping_attribution.csv` — 12 rows: forced-negative interval counts, counter-price shares, explicit NRM/ramp setter shares, and settled negative SRA residues.
8. `duid_economic_influence.csv` — 270 rows (top 45 units per link): mechanical vs tight-headroom vs congestion-rent-weighted rankings, rank shifts, and diurnal shares.
9. `constraint_economic_influence.csv` — 240 rows (top 40 equations per link): binding intervals, leading intervals, mean `|MV|`, and cumulative 24-month shadow rent (LP `*_ZERO` penalty rows excluded).
10. `bess_ramp_signature.csv` — 42 rows (6 links x 7 technology classes): active DUID counts, mechanical/rent/onset shares, and P95 5-minute impulse MW.
11. `headline_numbers.json` — 270 verified macro strings rendered directly into the report summary and checked by unit tests.

### B.3 Deterministic rebuild and verification commands

Run from the repository root (`C:\Users\HomePC\Documents\ChatGPT\IC FLOW FORECASTING`):

```powershell
# 1. Recompute all C1-C6 compact CSVs and headline numbers from local 24-month archives
python -m nemic.experiments.constraint_pressure_v2

# 2. Build compressed standalone Event Atlases v2 + Virtual Barrels Markdown companions
python -m nemic.experiments.event_atlas_v2

# 3. Assemble Flagship Edition A self-contained HTML + SHA-256 build manifest
python reports/constraint_pressure_atlas_v2/build_html.py

# 4. Run unit & accounting-invariant tests
python -m pytest -q tests/test_constraint_pressure_v2.py

# 5. Run headless Playwright desktop/mobile QA (including Event Atlas gzip smoke checks)
node reports/constraint_pressure_atlas_v2/qa_report.cjs
```
