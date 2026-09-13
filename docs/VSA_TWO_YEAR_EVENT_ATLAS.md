# VSA two-year event atlas

Period: 2024-09-01 00:00:00 to 2026-08-31 23:55:00, fixed UTC+10. Method version: 1.1-event-atlas-1.

## Results

- 7,731 contraction detections; 5,450 grouped incidents.
- 77 selected detailed contraction cases, plus 9 price-only cases.
- 23 exact MPC region-interval observations; 2 contraction detections with receiving-region MPC in the following hour.
- 6,734 matched observational comparisons. Mean paired peak-price-jump difference: $18.29/MWh; day-block bootstrap interval $0.17 to $37.54. This is not causal.

[Interactive event atlas](html/vsa_event_atlas.html) · [Methodology](INTERCONNECTOR_EVENT_ANALYSIS_METHODOLOGY.md)

## Selected-case generator accounting

| DUID     |    net_mw |   tightening_mw |   relief_mw |   events |
|:---------|----------:|----------------:|------------:|---------:|
| KESSB1   | 2102.21   |         5741.33 |    3639.12  |       41 |
| LIMOSF11 | 1111.98   |         5122.02 |    4010.04  |       47 |
| KIAMSF1  | 1265.1    |         3805.24 |    2540.14  |       51 |
| SUNRSF1  | 1462.6    |         3469.78 |    2007.18  |       47 |
| BLYTHB1  | 1631.24   |         3036.58 |    1405.34  |       12 |
| WEMENSF1 |  582.756  |         2934.56 |    2351.81  |       49 |
| BANN1    |  845.736  |         2857.33 |    2011.6   |       49 |
| LIMBESS1 |  426.01   |         2790.38 |    2364.37  |       24 |
| BRYB1WF1 | 1004.64   |         2490.76 |    1486.12  |       19 |
| YATSF1   | 1052.16   |         2404.48 |    1352.32  |       51 |
| HPR1     |  793.69   |         2160.78 |    1367.09  |       18 |
| GSWF1B1  |  905.872  |         2087.31 |    1181.44  |       18 |
| KARSF1   | 1201.8    |         1924.18 |     722.38  |       51 |
| GSWF1A   |  510.885  |         1887.41 |    1376.52  |       18 |
| STWF1    | -304.991  |         1835.56 |    2140.55  |       47 |
| MUWAWF1  |  612.095  |         1835.18 |    1223.08  |       51 |
| BROKENH1 |  496.36   |         1440.07 |     943.707 |       47 |
| MUWAWF2  | -668.328  |         1342.62 |    2010.94  |       51 |
| MURRAY   | 1143.62   |         1322.36 |     178.745 |       20 |
| GANNSF1  |  -18.2092 |         1313.42 |    1331.63  |       49 |

These totals cover selected fixed-equation segments, not all two-year movements. Gross tightening and relief can offset. Aggregate totals deduplicate shared physical steps; individual cases may overlap. Switching is not attributed to generators in the new equation.

## Seasonal results

|   season_year | season   | direction   |   events |   median_drop_mw |   near_mpc_events |   mpc_events |   valid_hours |   events_per_1000h | season_label   |
|--------------:|:---------|:------------|---------:|-----------------:|------------------:|-------------:|--------------:|-------------------:|:---------------|
|          2024 | Spring   | lower       |      321 |          274.318 |                 0 |            0 |          2184 |            146.978 | 2024 Spring    |
|          2024 | Spring   | upper       |      390 |          195.398 |                 0 |            0 |          2184 |            178.571 | 2024 Spring    |
|          2025 | Autumn   | lower       |      431 |          260.938 |                 0 |            0 |          2208 |            195.199 | 2025 Autumn    |
|          2025 | Autumn   | upper       |      441 |          219.419 |                 0 |            0 |          2208 |            199.728 | 2025 Autumn    |
|          2025 | Spring   | lower       |      610 |          259.964 |                 0 |            0 |          2184 |            279.304 | 2025 Spring    |
|          2025 | Spring   | upper       |      513 |          280.52  |                 0 |            0 |          2184 |            234.89  | 2025 Spring    |
|          2025 | Summer   | lower       |      411 |          356.712 |                 0 |            0 |          2160 |            190.278 | 2025 Summer    |
|          2025 | Summer   | upper       |      378 |          266.604 |                 2 |            0 |          2160 |            175     | 2025 Summer    |
|          2025 | Winter   | lower       |      518 |          167.039 |                 0 |            0 |          2208 |            234.601 | 2025 Winter    |
|          2025 | Winter   | upper       |      724 |          295.507 |                 1 |            0 |          2208 |            327.899 | 2025 Winter    |
|          2026 | Autumn   | lower       |      574 |          223.297 |                 0 |            0 |          2208 |            259.964 | 2026 Autumn    |
|          2026 | Autumn   | upper       |      436 |          189.785 |                 0 |            0 |          2208 |            197.464 | 2026 Autumn    |
|          2026 | Summer   | lower       |      488 |          307.971 |                 0 |            0 |          2160 |            225.926 | 2026 Summer    |
|          2026 | Summer   | upper       |      447 |          241.068 |                 0 |            0 |          2160 |            206.944 | 2026 Summer    |
|          2026 | Winter   | lower       |      517 |          209.774 |                 0 |            0 |          2208 |            234.149 | 2026 Winter    |
|          2026 | Winter   | upper       |      532 |          208.416 |                 4 |            2 |          2208 |            240.942 | 2026 Winter    |

December is assigned to the following summer year, preserving two complete December-February summers. Autumn and winter also have two complete observations; spring covers September-November 2024 and 2025. Rates use valid hours.

## Evidence and limitations

The population IC and regional-price grids are complete. Raw unit/equation archives were recovered only for selected case and control windows, with checksums, row filters and cleanup records in data/event_vsa_2y/source_manifest.jsonl.

The decomposition preserves aggregate other-LHS movements, switch composites and discrepancies. Full equations may contain an unresolved Z term. No causal dispatch replay, welfare-cost calculation or forecast validation has been performed. Coal status is an initial-MW operating proxy; dated registered capacity is included where recovered, but complete planned/forced outage classifications are unavailable. Temperature is hourly reanalysis, not measured station telemetry. No external outage narrative is assigned automatically to VSA cases.

## Rebuild

```text
python -m nemic.event_atlas screen --config configs/event_vsa_2y.json
python -m nemic.event_atlas match --config configs/event_vsa_2y.json
python -m nemic.event_atlas recover --config configs/event_vsa_2y.json
python -m nemic.event_atlas coal --config configs/event_vsa_2y.json
python -m nemic.event_reconstruction --config configs/event_vsa_2y.json
python scripts/build_vsa_event_atlas.py --config configs/event_vsa_2y.json
```

Rendering uses retained evidence and performs no downloads. The acquisition stage enforces a 10 GB combined base-study/event-study storage guard and a 20 GB free-space reserve.

## Detailed reconstruction coverage

| event_id                |   exact_step_share |   complete_terms_share |   observed_tightening_mw |   generator_tightening_mw |   switch_composite_mw |   unresolved_mw |
|:------------------------|-------------------:|-----------------------:|-------------------------:|--------------------------:|----------------------:|----------------:|
| VSA-lower-20240917T2325 |           1        |               0        |                  829.628 |                640.045    |             147.328   |     6.71485e-06 |
| VSA-lower-20241017T0705 |           1        |               0.166667 |                  910.775 |                106.262    |             339.131   |    -1e-05       |
| VSA-lower-20241017T0920 |           1        |               0        |                 1005.34  |                 93.3884   |             325.925   |    -6.51163e-06 |
| VSA-lower-20241105T1500 |           0.666667 |               0        |                  663.729 |                378.74     |             307.182   |    31.0846      |
| VSA-lower-20241220T0635 |           0.9375   |               0.875    |                 1075.54  |                269.075    |             373.77    |    19.7766      |
| VSA-lower-20241230T2135 |           0.75     |               0.75     |                  855.229 |                765.151    |               0       |    27.6218      |
| VSA-lower-20250116T0855 |           0        |               0        |                 1107.14  |                  0        |               0       |  1107.14        |
| VSA-lower-20250205T0735 |           0.965517 |               0.758621 |                  517.548 |                791.954    |             116.786   |    90.8801      |
| VSA-lower-20250222T1735 |           1        |               0        |                  760     |               1023.27     |               0       |     1e-05       |
| VSA-lower-20250304T0730 |           1        |               0.954545 |                  947.939 |               1085.43     |              65.8714  |     0           |
| VSA-lower-20250414T0940 |           1        |               1        |                  443.914 |                532.385    |               0       |    -2.17722e-05 |
| VSA-lower-20250424T0825 |           1        |               1        |                 1051.64  |                853.6      |               0       |    -4.83763e-05 |
| VSA-lower-20250513T1350 |           1        |               0        |                 1044.99  |                 -0.89818  |             913.514   |    -1e-05       |
| VSA-lower-20250619T0530 |           1        |               0        |                  764.264 |                  4.19658  |             757.801   |     0           |
| VSA-lower-20250628T1315 |           1        |               0        |                  192.607 |                  5.36024  |             113.06    |     5.68434e-14 |
| VSA-lower-20250706T2245 |           0.923077 |               0.769231 |                  561.768 |                 -1.2407   |              79.1197  |   475.2         |
| VSA-lower-20250831T0930 |           1        |               1        |                  695.679 |                494.8      |               0       |     2.65823e-06 |
| VSA-lower-20250929T1055 |           1        |               0.909091 |                 1107.13  |                -98.6192   |            1107.13    |    -1.21941e-05 |
| VSA-lower-20251017T0940 |           1        |               1        |                  760.058 |                374.043    |               0       |     5.6962e-06  |
| VSA-lower-20251105T0530 |           1        |               0.75     |                  932.867 |                -83.1725   |             857.97    |     3.9485e-06  |
| VSA-lower-20251112T0635 |           1        |               0.947368 |                  853.406 |                344.979    |             197.157   |    -1.7037e-05  |
| VSA-lower-20251120T1315 |           1        |               0.965517 |                  905.982 |                 -0.424415 |             546.433   |     2e-05       |
| VSA-lower-20251217T1330 |           1        |               0.777778 |                  750.626 |                625.742    |              90.9813  |     3.7037e-06  |
| VSA-lower-20260119T1505 |           1        |               1        |                  531.678 |                429.962    |               0       |     1.2963e-05  |
| VSA-lower-20260218T0800 |           1        |               0.958333 |                  980.255 |                229.765    |             171.807   |     7.03704e-06 |
| VSA-lower-20260228T1255 |           1        |               0.8      |                  760.474 |                727.959    |              73.0149  |     1.11111e-06 |
| VSA-lower-20260310T1505 |           1        |               1        |                  690.282 |                573.537    |               0       |    -2.07407e-05 |
| VSA-lower-20260410T1335 |           1        |               0.833333 |                  673.457 |                255.021    |             185.024   |    -1e-05       |
| VSA-lower-20260513T0730 |           0.5      |               0.5      |                  563.726 |                  0.1788   |               0       |   563.548       |
| VSA-lower-20260519T1420 |           1        |               0.692308 |                  501.98  |               -396.734    |             143.284   |     0           |
| VSA-lower-20260604T1640 |           1        |               0        |                 1100.95  |                851.11     |               0       |     0           |
| VSA-lower-20260713T0720 |           1        |               0        |                  866.496 |               -693.121    |            1294.46    |     1e-05       |
| VSA-lower-20260728T1110 |           1        |               0.923077 |                 1243.42  |              -1497.75     |             917.534   |     2e-05       |
| VSA-lower-20260817T1105 |           1        |               1        |                  770.421 |               1085.45     |               0       |     1.74074e-05 |
| VSA-lower-20260826T0850 |           1        |               0.961538 |                  754.686 |                386.378    |             381.47    |     3.55556e-05 |
| VSA-upper-20240904T1715 |           0        |               0        |                  741.176 |                  0        |               0       |   741.176       |
| VSA-upper-20241017T1430 |           1        |               0        |                  552.358 |                807.797    |               8.81199 |    -2.16981e-05 |
| VSA-upper-20241026T1500 |           1        |               1        |                  127.786 |                  0        |               0       |     4.26326e-14 |
| VSA-upper-20241106T1440 |           1        |               0        |                 1128.09  |                  4.17227  |            1107.64    |    -6.11392e-05 |
| VSA-upper-20241217T0735 |           1        |               0        |                  691.628 |                  0        |             691.628   |     8.53107e-06 |
| VSA-upper-20241220T1615 |           1        |               0        |                  753.389 |                579.609    |              35.9777  |     2.84906e-05 |
| VSA-upper-20250102T1910 |           0.833333 |               0        |                  393.375 |               -117.913    |               0       |    19.9958      |
| VSA-upper-20250104T1335 |           1        |               0.5      |                  582.25  |                 21.757    |             559.956   |     6.57047e-05 |
| VSA-upper-20250201T1720 |           0        |               0        |                  676.115 |                  0        |               0       |   676.115       |
| VSA-upper-20250201T1810 |           0        |               0        |                  278.447 |                  0        |               0       |   278.447       |
| VSA-upper-20250207T1825 |           1        |               0        |                  819.068 |                415.97     |               0       |     6.45847e-05 |
| VSA-upper-20250317T1020 |           0.15     |               0.15     |                  593.298 |                  0        |               0       |   556.062       |
| VSA-upper-20250331T1910 |           1        |               0.857143 |                  672.722 |                 94.2912   |             562.64    |     8.28452e-06 |
| VSA-upper-20250426T1450 |           1        |               0.666667 |                  778.412 |                -40.2253   |             728.539   |     3.43096e-06 |
| VSA-upper-20250527T1225 |           1        |               0.5      |                  771.669 |                429.551    |             218.881   |    -5.45455e-06 |
| VSA-upper-20250605T0015 |           1        |               0        |                  291.788 |                142.708    |               0       |    -6.06061e-06 |
| VSA-upper-20250612T1830 |           1        |               0        |                  487.901 |                  0        |             487.901   |    -9.64249e-06 |
| VSA-upper-20250614T1910 |           1        |               0        |                  903.675 |                551.134    |             472.938   |     3.0303e-06  |
| VSA-upper-20250618T1835 |           1        |               0        |                 1037.39  |                659.485    |               0       |     6.81818e-05 |
| VSA-upper-20250627T1740 |           1        |               0        |                  828.318 |                781.801    |               0       |     2.87879e-05 |
| VSA-upper-20250719T1400 |           1        |               0        |                  800.653 |                648.856    |              76.221   |    -1.21569e-05 |
| VSA-upper-20250812T1010 |           0.75     |               0.75     |                  611.233 |                  5.10216  |               0       |   575.978       |
| VSA-upper-20250905T0815 |           1        |               0.266667 |                  548.127 |                229.683    |             298.871   |    -1.82227e-05 |
| VSA-upper-20250918T0920 |           1        |               0.4      |                  675.472 |                -12.9494   |             659.627   |     2.38054e-05 |
| VSA-upper-20251025T1230 |           1        |               0        |                  782.252 |                -37.6951   |             742.815   |    -6.46635e-07 |
| VSA-upper-20251103T0530 |           0.833333 |               0.666667 |                  797.972 |               -106.578    |             595.021   |    10.515       |
| VSA-upper-20251213T1610 |           1        |               0        |                  829.039 |                184.601    |             148.171   |     6.99813e-06 |
| VSA-upper-20260131T1545 |           1        |               0.210526 |                  744.315 |                -33.0852   |             734.111   |     1.47147e-06 |
| VSA-upper-20260201T1815 |           1        |               0        |                  628.853 |                  0        |             628.853   |     6.77966e-07 |
| VSA-upper-20260226T1455 |           1        |               0.833333 |                  219.755 |                 94.8253   |             -49.8333  |     1.47748e-05 |
| VSA-upper-20260313T0610 |           1        |               0        |                  483.272 |                 49.2331   |               0       |    -1.45607e-05 |
| VSA-upper-20260403T1720 |           1        |               0.857143 |                  667.992 |                 37.6383   |             314.634   |    -2e-05       |
| VSA-upper-20260409T1405 |           1        |               0.818182 |                  823.938 |                200.393    |             123.08    |     2.99299e-06 |
| VSA-upper-20260519T1515 |           1        |               0.916667 |                  831.625 |                846.744    |             386.273   |     5.62252e-05 |
| VSA-upper-20260601T0550 |           1        |               1        |                  506.916 |               -188.541    |               0       |    -1.91213e-05 |
| VSA-upper-20260621T1955 |           1        |               1        |                  419.766 |                236.452    |               0       |     0           |
| VSA-upper-20260621T2010 |           1        |               1        |                  511.454 |                483.011    |               0       |     0           |
| VSA-upper-20260622T0630 |           1        |               1        |                  389.972 |                -20.062    |               0       |     1.42109e-14 |
| VSA-upper-20260622T0720 |           1        |               1        |                  275.418 |                 61.5693   |               0       |     1e-05       |
| VSA-upper-20260723T1610 |           1        |               0.555556 |                  810.319 |                 45.9893   |             565.51    |     2e-05       |
| VSA-upper-20260802T0900 |           1        |               0.931034 |                  318.463 |                 74.6984   |              51.5948  |     6.36637e-06 |
| VSA-upper-20260818T1655 |           1        |               0.952381 |                  739.258 |               -194.549    |              24.898   |     7.50751e-07 |

Exact-step coverage measures equation-version matching. Complete-terms coverage only concerns the retained energy factors; other LHS services or terms may remain aggregated. Positive components tighten and negative components relieve the directional bound. These are sums of MW changes across steps, not energy (MWh) or simultaneous capacity.

[Source and cleanup log](data/vsa_event_sources.jsonl)
