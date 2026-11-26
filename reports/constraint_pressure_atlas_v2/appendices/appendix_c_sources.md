## Appendix C · Sources, Methodology Notes, and Scope Qualifications

### C.1 Primary institutional and regulatory references

1. **Australian Energy Market Operator (AEMO).** *Constraint Formulation Guidelines* and *Constraint Implementation Guidelines* (NEM Dispatch Engine linear-programme structure, generic constraint naming conventions, feedback equations, and dynamic right-hand-side telemetry).
2. **Australian Energy Market Operator (AEMO).** *Negative Residue Management Procedures* (automatic interconnector clamping thresholds, counter-price accumulation triggers, and physical security override hierarchy).
3. **Australian Energy Market Operator (AEMO).** *Settlement Residue Auction (SRA) Rules and Procedures* (directional pooling of QNI with Directlink on the Queensland-New South Wales border, and Heywood with Murraylink on the Victoria-South Australia border).
4. **Australian Energy Market Commission (AEMC).** *National Electricity Rules (NER) Chapter 3* (central dispatch, regional reference pricing, interconnector settlement residues, and Market Network Service Provider dispatch offers).
5. **IC Flow Forecasting Research Programme.** *Interregional Valuation Research v3* (`reports/interregional_valuation_research_v3/NEM_Interconnector_Valuation_v3.html`), companion source for settled five-minute directional SRA residues and regional price panels.
6. **IC Flow Forecasting Research Programme.** *Standalone Event Atlases v2* (`reports/event_atlases_v2/{vni,qni,vsa}_event_atlas_v2.html` and `{VNI,QNI,VSA}_Event_Atlas_v2.md`), companion five-minute forensic case libraries covering 294 detailed windows across VNI, QNI, and Heywood.

### C.2 Methodological caveats and permitted claims

To uphold strict scientific and institutional discipline across the repository's three distinct model stacks, readers should keep four boundaries firmly in mind:

- **Dispatch-solution outputs versus physical capability:** Every interconnector export and import limit analysed in this atlas is an endogenous output of AEMO's five-minute dispatch solution. Limits reflect the joint state of generator offers, synchronous inertia, system-strength rules, dynamic line ratings, and discretionary clamps; they must never be interpreted as static maximum secure physical transfer capability.
- **Mechanical attribution versus independent causation:** Fixed-equation generator pressure ($-b_i / a \times \Delta P_i$) measures exact mechanical sensitivity along a solved linear inequality. Because generator dispatch, regional load, weather, and constraint invocations co-move within the same five-minute interval, generator rankings are mechanical and economic attributions rather than randomised causal treatment effects.
- **Model-stack separation:** This atlas belongs to the `nemic.experiments` network-state research stack. It does not alter, overwrite, or mix feature contracts with the original six-interconnector conditional backtest (`run_pipeline.py`) or the provider-neutral routing scaffold (`nemic.production`). Legacy baseline reports (`reports/all_interconnector_regime_research_20260921/` and `docs/html/*_event_atlas.html`) remain completely untouched on disk.
- **Backward-looking attribution versus live forecasting:** Although Chapter 9 defines a leak-free issue-time feature contract derived from these diagnostics, the metrics reported in Chapters 2 through 8 are retrospective attribution statistics over September 2024 to August 2026. Any predictive feature extracted from this atlas must pass strict chronological out-of-sample walk-forward evaluation against persistence and matched AEMO predispatch vintages before promotion.
