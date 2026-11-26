## Appendix C · Sources, Methodology Notes, and Scope Qualifications

### C.1 Institutional and repository references

1. **Australian Energy Market Operator (AEMO).** *Network Outage Scheduler (NOS) Operating Procedures and Market Management System Data Model* (booking submission, revision, withdrawal, actual switching timestamps, and constraint-set linkage).
2. **Australian Energy Market Operator (AEMO).** *Settlement Residue Auction (SRA) Rules* (directional pooling of interconnector settlement residues across border pairs and treatment of negative settlement residues).
3. **Efron, B., & Morris, C. (1975).** *Data analysis using Stein's estimator and its generalizations.* Journal of the American Statistical Association, 70(350), 311-319 (foundation for Empirical-Bayes partial pooling across regional transmission corridors).
4. **Zadrozny, B., & Elkan, C. (2002).** *Transforming classifier scores into accurate multiclass probability estimates.* KDD 2002 (monotonic isotonic regression calibration for probabilistic event forecasting).
5. **IC Flow Forecasting Research Programme.** Baseline archived studies preserved untouched on disk: `reports/nos_outage_regime_research_20260924/` and `reports/line_outage_risk_v1/`.
6. **IC Flow Forecasting Research Programme.** Companion Flagship Edition A: *Six-Link Constraint Pressure, Generator Influence, and Contraction Atlas v2* (`reports/constraint_pressure_atlas_v2/Constraint_Pressure_Atlas_v2.html`).

### C.2 Scope qualifications and permitted claims

- **Observational matching versus randomised causation:** Although every NOS family economic estimate pairs treated half-hours strictly against matched non-outage control half-hours and applies seven-day block-bootstrap confidence intervals, transmission maintenance scheduling remains an operational decision conditioned on weather and system security. Estimates represent matched observational attribution rather than randomised causal experiments.
- **Research-only calibrated outlook:** The chronological Empirical-Bayes and isotonic calibration in Chapter 4 demonstrates verified out-of-sample improvement across 11 monthly test origins (`55/96` skilful cells, `92/96` Brier reductions over legacy raw scores). It remains a retrospective research workflow inside `nemic.experiments`, not a deployed or scheduled live outage-alert service.
- **Dispatch-solution limits:** Consistent with all repository standards, AEMO reported interconnector limits are dispatch-solution outputs conditional on simultaneous system dispatch and must not be conflated with static maximum physical transfer ratings.
- **Model-stack isolation:** Flagship Edition B belongs strictly to the `nemic.experiments` outage-research stack and does not modify the original six-interconnector conditional backtest (`run_pipeline.py`), the saved QNI/VNI research bundles, or `nemic.production`.
