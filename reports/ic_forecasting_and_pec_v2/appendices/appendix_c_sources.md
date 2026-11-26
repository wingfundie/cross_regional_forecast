## Appendix C · Sources, Regulatory References, and Scope Qualifications

### C.1 Institutional and repository references

1. **Australian Energy Market Commission (AEMC).** *Improving the Inter-Regional Settlement Residue Arrangements (ERC0386): Final Rule Determination*, 25 September 2025 (Sections 3.2.1-3.2.3 and Appendix B net-trade loop settlement algorithm implemented in `nemic/valuation/loop.py`).
2. **Australian Energy Market Operator (AEMO).** *Project EnergyConnect Commissioning and Interconnector Testing Notices* and *Predispatch / ST PASA / MT PASA Market Procedures* (governing `NSW1-SA1` 150 MW commissioning and 350 MW testing envelopes).
3. **Holm, S. (1979).** *A simple sequentially rejective multiple test procedure.* Scandinavian Journal of Statistics, 6(2), 65-70 (family-wise error control applied across all 241 seven-day clustering comparisons).
4. **Hubert, L., & Arabie, P. (1985).** *Comparing partitions.* Journal of Classification, 2(1), 193-218 (Adjusted Rand Index used to audit seed and chronological block stability).
5. **IC Flow Forecasting Research Programme.** Preserved baseline reports left completely untouched on disk: `reports/forward_forecasting_verdict_20261005/`, `reports/qni_vni_clustering_v1/`, `reports/qni_vni_longrange_v1/`, `docs/QNI_VNI_EXPANDED_FORECAST_RESEARCH.md`, and `reports/interregional_valuation_research_v3/`.
6. **IC Flow Forecasting Research Programme.** Companion Flagship Editions A and B: `reports/constraint_pressure_atlas_v2/Constraint_Pressure_Atlas_v2.html` and `reports/outage_risk_handbook_v2/Outage_Risk_Handbook_v2.html`.

### C.2 Scope qualifications and permitted claims

- **Historical-price loop counterfactual:** Chapter 2's AEMC `ERC0386` loop settlement bridge holds 2024 to 2026 regional clearing prices and pre-existing VNI and Heywood+Murraylink flows fixed while injecting observed EnergyConnect commissioning capacity profiles. Because live physical transfer also compresses regional price spreads, the fixed-price totals represent an upper bound on gross loop dollars while accurately isolating bucket reallocation and negative-residue netting geometry.
- **No model promotion implied:** Neither the long-range 1-to-90-day MT PASA challengers (`10/10` retained baseline) nor the leakage-controlled clustering models (`0/241` Holm-significant wins) nor the EnergyConnect commissioning regressions (`Regional + Constraints`) are promoted for operational dispatch forecasting.
- **Strict three-stack isolation:** Consistent with `AGENTS.md`, this report keeps `original` conditional backtest claims, `experiments` retrospective research bundles, and `production` offline routing scaffolding strictly separated.
- **Dispatch-solution limits:** Every observed `NSW1-SA1`, VNI, QNI, and Heywood limit analysed in this report is an endogenous AEMO dispatch-solution output rather than maximum static physical wire capability.
