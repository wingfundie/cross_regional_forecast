# Conditional regimes: development and handoff

This is the source and documentation for the four-quarter conditional reported-limit workflow, its `nemic-regimes` package, local selector, exported workbook and offline research reports. Read the [Python tutorial](CONDITIONAL_REGIMES_PYTHON_TUTORIAL.md) for ordinary use and the [campaign guide](../execution/conditional_regimes_v1/README.md) for the research stages.

## Install and run

For package-only integration, install `python -m pip install ./packages/nemic-regimes`. Add `[models,collect]` to that path if you need fitted challengers and public input collection. Saved-model dependencies are pinned by the model extra; `packages/nemic-regimes/requirements-bundle-v1.txt` records the full research runtime. Load a separately supplied extracted bundle with `nemic_regimes.load_bundle`.

For acquisition, fitting and report development, use `python -m pip install -r requirements-conditional-regimes.txt` from the repository root. Python owns the selection calculations. `nemic.experiments.conditional_regimes` owns campaign acquisition, preparation, chronological evaluation, checkpoints and cached presentation. This does not alter saved QNI/VNI model contracts or `nemic.production` routes.

```text
python scripts/run_conditional_regimes.py --stage status
python scripts/serve_conditional_selector.py --bundle path/to/bundle --port 8061
```

The selector binds to localhost. Page loads and selection requests use the loaded bundle. The grid/weather buttons make explicit public-provider requests and save their receipts. Loading a bundle or clicking Calculate does not fetch new conditions. Collection is on demand; no schedule is added.

## Required artifacts and Git boundary

A clone contains the engine, campaign configuration, event catalogue, methodology, tests, four runbooks, report/workbook generators, integration examples and tutorial source. The compact [research snapshot](data/conditional_regimes_research_snapshot.json) identifies the completed local evidence and its limitations.

It does not contain downloaded NEMWEB/weather observations, extracted Parquet tables, fitted models, prediction rows, full inference bundles, built wheels, XLSX files, generated HTML, tutorial/handoff ZIPs, screenshots, runtime ledgers or environment directories. Those stay ignored and local. A source checkout alone therefore cannot reproduce an old result by inventing substitute data. Supply the identified bundle for inference, or audit retained inputs and execute the campaign to construct a new version.

The research stack reuses the retained original-system and NOS standing/dispatch/outage histories listed by the inventory stage. Their paths and hashes are recorded locally. Inspect coverage and the ledger before acquiring additional files; this is not a promise that a fresh clone contains the retained history. Measured historical receipt evidence remains absent for the complete as-of replay contract.

## Rebuild reports and the tutorial

Once the required cached campaign outputs are present:

```text
python scripts/run_conditional_regimes.py --stage report
python scripts/run_conditional_regimes.py --stage validate
```

The report stage reads cached results rather than fitting again. It generates `data/forecast_experiments/conditional_regimes_v1/workbook_payload.json`. The workbook builder is `scripts/build_conditional_regime_workbook.mjs`, accepting the payload path and output XLSX path. It requires a Node environment with `@oai/artifact-tool`; the original export used the bundled document-authoring runtime. Browser QA scripts additionally require Playwright and its Chromium installation. These authoring dependencies are separate from the portable Python inference package. Rebuild reports after the XLSX export so the downloadable workbook and its hash are current.

The tutorial generator also reads cached executed examples. Its source is `docs/CONDITIONAL_REGIMES_PYTHON_TUTORIAL.md`; the example imports only the installed package:

```text
python -m pip install "./packages/nemic-regimes[models]"
python packages/nemic-regimes/examples/tutorial.py --bundle path/to/bundle --output data/forecast_experiments/conditional_regimes_tutorial/example_outputs --models
python scripts/build_conditional_regimes_tutorial.py
```

The generator copies the locally built wheel and versioned bundle into the ignored tutorial downloads directory. It expects the completed campaign's bundle ZIP and wheel at the paths in the source; build/supply those before rendering. The generated HTML embeds its chart and style and works offline. Source citations and user-triggered collectors still need internet.

## Validation and interpretation

```text
python -m pytest -q tests/test_conditional_regimes.py
python -m pytest -q
```

Campaign validation additionally checks native target signs/completeness, fold signatures and incident separation, source and bundle hashes, offline report links, workbook/Python value reconciliation, installation receipts and visual QA. These artifact checks require the corresponding local files; they are not replaced by synthetic test fixtures.

The repository's existing `test_research.py` integration tests also require local `data/processed/drivers.parquet`, `targets.parquet`, `ic_5min.parquet` and `results/seasonal_references.csv`. Keep these ignored. The valuation evidence tests can skip when their optional local evidence/Node tooling is absent. The new conditional-regime tests use synthetic fixtures and do not require the full retained campaign history.

The completed local study has 132 chronological connector-direction folds and no challenger passing every declared calibration/risk gate. Its as-of scorecard has zero eligible historical rows. New PEC and regulated-Basslink eras lack complete seasonal history. The package supports conditional historical scenario research and separately labelled exploratory extrapolation; it is not a deployed forecast service or a physical transfer-capability calculator.
