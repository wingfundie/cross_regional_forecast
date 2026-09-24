# Results summary — NOS constraint mechanics and outlook (v1)

**Status:** Phase A complete (limit-setter layer, Release 1). Phase B (published binding), Phase D (outlook and backtest) and Phase C (full report) in progress. The execution log is authoritative.

## Phase A — limit-setters during outages

Gates: the matched-pair replay reproduces v1 exactly on all six links (405,120 outage half-hours; 0 mismatches). Reconstructed limit-setter counts reproduce v1's leading-interval counts exactly (2,159 family-connector checks).

| Link | Supported family-directions | Median own-set setting share while invoked | Matched normal | Own set dominant (≥50%) | Placebo clean |
|---|---|---|---|---|---|
| QNI | 37 | 2.9% | 0.0% | 5% | 95% |
| Directlink | 27 | 0.4% | 0.0% | 0% | 100% |
| VNI | 41 | 20.2% | 0.0% | 15% | 96% |
| Heywood | 50 | 3.8% | 0.0% | 18% | 99% |
| Murraylink | 67 | 4.0% | 0.0% | 10% | 97% |
| Basslink | 18 | 5.8% | 0.0% | 11% | 100% |

Largest own-set setting shares (supported):

| Link | Direction | Family | Own set sets the limit (95% CI) | Normal |
|---|---|---|---|---|
| Basslink | reverse | Q-X_BRHA_TWO | 90% (75%–100%) | 0% |
| VNI | forward | N-DTKV_18_WG_CLOSE | 78% (57%–89%) | 0% |
| Heywood | forward | V-HYMO | 76% (40%–98%) | 2% |
| Heywood | reverse | V-HYMO | 76% (42%–98%) | 1% |
| Heywood | forward | V-CRML | 74% (49%–87%) | 4% |
| VNI | reverse | N-DTKV_18_WG_CLOSE | 73% (46%–90%) | 0% |
| QNI | reverse | N-ARSR_8E | 71% (59%–78%) | 3% |
| Murraylink | forward | V-ARCW | 71% (60%–78%) | 0% |

Reading: in most supported family-directions the outage's own equations set the limit only occasionally; the outage usually acts by tightening a system-normal equation that stays in charge. A minority of families (mostly QNI and VNI line outages) take over the envelope.

Correction: v1's `leader_changed_share` was misaligned (every treated half-hour paired with one pre-run value); both reports now use the per-run alignment.

Report: `reports/nos_outage_regime_research_20260924/index.html#constraints`.
