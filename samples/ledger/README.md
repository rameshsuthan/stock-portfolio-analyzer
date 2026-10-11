# Synthetic ledger acceptance inputs

All prices, quantities, dates, names and basis amounts here are synthetic. Public security symbols in the large files do not make these market data.

Create **Synthetic A** and **Synthetic B** as full-history accounts. Import `linked_accounts.csv` using Multiple accounts; then import `prices.csv`. As of 2025-01-07:

- A: 4.8 ABC shares, basis 291, market value 384, realized gain 542, recorded dividends 50.
- B: 1 ABC share, basis 60.5, market value 80, realized gain 19.5, dividends 0.

`expected_results.json` contains hand-calculated expectations. The first sale consumes basis 1010 + 242, with net proceeds 1794. After the split, transferring two shares moves basis 121; the destination's one-share sale consumes 60.5.

For uncertainty, create a separate opening account with cutoff 2025-01-01, import `unknown_opening.csv`, then `unknown_sale.csv`. Remaining quantity is 6; basis and sale gain are unknown. In Lots, allocate four shares from its pool with supplied basis 400: remaining basis becomes 600 and sale gain 200.

`repeated_trades.csv` requires explicit keep/skip decisions for both occurrences. Keep both; `overlapping_trade.csv` then requires another decision. Never infer duplicate removal from equal economics.

`holdings_100.csv` creates 100 positions, total basis 10,000. `events_10000.csv` creates 10,000 events across 100 symbols, total quantity 10,000 and basis 1,000,000. Import each into a separate empty account. Their prices are trade executions; valuation requires independent observations.

`broker_match_a.csv` and `broker_mismatch_a.csv` apply to the unmodified linked-account example at 2025-01-07. The mismatch has basis 300 rather than 291. The `invalid/` files exercise structural, precision, unsupported-event and chronological errors; see exact expected issue codes in the JSON.
