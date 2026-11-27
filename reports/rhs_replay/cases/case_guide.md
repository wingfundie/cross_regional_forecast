# Feeding the three sampled equations

The case inputs describe the data bundle used by dispatch. For historical replay, terms.csv identifies each operator, factor, field and value. The replay.csv file contains the historical comparator, invocation and solution metadata. All timestamps use fixed UTC+10 and identify interval ends. An EMS timestamp records the measurement supplied to dispatch. Public availability requires a separate release timestamp.

## Sydney snapshot

For version 1 effective 11 July 2024, DATASNAP_DFS_NSYD adds 10,000 MW to analog N_SYDNEY_LOAD. The point maps to NSW1.LOAD.SYDLOAD.MW. It covers Sydney, Wollongong and Newcastle. The formula is a convenient arithmetic control and the 10,000 MW offset explains the large positive headroom. All 72 sample points carried EMS_Replaced=True and Can_Use_Value=True. The successful check thus reproduces the value that dispatch used. A lagged published snapshot may expose an earlier reading. Feeding the target interval's own snapshot RHS back into this control would invalidate the replay.

## NSW–Queensland stability constraint

For version 1 effective 1 May 2023, N::Q_NIL_KC invokes the generic equation X_N::Q_KPP_1_DS, version 1 effective 28 April 2023. With d equal to Terranora load in MW, i equal to initial N-Q-MNSP1 flow in AEMO's signed direction, and N and Q equal to the calculated regional RHS demand inputs in MW, the formula is

    RHS = 1488 − 50 − 55 − 0.001 (i + d)² − 0.0239 N + 0.0524 Q − 0.6394 d

Terranora load enters twice. Replacing only the final linear term would miss its contribution to the squared flow term. For a single-input counterfactual, evaluate proxy_constant + proxy_linear × d + proxy_quadratic × d² using the corresponding columns in replay.csv. They incorporate contemporaneous values of the other inputs.

The regional R terms matter for this equation. Across the 72 sampled cases, regional initial demand plus the five-minute demand change and aggregate dispatch error, minus the allocated initial-flow losses, reconciled both terms to the published RHS precision. The calculation retains the losses for every occupied case segment. Scheduled-load InitialMW changes the regional FixedDemand reported by dispatch. Deducting it from the R terms caused errors up to 25.7064 MW in this equation. Initial wholesale demand response was zero throughout, leaving its nonzero treatment untested.

In regional_demand_components.csv, sum rhs_component by interval and region to recover the demand used in the equation. Sum value to recover the separate FixedDemand diagnostic including the dispatchable load and WDR adjustments. We verified the latter against each case's independently reported regional FixedDemand at two-decimal precision. AEMO's general guidance describes components of regional demand. The different observed treatment of scheduled load in this equation is an empirical finding from these specific versions and windows. [AEMO dispatch fallback procedure](https://www.aemo.com.au/-/media/Files/Electricity/NEM/Security_and_Reliability/Power_System_Ops/Procedures/SO_OP_3706%20Failure-of-Market-or-Market-Systems.pdf) · [AEMO demand terms, table 4](https://www.aemo.com.au/news/-/media/Files/Electricity/NEM/Security_and_Reliability/Dispatch/Policy_and_Process/Demand-terms-in-EMMS-Data-Model.pdf)

The public five-minute DISPATCHREGIONSUM.TOTALDEMAND agreed with the rebuilt FixedDemand to its two-decimal precision in all 144 region–interval observations. Its largest difference from the constraint R input was 203.088 MW in NSW and 490.576 MW in Queensland. regional_validation.csv contains the matched rows.

The separate snapshot equation DATASNAP_TE_967_1 carries 10000 + TERRANORA_LOAD in the 1 February case. This makes a lagged public snapshot a candidate source for the local input. The three principal replays use the case's T174_TRA.SUMM.TRA_LOAD.MW value directly.

## George Town equipment state

For version 1 effective 29 September 2015, T^V_NIL_9 uses 594 − 244 × GTOWN_FL_TIMER. The state maps to G_TOWN.STATUS.FLT_LEVEL_LOW.STAT. A transition from 0 to 1 lowers the RHS from 594 MW to 350 MW. The state remained 1 throughout all 72 observations. Historical files provided the selected state, while its transition to 0 remains untested. An older status timestamp may describe an unchanged binary state, so age alone cannot verify a live transition.

## Validation and reproduction

Run python scripts/rhs_cases.py from the project root to reproduce the three cases. It reads the existing February DISPATCHCONSTRAINT archive and requests selected compressed byte ranges of three daily NEMDE archives. Each case member is CRC-checked by the ZIP reader, hashed and decompressed in memory. The source manifest identifies the URL and hash scope of each selected range. The case_members.csv file identifies every decompressed case by hash.

The calculator reads only NemSpdInputs. Validation joins the interval, run, intervention, equation, effective date and version to the monthly dispatch solution. Set and invocation IDs come from the matching case tracking rows. Block status comes from BlockedGenericConstraintCollection. The published constraint LHS, marginal value and violation degree provide historical context for the measured impact of changing RHS. [AEMO February NEMDE files](https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/NEMDE/2026/NEMDE_2026_02/NEMDE_Market_Data/NEMDE_Files/)
