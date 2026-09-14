# Forecast experiment campaign: running and reproducing

The completed VNI/QNI campaign contains 130 main jobs (104 numeric and 26 event jobs), followed by 520 pooled linear comparison cells. These are historical development experiments, not a promoted live forecasting system.

Published results:

- [Directional limit forecasting: performance, feature importance and examples](html/vni_qni_limit_forecast_research.html)
- [Research findings with 16 interactive charts](html/vni_qni_forecast_experiment_research.html)
- [Full Markdown results](forecast_experiment_framework_results.md)
- [Offline interactive HTML report](html/forecast_experiment_framework.html)

## Commands

Install the repository's `requirements.txt` first, then run from the repository root:

```powershell
python -m nemic.experiments plan
python -m nemic.experiments inventory
python -m nemic.experiments recover
python -m nemic.experiments run
python scripts/finish_forecast_campaign.py
python -m nemic.experiments report
python -m pytest -q
```

The completion script resumes missing main jobs, runs the AEMO and pooled comparisons, and rebuilds reports. It does not deploy models or publish to GitHub. A separate `--wait-pid` option attaches to an already running experiment process; do not launch duplicate campaigns against the same output directory.

Use `--ic VNI` or `--ic QNI`, `--fold fixed` or a rolling month such as `2026-08`, and `--kind numeric` or `--kind events` to run a subset. The configuration is `configs/experiments/vni_qni.json`. Other interconnectors require compatible retained targets, regional drivers and monthly topology study inputs before adding their configuration.

## Local input requirements and data handling

A fresh clone contains code and completed reports, not the study's downloaded data. It needs `data/processed/targets.parquet`, `ic_5min.parquet`, `drivers.parquet`, the configured monthly constraint study folders, and the configured event-atlas inputs. Optional original AEMO forecast issues reside in `results/aemo_vintages.parquet`.

`recover` uses the existing study's monthly source manifests to recover only DISPATCHLOAD for the scoped generator universe. It is not a bootstrap command for the entire MMS database. It logs URLs, hashes and filtered outputs, and deletes raw scratch archives after verification. Existing source studies are preserved. All campaigns share the 10 GB additional artifact cap and 20 GB free-disk reserve; downloads are serial and model work is bounded to two workers with two threads each.

Campaign outputs remain under `data/forecast_experiments/vni_qni_202409_202608_v1/`: source inventory, feature registry, SQLite checkpoints, trial scores, selected predictions and model bundles, download manifests, pooled scores and report build hashes. These local data and runtime artifacts are ignored by Git. The published HTML embeds comparison results and its rendering library for offline use; no external data files are needed merely to read it.

## Monitoring and recovery

`progress.json` records the latest main batch, while the ledger identifies checksum-valid completed jobs. `report_build.json` records the number included in the latest report. `continuation_status.json` describes the completion process's last recorded stage; an old stage alone does not establish whether a process is still alive. Check recent job timestamps and running processes together. Failed jobs are reported explicitly. Rerunning uses matching fingerprints and skips verified completed trials.

Changes to model code or source inputs invalidate fits. Report code can be changed and rendered without retraining. The fixed and rolling protocols overlap in evaluated observations; do not sum their scores as independent samples. Model comparisons must retain connector, protocol, target and horizon band.

## Manual shadow baseline

```powershell
python -m nemic.experiments shadow
python -m nemic.experiments score-shadow
```

The recorder retrieves one current dispatch archive, records its actual receipt time and hash, and saves an immutable persistence forecast. It does not deploy the retrospective learned models. Scoring uses only matured outcomes present in the retained target dataset; absent outcomes remain unscored. This is a manual capability, not an installed recurring service.

## Remaining scope

Individual-generator forecast integration, 100 detailed forecast-event cases per connector, verified historical publication vintages and matured live model validation remain unfinished extensions. Full generator-data recovery is complete but is not equivalent to testing those additional features. The completed campaign forecasts aggregate generator pressure and tests retrospective state/pressure features.

Publication validation: 45 tests passed; the HTML passed checks for rendering dependencies, local links and anchors. Browser policy prevented visual preview, so visual verification remains outstanding.
