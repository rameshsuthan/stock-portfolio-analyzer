# Portfolio Ledger V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:executing-plans** for native, sequential implementation. The user selected native execution in the existing project; preserve that choice. Implement tasks yourself, with one independent whole-branch review at the end. Do not restart brainstorming or ask for an execution-method choice after the next-session prompt approves these artifacts. Steps use checkboxes for tracking.

**Goal:** Add reliable transaction accounts, explainable purchase-lot cost basis, and brokerage holdings reconciliation while retaining snapshot mode and polishing the Streamlit workflows.

**Architecture:** A pure Decimal replay engine derives lots, holdings, proceeds, and basis from revisioned events. SQLite stores source records/audit history and dated prices; a separate reconciliation service compares derived positions with immutable broker assertions. Snapshot and transaction modes share presentation/calculation primitives but never share editable sources of truth.

**Tech Stack:** Python 3.14.*, Streamlit, pandas, Plotly, standard-library Decimal/SQLite/CSV, uv, pytest, Ruff; development-only Playwright for reproducible browser checks.

**Spec:** [Portfolio Ledger V2 design](../specs/2026-10-11-portfolio-ledger-v2-design.md). Read it in full first; it is authoritative for all rules below.

**Status:** Planning only. Baseline `feature/portfolio-v1` / `35662c6`, 58 tests passing. The completed V1 lives in `.worktrees/portfolio-v1`, not `main`. Create a new V2 worktree from the V1 branch after the planning documents are committed. No V2 product code has been written.

## Global constraints

- Local, single-user, long USD stocks/ETFs and fractional shares. Preserve all existing snapshot behavior and data.
- Keep Python 3.14.*, Streamlit, pandas, Plotly, SQLite, uv, pytest, Ruff. No ORM, API server, custom frontend, hosted service, brokerage authentication, live pricing, telemetry, or broad dependency upgrades.
- Generic CSV only; FIFO plus complete explicit lot allocation; BUY/SELL/fees, cash dividends/reinvestment, splits, internal tracked-account transfers.
- Arithmetic uses Decimal precision 50; inputs use at most 18 significant digits and 8 decimal places. Money/share inputs are plain decimals. Display rounding is not storage rounding.
- Strict ISO dates, at most 10,000,000 bytes and 10,000 rows per CSV; no silent ignored event types, guessed trade times, duplicate removal, missing basis, or missing price substitution.
- Preserve aggregate opening uncertainty. Unknown values are `None` plus a reason, never zero; manually supplied amounts retain provenance.
- All verification uses synthetic records and temporary databases. Never migrate, restore, inspect holdings from, or test against the owner's real database.
- No merge, push, publish, or course submission. Preserve user changes and leave the completed implementation branch/worktree available.

## Review focus

1. Two legitimate identical trades versus overlapping imports: require explicit occurrence decisions without silently skipping either (Task 5).
2. Unknown opening pools crossing partial sales/transfers: propagate uncertainty and later resolution without proportional estimates (Tasks 2–3).
3. A historical correction invalidating a later transfer or sale in another account: reject the complete change and preserve audit/data (Task 4).
4. Decimal residuals, reverse splits, and pre-split prices: conserve basis and reject unsupported settlement rather than fabricate precision or valuation (Tasks 2, 3, 6).
5. Preview/confirmation state surviving Streamlit reruns, page changes, and changed database revisions: no lost drafts, hidden confirmations, or stale commits (Tasks 5, 8–10).

## Execution protocol and progress ledger

- Before coding, inspect repository status and any applicable AGENTS.md. Verify the V1 baseline and planning documents; commit only these planning artifacts if untracked. Preserve unrelated changes. Create/verify a V2 worktree/branch based on the actual V1 implementation plus the planning commit. Never branch the implementation from the current `main` scaffolding.
- Run `uv sync --locked`, `uv run --locked pytest -q`, `uv run --locked ruff check .`, and `uv run --locked ruff format --check .`; record baseline results. Do not regenerate the lockfile except to add the planned dev browser dependency.
- Create `docs/implementation-progress-v2.md` with baseline/branch, task states, commits, RED/GREEN commands/results, implementation rulings/reasons, verification state, and next action. Update it in every task commit. On resume, read it and inspect Git before doing work; do not restart completed tasks.
- Execute Tasks 1–11 in order. For each behavioral slice: write the specified regression, observe the intended failure, implement the minimum change, pass relevant tests and the full suite, then make a focused commit. Test function names/assertions below are required behavior contracts, not permission to mock the engine/repository away.
- Do not repeatedly ask to continue. If an adjustment is necessary, preserve the approved outcome, record its reason, and proceed. Escalate only an actual unresolved product decision or destructive action; do not invent missing financial history.
- Keep runnable test evidence honest. No numerical test-count target for V2; the final count comes from the actual full run. Baseline's 58 tests may be relocated but their behavior must remain covered.

## File and interface map

Retain `app.py` as the entrypoint and retain the V1 models/calculator/CSV/validation/workflow/storage public behavior. Extract only what is needed:

| Area | Files and responsibility |
|---|---|
| Database/recovery | `src/stock_portfolio/database.py` connection/schema migrations; `backup.py` backup/offline restore; adapt existing `storage.py` to the shared layer |
| Domain | `src/stock_portfolio/ledger/models.py` typed records; `validation.py` event/input validation; `engine.py` deterministic replay; `lots.py` allocation/pool bookkeeping; `events.py` dividend/split/transfer handlers |
| Persistence | `src/stock_portfolio/ledger/repository.py` atomic operations, revisions, batches, prices, statements; `codec.py` canonical JSON/Decimal/date serialization |
| Exchange/services | `src/stock_portfolio/ledger/csv_io.py` typed parsers/exports; `imports.py` preview/duplicates/confirmation; `valuation.py` price-aware analysis; `reconciliation.py` dated comparison |
| UI | Existing `ui.py` becomes app shell; `views/snapshots.py`, `overview.py`, `transactions.py`, `lots.py`, `reconcile.py`, `data.py`; `ui_state.py` session draft/navigation guards; `presentation.py` shared safe formatting/table/chart adapters |
| Evidence | `tests/ledger/`, `tests/browser/`, `samples/ledger/`, `docs/implementation-progress-v2.md`, updated README/development log/manual acceptance |

Do not create a generic plugin system, domain event bus, trading framework, or speculative broker adapter layer. New package directories have `__init__.py`; keep the existing installed-entrypoint smoke test.

### Shared public types

All types below live in `ledger/models.py`, use frozen dataclasses/enums where appropriate, Decimal/date/UUID values in memory, and string serialization at persistence boundaries. Signature names are fixed for task handoff; helper internals are implementer choices.

- `Account(id: str, name: str, opening_date: date | None, archived: bool = False, currency: str = "USD", broker_label: str = "")`. `opening_date=None` means full history.
- `EventKind`: `OPENING_LOT`, `OPENING_BALANCE`, `BUY`, `SELL`, `DIVIDEND`, `SPLIT`, `TRANSFER`.
- `LotAllocation(lot_id: str, quantity: Decimal, basis_amount: Decimal | None = None)`. `basis_amount` is permitted only on an aggregate-pool slice; exact-lot basis is derived, never overridden here.
- `LedgerEvent(id: str, account_id: str, effective_date: date, day_sequence: int, kind: EventKind, symbol: str, quantity: Decimal | None = None, price: Decimal | None = None, fees: Decimal = Decimal(0), amount: Decimal | None = None, basis: Decimal | None = None, acquired_date: date | None = None, split_numerator: int | None = None, split_denominator: int | None = None, destination_account_id: str | None = None, allocations: tuple[LotAllocation, ...] = (), reinvestment_of: str | None = None, external_id: str | None = None, notes: str = "")`.
- `LedgerDataset(accounts: tuple[Account, ...], events: tuple[LedgerEvent, ...], revision: int, economic_revision: int)`. Contains active event heads, not superseded/voided revisions. `revision` changes for any input/evidence write; `economic_revision` changes only with economic/opening/allocation events and drives reconciliation staleness.
- `Issue(code: str, message: str, row: int | None = None, event_id: str | None = None, account_id: str | None = None, symbol: str | None = None)`.
- `Lot(id, account_id, symbol, acquired_date: date | None, acquisition_order: tuple[date,int,str], quantity: Decimal, basis: Decimal | None, origin_event_id, source_lot_id: str | None, aggregate: bool, issues: tuple[Issue,...])`.
- `Position(account_id, symbol, quantity: Decimal, basis: Decimal | None, lot_ids: tuple[str,...], issues: tuple[Issue,...])`.
- `Disposal(event_id, account_id, symbol, quantity, proceeds: Decimal, basis: Decimal | None, gain: Decimal | None, method: str, matches: tuple[LotAllocation,...], issues: tuple[Issue,...])`.
- `Reinvestment(dividend_event_id, buy_event_id, amount: Decimal, purchase_cost: Decimal, remainder: Decimal)`.
- `ReplayResult(lots: tuple[Lot,...], positions: tuple[Position,...], disposals: tuple[Disposal,...], dividends: dict[str,Decimal], reinvestments: tuple[Reinvestment,...], issues: tuple[Issue,...])`. `dividends` is account ID → recorded amount; unresolved-data issues are nonfatal. Invalid history raises `InvalidLedger(issues)` and must not produce commit-worthy partial output.
- `PriceObservation(symbol: str, price_date: date, price: Decimal, source_label: str = "Manual")`.
- `ValuedPosition(position: Position, price: Decimal | None, price_date: date | None, market_value: Decimal | None, unrealized_gain: Decimal | None, issues: tuple[Issue,...])`.
- `AccountValuation(account_id, as_of, holdings: tuple[ValuedPosition,...], known_basis: Decimal, known_value: Decimal, total_basis: Decimal | None, total_value: Decimal | None, unrealized_gain: Decimal | None, realized_gain: Decimal | None, dividends: Decimal, issues: tuple[Issue,...])`.
- `BrokerHolding(symbol: str, quantity: Decimal, basis: Decimal | None)`; `BrokerStatement(id, account_id, as_of, holdings: tuple[BrokerHolding,...], source_hash: str)`.
- `ReconciliationRow(symbol, local_quantity: Decimal | None, broker_quantity: Decimal | None, local_basis: Decimal | None, broker_basis: Decimal | None, quantity_difference: Decimal | None, basis_difference: Decimal | None, status: str)`; `ReconciliationResult(statement_id, account_id, as_of, source_hash, ledger_revision: int, policy: str, quantity_tolerance: Decimal, basis_tolerance: Decimal, rows: tuple[ReconciliationRow,...])`.

Repository-returned revision/history records additionally carry UTC recorded time, reason, operation ID, version, and provenance. BUY and detailed/aggregate opening lots use the originating event UUID as their lot ID. Transfer slice IDs use UUID5 with the standard URL namespace and name `transfer:{event_id}:lot:{source_lot_id}`, so exported allocations resolve on deterministic replay. No personal values in routine logs or exception trace dumps.

## Task 1: Safe schema evolution and recovery boundary

**Files:** create `database.py`, `backup.py`; modify `storage.py`; create `tests/test_migrations.py`, `tests/test_backup.py`; retain `tests/test_storage.py`.

**Interfaces:** `open_database(path: Path) -> sqlite3.Connection`; `create_backup(source: Path, destination: Path) -> Path`; `restore_backup(source: Path, destination: Path) -> Path` returns the pre-restore recovery backup path. Restore CLI: `uv run python -m stock_portfolio.backup restore --source PATH --destination PATH --confirm-stopped`.

- [ ] Write failing migration tests: construct a genuine schema-1 database with two snapshots; open with the new layer and assert `user_version == 2`, all names/dates/Decimal strings unchanged, and a valid pre-migration backup exists. Unknown version 99 and backup failure must leave the original schema/data unchanged; injected migration failure must roll back.
- [ ] Write recovery tests: restore into a temporary stopped-app directory, compare logical records, and assert the old destination survives as a backup. Invalid/corrupt/newer-version input and injected replacement failure must preserve the destination. Backup must use SQLite's backup API, not copy a live main file alone.
- [ ] Run `uv run --locked pytest tests/test_migrations.py tests/test_backup.py -q` and observe the failures.
- [ ] Implement transactional version-2 creation/upgrade and shared connection setup (`foreign_keys=ON`). Tables: `accounts`; `ledger_state` data/economic revision counters; `ledger_event_identities` (stable ID/account/external ID); `ledger_event_revisions` (event/version/status/canonical payload/reason/operation/provenance/time); `ledger_event_heads`; `price_observations` plus revisions; `import_batches`/`import_rows`; `broker_statements`/`broker_statement_rows`; `reconciliation_runs`/`reconciliation_rows`; `audit_operations`. Retain all V1 tables. Enforce identities/references/uniqueness with constraints; derive active chronology from heads and validate its unique day sequence in transaction. Add account/date/external-ID/batch indexes.
- [ ] Implement verified backup and offline restore. Backup before V1 migration; no migration when backup fails. Use a same-directory temporary destination, integrity/schema checks, a pre-restore backup, and atomic replacement. Document stopped-process requirement; do not attempt to stop arbitrary processes.
- [ ] Run focused tests, all existing storage tests, and the full suite. Update ledger; commit `feat: add safe ledger schema migration and backup recovery`.

## Task 2: Trades, opening records, FIFO, and explicit lots

**Files:** create `ledger/__init__.py`, `models.py`, `validation.py`, `engine.py`, `lots.py`; create `tests/ledger/test_trades.py`, `test_openings.py`, `conftest.py`.

**Interfaces:** shared types above; `validate_events(dataset: LedgerDataset, today: date | None = None) -> tuple[Issue,...]`; `replay(dataset: LedgerDataset, as_of: date) -> ReplayResult`. Validation catches malformed inputs; input services pass local today explicitly for future-date checks, while pure replay has no clock dependency; replay catches chronological/economic impossibility. Use fixed-date independent test helpers in `tests/ledger/conftest.py` only.

- [ ] Write `test_fifo_partial_sale_includes_fees`: buy 10 at 100 with fee 10; buy 5 at 120 with fee 5; sell 12 at 150 with fee 6. Assert proceeds `1794`, disposed basis `1252`, realized gain `542`, remaining quantity `3`, remaining basis `363`.
- [ ] Write `test_explicit_lots_override_fifo`: same buys; sell 8 at 150 with fee 4, selecting all 5 from the second lot and 3 from the first. Assert disposed basis `908`, gain `288`, remaining quantity `7`, basis `707`. Incomplete/wrong-account/future/overdrawn lot selections fail.
- [ ] Write `test_unknown_opening_basis_is_not_prorated`: aggregate opening 10 shares/basis 1000, sell 4 at 150. Assert remaining quantity `6`, remaining basis `None`, proceeds `600`, realized gain `None`. Supply pool allocation basis `400`, replay, and assert remaining basis `600` and gain `200`. Full disposal of an untouched pool at 150 resolves basis `1000` and gain `500`.
- [ ] Add tests for detailed openings, aggregate-to-detailed replacement totals, rejecting trades on/before an opening cutoff, dated FIFO across lots, zero basis, invalid/negative inputs, oversell before a later buy, same-day sequence collisions/order, closed positions, unaffected symbols when one pool is unknown, and all-disposed pools with unresolved historical allocations.
- [ ] Write conservation test using a detailed opening of 3 shares with basis 1 and three successive one-share sales: sum disposed basis must equal exactly `Decimal("1")`; final quantity/basis zero; no cents rounding. Add explicit-fee allocation and negative net proceeds cases.
- [ ] Run `uv run --locked pytest tests/ledger/test_trades.py tests/ledger/test_openings.py -q` and observe failures. Implement validated immutable types and replay with indexed account/symbol FIFO queues, lot availability, pool-resolution bookkeeping, and precision-50 contexts. No database/UI dependencies.
- [ ] Run focused and full tests. Record basis/quantity conservation and uncertainty rules in the ledger; commit `feat: derive trade positions and lot cost basis`.

## Task 3: Dividends, reinvestment, splits, and linked transfers

**Files:** create `ledger/events.py`; extend `engine.py`, `lots.py`, `validation.py`; create `tests/ledger/test_events.py`, `test_transfers.py`.

**Interfaces:** extend the same `replay`/event types; no second calculator. Handler functions in `events.py` may be internal; all tests exercise public replay.

- [ ] Write dividend/reinvestment test: dividend `50`; linked buy `.4` shares at `120`, fee `1`. Assert recorded dividend `50`, new basis `49`, quantity `.4`, and uninvested dividend remainder `1`. Validate missing/wrong-account/wrong-symbol links, wrong sequence, and buy cost exceeding dividend. BUY alone must not synthesize a dividend.
- [ ] Write split tests: 10 shares/basis 1000 → 2:1 split gives 20/basis 1000; subsequent 1:4 gives 5/basis 1000. Dates/provenance unchanged. Reject 1 share split 1:3 because the quantity requires unsupported precision; no silent rounding/cash-in-lieu.
- [ ] Write transfer test: source has 10 shares/basis 1000; transfer 4 to an empty tracked account. Assert source 6/basis 600, destination 4/basis 400, same acquisition date, zero transfer realized gain/dividends. Cover multiple lots, explicit allocation, destination selling on the same day after transfer, account cutoff, self-transfer, and oversell.
- [ ] Write aggregate transfer tests: partial transfer without supplied basis makes both related balances unresolved; basis amount 400 resolves source 600/destination 400. Transfer descendants propagate later source corrections. Unrelated accounts remain unaffected.
- [ ] Run `uv run --locked pytest tests/ledger/test_events.py tests/ledger/test_transfers.py -q`; observe intended failures. Implement events and deterministic destination lot IDs. Evaluate complete transfer/reinvestment groups atomically at service boundaries; no pair of independent source/destination writes.
- [ ] Run focused/full tests; commit `feat: support portfolio income splits and linked transfers`.

## Task 4: Revisioned persistence and atomic corrections

**Files:** create `ledger/codec.py`, `repository.py`; create `tests/ledger/test_repository.py`, `test_corrections.py`.

**Interfaces:** `LedgerRepository(path: Path)` context manager; `load_dataset() -> LedgerDataset`; `create_account(name: str, opening_date: date | None = None, broker_label: str = "") -> Account`; `archive_account(account_id: str) -> None`; `apply_operation(upserts: tuple[LedgerEvent,...], void_ids: tuple[str,...], expected_revision: int, reason: str, provenance: dict[str,str] | None = None) -> int`; `history(event_id: str) -> tuple[dict,...]`. `StaleRevision`, `InvalidLedger`, and `IdentityConflict` are explicit failures. All writes update the data revision; economic/opening/allocation changes additionally update the economic revision. Statement/price/account metadata changes do not stale reconciliation.

- [ ] Write round-trip/restart tests preserving Decimal strings, IDs, ordering, and links; canonical serialization must reject nonfinite values and never serialize Decimal through float.
- [ ] Write correction test: source buy 10, transfer 8 to another account, destination sell 6. Revising original buy to quantity 5 must raise `InvalidLedger`, retain the original source/both account results, and append no committed audit operation. A valid revision records old/new versions and reason and changes the economic revision once.
- [ ] Test immutable identity/external-ID conflicts, void/revive history, archive restrictions, linked reinvestment edits/voids as a group, duplicate day sequences, stale expected revisions, and no destructive account deletion. Voiding a transfer with a dependent sale fails atomically.
- [ ] Inject a SQLite trigger failure after the first row of a multi-account write; assert events, heads, audit, and global revision all roll back. Test full-history validation including later events, not only the currently viewed as-of date.
- [ ] Observe focused failures, then implement `BEGIN IMMEDIATE`, revision check, proposed-dataset replay through its latest event date, atomic heads/history/audit writes, and rollback. Recompute from all active events initially; optimize only if measured tests justify it.
- [ ] Run `uv run --locked pytest tests/ledger/test_repository.py tests/ledger/test_corrections.py -q` and full suite; commit `feat: persist auditable ledger revisions atomically`.

## Task 5: Generic import previews, duplicates, and exact exports

**Files:** create `ledger/csv_io.py`, `imports.py`; extend `repository.py`; create `tests/ledger/test_csv.py`, `test_imports.py`, `test_exports.py`.

**Interfaces:** `ImportKind` enum (`transactions`, `opening_lots`, `opening_balances`, `allocations`, `prices`, `broker_holdings`); `ParsedImport(kind, rows: tuple[dict[str,str],...], file_hash, source_name: str, warnings: tuple[str,...])`; `parse_import(content: bytes, kind: ImportKind, source_name: str = "upload.csv") -> ParsedImport`; `ImportChoice(row: int, action: str)` where action is `keep`/`skip`; `ImportPreview(id, kind, account_id: str | None, effective_date: date | None, expected_revision: int, issues, warnings, duplicate_rows, proposed_events: tuple[LedgerEvent,...], void_ids: tuple[str,...], proposed_prices: tuple[PriceObservation,...], proposed_statement: BrokerStatement | None, projected: ReplayResult | None, batch: ImportBatch, no_op_batch_id: str | None)`; `prepare_import(repo: LedgerRepository, parsed: ParsedImport, account_id: str | None, effective_date: date | None = None, choices: tuple[ImportChoice,...] = ()) -> ImportPreview`; `commit_import(repo: LedgerRepository, preview: ImportPreview) -> str` returns batch ID. `ImportBatch(id, account_ids: tuple[str,...], kind, source_hash, source_name, rows: tuple[dict[str,str],...], choices: tuple[ImportChoice,...])` stores normalized supported fields and sanitized basename. `account_id=None` deliberately selects Multiple accounts mode for transactions/allocations; all row account names must resolve exactly. Date metadata is needed for openings/statements. `expected_revision` is the global data revision. Price and statement persistence dispatches are completed by Tasks 6–7; until then their parsers validate but do not offer a false successful commit.

`export_events(dataset: LedgerDataset) -> bytes`, `export_openings(dataset: LedgerDataset, account_id: str, kind: ImportKind) -> bytes` (kind is opening_lots or opening_balances), `export_allocations(dataset, account_id) -> bytes`, and `export_prices(observations: tuple[PriceObservation,...]) -> bytes` use distinct kinds/version metadata. Event export excludes opening records (separate format) and includes all active trades/events across all tracked accounts, not UI filters. It includes `account_name`, stable `event_id`, original external ID, and JSON `lot_allocations` so dependent transfers/lots replay in one batch. Per-account filtered event downloads are marked reports. Preserve links and IDs. Cross-account transfer reimport requires existing matching account names and all opening records loaded first (opening exports preserve internal event IDs, sequence, and cutoff; detailed/aggregate openings use separate files); never invent destination accounts. Database backup remains the complete recovery format including audit history.

- [ ] Test the public five-column BUY/SELL sample shape; missing `fees` becomes zero. Test atomic all-account transaction import containing dependent transfers and sales, plus export/import of explicit allocations and deterministic destination lot IDs. Test strict event-dependent fields, metadata mismatch/report-as-input rejection, BOM, `NA`, duplicate headers, missing/trailing cells, unknown event type, 10,001 rows, oversized bytes, malformed ISO dates, future event dates with an explicit fixed today passed to validation, and plain-decimal limits. Record CSV row numbers including header.
- [ ] Test exact repeated file no-op; same external ID/same economics skipped; conflicting ID or voided ID requires correction. Test two identical ID-less buys in one file and an overlap across files: preview marks both possibilities, commit is blocked without keep/skip decisions, keeping both produces twice the shares. Generated sequence/IDs must not defeat duplicate detection; an ID match with omitted sequence preserves the stored sequence before payload comparison.
- [ ] Test source row order for same-day rows when sequence absent; explicit order collisions block; a historical import that makes a subsequent sale invalid blocks the entire batch. Changing database revision after preview produces `StaleRevision` and zero writes. Price/metadata changes must also invalidate a preview via data revision, while keeping saved quantity/basis reconciliation current.
- [ ] Test exact export/import round trips into a fresh temporary set of matching named accounts: load exported opening records first, then all-account event data atomically, including stable internal IDs, external IDs, links, allocation IDs, acquisition dates, and fractional values. Complete data exports retain excluded-by-filter holdings. Report exports cannot masquerade as import data.
- [ ] Run CSV/import/export tests to observe failures. Implement normalization, immutable preview identity/IDs, explicit duplicate occurrence choices, registry ID resolution, and transactional batch confirmation. Add repository `commit_import_batch(preview: ImportPreview) -> str`, defined with a TYPE_CHECKING-only type import if needed to avoid module cycles; its implementation writes the economic/price/statement operation and batch/dispositions in one transaction. Do not call the already-committing `apply_operation` then save the batch separately; share an internal transaction helper. Keep raw bytes/session upload objects out of stored records and logs. Store supported normalized original revision values and hashes, not raw CSV files.
- [ ] Run focused/full suite; commit `feat: add reviewable duplicate-safe ledger CSV exchange`.

## Task 6: Dated prices and honest valuation/reporting

**Files:** create `ledger/valuation.py`; extend `repository.py`, `imports.py`, `csv_io.py`; modify existing `calculations.py` only if a shared pure primitive is truly needed; create `tests/ledger/test_valuation.py`.

**Interfaces:** `LedgerRepository.save_prices(observations: tuple[PriceObservation,...], expected_revision: int, reason: str) -> None`; `load_prices() -> tuple[PriceObservation,...]`; `value_account(dataset: LedgerDataset, replayed: ReplayResult, prices: tuple[PriceObservation,...], account_id: str, as_of: date) -> AccountValuation`; `export_holdings_report(value: AccountValuation) -> bytes`; `export_realized_report(replayed: ReplayResult, account_id: str, as_of: date) -> bytes`. Global shared prices are visibly labeled as affecting all transaction accounts. Price corrections retain revisions, do not increment economic revision, and do not invalidate quantity/basis reconciliation.

- [ ] Test latest price on/before as-of, missing price, future-only price, zero price, and stale (>7 calendar days) status. A split on Jan 3 must prevent Jan 2 price use on Jan 3+, even when under the freshness threshold; a Jan 3 end-of-day price is valid.
- [ ] Test rejection of dates before an opening cutoff and clear since-tracking-start gain labeling. Test opening 10/basis 1000 with price 120 → market value 1200, unrealized 200. Partial unknown-basis sale leaves known value but `unrealized_gain is None`; known subtotals must never be labeled complete totals. Missing one holding's price makes total value/allocation unavailable but retains known subtotal. Closed positions remain in realized reports, not holdings.
- [ ] Test unknown-vs-zero export values, exact derived decimals exceeding input scale, independent realized/unrealized/dividend amounts, and unchanged V1 input/export contracts. Ledger report marker prevents accidental snapshot import. Price corrections at an existing symbol/date require explicit preview/confirmation and retain history.
- [ ] Observe failures, implement valuation and report metadata/completeness. Reuse V1 `analyze` only on fully valued/basis-known Holding adapters; do not inject zero for incomplete inputs or run derived values back through snapshot input validation.
- [ ] Run valuation tests and full suite; commit `feat: value ledger holdings with dated prices and completeness`.

## Task 7: Dated brokerage reconciliation and stale evidence

**Files:** create `ledger/reconciliation.py`; extend repository/import/export modules; create `tests/ledger/test_reconciliation.py`.

**Interfaces:** `reconcile(dataset: LedgerDataset, statement: BrokerStatement, quantity_tolerance: Decimal = Decimal("0.00000001"), basis_tolerance: Decimal = Decimal("0.01")) -> ReconciliationResult`; repository methods `save_statement(statement: BrokerStatement) -> str`, `save_reconciliation(result: ReconciliationResult) -> str`, `load_reconciliations(account_id: str) -> tuple[ReconciliationResult,...]`; `export_reconciliation(result: ReconciliationResult) -> bytes`. `reconcile` itself calls replay at statement.as_of, never at today. Record `dataset.economic_revision` in `result.ledger_revision`, not the global input revision.

- [ ] Build a fixture where quantity was 10 at statement date and is now 6. Assert comparison uses 10 and reports matched against 10/basis 1000. Test union-of-symbols missing statuses and a sold-out broker row.
- [ ] Test exact tolerance boundaries (`1e-8` quantity/`.01` basis accepted; larger differences mismatch), blank broker basis, unresolved local basis, quantity mismatch plus unknown basis, duplicate symbols, negative quantity, and owner confirmation that the statement is complete. Unknown basis never yields `matched`; show quantity difference even when basis is unknown.
- [ ] Save comparison, correct a past event, and assert saved evidence unchanged and displayed stale against the new economic revision; recalculation creates a new result. Price-only correction does not stale comparison. Test that importing a broker statement never edits ledger holdings.
- [ ] Observe failures; implement comparison rows with actual differences, statement/hash/date/revision/policy evidence, persistence, and report export. Set policy exactly `fifo-v1`; explicit sale allocations are event data within that policy.
- [ ] Run focused/full suite; commit `feat: reconcile dated ledger holdings against broker assertions`.

## Task 8: Application shell, snapshot preservation, and guarded navigation

**Files:** refactor `ui.py`; create `views/__init__.py`, `views/snapshots.py`, `ui_state.py`, `presentation.py`; update `tests/test_app.py`; create `tests/test_navigation.py`.

**Interfaces:** `ui.main()` remains the public entrypoint; `views.snapshots.render(repository: Repository, notices) -> None`; `ui_state.PendingDraft` stores mode/account/page/key, normalized input state, dirty flag and pending destination; `guard_navigation(current_context: tuple, requested_context: tuple, dirty: bool) -> bool` returns whether navigation is allowed and renders/records explicit discard/cancel outside page containers. Keep the existing snapshot Draft API unless a tested private extraction is needed.

- [ ] Write navigation tests for snapshot mode default, opening saved data, retained analysis/edit tabs, numbered rows, full monetary values, compact filters/reset, and unchanged snapshot imports/exports. Move existing assertions without weakening them.
- [ ] Write tests switching mode/account/page with unsaved editor/import state: rerun retains inputs; navigation waits for explicit discard; cancel stays on source context. Warnings, discard, and deletion confirmations must exist outside hidden tabs/pages. Mode/context selection updates only after guard resolution.
- [ ] Observe failures; implement a compact sidebar mode/account selector and transaction navigation, visible context/status bar, shared notices area, stable widget keys, and session draft storage independent of hidden widget lifecycle. Navigation controls use callbacks/pending targets rather than mutating an already-rendered widget's state.
- [ ] Extract snapshot UI into its view, shared money/percentage/unknown formatting into presentation helpers, and common database lifecycle into the shell. Preserve native controls and existing privacy config. Add neutral/blue theme without unsafe HTML interpolation or sweeping CSS.
- [ ] Run AppTest/navigation tests, installation smoke test, and full suite; commit `refactor: add guarded application modes and preserve snapshots`.

## Task 9: Transaction entry, import wizard, lots, and derived overview

**Files:** create `views/overview.py`, `transactions.py`, `lots.py`, `data.py`; extend `ui_state.py`/`presentation.py`; create `tests/test_ledger_ui.py`.

**Interfaces:** each view exposes `render(repo: LedgerRepository, account_id: str, as_of: date, notices) -> None`; all writes call the tested repository/import services, never direct SQL. Overview receives computed service results; do not implement arithmetic in widget callbacks.

- [ ] Write UI tests for empty account onboarding/full-history/opening modes; file upload alone makes no writes; wizard preview exposes normalized rows, duplicate decisions, chronology, issues, and projected impact; Confirm commits once and displays receipt. Invalid/duplicate/stale previews keep the file/draft and block commit.
- [ ] Test BUY/SELL forms, lot selection sums/availability, reason-required revision/void, unresolved basis resolution, linked dividend/reinvestment, split/transfer previews, and cancellation. Transfer previews name both accounts and each one's projected holdings.
- [ ] Test aggregate opening setup and explicit Start account from snapshot: preview exact quantities/total bases and unknown acquisition dates; create only a new account after confirmation; original snapshot unchanged; no one-purchase-per-snapshot conversion. Opening-detail replacement must show dependent gain changes before commit.
- [ ] Test Overview with missing prices/basis, closed positions, and 100 holdings; known subtotal labels cannot imply complete gains. Add exact-value drill-through and table filters/report downloads with data exports kept complete.
- [ ] Observe failures; implement forms/import steps and stable session state. Lots page links sales to consumed lots, shows provenance and unknown dates, and supports complete explicit allocation or supplied pool basis. Data view supports templates/openings/prices and account archiving. Transactions retain date/row numbers and sortable financial columns.
- [ ] Run UI/full tests; commit `feat: add transaction and lot management workflows`.

## Task 10: Reconciliation, recovery UI, and usability polish

**Files:** create `views/reconcile.py`; extend `views/data.py`, `presentation.py`, `.streamlit/config.toml`; create `tests/test_reconciliation_ui.py`.

**Interfaces:** use Task 7 services and Task 1 backup API; no UI restore while the app is running. Recovery view provides backup download and exact stopped-app restore command/instructions.

- [ ] Write UI tests for statement date/account/completeness confirmation, mismatch/unknown/missing statuses, stale comparisons, immutable previous results, and drill-through from a mismatch to its relevant lots/events. Recalculate must produce new evidence and never overwrite holdings.
- [ ] Test audit history old/new values/reasons, archive behavior, backup download backed by a consistent SQLite artifact, and restore instructions naming the currently configured data directory without exposing secrets. User paths remain session/local display only, not logs/evidence.
- [ ] Observe failures; implement readable status text/badges, side-by-side broker/local columns, full metric amounts, financial column ordering, row numbers, sparse empty states with next actions, compact filters and purposeful action groups. Price-date/unknown labels are visible near values, not hidden in tooltips alone.
- [ ] Apply the spec's native Streamlit polish across both modes. Use existing chart summaries for complete data; hide misleading partial allocation plots. Put safety confirmations and import errors where visible regardless of current page. Avoid duplicate save/import buttons with ambiguous effects.
- [ ] Run focused/full suite plus lint/format checks; commit `feat: add reconciliation recovery and polished portfolio views`.

## Task 11: Synthetic acceptance pack, cleanup, browser checks, and independent review

**Files:** create `samples/ledger/README.md`, `expected_results.json`, valid/invalid fixtures, `tests/browser/test_ledger_acceptance.py`; update `pyproject.toml`/`uv.lock` only for dev Playwright, README, development log, active demo instructions, and `docs/implementation-progress-v2.md`; remove only superseded private code identified below.

- [ ] Write fixture tests against independently calculated expected results, covering 100 holdings, 10,000 events in a file, repeated legitimate trades, overlapping imports, unknown opening pools, two linked accounts, multi-lot sales/transfers, corrections, splits, reinvestment, missing/stale prices, and broker matches/mismatches. Include invalid headers/precision/chronology/events and exact expected issue codes. Do not derive expected totals by calling replay. Reuse synthetic public tickers without claiming generated prices are market data.
- [ ] Add a development-only browser harness that creates a temporary data directory, starts/stops its own local server, and uses an isolated Edge Chromium profile (`channel="msedge"`) with Playwright; document fallback Chromium setup if Edge unavailable. Never attach the owner's profile. Browser tests run explicitly and are not silently skipped as passed.
- [ ] Run actual browser acceptance: create two accounts; upload/preview/confirm generic CSV; import again/no-op; decide ambiguous duplicates; edit a trade and cancel/confirm; select lots; resolve opening basis; record dividend/reinvestment/split/transfer; import dated prices; compare broker holdings; correct a mismatch; verify stale comparison/recalculate; download and inspect exports; back up; restart and verify persistence. Recheck snapshot CSV upload and actual canvas editing. Test tab/page navigation while dirty and all visible confirmations.
- [ ] Inspect UI/screenshots at 1440×900, 1366×900, 1024×768 and smoke-test 768 width. Measure summary-value overflow and inspect charts/tables. Capture only synthetic evidence. Use a 10,000-event file for import/replay responsiveness; record actual timings on the test machine, show progress during long work, and investigate a 10-second-plus replay before claiming usable release. No arbitrary benchmark assertion tied to hardware.
- [ ] Complete cleanup inventory: remove old duplicate database initialization and superseded private UI helpers; delete unused imports/modules only after references and tests are moved; consolidate shared formatting once; remove obsolete global unsupported-feature copy; update navigation/docs/templates. Preserve legacy modes/contracts/test coverage, historical specs/evidence, synthetic snapshot pack, lockfile, privacy ignores, and course materials. Do not delete user files, databases, worktrees, or unrelated repository artifacts.
- [ ] Run a fresh isolated install using the committed lockfile, then the installed entrypoint from outside source cwd. Run `uv run --locked pytest -q`, `uv run --locked ruff check .`, `uv run --locked ruff format --check .`, `git diff --check`, and the explicit browser test command. Record results and any actual warnings/limitations.
- [ ] Commit focused acceptance/cleanup changes. Request **one independent whole-branch review using GPT-6 Astra, High reasoning**, if available, against the new V2 branch base and full spec/plan. Give reviewer the calculation/uncertainty/migration/privacy focus, and require important findings with file references. Do not spawn implementation subagents. If unavailable, report the actual fallback review method; do not claim independent Astra review occurred.
- [ ] Address important findings with failing regression → fix → relevant/full checks. Recheck affected browser flows after UI fixes. Review the final diff for private data and unintended deletion. Mark every task complete only with evidence; record unresolved findings explicitly. Finish with setup/launch/upgrade/recovery commands, test/browser results, limitations, and the manual acceptance checklist below. Do not merge/push/publish.

## Manual acceptance checklist

- [ ] Old snapshot portfolios open and remain editable; 100-holding totals and row numbers remain readable.
- [ ] Create a full-history account and an opening-balance account without guessed history.
- [ ] Import transactions twice; verify no duplicate shares. Two legitimate identical trades can both be retained deliberately.
- [ ] Verify fee-inclusive FIFO example: remaining 3 shares/basis 363 and realized gain 542; explicit allocation produces the documented alternate result.
- [ ] Partial sale from unknown opening lots displays unresolved basis/gain; supplied basis resolves it with an audit reason.
- [ ] Dividend/reinvestment, split, and two-account transfer preserve their documented quantities, dates, basis and income meanings.
- [ ] A historically invalid correction is rejected without partially changing either account.
- [ ] Missing/pre-split prices show unknown valuation; a suitable dated price resolves it.
- [ ] Dated broker statement matches the appropriate historical position; a later correction makes saved reconciliation stale.
- [ ] Complete exports, restart, backup, and offline restore work with synthetic data; account/report filters never truncate complete data exports.

## Self-review record

Spec coverage: persistence/recovery → Task 1/4; calculations/uncertainty → Tasks 2–3; generic exchange → Task 5; prices/completeness → Task 6; reconciliation → Task 7; coexistence/navigation → Task 8; entry/lot workflows → Task 9; polished reconciliation/recovery → Task 10; cleanup/evidence/review → Task 11. All five review-focus cases have named regression ownership. Domain signatures are defined once above and reused. No task authorizes live data testing, tax completeness, deployment, or removal of snapshot mode.
