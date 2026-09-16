# VNI diurnal and NOS execution

The VNI-first v2 campaign implements the [research specification](QNI_VNI_DIURNAL_NOS_IMPLEMENTATION_PLAN.md) in a separate output directory. Historical model results are development evidence, not prospective performance. MAE is the main point-model objective; MAPE is assessment-only, and DR-NMAE is a named challenger.

## Reproduction

Use the repository Python environment and install `requirements.txt`. Configuration: `configs/experiments/vni_diurnal_nos_v2.json`. Commands below use `python -m nemic.experiments` and require `--config configs/experiments/vni_diurnal_nos_v2.json`:

| Command | Purpose |
|---|---|
| `inventory-nos` | Refresh public archive inventory |
| `recover-nos` | Recover lossless snapshot changes with bounded serial downloads |
| `audit-nos` | Measure freshness/partition coverage and historical feasibility |
| `analyse-nos-impacts` | Replay exposure and create descriptive/matched outage evidence |
| `audit-nos-feasibility` | Freeze the common-source incident cohort and paired recall-power grid before NOS HPO |
| `run-diurnal --stage primary` | Minimum directional limits, first band, T0–T6 and bounded percentage challengers |
| `run-diurnal-fixed --config configs/experiments/vni_diurnal_nos_v2_fixed.json` | Separate fixed-split primary comparison without replacing rolling lineage |
| `run-diurnal-extensions` | Remaining configured targets/bands with the primary-fold shortlist and hyperparameters frozen |
| `run-diurnal-curves` | First daily issue, full 336-step finalist curves and band/period boundary-jump audit |
| `run-diurnal-bridge` | Legacy fixed-grid candidate/blend policy on corrected observations, including the sampling bridge |
| `run-nos-models` | Matched-history O1–O4 ablations after NOS gates pass |
| `run-nos-risk` | Source-common O1–O4 contraction-risk ablations under the joint alarm budget |
| `run-diurnal-refinements` | Selection-bounded lead-pressure and 180/365-day adaptation comparisons; cross-connector pooling stays pending until QNI |
| `run-diurnal-risk` | Probability fitting, calibration and joint directional alert budgets |
| `diurnal-statistics` | Paired calendar-block model comparisons |
| `explain-diurnal` | Grouped permutation and full-predictor SHAP |
| `explain-nos` | Source-common grouped permutation and exact MW SHAP for every NOS point model |
| `refit-diurnal` | Final research bundles with exact parameters and reload checks |

Render the complete navigable report suite with `python scripts/build_vni_report_suite.py`. Start at `data/forecast_experiments/vni_diurnal_nos_v2/report/index.html`; the focused pages, full report, downloads and manifests are described in `docs/VNI_MODEL_RUN_GUIDE.md`. The report build reads cached results and does not retrain models. A report generated during execution explicitly displays pending stages; it is not a completed handoff. NOS-aware predictive fitting must not proceed merely because a preliminary exposure table exists: mapping, temporal negative controls and the pre-model analysis gate remain mandatory.

## Artifacts and information tracks

Generated artifacts live under `data/forecast_experiments/vni_diurnal_nos_v2/` and stay outside Git. Snapshot report timestamps use NEM time and a stated 30-minute availability assumption; actual historical receipt times are unverified. The snapshot archive preserves additions/removals of exact raw records and source hashes. Removed rows are not automatically interpreted as restored equipment. Invalid snapshots are rejected and reported.

Retained standing equation/constraint metadata and network features are reconstructed historical inputs. A valid NOS vintage does not make those inputs live-verified. Models using them remain research bundles. AEMO signed imports are normalized by negation, with forced-direction negatives preserved.

`diurnal/<fold>/band<band>/<target>/` contains every evaluated candidate's predictions, tuning paths, selected policy, model files and uncertainty results. `final/` contains independently refitted bundles and example feature/prediction pairs; rolling scores do not transfer automatically to those refits. `report/` contains the offline report, result table and hashed build manifest.

## Validation and completion

Run `python -m pytest -q`. Relevant new tests cover origin weighting, zero/signed metrics, frozen percentage denominators, strict label maturity, snapshot schema/clock validation, multiline record-cache parity, joint warning exposure budgets, block sampling and model reload/schema checks.

Before declaring completion, verify the full requested experiment manifest, NOS feasibility/model gates, matched controls, report explanations, statistical guardrails, final bundle parity and report visual checks. Record unavailable or inconclusive comparisons explicitly. Final publication includes source/configuration/documentation, never downloaded archives, trained binary files or local attachments. The user has authorized a pull request and merge after completion.
