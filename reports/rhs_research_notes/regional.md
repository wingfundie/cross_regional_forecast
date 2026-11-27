# Allocating regional demand to a local load

- Twelve half-hours on 19, 20 and 22 February 2026 formed the morning evaluation.
- For broad Sydney, population allocation recorded 411.6 MW previous-afternoon mean absolute error.
- The issued local forecasts recorded errors of 295.1 MW for Sydney and 8.9 MW for Terranora.

Population allocation gives each resident the same implicit share of regional electricity demand. Its 66.97% weight is fixed through the day. A historical electrical share can vary with delivery time and day type, allowing the local mix of residential load, industrial consumption and embedded generation to influence the estimate.

For Sydney, a clock and day-type share reduced previous-afternoon error to 333.4 MW. A fixed electrical share recorded 380.1 MW. For Terranora, seven of twelve realised half-hours had negative net load. Multiplying positive regional demand by a positive population share misses that operating state altogether.

Benchmark against the issued local monitor wherever its electrical boundary matches. With regional demand alone, fit the share on earlier readings and preserve its sign. These results use AEMO regional vintages and seven training mornings. An alternative provider's forecast errors will also enter the local estimate.

### Day-ahead results

| method                              |   Sydney-area load |   Terranora load |   Network RHS |
|:------------------------------------|-------------------:|-----------------:|--------------:|
| Population share                    |              411.6 |            –   |         –   |
| Fixed historical share              |              380.1 |             20.7 |          52.9 |
| Clock and day-type share            |              333.4 |             22.7 |          56.0 |
| Clock and day-type level            |              438.3 |             20.5 |          27.4 |
| Latest public reading               |             1858.4 |             21.3 |          15.5 |
| Latest reading plus regional change |              426.1 |             18.5 |          51.2 |
| Issued AEMO                         |              295.1 |              8.9 |          36.5 |

### Short-horizon results

| method                              |   Sydney-area load |   Terranora load |   Network RHS |
|:------------------------------------|-------------------:|-----------------:|--------------:|
| Population share                    |              164.1 |            –   |         –   |
| Fixed historical share              |              122.4 |             19.9 |          33.7 |
| Clock and day-type share            |              139.0 |             21.2 |          36.2 |
| Clock and day-type level            |              438.3 |             20.5 |          27.4 |
| Latest public reading               |              183.6 |              4.8 |          11.1 |
| Latest reading plus regional change |              144.6 |              4.6 |          10.1 |
| Issued AEMO                         |              154.6 |              5.1 |          27.9 |

## Sources and evidence

- [February 2026 research record, method and supporting tables](../../local_exports/rhs_forward_feb26/brief.md)
- [ABS source released March 2025](https://www.abs.gov.au/statistics/people/population/regional-population/2023-24)
- [AEMO predispatch files](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/pre-dispatch)
- [Endeavour planning data](https://dapr.endeavourenergy.com.au/)
- [CER postcode solar data](https://cer.gov.au/markets/reports-and-data/small-scale-installation-postcode-data)
