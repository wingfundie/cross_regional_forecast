# S-1 pilot summary (VNI + Heywood)

Generated 2026-09-24 from `data/nos_regime_v1/tables/*__VIC1-NSW1|V-SA.parquet`. Log entries E024–E029.

| connector   |   relevant families |   supported families (any direction) |   median match rate (all family-directions) | placebo clean among pre-gate eligible   |   supported K1 assets |   supported K1xK2 |   supported K3 substations |   supported K4 areas |
|:------------|--------------------:|-------------------------------------:|--------------------------------------------:|:----------------------------------------|----------------------:|------------------:|---------------------------:|---------------------:|
| VNI         |                 107 |                                   26 |                                       0.859 | 0.71 (41/58)                            |                    26 |                23 |                         23 |                   11 |
| Heywood     |                  87 |                                   28 |                                       0.868 | 0.86 (50/58)                            |                    30 |                32 |                         19 |                   10 |

## Gate (PLAN §5)

| Condition | Result | Verdict |
|---|---|---|
| ≥10 supported families per connector with ≥60% match | VNI 26, Heywood 28 | **met** |
| ≥80% of primary assets resolve to K3 | 98.8% (all connectors) | **met** |
| K4 resolution rate reported | 73.9% of non-N/A primary assets | reported |

**Verdict: pilot gate met.** The user waived the pause for review (log decision E006), so the full six-connector build proceeds.

## Findings that changed the method during the pilot
- Strict matching (exact half-hour × day type × 27 weather/VRE/demand cells × exact other-family signature) matched 0–75% of units. The logged matching ladder (E026) raises the median match to about 0.85, and each unit records its rung.
- The placebo-clean share among families that pass the pre-gate thresholds is shown above. Families failing the placebo test are never "supported".
- `CA_*` constraint-automation sets and `I-*` inter-regional sets appear among the relevant families; they are kept, labelled by ID.
