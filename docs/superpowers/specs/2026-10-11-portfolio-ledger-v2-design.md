# Portfolio Ledger V2 — Design for Implementation Review

**Date:** 2026-10-11
**Status:** Interview decisions confirmed; design and implementation handoff prepared for the owner's review. No V2 implementation is authorized by this document alone.
**Baseline:** `feature/portfolio-v1` at `35662c6`; 58 tests and Ruff lint pass. The repository's `main` branch contains planning scaffolding, not the implemented application. V2 must branch from the implementation branch, not `main`.
**Plan:** [Implementation plan](../plans/2026-10-11-portfolio-ledger-v2.md)

## 1. Purpose and confirmed decisions

Build a local personal portfolio manager that explains quantities, remaining cost basis, and gains and can compare them with brokerage records. The owner selected:

- Generic CSV contracts first; no broker-specific connectors or import adapters in this release.
- Retain Streamlit and polish navigation, tables, import previews, and reconciliation.
- Keep editable snapshot mode alongside transaction accounts, with clear separation and shared analysis.
- Start accounts either from complete history or from opening holdings/lots; records vary by account.
- FIFO by default; allow explicit lot selection to reproduce a broker's allocations.
- Include BUY/SELL, trade fees, cash dividends, reinvestment, splits, and transfers between tracked accounts.
- When opening quantity and total basis are known but lots are missing, track quantities and leave affected basis/gains unresolved until supported by lot detail or an explicit sale-basis amount. Never estimate silently.

Success means independently reproducible calculations, repeatable imports without accidental duplication, explainable differences from broker statements, and recovery from bad edits. This is a personal tracking and reconciliation application, not a tax filing system. In particular, FIFO may differ from actual broker allocations and tax adjustments.

## 2. Boundaries

Continue local, single-user, long USD stocks/ETFs and fractional shares. Retain Python 3.14.*, Streamlit, pandas, Plotly, SQLite, uv, pytest, Ruff. No separate frontend, API server, ORM, database service, cloud upload, brokerage login, telemetry, or in-app AI.

Do not add live prices, aggregate multi-account dashboards, cash balances, deposits/withdrawals, investment return rates, benchmarks, rebalancing, tax forms, wash-sale automation, interest, options, shorts, FX, mergers/spinoffs, return-of-capital adjustments, or automatic fractional-share cash-in-lieu. Unsupported activity is rejected or explicitly reported as requiring an external adjustment; it must not be silently dropped. A basis discrepancy is reported, never automatically forced to match.

Dividends are recorded cash distributions as supplied, not a taxable-income determination. Transfers cover only two tracked accounts with the same owner and currency; external incoming positions use opening records. No taxable disposal or income is created by an internal transfer.

Use only synthetic inputs and temporary databases in development, tests, screenshots, browser work, and reviews. Private data directories, exports, backups, credentials, and raw uploads stay out of Git.

## 3. Sources of truth and coexistence

There are two explicit modes:

1. **Snapshots:** existing named portfolios, dated editable holdings, save/replacement semantics, template, and exact input round trips remain supported.
2. **Transaction accounts:** immutable event identities with revision history are authoritative. Holdings/lots/gains are derived by deterministic replay; they are not editable holdings rows. Prices are independent dated observations.

A snapshot is not an account or a transaction. Never automatically convert every historical snapshot into purchases. An explicit "Start account from snapshot" action creates a new transaction account with one aggregate opening record per symbol, cutoff equal to the selected snapshot date, and optional price observations on that date. It previews records before confirmation and leaves the source snapshot intact. No purchases or acquisition dates are fabricated.

An account starts in `full_history` or `opening` mode. An opening account has one end-of-day cutoff; its opening records describe positions at that cutoff. Later activity must have dates strictly after it. Earlier/equal-date transactions are rejected rather than double counted. Detailed opening lots require actual acquisition dates no later than cutoff. Aggregate opening records have no acquisition dates. Use one representation per account/symbol: detailed lots or one aggregate opening balance, never both. A reviewed atomic replacement can exchange aggregate openings for detailed lots with the same total quantity and basis and replay all later activity.

## 4. Domain and calculation rules

### Identity, ordering, and precision

- Account identity is an internal UUID; display name is trimmed and Unicode-casefold unique among accounts. Optional brokerage label is informational, not an account number. Snapshot names and account names have separate namespaces.
- Security identity in this release is normalized uppercase symbol; do not claim to handle ticker changes or shared identifiers across listings.
- Event identity is a stable UUID. Revisions change payload/status, not identity. Opening lots and buy events produce stable lot IDs; transfer-created lot IDs are deterministically derived from transfer ID and source lot ID.
- Order active events by `(effective_date, day_sequence)`. `day_sequence` is a positive integer unique across active events on that date throughout the ledger, including transfers. This supplies explicit same-day ordering without inventing trade times. Preview source-file order when sequence is absent, append to that day's existing sequence, and let the owner revise it before commit. Reordering must replay dependent events; never fall back to alphabetic symbol or random-ID ordering.
- All monetary/share calculations use Decimal precision 50, never binary floats. Inputs retain existing plain-decimal limits: at most 18 significant digits and 8 decimal places. Quantities are positive except reconciliation holdings may be zero; prices and fees are nonnegative. Dates are strict `YYYY-MM-DD`. Reject future-dated economic events/opening cutoffs relative to the local date, and unsupported currency. Derived values may have more decimal places and bypass input validators; float copies exist only for presentation.
- Allocate lot basis proportionally at precision 50, carrying any remainder to the final disposal of that lot. Similarly allocate a sale's total fee across its matched quantities and carry remainder to the final match. Preserve conservation; never repeatedly round lots to cents.

### Trades and lot allocation

BUY opens a lot: quantity `q`, basis `q * price + fees`, acquisition date equal to trade date. SELL reduces holdings: net proceeds `q * price - fees`; realized gain is net proceeds minus disposed basis. Fees may exceed proceeds; preserve the resulting loss. Reject oversells against the chronology, not just the current ending balance.

FIFO consumes oldest acquisition dates first, then original acquisition order and lot ID as a deterministic tie breaker. Aggregate opening pools precede post-cutoff purchases but have unknown internal lot composition. Explicit allocation must fully cover a sale, use available lots for the same account/symbol at that moment, and never oversubscribe. A partial explicit allocation is an error; do not silently fill its remainder with FIFO. Display the method and consumed lots for each sale. A sale with explicit allocation is identified as such even in a FIFO-default account.

A purchase-lot fee is already part of basis; do not deduct it a second time at sale. Closed holdings disappear from current positions but remain in the transaction and realized-gain views. Full liquidation is a valid account state.

### Aggregate opening uncertainty

An untouched aggregate opening balance has known quantity and total basis, but unknown acquisition lots. A partial sale has known proceeds and quantity but no assigned basis unless the owner supplies an explicit basis amount for that pool consumption. Do not divide pooled basis by shares as an estimate.

Track pool quantity, original supplied basis, resolved consumed basis, and unresolved consumption records. While unresolved consumption remains, the pool's remaining basis is unknown. This affects only dependent positions/sales, not unrelated symbols. Known post-cutoff lot slices in the same sale remain visible but its total realized gain is unresolved. Fully consuming a pool with known remaining total basis resolves that consumption exactly; earlier unresolved sale allocations stay unresolved until supplied. A depleted pool has zero remaining quantity and basis, even if historical sale gains remain unresolved.

Explicit amounts for aggregate consumptions must be nonnegative; known allocations must not exceed the pool's original total basis. When every share is consumed, assigned amounts must sum to that basis. Completing missing amounts or replacing the opening pool with detailed lots replays dependent history and exposes incompatible prior manual allocations as blocking errors. Manual basis is labeled "User supplied", not broker-verified or tax-adjusted.

Transfer/split events carry uncertainty with the affected quantity. A partial transfer from an aggregate pool requires a supplied transferred-basis amount to preserve known basis on each side; without it both affected pools are unresolved. A complete transfer with known pool basis preserves that known basis. Resolution propagates along linked transfer descendants.

### Other events

- **DIVIDEND:** record `amount` of cash distribution received and its date/symbol; quantity and price are absent. Show separately from gains. It does not reduce holding basis.
- **Reinvestment:** a linked DIVIDEND and BUY, committed/revised/voided atomically. The BUY references the dividend event; accounts, symbol, and date match, with the dividend sequenced before its buy. `quantity * price + fees <= dividend amount`. Show uninvested remainder, but do not claim to track a cash balance. The new buy opens a normal lot. Imported unlinked BUY/DIVIDEND rows remain distinct until explicitly linked; no proximity-based guessing.
- **SPLIT:** positive integer numerator and denominator, effective before/after trades according to day sequence; multiply every open lot/pool quantity by the ratio, preserve total basis and acquisition dates. If any resulting quantity cannot be represented exactly with at most 8 fractional digits, reject with a cash-in-lieu/rounding explanation rather than invent settlement. Zero/negative ratios or no held shares are errors.
- **TRANSFER:** one event references source and destination accounts, quantity, symbol, and FIFO or explicit source-lot allocation. Move lot slices atomically without proceeds, realized gain, or dividends; preserve acquisition dates, basis, provenance, and uncertainty. Both accounts must be tracked and USD; no self-transfer; respect each account's opening cutoff and same-day order. Split multi-lot transfers into derived destination lots, not unrelated manual buys. Corrections replay both accounts and all later dependent transfers.

### Prices and incomplete analysis

Maintain manual/imported price observations `(symbol, price_date, price, source_label)` independent of trade prices and shared across transaction accounts. The price editor states that a correction affects all transaction accounts using that observation. For an as-of date use the latest observation on or before that date; never use a future observation or trade execution price as an automatic valuation. Price observations are end-of-day values. After a split, reject a pre-split observation for valuation until a price dated on/after that split is supplied; do not silently apply an old per-share price to the new share count. Splits are recorded per account, and the UI reminds the owner to record the event in every affected account. Display actual price dates and mark observations older than 7 calendar days as stale; this is an informational freshness threshold, not a trading calendar.

Missing price means unknown market value, not zero. Unknown basis means unknown unrealized/realized gain, not zero. Present totals only when complete; otherwise label known subtotals and show affected holding counts. Suppress portfolio percentages/allocation charts when selection-wide price or basis completeness required by that calculation is missing. Quantity views and independent complete calculations remain available. Realized gains, unrealized gains, and recorded dividends appear separately; no investment-return percentage combining them with deposits.

## 5. Generic CSV contracts

All formats: UTF-8/BOM, case/whitespace-normalized unique headers, strict row lengths, explicit blank handling, maximum 10,000,000 bytes and 10,000 data rows per file. Retain valid text such as `NA`; reject duplicate normalized headers. Unrecognized columns produce a visible preview warning; unrecognized event types block import. Persist normalized supported fields, file SHA-256, sanitized basename, and revision provenance locally; never retain raw upload bytes or full source paths automatically.

Account scope is selected explicitly before import. Ordinary files target one selected source account; transaction and allocation imports also support a deliberate Multiple accounts mode with `account_name` on every row. This allows dependent cross-account histories to be validated and committed together. Each named account must already exist. A transfer row references its destination by exact account name, resolved during preview. Do not match accounts by partial names. Required/type-dependent fields must be validated before any write.

| Import | Required columns | Optional/type-dependent columns |
|---|---|---|
| Transactions | `date,transaction_type,ticker` | `account_name,transaction_id,event_id,sequence,quantity,price,fees,amount,split_numerator,split_denominator,to_account,reinvestment_of,lot_allocations,notes` |
| Detailed opening lots | `lot_id,ticker,acquired_date,quantity,cost_basis` | `event_id,sequence,opening_date,company_name,sector` |
| Aggregate openings | `ticker,quantity,cost_basis` | `event_id,sequence,opening_date,company_name,sector` |
| Sale/transfer allocations | `transaction_id,lot_id,quantity` | `account_name,basis_amount` (basis amount only for aggregate pool slices) |
| Prices | `ticker,price_date,price` | `source_label` |
| Broker holdings for reconciliation | `ticker,quantity,cost_basis` | `company_name,sector` |

Detailed and aggregate opening exports are separate files when an account contains both kinds. Opening exports preserve `event_id`, `sequence`, and a consistent `opening_date`; a supplied opening date must agree with the selected cutoff. Opening cutoff and reconciliation statement date are selected in the import UI and included in the committed batch metadata. Reconciliation `cost_basis` may be blank (unknown), never implicitly zero. Opening basis is required; a genuinely unknown opening basis must be rejected with guidance, not represented as zero. Full-history empty accounts need no opening file. Opening IDs and transaction IDs are account-scoped, case-sensitive strings; internal UUIDs are also exported for subsequent allocation/correction references. Transaction exports include `event_id` (internal UUID) and `transaction_id` (original external ID, if any). Imports resolve either identifier only within the selected account, preserve exported IDs in a fresh compatible dataset, and reject conflicting/ambiguous identities. Reinvestment/allocation references accept an unambiguous event ID or external transaction ID. Exports also carry `export_kind` and `format_version=1`; account-bound exports additionally carry `account_name` (prices are global and omit it); importers validate consistent supported metadata and agreement with the selected account in single-account mode. In Multiple accounts mode only `account_name` may vary by row; kind/version remain consistent. Plain single-account templates may omit all metadata; plain multi-account templates require account names. Export a lot-reference column linking each buy/opening row to its generated internal lot IDs; allocation import accepts those exported lot IDs only.

BUY/SELL require quantity/price; fees default to zero. DIVIDEND requires amount. SPLIT requires numerator/denominator. TRANSFER requires quantity/to_account. Fields irrelevant to a type must be blank (fees may be blank or zero), preventing ambiguous price/basis interpretation. Reinvestment is expressed as DIVIDEND plus BUY with `reinvestment_of` equal to the dividend's transaction ID; such linked CSV rows require nonblank IDs. For round-trippable transaction exports, optional `lot_allocations` contains a JSON array of objects with `lot_id`, decimal-string `quantity`, and optional decimal-string `basis_amount`; absence means FIFO. Validate the complete proposed batch, including these references and their deterministic generated lot IDs. A separate allocation CSV/editor remains the ordinary human workflow. Its rows are grouped by transaction; each group completely replaces that transaction's allocation. Explicit lot allocation is a separate previewable import or editor action against known event IDs; changing it is a revision followed by replay.

The earlier public sample (`ticker,date,transaction_type,quantity,price`) is accepted directly for BUY/SELL with zero fees. It does not supply current prices, lot selections, or opening history; imports may therefore expose missing valuation or oversells. Do not infer missing history to make it pass.

### Duplicate-safe import and atomic previews

- Same account/type/content hash already committed: show prior batch and no-op by default, including the dispositions previously chosen.
- Nonblank external transaction/lot ID already present with identical canonical payload: skip as duplicate. If incoming sequence is omitted, preserve the existing event sequence before comparison rather than comparing a newly generated sequence; a supplied changed sequence is a conflict. A conflicting payload or a previously voided ID requires an explicit correction/revival, never an automatic overwrite.
- Without IDs, matching semantic fingerprints are **possible duplicates**, not proof. Include account, date, event type, symbol, quantity/price/fees/amount and type-specific fields; exclude generated IDs, sequence assigned by this app, filename, and notes. Repeated identical trades can be legitimate. Every ambiguous row requires a keep/skip decision, with occurrence counts visible. Ambiguity also applies within the same file.
- Parsed rows, validation errors, possible duplicates, and projected account changes form a session-only preview. Nothing persists before Confirm import. Invalid or unresolved duplicate rows block the complete batch; no automatic partial import.
- Capture the global data revision with previews (any committed input change, including prices). If committed data changes before confirmation, reject stale previews and require recomputation. The final commit revalidates the whole affected history and saves events, audit history, and import records in one SQLite transaction.
- Rows that are arithmetically valid but have unresolved aggregate opening basis are permitted with explicit unresolved results. Oversells, impossible allocations, unknown event types, and broken transfer/reinvestment links block writes.

Exports have distinct `export_kind` and version metadata: transaction/opening/price data exports are round-trippable through their corresponding importer; complete transaction data export covers all tracked accounts (with account names, internal IDs, and allocations) so transfer dependencies can be imported atomically. Per-account filtered transaction downloads are reports, not complete reconstruction data. Import opening files for all referenced accounts before the all-account transaction file; opening exports preserve internal event IDs. Derived holdings/lots/realized/reconciliation reports are explicitly reports. Existing `snapshot` and `analysis` formats remain unchanged. Never label derived 50-digit ledger basis as an editable V1 input snapshot. Export schemas carry dates, account, method, provenance, and completeness; blank numeric fields mean unknown. UI filters affect report exports only, never complete ledger data exports.

## 6. Persistence, migration, and recovery

Use SQLite schema version 2. Retain V1 `portfolios`, `snapshots`, and `holdings` intact. Add accounts, global data and economic revision counters, event identities/revisions/heads, price observations with revisions, import batches/row dispositions, reconciliation statement records/results, and audit operations. Decimal fields in payloads/columns are strings, never SQLite REAL. Use foreign keys and indexes for account/date, external IDs, active heads, and batch hashes. Compute positions/lots by replay rather than maintaining a second editable holdings cache.

Use a shared connection/migration layer so snapshot and ledger repositories agree about schema version. Before upgrading a V1 database, create a verified local SQLite backup via `Connection.backup`; if backup fails, do not migrate. The schema migration and version change are one transaction. Unknown versions and corrupt databases fail without modifying the source. A new database creates the complete schema atomically. Old code must continue rejecting schema 2 rather than attempting to use it.

Every correction/void requires a reason and appends a revision with UTC recorded time, prior/new normalized payload, operation ID, and import provenance. No hard deletion of committed events, audit history, or used accounts. Archive accounts instead. Existing snapshot delete semantics remain unchanged. Validate replay of the full affected transfer dependency set before committing any historical change; a rejected change leaves everything untouched. Account display-name edits must not rewrite historical security identity; symbol-change corporate actions are outside this release.

Provide a backup download/action using SQLite backup, plus an offline restore CLI. Restoration requires the app stopped, validates the source schema/integrity in a temporary copy, takes a recovery backup of the current DB, and atomically replaces it. Do not claim exclusive access to arbitrary external SQLite clients; document that every app process must be stopped. Failure preserves the original/recovery copy. Restore and migration tests always use temporary directories; execution must never run restore against the owner's database.

## 7. Reconciliation

Reject valuation/reconciliation dates before an opening account's cutoff; absence of older records is not a zero-share history. Realized gains and dividends are labeled as recorded since the tracking start, never as lifetime amounts for opening accounts.

A broker holdings import is an immutable external assertion for one account at one end-of-day date, marked complete by the user. Compute local holdings on that date from the current event revisions. Compare the union of symbols, including missing-on-either-side entries. Do not compare today's local positions to an older statement.

Default tolerances: absolute quantity difference <= `0.00000001` and absolute basis difference <= `$0.01`. Display tolerances and unrounded differences; tolerances never mutate recorded amounts. Status precedence is missing-on-either-side, then quantity mismatch, then unknown basis (`unresolved`), then basis mismatch/match. Unknown basis can never yield `matched`. A match is a holdings/basis comparison, not certification that tax lots or lifetime realized gains are correct.

Rows show local/broker quantity and basis, differences, and status (`matched`, `mismatch`, `unresolved`, `missing_local`, `missing_broker`). The report references statement date, input hash, economic revision, and calculation policy `fifo-v1`. Any subsequent economic/opening/allocation change marks saved comparisons stale; keep old evidence immutable and offer Recalculate. Price edits change the data revision but not the economic revision and therefore do not stale quantity/basis reconciliation. Economic changes increment both counters. Account metadata and statement/evidence writes change only the data revision. Resolve discrepancies through explicit corrections or supplied lot/basis information, never "overwrite local with broker".

## 8. UI and polish

Keep Streamlit. Use a simple application shell with two labeled modes, a compact context bar, and consistent native controls. Split the existing 363-line `ui.py` by workflow as it changes; avoid another monolithic screen.

**Snapshot mode:** preserve current Analysis/Edit workflow, numbered tables, full totals, compact filters, and charts. Existing saved portfolios remain recognizable.

**Transaction mode navigation:** Overview, Transactions, Lots & realized gains, Reconcile, and Data & recovery. Context bar shows account, as-of date, data completeness, and draft/pending status. Show warnings and navigation confirmations outside hidden tabs/pages. Use session drafts and guarded navigation; changing account/mode never silently discards an import or edit.

- Overview: full-width money values, separate realized/unrealized/dividend summaries, completeness labels, priced/unpriced counts, latest price dates, numbered holdings table. Drill into a holding's lots/events. Do not use color as the sole status signal.
- Transactions: searchable/filterable, numbered ledger; deliberate add/edit/void forms with previewed effects and reason; dedicated reinvestment/split/transfer forms with plain-language summaries. Import wizard: choose type/account → upload/map fixed aliases → review errors/duplicates/order/projected changes → confirm → receipt. No writing on file selection.
- Lots & realized gains: remaining quantity/basis, acquisition date or Unknown, provenance, allocation method, and unresolved explanations. Explicit allocation editor cannot select unavailable lots. A basis-resolution form asks for amount and reason/source description; no free editing of derived holdings.
- Reconcile: statement date and upload, comparison summary, differences table, drill-through to underlying events, stale badge, Recalculate. Distinguish missing data from numeric mismatches.
- Data & recovery: templates, complete data/report downloads, opening records, dated price editing/import, account archive, audit history, backup and offline-restore instructions.

Use a neutral theme with one blue accent, consistent spacing, readable text and badges, and native Streamlit layout. Minimal narrowly scoped CSS only for proven clipping problems; no HTML assembled from unescaped user data. Prefer forms/editable previews for input and read-only tables for derived results. Tables pin row number and symbol/date as useful, put financial columns first, support horizontal scrolling and full-screen inspection. Use full amounts with two display decimals; preserve exact values in data exports and detail views. Charts remain top-ten plus Other, sector bars, and top gain/loss bars; they never truncate table/report data.

Acceptance sizes: 1440×900, 1366×900, and 1024×768; narrow-width smoke check at 768 pixels. Verify keyboard navigation, visible labels, accessible status text, no ellipsized summary money, and usable long tables with synthetic 100-holding/10,000-event datasets. This is desktop-first, not a separate mobile application.

## 9. Cleanup and compatibility

Retain and reuse pure `analyze`, existing value models/charts where valid, all V1 user data, templates, snapshot CSV contracts, relevant tests, and historical design/evidence documents. Mark V1 specifications as historical with links to V2; do not delete them or rewrite past acceptance claims.

Extract common application/session/layout concerns once. Keep separate input validation for snapshot rows and ledger events; reuse the strict decimal/text primitives rather than forcing transactions through snapshot rules. Rename ambiguous UI labels/functions only where the two modes require it. Remove superseded private helpers and duplicate database initialization after all call sites/tests move. Remove old global copy claiming transactions or realized gains are unsupported; keep scoped explanations in Snapshot mode. Do not delete snapshot editing, the useful synthetic snapshot pack, lockfile, privacy ignore rules, or course materials.

No broad dependency upgrades or frontend rewrite. Add development-only Playwright if needed for repeatable browser tests; no additional runtime dependency is required. Archive or clearly label obsolete navigation instructions/screenshots, and update active README/demo paths to the new shell. Finish with a search for stale imports, unused modules, duplicate calculation paths, and stale product claims, followed by full tests and fresh installation verification.

## 10. Validation and delivery

Use independent hand-calculated fixtures for partial/full lot sales, fees, explicit allocations, unknown openings, dividend/reinvestment, forward/reverse splits, transfers and transfer descendants. Test replay ordering, conservation, invalid edits, duplicate ambiguity, transaction rollback, migration/restore, missing prices, exports, retained V1 workflows, and UI rerun/navigation state.

Native sequential execution remains the selected workflow. Every task has RED→GREEN behavioral checks, focused commits, and a progress ledger. After implementation, request one independent whole-branch review using GPT-6 Astra with High reasoning if available; address important findings and rerun relevant checks. Use isolated Edge/Playwright for actual uploads, editor/forms, allocation changes, reconciliation, and downloads. No merge, push, publish, or course submission.

References for terminology (not a claim of tax completeness): [IRS stock basis and share identification](https://www.irs.gov/faqs/capital-gains-losses-and-sale-of-home/stocks-options-splits-traders), [IRS Publication 550](https://www.irs.gov/publications/p550). The application records supplied data and identifies differences; it does not implement all tax-basis adjustments.
