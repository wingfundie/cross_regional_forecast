# Heywood (V-SA) two-year sharp-contraction event atlas (Version 2)

## Executive summary and mechanical scope

This standalone event atlas examines every sharp 30-minute directional capacity contraction recorded on Heywood (V-SA) (V-SA, VIC → SA positive) between 1 September 2024 and 31 August 2026 in fixed Australian National Electricity Market time (UTC+10). Across 210,240 five-minute dispatch intervals, the monthly adaptive 90th-percentile screen identifies **7,731 contraction detections** grouping into **5,450 distinct incidents**. Ninety-plus detailed windows (77 contraction cases plus 9 price-only episodes without a nearby contraction) retain complete five-minute unit dispatch, constraint-equation factor reconstruction, coal availability proxies, rooftop solar estimates, and hourly weather context.

> [!TAKEAWAY] Core Operational Takeaway for Heywood (V-SA)
> Contractions on Heywood (V-SA) are associated with a matched observational next-hour peak price jump difference of **$18.29/MWh** relative to same-month, similar-condition control windows (6,734 matched pairs; event-day block-bootstrap 95% confidence interval **$0.17 to $37.54/MWh**). Across the 77 reconstructed cases, **KESSB1** recorded the largest gross fixed-equation tightening contribution, and **63 of 77** selected cases achieved 100% exact equation-version matching on every attribution step.

> [!WARNING] Mechanical Attribution Versus Independent Causation
> Generator contributions quantify mechanical bound sensitivity ($-b_i/a \times \Delta P_i$) along fixed-equation segments of the solved dispatch linear programme. Because regional demand, generator offers, transmission outages, and constraint switches co-move within the same five-minute interval, these figures are mechanical decompositions rather than independent causal estimates. Unresolved right-hand-side terms and equation switches are always reported separately from generator ramps.

## Selected-case generator accounting

Gross tightening and relief are deduplicated across shared five-minute physical steps inside the 77 detailed contraction cases so overlapping case windows never double-count the same dispatch move. Positive net tightening indicates that a unit's output changes predominantly reduced available transfer capacity during active fixed-equation intervals.

| Generator unit | Net tightening (MW) | Gross tightening (MW) | Gross relief (MW) | Active cases |
|---|---:|---:|---:|---:|
| KESSB1 | 2,102.2 | 5,741.3 | 3,639.1 | 41 |
| LIMOSF11 | 1,112.0 | 5,122.0 | 4,010.0 | 47 |
| KIAMSF1 | 1,265.1 | 3,805.2 | 2,540.1 | 51 |
| SUNRSF1 | 1,462.6 | 3,469.8 | 2,007.2 | 47 |
| BLYTHB1 | 1,631.2 | 3,036.6 | 1,405.3 | 12 |
| WEMENSF1 | 582.8 | 2,934.6 | 2,351.8 | 49 |
| BANN1 | 845.7 | 2,857.3 | 2,011.6 | 49 |
| LIMBESS1 | 426.0 | 2,790.4 | 2,364.4 | 24 |
| BRYB1WF1 | 1,004.6 | 2,490.8 | 1,486.1 | 19 |
| YATSF1 | 1,052.2 | 2,404.5 | 1,352.3 | 51 |
| HPR1 | 793.7 | 2,160.8 | 1,367.1 | 18 |
| GSWF1B1 | 905.9 | 2,087.3 | 1,181.4 | 18 |
| KARSF1 | 1,201.8 | 1,924.2 | 722.4 | 51 |
| GSWF1A | 510.9 | 1,887.4 | 1,376.5 | 18 |
| STWF1 | -305.0 | 1,835.6 | 2,140.6 | 47 |
| MUWAWF1 | 612.1 | 1,835.2 | 1,223.1 | 51 |
| BROKENH1 | 496.4 | 1,440.1 | 943.7 | 47 |
| MUWAWF2 | -668.3 | 1,342.6 | 2,010.9 | 51 |
| MURRAY | 1,143.6 | 1,322.4 | 178.7 | 20 |
| GANNSF1 | -18.2 | 1,313.4 | 1,331.6 | 49 |

## Seasonal contraction frequency and price-cap coincidence

Across the two full seasonal cycles (with December assigned to the following summer year), contraction intensity clusters around seasonal thermal limits, solar-midday congestion, and planned transmission maintenance. Exactly 23 exact Market Price Cap region-intervals occurred in the study window, of which 2 contraction detections coincided with a receiving-region cap interval within the following hour.

| Season | Direction | Detections | Median drop (MW) | Near-cap cases | Cap cases | Rate per 1,000 hours |
|---|---|---:|---:|---:|---:|---:|
| 2024 Spring | Lower | 321 | 274.3 | 0 | 0 | 147.0 |
| 2024 Spring | Upper | 390 | 195.4 | 0 | 0 | 178.6 |
| 2025 Autumn | Lower | 431 | 260.9 | 0 | 0 | 195.2 |
| 2025 Autumn | Upper | 441 | 219.4 | 0 | 0 | 199.7 |
| 2025 Spring | Lower | 610 | 260.0 | 0 | 0 | 279.3 |
| 2025 Spring | Upper | 513 | 280.5 | 0 | 0 | 234.9 |
| 2025 Summer | Lower | 411 | 356.7 | 0 | 0 | 190.3 |
| 2025 Summer | Upper | 378 | 266.6 | 2 | 0 | 175.0 |
| 2025 Winter | Lower | 518 | 167.0 | 0 | 0 | 234.6 |
| 2025 Winter | Upper | 724 | 295.5 | 1 | 0 | 327.9 |
| 2026 Autumn | Lower | 574 | 223.3 | 0 | 0 | 260.0 |
| 2026 Autumn | Upper | 436 | 189.8 | 0 | 0 | 197.5 |
| 2026 Summer | Lower | 488 | 308.0 | 0 | 0 | 225.9 |
| 2026 Summer | Upper | 447 | 241.1 | 0 | 0 | 206.9 |
| 2026 Winter | Lower | 517 | 209.8 | 0 | 0 | 234.1 |
| 2026 Winter | Upper | 532 | 208.4 | 4 | 2 | 240.9 |

## Top reconstructed contraction cases

The table below reports the twenty-five largest selected contractions ranked by baseline-to-trough observed tightening, separating fixed-equation generator ramps, equation-switch composites, and unresolved residuals (values below 0.05 MW rounded cleanly to 0.0 MW).

| Case identifier | Exact-version steps | Complete energy terms | Observed loss (MW) | Generator tightening (MW) | Equation switch (MW) | Unresolved residual (MW) |
|---|---:|---:|---:|---:|---:|---:|
| VSA-lower-20260728T1110 | 100% | 92% | 1,243.4 | -1,497.8 | 917.5 | 0.0 |
| VSA-upper-20241106T1440 | 100% | 0% | 1,128.1 | 4.2 | 1,107.6 | 0.0 |
| VSA-lower-20250116T0855 | 0% | 0% | 1,107.1 | 0.0 | 0.0 | 1,107.1 |
| VSA-lower-20250929T1055 | 100% | 91% | 1,107.1 | -98.6 | 1,107.1 | 0.0 |
| VSA-lower-20260604T1640 | 100% | 0% | 1,100.9 | 851.1 | 0.0 | 0.0 |
| VSA-lower-20241220T0635 | 94% | 88% | 1,075.5 | 269.1 | 373.8 | 19.8 |
| VSA-lower-20250424T0825 | 100% | 100% | 1,051.6 | 853.6 | 0.0 | 0.0 |
| VSA-lower-20250513T1350 | 100% | 0% | 1,045.0 | -0.9 | 913.5 | 0.0 |
| VSA-upper-20250618T1835 | 100% | 0% | 1,037.4 | 659.5 | 0.0 | 0.0 |
| VSA-lower-20241017T0920 | 100% | 0% | 1,005.3 | 93.4 | 325.9 | 0.0 |
| VSA-lower-20260218T0800 | 100% | 96% | 980.3 | 229.8 | 171.8 | 0.0 |
| VSA-lower-20250304T0730 | 100% | 95% | 947.9 | 1,085.4 | 65.9 | 0.0 |
| VSA-lower-20251105T0530 | 100% | 75% | 932.9 | -83.2 | 858.0 | 0.0 |
| VSA-lower-20241017T0705 | 100% | 17% | 910.8 | 106.3 | 339.1 | 0.0 |
| VSA-lower-20251120T1315 | 100% | 97% | 906.0 | -0.4 | 546.4 | 0.0 |
| VSA-upper-20250614T1910 | 100% | 0% | 903.7 | 551.1 | 472.9 | 0.0 |
| VSA-lower-20260713T0720 | 100% | 0% | 866.5 | -693.1 | 1,294.5 | 0.0 |
| VSA-lower-20241230T2135 | 75% | 75% | 855.2 | 765.2 | 0.0 | 27.6 |
| VSA-lower-20251112T0635 | 100% | 95% | 853.4 | 345.0 | 197.2 | 0.0 |
| VSA-upper-20260519T1515 | 100% | 92% | 831.6 | 846.7 | 386.3 | 0.0 |
| VSA-lower-20240917T2325 | 100% | 0% | 829.6 | 640.0 | 147.3 | 0.0 |
| VSA-upper-20251213T1610 | 100% | 0% | 829.0 | 184.6 | 148.2 | 0.0 |
| VSA-upper-20250627T1740 | 100% | 0% | 828.3 | 781.8 | 0.0 | 0.0 |
| VSA-upper-20260409T1405 | 100% | 82% | 823.9 | 200.4 | 123.1 | 0.0 |
| VSA-upper-20250207T1825 | 100% | 0% | 819.1 | 416.0 | 0.0 | 0.0 |

## Compression, provenance, and rebuild notes

Version 2 preserves every reconstructed case and five-minute trace from the frozen Version 1 event-atlas evidence while compressing the interactive bundle payload into rounded columnar arrays encoded with gzip and decompressed natively in the browser. All legacy Version 1 atlases remain untouched as frozen baselines. Recompute from retained local archives with `python -m nemic.experiments.event_atlas_v2`.
