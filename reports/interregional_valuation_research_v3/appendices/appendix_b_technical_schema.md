## Appendix B Technical schema, AEMO table mapping, and reproducibility

To keep Chapters 1 through 12 free of raw database codes and file paths, this appendix maps every plain-English institutional reference in the main narrative to its exact AEMO MMSDM table, local evidence file, configuration contract, and command-line reproduction workflow.

### B.1 AEMO MMSDM source table mapping

| Plain-English reference in narrative | AEMO MMSDM table | Key fields used | Local archive coverage |
|---|---|---|---|
| Five-minute regional reference prices and status flags | `DISPATCHPRICE` | `SETTLEMENTDATE`, `REGIONID`, `RRP`, `INTERVENTION`, `PRICE_STATUS`, `APCFLAG`, `MARKETSUSPENDEDFLAG` | 90 monthly parquet partitions |
| Five-minute interconnector flows, limits, losses, and setters | `DISPATCHINTERCONNECTORRES` | `INTERCONNECTORID`, `MWFLOW`, `METEREDMWFLOW`, `MWLOSSES`, `MARGINALLOSS`, `EXPORTLIMIT`, `IMPORTLIMIT`, `EXPORTGENCONID`, `IMPORTGENCONID` | 90 monthly parquet partitions |
| Published AEMO settled inter-regional residue | `SETIRSURPLUS` | `SETTLEMENTDATE`, `SETTLEMENTRUNNO`, `PERIODID`, `INTERCONNECTORID`, `REGIONID`, `MWFLOW`, `LOSSFACTOR`, `SURPLUSVALUE` | 59 monthly files (latest run selected) |
| Dated interconnector loss shares | `INTERCONNECTORCONSTRAINT` | `INTERCONNECTORID`, `EFFECTIVEDATE`, `VERSIONNO`, `FROMREGIONLOSSSHARE` | 59 monthly files |
| Statutory market price cap, floor, and CPT schedule | `MARKET_PRICE_THRESHOLDS` | `EFFECTIVEDATE`, `VERSIONNO`, `VOLL`, `MARKETPRICEFLOOR`, `ADMINISTERED_PRICE_THRESHOLD` | 59 monthly files |
| Negative residue management activation flags | `NEGATIVE_RESIDUE` | `SETTLEMENTDATE`, `NRM_DATETIME`, `DIRECTIONAL_INTERCONNECTORID`, `NRM_ACTIVATED_FLAG` | 25 monthly files (from Aug 2024) |
| Public SRA tranche clearing results | `RESIDUE_PUBLIC_DATA` | `CONTRACTID`, `INTERCONNECTORID`, `FROMREGIONID`, `UNITSOFFERED`, `UNITSSOLD`, `CLEARINGPRICE`, `RESERVEPRICE` | 27 monthly files |
| Dated unit proportions, maximum units, and fees | `AUCTION_IC_ALLOCATIONS` | `CONTRACTYEAR`, `QUARTER`, `INTERCONNECTORID`, `FROMREGIONID`, `MAXIMUMUNITS`, `PROPORTION`, `AUCTIONFEE`, `VERSIONNO` | 40 monthly files |
| Auction dates, notification dates, and payment calendar | `RESIDUE_CONTRACTS`, `AUCTION_TRANCHE`, `AUCTION_CALENDAR` | `CONTRACTID`, `AUCTIONDATE`, `NOTIFYDATE`, `PAYMENTDATE`, `STARTDATE` | 23–42 monthly files |
| Anonymised aggregate auction bid stacks | `RESIDUE_PRICE_FUNDS_BID` | `AUCTIONID`, `CONTRACTID`, `INTERCONNECTORID`, `FROMREGIONID`, `UNITS`, `BIDPRICE`, `LINKEDBIDFLAG` | 21 monthly files |
| Generator energy offers (exploratory 4-day pilot) | `BIDPEROFFER_D`, `BIDDAYOFFER_D` | `DUID`, `BIDTYPE`, `PRICEBAND1..10`, `BANDAVAIL1..10`, `MAXAVAIL` | Streamed on demand (4/6 months absent) |

### B.2 Price flag bitmask decoding and constraint naming heuristic

AEMO's `APCFLAG` column encodes bit flags rather than a single status string [R2]: bit 1 (`1`) indicates an administered price cap or floor binding ({{apc_binding_rows}} rows); bit 2 (`2`) indicates VOLL override (10 rows); bit 4 (`4`) indicates market price cap or floor binding ({{mpc_binding_rows}} rows); bit 8 (`8`) indicates manual override (87 rows); and bit 16 (`16`) indicates inter-regional loss-factor price scaling ({{irlf_rows}} rows). All complete quarters contain {{not_firm_complete}} non-firm rows (`PRICE_STATUS = FIRM`).

Constraint-family attribution in Chapter 6 applies AEMO's standard identifier convention: `>>` denotes thermal limits, `^^` denotes voltage stability, `::` denotes transient stability, `<<` denotes oscillatory stability, `NRM` prefixes denote automated negative residue management, `#` denotes manual or ramp constraints, and `NIL` designates system-normal equations rather than outage-specific constraint sets.

### B.3 Version 3 evidence inventory and module ownership

| Evidence file (under `reports/interregional_valuation_research_v3/evidence/`) | Generating module | Primary chapter |
|---|---|---|
| `sra_ledger_quarterly.csv`, `sra_reconciliation.csv`, `sra_unit_registry.csv` | `nemic.valuation.settlement` | Ch. 2 |
| `sra_payoff_decomposition.csv`, `qni_south_reconciliation_diag.csv` | `nemic.valuation.v3_analytics` | Ch. 2 |
| `loop_counterfactual.csv`, `loop_diagnostics.csv`, `loop_attribution_waterfall.csv`, `loop_parametric_pec.csv`, `qni_dilution_check.csv`, `basslink_proforma_backcast.csv` | `nemic.valuation.mechanisms`, `v3_analytics` | Ch. 3 |
| `spread_decomposition.csv`, `regional_decomposition.csv`, `joint_regimes.csv`, `bootstrap_quarterly.csv`, `leave_one_day_out.csv`, `extremogram.csv`, `mpc_cpt_normalised.csv`, `diurnal_profile.csv`, `diurnal_regime_summary.csv` | `nemic.valuation.baseline`, `evidence`, `v3_analytics` | Ch. 4 |
| `loss_congestion_quarterly.csv`, `loss_curve_fits.csv`, `mlf_flow_sample.csv`, `flow_diagnostics_full.csv`, `tail_dependence.csv`, `negative_price_mechanics.csv` | `nemic.valuation.evidence`, `v3_analytics` | Ch. 5 |
| `counterprice_quarterly.csv`, `counterprice_days.csv`, `constraint_attribution.csv`, `constraint_top_setters.csv`, `outage_plan_predictive.csv`, `strategic_pilot.csv` | `nemic.valuation.mechanisms`, `valuation_tests` | Ch. 6 |
| `auction_panel.csv`, `auction_vs_realised.csv`, `auction_regime_sensitivity.csv`, `auction_tranche_drift.csv`, `auction_carry_returns.csv`, `auction_premium_heatmap.csv`, `auction_proceeds_vs_residue.csv`, `auction_microstructure.csv`, `auction_bid_curve_latest.csv`, `bid_stack_slippage.csv` | `nemic.valuation.market`, `v3_analytics` | Ch. 7 |
| `hedge_effectiveness.csv`, `hedge_weekly_points.csv`, `hedge_quarterly_and_components.csv`, `hedge_two_instrument_frontier.csv`, `loop_hedge_effectiveness.csv`, `futures_status.json` | `nemic.valuation.market`, `v3_analytics` | Ch. 8 |
| `walk_forward_v3_forecasts.csv`, `walk_forward_v3_scores.csv`, `walk_forward_by_direction.csv`, `walk_forward_by_horizon.csv`, `scenario_sensitivity.csv`, `scenario_registry.json`, `option_benchmark_v3.csv`, `option_sensitivity_v3.csv` | `nemic.valuation.valuation_tests`, `mechanisms`, `v3_analytics` | Ch. 9 |
| `headline_numbers.json`, `data_audit.json`, `mpc_schedule.json` | `nemic.valuation.v3_summary`, `evidence` | All chapters |

### B.4 Complete rebuild and verification commands

From the repository root, run the cached Tier A analytics, rebuild the summary ledger, and execute the full test suite:

```bash
python -m nemic.valuation all               # optional: rebuild cached v2 panel and base tables
python -m nemic.valuation.v3_analytics      # compute all 9 Tier A v3 tables into v3/evidence/
python -m nemic.valuation.v3_summary        # regenerate v3/evidence/headline_numbers.json
python -m pytest -q                         # verify settlement, evidence, v3, and repo tests
```

From `reports/interregional_valuation_research_v3/`, build the offline HTML report, run the browser QA suite, and verify Virtual Barrels prose lint:

```bash
python build_html.py
node qa_report.cjs
```

To enable the unobserved AER base-futures exhibits (`futures_paths.csv` and `futures_premia.csv`), save the manual AER chart exports documented in `data/external/README.md` into `data/external/aer_futures/`, then re-run `python -m nemic.valuation market`, `python -m nemic.valuation.v3_analytics`, and `python build_html.py`. Raw AEMO archives remain local under `data/` and are excluded from version control.
