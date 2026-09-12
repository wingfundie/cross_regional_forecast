# VNI two-year event atlas

Period: 2024-09-01 00:00:00 to 2026-08-31 23:55:00, fixed UTC+10. Method version: 1.1-event-atlas-1.

## Results

- 7,486 contraction detections; 5,379 grouped incidents.
- 91 selected detailed contraction cases, plus 12 price-only cases.
- 26 exact MPC region-interval observations; 13 contraction detections with receiving-region MPC in the following hour.
- 6,356 matched observational comparisons. Mean paired peak-price-jump difference: $94.97/MWh; day-block bootstrap interval $58.27 to $136.83. This is not causal.

[Interactive event atlas](html/vni_event_atlas.html) · [Methodology](INTERCONNECTOR_EVENT_ANALYSIS_METHODOLOGY.md)

## Selected-case generator accounting

| DUID     |    net_mw |   tightening_mw |   relief_mw |   events |
|:---------|----------:|----------------:|------------:|---------:|
| TUMUT3   | 31956.3   |        35037.5  |     3081.2  |       61 |
| UPPTUMUT |  7708.28  |         9712.73 |     2004.44 |       61 |
| LIMOSF11 |  3600.55  |         9211.01 |     5610.46 |       85 |
| VBB1     |  2747.3   |         6757.8  |     4010.5  |       11 |
| SUNRSF1  |  2235.08  |         6427.7  |     4192.62 |       85 |
| MUWAWF1  |  1176.46  |         5392.06 |     4215.61 |       39 |
| KIAMSF1  |  1511.3   |         5314.68 |     3803.38 |       38 |
| DARLSF1  |   622.954 |         4599.46 |     3976.51 |       78 |
| MERCER01 |  1409.67  |         4002.15 |     2592.48 |       14 |
| AVLSF1   |  -490.3   |         3637.68 |     4127.98 |       58 |
| ARWF1    |   194.698 |         3591.7  |     3397.01 |       37 |
| GPWFEST2 |  2125.86  |         3496.34 |     1370.48 |        6 |
| CUSF1    |  -679.862 |         3439.89 |     4119.75 |       13 |
| STWF1    |   683.937 |         3140.39 |     2456.45 |       85 |
| MURRAY   |  1906.77  |         3077.97 |     1171.19 |       58 |
| GPWFEST1 |  1896.87  |         3067.67 |     1170.8  |        6 |
| NEWENSF1 |   682.5   |         2799.59 |     2117.09 |       14 |
| NEWENSF2 |   732.471 |         2778.57 |     2046.1  |       14 |
| KARSF1   |  -214.259 |         2764.85 |     2979.11 |       45 |
| BANN1    |   559.656 |         2688.2  |     2128.55 |       38 |

These totals cover selected fixed-equation segments, not all two-year movements. Gross tightening and relief can offset. Aggregate totals deduplicate shared physical steps; individual cases may overlap. Switching is not attributed to generators in the new equation.

## Seasonal results

|   season_year | season   | direction   |   events |   median_drop_mw |   near_mpc_events |   mpc_events |   valid_hours |   events_per_1000h | season_label   |
|--------------:|:---------|:------------|---------:|-----------------:|------------------:|-------------:|--------------:|-------------------:|:---------------|
|          2024 | Spring   | lower       |      368 |          531.12  |                 0 |            0 |          2184 |            168.498 | 2024 Spring    |
|          2024 | Spring   | upper       |      444 |          533.675 |                 7 |            3 |          2184 |            203.297 | 2024 Spring    |
|          2025 | Autumn   | lower       |      459 |          352.315 |                 0 |            0 |          2208 |            207.88  | 2025 Autumn    |
|          2025 | Autumn   | upper       |      471 |          310.412 |                 4 |            0 |          2208 |            213.315 | 2025 Autumn    |
|          2025 | Spring   | lower       |      502 |          385.208 |                 0 |            0 |          2184 |            229.853 | 2025 Spring    |
|          2025 | Spring   | upper       |      514 |          422.662 |                 2 |            2 |          2184 |            235.348 | 2025 Spring    |
|          2025 | Summer   | lower       |      307 |          462.245 |                 0 |            0 |          2160 |            142.13  | 2025 Summer    |
|          2025 | Summer   | upper       |      425 |          511.315 |                 8 |            6 |          2160 |            196.759 | 2025 Summer    |
|          2025 | Winter   | lower       |      479 |          275.473 |                 0 |            0 |          2208 |            216.938 | 2025 Winter    |
|          2025 | Winter   | upper       |      515 |          323.641 |                 1 |            0 |          2208 |            233.243 | 2025 Winter    |
|          2026 | Autumn   | lower       |      417 |          176.16  |                 0 |            0 |          2208 |            188.859 | 2026 Autumn    |
|          2026 | Autumn   | upper       |      529 |          278.052 |                 0 |            0 |          2208 |            239.583 | 2026 Autumn    |
|          2026 | Summer   | lower       |      451 |          323.297 |                 0 |            0 |          2160 |            208.796 | 2026 Summer    |
|          2026 | Summer   | upper       |      567 |          330.565 |                 2 |            2 |          2160 |            262.5   | 2026 Summer    |
|          2026 | Winter   | lower       |      473 |          244.775 |                 0 |            0 |          2208 |            214.221 | 2026 Winter    |
|          2026 | Winter   | upper       |      565 |          300.472 |                 0 |            0 |          2208 |            255.888 | 2026 Winter    |

December is assigned to the following summer year, preserving two complete December-February summers. Autumn and winter also have two complete observations; spring covers September-November 2024 and 2025. Rates use valid hours.

## Evidence and limitations

The population IC and regional-price grids are complete. Raw unit/equation archives were recovered only for selected case and control windows, with checksums, row filters and cleanup records in data/event_vni_2y/source_manifest.jsonl.

The decomposition preserves aggregate other-LHS movements, switch composites and discrepancies. Full equations may contain an unresolved Z term. No causal dispatch replay, welfare-cost calculation or forecast validation has been performed. Coal status is an initial-MW operating proxy; dated registered capacity is included where recovered, but complete planned/forced outage classifications are unavailable. Temperature is hourly reanalysis, not measured station telemetry. Externally corroborated November 2024 and November 2025 cases cite AEMO's Q4 report in the atlas.

## Rebuild

```text
python -m nemic.event_atlas screen
python -m nemic.event_atlas match
python -m nemic.event_atlas recover
python -m nemic.event_supplement
python -m nemic.event_atlas coal
python -m nemic.event_reconstruction
python scripts/build_event_atlas.py
```

Rendering uses retained evidence and performs no downloads. The acquisition stage enforces a 10 GB combined base-study/event-study storage guard and a 20 GB free-space reserve.

## Detailed reconstruction coverage

| event_id                |   exact_step_share |   complete_terms_share |   observed_tightening_mw |   generator_tightening_mw |   switch_composite_mw |   unresolved_mw |
|:------------------------|-------------------:|-----------------------:|-------------------------:|--------------------------:|----------------------:|----------------:|
| VNI-lower-20240904T2110 |           1        |              0         |                 1429.66  |                 605.263   |             447.776   |    -1e-05       |
| VNI-lower-20241019T0945 |           0.333333 |              0.333333  |                 1084.07  |                  55.4866  |               0       |  1018.03        |
| VNI-lower-20241028T1535 |           0.833333 |              0.666667  |                 1583.79  |                 595.082   |              29.4421  |   939.368       |
| VNI-lower-20241106T1655 |           1        |              0.714286  |                 1961.25  |                   3.46039 |            1842.36    |     7.57862e-05 |
| VNI-lower-20241201T1420 |           1        |              0.833333  |                 1428.1   |                 132.903   |            1239.19    |    -1e-05       |
| VNI-lower-20241220T0910 |           0        |              0         |                  422.73  |                   0       |               0       |   422.73        |
| VNI-lower-20250115T1955 |           1        |              0.4       |                 1902.74  |                 191.601   |            1708.49    |     9.64234e-05 |
| VNI-lower-20250212T1935 |           0.966667 |              0.866667  |                  617.691 |                 109.276   |             -43.5887  |   104.106       |
| VNI-lower-20250215T0750 |           1        |              0.833333  |                 1264.74  |                1925.71    |             249.973   |     2.92857e-05 |
| VNI-lower-20250301T1405 |           1        |              0.833333  |                 1760.19  |                -290.746   |             150.234   |    -5e-05       |
| VNI-lower-20250309T0800 |           1        |              1         |                  657.739 |                2412.03    |               0       |     4.72727e-05 |
| VNI-lower-20250421T1335 |           1        |              0.9       |                 1645.38  |                 478.518   |             102.903   |    -3e-05       |
| VNI-lower-20250506T0835 |           1        |              1         |                 1372.41  |                 311.38    |               0       |    -7.85714e-06 |
| VNI-lower-20250602T0600 |           1        |              0.863636  |                  365.97  |                 327.97    |             108.467   |    -5.68434e-14 |
| VNI-lower-20250606T1815 |           1        |              0.5       |                 1721.75  |                 308.466   |            1321.92    |     4.06406e-06 |
| VNI-lower-20250708T0730 |           1        |              0.142857  |                 1516.08  |                 324.992   |             644.448   |     4e-05       |
| VNI-lower-20250827T1210 |           1        |              0.833333  |                 1484.77  |                  28.6847  |            1434.47    |    -4.43396e-05 |
| VNI-lower-20250926T2020 |           1        |              0.5       |                 1113.71  |                 898.566   |             342.885   |    -1e-05       |
| VNI-lower-20251006T0425 |           1        |              1         |                 1368.39  |                 159.543   |               0       |     5.67925e-05 |
| VNI-lower-20251104T1715 |           1        |              0.857143  |                 1680.92  |                -982.322   |            1564.99    |     1e-05       |
| VNI-lower-20251107T0655 |           1        |              0.666667  |                 1676.56  |                -511.937   |            1531.45    |    -2e-05       |
| VNI-lower-20251119T2035 |           1        |              1         |                  604.925 |                 611.303   |               0       |    -1e-05       |
| VNI-lower-20251215T0205 |           1        |              0.583333  |                 1785.7   |                 232.141   |             696.937   |    -5e-05       |
| VNI-lower-20260106T1640 |           1        |              1         |                  507.754 |                 521.484   |               0       |     1e-05       |
| VNI-lower-20260111T0015 |           1        |              0.642857  |                 1201.74  |                -113.604   |            1392.05    |    -1.72727e-05 |
| VNI-lower-20260212T1435 |           1        |              0.75      |                 1230.38  |                  59.3411  |            1164.48    |     0           |
| VNI-lower-20260307T1215 |           1        |              0.857143  |                 1023.15  |                  36.2593  |             946.784   |     0           |
| VNI-lower-20260409T1710 |           1        |              0.625     |                 1684.01  |                3420.71    |             694.662   |     2e-05       |
| VNI-lower-20260425T2315 |           1        |              1         |                  282.141 |                 152.089   |               0       |    -1.13687e-13 |
| VNI-lower-20260503T0930 |           1        |              0.809524  |                 1686.17  |                 254.372   |            1202.54    |    -1e-05       |
| VNI-lower-20260603T1715 |           1        |              0         |                 1668.2   |                1639.74    |             183.729   |     3e-05       |
| VNI-lower-20260622T0635 |           1        |              0.866667  |                  727.403 |                 541.895   |              88.7239  |     1e-05       |
| VNI-lower-20260714T1510 |           1        |              0.0833333 |                 1656.44  |                 896.23    |             868.297   |    -3.28931e-05 |
| VNI-lower-20260810T1610 |           1        |              1         |                  981.032 |                 899.686   |               0       |    -2.59119e-05 |
| VNI-upper-20240908T1800 |           1        |              0         |                 1517.35  |                1623.6     |               0       |     2.04081e-07 |
| VNI-upper-20240929T1720 |           1        |              0         |                 1681.18  |                1210.47    |            1381.99    |    -1e-05       |
| VNI-upper-20241028T1505 |           1        |              0         |                 1497.98  |                   0       |            1497.98    |    -3.29928e-06 |
| VNI-upper-20241111T1735 |           1        |              1         |                  947.176 |                 956.641   |               0       |     2.61491e-06 |
| VNI-upper-20241117T1550 |           1        |              0.5       |                 2351.87  |                 276.163   |            2151.41    |     2.14504e-07 |
| VNI-upper-20241121T1750 |           1        |              0.888889  |                 1922.53  |                1908.3     |              70.733   |     5.9204e-06  |
| VNI-upper-20241122T1800 |           1        |              1         |                  987.874 |                 948.909   |               0       |    -4.18795e-07 |
| VNI-upper-20241123T1740 |           1        |              0.866667  |                 1049.56  |                1065.02    |              63.3187  |     1e-05       |
| VNI-upper-20241127T1450 |           1        |              0         |                  867.725 |                 128.041   |             775.301   |    -4.96357e-06 |
| VNI-upper-20241127T1500 |           1        |              0         |                  867.725 |                 128.041   |             775.301   |    -4.96357e-06 |
| VNI-upper-20241129T0615 |           1        |              0.307692  |                 2539.2   |                 353.043   |            2166.92    |     3.18408e-06 |
| VNI-upper-20241203T1135 |           1        |              0.25      |                 1795.74  |                 386.006   |            1394.93    |     6.02145e-05 |
| VNI-upper-20241206T1425 |           1        |              0.5       |                 1537.91  |                1516.69    |              31.6711  |    -3.9801e-07  |
| VNI-upper-20241208T1805 |           1        |              0         |                 1523.29  |                3128.23    |               0       |     0.00010395  |
| VNI-upper-20241213T1315 |           1        |              0.857143  |                  956.398 |                 937.397   |              29.2246  |     5e-05       |
| VNI-upper-20250114T1740 |           1        |              0.9       |                 1542.39  |                1567.8     |             149.876   |     9.40896e-07 |
| VNI-upper-20250115T1345 |           1        |              0.111111  |                 1458.95  |                1500.14    |             129.363   |    -1e-05       |
| VNI-upper-20250115T1400 |           1        |              0         |                 1447.01  |                1447.86    |             141       |    -6.40583e-05 |
| VNI-upper-20250122T0705 |           1        |              0.947368  |                 1041.32  |                 790.604   |             139.192   |    -3.74486e-06 |
| VNI-upper-20250204T1515 |           1        |              0.5       |                 1673.14  |                2025.66    |            -243.127   |     2.97855e-05 |
| VNI-upper-20250205T1630 |           1        |              0.947368  |                 1526.67  |                1375.39    |             -48.2338  |    -1e-05       |
| VNI-upper-20250205T1645 |           1        |              1         |                 1457.74  |                1520.38    |               0       |     2.14504e-07 |
| VNI-upper-20250205T1655 |           1        |              1         |                 1457.74  |                1520.38    |               0       |     2.14504e-07 |
| VNI-upper-20250207T1710 |           1        |              0         |                 1653.52  |                   0       |            1653.52    |    -3.32119e-05 |
| VNI-upper-20250208T1435 |           1        |              0.25      |                 1355.56  |                  51.7933  |            1361.85    |     2.84217e-14 |
| VNI-upper-20250210T1205 |           1        |              0.666667  |                 1711.14  |                 440.296   |            1614.81    |    -1e-05       |
| VNI-upper-20250306T1535 |           1        |              0.5       |                  545.669 |                 197.291   |             419.126   |    -9.8167e-06  |
| VNI-upper-20250315T1620 |           1        |              0.888889  |                 2134.97  |                2258.13    |              36.4567  |    -2.14505e-07 |
| VNI-upper-20250409T1635 |           1        |              1         |                 1682.64  |                1856.97    |               0       |     7.58691e-06 |
| VNI-upper-20250409T1650 |           1        |              1         |                 1682.64  |                1856.97    |               0       |     7.58691e-06 |
| VNI-upper-20250411T1705 |           1        |              1         |                 1656.82  |                1831.85    |               0       |     5.97719e-06 |
| VNI-upper-20250513T1615 |           1        |              1         |                 1984.16  |                2170.19    |               0       |     1.65021e-05 |
| VNI-upper-20250528T1630 |           1        |              1         |                 1750.88  |                2318.66    |               0       |     1.4309e-06  |
| VNI-upper-20250615T0635 |           1        |              0.8       |                 1078.61  |                   6.83257 |             933.963   |     9.39501e-05 |
| VNI-upper-20250626T2005 |           1        |              0.857143  |                  502.374 |                 -59.7257  |             448.612   |    -1.13687e-13 |
| VNI-upper-20250716T1035 |           1        |              0.888889  |                  668.617 |                 472.456   |              -5.01962 |     1e-05       |
| VNI-upper-20250728T2235 |           1        |              0.8       |                 1877.76  |                 694.684   |             191.092   |     1e-05       |
| VNI-upper-20250829T0625 |           1        |              0.666667  |                 2057.31  |                1457.17    |             658.821   |     1.02041e-05 |
| VNI-upper-20250914T1540 |           1        |              0.5       |                 1211.73  |                 192.554   |            1087.27    |    -1e-05       |
| VNI-upper-20250930T1325 |           1        |              0.666667  |                 1093.36  |                 225.04    |            1194.48    |    -1e-05       |
| VNI-upper-20251010T1735 |           1        |              0.5       |                 1806.38  |                 222.223   |            1565.32    |     6.72359e-07 |
| VNI-upper-20251126T1040 |           1        |              0.625     |                 2319.06  |                2029       |             108.311   |     1e-05       |
| VNI-upper-20251126T1420 |           1        |              0.571429  |                 1812.23  |                1212.83    |             793.423   |     6.39501e-05 |
| VNI-upper-20251205T1550 |           1        |              0         |                 1479.97  |                1801.76    |               0       |     1.28571e-05 |
| VNI-upper-20260110T1505 |           1        |              0         |                 1073.07  |                1153.5     |               0       |     1e-05       |
| VNI-upper-20260112T0710 |           1        |              0.9       |                  643.572 |                  58.8749  |              84.887   |    -2.13163e-14 |
| VNI-upper-20260205T1340 |           1        |              0.0833333 |                 1693.34  |                1829       |             -14.1674  |    -1.42857e-05 |
| VNI-upper-20260205T1415 |           1        |              0         |                 1690.7   |                1774.36    |               0       |     1.42857e-06 |
| VNI-upper-20260206T1255 |           1        |              0         |                 1755.94  |                1767.1     |              11.7937  |     5.71429e-06 |
| VNI-upper-20260304T1555 |           1        |              0.8       |                 1939.45  |                1818.19    |             -93.5567  |     1.83299e-07 |
| VNI-upper-20260406T1055 |           1        |              1         |                  829.72  |                1429.7     |               0       |    -1.06581e-14 |
| VNI-upper-20260407T0925 |           1        |              1         |                  376.582 |                 -68.4002  |               0       |     3.19149e-06 |
| VNI-upper-20260504T0845 |           1        |              1         |                  959.525 |                1420.35    |               0       |    -1.65957e-05 |
| VNI-upper-20260623T0905 |           1        |              0.75      |                 1267.21  |                   0       |            1020.99    |     1.92369e-05 |
| VNI-upper-20260714T1430 |           1        |              1         |                  805.138 |                 822.406   |               0       |     1e-05       |
| VNI-upper-20260722T2335 |           1        |              1         |                  710.403 |                 598.224   |               0       |     0           |
| VNI-upper-20260801T1320 |           1        |              1         |                 1137.92  |                 291.681   |               0       |     5.68434e-14 |

Exact-step coverage measures equation-version matching. Complete-terms coverage only concerns the retained energy factors; other LHS services or terms may remain aggregated. Positive components tighten and negative components relieve the directional bound. These are sums of MW changes across steps, not energy (MWh) or simultaneous capacity.

[Source and cleanup log](data/vni_event_sources.jsonl)
