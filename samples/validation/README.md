# Synthetic portfolio validation pack

**Real security identifiers; entirely synthetic financial data.** Symbols and security names are matched against Nasdaq's public symbol directory (file creation stamp `1009202621:32`, retrieved 2026-10-10). Quantities, cost bases, prices, portfolio ownership, dates/scenarios, and sector groupings are test inputs, not quotes, holdings recommendations, official classifications, or historical returns. No personal holdings are included.

Source: https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt
Directory explanation: https://www.nasdaqtrader.com/trader.aspx?id=symbollookup
The source SHA-256 and deterministic generation seed are recorded in `expected_results.json`. Only selected identifiers/names are carried into fixtures; raw source data is not required to use them.

## Start here

Upload **`valid/real_symbols_100.csv`** and click **Import uploaded CSV**. It pre-fills the target portfolio and date. It contains 85 stocks and 15 ETFs, including AAPL, MSFT, NVDA, AMZN, JPM, XOM, SPY, VTI, and QQQ. Stocks span all 11 broad equity sectors; fund classifications describe the entered fund, not underlying holdings.

Expected dashboard (100 holdings):

| Metric | Expected display |
| --- | ---: |
| Cost basis | $16,233,618.53 |
| Market value | $16,368,367.89 |
| Unrealized gain | $134,749.36 |
| Gain percentage | 0.83% |

Large position sizes are intentional test inputs. Price ranges are arbitrary and need not resemble the actual price of a named security.

## Files and exercises

| File/group | Rows per file | What to validate |
| --- | ---: | --- |
| `valid/real_symbols_100.csv` | 100 | Mixed stocks/ETFs, fractional shares, positive/negative/zero gains, sector filters |
| `valid/template_style_100.csv` | 100 | Same holdings without metadata; enter target name/date yourself |
| `valid/real_symbols_1000.csv` | 1,000 | Many real stock identifiers; sorting, filtering, imports and exports. Unclassified sectors are `Unknown` |
| `snapshots/mixed_100_*.csv` | 100 × 12 files | Save separate dates from November 2025 to October 2026 under one portfolio, then reopen older dates and replace a date |
| `valid/precision_and_zero_basis.csv` | 5 | Eight decimal places, zero cost basis, zero price, tiny fractions, blank optional fields |
| `valid/zero_market_value.csv` | 10 | All prices zero; allocation charts omitted and losses retained |
| `valid/bom_and_ignored_column.csv` | 5 | UTF-8 BOM and visible ignored-column warning |
| `stress/fictional_10000.csv` | 10,000 | Exact accepted row limit; **fictional TEST identifiers**, not real securities |
| `invalid/too_many_rows_10001.csv` | 10,001 | Reject exceeding the row limit; fictional identifiers |
| Other `invalid/*.csv` | 1–5 | Each isolates a validation failure, listed below |

The 12 dated files are simulated scenarios with fixed quantities/costs and generated price changes. They are **not historical market data**. Import and save one at a time; v1 analyzes one snapshot at a time.

The 10,000-row case verifies the parser/storage limit, not an interactive performance guarantee. Start with 100 or 1,000 rows; charts showing thousands of categories can be slow and crowded.

## Intentional invalid files

**Editable row errors** (normally CSV row 3): `negative_quantity`, `zero_quantity`, `nonfinite_price`, `currency_in_cost`, `too_many_decimals`, `duplicate_symbol`. The app should retain editable rows, identify affected columns, and block the whole analysis/save until corrected. Duplicate symbols collide after trimming and uppercasing.

**Structural errors requiring a corrected upload:** `too_many_rows_10001`, `analysis_report`, `conflicting_metadata`, `duplicate_headers`, `missing_column`, `malformed_quotes`. `analysis_report.csv` deliberately has an analysis marker; it is not a valid snapshot input.

## Suggested walkthrough

1. Import the 100-holding file and compare the four totals above.
2. Filter by a stock and then a sector; confirm the intersection drives every analysis view.
3. Download the report and complete snapshot. The report should be filtered; complete export should retain all 100 holdings.
4. Save several dated snapshots; restart the app and open the latest/older dates. Re-import a saved date and exercise replacement cancel/confirm.
5. Edit quantity, price, and total cost basis; add/delete a row. Test an invalid file and repair its affected cell.
6. Exercise zero-value/precision cases, then increase to 1,000 rows. Use the fictional limit files only for stress testing.

`expected_results.json` records exact Decimal totals, row counts, descriptions, and expected validation outcomes for every file. These totals were calculated independently of the app's analysis function, then compared against it.

## Verification performed

All 31 CSVs matched their expected outcome: **19 valid, 6 editable row errors, 6 structural errors**. Each valid file passed exact totals and CSV → temporary SQLite → CSV normalized holdings/metadata round trips, including all 10,000 stress rows. No real database was opened. These checks validate the files and data pipeline; this new large-data pack has not been separately benchmarked in the browser.
