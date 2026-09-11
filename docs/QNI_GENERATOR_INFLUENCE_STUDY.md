# QNI generator influence and constraint-feature study

## Research question and result

This rerun asks which generators most strongly and persistently moved the constraint-derived `NSW1-QLD1` (QNI) directional bounds during February 2026, including sharp limit contractions, flow reversals and forced-direction limits. It also tests whether 14 compact network-state features improve a one-step persistence benchmark.

The strongest broad-coverage candidates are **NEWENSF2, NEWENSF1, METZSF1, SAPHWF1, WRWF1, ERB01, GNNDHSF1, BW02, KPP_1, BW04**. The highest exposure ranks also contain episodic units—**TUMUT3, UPPTUMUT, CUSF1, DARLSF1, RYEPARK1, AVLSF1, LIMOSF11, WLWLSF2**—whose large impacts occur across fewer than 1,000 active rows. These should enter a forecast as regime-conditioned signed pressures, not as unconditional raw-generation features.

The one-month model result is mixed. Import-limit MAE improved by 0.09 MW (0.22%), while export-limit MAE worsened by 2.07 MW (4.98%). QNI’s reconstructed limit MAE is 40.29 MW export and 77.58 MW import. This is adequate for feature exploration but requires equation-eligibility and setter-attribution work before an operational claim.

## Scope and headline evidence

| Item | Result |
|---|---:|
| Study period | 1–28 February 2026 |
| Native resolution | 5 minutes |
| Intervals | 8,064 |
| Generators with valid sensitivities | 211 |
| Constraints leading an envelope | 30 |
| Flow reversal events | 526 |
| Upper contractions: intervals / episodes | 386 / 122 |
| Lower contractions: intervals / episodes | 407 / 169 |
| Forced upper / lower intervals | 243 / 20 |
| Envelope coverage, upper / lower | 99.99% / 99.99% |
| Exact-version equation coverage | 74.79% |

This is a descriptive mechanical-attribution study. Dispatch changes, constraint coefficients and the active envelope are observed together. The rankings do not identify independent causal effects because dispatch responds to prices, regional balance and the same constraints being studied.

## Method

For each solved generic constraint and exact effective version, the study isolates QNI from AEMO’s published solved left-hand side:

```text
a * QNI + sum(b_i * P_i) + other terms <= RHS
conditional QNI bound = observed QNI + (RHS - solved LHS) / a
unit sensitivity s_i = -b_i / a
30-minute unit bound impact = s_i * delta P_i
```

Positive `a` is treated as an upper QNI bound and negative `a` as a lower signed-flow bound. At each interval, the minimum valid upper bound and maximum valid lower bound form the directional envelope. The pipeline also retains the runner-up gap, coefficient-weighted tightening and relief, available ramp-limited relief, completeness flags, and the exact leading equation/version.

A contraction is a 30-minute directional-limit fall in the worst 10% of positive drops: at least 150.21 MW for the upper direction or 136.37 MW for the lower direction. Consecutive contraction intervals are grouped into episodes. A reversal is one crossing of the last non-zero observed flow sign. A forced state occurs when a directional capacity is negative.

## Generator influence ranking

`Exposure MW-observations` is the sum of absolute coefficient-weighted 30-minute impacts while the unit appears in the leading equation. It rewards persistence and magnitude. Mean and P95 impact separate intensity from persistence. Event ranks require at least 20 contribution rows.

|   Rank | DUID     |   Active rows |   Leading versions |   b min |   b mean |   b max |   Mean s |   Max abs s | Exposure MW-observations   |   Mean abs impact MW | P95 abs impact MW   |   Contraction rank | Reversal rank   | Forced rank   |
|-------:|:---------|--------------:|-------------------:|--------:|---------:|--------:|---------:|------------:|:---------------------------|---------------------:|:--------------------|-------------------:|:----------------|:--------------|
|      1 | TUMUT3   |           238 |                  4 |   0.67  |    0.808 |   0.95  |    3.069 |       3.994 | 183,648                    |              771.629 | 6,191.143           |                  1 | —               | 2             |
|      2 | NEWENSF2 |          6279 |                  8 |  -0.961 |    0.25  |   0.722 |    0.987 |       1.003 | 139,527                    |               22.221 | 86.264              |                  9 | 1               | 35            |
|      3 | NEWENSF1 |          6279 |                  8 |  -0.961 |    0.25  |   0.722 |    0.987 |       1.003 | 129,682                    |               20.653 | 79.569              |                 10 | 3               | 33            |
|      4 | METZSF1  |         12345 |                 14 |  -0.946 |    0.082 |   0.96  |    0.801 |       1.168 | 112,763                    |                9.134 | 44.682              |                 19 | 15              | 43            |
|      5 | SAPHWF1  |         12374 |                 18 |  -0.958 |    0.251 |   1.04  |    0.766 |       1.04  | 108,699                    |                8.785 | 38.692              |                 61 | 16              | 38            |
|      6 | WRWF1    |         12345 |                 14 |  -0.948 |    0.112 |   0.853 |    0.766 |       1.147 | 81,553                     |                6.606 | 26.198              |                 37 | 19              | 49            |
|      7 | UPPTUMUT |           238 |                  4 |   0.67  |    0.807 |   0.95  |    3.067 |       3.989 | 80,574                     |              338.546 | 1,333.180           |                  2 | —               | 3             |
|      8 | ERB01    |          3241 |                  3 |  -0.309 |    0.045 |   0.258 |    0.554 |       0.721 | 79,492                     |               24.527 | 99.983              |                 36 | 2               | 31            |
|      9 | GNNDHSF1 |         11089 |                 13 |  -0.973 |    0.002 |   0.6   |    0.687 |       1.017 | 67,480                     |                6.085 | 32.716              |                 26 | 20              | 40            |
|     10 | BW02     |          3456 |                  5 |   0.192 |    0.336 |   0.525 |    0.74  |       1.097 | 56,655                     |               16.393 | 52.893              |                 13 | 8               | 41            |
|     11 | KPP_1    |          4837 |                 10 |   0.234 |    0.685 |   1.37  |   -0.968 |       1.37  | 54,850                     |               11.34  | 84.364              |                  6 | 17              | —             |
|     12 | CUSF1    |           238 |                  4 |   0.669 |    0.808 |   0.949 |    3.072 |       4.017 | 54,377                     |              228.474 | 745.742             |                 78 | —               | 1             |
|     13 | DARLSF1  |           238 |                  4 |   0.669 |    0.808 |   0.949 |    3.073 |       4.023 | 51,822                     |              217.739 | 864.623             |                 21 | —               | 4             |
|     14 | BW04     |          3456 |                  5 |   0.282 |    0.4   |   0.488 |    1.083 |       1.611 | 51,091                     |               14.783 | 48.736              |                 12 | 7               | 58            |
|     15 | BW03     |          3456 |                  5 |   0.282 |    0.4   |   0.488 |    1.083 |       1.611 | 50,861                     |               14.717 | 46.086              |                 14 | 6               | 47            |
|     16 | BW01     |          3456 |                  5 |   0.192 |    0.336 |   0.525 |    0.74  |       1.097 | 50,253                     |               14.541 | 49.928              |                 15 | 9               | 45            |
|     17 | WELNSF1  |          3456 |                  5 |   0.242 |    0.487 |   0.662 |    1.582 |       2.339 | 48,902                     |               14.15  | 48.944              |                 65 | 4               | 39            |
|     18 | WOLARSF1 |          3456 |                  5 |   0.298 |    0.472 |   0.624 |    1.479 |       2.137 | 44,163                     |               12.779 | 50.181              |                 88 | 5               | 51            |
|     19 | RYEPARK1 |           238 |                  4 |   0.651 |    0.843 |   0.971 |    3.238 |       4.566 | 40,095                     |              168.468 | 664.268             |                104 | —               | 18            |
|     20 | MOREESF1 |          7535 |                  9 |  -0.96  |    0.268 |   0.725 |    0.915 |       1.003 | 37,494                     |                4.976 | 22.087              |                 25 | 22              | 64            |
|     21 | MP1      |          3456 |                  5 |   0.187 |    0.496 |   0.694 |    1.658 |       2.658 | 35,364                     |               10.233 | 27.126              |                 16 | 18              | 57            |
|     22 | STUBSF2  |          3456 |                  5 |   0.275 |    0.478 |   0.64  |    1.522 |       2.163 | 34,916                     |               10.103 | 34.361              |                 74 | 13              | 48            |
|     23 | MP2      |          3456 |                  5 |   0.187 |    0.496 |   0.694 |    1.658 |       2.658 | 34,854                     |               10.085 | 28.396              |                 17 | 11              | 54            |
|     24 | STUBSF1  |          3456 |                  5 |   0.275 |    0.478 |   0.64  |    1.522 |       2.163 | 31,787                     |                9.198 | 30.646              |                 75 | 10              | 50            |
|     25 | AVLSF1   |           238 |                  4 |   0.668 |    0.808 |   0.948 |    3.075 |       4.034 | 31,268                     |              131.38  | 519.608             |                 69 | —               | 7             |

The leading raw rank is not automatically the best compact feature. Tumut 3, for example, ranks first but appears in only 238 active rows and four leading versions; its mean impact is amplified by QNI coefficients between roughly 0.17 and 0.36 in those equations. That makes it a useful outage/regime indicator and tail-pressure feature, but weak evidence for a stable unconditional QNI driver. The broad-coverage group should anchor the first compact panel, while episodic hydro/solar units can be pooled into a tail-pressure feature or activated by constraint family.

### Sharp limit contractions

|   Rank | DUID     |   Rows |   Mean tightening MW | Tightening share   |
|-------:|:---------|-------:|---------------------:|:-------------------|
|      1 | TUMUT3   |     86 |               785.27 | 37.2%              |
|      2 | UPPTUMUT |     86 |               314.57 | 46.5%              |
|      3 | URANQ12  |     86 |               102    | 39.5%              |
|      4 | URANQ13  |     86 |                92.36 | 38.4%              |
|      5 | URANQ14  |     86 |                85.53 | 33.7%              |
|      6 | KPP_1    |     79 |                83.77 | 63.3%              |
|      7 | URANQ11  |     86 |                83.14 | 30.2%              |
|      8 | SNOWYP   |     86 |                70.6  | 9.3%               |
|      9 | NEWENSF2 |    657 |                38.56 | 80.2%              |
|     10 | NEWENSF1 |    657 |                36.81 | 81.3%              |

Mean tightening preserves sign: a positive value means the unit movement mechanically reduced capacity in the relevant direction. The tightening share shows how often the contribution had that sign; large means with modest shares indicate asymmetric tails rather than a universal directional rule.

### Flow reversals

|   Rank | DUID     |   Rows |   Mean abs impact MW | Flow alignment   |
|-------:|:---------|-------:|---------------------:|:-----------------|
|      1 | NEWENSF2 |    372 |                28.25 | 40.1%            |
|      2 | ERB01    |    182 |                27.44 | 35.7%            |
|      3 | NEWENSF1 |    372 |                26.15 | 38.4%            |
|      4 | WELNSF1  |    194 |                23.3  | 33.5%            |
|      5 | WOLARSF1 |    194 |                18.7  | 35.1%            |
|      6 | BW03     |    194 |                15.19 | 34.5%            |
|      7 | BW04     |    194 |                14.65 | 28.9%            |
|      8 | BW02     |    194 |                13.98 | 29.4%            |
|      9 | BW01     |    194 |                13.94 | 29.9%            |
|     10 | STUBSF1  |    194 |                12.6  | 41.2%            |

Flow alignment compares the sign of the coefficient-weighted bound impact with the observed 30-minute flow move. Values around 50% reinforce that regional balance, losses, other constraints and simultaneous unit movements still determine actual QNI direction.

### Forced-direction limits

|   Rank | DUID     |   Rows |   Mean abs impact MW |
|-------:|:---------|-------:|---------------------:|
|      1 | CUSF1    |     20 |               260.23 |
|      2 | TUMUT3   |     20 |               259.26 |
|      3 | UPPTUMUT |     20 |               219.64 |
|      4 | DARLSF1  |     20 |               217.48 |
|      5 | WLWLSF2  |     20 |               192.38 |
|      6 | WLWLSF1  |     20 |               179.73 |
|      7 | AVLSF1   |     20 |               131.2  |
|      8 | HILLSTN1 |     20 |               129.62 |
|      9 | URANQ11  |     20 |               128.92 |
|     10 | URANQ14  |     20 |               113.12 |

These ranks describe intervals where an export or import directional capacity was negative. They identify units exposed to the equations forcing QNI into one direction; they do not prove the unit independently caused the forced-flow state.

## Leading constraint equations and invoked sets

The table includes all equations that led either directional envelope. `a` is the exact QNI coefficient range across leading versions. Set labels marked `(invoked)` had an invocation overlapping the study month; a blank set field means no matching set membership was found in the downloaded standing-data vintages.

| Direction   | Constraint          |   Leading intervals |   Versions |   a min |   a max | Type                  |   Contraction episodes |   Reversals |   Forced intervals | Sets                       |
|:------------|:--------------------|--------------------:|-----------:|--------:|--------:|:----------------------|-----------------------:|------------:|-------------------:|:---------------------------|
| upper       | N^^Q_NIL_KPP_1      |                4571 |          1 |  1      |  1      | Voltage Stability     |                     22 |         310 |                  0 |                            |
| upper       | N>>NIL_33_34        |                3224 |          1 |  0.958  |  0.958  | Thermal               |                     96 |         180 |                243 |                            |
| lower       | N>>NIL_964_84_S     |                2322 |          1 | -0.746  | -0.746  | Thermal               |                     96 |         159 |                  0 |                            |
| lower       | F_Q++NIL_R5         |                1958 |          1 | -1      | -1      | FCAS                  |                     26 |         171 |                  0 |                            |
| lower       | F_Q++NIL_R6         |                1423 |          1 | -1      | -1      | FCAS                  |                      4 |          95 |                  0 |                            |
| lower       | N>>NIL_8U_86_S      |                1256 |          1 | -1      | -1      | Thermal               |                      0 |          57 |                  0 |                            |
| lower       | N>>NIL_964_88_S     |                 479 |          1 | -0.742  | -0.742  | Thermal               |                      8 |          15 |                  0 |                            |
| lower       | F_Q++NIL_R60        |                 322 |          1 | -1      | -1      | FCAS                  |                      1 |          10 |                  0 |                            |
| lower       | N>>16_8_39          |                 213 |          1 | -0.175  | -0.175  | Thermal               |                     29 |          12 |                 18 |                            |
| upper       | N^^Q_AR_VC_KPP_1    |                 151 |          1 |  1      |  1      | Voltage Stability     |                      1 |          27 |                  0 |                            |
| upper       | N^^Q_LS_SVC_KPP_1   |                  73 |          1 |  1      |  1      | Voltage Stability     |                      0 |           6 |                  0 |                            |
| lower       | N>>NIL_9W2_9W8      |                  22 |          1 | -0.449  | -0.449  | Thermal               |                      0 |           4 |                  0 |                            |
| lower       | N>>NIL_39           |                  22 |          1 | -0.302  | -0.302  | Thermal               |                      3 |           2 |                  2 |                            |
| upper       | #R034999_004_RAMP_V |                  13 |          1 |  1      |  1      | Voltage Stability     |                      0 |           0 |                  0 | #R034999_RAMP (invoked)    |
| upper       | #R035031_001_RAMP_F |                  13 |          1 |  1      |  1      | Transient Stability   |                      1 |           3 |                  0 | #R035031_RAMP (invoked)    |
| lower       | #R034885_002_RAMP_F |                  13 |          1 | -1      | -1      | Oscillatory Stability |                      2 |           0 |                  0 | #R034885_RAMP (invoked)    |
| lower       | #R035031_012_RAMP_F |                   9 |          1 | -1      | -1      | Voltage Stability     |                      0 |           1 |                  0 | #R035031_RAMP (invoked)    |
| lower       | #R034904_001_RAMP_F |                   7 |          1 | -1      | -1      | Oscillatory Stability |                      0 |           0 |                  0 | #R034904_RAMP (invoked)    |
| upper       | #R034870_003_RAMP_V |                   6 |          1 |  0.255  |  0.255  | Voltage Stability     |                      0 |           0 |                  0 | #R034870_RAMP (invoked)    |
| upper       | Q^^TR_TRBK_-750     |                   4 |          1 |  0.255  |  0.255  | Voltage Stability     |                      0 |           0 |                  0 | Q-X_MRGB_MRGB (invoked)    |
| lower       | #R034999_009_RAMP_V |                   4 |          1 | -1      | -1      | Voltage Stability     |                      0 |           0 |                  0 | #R034999_RAMP (invoked)    |
| lower       | #R034933_002_RAMP_F |                   4 |          1 | -1      | -1      | Oscillatory Stability |                      0 |           0 |                  0 | #R034933_RAMP (invoked)    |
| lower       | #R034999_009_RAMP_F |                   3 |          1 | -1      | -1      | Voltage Stability     |                      0 |           0 |                  0 | #R034999_RAMP (invoked)    |
| lower       | F_Q++NIL_R1         |                   3 |          1 | -1      | -1      | FCAS                  |                      0 |           0 |                  0 |                            |
| upper       | CA_BRIS_5892A65A_1  |                   3 |          1 |  0.7534 |  0.7534 | Thermal               |                      0 |           0 |                  0 | CA_BRIS_5892A65A (invoked) |
| lower       | N>>ERTX_12_14       |                   2 |          1 | -0.257  | -0.257  | Thermal               |                      0 |           0 |                  0 | N-ER_TX (invoked)          |
| upper       | N^^Q_NIL_CPP_4      |                   2 |          1 |  1      |  1      | Voltage Stability     |                      0 |           0 |                  0 |                            |
| upper       | #R034868_002_RAMP_V |                   2 |          1 |  0.255  |  0.255  | Voltage Stability     |                      1 |           0 |                  0 | #R034868_RAMP (invoked)    |
| lower       | N>>12_39_14         |                   1 |          1 | -0.358  | -0.358  | Thermal               |                      0 |           0 |                  0 |                            |
| upper       | #R034867_002_RAMP_V |                   1 |          1 |  0.255  |  0.255  | Voltage Stability     |                      1 |           0 |                  0 | #R034867_RAMP (invoked)    |

## Dominant unit terms in the main equations

For the ten most frequent leading equations, the following are the five unit terms with the largest absolute sensitivity weighted by that equation’s leading-interval count.

| Direction   | Constraint       | DUID     |   Leading intervals |   a IC |   b unit |   s = -b/a |
|:------------|:-----------------|:---------|--------------------:|-------:|---------:|-----------:|
| upper       | N^^Q_NIL_KPP_1   | KPP_1    |                4571 |  1     |   1.0653 |    -1.0653 |
| upper       | N^^Q_NIL_KPP_1   | METZSF1  |                4571 |  1     |  -0.4167 |     0.4167 |
| upper       | N^^Q_NIL_KPP_1   | GNNDHSF1 |                4571 |  1     |  -0.3186 |     0.3186 |
| upper       | N^^Q_NIL_KPP_1   | WRSF1    |                4571 |  1     |  -0.3178 |     0.3178 |
| upper       | N^^Q_NIL_KPP_1   | WRWF1    |                4571 |  1     |  -0.3178 |     0.3178 |
| upper       | N>>NIL_33_34     | LDBESS1  |                3224 |  0.958 |  -1      |     1.0438 |
| upper       | N>>NIL_33_34     | GNNDHSF1 |                3224 |  0.958 |  -0.973  |     1.0157 |
| upper       | N>>NIL_33_34     | NESBESS1 |                3224 |  0.958 |  -0.961  |     1.0031 |
| upper       | N>>NIL_33_34     | NESBESS2 |                3224 |  0.958 |  -0.961  |     1.0031 |
| upper       | N>>NIL_33_34     | NEWENSF2 |                3224 |  0.958 |  -0.961  |     1.0031 |
| lower       | N>>NIL_964_84_S  | METZSF1  |                2322 | -0.746 |   0.869  |     1.1649 |
| lower       | N>>NIL_964_84_S  | WRWF1    |                2322 | -0.746 |   0.853  |     1.1434 |
| lower       | N>>NIL_964_84_S  | WRSF1    |                2322 | -0.746 |   0.853  |     1.1434 |
| lower       | N>>NIL_964_84_S  | SAPHWF1  |                2322 | -0.746 |   0.747  |     1.0013 |
| lower       | N>>NIL_964_84_S  | MOREESF1 |                2322 | -0.746 |   0.725  |     0.9718 |
| lower       | N>>NIL_8U_86_S   | SAPHWF1  |                1256 | -1     |   1      |     1      |
| lower       | N>>NIL_8U_86_S   | METZSF1  |                1256 | -1     |   0.96   |     0.96   |
| lower       | N>>NIL_8U_86_S   | WRWF1    |                1256 | -1     |   0.85   |     0.85   |
| lower       | N>>NIL_8U_86_S   | WRSF1    |                1256 | -1     |   0.85   |     0.85   |
| lower       | N>>NIL_8U_86_S   | MOREESF1 |                1256 | -1     |   0.461  |     0.461  |
| lower       | N>>NIL_964_88_S  | METZSF1  |                 479 | -0.742 |   0.867  |     1.1685 |
| lower       | N>>NIL_964_88_S  | WRSF1    |                 479 | -0.742 |   0.851  |     1.1469 |
| lower       | N>>NIL_964_88_S  | WRWF1    |                 479 | -0.742 |   0.851  |     1.1469 |
| lower       | N>>NIL_964_88_S  | SAPHWF1  |                 479 | -0.742 |   0.742  |     1      |
| lower       | N>>NIL_964_88_S  | MOREESF1 |                 479 | -0.742 |   0.72   |     0.9704 |
| lower       | N>>16_8_39       | TARALGA1 |                 213 | -0.175 |   1      |     5.7143 |
| lower       | N>>16_8_39       | COLWF01  |                 213 | -0.175 |   0.865  |     4.9429 |
| lower       | N>>16_8_39       | CROOKWF2 |                 213 | -0.175 |   0.864  |     4.9371 |
| lower       | N>>16_8_39       | CROOKWF3 |                 213 | -0.175 |   0.864  |     4.9371 |
| lower       | N>>16_8_39       | GULLRWF1 |                 213 | -0.175 |   0.847  |     4.84   |
| upper       | N^^Q_AR_VC_KPP_1 | KPP_1    |                 151 |  1     |   1.0653 |    -1.0653 |
| upper       | N^^Q_AR_VC_KPP_1 | METZSF1  |                 151 |  1     |  -0.4167 |     0.4167 |
| upper       | N^^Q_AR_VC_KPP_1 | GNNDHSF1 |                 151 |  1     |  -0.3186 |     0.3186 |
| upper       | N^^Q_AR_VC_KPP_1 | WRSF1    |                 151 |  1     |  -0.3178 |     0.3178 |
| upper       | N^^Q_AR_VC_KPP_1 | WRWF1    |                 151 |  1     |  -0.3178 |     0.3178 |

## Compact feature recommendation

Keep the production candidate near 20–25 numeric variables:

1. Upper/lower conditional bound, flow room and runner-up switch gap.
2. Upper/lower aggregate generator tightening, relief and 30-minute pressure change.
3. Upper/lower ramp-and-availability-limited relief.
4. Candidate count, pressure completeness, crossed-envelope flag and a compact constraint-family encoding.
5. Four to eight frozen signed unit-pressure features chosen across training months. Start the broad panel with NEWENSF2, NEWENSF1, METZSF1, SAPHWF1, WRWF1, ERB01, GNNDHSF1, BW02. Pool episodic units such as TUMUT3, UPPTUMUT, CUSF1, DARLSF1, RYEPARK1 by regime until repeated months establish persistence.

For a forecast horizon, replace realised `delta P` with lagged dispatch plus generator scenarios or dispatch forecasts. Carry base/up/down pressure paths through the current candidate envelope so a different constraint can take over. Raw generator output without `s_i`, direction and constraint regime loses the topology-dependent sign.

## Model comparison

| Target | Rows | Persistence MAE | Compact-feature MAE | Improvement | Relative |
|---|---:|---:|---:|---:|---:|
| Export tight limit | 447 | 41.60 MW | 43.67 MW | -2.07 MW | -4.98% |
| Import tight limit | 447 | 42.84 MW | 42.75 MW | 0.09 MW | 0.22% |

This split is a retrospective feasibility comparison: 895 earlier half-hours train the model and 447 later half-hours test it. It is neither an untouched multi-month holdout nor an issue-time backtest. The export result says the current compact block should not be adopted wholesale without ablation and regime refinement.

## Data guard and reproducibility

The run requested only the 25 explicit table archives inherited by `configs/constraint_qni_pilot.json`: eight February standing/metadata tables, two February interval tables, and small historical standing-data supplements needed for exact equation versions. It did not download a full MMSDB snapshot or enumerate an archive directory. The audited compressed total was 261.8 MiB against a 2 GiB cap; all 25 files were reused from the integrity-checked cache. Extraction retained 3,582 QNI-linked/setter constraint IDs and 225 mapped DUIDs. Raw and derived data stay under ignored `data/` paths and are not committed.

Rebuild commands:

```powershell
python run_constraint_pilot.py --config configs/constraint_qni_pilot.json
python scripts/build_constraint_study_report.py --config configs/constraint_qni_pilot.json
python scripts/build_docs_html.py
python -m unittest discover -s tests -v
```

## Limitations and next tests

- Exact QNI-factor coverage is 74.79%; 14 observed setter IDs were absent from the base February factor archive, and older version supplements do not resolve every dispatch row.
- Setter agreement is 46.7% upper and 32.5% lower. Numeric reconstruction, eligibility rules, ties and omitted non-energy terms need investigation before using the reconstructed leader as definitive attribution.
- Ten connection points were unmapped to active DUID records in the extracted standing data. Their influence remains outside unit rankings.
- The rankings share common dispatch and equation regimes and should not be read as independent causal effects.
- Repeat non-contiguous seasonal and outage months, freeze generator selection on training months, run feature-block ablations, then evaluate a final untouched chronological holdout with issue-time-valid inputs.
