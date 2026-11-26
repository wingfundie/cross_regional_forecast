# QNI two-year sharp-contraction event atlas (Version 2)

## Executive summary and mechanical scope

This standalone event atlas examines every sharp 30-minute directional capacity contraction recorded on QNI (NSW1-QLD1, NSW → QLD positive) between 1 September 2024 and 31 August 2026 in fixed Australian National Electricity Market time (UTC+10). Across 210,240 five-minute dispatch intervals, the monthly adaptive 90th-percentile screen identifies **7,430 contraction detections** grouping into **5,445 distinct incidents**. Ninety-plus detailed windows (92 contraction cases plus 13 price-only episodes without a nearby contraction) retain complete five-minute unit dispatch, constraint-equation factor reconstruction, coal availability proxies, rooftop solar estimates, and hourly weather context.

> [!TAKEAWAY] Core Operational Takeaway for QNI
> Contractions on QNI are associated with a matched observational next-hour peak price jump difference of **$15.67/MWh** relative to same-month, similar-condition control windows (5,810 matched pairs; event-day block-bootstrap 95% confidence interval **$-26.73 to $53.33/MWh**). Across the 92 reconstructed cases, **TUMUT3** recorded the largest gross fixed-equation tightening contribution, and **31 of 92** selected cases achieved 100% exact equation-version matching on every attribution step.

> [!WARNING] Mechanical Attribution Versus Independent Causation
> Generator contributions quantify mechanical bound sensitivity ($-b_i/a \times \Delta P_i$) along fixed-equation segments of the solved dispatch linear programme. Because regional demand, generator offers, transmission outages, and constraint switches co-move within the same five-minute interval, these figures are mechanical decompositions rather than independent causal estimates. Unresolved right-hand-side terms and equation switches are always reported separately from generator ramps.

## Selected-case generator accounting

Gross tightening and relief are deduplicated across shared five-minute physical steps inside the 92 detailed contraction cases so overlapping case windows never double-count the same dispatch move. Positive net tightening indicates that a unit's output changes predominantly reduced available transfer capacity during active fixed-equation intervals.

| Generator unit | Net tightening (MW) | Gross tightening (MW) | Gross relief (MW) | Active cases |
|---|---:|---:|---:|---:|
| TUMUT3 | 9,547.1 | 12,233.8 | 2,686.6 | 14 |
| ALDGASF1 | -1,154.0 | 6,426.8 | 7,580.9 | 17 |
| STAN-2 | 2,432.6 | 4,679.8 | 2,247.3 | 27 |
| STAN-1 | 2,840.0 | 4,044.7 | 1,204.7 | 27 |
| RYEPARK1 | 63.4 | 3,837.5 | 3,774.1 | 14 |
| CLARESF1 | 387.9 | 3,823.2 | 3,435.3 | 27 |
| LILYSF1 | 309.3 | 3,806.9 | 3,497.6 | 27 |
| EMERASF1 | 1,109.3 | 3,797.2 | 2,687.9 | 27 |
| BBATTERY1 | -1,220.7 | 3,227.5 | 4,448.2 | 27 |
| UPPTUMUT | 1,343.9 | 3,132.5 | 1,788.6 | 14 |
| CLRKCWF1 | 276.8 | 3,129.7 | 2,852.8 | 20 |
| STAN-4 | 2,265.6 | 3,098.5 | 833.0 | 27 |
| HAUGHT11 | -1,357.5 | 2,875.4 | 4,233.0 | 27 |
| STAN-3 | 1,667.6 | 2,728.0 | 1,060.4 | 27 |
| WLWLSF2 | 1,625.3 | 2,608.4 | 983.0 | 11 |
| CPP_3 | 1,916.0 | 2,596.2 | 680.2 | 27 |
| MOUSF1 | -777.5 | 2,527.8 | 3,305.3 | 27 |
| WLWLSF1 | 1,565.4 | 2,522.5 | 957.0 | 11 |
| NEWENSF1 | 1,174.1 | 2,468.1 | 1,294.0 | 34 |
| CLERMSF1 | -62.8 | 2,460.5 | 2,523.3 | 27 |

## Seasonal contraction frequency and price-cap coincidence

Across the two full seasonal cycles (with December assigned to the following summer year), contraction intensity clusters around seasonal thermal limits, solar-midday congestion, and planned transmission maintenance. Exactly 26 exact Market Price Cap region-intervals occurred in the study window, of which 5 contraction detections coincided with a receiving-region cap interval within the following hour.

| Season | Direction | Detections | Median drop (MW) | Near-cap cases | Cap cases | Rate per 1,000 hours |
|---|---|---:|---:|---:|---:|---:|
| 2024 Spring | Lower | 483 | 167.6 | 2 | 0 | 221.2 |
| 2024 Spring | Upper | 379 | 175.4 | 2 | 1 | 173.5 |
| 2025 Autumn | Lower | 491 | 137.7 | 1 | 0 | 222.4 |
| 2025 Autumn | Upper | 355 | 124.6 | 0 | 0 | 160.8 |
| 2025 Spring | Lower | 606 | 181.9 | 1 | 1 | 277.5 |
| 2025 Spring | Upper | 391 | 163.0 | 0 | 0 | 179.0 |
| 2025 Summer | Lower | 435 | 210.2 | 2 | 2 | 201.4 |
| 2025 Summer | Upper | 368 | 188.0 | 3 | 0 | 170.4 |
| 2025 Winter | Lower | 586 | 130.6 | 6 | 0 | 265.4 |
| 2025 Winter | Upper | 410 | 218.4 | 1 | 0 | 185.7 |
| 2026 Autumn | Lower | 674 | 184.6 | 0 | 0 | 305.3 |
| 2026 Autumn | Upper | 441 | 110.5 | 0 | 0 | 199.7 |
| 2026 Summer | Lower | 494 | 192.9 | 2 | 1 | 228.7 |
| 2026 Summer | Upper | 373 | 167.9 | 0 | 0 | 172.7 |
| 2026 Winter | Lower | 536 | 156.2 | 0 | 0 | 242.8 |
| 2026 Winter | Upper | 408 | 167.4 | 0 | 0 | 184.8 |

## Top reconstructed contraction cases

The table below reports the twenty-five largest selected contractions ranked by baseline-to-trough observed tightening, separating fixed-equation generator ramps, equation-switch composites, and unresolved residuals (values below 0.05 MW rounded cleanly to 0.0 MW).

| Case identifier | Exact-version steps | Complete energy terms | Observed loss (MW) | Generator tightening (MW) | Equation switch (MW) | Unresolved residual (MW) |
|---|---:|---:|---:|---:|---:|---:|
| QNI-upper-20241128T1305 | 56% | 0% | 2,056.6 | 1,171.5 | 0.0 | 1,888.7 |
| QNI-upper-20241128T1330 | 57% | 0% | 2,027.2 | 2,183.2 | 0.0 | 908.1 |
| QNI-upper-20250704T1615 | 57% | 57% | 2,023.8 | 1,804.0 | 0.0 | 1,446.1 |
| QNI-upper-20250929T0930 | 25% | 25% | 2,022.8 | -3,039.9 | 0.0 | 1,762.9 |
| QNI-upper-20260413T1350 | 91% | 86% | 1,984.1 | 373.4 | 1,415.6 | -210.7 |
| QNI-upper-20250701T0910 | 80% | 80% | 1,957.4 | -3,127.7 | 0.0 | 1,652.9 |
| QNI-upper-20250712T1610 | 58% | 42% | 1,953.6 | 1,553.4 | -254.6 | 2,021.8 |
| QNI-upper-20241128T1520 | 0% | 0% | 1,890.7 | 0.0 | 0.0 | 1,890.7 |
| QNI-upper-20250627T0730 | 50% | 50% | 1,874.2 | 208.6 | 0.0 | 1,665.5 |
| QNI-upper-20250626T0730 | 25% | 25% | 1,771.0 | 142.2 | 0.0 | 1,628.9 |
| QNI-upper-20251122T1630 | 65% | 0% | 1,738.3 | 2,627.3 | 0.0 | 1,556.9 |
| QNI-upper-20251206T0630 | 25% | 25% | 1,634.6 | 72.6 | 0.0 | 1,465.7 |
| QNI-upper-20241105T1120 | 50% | 0% | 1,576.8 | -389.2 | 0.0 | 1,563.9 |
| QNI-lower-20260805T1625 | 0% | 0% | 1,486.7 | 0.0 | 0.0 | 1,486.7 |
| QNI-upper-20241019T1530 | 50% | 0% | 1,438.7 | 315.8 | 0.0 | 629.8 |
| QNI-upper-20250115T1345 | 67% | 0% | 1,397.0 | 1,024.8 | 15.4 | 847.1 |
| QNI-upper-20250826T0730 | 86% | 71% | 1,385.1 | -1,132.5 | -72.8 | 1,331.3 |
| QNI-upper-20260630T0730 | 100% | 60% | 1,348.9 | 808.3 | 684.5 | 0.0 |
| QNI-lower-20241108T1510 | 80% | 0% | 1,318.3 | 826.7 | 0.0 | 236.4 |
| QNI-upper-20240926T1315 | 0% | 0% | 1,268.7 | 0.0 | 0.0 | 1,268.7 |
| QNI-lower-20241209T1440 | 100% | 0% | 1,264.7 | 147.7 | 1,159.6 | 0.0 |
| QNI-lower-20240919T1735 | 0% | 0% | 1,246.8 | 0.0 | 0.0 | 1,246.8 |
| QNI-upper-20251012T1230 | 100% | 50% | 1,222.1 | -324.5 | 1,120.0 | 0.0 |
| QNI-upper-20241209T0915 | 27% | 0% | 1,191.0 | -1,528.6 | 0.0 | -634.5 |
| QNI-upper-20260815T1130 | 75% | 75% | 1,116.7 | 252.2 | 0.0 | 1,051.7 |

## Compression, provenance, and rebuild notes

Version 2 preserves every reconstructed case and five-minute trace from the frozen Version 1 event-atlas evidence while compressing the interactive bundle payload into rounded columnar arrays encoded with gzip and decompressed natively in the browser. All legacy Version 1 atlases remain untouched as frozen baselines. Recompute from retained local archives with `python -m nemic.experiments.event_atlas_v2`.
