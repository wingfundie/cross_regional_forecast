# NEM coal research files

## Start here

**nem_coal_prices_reviewed.csv** is the regenerated 16-row station assumptions file. `BASE_AUD_GJ`, `LOW_AUD_GJ` and `HIGH_AUD_GJ` are the reviewed modelling inputs in real June-2025 A$/GJ. Original screenshot values are preserved in separate columns. Only Mt Piper's central estimate changes, from 5.00 to 7.50; other central values remain provisional and most uncertainty ranges widen.

The populated prices are **analyst assumptions, not verified current invoices**. The detailed notes identify whether a value is retained, supplier-proxied or supported by a historical partial-cost crosscheck. `CURRENT_PUBLIC_STATION_PRICE_AUD_GJ` is blank throughout because a complete current station price was not established. The evidence cutoff is 15 September 2026; actual source periods differ.

## Files

| File | Contents |
|---|---|
| nem_coal_prices_reviewed.csv | 16 station rows, original and reviewed prices, confidence, inline URLs and decision notes |
| nem_coal_export_blends.csv | 17 component/regime rows separating supply shares, contract indexation and export diversion |
| coal_source_register.csv | 47 source entries, exact URLs, dates, locations, claims, limitations and access status |
| coal_calculations.csv | 13 reproducible calculations, units and explicit conversion assumptions |
| coal_price_research_report.md | Detailed methodology, one-by-one station review and numbered source inventory |

The ZIP contains these five files and this README. It does not include downloaded source documents, scripts or temporary files.

## Import rules

- CSV files use UTF-8 with BOM for Excel compatibility. Quoted commas are standard CSV, not extra columns.
- Blank means unknown or not applicable. **Do not replace blank export weights or closed-station prices with zero.**
- Numeric fractions such as 0.50 represent 50%. Source IDs separated by semicolons refer to the source register.
- `ORIGINAL_GROSS_BETA_REFERENCE` is archival only. None of those nonzero values has been verified as a current station export weight.
- Zero values in `RECOMMENDED_NEAR_TERM_EXPORT_WEIGHT` are explicitly labelled model assumptions or conditional contract scenarios. They are not measured statistical sensitivities.
- Vales Point's 50/50 component split is approximate tonnes, not verified energy weights. Its component price fields remain blank.
- Eraring's 75–85% coverage is a forward contract/hedge/stock measure as disclosed in April 2026. Its 15–25% complement is not an export blend.
- `HISTORICAL_OR_PROXY_ANCHOR_AUD_GJ` is a diagnostic value. It is not a current observed price and does not necessarily share the full cost scope of `BASE_AUD_GJ`.
- Range limits are analyst stress scenarios, not probabilistic intervals or sourced contract bounds.
- `ACTIVE_ASSET_NOT_LIVE_AVAILABILITY` identifies operating assets, not live unit availability. Liddell is inactive and excluded.

## Scope of reconstruction

The input was two screenshots, not the original CSV/workbook. Visible price values and station rows were transcribed. The new schema preserves the main price fields and adds audit fields; it does not claim to reproduce hidden columns, truncated headings, formulas or original internal references. Do not treat this as an automatically compatible replacement for an unseen model schema.

All sources are public. Some primary documents were available through indexed text only; certain court materials through reproductions. Access limitations and stale evidence are marked. The original screenshot's internal report references were unavailable and were not treated as independent public evidence.

## Validation

Checked all 16 station rows for uniqueness and low ≤ base ≤ high; confirmed blank closed-asset prices, complete source-ID references, valid fractional shares, the approximate Vales Point component sum, and successful parsing of all four CSVs. These checks validate the files' structure and calculations; they do not turn estimates into verified contract prices.
