# Flagship Edition C · Interconnector Forecasting Verdict, Clustering & Project EnergyConnect (v2)

Self-contained Virtual Barrels institutional synthesis bridging observed Project EnergyConnect (`NSW1-SA1`) commissioning telemetry into the AEMC `ERC0386` loop settlement engine (`nemic.valuation.loop`), auditing EnergyConnect issue-time Predispatch/ST PASA forecasts, visualising all 50 long-range MT PASA bands (`10/10` retain baseline), evaluating leakage-controlled QNI/VNI clustering against matched controls, and enforcing strict architectural separation across the repository's three model stacks (`original`, `experiments`, `production`).

## Rebuild
```powershell
python -m nemic.experiments.ic_forecasting_pec_v2
python reports/ic_forecasting_and_pec_v2/build_html.py
python -m pytest -q tests/test_ic_forecasting_pec_v2.py
node reports/ic_forecasting_and_pec_v2/qa_report.cjs
```
