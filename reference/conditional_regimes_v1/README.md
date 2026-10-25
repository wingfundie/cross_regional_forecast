# Four-quarter conditional limits: complete reference outputs

This is the approved 25 October 2026 reference snapshot for QNI, Directlink, VNI, Heywood, Murraylink and Basslink, both directions. The data cutoff is 2026-10-25 00:00 fixed NEM time. The inference bundle identity is `conditional-regimes-v1-b3352cb955ecbeb0`.

## Excel and CSVs

- [Complete Excel workbook](research/downloads/conditional_limits.xlsx): all seven sheets, including quarterly references, named conditions, the selected profile and validation/evidence notes.
- [Complete quarterly and conditional catalogue](research/downloads/quarterly_catalogue.csv): 33,825 cells; 14,184 meet the declared support convention.
- [Final assessed scorecards](research/downloads/scores.csv), [method gates](research/downloads/method_gates.csv), [paired comparisons](research/downloads/paired_comparisons.csv) and [method availability](research/downloads/evaluation_availability.csv).
- [Selected 48-interval profile](research/downloads/example_profile.csv) and [evidence-rich JSON](research/downloads/example_profile.json).
- [All campaign CSV exports](campaign_tables/), including retained preliminary and assessed score tables. The `assessed_*` files and the research report's download aliases are the final assessment; unprefixed preliminary score/gate files are retained for traceability.
- [Tutorial CSV/JSON outputs](tutorial_examples/), including both directions, varying conditions, method comparisons and full profiles.

For one download containing every CSV export, use the [all-CSV ZIP](https://github.com/wingfundie/cross_regional_forecast/releases/download/conditional-regimes-v1-20261025/conditional-regimes-all-csv-20261025.zip). The release also provides the complete workbook as a direct download.

## Reports and Python

- [Research centre](research/index.html) with all three substantive reports and Markdown companions.
- [Python tutorial](tutorial/index.html) with runnable examples and actual outputs.
- [Portable inference bundle](research/downloads/nemic_regimes_bundle_v1.zip) and [installable wheel](research/downloads/nemic_regimes-0.1.0-py3-none-any.whl).

Download the reference files and open the HTML locally for the rendered offline reports. GitHub's file view may display HTML as source. Relative report/download links remain intact.

## Full campaign data

The [versioned data release](https://github.com/wingfundie/cross_regional_forecast/releases/tag/conditional-regimes-v1-20261025) contains:

- [Campaign data archive](https://github.com/wingfundie/cross_regional_forecast/releases/download/conditional-regimes-v1-20261025/conditional-regimes-campaign-data-20261025.zip): full prepared/inference panels, predictions, fold outputs, models, tuning, raw acquired archives, parsed extensions, weather and evidence/provenance records.
- [Retained input archive](https://github.com/wingfundie/cross_regional_forecast/releases/download/conditional-regimes-v1-20261025/conditional-regimes-retained-inputs-20261025.zip): original target/driver/native observations and the reused NOS/constraint/generator input tables required by this campaign.

Extract both archives at the repository root. Their entries retain their original `data/` and `results/` paths. Each archive contains `DATA_MANIFEST.json` with per-file SHA-256 values. The [dataset manifest](dataset_manifest.json) records every committed reference file, archive contents, sizes and archive hashes.

The archives contain the retained data for this campaign and its declared dependencies. Unrelated project data, credentials, Python environments, operational logs, process-ownership records and temporary publishing/install caches are excluded. The very large workbook-authoring inspection trace is a debug artifact; the complete workbook and exported research evidence are provided.

## Interpretation

These are conditional estimates of AEMO-reported dispatch limits, not maximum secure physical transfer capability. Negative values are preserved. Current structural eras have incomplete seasonal history; no challenger passed every historical calibration/risk gate, and measured-receipt historical as-of evaluation has zero eligible rows. See the reports and runbooks for support, sparse cases and permitted uses.
