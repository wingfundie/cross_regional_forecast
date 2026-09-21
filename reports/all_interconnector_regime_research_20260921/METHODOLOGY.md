# Methodology — all-interconnector diurnal and constraint-pressure research

## Scope and frozen windows

The flow, dispatch-limit, weather and VRE study covers `(2023-09-01 00:00, 2026-09-01 00:00]` in fixed UTC+10 NEM time. The constraint and DUID-pressure study covers `2024-09-01 00:00` through `2026-08-31 23:55`. The six links are QNI, Directlink, VNI, Heywood, Murraylink and Basslink. Nominal ratings, ENSO and prices are outside scope.

Australian seasons are complete three-month blocks: Summer December–February, Autumn March–May, Winter June–August and Spring September–November. December belongs to the summer ending in the next year. Calendar-quarter sensitivity uses only complete Q1–Q4 blocks; partial boundary quarters are excluded.

## Flow and dispatch limits

Signed flow follows each connector's declared forward orientation. `forward_capacity = upper_bound`; `reverse_capacity = -lower_bound`. Headroom is capacity less directional flow. Negative capacities are retained and counted as forced-direction observations. A restricted limit is below 50% of the connector-direction Australian-season median of strictly positive capacity. A complete half-hour requires six distinct five-minute observations.

## Weather and VRE

Weather is the mean of retained representative sites in each endpoint region; endpoint maximum temperature is also retained. Regional VRE is cleared semi-scheduled wind plus solar. Residual demand is regional demand less those wind and solar fields; rooftop PV is not subtracted again. Regimes are defined within connector and Australian season: low ≤P20, normal P20–P80 and high ≥P80. Scatterplots use a deterministic sample of 3,000 observed half-hours per connector-direction for browser performance. No trend line, regression or model-derived effect is fitted.

## Constraint reconstruction

For `aF + Σ(bᵢPᵢ) + Z ≤ RHS`, the conditional bound is `observed flow + (RHS − solved LHS)/a`, and DUID sensitivity is `−bᵢ/a`. Positive `a` forms an upper candidate; negative `a` forms a lower candidate. Minimum upper and maximum lower candidates form the reconstructed envelope. Binding means absolute published marginal value above `1e-9`; near-binding means interconnector-normalized slack from 0 to 50 MW. Reported setters and reconstructed leaders remain separate.

Constraint run coverage at build time:

| ic        | name       |   expected_months |   complete_months | status   |
|:----------|:-----------|------------------:|------------------:|:---------|
| NSW1-QLD1 | QNI        |                24 |                24 | complete |
| N-Q-MNSP1 | Directlink |                24 |                24 | complete |
| VIC1-NSW1 | VNI        |                24 |                24 | complete |
| V-SA      | Heywood    |                24 |                24 | complete |
| V-S-MNSP1 | Murraylink |                24 |                24 | complete |
| T-V-MNSP1 | Basslink   |                24 |                24 | complete |

## DUID pressure

For the active reconstructed leader, movement contribution is `sᵢ × (Pᵢ[t] − Pᵢ[t−30m])`. Upper capacity uses that sign; lower/reverse capacity negates it. Tightening is the positive part of a capacity reduction; relief is the positive part of a capacity increase. Rankings therefore reflect observed movement under an active equation, not coefficient size alone and not independent causation. Pumps, batteries and loads retain source dispatch signs. Compact monthly files preserve leader-based pressure; simultaneous non-leading binding equations remain in the constraint-population table but do not receive duplicated connector-level pressure.

## Output lineage

`connector_summary.csv`, `diurnal_profiles.csv`, `seasonal_profiles.csv`, `weather_vre_regimes.csv`, `regime_scatter_sample.csv`, `constraint_family_summary.csv`, `constraint_duid_influence.csv`, `constraint_duid_regime_matrix.csv` and `coverage_audit.csv` are generated before report rendering. The build manifest records input and output hashes. Missing observations are never converted to zero.

## Rebuild

```powershell
python scripts/build_all_ic_regime_report.py
python C:\Users\HomePC\.codex\skills\editorial-html-report\scripts\validate_report.py reports\all_interconnector_regime_research_20260921\index.html
```
