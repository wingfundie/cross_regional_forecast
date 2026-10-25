# Four-quarter conditional interconnector limits

The campaign implements the agreed conditional analogue library for QNI, Directlink, VNI, Heywood, Murraylink and Basslink. It retains half-hour average reported limits as the main target, tight five-minute minima as a risk measure, and calendar-quarter conditioning.

Read [METHODOLOGY.md](METHODOLOGY.md) before fitting or changing definitions. Run from the repository root:

```text
python scripts/run_conditional_regimes.py --stage status
python scripts/run_conditional_regimes.py --stage all --resume
```

The local ledger and runtime artifacts are under `data/forecast_experiments/conditional_regimes_v1`. Model and source coverage claims belong to the generated reports and ledger, not this entrypoint. Read the four runbooks for the supported operations:

- [Research and recovery](RUNBOOK_RESEARCH.md)
- [Python integration](RUNBOOK_PYTHON.md)
- [Selector and workbook](RUNBOOK_SELECTOR.md)
- [Refresh and validation](RUNBOOK_REFRESH.md)

Reports are generated under `reports/conditional_regimes_v1`. The inference package lives under `packages/nemic-regimes`; its versioned bundle is separate from the wheel. No existing production route or paused schedule is changed.

For installation, required local artifacts, report/workbook rebuilds and the publication boundary, see [the development and handoff guide](../../docs/CONDITIONAL_REGIMES_DEVELOPMENT.md). The [Python tutorial](../../docs/CONDITIONAL_REGIMES_PYTHON_TUTORIAL.md) covers interval selection, directional inputs and exports. The [compact research snapshot](../../docs/data/conditional_regimes_research_snapshot.json) records the completed local run's identities and limitations without distributing observations or fitted models.
