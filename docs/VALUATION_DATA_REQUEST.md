# Valuation data request

The physical VNI/QNI forecast campaign does not depend on this request. These fields are the remaining inputs needed to turn the existing interregional valuation research into a reproducible forward market backtest.

## Required quote history

Provide timestamped Australian electricity futures quotes for NSW, Victoria, Queensland and South Australia:

- quarterly base contracts;
- quarterly $300/MWh cap contracts;
- bid, ask and settlement or last price;
- quote timestamp and timezone;
- delivery quarter;
- contract code, exchange/vendor and any rollover rule;
- trading volume and open interest where licensed and available.

Preferred coverage is one, three, six and twelve months before each delivery quarter, plus in-quarter observations, from 2023 onward. Earlier history is useful but secondary. Daily close is sufficient for the first matched backtest; intraday data are optional.

## Minimum file contract

CSV or Parquet with one row per contract snapshot:

| Field | Example |
|---|---|
| `observed_at` | `2026-09-30T16:00:00+10:00` |
| `region` | `NSW1` |
| `product` | `base` or `cap300` |
| `delivery_quarter` | `2027Q1` |
| `contract_code` | Vendor/exchange identifier |
| `bid_aud_mwh` | Numeric or blank |
| `ask_aud_mwh` | Numeric or blank |
| `settlement_aud_mwh` | Numeric or blank |
| `volume` | Numeric or blank |
| `open_interest` | Numeric or blank |
| `source` | Vendor/exchange name |

Keep the provider's raw export unchanged and include its licence or redistribution restrictions. The ingestion step will hash the raw file, preserve its timezone and map identifiers in a separate versioned adapter.

## Acceptance checks

The valuation run will reject duplicate contract timestamps, inverted bid/ask pairs, unknown delivery quarters and observations published after the valuation snapshot. Missing bid or ask remains missing; it is not replaced with settlement. Results will report quote age, spread, coverage and unmatched SRA auctions before any premium or hedge-effectiveness claim.
