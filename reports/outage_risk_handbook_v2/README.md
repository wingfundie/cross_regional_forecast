# Flagship Edition B · Outage Risk & NOS Regime Handbook (v2)

Self-contained Virtual Barrels institutional research handbook consolidating NEM Network Outage Scheduler (NOS) regime attribution, economic `$/MWh` and `$/day` SRA outage impacts, strictly chronological Empirical-Bayes + isotonic binding-outlook calibration, N-1-1 concurrent-outage super-additivity, and hierarchical corridor pooling across all 50 high-impact transmission lines (including Capital–Canberra Line 6 and Dapto–Marulan Line 8).

## Rebuild
```powershell
python -m nemic.experiments.outage_risk_v2
python reports/outage_risk_handbook_v2/build_html.py
python -m pytest -q tests/test_outage_risk_v2.py
node reports/outage_risk_handbook_v2/qa_report.cjs
```
