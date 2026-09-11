# INTERFLOW · NEM interconnector forecast lab

Local research dashboard and reproducible three-year conditional backtest for QNI, Directlink, VNI, Heywood, Murraylink and Basslink.

## Open

Run `python app.py`, then open [the local dashboard](http://127.0.0.1:8050). `start_dashboard.ps1` is an equivalent launcher.

## Reproduce

Install the packages in `requirements.txt`. Run `python run_pipeline.py` from this directory. The pipeline caches NEMWEB ZIPs and Open-Meteo responses, preserves five-minute observations, fits models, calibrates on validation, evaluates every half-hour origin and lead through seven days, matches original AEMO forecast vintages, runs a scenario and verifies completion. `--from-step N` resumes a specific stage.

Read `BUILD_PLAN.md` for the agreed specification and `BACKTEST_REPORT.md` for executed results and limitations. Model, source-data and result files stay local; no external publishing or scheduled live forecasting is configured.

## Documentation

The complete offline [HTML handbook](docs/html/index.html) includes the research, results, backtest protocol and improvement roadmap. Rebuild it with `python scripts/build_docs_html.py`. Open the downloaded file in a browser; GitHub's file view displays HTML source.

Five interactive charts cover flow improvement versus persistence, import/export limit errors, interval coverage and restriction recall/precision. `docs/chart_data.json` is an intentionally included compact aggregate-score snapshot, not the raw dataset. Its source hash and the HTML build manifest preserve provenance. The HTML embeds Plotly and works offline; the Python dashboard remains a separate application.

- [Improvement roadmap](docs/IMPROVEMENT_ROADMAP.md): prioritised extra data, candidate methods, source/access caveats and experiments to establish improvement.

- [Methods and research](docs/METHODS_AND_RESEARCH.md): literature reviewed, industry definitions, data transformations, model features/settings, restriction probabilities and limitations.
- [Backtest protocol](docs/BACKTEST_PROTOCOL.md): exact split boundaries, training/validation/test steps, publication controls, metrics, bootstrap, AEMO comparison, reproduction and cache caveats.
- [Executed results](BACKTEST_REPORT.md): measured performance and completion evidence.

## Interpretation

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
