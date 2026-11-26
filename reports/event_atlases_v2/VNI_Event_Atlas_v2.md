# VNI two-year sharp-contraction event atlas (Version 2)

## Executive summary and mechanical scope

This standalone event atlas examines every sharp 30-minute directional capacity contraction recorded on VNI (VIC1-NSW1, VIC → NSW positive) between 1 September 2024 and 31 August 2026 in fixed Australian National Electricity Market time (UTC+10). Across 210,240 five-minute dispatch intervals, the monthly adaptive 90th-percentile screen identifies **7,486 contraction detections** grouping into **5,379 distinct incidents**. Ninety-plus detailed windows (91 contraction cases plus 12 price-only episodes without a nearby contraction) retain complete five-minute unit dispatch, constraint-equation factor reconstruction, coal availability proxies, rooftop solar estimates, and hourly weather context.

> [!TAKEAWAY] Core Operational Takeaway for VNI
> Contractions on VNI are associated with a matched observational next-hour peak price jump difference of **$94.97/MWh** relative to same-month, similar-condition control windows (6,356 matched pairs; event-day block-bootstrap 95% confidence interval **$58.27 to $136.83/MWh**). Across the 91 reconstructed cases, **TUMUT3** recorded the largest gross fixed-equation tightening contribution, and **87 of 91** selected cases achieved 100% exact equation-version matching on every attribution step.

> [!WARNING] Mechanical Attribution Versus Independent Causation
> Generator contributions quantify mechanical bound sensitivity ($-b_i/a \times \Delta P_i$) along fixed-equation segments of the solved dispatch linear programme. Because regional demand, generator offers, transmission outages, and constraint switches co-move within the same five-minute interval, these figures are mechanical decompositions rather than independent causal estimates. Unresolved right-hand-side terms and equation switches are always reported separately from generator ramps.

## Selected-case generator accounting

Gross tightening and relief are deduplicated across shared five-minute physical steps inside the 91 detailed contraction cases so overlapping case windows never double-count the same dispatch move. Positive net tightening indicates that a unit's output changes predominantly reduced available transfer capacity during active fixed-equation intervals.

| Generator unit | Net tightening (MW) | Gross tightening (MW) | Gross relief (MW) | Active cases |
|---|---:|---:|---:|---:|
| TUMUT3 | 31,956.3 | 35,037.5 | 3,081.2 | 61 |
| UPPTUMUT | 7,708.3 | 9,712.7 | 2,004.4 | 61 |
| LIMOSF11 | 3,600.5 | 9,211.0 | 5,610.5 | 85 |
| VBB1 | 2,747.3 | 6,757.8 | 4,010.5 | 11 |
| SUNRSF1 | 2,235.1 | 6,427.7 | 4,192.6 | 85 |
| MUWAWF1 | 1,176.5 | 5,392.1 | 4,215.6 | 39 |
| KIAMSF1 | 1,511.3 | 5,314.7 | 3,803.4 | 38 |
| DARLSF1 | 623.0 | 4,599.5 | 3,976.5 | 78 |
| MERCER01 | 1,409.7 | 4,002.1 | 2,592.5 | 14 |
| AVLSF1 | -490.3 | 3,637.7 | 4,128.0 | 58 |
| ARWF1 | 194.7 | 3,591.7 | 3,397.0 | 37 |
| GPWFEST2 | 2,125.9 | 3,496.3 | 1,370.5 | 6 |
| CUSF1 | -679.9 | 3,439.9 | 4,119.7 | 13 |
| STWF1 | 683.9 | 3,140.4 | 2,456.4 | 85 |
| MURRAY | 1,906.8 | 3,078.0 | 1,171.2 | 58 |
| GPWFEST1 | 1,896.9 | 3,067.7 | 1,170.8 | 6 |
| NEWENSF1 | 682.5 | 2,799.6 | 2,117.1 | 14 |
| NEWENSF2 | 732.5 | 2,778.6 | 2,046.1 | 14 |
| KARSF1 | -214.3 | 2,764.8 | 2,979.1 | 45 |
| BANN1 | 559.7 | 2,688.2 | 2,128.5 | 38 |

## Seasonal contraction frequency and price-cap coincidence

Across the two full seasonal cycles (with December assigned to the following summer year), contraction intensity clusters around seasonal thermal limits, solar-midday congestion, and planned transmission maintenance. Exactly 26 exact Market Price Cap region-intervals occurred in the study window, of which 13 contraction detections coincided with a receiving-region cap interval within the following hour.

| Season | Direction | Detections | Median drop (MW) | Near-cap cases | Cap cases | Rate per 1,000 hours |
|---|---|---:|---:|---:|---:|---:|
| 2024 Spring | Lower | 368 | 531.1 | 0 | 0 | 168.5 |
| 2024 Spring | Upper | 444 | 533.7 | 7 | 3 | 203.3 |
| 2025 Autumn | Lower | 459 | 352.3 | 0 | 0 | 207.9 |
| 2025 Autumn | Upper | 471 | 310.4 | 4 | 0 | 213.3 |
| 2025 Spring | Lower | 502 | 385.2 | 0 | 0 | 229.9 |
| 2025 Spring | Upper | 514 | 422.7 | 2 | 2 | 235.3 |
| 2025 Summer | Lower | 307 | 462.2 | 0 | 0 | 142.1 |
| 2025 Summer | Upper | 425 | 511.3 | 8 | 6 | 196.8 |
| 2025 Winter | Lower | 479 | 275.5 | 0 | 0 | 216.9 |
| 2025 Winter | Upper | 515 | 323.6 | 1 | 0 | 233.2 |
| 2026 Autumn | Lower | 417 | 176.2 | 0 | 0 | 188.9 |
| 2026 Autumn | Upper | 529 | 278.1 | 0 | 0 | 239.6 |
| 2026 Summer | Lower | 451 | 323.3 | 0 | 0 | 208.8 |
| 2026 Summer | Upper | 567 | 330.6 | 2 | 2 | 262.5 |
| 2026 Winter | Lower | 473 | 244.8 | 0 | 0 | 214.2 |
| 2026 Winter | Upper | 565 | 300.5 | 0 | 0 | 255.9 |

## Top reconstructed contraction cases

The table below reports the twenty-five largest selected contractions ranked by baseline-to-trough observed tightening, separating fixed-equation generator ramps, equation-switch composites, and unresolved residuals (values below 0.05 MW rounded cleanly to 0.0 MW).

| Case identifier | Exact-version steps | Complete energy terms | Observed loss (MW) | Generator tightening (MW) | Equation switch (MW) | Unresolved residual (MW) |
|---|---:|---:|---:|---:|---:|---:|
| VNI-upper-20241129T0615 | 100% | 31% | 2,539.2 | 353.0 | 2,166.9 | 0.0 |
| VNI-upper-20241117T1550 | 100% | 50% | 2,351.9 | 276.2 | 2,151.4 | 0.0 |
| VNI-upper-20251126T1040 | 100% | 62% | 2,319.1 | 2,029.0 | 108.3 | 0.0 |
| VNI-upper-20250315T1620 | 100% | 89% | 2,135.0 | 2,258.1 | 36.5 | 0.0 |
| VNI-upper-20250829T0625 | 100% | 67% | 2,057.3 | 1,457.2 | 658.8 | 0.0 |
| VNI-upper-20250513T1615 | 100% | 100% | 1,984.2 | 2,170.2 | 0.0 | 0.0 |
| VNI-lower-20241106T1655 | 100% | 71% | 1,961.3 | 3.5 | 1,842.4 | 0.0 |
| VNI-upper-20260304T1555 | 100% | 80% | 1,939.4 | 1,818.2 | -93.6 | 0.0 |
| VNI-upper-20241121T1750 | 100% | 89% | 1,922.5 | 1,908.3 | 70.7 | 0.0 |
| VNI-lower-20250115T1955 | 100% | 40% | 1,902.7 | 191.6 | 1,708.5 | 0.0 |
| VNI-upper-20250728T2235 | 100% | 80% | 1,877.8 | 694.7 | 191.1 | 0.0 |
| VNI-upper-20251126T1420 | 100% | 57% | 1,812.2 | 1,212.8 | 793.4 | 0.0 |
| VNI-upper-20251010T1735 | 100% | 50% | 1,806.4 | 222.2 | 1,565.3 | 0.0 |
| VNI-upper-20241203T1135 | 100% | 25% | 1,795.7 | 386.0 | 1,394.9 | 0.0 |
| VNI-lower-20251215T0205 | 100% | 58% | 1,785.7 | 232.1 | 696.9 | 0.0 |
| VNI-lower-20250301T1405 | 100% | 83% | 1,760.2 | -290.7 | 150.2 | 0.0 |
| VNI-upper-20260206T1255 | 100% | 0% | 1,755.9 | 1,767.1 | 11.8 | 0.0 |
| VNI-upper-20250528T1630 | 100% | 100% | 1,750.9 | 2,318.7 | 0.0 | 0.0 |
| VNI-lower-20250606T1815 | 100% | 50% | 1,721.8 | 308.5 | 1,321.9 | 0.0 |
| VNI-upper-20250210T1205 | 100% | 67% | 1,711.1 | 440.3 | 1,614.8 | 0.0 |
| VNI-upper-20260205T1340 | 100% | 8% | 1,693.3 | 1,829.0 | -14.2 | 0.0 |
| VNI-upper-20260205T1415 | 100% | 0% | 1,690.7 | 1,774.4 | 0.0 | 0.0 |
| VNI-lower-20260503T0930 | 100% | 81% | 1,686.2 | 254.4 | 1,202.5 | 0.0 |
| VNI-lower-20260409T1710 | 100% | 62% | 1,684.0 | 3,420.7 | 694.7 | 0.0 |
| VNI-upper-20250409T1650 | 100% | 100% | 1,682.6 | 1,857.0 | 0.0 | 0.0 |

## Compression, provenance, and rebuild notes

Version 2 preserves every reconstructed case and five-minute trace from the frozen Version 1 event-atlas evidence while compressing the interactive bundle payload into rounded columnar arrays encoded with gzip and decompressed natively in the browser. All legacy Version 1 atlases remain untouched as frozen baselines. Recompute from retained local archives with `python -m nemic.experiments.event_atlas_v2`.
