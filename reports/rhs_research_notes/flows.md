# Initial flows and the NSW–Queensland stability limit

- Six interconnectors were evaluated on 72 five-minute deliveries per horizon on 19, 20 and 22 February 2026.
- Adding three earlier pump readings reduced short-lead RHS error from 27.92 to 11.44 MW.
- The short-lead issued marginal value detected seven binding intervals and produced eleven false alerts.

The initial flow entering a dispatch expression is measured at the start of the interval. An issued target describes where dispatch expects flow to move. The preceding delivery target from the same forecast vintage is a plausible starting estimate. For Directlink it recorded 23.7 MW short-lead error, against 13.9 MW for carrying the meter reading.

The regional demand definition also matters. At delivery, adding three measured pump loads to public regional demand reduced stability-limit error from 22.18 to 2.12 MW with other terms observed. At issue the future pump readings were unknown. Carrying their earlier values helped at short leads and offered little improvement the previous afternoon.

The previous-afternoon issued forecast missed all seven economic binds. Those intervals occurred in three episodes on one morning. Evaluate headroom using an issued left-hand side, and retain the event dates alongside interval counts when judging alert reliability.

### Signed interconnector flow

| Signed link   |   Short carry |   Short clock |   Short issued |   Day carry |   Day clock |   Day prior target |   Day ramp |
|:--------------|--------------:|--------------:|---------------:|------------:|------------:|-------------------:|-----------:|
| N-Q-MNSP1     |          13.9 |          41.9 |           23.7 |        63.8 |        41.9 |               57.2 |       58.0 |
| NSW1-QLD1     |         149.4 |         642.1 |          202.9 |       245.5 |       642.1 |              413.0 |      414.1 |
| T-V-MNSP1     |          35.9 |          86.8 |           34.7 |        48.3 |        86.8 |               61.2 |       59.7 |
| V-S-MNSP1     |          14.4 |          17.2 |           22.7 |        25.1 |        17.2 |                7.9 |        7.4 |
| V-SA          |          70.6 |         222.4 |          189.4 |       198.9 |       222.4 |              228.4 |      226.9 |
| VIC1-NSW1     |         118.5 |         101.1 |          244.6 |       146.4 |       101.1 |              380.8 |      386.4 |

### Regional demand semantics and full NSW–Queensland RHS

| method                                                                      |   Short MAE |   Day-ahead MAE |
|:----------------------------------------------------------------------------|------------:|----------------:|
| RHS persistence                                                             |       12.21 |           15.79 |
| clock RHS profile                                                           |       27.54 |           27.54 |
| issued AEMO RHS                                                             |       27.92 |           36.48 |
| Issued flow and local load + total demand plus three prior pump readings    |       11.44 |           36.50 |
| Issued flow and local load + total demand only                              |       27.92 |           36.50 |
| Issued flow and local load + total demand plus all issued dispatchable load |       19.06 |           12.06 |
| regional forecast change from observed RHS                                  |       10.95 |           51.23 |
| regional forecast with clock flow and fixed load share                      |       34.67 |           53.90 |

## Sources and evidence

- [February 2026 research record, method and supporting tables](../../local_exports/rhs_approximation_study/flows/report.md)
- [AEMO predispatch](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/pre-dispatch)
- [Public DispatchIS](https://www.nemweb.com.au/Reports/ARCHIVE/DispatchIS_Reports/)
- [Public unit SCADA](https://www.nemweb.com.au/Reports/ARCHIVE/Dispatch_SCADA/)
