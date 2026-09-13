# VSA two-year constraint, topology and generator-influence study

## Result and scope

This study reconstructs the constraint-derived `V-SA` (VSA) directional envelope at five-minute resolution from **1 September 2024 through 31 August 2026**. It evaluates every directly linked or observed setter equation available inside that same 24-month acquisition window, then separates four operational populations: AEMO binding equations, equations within 50 MW of binding, reported directional setters, and reconstructed envelope leaders.

The broadest generator-pressure candidates by persistence-weighted absolute impact are **KIAMSF1, LIMOSF11, WEMENSF1, BANN1, KESSB1, MUWAWF1, SUNRSF1, KARSF1**. Their signs and magnitudes vary by equation version and direction, so the forecast representation should use signed `-b/a × ΔMW` pressure under the active constraint regime rather than raw unit generation alone. These are mechanical attributions from solved equations and simultaneous dispatch; they are not independent causal estimates.

## Coverage and integrity

| Item | Result |
|---|---:|
| Analysis window | 1 Sep 2024–31 Aug 2026 |
| Calendar months / seasons | 24 / two complete cycles of each season |
| Five-minute VSA observations | 210,240 |
| Generator DUIDs with valid sensitivities | 224 |
| Exact equation versions researched | 16,488 |
| Distinct constraint IDs researched | 13,836 |
| Reconstructed upper/lower coverage | 99.65% / 99.65% |
| Mean upper/lower reconstruction MAE | 126.78 / 130.01 MW |
| Exact dispatch-to-equation version match | 79.73% |
| Available standing archives | 144 |
| Peak-controlled study footprint at report build | 0.17 GB of 10.00 GB |

Both standing and interval acquisition are hard-bounded to the same two years. The run downloads only six small monthly standing tables and two monthly interval tables. Each interval month is dependency-filtered, reduced to compact Parquet outputs, checked, and its large archives are removed before the following month. The [source manifest](data/vsa_2y_source_manifest.json) records every available standing archive, byte size and SHA-256 digest; unavailable monthly table archives are listed explicitly.

The dispatch-supplied exact equation version matched 79.73% of reconstructed rows; remaining rows use the documented time-effective fallback. The upper/lower reconstruction MAE of 126.78/130.01 MW is therefore a material quality diagnostic, and forecast testing should retain the match/fallback flag rather than treating every reconstructed bound as equally certain.

## Seasonal network state

| Season   |   Intervals |   Median flow MW |   Flow P05 |   Flow P95 |   Median export limit |   Median import limit | Westward share   | Eastward share   |   Reversals |   Forced export |   Forced import | Upper setter match   | Lower setter match   |
|:---------|------------:|-----------------:|-----------:|-----------:|----------------------:|----------------------:|:------------------|:------------------|------------:|----------------:|----------------:|:---------------------|:---------------------|
| Autumn   |       52992 |            201.3 |     -394.6 |      586.9 |                 480.1 |                 313.2 | 71.6%             | 28.4%             |        2610 |            3132 |            8320 | 81.2%                | 91.6%                |
| Spring   |       52416 |            -33.4 |     -539.5 |      556.5 |                 376.3 |                 486.4 | 46.8%             | 53.1%             |        2276 |            4280 |            3206 | 67.9%                | 65.7%                |
| Summer   |       51840 |            115.7 |     -486.3 |      575   |                 423.6 |                 349.1 | 62.3%             | 37.7%             |        2576 |            4565 |           11135 | 76.9%                | 82.5%                |
| Winter   |       52992 |             48.6 |     -432.2 |      545.9 |                 238.8 |                 211.3 | 56.7%             | 43.2%             |        2970 |            8178 |            8109 | 60.3%                | 61.8%                |

Spring’s median flow was -33.4 MW, with a 53.1% share of eastward intervals. Seasonal medians describe the realised mix of demand, renewable output, outages, dispatch and constraint regimes. They do not isolate a single physical driver.

The full machine-readable seasonal summaries are [network state](data/vsa_2y_seasonal_summary.csv), [constraint populations](data/vsa_2y_constraint_population_by_season.csv), and [generator influence by season and direction](data/vsa_2y_generator_seasonal_rankings.csv).

The HTML report adds a seasonal generator-pressure heatmap for the twelve highest two-year contributors. It makes it easy to distinguish persistent units such as KIAMSF1 from units whose exposure is concentrated in one season.

## Diurnal behaviour

The [48-bin diurnal table](data/vsa_2y_diurnal_summary.csv) contains mean, median, P05 and P95 flow; median and P05 directional limits; directional-flow shares; reversal counts; and forced-direction interval counts for every half-hour of the day across the two-year sample. This preserves the morning ramp, solar-hours transfer pattern, evening ramp and overnight regime without adding 48 raw dummy variables to a forecast.

For modelling, compress the diurnal shape into clock sine/cosine, season × clock interactions, and a small set of learned training-only profiles or principal components. Retain explicit ramp-window flags only when cross-validation shows they improve event forecasts.

The HTML report also shows reversal and forced-export/import rates by half-hour. These event-rate curves are useful for identifying ramp windows and directional-regime risk before adding any high-cardinality clock features.

## Sharp limit contractions

A sharp contraction is a fall in the reported directional limit over 30 minutes that is at or above the **90th percentile of positive 30-minute falls within the same calendar month and direction**. The threshold is recalculated by month and direction so the study captures locally exceptional moves across different seasonal regimes. `Contraction onset` marks the first five-minute interval of each contiguous contraction episode, preventing a sustained move from being presented as a new event at every interval.

| Direction   |   Episodes |   Median drop MW |   P90 drop MW | Maximum drop MW   |   Episodes ≥250 MW |   Episodes ≥500 MW |   Episodes ≥1,000 MW |   Minimum monthly threshold MW |   Median monthly threshold MW |   Maximum monthly threshold MW |
|:------------|-----------:|-----------------:|--------------:|:------------------|-------------------:|-------------------:|---------------------:|-------------------------------:|------------------------------:|-------------------------------:|
| lower       |       3867 |            258.3 |         426   | 1,107.1           |               2049 |                192 |                    1 |                          123.3 |                         194   |                          325.3 |
| upper       |       3859 |            236.2 |         416.6 | 1,050.1           |               1707 |                158 |                    2 |                          123   |                         168.3 |                          281.9 |

Across the full study there were **7,726 directional contraction episodes**. The largest observed episode began at **2025-09-29 10:55:00**, when the lower directional limit fell **1,107.1 MW** over 30 minutes and the reconstructed leading constraint was `V^^V_NIL_KGTS`. Very large moves, especially those ending in negative reported limits, should be reviewed as forced-flow or ramp-constraint regimes rather than treated as ordinary capacity changes.

Event timing and drop size come directly from the reported directional-limit series. Generator attribution then uses the reconstructed leading equation and mapped unit sensitivities, so the 79.73% exact-version match rate and fallback flag remain material when interpreting unit ranks.

### Seasonal contraction pattern

| Season   | Direction   |   Episodes |   Median drop MW |   P90 drop MW | Maximum drop MW   |
|:---------|:------------|-----------:|-----------------:|--------------:|:------------------|
| Autumn   | lower       |       1005 |            236.7 |         389.7 | 884.5             |
| Autumn   | upper       |        876 |            203.5 |         349.7 | 738.2             |
| Spring   | lower       |        931 |            267.3 |         447.8 | 1,107.1           |
| Spring   | upper       |        903 |            248.6 |         424.4 | 1,050.1           |
| Summer   | lower       |        899 |            331.5 |         494.1 | 800.3             |
| Summer   | upper       |        824 |            254.1 |         394.8 | 781.3             |
| Winter   | lower       |       1032 |            186   |         335.7 | 840.4             |
| Winter   | upper       |       1256 |            235.8 |         447.8 | 1,037.4           |

### Generators exposed during contractions

The contraction leaderboard ranks units by the sum of **positive equation-derived tightening pressure only during contraction intervals**. This corrects the earlier report build, which displayed a contraction rank based on tightening across all intervals. Upper-direction leaders were **MURRAY, BLYTHB1, GSWF1A, GSWF1B1, PAREPW1**; lower-direction leaders were **LIMOSF11, KIAMSF1, MUWAWF1, WEMENSF1, SUNRSF1**.

|   Rank | DUID     |   Contraction rows |   Episode-onset exposures | Positive tightening MW-observations   |   Mean positive tightening MW | Positive tightening share   |
|-------:|:---------|-------------------:|--------------------------:|:--------------------------------------|------------------------------:|:----------------------------|
|      1 | KIAMSF1  |              11975 |                      4860 | 415,724                               |                         34.72 | 43.0%                       |
|      2 | LIMOSF11 |              10302 |                      4145 | 412,100                               |                         40    | 42.6%                       |
|      3 | MUWAWF1  |              11767 |                      4778 | 285,822                               |                         24.29 | 32.1%                       |
|      4 | SUNRSF1  |              10302 |                      4145 | 283,596                               |                         27.53 | 44.6%                       |
|      5 | WEMENSF1 |              11637 |                      4710 | 277,160                               |                         23.82 | 42.8%                       |
|      6 | BANN1    |              11637 |                      4710 | 255,241                               |                         21.93 | 43.4%                       |
|      7 | KARSF1   |              11911 |                      4835 | 237,851                               |                         19.97 | 42.2%                       |
|      8 | KESSB1   |               9524 |                      3900 | 222,238                               |                         23.33 | 13.5%                       |
|      9 | YATSF1   |              11911 |                      4835 | 208,457                               |                         17.5  | 43.8%                       |
|     10 | MURRAY   |               5720 |                      2230 | 187,228                               |                         32.73 | 17.9%                       |
|     11 | MUWAWF2  |              11786 |                      4783 | 160,824                               |                         13.65 | 34.7%                       |
|     12 | BLYTHB1  |               1652 |                       857 | 143,817                               |                         87.06 | 30.4%                       |
|     13 | GSWF1A   |               3917 |                      1755 | 129,148                               |                         32.97 | 55.3%                       |
|     14 | MOORAWF1 |               5097 |                      1968 | 128,324                               |                         25.18 | 49.6%                       |
|     15 | GSWF1B1  |               3917 |                      1755 | 124,110                               |                         31.68 | 48.6%                       |

`Positive tightening share` is the fraction of a unit's contraction-state equation rows in which its 30-minute movement mechanically tightened the active directional bound. A unit can rank highly through a smaller number of very large conditional impacts. For example, KIAMSF1 ranks first overall even though its pressure is positive in only 43.0% of its contraction-state rows. This does not mean every unit movement contracts VSA or that the movement independently caused the observed limit change.

The most frequently leading reconstructed constraints at contraction onsets were:

| Direction   | Leading constraint   |   Episodes |   Median drop MW | Maximum drop MW   |
|:------------|:---------------------|-----------:|-----------------:|:------------------|
| lower       | V^^V_NIL_KGTS        |       1647 |            301.9 | 1,107.1           |
| lower       | I_6F_SN_150          |        831 |            198.8 | 596.5             |
| lower       | V^^V_NIL_SWVIC       |        215 |            190.1 | 667.0             |
| lower       | V>>NIL_MLGT_MLGT     |        137 |            260.2 | 826.0             |
| lower       | V>>NIL_ELML_BAML2    |        117 |            281.6 | 910.8             |
| lower       | F_S++TBTU_R5         |        113 |            169   | 546.8             |
| upper       | I_6F_NS_150          |        627 |            212.2 | 609.1             |
| upper       | S>>NIL_BWMP_RBTU     |        387 |            366.1 | 1,037.4           |
| upper       | V::N_NIL_V2          |        360 |            222.1 | 673.2             |
| upper       | S>>NIL_RBTU_RBTU     |        288 |            260.7 | 800.7             |
| upper       | V::N_NIL_O2          |        280 |            247.9 | 798.0             |
| upper       | V::N_NIL_V1          |        219 |            212.9 | 600.7             |

The full event ledger, adaptive monthly thresholds, constraint episode summary and direction-specific generator rankings are available in [contraction events](data/vsa_2y_contraction_events.csv), [monthly thresholds](data/vsa_2y_contraction_thresholds_monthly.csv), [contraction constraints](data/vsa_2y_contraction_constraints.csv), and [generator contraction rankings](data/vsa_2y_generator_contraction_rankings.csv).

## Generator influence

`Abs impact MW-observations` sums `abs(-b/a × ΔMW)` while a unit appears in an applicable VSA equation. Tightening preserves the direction-specific sign; contraction rank uses positive tightening during sharp-contraction intervals, while reversal and forced ranks count event exposure. `Flow-move rho` is a weighted monthly Spearman association, not causation.

|   Rank | DUID     |   Active months |   Equation versions | Abs impact MW-observations   |   Mean abs impact MW | P95 abs impact MW   | Tightening MW-observations   |   Contraction rank |   Reversal rank |   Forced rank |   Flow-move rho |
|-------:|:---------|----------------:|--------------------:|:-----------------------------|---------------------:|:--------------------|:-----------------------------|-------------------:|----------------:|--------------:|----------------:|
|      1 | KIAMSF1  |              24 |                5251 | 2,715,546                    |               21.908 | 346.589             | 1,585,549                    |                  1 |               9 |             1 |          -0.003 |
|      2 | LIMOSF11 |              24 |                3446 | 2,627,481                    |               20.667 | 410.923             | 1,535,496                    |                  2 |              23 |            22 |           0.028 |
|      3 | WEMENSF1 |              24 |                5298 | 2,164,057                    |               18.713 | 317.604             | 1,217,383                    |                  5 |              12 |             7 |           0.004 |
|      4 | BANN1    |              24 |                5298 | 2,068,284                    |               17.782 | 290.669             | 1,163,194                    |                  6 |              12 |             7 |          -0.002 |
|      5 | KESSB1   |              20 |                4385 | 2,011,363                    |               25.216 | 655.556             | 1,094,167                    |                  8 |              29 |            27 |           0.011 |
|      6 | MUWAWF1  |              24 |                4877 | 1,982,768                    |               17.524 | 442.446             | 1,108,133                    |                  3 |              18 |             6 |           0.038 |
|      7 | SUNRSF1  |              24 |                3446 | 1,867,528                    |               14.827 | 231.652             | 1,118,867                    |                  4 |              23 |            22 |           0.016 |
|      8 | KARSF1   |              24 |                5362 | 1,590,421                    |               12.707 | 233.070             | 935,759                      |                  7 |              10 |             2 |           0.001 |
|      9 | MUWAWF2  |              24 |                4881 | 1,573,509                    |               13.313 | 230.021             | 817,576                      |                 11 |              17 |             5 |           0.022 |
|     10 | STWF1    |              24 |                3711 | 1,540,439                    |               12.398 | 171.394             | 678,659                      |                 18 |              21 |            20 |           0.022 |
|     11 | YATSF1   |              24 |                5362 | 1,497,849                    |               11.813 | 232.925             | 869,802                      |                  9 |              10 |             2 |           0.001 |
|     12 | ARWF1    |              24 |                4501 | 1,259,141                    |               25.773 | 647.647             | 649,096                      |                 16 |              31 |            31 |          -0.007 |
|     13 | MURRAY   |              24 |                4008 | 1,221,595                    |               24.419 | 457.952             | 751,790                      |                 10 |              65 |            62 |           0.008 |
|     14 | MACARTH1 |              24 |                4162 | 1,220,377                    |               22.478 | 242.771             | 632,907                      |                 17 |              38 |            55 |           0.044 |
|     15 | MOORAWF1 |              24 |                4034 | 1,012,253                    |               67.909 | 2,231.899           | 538,934                      |                 14 |             101 |            70 |           0.036 |
|     16 | RYANCWF1 |              24 |                4101 | 969,095                      |               17.865 | 181.801             | 511,111                      |                 25 |              61 |            56 |           0.028 |
|     17 | LKBONNY2 |              24 |                7343 | 930,742                      |                6.015 | 48.144              | 492,986                      |                 41 |               1 |            12 |           0.128 |
|     18 | MERCER01 |              24 |                4038 | 843,371                      |               57.191 | 1,289.647           | 392,128                      |                 22 |             100 |            69 |           0.015 |
|     19 | GSWF1A   |              24 |                1605 | 837,951                      |               37.161 | 535.589             | 487,140                      |                 13 |              45 |            32 |          -0.105 |
|     20 | GSWF1B1  |              24 |                1605 | 810,062                      |               34.071 | 714.476             | 474,219                      |                 15 |              45 |            32 |          -0.099 |

The complete ranking, factor extrema, equation-version coverage and event measures are in [vsa_2y_generator_rankings.csv](data/vsa_2y_generator_rankings.csv). The compressed [unit-by-equation factor file](data/vsa_2y_unit_equation_factors.csv.gz) preserves every distinct exact-version `b` coefficient, VSA `a` coefficient and derived `-b/a` sensitivity. Seasonal ranks should be used to decide which unit-specific pressure terms are stable enough to keep. Units that rank highly in only one season should be pooled into constraint-family or regional pressure features until an untouched period confirms persistence.

## Binding, near-binding, setter and leading equations

`Binding` means absolute published marginal value above numerical zero. `Near binding` means solved constraint slack divided by the absolute VSA coefficient is between 0 and 50 MW. `Near setting` means the equation’s implied bound is within 50 MW of the reconstructed directional envelope. `Leading` means it is the reconstructed tightest valid upper or lower equation. Reported setters come from `EXPORTGENCONID` and `IMPORTGENCONID`; reconstructed leaders are kept separately so disagreement remains visible.

The 40 most operationally relevant exact versions are shown below. The [complete equation file](data/vsa_2y_constraint_equations.csv) includes every researched exact version, VSA coefficient, description, constraint-set membership, overlapping invoked sets, applicable counts, binding/near-binding/near-setting counts, leading counts, marginal-value summary and VSA-normalised slack.

| Direction   | Constraint          |   Version |   VSA coefficient |   Binding |   Near binding |   Near setting |   Leading | Type                  | Constraint sets                                            |
|:------------|:--------------------|----------:|------------------:|----------:|---------------:|---------------:|----------:|:----------------------|:-----------------------------------------------------------|
| upper       | V_S_HEYWOOD_UFLS    |         1 |             1     |      5062 |           6902 |          33525 |     28235 | Other                 | S-NIL                                                      |
| upper       | V_S_NIL_ROCOF       |         1 |             1     |      2590 |           4926 |          37627 |     27046 | ROC Frequency         | S-NIL                                                      |
| lower       | I_6F_SN_150         |         1 |            -1     |      1541 |           2396 |          26830 |     25299 | Discretionary         | I-6F_SN_150, N-NIL                                         |
| lower       | I_6F_SN_150         |         1 |            -1     |      1238 |           1835 |          24983 |     22813 | Discretionary         | I-6F_SN_150, N-NIL                                         |
| lower       | I_6F_SN_150         |         1 |            -1     |       248 |            418 |          17312 |     16609 | Discretionary         | I-6F_SN_150, N-NIL                                         |
| upper       | I_6F_NS_150         |         2 |             0.979 |      1318 |           1816 |          16298 |     13525 | Other                 | I-6F_NS_150, N-NIL                                         |
| lower       | S_V_HEYWOOD_OFGS    |         1 |            -1     |       693 |           1157 |          15038 |     11231 | Other                 | S-NIL                                                      |
| lower       | SV_550_TEST         |         1 |            -1     |      1340 |           2736 |          12009 |      8323 | Other                 | S-NIL                                                      |
| upper       | I_6F_NS_150         |         1 |             1     |       440 |            703 |           8666 |      7092 | Discretionary         | I-6F_NS_150, N-NIL                                         |
| lower       | F_S++TBTU_R5        |         1 |            -1     |      3125 |           2704 |           8844 |      6898 | FCAS                  | S-TBTU, S-TBTU_BC-2CP, S-X_BDBU+TBTU_BC-2CP, S-X_TBTU+BDBU |
| upper       | F_S++TBTU_L5        |         1 |             1     |      1668 |           1611 |           8950 |      6609 | FCAS                  | S-TBTU, S-TBTU_BC-2CP, S-X_BDBU+TBTU_BC-2CP, S-X_TBTU+BDBU |
| lower       | S>>BDBU_TUTB_TUTB_1 |         3 |            -1     |       449 |            774 |           8622 |      6567 | Thermal               | I-BDBU_ONE                                                 |
| lower       | S_V_NIL_ROCOF       |         1 |            -1     |        83 |            275 |           8284 |      6536 | ROC Frequency         | S-NIL                                                      |
| lower       | V^^V_NIL_SWVIC      |         1 |            -0.765 |      3304 |           3615 |           7494 |      6452 | Voltage Stability     | V-NIL                                                      |
| lower       | F_S++SETB_R5        |         1 |            -1     |       634 |            571 |           7611 |      6286 | FCAS                  | S-SETB_N-2, S-TBSE, S-TBSE_BC-2CP, S-X_TBSE+BDBU           |
| lower       | S>>BDBU_TUTB_TUTB_1 |         1 |            -1     |       130 |            306 |           7675 |      6081 | Thermal               | I-BDBU_ONE                                                 |
| lower       | S:V_BDBU_650        |         1 |            -1     |         0 |              0 |          12388 |      5997 | Oscillatory Stability | I-BDBU_ONE                                                 |
| upper       | VS_600_TEST         |         1 |             1     |      2874 |           3391 |           7196 |      5866 | Other                 | S-NIL                                                      |
| upper       | F_S++SETB_L5        |         1 |             1     |       971 |            921 |           7317 |      5562 | FCAS                  | S-SETB_N-2, S-TBSE, S-TBSE_BC-2CP, S-X_TBSE+BDBU           |
| upper       | VS_600_TEST         |         2 |             1     |      1671 |           2060 |           7122 |      5058 | Other                 | S-NIL                                                      |
| lower       | V^^V_NIL_KGTS       |         1 |            -0.27  |      2763 |           2494 |           5346 |      5039 | Voltage Stability     | V-NIL                                                      |
| upper       | S>>NIL_BWMP_RBTU    |         1 |             0.264 |       428 |            595 |           5118 |      4621 | Thermal               | S-NIL                                                      |
| lower       | V^^V_NIL_KGTS       |         1 |            -0.27  |      3291 |           2942 |           4928 |      4592 | Voltage Stability     | V-NIL                                                      |
| upper       | I_6F_NS_150         |         1 |             0.999 |       776 |           1071 |           5471 |      4437 | Discretionary         | I-6F_NS_150, N-NIL                                         |
| upper       | VS_HEY_600_TEST     |         1 |             1     |      2107 |           2416 |           5510 |      4111 | Other                 | I-VS_HEY_600_TEST                                          |
| upper       | V:S_BDBU_700        |         1 |             1     |         0 |              0 |           9106 |      4071 | Oscillatory Stability | I-BDBU_ONE                                                 |
| upper       | VS_600_TEST         |         1 |             1     |      2192 |           2562 |           4987 |      4010 | Other                 | S-NIL                                                      |
| lower       | I_6F_SN_150         |         1 |            -1     |       228 |            410 |           4146 |      3920 | Discretionary         | I-6F_SN_150, N-NIL                                         |
| lower       | V^^V_BDBU_SWVIC     |         1 |            -1     |       867 |           1586 |           4810 |      3337 | Voltage Stability     | I-BDBU_ONE                                                 |
| lower       | V^^V_NIL_KGTS       |         1 |            -0.215 |       159 |            333 |           3589 |      3166 | Voltage Stability     | V-NIL                                                      |
| lower       | V^^V_NIL_KGTS       |         1 |            -0.237 |      1189 |           1192 |           3492 |      3124 | Voltage Stability     | V-NIL                                                      |
| upper       | VS_HEY_600_TEST     |         1 |             1     |      1036 |           1304 |           3822 |      3013 | Other                 | I-VS_HEY_600_TEST                                          |
| upper       | V:S_700             |         1 |             1     |        59 |            246 |           6273 |      2835 | Oscillatory Stability | S-NIL                                                      |
| upper       | V::S_BDBU_MAXG_1    |         1 |             1     |       365 |            508 |           3791 |      2824 | Transient Stability   | I-BDBU_ONE                                                 |
| upper       | I_6F_NS_150         |         1 |             0.999 |       452 |            640 |           3206 |      2727 | Discretionary         | I-6F_NS_150, N-NIL                                         |
| upper       | VS_600_TEST         |         2 |             1     |      1089 |           1259 |           2988 |      2714 | Other                 | S-NIL                                                      |
| upper       | V::N_NIL_O2         |         1 |             0.354 |       711 |           1096 |           3610 |      2682 | Transient Stability   | V-NIL                                                      |
| upper       | V::N_NIL_V2         |         1 |             0.478 |      1426 |           1734 |           3632 |      2626 | Transient Stability   | V-NIL                                                      |
| lower       | I_6F_SN_150         |         1 |            -1     |        99 |            171 |           2666 |      2527 | Discretionary         | I-6F_SN_150, N-NIL                                         |
| lower       | V^^V_NIL_KGTS       |         1 |            -0.27  |      1342 |           1322 |           2688 |      2405 | Voltage Stability     | V-NIL                                                      |

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

The reusable [feature dictionary](data/vsa_2y_feature_dictionary.csv) records each feature group, unit, definition and recommended variable count. The configuration and orchestrator accept the interconnector ID, dates, thresholds and storage limits as parameters, so the same method can be applied to another interconnector after its study config is reviewed.

## Calculation method

For each exact effective generic-constraint version:

```text
a * VSA + sum(b_i * P_i) + other solved terms <= RHS
conditional VSA bound = observed VSA flow + (RHS - solved LHS) / a
unit sensitivity = -b_i / a
30-minute unit pressure = sensitivity * (P_i[t] - P_i[t-30m])
```

Positive `a` yields an upper signed-flow bound; negative `a` yields a lower bound. The minimum upper and maximum lower valid candidates form the reconstructed envelope. Constraint versions are matched using dispatch-supplied effective date/version where available, with time-effective fallback recorded by the feature audit. The first 30 minutes of each independently processed month lack a within-file 30-minute unit change and are excluded from movement attribution; this affects 12 hours across two years, about 0.07% of the study timeline, while equation, binding, limit, flow, seasonal and diurnal coverage remain intact.

## Interpretation limits and testing use

- Generator rankings describe mechanical exposure under observed dispatch and constraint regimes. Simultaneous system responses prevent a causal claim.
- Reported directional limits depend on solved dispatch and should not be interpreted as independent transmission ratings or jointly feasible counterfactual capacities.
- Near-binding and near-setting thresholds are both 50 MW in VSA-normalised space and should be sensitivity-tested at 25 and 100 MW before feature selection is frozen.
- Feature selection must use training seasons only. Evaluate the frozen compact block on a later untouched chronological period against persistence, reported-setter history and a non-topological fundamentals baseline.
- Forecast-horizon pressure requires lagged dispatch plus generator scenarios or unit forecasts. Realised future dispatch must never enter an operational backtest.

## Rebuild

```powershell
python -m nemic.constraint_longitudinal run --config configs/constraint_vsa_2y.json
python scripts/build_vsa_two_year_report.py --config configs/constraint_vsa_2y.json
python scripts/build_docs_html.py
python -m unittest discover -s tests -v
```
