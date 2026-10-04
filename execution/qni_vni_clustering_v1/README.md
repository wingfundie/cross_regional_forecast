# QNI/VNI clustering v1 execution

This directory owns the tracked specification for the isolated clustering
research campaign. Runtime data, fitted estimators, predictions, logs and the
ledger live under `data/forecast_experiments/qni_vni_clustering_v1` and remain
local.

Read `methodology.md` before changing or running the campaign. The intended
command surface is:

```text
python -m nemic.experiments.clustering inventory
python -m nemic.experiments.clustering pilot --connector VNI
python -m nemic.experiments.clustering run --connector VNI
python -m nemic.experiments.clustering run --connector QNI
python -m nemic.experiments.clustering report
python -m nemic.experiments.clustering validate
python -m nemic.experiments.clustering status
```

For an already-running VNI process, the guarded continuation helper waits for
that exact process, verifies the completed VNI all-stage summary, runs QNI, and
then rebuilds and validates the cached report:

```text
pwsh -File scripts/continue_clustering_campaign.ps1 -VniProcessId <PID>
```

VNI must complete its core stages before QNI modelling begins. The campaign is
retrospective development research and does not register models with
`nemic.production`.
