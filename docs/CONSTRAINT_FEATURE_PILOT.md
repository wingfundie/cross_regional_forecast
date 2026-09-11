# VNI constraint-feature feasibility pilot

Executed 11 September 2026. This is a one-month retrospective engineering pilot, not an untouched backtest or an operational forecast result.

## Outcome

The pilot implemented guarded acquisition, version-aware factor joins, dispatch filtering, equation isolation, compact five-minute and half-hour features, generator discovery, a chronological feasibility comparison and numerical/download-policy tests.

The result does **not** yet support promoting the features into the main forecast. Complete directional-envelope coverage was about 28–29%, and the small matched-sample model performed substantially worse than persistence. The comparison spans only February 2026 and includes a sharp coverage/regime split, so it is evidence that the present feature/data construction is not ready rather than a reliable estimate of its eventual forecast value.

## Download isolation

The run used ten explicit table-level archives from February 2026. It did not download an MMS database snapshot or recursively queue an archive listing.

| Measure | Result |
|---|---:|
| Compressed files | 257.2 MiB |
| Pilot cap | 1 GiB |
| Large interval products | `DISPATCHCONSTRAINT`, `DISPATCHLOAD` |
| Retained constraint rows | 165,461 of the 1,010 VNI-linked IDs |
| Retained dispatch rows | 1,651,968 for 207 mapped DUIDs |

The tracked configuration contains the only permitted URLs. The downloader rejects non-NEMWEB URLs, product/filename mismatches, duplicates, files above 512 MiB and manifests above 1 GiB. It streams downloads, checks compressed and expanded sizes, verifies ZIP integrity, reuses checksum-audited cached files and never converts directory listings into an implicit queue.

Filtering occurs while the two large tables are parsed. Unrelated dispatch records are not written to the pilot tables. Raw source ZIPs and derived Parquet files remain under ignored `data/constraint_pilot/` storage.

## Reconstruction and features

The implementation converts generator coefficients into target-IC sensitivities, adds other-interconnector LHS contributions and excludes equations with unresolved energy connection points or regional terms. This intentionally conservative completeness rule prevents partial equations from being presented as secure bounds.

The monthly standing-data archive was generated after the pilot month and contains later `LASTCHANGED` values. It is therefore suitable for this retrospective mapping exercise but is not treated as proof that the same mapping vintage was available at each February origin.

| Audit | Result |
|---|---:|
| VNI-linked constraint IDs in the monthly factor set | 1,010 |
| Mapped dispatch units | 207 |
| Unmapped connection points | 3 |
| Equation-state rows | 165,442 |
| Complete equation rows | 17.4% |
| Upper-envelope five-minute coverage | 28.2% |
| Lower-envelope five-minute coverage | 28.9% |
| Inconsistent trusted envelopes | 0 |

The compact output includes signed upper/lower bounds, rooms, switching gaps, tightening and relief, available-relief proxies, pressure changes, leading families, candidate counts, partial-candidate fraction and provenance IDs. Generator persistence produces explicit zero scenario-envelope movement fields.

Tumut 3 was found in 627 VNI-linked equation IDs in this monthly factor set, with both positive and negative coefficients across regimes. Its February dispatch was zero in most intervals, so a median-movement ranking would incorrectly assign no importance. The implemented discovery score uses mean absolute 30-minute movement and retains its equation-level coefficient evidence.

## Feasibility comparison

The comparison predicts the next half-hour tight directional limit from a one-interval delayed feature snapshot. It trains on the first two-thirds of the feature-covered time span and tests on the remainder. It is deliberately labelled retrospective and uses a small matched population.

| Target | Coverage | Persistence MAE | Candidate MAE | Relative change |
|---|---:|---:|---:|---:|
| Export tight limit | 29.5% | 95.8 MW | 178.8 MW | 86.6% worse |
| Import tight limit | 29.5% | 60.9 MW | 121.3 MW | 99.0% worse |

Feature coverage is concentrated on 1–3 February and 24–28 February, so the train/test comparison crosses a marked network-regime change. These results must not be extrapolated to the full historical period or all interconnectors.

## Reproduction and next gate

Run:

```powershell
python run_constraint_pilot.py
```

The next defensible step is to improve complete equation coverage without weakening the completeness rule. Audit the three unmapped connection points and determine the missing regional-service quantities. Then create a new explicit, size-audited manifest for a longer chronological sample. Do not start a multi-year `DISPATCHLOAD` or `DISPATCHCONSTRAINT` backfill automatically: those two products alone are about 269 MB compressed for this single month and would exceed the pilot guard at scale.

Only after coverage is adequate should the project run the planned E0–E5 ablations and prospective shadow evaluation.
