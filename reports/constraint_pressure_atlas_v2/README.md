# NEM Six-Link Constraint Pressure, Generator Influence & Contraction Atlas (v2)

Flagship Wave 1 edition unifying the six-link diurnal/constraint-pressure regime research and the two-year VNI, QNI, and V-SA constraint studies while unlocking full 24-month parity for Directlink, Murraylink, and Basslink and closing the MW-without-dollars gap.

## Deliverables

- `Constraint_Pressure_Atlas_v2.html`: Self-contained offline HTML report (Virtual Barrels mechanics-first edition, pure `#ffffff` canvas, 12 inline Plotly exhibits, 3 diagrams, 2 searchable paginated directories, server-side KaTeX, embedded CSV downloads).
- `research_report.md`: Unified standalone Markdown companion.
- `chapters/` & `appendices/`: Modular source files with build-time numeric binding from `evidence/headline_numbers.json`.
- `evidence/`: Compact audited CSV and JSON tables produced by `nemic/experiments/constraint_pressure_v2.py`.
- `report_manifest.json`: Content-addressed SHA-256 manifest.

## Rebuild from Retained Local Archives

```powershell
python -m nemic.experiments.constraint_pressure_v2
python -m nemic.experiments.event_atlas_v2
python reports/constraint_pressure_atlas_v2/build_html.py
node reports/constraint_pressure_atlas_v2/qa_report.cjs
python -m pytest -q tests/test_constraint_pressure_v2.py
```

All legacy Version 1 report folders (`all_interconnector_regime_research_20260921/`, `docs/html/*_2y_constraint_study.html`, `docs/html/*_event_atlas.html`) remain untouched as frozen baselines.
