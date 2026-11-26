# INTERFLOW Â· NEM interconnector forecast lab

Local research dashboard and reproducible three-year conditional backtest for QNI, Directlink, VNI, Heywood, Murraylink and Basslink.

## Open

Run `python app.py`, then open [the local dashboard](http://127.0.0.1:8050). `start_dashboard.ps1` is an equivalent launcher.

## Reproduce

Install the packages in `requirements.txt`. Run `python run_pipeline.py` from this directory. The pipeline caches NEMWEB ZIPs and Open-Meteo responses, preserves five-minute observations, fits models, calibrates on validation, evaluates every half-hour origin and lead through seven days, matches original AEMO forecast vintages, runs a scenario and verifies completion. `--from-step N` resumes a specific stage.

Read `BUILD_PLAN.md` for the agreed specification and `BACKTEST_REPORT.md` for executed results and limitations. Model, source-data and result files stay local; no external publishing or scheduled live forecasting is configured.

## Documentation

- [EnergyConnect directional-limit study](execution/pec_limits_v1/README.md) covers the separate `NSW1-SA1` dispatch record, constraint and outage evidence, issue-time evaluation, and an offline scenario tool.

- [Rebid Mistress - 10 October 2026](rebid_mistress/README.md): isolated NSW/QLD/VIC coal, gas and battery energy-rebid forensics, accepted/effective offer reconciliation, observed response, physical portfolio comparisons and an offline evidence explorer. Generated data and reports remain local.

- [Transmission-line outage risk campaign](execution/line_outage_risk_v1/README.md): asset-specific congestion and regional-price research for up to 50 lines, including Capital-Canberra line 6 and Dapto-Marulan line 8. Includes direct asset/set audits, native five-minute prices, chronological controlled comparisons, ten deep dives and a provenance-gated booking outlook. Run `python scripts/run_line_outage_research.py --stage all`; generated reports and interval evidence remain local.

- [Forward forecasting evidence and verdict — 5 October 2026](reports/forward_forecasting_verdict_20261005/index.html): comprehensive offline report with six charts, all 50 new long-range band results, prior-model comparisons, use restrictions and the path to prospective confirmation. The long-range run samples 18 leads rather than a complete half-hour path; collection and shadow schedules are paused. Rebuild with `python scripts/build_forward_forecasting_verdict.py`.

- [Research evidence register](docs/RESEARCH_REGISTER.md): current status, permitted claims, unresolved gates and reproduction entry points across the original backtest, experiment stack, valuation work and production scaffold.
- [QNI/VNI long-range improvement campaign](execution/qni_vni_longrange_v1/README.md) and [executed report](reports/qni_vni_longrange_v1/Long_Range_Research.html): a bounded VNI-first/QNI-second comparison using original-vintage MT PASA availability, daily 08:00 NEM origins and separate 1â€“7, 8â€“14, 15â€“30, 31â€“60 and 61â€“90 day results. All ten historical cells retained the baseline; output remains research-only pending measured-receipt prospective confirmation.

- [QNI/VNI clustering experiment](execution/qni_vni_clustering_v1/README.md), [frozen methodology](execution/qni_vni_clustering_v1/methodology.md) and [future confirmation protocol](execution/qni_vni_clustering_v1/future_confirmation_protocol.md): leakage-controlled origin-state, forecast-condition and generator-sensitivity clustering against matched controls, with a resumable VNI-first/QNI-replication workflow. Generated models, predictions and the local offline report remain ignored research artifacts and are not production routes.

- [Six-interconnector diurnal and constraint-pressure research](reports/all_interconnector_regime_research_20260921/index.html) and [complete methodology](reports/all_interconnector_regime_research_20260921/METHODOLOGY.md): observed scatterplots and regime tables for three years of flows, dispatch limits, temperature, humidity and VRE; Australian seasonal quarter blocks plus calendar-quarter sensitivity; two-year binding-constraint and DUID tightening/relief pressure analysis. Rebuild with `python scripts/build_all_ic_regime_report.py` after the six longitudinal constraint studies are complete. Its **Outage regimes** section (NOS outages, Sep 2024â€“Aug 2026) contains matched limit/flow effects by constraint-set family, a specific-outage lookup (asset â†’ family â†’ substation â†’ area, with electrically and geographically nearby generators), spillover, event studies and booking reliability. It is built by `python scripts/build_nos_regime_section.py` from `scripts/run_nos_regime.py` stages; plan, methodology and execution log are in [`execution/nos_outage_regime_v1/`](execution/nos_outage_regime_v1/PLAN.md). The full standalone write-up of that pass (landscape, family effects, timing and weather, flow response, cross-link spillover and system footprint, constraint/DUID mechanics, event studies, connector chapters, specific-outage lookup, robustness, execution record) is [`reports/nos_outage_regime_research_20260924/index.html`](reports/nos_outage_regime_research_20260924/index.html), rebuilt with `python scripts/build_nos_outage_report.py`. Its constraint-mechanics and 12-month outlook chapters (which equations bind and set each link's limit during every outage family, and a walk-forward-backtested research outlook for booked NOS outages) come from [`execution/nos_constraint_binding_v1/`](execution/nos_constraint_binding_v1/PLAN.md) via `python scripts/run_nos_binding.py --stage â€¦`; results in [`RESULTS_SUMMARY.md`](execution/nos_constraint_binding_v1/RESULTS_SUMMARY.md).

- [Quarterly interregional valuation research](reports/interregional_valuation_research_20260918/Quarterly_Interregional_Valuation_Research.html) and [research package guide](reports/interregional_valuation_research_20260918/README.md): nine interactive charts and three explanatory diagrams covering energy-versus-scarcity decomposition, joint price states, frequency and severity, tail concentration, flowâ€“spread covariance, payoff mechanics, physical triggers and the valuation architecture; includes an illustrative futures/SRA workbench, 32 external references, and a staged implementation design. The checked-in CSVs are compact aggregate evidence used by the report; raw market archives remain local and excluded from Git.
- [Interregional valuation research v2](reports/interregional_valuation_research_v2/Interregional_Valuation_Research_v2.html) and [v2 guide](reports/interregional_valuation_research_v2/README.md): executes the review extensions: AEMO-settled SRA payoff ledger, every auction tranche since 2021 against realised payoffs, SRA-vs-spread hedge effectiveness, loss/congestion decomposition, counter-price and constraint mechanisms, the AEMC loop net-trade rule applied to history, 27 new exhibits and KaTeX-typeset formulas (`nemic/valuation/`).
- [Interregional valuation research v3](reports/interregional_valuation_research_v3/Interregional_Valuation_Research_v3.html), [v3 guide](reports/interregional_valuation_research_v3/README.md), and [v2-to-v3 upgrade plan](reports/interregional_valuation_research_v2_upgrade_plan.html): full mechanics-first Virtual Barrels rewrite (four parts, twelve chapters, three appendices, 28 inline Plotly exhibits, 242 KaTeX formulas, embedded Historical Explorer and Valuation Workbench) with nine Tier A local-data upgrades (SRA $/unit payoff decomposition, ex-2022 & tranche-drift & credit-support carry tests, three-way loop attribution & parametric EnergyConnect sensitivities, quarterly & SRA+cap CVaR frontiers, diurnal operating blocks & negative-price loss inversion, disaggregated walk-forward benchmarks, 2027 Q2 QNI dilution & pro-forma regulated Basslink backcast, FY2027 MPC×CPT truncation, and strictly ex-ante Bachelier option benchmark + Greeks) plus a build-ready Part IV implementation spec and exhaustive paper-by-paper literature synthesis (`nemic/valuation/v3_analytics.py`, `nemic/valuation/v3_summary.py`, `configs/valuation/interregional_valuation_v3.json`).
- [Constraint pressure, generator influence & contraction atlas v2 (Flagship Edition A)](reports/constraint_pressure_atlas_v2/Constraint_Pressure_Atlas_v2.html) and [compressed Event Atlases v2](reports/event_atlases_v2/event_atlases_manifest.json): Virtual Barrels institutional upgrade delivering full 24-month six-link parity (VNI, QNI, Heywood, Directlink, Murraylink, Basslink), tight-headroom congestion-rent DUID and shadow-rent constraint rankings, envelope MAE root-cause audit, full-population LHS/RHS/switch contraction decomposition, five-minute BESS impulse profiles, 6x6 cascades, NRM clamping attribution, and ~70% smaller standalone Event Atlases (`nemic/experiments/constraint_pressure_v2.py`, `event_atlas_v2.py`).
- [Outage risk & NOS regime handbook v2 (Flagship Edition B)](reports/outage_risk_handbook_v2/Outage_Risk_Handbook_v2.html): Virtual Barrels institutional upgrade delivering matched-pair $/MWh spread and $/day SRA outage attribution across 697 family-directions, strictly chronological Empirical-Bayes + isotonic binding/setter outlook calibration (55/96 skilful cells, 92/96 Brier reductions, 7x-8x ECE reduction), N-1-1 concurrent-outage super-additivity (109 compounding pairs), and hierarchical corridor pooling across all 50 transmission lines including Capital-Canberra Line 6 and Dapto-Marulan Line 8 (`nemic/experiments/outage_risk_v2.py`).
- [Interconnector forecasting verdict, clustering & Project EnergyConnect v2 (Flagship Edition C)](reports/ic_forecasting_and_pec_v2/IC_Forecasting_and_PEC_v2.html): Virtual Barrels institutional upgrade documenting observed EnergyConnect (`NSW1-SA1`) commissioning limits (15,264 five-minute intervals, 31.2% VNI ring coupling), bridging observed 0/150/350/800 MW profiles into the AEMC `ERC0386` six-bucket loop settlement engine (22.9% to 58.2% PEC share, up to 85% negative net-loop reduction), auditing 66,144 PEC issue-time Predispatch/ST PASA forecasts, synthesising all 50 long-range MT PASA horizon bands (10/10 cells retain baseline) and 241 leakage-controlled clustering evaluations (0/241 Holm-significant wins), and formalising three-stack repository governance (`nemic/experiments/ic_forecasting_pec_v2.py`).
- [Valuation data request](docs/VALUATION_DATA_REQUEST.md): exact base/cap futures quote fields, coverage and acceptance checks needed for the remaining forward valuation backtest.

- [Diurnal and NOS forecasting research](docs/QNI_VNI_DIURNAL_NOS_RESEARCH.md), [implementation plan](docs/QNI_VNI_DIURNAL_NOS_IMPLEMENTATION_PLAN.md) and [VNI execution guide](docs/VNI_DIURNAL_NOS_EXECUTION.md): delivery-period models, NOS vintage replay, data-profiled chronological optimization, MAPE/MAE reporting, model explanations and trained research-bundle handoff. Generated predictions, fitted models and reports remain local and reproducible from the execution guide.

- [QNI diurnal/NOS execution guide](docs/QNI_DIURNAL_NOS_EXECUTION.md), [executed results](docs/QNI_DIURNAL_NOS_RESULTS.md), [saved-model guide](docs/QNI_SAVED_MODEL_GUIDE.md) and [published report centre](reports/qni_diurnal_nos_v2/index.html): the same v2 chronological research protocol rerun for `NSW1-QLD1`, with QNI-specific selection, NOS evidence, explanations and sixteen target Ã— lead-band bundles. Reproduce the complete resumable campaign with `python scripts/run_qni_diurnal_nos_campaign.py`.

The complete offline [HTML handbook](docs/html/index.html) includes the research, results, backtest protocol and improvement roadmap. Rebuild it with `python scripts/build_docs_html.py`. Open the downloaded file in a browser; GitHub's file view displays HTML source.

Five interactive charts cover flow improvement versus persistence, import/export limit errors, interval coverage and restriction recall/precision. `docs/chart_data.json` is an intentionally included compact aggregate-score snapshot, not the raw dataset. Its source hash and the HTML build manifest preserve provenance. The HTML embeds Plotly and works offline; the Python dashboard remains a separate application.

- [Improvement roadmap](docs/IMPROVEMENT_ROADMAP.md): prioritised extra data, candidate methods, source/access caveats and experiments to establish improvement.

- [QNI/VNI forecasting improvement research](docs/QNI_VNI_FORECAST_MODEL_IMPROVEMENT_PLAN.md) Â· [HTML edition](docs/html/qni_vni_forecast_model_improvement.html): integrates the two-year studies, a retained-data simple-model probe, academic and industry evidence, compact features, operational data requirements and a staged evaluation plan. Rebuild the report with `python scripts/build_forecast_research.py`.

- [Constraint-derived network features](docs/CONSTRAINT_NETWORK_FEATURES.md): proposed end-to-end design for compact generator influence, directional constraint pressure, limit switching and forecast-time network-state features, starting with VNI.

- [Executed VNI feasibility pilot](docs/CONSTRAINT_FEATURE_PILOT.md): guarded table-level acquisition, exact-version equation reconstruction, compact features and the corrected one-month feasibility result. Reproduce it with `python run_constraint_pilot.py`.

- [VNI generator influence study](docs/VNI_GENERATOR_INFLUENCE_STUDY.md): mechanical sensitivities, distinct contraction/reversal/forced-direction events, generator and constraint rankings, the Tumut 3 case study and a compact production feature recommendation.

- [VNI two-year constraint study](docs/VNI_TWO_YEAR_CONSTRAINT_STUDY.md): September 2024â€“August 2026 binding, near-binding, reported-setter and reconstructed-leader populations, full equation/version and factor snapshots, generator influence rankings, seasonal and diurnal analysis, and a standalone offline HTML report. Reproduce it with `python -m nemic.constraint_longitudinal run --config configs/constraint_vni_2y.json`.

- [QNI generator influence study](docs/QNI_GENERATOR_INFLUENCE_STUDY.md): rerun for `NSW1-QLD1` with all leading equations, invoked constraint sets, unit factors, event rankings, compact-feature results and a standalone offline HTML report. Reproduce it with `python run_constraint_pilot.py --config configs/constraint_qni_pilot.json`.

- [QNI two-year constraint study](docs/QNI_TWO_YEAR_CONSTRAINT_STUDY.md): September 2024â€“August 2026 binding, near-binding, reported-setter and reconstructed-leader populations, full equation/version and factor snapshots, generator influence rankings, seasonal and diurnal analysis, and a standalone offline HTML report. Reproduce it with `python -m nemic.constraint_longitudinal run --config configs/constraint_qni_2y.json`.

- [V-SA two-year constraint study](docs/VSA_TWO_YEAR_CONSTRAINT_STUDY.md): September 2024â€“August 2026 binding, near-binding, setter, reconstructed-envelope, seasonal, diurnal and generator-influence analysis for the Victoriaâ€“South Australia interconnector.

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

## Four-quarter conditional interconnector limits

The [conditional-regime campaign guide](execution/conditional_regimes_v1/README.md) documents a separate six-link analogue library: quarter/diurnal references, measurable joint grid conditions, signed limit ranges, restrictive examples and labelled extrapolation. Its portable package is [nemic-regimes](packages/nemic-regimes/README.md); execution, integration, selector/workbook and refresh runbooks live with the campaign. Run `python scripts/run_conditional_regimes.py --stage status` for artifact-backed progress. The approved [complete reference outputs](reference/conditional_regimes_v1/README.md) include the Excel workbook, all CSV exports and offline reports; full campaign data are linked from their versioned release. Working refresh folders remain ignored. This research does not activate production routes or paused schedules.

Read the [Python usage tutorial](docs/CONDITIONAL_REGIMES_PYTHON_TUTORIAL.md) for installation, supported inputs, interval queries, both directions and exports. Rebuild its offline HTML with `python scripts/build_conditional_regimes_tutorial.py` after executing the example script.
