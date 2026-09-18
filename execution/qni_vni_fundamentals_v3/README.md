# QNI/VNI fundamentals v3 execution

This directory owns the execution history. Large datasets, predictions and models live in `data/forecast_experiments/qni_vni_fundamentals_v3`; they are referenced, never duplicated here.

Read `methodology/methodology.md` before implementation. `ledger.sqlite` is authoritative. `STATUS.md`, `status.json`, `status.html` and `events.jsonl` are derived views. Check `handoff.md` when resuming. Do not interpret a successful process exit as completion of the campaign.

Commands (repository root): `python -m nemic.fundamentals status`, `inventory`, `acquire`, `prepare-indexes --resume`, `features --workers 2 --resume`, `train --resume`, `benchmark`, `test`, `report`, and `run --resume`. Use `--help` for bounded stage options. No process is scheduled automatically.

Post-feature connector execution is sequential: complete VNI feature reduction, training, assessment and packaging before starting QNI. Parallelism is bounded within an active connector or during the independent feature backfill; QNI and VNI model campaigns must not run concurrently.

Tracked specifications and decisions may be committed; runtime ledgers, logs and state exports are ignored. Every completed unit must have verified, hashed artifacts. New methodology changes invalidate dependent work rather than overwriting earlier evidence.
