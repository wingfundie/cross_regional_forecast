# Feature engineering research and evidence register

Written before feature implementation, 2026-09-17. This is a hypothesis register, not measured improvement. Linked local studies contain earlier, differently scoped results.

## Evidence and proposed experiments

| Mechanism | Candidate | Formula / interpretation | Failure mode | Controlled comparison |
|---|---|---|---|---|
| Regional supply-demand imbalance | Endpoint residual difference | (D50-W-S)_sink - (D50-W-S)_source | Bids, storage and other fuels omitted | Network vs network + balance |
| Coincident scarcity | Joint positive coal-balance stress | max(residual_A-coal_A,0) * max(residual_B-coal_B,0) | Coal capacity is neither dispatch nor all reserve | Main effects vs joint stress |
| Renewable export need | Opposing surplus/deficit | max(-residual_source,0) * max(residual_sink,0) | Residual rarely negative; demand definition | Retain only supported training variation |
| Corridor headroom | Forecast imbalance × observed room | Balance difference times upper/lower room separately | Directional limits can be negative, constraints switch | Separate directional interactions |
| Candidate competition | Suppression × switch gap | Regional PASA suppression against upper/lower candidate gap | Suppression embeds AEMO forecast constraint knowledge | Explicit suppression off/on |
| Evening ramp | Solar decline × demand rise | max(-delta solar,0) * max(delta demand,0), same vintage | Product changes can masquerade as ramps | Same-run only; transition flags |
| Station concentration | Coal available-share HHI | Sum squared station shares among known offered coal MW | Incomplete station mapping | Coverage gated, versus simple totals |
| Heat and humidity | Temperature × relative humidity / 100 | Statistical demand stress, not a physical line rating | Sparse weather sites and regional forecast already includes weather | Incremental weather off/on |
| Coal heat exposure | Positive hot-weather degree exposure × coal-balance proxy | 25°C excess at regional demand site times coal balance | Not plant-specific cooling-water conditions | Do not claim thermal derating causality |
| Regional weather contrast | Role-matched signed gradients | Same-role weather_A - weather_B | Different providers/heights | Coherent provider/run and actual height |
| Outage sensitivity | NOS exposure × balance/coal/renewables | Operating conditions modulate restriction exposure | Retrospective mapping/source vintages | Four-way matched factorial |
| Persistent network regime | Forecast shift × setter age / pressure | Forecast change conditioned on observed regime | Missing future RHS and unit dispatch | Near-term versus longer bands |

Power-unit sum/difference features have MW units; products are scaled using training-only statistics. Every interaction retains its parents. Ratios use explicit floors and flags. A demand term already net of rooftop must not subtract rooftop again. No future target, setter, price or realised weather is an input.

## Literature and interpretation

- AEMO constraint FAQ describes interconnector limits as outcomes of generic constraints involving generation, demand and interconnector terms, with thermal/voltage/transient stability mechanisms. https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/system-operations/congestion-information-resource/constraint-faq
- AEMO Renewable Integration Study Appendix C motivates spatial variability, ramps and forecast uncertainty, not a promise of accuracy for these proposed features. https://aemo.com.au/-/media/major-publications/ris/2020/ris-stage-1-appendix-c.pdf
- Existing local research: docs/QNI_VNI_EXPANDED_FORECAST_RESEARCH.md and docs/CONSTRAINT_NETWORK_FEATURES.md. QNI reconstruction discrepancies caution against causal/physical interpretation of statistical pressure features.
- ST/PD PASA schemas are the definition of UIGF versus constrained capacity. Differences include availability restrictions, not only economic/physical curtailment. Schema URLs are in the master methodology.
- Weather provider/source changes are potential distribution shifts. BOM is preferred, ECMWF supports longer labelled research history. Sparse regional locations are proxies rather than engineered line ratings.

## Result contract

For every hypothesis publish cohort, baseline/main/interaction scores, paired uncertainty, selection frequency and supported feature range. Findings remain `not evaluated` until actual matched experiments exist. SHAP is a predictive decomposition, not mechanism identification.
