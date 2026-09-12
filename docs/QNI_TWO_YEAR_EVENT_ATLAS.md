# QNI two-year event atlas

Period: 2024-09-01 00:00:00 to 2026-08-31 23:55:00, fixed UTC+10. Method version: 1.1-event-atlas-1.

## Results

- 7,430 contraction detections; 5,445 grouped incidents.
- 92 selected detailed contraction cases, plus 13 price-only cases.
- 26 exact MPC region-interval observations; 5 contraction detections with receiving-region MPC in the following hour.
- 5,810 matched observational comparisons. Mean paired peak-price-jump difference: $15.67/MWh; day-block bootstrap interval $-26.73 to $53.33. This is not causal.

[Interactive event atlas](html/qni_event_atlas.html) · [Methodology](INTERCONNECTOR_EVENT_ANALYSIS_METHODOLOGY.md)

## Selected-case generator accounting

| DUID      |     net_mw |   tightening_mw |   relief_mw |   events |
|:----------|-----------:|----------------:|------------:|---------:|
| TUMUT3    |  9547.14   |        12233.8  |    2686.63  |       14 |
| ALDGASF1  | -1154.03   |         6426.84 |    7580.86  |       17 |
| STAN-2    |  2432.55   |         4679.85 |    2247.3   |       27 |
| STAN-1    |  2840.04   |         4044.73 |    1204.68  |       27 |
| RYEPARK1  |    63.3866 |         3837.52 |    3774.14  |       14 |
| CLARESF1  |   387.932  |         3823.21 |    3435.28  |       27 |
| LILYSF1   |   309.298  |         3806.89 |    3497.59  |       27 |
| EMERASF1  |  1109.29   |         3797.16 |    2687.87  |       27 |
| BBATTERY1 | -1220.7    |         3227.46 |    4448.15  |       27 |
| UPPTUMUT  |  1343.93   |         3132.48 |    1788.55  |       14 |
| CLRKCWF1  |   276.829  |         3129.66 |    2852.83  |       20 |
| STAN-4    |  2265.57   |         3098.54 |     832.968 |       27 |
| HAUGHT11  | -1357.54   |         2875.44 |    4232.97  |       27 |
| STAN-3    |  1667.58   |         2728    |    1060.42  |       27 |
| WLWLSF2   |  1625.31   |         2608.36 |     983.045 |       11 |
| CPP_3     |  1916.02   |         2596.18 |     680.159 |       27 |
| MOUSF1    |  -777.464  |         2527.8  |    3305.26  |       27 |
| WLWLSF1   |  1565.43   |         2522.47 |     957.036 |       11 |
| NEWENSF1  |  1174.08   |         2468.1  |    1294.02  |       34 |
| CLERMSF1  |   -62.7841 |         2460.53 |    2523.32  |       27 |

These totals cover selected fixed-equation segments, not all two-year movements. Gross tightening and relief can offset. Aggregate totals deduplicate shared physical steps; individual cases may overlap. Switching is not attributed to generators in the new equation.

## Seasonal results

|   season_year | season   | direction   |   events |   median_drop_mw |   near_mpc_events |   mpc_events |   valid_hours |   events_per_1000h | season_label   |
|--------------:|:---------|:------------|---------:|-----------------:|------------------:|-------------:|--------------:|-------------------:|:---------------|
|          2024 | Spring   | lower       |      483 |          167.62  |                 2 |            0 |          2184 |            221.154 | 2024 Spring    |
|          2024 | Spring   | upper       |      379 |          175.39  |                 2 |            1 |          2184 |            173.535 | 2024 Spring    |
|          2025 | Autumn   | lower       |      491 |          137.737 |                 1 |            0 |          2208 |            222.373 | 2025 Autumn    |
|          2025 | Autumn   | upper       |      355 |          124.572 |                 0 |            0 |          2208 |            160.779 | 2025 Autumn    |
|          2025 | Spring   | lower       |      606 |          181.856 |                 1 |            1 |          2184 |            277.473 | 2025 Spring    |
|          2025 | Spring   | upper       |      391 |          162.996 |                 0 |            0 |          2184 |            179.029 | 2025 Spring    |
|          2025 | Summer   | lower       |      435 |          210.173 |                 2 |            2 |          2160 |            201.389 | 2025 Summer    |
|          2025 | Summer   | upper       |      368 |          187.961 |                 3 |            0 |          2160 |            170.37  | 2025 Summer    |
|          2025 | Winter   | lower       |      586 |          130.557 |                 6 |            0 |          2208 |            265.399 | 2025 Winter    |
|          2025 | Winter   | upper       |      410 |          218.408 |                 1 |            0 |          2208 |            185.688 | 2025 Winter    |
|          2026 | Autumn   | lower       |      674 |          184.557 |                 0 |            0 |          2208 |            305.254 | 2026 Autumn    |
|          2026 | Autumn   | upper       |      441 |          110.478 |                 0 |            0 |          2208 |            199.728 | 2026 Autumn    |
|          2026 | Summer   | lower       |      494 |          192.899 |                 2 |            1 |          2160 |            228.704 | 2026 Summer    |
|          2026 | Summer   | upper       |      373 |          167.941 |                 0 |            0 |          2160 |            172.685 | 2026 Summer    |
|          2026 | Winter   | lower       |      536 |          156.223 |                 0 |            0 |          2208 |            242.754 | 2026 Winter    |
|          2026 | Winter   | upper       |      408 |          167.447 |                 0 |            0 |          2208 |            184.783 | 2026 Winter    |

December is assigned to the following summer year, preserving two complete December-February summers. Autumn and winter also have two complete observations; spring covers September-November 2024 and 2025. Rates use valid hours.

## Evidence and limitations

The population IC and regional-price grids are complete. Raw unit/equation archives were recovered only for selected case and control windows, with checksums, row filters and cleanup records in data/event_qni_2y/source_manifest.jsonl.

The decomposition preserves aggregate other-LHS movements, switch composites and discrepancies. Full equations may contain an unresolved Z term. No causal dispatch replay, welfare-cost calculation or forecast validation has been performed. Coal status is an initial-MW operating proxy; dated registered capacity is included where recovered, but complete planned/forced outage classifications are unavailable. Temperature is hourly reanalysis, not measured station telemetry. No external outage narrative is assigned automatically to QNI cases.

## Rebuild

```text
python -m nemic.event_atlas screen
python -m nemic.event_atlas match
python -m nemic.event_atlas recover
python -m nemic.event_atlas coal
python -m nemic.event_reconstruction
python scripts/build_event_atlas.py
```

Rendering uses retained evidence and performs no downloads. The acquisition stage enforces a 10 GB combined base-study/event-study storage guard and a 20 GB free-space reserve.

## Detailed reconstruction coverage

| event_id                |   exact_step_share |   complete_terms_share |   observed_tightening_mw |   generator_tightening_mw |   switch_composite_mw |   unresolved_mw |
|:------------------------|-------------------:|-----------------------:|-------------------------:|--------------------------:|----------------------:|----------------:|
| QNI-lower-20240919T1735 |          0         |              0         |                 1246.79  |                  0        |                0      |  1246.79        |
| QNI-lower-20241024T0505 |          0         |              0         |                  703.201 |                  0        |                0      |   703.201       |
| QNI-lower-20241107T1655 |          1         |              0         |                  654.911 |               2107.7      |                0      |     0.00012015  |
| QNI-lower-20241108T1510 |          0.8       |              0         |                 1318.31  |                826.71     |                0      |   236.394       |
| QNI-lower-20241111T1800 |          0         |              0         |                  660.884 |                  0        |                0      |   660.884       |
| QNI-lower-20241124T1055 |          1         |              1         |                  469.386 |                380.561    |                0      |     1.07775e-05 |
| QNI-lower-20241202T1605 |          1         |              0         |                  483.875 |                  0        |              483.875  |     4.38713e-06 |
| QNI-lower-20241209T1440 |          1         |              0         |                 1264.69  |                147.682    |             1159.65   |    -2.699e-05   |
| QNI-lower-20250115T1350 |          1         |              0.5       |                  469.276 |                 45.3806   |               22.5936 |     1.82306e-06 |
| QNI-lower-20250122T1430 |          0.166667  |              0.166667  |                 1057.73  |                 71.7458   |                0      |   975.022       |
| QNI-lower-20250127T1055 |          1         |              0.75      |                  214.013 |                -22.5801   |               35.1399 |     3.88898e-06 |
| QNI-lower-20250201T0635 |          0.133333  |              0.133333  |                  868.83  |                 -1.6848   |                0      |   870.515       |
| QNI-lower-20250205T1710 |          0         |              0         |                  226.539 |                  0        |                0      |   226.539       |
| QNI-lower-20250304T0845 |          1         |              0.571429  |                  713.468 |               -581.218    |              916.174  |     4.26106e-05 |
| QNI-lower-20250421T1130 |          0.315789  |              0.315789  |                  433.502 |                328.196    |                0      |   105.221       |
| QNI-lower-20250513T1715 |          0         |              0         |                  172.721 |                  0        |                0      |   172.721       |
| QNI-lower-20250517T1210 |          0.9       |              0.9       |                  332.335 |                254.725    |                0      |    30.6003      |
| QNI-lower-20250519T0640 |          0         |              0         |                  964.409 |                  0        |                0      |   964.409       |
| QNI-lower-20250603T0040 |          0         |              0         |                  354.705 |                  0        |                0      |   354.705       |
| QNI-lower-20250612T1910 |          0.571429  |              0.571429  |                  165.935 |                  0        |                0      |   138.275       |
| QNI-lower-20250612T1925 |          0.727273  |              0.727273  |                  123.336 |                  0        |                0      |    95.6762      |
| QNI-lower-20250612T1950 |          1         |              1         |                  104.99  |                  0        |                0      |     0           |
| QNI-lower-20250614T1035 |          1         |              0.608696  |                  197.27  |                -33.8185   |              -31.5461 |     1e-05       |
| QNI-lower-20250626T1950 |          1         |              1         |                  201.52  |                  0        |                0      |     0           |
| QNI-lower-20250626T2005 |          1         |              1         |                  177     |                  0        |                0      |     0           |
| QNI-lower-20250626T2030 |          1         |              1         |                  141     |                  0        |                0      |     0           |
| QNI-lower-20250722T1910 |          0         |              0         |                 1070.44  |                  0        |                0      |  1070.44        |
| QNI-lower-20250828T1250 |          1         |              0.833333  |                  428.608 |                404.196    |               47.4777 |    -1e-05       |
| QNI-lower-20250928T0715 |          0.947368  |              0.736842  |                 1020.42  |                 42.156    |              689.131  |    63.2327      |
| QNI-lower-20251010T1700 |          0.5       |              0.5       |                  167.107 |                 12.3513   |                0      |   170.873       |
| QNI-lower-20251017T1505 |          0.875     |              0.625     |                  810.588 |              -1680.19     |               27.9268 |   112.798       |
| QNI-lower-20251027T1655 |          0.333333  |              0.333333  |                  913.085 |                -79.7413   |                0      |  1060.45        |
| QNI-lower-20251126T1750 |          0.666667  |              0.666667  |                  997.704 |                579.836    |                0      |   826.63        |
| QNI-lower-20251211T1340 |          0.5       |              0         |                  952.514 |                371.668    |                0      |    18.2328      |
| QNI-lower-20260110T1540 |          1         |              0         |                  860.959 |               -361.691    |                0      |     4e-05       |
| QNI-lower-20260205T1420 |          1         |              0         |                  333.361 |              -3383.7      |              200.418  |     2e-05       |
| QNI-lower-20260206T1305 |          1         |              0         |                  354.681 |               6609.8      |               37.2656 |    -1e-05       |
| QNI-lower-20260211T1320 |          1         |              0         |                  843.571 |                192.979    |              132.582  |    -3.28993e-06 |
| QNI-lower-20260219T0815 |          1         |              0.785714  |                  270.124 |                 58.6848   |               13.2662 |     7.39946e-06 |
| QNI-lower-20260321T0630 |          0.24      |              0.2       |                  781.18  |                  0        |              165      |   616.18        |
| QNI-lower-20260414T0630 |          0.75      |              0.75      |                 1002.37  |                 -8.194    |                0      |   924.856       |
| QNI-lower-20260507T0830 |          0.666667  |              0.619048  |                 1039.39  |                 11.1014   |              797.115  |   131.616       |
| QNI-lower-20260512T2040 |          0         |              0         |                  319.87  |                  0        |                0      |   319.87        |
| QNI-lower-20260616T0705 |          0         |              0         |                  500.377 |                  0        |                0      |   500.377       |
| QNI-lower-20260716T0700 |          0.75      |              0.75      |                  717.775 |                  0        |                0      |   717.775       |
| QNI-lower-20260729T1440 |          1         |              1         |                  124.029 |                 63.6793   |                0      |     3.40483e-06 |
| QNI-lower-20260805T1625 |          0         |              0         |                 1486.68  |                  0        |                0      |  1486.68        |
| QNI-upper-20240908T1710 |          0         |              0         |                  195.483 |                  0        |                0      |   195.483       |
| QNI-upper-20240926T1315 |          0         |              0         |                 1268.67  |                  0        |                0      |  1268.67        |
| QNI-upper-20241019T1530 |          0.5       |              0         |                 1438.72  |                315.773    |                0      |   629.824       |
| QNI-upper-20241022T1615 |          0         |              0         |                  258.012 |                  0        |                0      |   258.012       |
| QNI-upper-20241105T1120 |          0.5       |              0         |                 1576.79  |               -389.225    |                0      |  1563.92        |
| QNI-upper-20241107T1645 |          1         |              0         |                  192.547 |                 91.8179   |                0      |     1.42132e-06 |
| QNI-upper-20241128T1305 |          0.555556  |              0         |                 2056.58  |               1171.46     |                0      |  1888.69        |
| QNI-upper-20241128T1330 |          0.571429  |              0         |                 2027.23  |               2183.17     |                0      |   908.092       |
| QNI-upper-20241128T1520 |          0         |              0         |                 1890.65  |                  0        |                0      |  1890.65        |
| QNI-upper-20241208T1710 |          1         |              0         |                  450.467 |                446.308    |                0      |    -1.52284e-07 |
| QNI-upper-20241208T1725 |          1         |              0         |                  420.357 |                382.267    |                0      |    -1.03046e-05 |
| QNI-upper-20241209T0915 |          0.272727  |              0         |                 1190.99  |              -1528.55     |                0      |  -634.475       |
| QNI-upper-20241218T0840 |          1         |              0         |                  847.071 |               2831.47     |                0      |     3.54701e-05 |
| QNI-upper-20250115T1345 |          0.666667  |              0         |                 1397.04  |               1024.81     |               15.4189 |   847.062       |
| QNI-upper-20250122T1635 |          0         |              0         |                  306.143 |                  0        |                0      |   306.143       |
| QNI-upper-20250213T1640 |          0         |              0         |                 1009.62  |                  0        |                0      |  1009.62        |
| QNI-upper-20250225T1540 |          1         |              0         |                  551.053 |                703.056    |                0      |     2.57089e-06 |
| QNI-upper-20250321T1335 |          0.5       |              0         |                 1006     |                403.326    |                0      |   817.67        |
| QNI-upper-20250322T1445 |          0.0344828 |              0.0344828 |                  276.541 |                 -0.923447 |                0      |   241.532       |
| QNI-upper-20250430T1125 |          0         |              0         |                  827.847 |                  0        |                0      |   827.847       |
| QNI-upper-20250529T0630 |          0.666667  |              0.666667  |                  962.02  |                 26.9728   |                0      |   957.832       |
| QNI-upper-20250610T1800 |          1         |              0         |                  283.252 |                381.217    |                0      |     9.413e-06   |
| QNI-upper-20250612T1935 |          1         |              0         |                  244.88  |                138.701    |                0      |     7.2327e-06  |
| QNI-upper-20250626T0730 |          0.25      |              0.25      |                 1771.04  |                142.169    |                0      |  1628.87        |
| QNI-upper-20250627T0730 |          0.5       |              0.5       |                 1874.16  |                208.643    |                0      |  1665.52        |
| QNI-upper-20250701T0910 |          0.8       |              0.8       |                 1957.36  |              -3127.68     |                0      |  1652.93        |
| QNI-upper-20250704T1615 |          0.571429  |              0.571429  |                 2023.76  |               1804.03     |                0      |  1446.09        |
| QNI-upper-20250712T1610 |          0.583333  |              0.416667  |                 1953.59  |               1553.41     |             -254.553  |  2021.8         |
| QNI-upper-20250826T0730 |          0.857143  |              0.714286  |                 1385.12  |              -1132.54     |              -72.7842 |  1331.35        |
| QNI-upper-20250902T0605 |          1         |              1         |                  261.63  |                 86.5724   |                0      |     8.73096e-06 |
| QNI-upper-20250929T0930 |          0.25      |              0.25      |                 2022.84  |              -3039.89     |                0      |  1762.88        |
| QNI-upper-20251012T1230 |          1         |              0.5       |                 1222.09  |               -324.505    |             1120      |    -1.03896e-06 |
| QNI-upper-20251122T1630 |          0.647059  |              0         |                 1738.26  |               2627.32     |                0      |  1556.93        |
| QNI-upper-20251206T0630 |          0.25      |              0.25      |                 1634.64  |                 72.6337   |                0      |  1465.74        |
| QNI-upper-20260110T1605 |          1         |              0.2       |                  619.774 |                178.447    |              126.686  |    -6.82672e-06 |
| QNI-upper-20260124T1845 |          1         |              0         |                  162.527 |                175.753    |                0      |     5.01044e-07 |
| QNI-upper-20260205T1550 |          0.75      |              0         |                  659.075 |                440.173    |                0      |   118.561       |
| QNI-upper-20260303T0600 |          0.352941  |              0.294118  |                  838.462 |                 -0.97692  |               38.2637 |   859.875       |
| QNI-upper-20260413T1350 |          0.909091  |              0.863636  |                 1984.08  |                373.378    |             1415.62   |  -210.729       |
| QNI-upper-20260511T1040 |          0         |              0         |                  731.046 |                  0        |                0      |   731.046       |
| QNI-upper-20260528T0645 |          0         |              0         |                  160.948 |                  0        |                0      |   160.948       |
| QNI-upper-20260630T0730 |          1         |              0.6       |                 1348.89  |                808.349    |              684.502  |    -3.28749e-06 |
| QNI-upper-20260702T0700 |          0.875     |              0.75      |                  847.567 |                  0        |              169.473  |   705.095       |
| QNI-upper-20260721T0440 |          0.625     |              0         |                  430.813 |                426.143    |                0      |    -8.10677     |
| QNI-upper-20260815T1130 |          0.75      |              0.75      |                 1116.65  |                252.15     |                0      |  1051.73        |

Exact-step coverage measures equation-version matching. Complete-terms coverage only concerns the retained energy factors; other LHS services or terms may remain aggregated. Positive components tighten and negative components relieve the directional bound. These are sums of MW changes across steps, not energy (MWh) or simultaneous capacity.

[Source and cleanup log](data/qni_event_sources.jsonl)
