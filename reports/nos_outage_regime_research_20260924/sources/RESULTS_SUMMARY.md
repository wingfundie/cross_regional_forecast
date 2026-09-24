# Results summary — NOS outage regime research (v1)

Completed 2026-09-24. Comprehensive standalone report: `reports/nos_outage_regime_research_20260924/index.html` (`python scripts/build_nos_outage_report.py`). The report section is **Outage regimes** in `reports/all_interconnector_regime_research_20260921/index.html#outages`. Downloads are prefixed `nos_`, and the manifest is v2 (the v1 manifest is archived as `build_manifest_v1.json`; all 16 v1 outputs are hash-identical).

## Coverage by connector

| name       |   relevant |   median_match |   placebo_clean |   supported |   lookup_assets_supported |   asset_level_entries |
|:-----------|-----------:|---------------:|----------------:|------------:|--------------------------:|----------------------:|
| QNI        |         51 |           0.94 |            0.75 |          20 |                        58 |                    19 |
| Directlink |         28 |           0.96 |            0.83 |          16 |                        47 |                    12 |
| VNI        |        107 |           0.86 |            0.72 |          26 |                       101 |                    27 |
| Heywood    |         87 |           0.87 |            0.74 |          28 |                        96 |                    32 |
| Murraylink |        118 |           0.84 |            0.80 |          36 |                       109 |                    36 |
| Basslink   |         19 |           0.99 |            0.94 |           9 |                        33 |                     9 |

## Largest supported limit changes

| name   | direction   | GENCONSETID         |   effect_capacity |   ci_lo_capacity |   ci_hi_capacity |   episodes |   treated_hours |
|:-------|:------------|:--------------------|------------------:|-----------------:|-----------------:|-----------:|----------------:|
| QNI    | reverse     | N-ARSR_8E           |              -656 |             -751 |             -583 |         10 |             990 |
| QNI    | reverse     | N-DMSR_8J           |              -635 |             -700 |             -559 |          9 |             728 |
| QNI    | reverse     | N-TWUL_85           |              -620 |             -701 |             -507 |          5 |             343 |
| QNI    | forward     | N-TWUL_85           |              -570 |             -651 |             -472 |          5 |             343 |
| QNI    | reverse     | N-ARDM_8C           |              -534 |             -583 |             -473 |         21 |            1640 |
| QNI    | forward     | N-ARSR_8E           |              -506 |             -538 |             -457 |         10 |             990 |
| QNI    | forward     | N-ARDM_8C           |              -447 |             -496 |             -385 |         21 |            1640 |
| VNI    | forward     | I-BURC              |               365 |              142 |              508 |         16 |             158 |
| QNI    | reverse     | N-X_8E+DM+TW+LS_SVC |              -349 |             -397 |             -231 |          5 |              26 |
| VNI    | forward     | N-DTKV_18_WG_CLOSE  |              -291 |             -553 |             -142 |          5 |              60 |

## Caveats found during validation
- The placebo test is clean for 71–100% of eligible families (VNI lowest). Families that fail it are excluded from "supported".
- Some booked-only / withdrawn-booking falsification medians are not near zero: Heywood withdrawn −35 MW, QNI withdrawn −38 MW, VNI booked-only −20 MW.
- The booked→invoked rate (~100%) is close to built in, because final-state MMSDM records link the sets that were used.
- K4 coordinates come from an OpenStreetMap name crosswalk (68% of assets). Geoscience Australia was unreachable, and ISP sub-regions were not used.

## Rebuild
```
python scripts/run_nos_regime.py --stage acquire|episodes|state|keys
python scripts/run_nos_regime.py --stage compare --tag full     # ~40 min
python scripts/build_nos_regime_section.py                        # presentation only
```
