# VNI two-year constraint, topology and generator-influence study

## Result and scope

This study reconstructs the constraint-derived `VIC1-NSW1` (VNI) directional envelope at five-minute resolution from **1 September 2024 through 31 August 2026**. It evaluates every directly linked or observed setter equation available inside that same 24-month acquisition window, then separates four operational populations: AEMO binding equations, equations within 50 MW of binding, reported directional setters, and reconstructed envelope leaders.

The broadest generator-pressure candidates by persistence-weighted absolute impact are **MURRAY, LIMOSF11, TUMUT3, SUNRSF1, UPPTUMUT, DARLSF1, STWF1, MUWAWF1**. Their signs and magnitudes vary by equation version and direction, so the forecast representation should use signed `-b/a × ΔMW` pressure under the active constraint regime rather than raw unit generation alone. These are mechanical attributions from solved equations and simultaneous dispatch; they are not independent causal estimates.

## Coverage and integrity

| Item | Result |
|---|---:|
| Analysis window | 1 Sep 2024–31 Aug 2026 |
| Calendar months / seasons | 24 / two complete cycles of each season |
| Five-minute VNI observations | 210,240 |
| Generator DUIDs with valid sensitivities | 232 |
| Exact equation versions researched | 20,827 |
| Distinct constraint IDs researched | 17,382 |
| Reconstructed upper/lower coverage | 99.77% / 99.49% |
| Mean upper/lower reconstruction MAE | 7.11 / 22.55 MW |
| Exact dispatch-to-equation version match | 92.06% |
| Available standing archives | 144 |
| Peak-controlled study footprint at report build | 0.26 GB of 10.00 GB |

Both standing and interval acquisition are hard-bounded to the same two years. The run downloads only six small monthly standing tables and two monthly interval tables. Each interval month is dependency-filtered, reduced to compact Parquet outputs, checked, and its large archives are removed before the following month. The [source manifest](data/vni_2y_source_manifest.json) records every available standing archive, byte size and SHA-256 digest; unavailable monthly table archives are listed explicitly.

The dispatch-supplied exact equation version matched 92.06% of reconstructed rows; remaining rows use the documented time-effective fallback. The upper/lower reconstruction MAE of 7.11/22.55 MW is therefore a material quality diagnostic, and forecast testing should retain the match/fallback flag rather than treating every reconstructed bound as equally certain.

## Seasonal network state

| Season   |   Intervals |   Median flow MW |   Flow P05 | Flow P95   |   Median export limit |   Median import limit | Northward share   | Southward share   |   Reversals |   Forced export |   Forced import | Upper setter match   | Lower setter match   |
|:---------|------------:|-----------------:|-----------:|:-----------|----------------------:|----------------------:|:------------------|:------------------|------------:|----------------:|----------------:|:---------------------|:---------------------|
| Autumn   |       52992 |            204.9 |     -488.6 | 1,049.2    |                 748.2 |                 456.1 | 64.1%             | 35.5%             |        2769 |            6340 |            1660 | 97.4%                | 98.2%                |
| Spring   |       52416 |            380.1 |     -559.1 | 1,123.4    |                 753   |                 469.1 | 69.6%             | 28.3%             |        2358 |            6631 |            2514 | 93.8%                | 91.7%                |
| Summer   |       51840 |            117.7 |     -672.4 | 1,073.5    |                 622.5 |                 475.3 | 56.4%             | 41.7%             |        2521 |           11574 |            2396 | 95.3%                | 94.3%                |
| Winter   |       52992 |            222.3 |     -511.4 | 1,072.7    |                 831.6 |                 411   | 63.4%             | 36.6%             |        2716 |            2404 |            4635 | 92.9%                | 96.7%                |

Spring’s median flow was 380.1 MW, with a 28.3% share of southward intervals. Seasonal medians describe the realised mix of demand, renewable output, outages, dispatch and constraint regimes. They do not isolate a single physical driver.

The full machine-readable seasonal summaries are [network state](data/vni_2y_seasonal_summary.csv), [constraint populations](data/vni_2y_constraint_population_by_season.csv), and [generator influence by season and direction](data/vni_2y_generator_seasonal_rankings.csv).

The HTML report adds a seasonal generator-pressure heatmap for the twelve highest two-year contributors. It makes it easy to distinguish persistent units such as MURRAY from units whose exposure is concentrated in one season.

## Diurnal behaviour

The [48-bin diurnal table](data/vni_2y_diurnal_summary.csv) contains mean, median, P05 and P95 flow; median and P05 directional limits; directional-flow shares; reversal counts; and forced-direction interval counts for every half-hour of the day across the two-year sample. This preserves the morning ramp, solar-hours transfer pattern, evening ramp and overnight regime without adding 48 raw dummy variables to a forecast.

For modelling, compress the diurnal shape into clock sine/cosine, season × clock interactions, and a small set of learned training-only profiles or principal components. Retain explicit ramp-window flags only when cross-validation shows they improve event forecasts.

The HTML report also shows reversal and forced-export/import rates by half-hour. These event-rate curves are useful for identifying ramp windows and directional-regime risk before adding any high-cardinality clock features.

## Sharp limit contractions

A sharp contraction is a fall in the reported directional limit over 30 minutes that is at or above the **90th percentile of positive 30-minute falls within the same calendar month and direction**. The threshold is recalculated by month and direction so the study captures locally exceptional moves across different seasonal regimes. `Contraction onset` marks the first five-minute interval of each contiguous contraction episode, preventing a sustained move from being presented as a new event at every interval.

| Direction   |   Episodes |   Median drop MW |   P90 drop MW | Maximum drop MW   |   Episodes ≥250 MW |   Episodes ≥500 MW |   Episodes ≥1,000 MW |   Minimum monthly threshold MW |   Median monthly threshold MW |   Maximum monthly threshold MW |
|:------------|-----------:|-----------------:|--------------:|:------------------|-------------------:|-------------------:|---------------------:|-------------------------------:|------------------------------:|-------------------------------:|
| lower       |       3455 |            316.7 |         785.1 | 1,952.6           |               2325 |                902 |                  146 |                          137.1 |                         224.4 |                          470.5 |
| upper       |       4029 |            349.9 |         661.9 | 2,142.4           |               3791 |                940 |                  100 |                          219.7 |                         259.7 |                          479   |

Across the full study there were **7,484 directional contraction episodes**. The largest observed episode began at **2024-11-17 15:50:00**, when the upper directional limit fell **2,142.4 MW** over 30 minutes and the reconstructed leading constraint was `N::N_MNYS_2`. Very large moves, especially those ending in negative reported limits, should be reviewed as forced-flow or ramp-constraint regimes rather than treated as ordinary capacity changes.

Event timing and drop size come directly from the reported directional-limit series. Generator attribution then uses the reconstructed leading equation and mapped unit sensitivities, so the 92.06% exact-version match rate and fallback flag remain material when interpreting unit ranks.

### Seasonal contraction pattern

| Season   | Direction   |   Episodes |   Median drop MW |   P90 drop MW | Maximum drop MW   |
|:---------|:------------|-----------:|-----------------:|--------------:|:------------------|
| Autumn   | lower       |        876 |            264.4 |         599   | 1,560.9           |
| Autumn   | upper       |       1000 |            291.8 |         497.1 | 1,563.6           |
| Spring   | lower       |        870 |            459.2 |         982.3 | 1,952.6           |
| Spring   | upper       |        957 |            481.2 |         790.7 | 2,142.4           |
| Summer   | lower       |        757 |            413.8 |         905.2 | 1,726.8           |
| Summer   | upper       |        992 |            410.3 |         693.3 | 1,673.1           |
| Winter   | lower       |        952 |            257   |         538.5 | 1,484.8           |
| Winter   | upper       |       1080 |            311.4 |         492.1 | 1,760.4           |

### Generators exposed during contractions

The contraction leaderboard ranks units by the sum of **positive equation-derived tightening pressure only during contraction intervals**. This corrects the earlier report build, which displayed a contraction rank based on tightening across all intervals. Upper-direction leaders were **TUMUT3, LIMOSF11, SUNRSF1, DARLSF1, AVLSF1**; lower-direction leaders were **MURRAY, MUWAWF1, KIAMSF1, LIMOSF11, TUMUT3**.

|   Rank | DUID     |   Contraction rows |   Episode-onset exposures | Positive tightening MW-observations   |   Mean positive tightening MW | Positive tightening share   |
|-------:|:---------|-------------------:|--------------------------:|:--------------------------------------|------------------------------:|:----------------------------|
|      1 | TUMUT3   |               9166 |                      2793 | 1,491,382                             |                        162.71 | 37.2%                       |
|      2 | LIMOSF11 |              18240 |                      6599 | 1,435,836                             |                         78.72 | 47.3%                       |
|      3 | SUNRSF1  |              18240 |                      6599 | 949,765                               |                         52.07 | 49.2%                       |
|      4 | MURRAY   |              15871 |                      5995 | 900,971                               |                         56.77 | 36.4%                       |
|      5 | DARLSF1  |              16649 |                      6010 | 530,759                               |                         31.88 | 47.2%                       |
|      6 | UPPTUMUT |               9294 |                      2838 | 514,434                               |                         55.35 | 43.0%                       |
|      7 | KIAMSF1  |               8305 |                      3365 | 500,011                               |                         60.21 | 33.0%                       |
|      8 | MUWAWF1  |               9303 |                      3724 | 480,883                               |                         51.69 | 39.2%                       |
|      9 | AVLSF1   |               9084 |                      3462 | 456,063                               |                         50.21 | 52.7%                       |
|     10 | VBB1     |               3786 |                      1411 | 349,011                               |                         92.18 | 38.8%                       |
|     11 | COLEASF1 |              16648 |                      6011 | 289,509                               |                         17.39 | 46.1%                       |
|     12 | MUWAWF2  |               9283 |                      3719 | 286,745                               |                         30.89 | 42.9%                       |
|     13 | MOORAWF1 |               4224 |                      1568 | 268,843                               |                         63.65 | 51.5%                       |
|     14 | STWF1    |              18622 |                      6707 | 268,842                               |                         14.44 | 38.5%                       |
|     15 | KARSF1   |              10074 |                      4206 | 259,010                               |                         25.71 | 35.9%                       |

`Positive tightening share` is the fraction of a unit's contraction-state equation rows in which its 30-minute movement mechanically tightened the active directional bound. A unit can rank highly through a smaller number of very large conditional impacts. For example, TUMUT3 ranks first overall even though its pressure is positive in only 37.2% of its contraction-state rows. This does not mean every unit movement contracts VNI or that the movement independently caused the observed limit change.

The most frequently leading reconstructed constraints at contraction onsets were:

| Direction   | Leading constraint   |   Episodes |   Median drop MW | Maximum drop MW   |
|:------------|:---------------------|-----------:|-----------------:|:------------------|
| lower       | I_6F_NS_150          |        715 |            509.4 | 1,679.4           |
| lower       | N^^V_NIL_1           |        675 |            229.8 | 1,583.8           |
| lower       | N^^V_NIL_ARWBBA      |        469 |            231.6 | 1,184.9           |
| lower       | V>>NIL_MLGT_MLGT     |        233 |            333.8 | 1,480.7           |
| lower       | N^^V_CTMN_1          |        150 |            397.4 | 1,209.1           |
| lower       | N>>NIL_BU_PST_ML_W   |        121 |            437.6 | 1,383.2           |
| upper       | N^^N_NIL_WGLT        |        839 |            331.5 | 1,147.3           |
| upper       | N^^N_NIL_X5_BESH     |        334 |            423.8 | 1,565.6           |
| upper       | V::N_NIL_V2          |        252 |            283.7 | 592.3             |
| upper       | N^^N_NIL_X5_BEKG     |        216 |            395.6 | 1,251.4           |
| upper       | N>>BDBU_970_051      |        215 |            590.8 | 1,351.1           |
| upper       | V::N_NIL_V1          |        170 |            275.4 | 502.7             |

The full event ledger, adaptive monthly thresholds, constraint episode summary and direction-specific generator rankings are available in [contraction events](data/vni_2y_contraction_events.csv), [monthly thresholds](data/vni_2y_contraction_thresholds_monthly.csv), [contraction constraints](data/vni_2y_contraction_constraints.csv), and [generator contraction rankings](data/vni_2y_generator_contraction_rankings.csv).

## Generator influence

`Abs impact MW-observations` sums `abs(-b/a × ΔMW)` while a unit appears in an applicable VNI equation. Tightening preserves the direction-specific sign; contraction rank uses positive tightening during sharp-contraction intervals, while reversal and forced ranks count event exposure. `Flow-move rho` is a weighted monthly Spearman association, not causation.

|   Rank | DUID     |   Active months |   Equation versions | Abs impact MW-observations   |   Mean abs impact MW | P95 abs impact MW   | Tightening MW-observations   |   Contraction rank |   Reversal rank |   Forced rank |   Flow-move rho |
|-------:|:---------|----------------:|--------------------:|:-----------------------------|---------------------:|:--------------------|:-----------------------------|-------------------:|----------------:|--------------:|----------------:|
|      1 | MURRAY   |              24 |                9031 | 9,396,145                    |               25.997 | 208.290             | 5,109,021                    |                  4 |               7 |            27 |           0.148 |
|      2 | LIMOSF11 |              24 |               18011 | 6,353,232                    |               19.171 | 359.167             | 3,826,195                    |                  2 |               4 |             4 |           0.184 |
|      3 | TUMUT3   |              24 |               10759 | 5,290,267                    |               43.909 | 1,132.969           | 3,113,576                    |                  1 |              21 |            37 |           0.131 |
|      4 | SUNRSF1  |              24 |               18011 | 4,826,413                    |               14.429 | 216.327             | 2,803,860                    |                  3 |               4 |             4 |           0.168 |
|      5 | UPPTUMUT |              24 |               10850 | 4,699,537                    |               23.38  | 324.925             | 2,491,376                    |                  6 |              20 |            36 |           0.092 |
|      6 | DARLSF1  |              24 |               15423 | 4,239,370                    |               13.494 | 205.377             | 2,266,126                    |                  5 |               9 |             8 |           0.149 |
|      7 | STWF1    |              24 |               18275 | 3,415,561                    |                9.436 | 76.881              | 1,655,683                    |                 14 |               1 |             2 |           0.016 |
|      8 | MUWAWF1  |              24 |                5423 | 3,080,831                    |               22.506 | 373.099             | 1,727,270                    |                  8 |              32 |            41 |           0.091 |
|      9 | AVLSF1   |              24 |               12454 | 2,965,466                    |               30.217 | 430.972             | 1,597,201                    |                  9 |              35 |            19 |           0.148 |
|     10 | COLEASF1 |              24 |               15352 | 2,462,983                    |                7.902 | 126.350             | 1,275,131                    |                 11 |               8 |             7 |           0.129 |
|     11 | KIAMSF1  |              24 |                6450 | 2,425,130                    |               56.477 | 694.917             | 1,461,269                    |                  7 |              40 |            50 |          -0.066 |
|     12 | MUWAWF2  |              24 |                5400 | 2,406,573                    |               17.695 | 198.348             | 1,314,096                    |                 12 |              33 |            43 |           0.077 |
|     13 | CUSF1    |              14 |                2979 | 2,219,134                    |               45.396 | 425.089             | 1,163,999                    |                 19 |              98 |            40 |           0.039 |
|     14 | ARWF1    |              24 |                4781 | 2,039,637                    |               15.265 | 243.178             | 1,033,158                    |                 23 |              39 |            46 |           0.066 |
|     15 | RIVNB2   |              24 |               13492 | 2,013,495                    |               11.522 | 172.872             | 1,060,037                    |                 30 |              16 |            10 |           0.038 |
|     16 | VBB1     |              24 |                3814 | 1,887,395                    |              123.472 | 2,385.220           | 1,085,289                    |                 10 |              87 |           105 |           0.063 |
|     17 | HILLSTN1 |              24 |               14787 | 1,817,310                    |               13.013 | 469.321             | 960,612                      |                 18 |              25 |            18 |           0.133 |
|     18 | WLWLSF1  |              24 |               10378 | 1,657,729                    |               11.012 | 194.564             | 853,487                      |                 27 |              22 |            30 |           0.125 |
|     19 | WLWLSF2  |              24 |               10378 | 1,624,772                    |               10.729 | 195.837             | 836,766                      |                 29 |              22 |            30 |           0.126 |
|     20 | MOORAWF1 |              24 |                4084 | 1,624,071                    |               92.658 | 1,684.108           | 934,594                      |                 13 |              78 |            92 |           0.091 |

The complete ranking, factor extrema, equation-version coverage and event measures are in [vni_2y_generator_rankings.csv](data/vni_2y_generator_rankings.csv). The compressed [unit-by-equation factor file](data/vni_2y_unit_equation_factors.csv.gz) preserves every distinct exact-version `b` coefficient, VNI `a` coefficient and derived `-b/a` sensitivity. Seasonal ranks should be used to decide which unit-specific pressure terms are stable enough to keep. Units that rank highly in only one season should be pooled into constraint-family or regional pressure features until an untouched period confirms persistence.

## Binding, near-binding, setter and leading equations

`Binding` means absolute published marginal value above numerical zero. `Near binding` means solved constraint slack divided by the absolute VNI coefficient is between 0 and 50 MW. `Near setting` means the equation’s implied bound is within 50 MW of the reconstructed directional envelope. `Leading` means it is the reconstructed tightest valid upper or lower equation. Reported setters come from `EXPORTGENCONID` and `IMPORTGENCONID`; reconstructed leaders are kept separately so disagreement remains visible.

The 40 most operationally relevant exact versions are shown below. The [complete equation file](data/vni_2y_constraint_equations.csv) includes every researched exact version, VNI coefficient, description, constraint-set membership, overlapping invoked sets, applicable counts, binding/near-binding/near-setting counts, leading counts, marginal-value summary and VNI-normalised slack.

| Direction   | Constraint        |   Version |   VNI coefficient |   Binding |   Near binding |   Near setting |   Leading | Type                | Constraint sets                                                                                                                                                                                                  |
|:------------|:------------------|----------:|------------------:|----------:|---------------:|---------------:|----------:|:--------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| lower       | N^^V_NIL_1        |         1 |           -1      |      3325 |           3937 |          40582 |     36897 | Voltage Stability   | V-NIL                                                                                                                                                                                                            |
| lower       | N^^V_NIL_1        |         1 |           -1      |      3947 |           4859 |          28793 |     23203 | Voltage Stability   | V-NIL                                                                                                                                                                                                            |
| lower       | N^^V_NIL_ARWBBA   |         1 |           -1      |       662 |            857 |          22812 |     18698 | Voltage Stability   | V-NIL                                                                                                                                                                                                            |
| lower       | N^^V_NIL_ARWBBA   |         1 |           -1      |      1066 |           1516 |          22949 |     18312 | Voltage Stability   | V-NIL                                                                                                                                                                                                            |
| upper       | V^^N_NIL_1        |         1 |            1      |     11838 |          12997 |          23875 |     17987 | Voltage Stability   | V-NIL                                                                                                                                                                                                            |
| lower       | N^^V_NIL_ARWBBA   |         1 |           -1      |       440 |            660 |          14322 |     12101 | Voltage Stability   | V-NIL                                                                                                                                                                                                            |
| upper       | V::N_NIL_V1       |         1 |            1      |       424 |           1168 |          17875 |     11727 | Transient Stability | V-NIL                                                                                                                                                                                                            |
| lower       | N^^V_NIL_1        |         1 |           -1      |       786 |           1009 |          12798 |     11350 | Voltage Stability   | V-NIL                                                                                                                                                                                                            |
| lower       | N^^V_CTMN_1       |         1 |           -1      |      1086 |           1266 |          11669 |      9673 | Voltage Stability   | N-4+1_WG_CLOSE, N-CTMN_4_WG_CLOSE, N-CTMN_4_WG_OPEN, N-CTYS_3L_WG_CLOSE, N-CTYS_3L_WG_OPEN, N-MNYS_5_WG_CLOSE                                                                                                    |
| upper       | V::N_NIL_V2       |         1 |            1      |      1426 |           2709 |          13560 |      9513 | Transient Stability | V-NIL                                                                                                                                                                                                            |
| upper       | N^^N_NIL_WGLT     |         4 |            0.376  |      6544 |           5677 |           8746 |      8236 | Voltage Stability   | N-NIL                                                                                                                                                                                                            |
| upper       | V::N_NIL_V2       |         1 |            1      |       585 |           1396 |          16212 |      7757 | Transient Stability | V-NIL                                                                                                                                                                                                            |
| lower       | N^^V_CTMN_1       |         1 |           -1      |      1138 |           1557 |           9231 |      7286 | Voltage Stability   | N-4+1_WG_CLOSE, N-CTMN_4_WG_CLOSE, N-CTMN_4_WG_OPEN, N-CTYS_3L_WG_CLOSE, N-CTYS_3L_WG_OPEN, N-MNYS_5_WG_CLOSE                                                                                                    |
| upper       | V^^N_MNYS_1       |         1 |            0.249  |      2136 |           2556 |           6959 |      6282 | Voltage Stability   | N-CTMN_4_WG_CLOSE, N-CTMN_4_WG_OPEN, N-CTYS_3L_WG_CLOSE, N-CTYS_3L_WG_OPEN, N-MNYS_5_WG_CLOSE                                                                                                                    |
| upper       | V>>N_NIL_65_051   |         2 |            1      |      2343 |           2386 |           6790 |      5660 | Thermal             | N-NIL                                                                                                                                                                                                            |
| lower       | N^^V_JNWG_63_X5_1 |         1 |           -1      |      1151 |           1156 |           5196 |      5158 | Voltage Stability   | N-CLCWG_X5, N-JNWG_RADIAL, N-JNWL_X5, N-WGWA_63, N-WGWA_63_X5, N-WGWA_RADIAL, N-WGWA_X5                                                                                                                          |
| lower       | N^^V_BADP_1       |         1 |           -1      |       756 |            862 |           5431 |      5142 | Voltage Stability   | I-JNWO_RADIAL, I-JNWO_X5, I-X_BABU_BURC, N-BABU, N-BADP, N-CLCWG_X5, N-JNWG_RADIAL, N-JNWL_X5, N-LTWG_RADIAL, N-LTWG_X5, N-WGWA_63, N-WGWA_63_X5, N-WGWA_RADIAL, N-WGWA_X5, N-X_051_X5, V-DDWO_RADIAL, V-DDWO_X5 |
| upper       | N^^N_NIL_WGLT     |         2 |            0.376  |      3792 |           3307 |           5204 |      4881 | Voltage Stability   | N-NIL                                                                                                                                                                                                            |
| lower       | N^^V_NIL_1        |         1 |           -1      |       228 |            268 |           5372 |      4849 | Voltage Stability   | V-NIL                                                                                                                                                                                                            |
| upper       | V^^N_MNYS_1       |         1 |            0.249  |      1873 |           2154 |           5734 |      4739 | Voltage Stability   | N-CTMN_4_WG_CLOSE, N-CTMN_4_WG_OPEN, N-CTYS_3L_WG_CLOSE, N-CTYS_3L_WG_OPEN, N-MNYS_5_WG_CLOSE                                                                                                                    |
| upper       | V::N_NIL_O2       |         1 |            1      |       711 |           1916 |          10945 |      4549 | Transient Stability | V-NIL                                                                                                                                                                                                            |
| upper       | V::N_NIL_V2       |         1 |            1      |      1113 |           1137 |           4593 |      4051 | Transient Stability | V-NIL                                                                                                                                                                                                            |
| upper       | V::N_NIL_V1       |         1 |            1      |       494 |           1059 |           7276 |      3775 | Transient Stability | V-NIL                                                                                                                                                                                                            |
| upper       | V>>N_NIL_65_66    |         1 |            0.8    |       188 |            368 |           5494 |      3436 | Thermal             | N-NIL                                                                                                                                                                                                            |
| lower       | N^^V_MLNK_1       |         1 |           -1      |       193 |            371 |           4001 |      3411 | Voltage Stability   |                                                                                                                                                                                                                  |
| lower       | N^^V_CNCW_1       |         1 |           -1      |       441 |            702 |           5361 |      3382 | Voltage Stability   | N-DTKV_18_WG_CLOSE, N-DTKV_18_WG_OPEN, N-KVCW_3W_WG_CLOSE                                                                                                                                                        |
| lower       | N^^V_LTUT_1       |         1 |           -1      |       559 |            613 |           3452 |      3162 | Voltage Stability   | I-X_64+67/68, I-X_64_DDSM, N-LTUT_64_15M                                                                                                                                                                         |
| upper       | N>>BDBU_970_051   |         1 |            0.0884 |      2624 |           3392 |           4406 |      2842 | Thermal             | I-BDBU_ONE                                                                                                                                                                                                       |
| lower       | N^^V_MLNK_1       |         1 |           -1      |       675 |            796 |           3602 |      2821 | Voltage Stability   |                                                                                                                                                                                                                  |
| upper       | N^^N_NIL_X5_BESH  |         1 |            0.12   |      2472 |           2807 |           3796 |      2811 | Voltage Stability   | N-NIL                                                                                                                                                                                                            |
| upper       | V::N_SMSC_V1      |         1 |            1      |       415 |            828 |           3936 |      2739 | Transient Stability | V-SMSC                                                                                                                                                                                                           |
| upper       | V>>N_NIL_65_051   |         1 |            1      |       568 |            673 |           3519 |      2733 | Thermal             | N-NIL                                                                                                                                                                                                            |
| lower       | I_6F_NS_150       |         2 |           -0.106  |      1318 |           1179 |           2875 |      2668 | Other               | I-6F_NS_150, N-NIL                                                                                                                                                                                               |
| upper       | V::N_NIL_O1       |         1 |            1      |       570 |           1557 |          11328 |      2477 | Transient Stability | V-NIL                                                                                                                                                                                                            |
| upper       | N^^N_NIL_WGLT     |         1 |            0.376  |      1598 |           1485 |           2510 |      2299 | Voltage Stability   | N-NIL                                                                                                                                                                                                            |
| upper       | N>>NIL_990_051    |         1 |            0.385  |      1793 |           1766 |           3176 |      2224 | Thermal             | N-NIL                                                                                                                                                                                                            |
| upper       | N>>NIL_998_18     |         1 |            0.0861 |      1163 |           1311 |           2627 |      2180 | Thermal             | N-NIL, N-NIL_998                                                                                                                                                                                                 |
| upper       | N>>NIL_970_051    |         1 |            0.0891 |      1512 |           4487 |           5851 |      2128 | Thermal             | N-NIL                                                                                                                                                                                                            |
| upper       | N::N_CNLT_2       |         1 |            0.9819 |      1184 |           1128 |           2384 |      2070 | Transient Stability | N-CNLT_07                                                                                                                                                                                                        |
| upper       | N^^N_NIL_X5_BEKG  |         1 |            0.12   |      1365 |           1669 |           2829 |      2056 | Voltage Stability   | N-NIL                                                                                                                                                                                                            |

## Compact feature design

Use a compact network-state block of roughly 20–30 continuous variables plus small categorical encodings:

1. Conditional upper/lower envelope, flow room, runner-up switch gaps and envelope-move persistence.
2. Aggregate signed generator tightening and relief for each direction, plus 30-minute pressure changes.
3. Ramp-and-availability-limited relief, candidate counts and pressure-completeness fractions.
4. Reported setter and reconstructed leader families as separate low-cardinality encodings, with a disagreement flag.
5. Four to eight frozen unit-pressure features chosen only on training history; pool the remaining units by constraint family, region or hydro/thermal/renewable class.
6. Seasonal and diurnal context through two clock harmonics, two annual harmonics, and selected season × clock interactions.
7. Regime flags for binding, near-binding, near-setting, forced-direction limits, crossed envelopes and recent leader switches.

This representation keeps topology-dependent signs while avoiding one variable per generator or constraint. The exact leader ID is valuable for diagnosis, but operational forecasts should also carry top-K candidate summaries because the active equation can switch within the horizon.

The reusable [feature dictionary](data/vni_2y_feature_dictionary.csv) records each feature group, unit, definition and recommended variable count. The configuration and orchestrator accept the interconnector ID, dates, thresholds and storage limits as parameters, so the same method can be applied to another interconnector after its study config is reviewed.

## Calculation method

For each exact effective generic-constraint version:

```text
a * VNI + sum(b_i * P_i) + other solved terms <= RHS
conditional VNI bound = observed VNI flow + (RHS - solved LHS) / a
unit sensitivity = -b_i / a
30-minute unit pressure = sensitivity * (P_i[t] - P_i[t-30m])
```

Positive `a` yields an upper signed-flow bound; negative `a` yields a lower bound. The minimum upper and maximum lower valid candidates form the reconstructed envelope. Constraint versions are matched using dispatch-supplied effective date/version where available, with time-effective fallback recorded by the feature audit. The first 30 minutes of each independently processed month lack a within-file 30-minute unit change and are excluded from movement attribution; this affects 12 hours across two years, about 0.07% of the study timeline, while equation, binding, limit, flow, seasonal and diurnal coverage remain intact.

## Interpretation limits and testing use

- Generator rankings describe mechanical exposure under observed dispatch and constraint regimes. Simultaneous system responses prevent a causal claim.
- Reported directional limits depend on solved dispatch and should not be interpreted as independent transmission ratings or jointly feasible counterfactual capacities.
- Near-binding and near-setting thresholds are both 50 MW in VNI-normalised space and should be sensitivity-tested at 25 and 100 MW before feature selection is frozen.
- Feature selection must use training seasons only. Evaluate the frozen compact block on a later untouched chronological period against persistence, reported-setter history and a non-topological fundamentals baseline.
- Forecast-horizon pressure requires lagged dispatch plus generator scenarios or unit forecasts. Realised future dispatch must never enter an operational backtest.

## Rebuild

```powershell
python -m nemic.constraint_longitudinal run --config configs/constraint_vni_2y.json
python scripts/build_vni_two_year_report.py --config configs/constraint_vni_2y.json
python scripts/build_docs_html.py
python -m unittest discover -s tests -v
```
