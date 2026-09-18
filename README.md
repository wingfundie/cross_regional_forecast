# INTERFLOW · NEM interconnector forecast lab

Local research dashboard and reproducible three-year conditional backtest for QNI, Directlink, VNI, Heywood, Murraylink and Basslink.

## Open

Run `python app.py`, then open [the local dashboard](http://127.0.0.1:8050). `start_dashboard.ps1` is an equivalent launcher.

## Reproduce

Install the packages in `requirements.txt`. Run `python run_pipeline.py` from this directory. The pipeline caches NEMWEB ZIPs and Open-Meteo responses, preserves five-minute observations, fits models, calibrates on validation, evaluates every half-hour origin and lead through seven days, matches original AEMO forecast vintages, runs a scenario and verifies completion. `--from-step N` resumes a specific stage.

Read `BUILD_PLAN.md` for the agreed specification and `BACKTEST_REPORT.md` for executed results and limitations. Model, source-data and result files stay local; no external publishing or scheduled live forecasting is configured.

## Documentation

- [Quarterly interregional valuation research](reports/interregional_valuation_research_20260918/Quarterly_Interregional_Valuation_Research.html) and [research package guide](reports/interregional_valuation_research_20260918/README.md): nine interactive charts and three explanatory diagrams covering energy-versus-scarcity decomposition, joint price states, frequency and severity, tail concentration, flow–spread covariance, payoff mechanics, physical triggers and the valuation architecture; includes an illustrative futures/SRA workbench, 32 external references, and a staged implementation design. The checked-in CSVs are compact aggregate evidence used by the report; raw market archives remain local and excluded from Git.

- [Diurnal and NOS forecasting research](docs/QNI_VNI_DIURNAL_NOS_RESEARCH.md), [implementation plan](docs/QNI_VNI_DIURNAL_NOS_IMPLEMENTATION_PLAN.md) and [VNI execution guide](docs/VNI_DIURNAL_NOS_EXECUTION.md): delivery-period models, NOS vintage replay, data-profiled chronological optimization, MAPE/MAE reporting, model explanations and trained research-bundle handoff. Generated predictions, fitted models and reports remain local and reproducible from the execution guide.

- [QNI diurnal/NOS execution guide](docs/QNI_DIURNAL_NOS_EXECUTION.md), [executed results](docs/QNI_DIURNAL_NOS_RESULTS.md), [saved-model guide](docs/QNI_SAVED_MODEL_GUIDE.md) and [published report centre](reports/qni_diurnal_nos_v2/index.html): the same v2 chronological research protocol rerun for `NSW1-QLD1`, with QNI-specific selection, NOS evidence, explanations and sixteen target × lead-band bundles. Reproduce the complete resumable campaign with `python scripts/run_qni_diurnal_nos_campaign.py`.

The complete offline [HTML handbook](docs/html/index.html) includes the research, results, backtest protocol and improvement roadmap. Rebuild it with `python scripts/build_docs_html.py`. Open the downloaded file in a browser; GitHub's file view displays HTML source.

Five interactive charts cover flow improvement versus persistence, import/export limit errors, interval coverage and restriction recall/precision. `docs/chart_data.json` is an intentionally included compact aggregate-score snapshot, not the raw dataset. Its source hash and the HTML build manifest preserve provenance. The HTML embeds Plotly and works offline; the Python dashboard remains a separate application.

- [Improvement roadmap](docs/IMPROVEMENT_ROADMAP.md): prioritised extra data, candidate methods, source/access caveats and experiments to establish improvement.

- [QNI/VNI forecasting improvement research](docs/QNI_VNI_FORECAST_MODEL_IMPROVEMENT_PLAN.md) · [HTML edition](docs/html/qni_vni_forecast_model_improvement.html): integrates the two-year studies, a retained-data simple-model probe, academic and industry evidence, compact features, operational data requirements and a staged evaluation plan. Rebuild the report with `python scripts/build_forecast_research.py`.

- [Constraint-derived network features](docs/CONSTRAINT_NETWORK_FEATURES.md): proposed end-to-end design for compact generator influence, directional constraint pressure, limit switching and forecast-time network-state features, starting with VNI.

- [Executed VNI feasibility pilot](docs/CONSTRAINT_FEATURE_PILOT.md): guarded table-level acquisition, exact-version equation reconstruction, compact features and the corrected one-month feasibility result. Reproduce it with `python run_constraint_pilot.py`.

- [VNI generator influence study](docs/VNI_GENERATOR_INFLUENCE_STUDY.md): mechanical sensitivities, distinct contraction/reversal/forced-direction events, generator and constraint rankings, the Tumut 3 case study and a compact production feature recommendation.

- [VNI two-year constraint study](docs/VNI_TWO_YEAR_CONSTRAINT_STUDY.md): September 2024–August 2026 binding, near-binding, reported-setter and reconstructed-leader populations, full equation/version and factor snapshots, generator influence rankings, seasonal and diurnal analysis, and a standalone offline HTML report. Reproduce it with `python -m nemic.constraint_longitudinal run --config configs/constraint_vni_2y.json`.

- [QNI generator influence study](docs/QNI_GENERATOR_INFLUENCE_STUDY.md): rerun for `NSW1-QLD1` with all leading equations, invoked constraint sets, unit factors, event rankings, compact-feature results and a standalone offline HTML report. Reproduce it with `python run_constraint_pilot.py --config configs/constraint_qni_pilot.json`.

- [QNI two-year constraint study](docs/QNI_TWO_YEAR_CONSTRAINT_STUDY.md): September 2024–August 2026 binding, near-binding, reported-setter and reconstructed-leader populations, full equation/version and factor snapshots, generator influence rankings, seasonal and diurnal analysis, and a standalone offline HTML report. Reproduce it with `python -m nemic.constraint_longitudinal run --config configs/constraint_qni_2y.json`.

- [V-SA two-year constraint study](docs/VSA_TWO_YEAR_CONSTRAINT_STUDY.md): September 2024–August 2026 binding, near-binding, setter, reconstructed-envelope, seasonal, diurnal and generator-influence analysis for the Victoria–South Australia interconnector.

- [V-SA sharp-contraction event atlas](docs/VSA_TWO_YEAR_EVENT_ATLAS.md): two-year contraction screening with selected-event equation reconstruction, generator contributions, prices, market conditions and a standalone interactive HTML explorer.

- [Results, data and feature engineering](docs/RESULTS_DATA_AND_FEATURES.md): completed results, raw-to-model transformations, publication-aware network state, feature importance and a precise seasonal/diurnal/duck-curve audit.
- [Methods and research](docs/METHODS_AND_RESEARCH.md): literature reviewed, industry definitions, data transformations, model features/settings, restriction probabilities and limitations.
- [Backtest protocol](docs/BACKTEST_PROTOCOL.md): exact split boundaries, training/validation/test steps, publication controls, metrics, bootstrap, AEMO comparison, reproduction and cache caveats.
- [Executed results](BACKTEST_REPORT.md): measured performance and completion evidence.

## Interpretation

- [Expanded QNI/VNI forecasting research](docs/QNI_VNI_EXPANDED_FORECAST_RESEARCH.md) and [offline HTML report](docs/html/qni_vni_expanded_forecast_research.html): wider academic and industry review integrated with the two-year studies, 144 regression comparisons, 20 contraction-probability comparisons, monthly quality audits, and a compact-feature implementation plan from simple models through boosting. Includes [search and access log](docs/QNI_VNI_EXPANDED_RESEARCH_LOG.md). These remain retrospective development experiments, not live validation.

Future realised demand, renewables and weather are explicitly supplied in the main experiment. Its results are conditional research performance, not the accuracy of a live seven-day forecast. Reported AEMO limits depend on dispatch and do not represent maximum secure physical transfer capability. The 50% flag uses the training-only seasonal median of positive directional limits; zero and negative limits remain meaningful outcomes.

## Scenarios

Download a 336-row input template in the Scenarios tab, edit paths or use the regional adjustments, and run the scenario. The example is historical. For explicit future paths from the final observed origin, the command-line runner supports `python -m nemic.scenario --origin "2026-09-01 00:00" --input inputs.csv --output outputs.csv`. Later issue dates require additional observed network history, which is not invented.

## Storage and operation

The repository contains source code, Markdown documentation and the requested HTML documentation export. Historical datasets, fitted models and runtime result tables remain local and are excluded from Git. A fresh clone needs `python run_pipeline.py` to produce the local artifacts required by the dashboard; it is not a bundled live forecast service. The checked-in report preserves the completed experiment's findings.

- `data/raw/`: original public archives; `data/tables/`: extracted records; `data/processed/`: five-minute and half-hour tables.
- `models/`: fitted regressors and frozen calibration/selection.
- `results/`: scores, audits, scenario outputs and per-origin test predictions.
- `tests/`: meaningful temporal, publication, aggregation, feature-isolation and scenario checks.
- The server binds only to `127.0.0.1:8050`; stopping that Python process stops the dashboard.

HTTPS verification stays enabled. On Windows, `nemic/common.py` builds a local CA bundle from the operating system's trusted public certificates if necessary. The bundle is not committed.
# Multi-interconnector forecasting scaffold

See [the production pipeline guide](docs/PRODUCTION_PIPELINE_GUIDE.md) for provider mappings, model registration/routing, training, portable saved models, scenarios and offline HTML reports. Start with `python -m nemic.production --help` or the synthetic `demo` command. This scaffold does not deploy or schedule live forecasts.
