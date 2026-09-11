# Corrected VNI constraint-feature pilot

Executed 11 September 2026. This is a retrospective February 2026 engineering study. It establishes that the equation reconstruction and compact feature pipeline work on the study month; it is not an untouched backtest or an operational forecast claim.

## Outcome

The corrected build joins every dispatch solution to the exact generic-constraint effective date and version published in `DISPATCHCONSTRAINT`. It uses the solved left-hand side (`LHS`) to isolate the VNI conditional bound and maps dispatch units through their actual connection points. This replaces the preliminary build, which used one late standing-data vintage for the month and omitted `LHS`; all preliminary coverage and model figures are superseded by the results below.

The corrected envelopes cover 8,063 of 8,064 five-minute intervals in each direction and reproduce the published directional limits to numerical precision. A small chronological feasibility model improved on half-hour persistence during this month, but the sample is too short and was used during development. Its result supports a longer prospective test; it does not establish production forecast improvement.

## Isolated data acquisition

The run downloads only 25 explicit table archives in the allowlist at `configs/constraint_vni_pilot.json`. It never downloads an MMS database snapshot, walks an archive directory, or queues all tables for a month.

| Measure | Result |
|---|---:|
| Study interval | 1–28 February 2026 |
| Explicit files | 25 |
| Compressed total | 274,524,060 bytes (261.8 MiB) |
| February interval files | `DISPATCHCONSTRAINT`, `DISPATCHLOAD` only |
| Earlier supplements | 15 small factor/version files from five required months |
| Retained constraint-solution rows | 1,251,774 |
| Retained dispatch rows | 1,740,672 |
| Retained DUIDs / connection points | 218 / 229 |
| Manifest cap | 1 GiB compressed |
| Per-file cap | 512 MiB compressed |
| Expanded batch cap | 20 GiB |
| Required free disk | 20 GiB |

The five supplemental vintages are October 2024, March 2025, November 2025, December 2025 and January 2026. They contain only `GENCONDATA`, `SPDCONNECTIONPOINTCONSTRAINT` and `SPDINTERCONNECTORCONSTRAINT`; the pipeline identified these months from versions actually referenced by February dispatch. It did not fetch older `DISPATCHLOAD` or `DISPATCHCONSTRAINT` archives.

The downloader rejects non-NEMWEB hosts, table/filename mismatches, duplicate URLs, files above the cap and manifests above the total cap. It streams downloads, validates ZIP integrity and expanded size, records SHA-256 hashes, reuses audited cached files and filters the two large interval tables during extraction. Source ZIPs and derived data remain under ignored `data/constraint_pilot/` storage.

## Reconstruction

For a solved generic constraint

```text
a × VNI_flow + Σ(b_i × dispatch_i) + other_terms ≤ RHS
```

the current conditional VNI bound is recovered from AEMO's solved values as

```text
bound = VNI_flow + (RHS − LHS) / a
```

and the local sensitivity of that bound to generator `i` is

```text
s_i = ∂bound/∂dispatch_i = −b_i / a
```

Positive `a` gives an upper VNI bound. Negative `a` gives a lower signed-flow bound; its reported import capacity is `−bound`. The exact effective date and version are part of every join key.

| Reconstruction audit | Result |
|---|---:|
| Five-minute rows | 8,064 |
| Equation-state rows | 1,251,626 |
| Exact target-factor/version match | 94.81% |
| Generator-pressure completeness | 94.74% |
| Upper-envelope coverage | 99.9876% |
| Lower-envelope coverage | 99.9876% |
| Upper limit reconstruction MAE | 0.0000046 MW |
| Lower capacity reconstruction MAE | 0.0000026 MW |
| Published export setter agreement | 98.83% |
| Published import setter agreement | 99.89% |
| Crossed upper/lower envelopes flagged | 48 intervals |

Fourteen of the 375 observed constraint versions have no direct VNI factor in their exact standing-data vintage. They are excluded from direct bound construction. The envelopes remain complete because other directly linked constraints set the limit in those intervals. Setter agreement below 100% is consistent with ties or near ties among constraints; the reconstructed numeric limits are the stronger validation.

## Compact features

The output uses envelope-level summaries instead of one column per generator or constraint:

- signed conditional upper and lower bounds, current room and the gap to the second constraint;
- leading constraint/version identifiers and broad limit family;
- 30-minute generator tightening and relief pressure for each direction;
- ramp- and availability-limited relief capacity;
- candidate counts, missing-pressure share and crossed-envelope flag.

The separate influence table preserves unit detail for diagnostics and for selecting a small stable generator panel. The proposed production model should use the compact aggregates plus a handful of event-proven units rather than all 185 units.

## Chronological feasibility comparison

Features are delayed by one half-hour. The first two-thirds of February train a small gradient-boosting model and the last third tests it against one-step persistence.

| Target | Test rows | Persistence MAE | Candidate MAE | Improvement |
|---|---:|---:|---:|---:|
| Export tight limit | 447 | 92.52 MW | 75.50 MW | 17.02 MW (18.40%) |
| Import tight limit | 447 | 63.16 MW | 57.02 MW | 6.13 MW (9.71%) |

This is a feasibility result from one development month. The model, feature design and period were inspected while they were built. A decision about deployment requires multiple chronological months, frozen feature selection, publication-time data controls, regime coverage and a final untouched test.

## Reproduction

Run:

```powershell
python run_constraint_pilot.py
```

The runner validates and reuses the allowlisted cache, extracts only dependency-scoped rows, rebuilds equations and features, evaluates the feasibility model, runs the influence study and executes the focused tests. See `docs/VNI_GENERATOR_INFLUENCE_STUDY.md` for the generator rankings and event analysis.
