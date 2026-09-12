# QNI two-year constraint, topology and generator-influence study

## Result and scope

This study reconstructs the constraint-derived `NSW1-QLD1` (QNI) directional envelope at five-minute resolution from **1 September 2024 through 31 August 2026**. It evaluates every directly linked or observed setter equation available inside that same 24-month acquisition window, then separates four operational populations: AEMO binding equations, equations within 50 MW of binding, reported directional setters, and reconstructed envelope leaders.

The broadest generator-pressure candidates by persistence-weighted absolute impact are **NEWENSF2, NEWENSF1, SAPHWF1, WRWF1, METZSF1, TUMUT3, BW01, GNNDHSF1**. Their signs and magnitudes vary by equation version and direction, so the forecast representation should use signed `-b/a × ΔMW` pressure under the active constraint regime rather than raw unit generation alone. These are mechanical attributions from solved equations and simultaneous dispatch; they are not independent causal estimates.

## Coverage and integrity

| Item | Result |
|---|---:|
| Analysis window | 1 Sep 2024–31 Aug 2026 |
| Calendar months / seasons | 24 / two complete cycles of each season |
| Five-minute QNI observations | 210,240 |
| Generator DUIDs with valid sensitivities | 238 |
| Exact equation versions researched | 15,010 |
| Distinct constraint IDs researched | 13,699 |
| Reconstructed upper/lower coverage | 99.75% / 99.75% |
| Mean upper/lower reconstruction MAE | 410.58 / 248.90 MW |
| Exact dispatch-to-equation version match | 65.32% |
| Available standing archives | 144 |
| Peak-controlled study footprint at report build | 0.21 GB of 10.00 GB |

Both standing and interval acquisition are hard-bounded to the same two years. The run downloads only six small monthly standing tables and two monthly interval tables. Each interval month is dependency-filtered, reduced to compact Parquet outputs, checked, and its large archives are removed before the following month. The [source manifest](data/qni_2y_source_manifest.json) records every available standing archive, byte size and SHA-256 digest; unavailable monthly table archives are listed explicitly.

The dispatch-supplied exact equation version matched 65.32% of reconstructed rows; remaining rows use the documented time-effective fallback. The upper/lower reconstruction MAE of 410.58/248.90 MW is therefore a material quality diagnostic, and forecast testing should retain the match/fallback flag rather than treating every reconstructed bound as equally certain.

## Seasonal network state

| Season   |   Intervals |   Median flow MW | Flow P05   |   Flow P95 |   Median export limit | Median import limit   | Northward share   | Southward share   |   Reversals |   Forced export |   Forced import | Upper setter match   | Lower setter match   |
|:---------|------------:|-----------------:|:-----------|-----------:|----------------------:|:----------------------|:------------------|:------------------|------------:|----------------:|----------------:|:---------------------|:---------------------|
| Autumn   |       52992 |           -315   | -874.5     |      390.2 |                 566.6 | 938.3                 | 21.4%             | 78.6%             |        1975 |            4637 |             169 | 14.4%                | 26.0%                |
| Spring   |       52416 |           -189.8 | -833.0     |      412.5 |                 292.7 | 697.8                 | 27.5%             | 72.5%             |        2480 |            7062 |            1524 | 12.1%                | 20.6%                |
| Summer   |       51840 |            -45.9 | -848.6     |      662.1 |                 626   | 946.6                 | 46.7%             | 53.3%             |        2562 |            1115 |             345 | 27.7%                | 44.8%                |
| Winter   |       52992 |           -600   | -1,132.1   |      169.4 |                 554.9 | 1,078.0               | 9.9%              | 90.1%             |        1075 |            3899 |              32 | 32.5%                | 41.3%                |

Spring’s median flow was -189.8 MW, with a 72.5% share of southward intervals. Seasonal medians describe the realised mix of demand, renewable output, outages, dispatch and constraint regimes. They do not isolate a single physical driver.

The full machine-readable seasonal summaries are [network state](data/qni_2y_seasonal_summary.csv), [constraint populations](data/qni_2y_constraint_population_by_season.csv), and [generator influence by season and direction](data/qni_2y_generator_seasonal_rankings.csv).

The HTML report adds a seasonal generator-pressure heatmap for the twelve highest two-year contributors. It makes it easy to distinguish persistent units such as NEWENSF2 from units whose exposure is concentrated in one season.

## Diurnal behaviour

The [48-bin diurnal table](data/qni_2y_diurnal_summary.csv) contains mean, median, P05 and P95 flow; median and P05 directional limits; directional-flow shares; reversal counts; and forced-direction interval counts for every half-hour of the day across the two-year sample. This preserves the morning ramp, solar-hours transfer pattern, evening ramp and overnight regime without adding 48 raw dummy variables to a forecast.

For modelling, compress the diurnal shape into clock sine/cosine, season × clock interactions, and a small set of learned training-only profiles or principal components. Retain explicit ramp-window flags only when cross-validation shows they improve event forecasts.

The HTML report also shows reversal and forced-export/import rates by half-hour. These event-rate curves are useful for identifying ramp windows and directional-regime risk before adding any high-cardinality clock features.

## Generator influence

`Abs impact MW-observations` sums `abs(-b/a × ΔMW)` while a unit appears in an applicable QNI equation. Tightening preserves the direction-specific sign; event ranks count exposure during sharp limit contractions, flow reversals and negative directional limits. `Flow-move rho` is a weighted monthly Spearman association, not causation.

|   Rank | DUID     |   Active months |   Equation versions | Abs impact MW-observations   |   Mean abs impact MW | P95 abs impact MW   | Tightening MW-observations   |   Contraction rank |   Reversal rank |   Forced rank |   Flow-move rho |
|-------:|:---------|----------------:|--------------------:|:-----------------------------|---------------------:|:--------------------|:-----------------------------|-------------------:|----------------:|--------------:|----------------:|
|      1 | NEWENSF2 |              24 |                5083 | 3,610,167                    |               15.778 | 109.828             | 1,949,683                    |                  1 |               6 |             6 |           0.075 |
|      2 | NEWENSF1 |              24 |                5083 | 3,503,826                    |               15.238 | 102.543             | 1,897,102                    |                  2 |               6 |             6 |           0.074 |
|      3 | SAPHWF1  |              24 |               10819 | 3,331,645                    |               11.42  | 64.598              | 1,606,821                    |                  3 |               1 |             1 |           0.063 |
|      4 | WRWF1    |              24 |                6049 | 2,147,247                    |                7.756 | 58.347              | 1,054,020                    |                  6 |               2 |             2 |           0.049 |
|      5 | METZSF1  |              24 |                6053 | 2,139,708                    |                8.32  | 98.086              | 1,131,077                    |                  5 |               2 |             2 |           0.013 |
|      6 | TUMUT3   |              22 |                3635 | 2,040,814                    |              292.471 | 13,514.088          | 1,461,186                    |                  4 |              73 |            72 |           0.005 |
|      7 | BW01     |              24 |                4269 | 1,269,843                    |               16.284 | 114.592             | 693,659                      |                  7 |              10 |            10 |          -0.03  |
|      8 | GNNDHSF1 |              24 |                5861 | 1,193,379                    |                7.07  | 69.506              | 670,650                      |                  8 |               8 |             5 |           0.01  |
|      9 | BW03     |              24 |                4096 | 1,064,965                    |               18.039 | 154.096             | 595,579                      |                  9 |              12 |            12 |          -0.03  |
|     10 | BW04     |              24 |                4096 | 1,009,649                    |               14.209 | 169.058             | 546,154                      |                 11 |              12 |            12 |          -0.048 |
|     11 | BW02     |              24 |                4269 | 869,569                      |               12.786 | 112.268             | 494,404                      |                 12 |              10 |            10 |          -0.016 |
|     12 | UPPTUMUT |              22 |                3635 | 832,019                      |              133.065 | 2,821.663           | 557,505                      |                 10 |              73 |            72 |           0.012 |
|     13 | WELNSF1  |              24 |                3920 | 762,861                      |               33.004 | 701.855             | 324,003                      |                 23 |              14 |            12 |          -0.015 |
|     14 | MOREESF1 |              24 |                5642 | 701,367                      |                2.991 | 22.832              | 387,994                      |                 17 |               5 |             8 |          -0.01  |
|     15 | MP1      |              24 |                3851 | 670,636                      |               29.662 | 328.044             | 398,750                      |                 15 |              34 |            25 |          -0     |
|     16 | ER02     |              24 |                3012 | 670,338                      |                6.801 | 79.890              | 333,496                      |                 22 |              25 |            30 |           0.032 |
|     17 | ER01     |              24 |                3012 | 653,803                      |               10.046 | 189.810             | 323,573                      |                 24 |              25 |            30 |           0.042 |
|     18 | STAN-2   |              24 |                1550 | 642,269                      |               98.543 | 774.741             | 419,482                      |                 13 |             141 |           130 |           0.063 |
|     19 | CPP_3    |              24 |                2047 | 621,961                      |               59.184 | 693.984             | 366,080                      |                 18 |             131 |            98 |           0.056 |
|     20 | KPP_1    |              24 |                2605 | 595,789                      |               11.985 | 237.683             | 312,275                      |                 25 |              92 |            87 |           0.031 |

The complete ranking, factor extrema, equation-version coverage and event measures are in [qni_2y_generator_rankings.csv](data/qni_2y_generator_rankings.csv). The compressed [unit-by-equation factor file](data/qni_2y_unit_equation_factors.csv.gz) preserves every distinct exact-version `b` coefficient, QNI `a` coefficient and derived `-b/a` sensitivity. Seasonal ranks should be used to decide which unit-specific pressure terms are stable enough to keep. Units that rank highly in only one season should be pooled into constraint-family or regional pressure features until an untouched period confirms persistence.

## Binding, near-binding, setter and leading equations

`Binding` means absolute published marginal value above numerical zero. `Near binding` means solved constraint slack divided by the absolute QNI coefficient is between 0 and 50 MW. `Near setting` means the equation’s implied bound is within 50 MW of the reconstructed directional envelope. `Leading` means it is the reconstructed tightest valid upper or lower equation. Reported setters come from `EXPORTGENCONID` and `IMPORTGENCONID`; reconstructed leaders are kept separately so disagreement remains visible.

The 40 most operationally relevant exact versions are shown below. The [complete equation file](data/qni_2y_constraint_equations.csv) includes every researched exact version, QNI coefficient, description, constraint-set membership, overlapping invoked sets, applicable counts, binding/near-binding/near-setting counts, leading counts, marginal-value summary and QNI-normalised slack.

| Direction   | Constraint          |   Version |   QNI coefficient |   Binding |   Near binding |   Near setting |   Leading | Type                  | Constraint sets                                       |
|:------------|:--------------------|----------:|------------------:|----------:|---------------:|---------------:|----------:|:----------------------|:------------------------------------------------------|
| upper       | N>>NIL_33_34        |         1 |             0.985 |      1666 |           1972 |          65288 |     61241 | Thermal               | N-NIL                                                 |
| lower       | QN+RAISE_NIL        |         1 |            -1     |      1700 |           2544 |          52274 |     48446 | Other                 | N-NIL                                                 |
| upper       | N^^Q_NIL_KPP_1      |         1 |             1     |       471 |           1029 |          26809 |     23554 | Voltage Stability     | N-NIL                                                 |
| lower       | N>>NIL_8U_86_S      |         1 |            -1     |       140 |            408 |          21041 |     17724 | Thermal               | N-NIL                                                 |
| upper       | N>>NIL_86_85_N      |         1 |             0.999 |         0 |              0 |          20558 |     17147 | Thermal               | N-NIL                                                 |
| upper       | N>>NIL_33_34        |         1 |             0.985 |         7 |             11 |          16009 |     15966 | Thermal               | N-NIL                                                 |
| lower       | F_Q++NIL_R6         |         1 |            -1     |       533 |            965 |          23524 |     15535 | FCAS                  | F-I_NIL, N-NIL                                        |
| lower       | N>>NIL_964_84_S     |         1 |            -0.746 |      1351 |           1442 |          14025 |     12537 | Thermal               | N-NIL                                                 |
| upper       | N>>NIL_33_34        |         1 |             0.985 |       312 |            432 |          11253 |     10616 | Thermal               | N-NIL                                                 |
| upper       | NQ_950_TEST         |         1 |             1     |        54 |            312 |          24625 |     10573 | Discretionary         | I-NQ_950_TEST                                         |
| lower       | N>>NIL_85_86_S      |         1 |            -0.986 |      1996 |           2848 |          15432 |     10431 | Thermal               | N-NIL                                                 |
| upper       | N>>NIL_33_34        |         2 |             0.958 |       250 |            813 |          11710 |      9849 | Thermal               | N-NIL                                                 |
| upper       | NQ_950_DYN_TEST     |         1 |             1     |       243 |            514 |          24850 |      9362 | Transient Stability   | I-NQ_950_TEST                                         |
| lower       | N>>NIL_85_86_S      |         1 |            -0.986 |      1452 |           4074 |          16471 |      9164 | Thermal               | N-NIL                                                 |
| lower       | F_Q++NIL_R5         |         1 |            -1     |       333 |            623 |          16540 |      8489 | FCAS                  | F-I_NIL, N-NIL                                        |
| upper       | N^^Q_ARSR_KPP_1     |         1 |             1     |         0 |              0 |           7653 |      7131 | Voltage Stability     | N-ARSR_8E                                             |
| lower       | N>>NIL_964_84_S     |         1 |            -0.746 |      1693 |           2486 |          13583 |      6807 | Thermal               | N-NIL                                                 |
| upper       | N>>NIL_33_34        |         1 |             0.958 |      1354 |           1513 |           7462 |      6407 | Thermal               | N-NIL                                                 |
| lower       | N>>NIL_964_88_S     |         1 |            -0.742 |      3244 |           6570 |          19959 |      5898 | Thermal               | N-NIL                                                 |
| lower       | QN_590              |         1 |            -1     |       489 |           2443 |           8262 |      5559 | Discretionary         | I-BCDM_ONE, I-QN_590, N-ARDM_8C, N-ARSR_8E, N-DMSR_8J |
| lower       | N>>NIL_964_84_S     |         1 |            -0.746 |       437 |            583 |           7051 |      5396 | Thermal               | N-NIL                                                 |
| lower       | N>>NIL_964_84_S     |         1 |            -0.746 |      1864 |           2158 |           8235 |      5210 | Thermal               | N-NIL                                                 |
| lower       | N>>NIL_86_85_S      |         1 |            -0.999 |      1781 |           3666 |          13502 |      4078 | Thermal               | N-NIL                                                 |
| lower       | N>>NIL_964_84_S     |         1 |            -0.746 |      2742 |           3164 |           5731 |      4065 | Thermal               | N-NIL                                                 |
| upper       | N>>NIL_33_34        |         2 |             0.958 |       254 |            307 |           4646 |      3965 | Thermal               | N-NIL                                                 |
| lower       | QNI_SOUTH_590_DYN   |         1 |            -1     |      2770 |           3782 |           9578 |      3944 | Transient Stability   | I-BCDM_ONE, I-QN_590, N-ARDM_8C, N-ARSR_8E, N-DMSR_8J |
| lower       | Q:N_760             |         1 |            -1     |       322 |            534 |           4017 |      3844 | Oscillatory Stability | N-ARDM_8C, N-ARSR_8E, N-DMSR_8J, N-X_8C+8E            |
| lower       | Q:N_760             |         1 |            -1     |       493 |            747 |           3937 |      3759 | Oscillatory Stability | N-ARDM_8C, N-ARSR_8E, N-DMSR_8J, N-X_8C+8E            |
| lower       | N>>NIL_8U_86_S      |         1 |            -1     |        27 |            101 |           5635 |      3589 | Thermal               | N-NIL                                                 |
| upper       | N^^Q_ARDM_KPP_1     |         1 |             1     |         0 |              0 |           3518 |      3177 | Voltage Stability     | N-ARDM_8C                                             |
| upper       | Q>>TRSP_BKSP_MESP   |         1 |             0.954 |         0 |              0 |           2874 |      2818 | Thermal               |                                                       |
| lower       | N>>NIL_964_84_S     |         2 |            -0.746 |      1165 |           1454 |           3827 |      2496 | Thermal               | N-NIL                                                 |
| upper       | NQ_630              |         1 |             1     |         0 |              0 |           2470 |      2129 | Discretionary         | I-BCDM_ONE, I-NQ_630, N-ARDM_8C, N-ARSR_8E, N-DMSR_8J |
| upper       | N>>LDTM_33_34_OPEN  |         1 |             0.981 |        73 |            115 |           2272 |      2115 | Thermal               | N-LDTM_82, N-X_KCTX_LDTM                              |
| lower       | N>>NIL_964_88_S     |         1 |            -0.742 |         5 |           1555 |          13254 |      2113 | Thermal               | N-NIL                                                 |
| lower       | N>>NIL_85_86_S      |         1 |            -0.986 |       387 |            509 |           2828 |      2111 | Thermal               | N-NIL                                                 |
| lower       | F_Q++NIL_R60        |         1 |            -1     |       359 |            618 |          15895 |      1906 | FCAS                  | F-I_NIL, N-NIL                                        |
| lower       | N>>NIL_86_8U_S      |         1 |            -1     |         0 |              0 |           3239 |      1788 | Thermal               | N-NIL                                                 |
| upper       | N>>LDTM_33_34_CL    |         1 |             0.942 |         0 |              0 |           2039 |      1773 | Thermal               | N-LDTM_82, N-X_KCTX_LDTM                              |
| lower       | N>>LDTM_964_81_OPEN |         1 |            -0.701 |       111 |            167 |           1953 |      1664 | Thermal               | N-LDTM_82, N-X_KCTX_LDTM                              |

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

The reusable [feature dictionary](data/qni_2y_feature_dictionary.csv) records each feature group, unit, definition and recommended variable count. The configuration and orchestrator accept the interconnector ID, dates, thresholds and storage limits as parameters, so the same method can be applied to another interconnector after its study config is reviewed.

## Calculation method

For each exact effective generic-constraint version:

```text
a * QNI + sum(b_i * P_i) + other solved terms <= RHS
conditional QNI bound = observed QNI flow + (RHS - solved LHS) / a
unit sensitivity = -b_i / a
30-minute unit pressure = sensitivity * (P_i[t] - P_i[t-30m])
```

Positive `a` yields an upper signed-flow bound; negative `a` yields a lower bound. The minimum upper and maximum lower valid candidates form the reconstructed envelope. Constraint versions are matched using dispatch-supplied effective date/version where available, with time-effective fallback recorded by the feature audit. The first 30 minutes of each independently processed month lack a within-file 30-minute unit change and are excluded from movement attribution; this affects 12 hours across two years, about 0.07% of the study timeline, while equation, binding, limit, flow, seasonal and diurnal coverage remain intact.

## Interpretation limits and testing use

- Generator rankings describe mechanical exposure under observed dispatch and constraint regimes. Simultaneous system responses prevent a causal claim.
- Reported directional limits depend on solved dispatch and should not be interpreted as independent transmission ratings or jointly feasible counterfactual capacities.
- Near-binding and near-setting thresholds are both 50 MW in QNI-normalised space and should be sensitivity-tested at 25 and 100 MW before feature selection is frozen.
- Feature selection must use training seasons only. Evaluate the frozen compact block on a later untouched chronological period against persistence, reported-setter history and a non-topological fundamentals baseline.
- Forecast-horizon pressure requires lagged dispatch plus generator scenarios or unit forecasts. Realised future dispatch must never enter an operational backtest.

## Rebuild

```powershell
python -m nemic.constraint_longitudinal run --config configs/constraint_qni_2y.json
python scripts/build_qni_two_year_report.py --config configs/constraint_qni_2y.json
python scripts/build_docs_html.py
python -m unittest discover -s tests -v
```
