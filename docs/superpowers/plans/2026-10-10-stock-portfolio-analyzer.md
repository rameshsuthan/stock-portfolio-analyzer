> Historical V1 record. Current release: [Portfolio Ledger V2](../specs/2026-10-11-portfolio-ledger-v2-design.md). Original acceptance claims below are unchanged.

# Stock Portfolio Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:executing-plans** for native, task-by-task implementation. The user has already selected native execution; do not ask them to select an execution method again. Implementation begins only when requested after plan review. Steps use checkboxes for tracking.

**Goal:** Build a maintainable local application for analyzing, editing, saving, and exchanging the owner's portfolio snapshots.

**Architecture:** A Streamlit interface calls shared validation and calculation modules, with SQLite providing local persistence. Calculations remain independent of the UI and database.

**Tech Stack:** Python 3.14.3, Streamlit, pandas, Plotly, standard-library `decimal` and `sqlite3`, pytest, Ruff, and uv.

**Spec:** [Stock Portfolio Analyzer — Approved Design](../specs/2026-10-10-stock-portfolio-analyzer-design.md). Read the spec before executing this plan. The original [project brief](../../../Stock%20Portfolio%20Analyzer%20-%20Project%20Brief.md) contains proposed defaults that this design revises.

**Handoff status:** Only the design and plan have been written. Application implementation, dependency installation, and test execution have not started. The existing brief has not yet been updated.

## Global constraints

- Local, single-user operation; no database server, ORM, separate API service, or deployment infrastructure.
- Python 3.14.3; Streamlit, pandas, and Plotly remain the selected stack.
- Independent named portfolios of long USD stocks and ETFs, including fractional shares; one consolidated row per symbol per snapshot.
- Both CSV import and in-app editing belong in v1 and must use the same validation rules.
- `cost_basis` is the authoritative total acquisition cost; average cost per share is derived.
- Complete dated snapshots, one per portfolio/date; confirmed atomic replacement for same-date corrections.
- Decimal precision is preserved through calculations, SQLite storage, and snapshot CSV round trips; display rounding is separate.
- Keep personal data and credentials out of Git; use synthetic data for tests and course evidence.
- Live prices, transactions, realized gains, cash, multiple currencies, short positions, derivatives, benchmark comparisons, combined-account analysis, hosting, and in-app AI remain later work.

## Review focus

These cases must be exercised in the owning task, not left to general smoke testing:

1. Text identifiers such as `NA`, BOM-prefixed headers, and headers that collide after normalization: preserve valid text and report ambiguity (Task 2).
2. Exported metadata that conflicts across rows or an analysis report uploaded as a snapshot: reject clearly rather than silently assigning the wrong portfolio/date (Task 2).
3. A replacement that fails after deleting old rows but before inserting all new rows: roll back and preserve the previous snapshot (Task 3).
4. Streamlit reruns and switching datasets with unsaved edits: retain drafts on rerun and require discard acknowledgment on navigation (Task 4).
5. Filtering immediately before saving or full export: persist/export the complete draft, never just the visible selection (Tasks 4 and 5).

## 1. Agreed scope and contracts

### First usable release

- Independent named portfolios containing long USD stocks and ETFs.
- One consolidated holding per symbol within each snapshot.
- CSV import and in-app addition, editing, and removal of holdings.
- Complete dated snapshots, persistent across restarts.
- Allocation, unrealized gain/loss, shared filters, and two export formats.
- Synthetic demo data, practical documentation, and course demonstration materials.

### Holding contract

| Field | Rule |
| --- | --- |
| `symbol` | Required; trimmed, uppercase, unique within the snapshot |
| `quantity` | Required positive decimal; fractional shares allowed |
| `cost_basis` | Required nonnegative total acquisition cost |
| `current_price` | Required nonnegative price per share |
| `company_name` | Optional; defaults to symbol |
| `sector` | Optional; defaults to `Unknown` |

Average cost becomes a derived value. ETF allocation uses the supplied classification without examining underlying holdings.

### Calculation contract

- Market value = quantity × current price.
- Unrealized gain/loss = market value − cost basis.
- Average cost = cost basis ÷ quantity.
- Gain/loss percentage = gain/loss ÷ cost basis × 100.
- Portfolio percentages use aggregate totals, never averages of holding percentages.
- Allocation uses the market value of the active selection.
- Undefined percentages are `None` internally, `N/A` in the UI, and blank in reports.
- Preserve decimal inputs through calculations, storage, and snapshot exports. Round displayed money and percentages to two decimal places.

### Snapshot contract

- Required portfolio name and prices-as-of date; currency is USD.
- One saved snapshot per portfolio/date.
- Every save contains the entire holdings set, independent of dashboard filters.
- Same-date replacement requires explicit confirmation and an atomic database transaction.
- Drafts remain in session memory until saved. Confirm discarding changes during in-app navigation; browser closure can lose unsaved drafts.
- Default to the latest snapshot by date. Confirm snapshot and portfolio deletion.

## 2. Structure and interfaces

Use a thin `app.py` entry point and a `src/stock_portfolio/` package with these responsibilities:

| Module | Responsibility |
| --- | --- |
| `models.py` | Holding, snapshot, validation, selection, and analysis types |
| `validation.py` | Shared normalization and validation for CSV and editor input |
| `csv_io.py` | CSV parsing, snapshot export, analysis export |
| `calculations.py` | Pure holding calculations, filtering, totals, and allocations |
| `storage.py` | SQLite initialization, transactions, and portfolio/snapshot operations |
| `workflow.py` | Draft lifecycle, save confirmation, and dataset transitions |
| `ui.py`, `charts.py` | Streamlit controls and Plotly presentation |

Use matching test modules. Keep database access and Streamlit imports out of the calculation core.

The main interfaces are:

- `validate_rows(rows) -> ValidationResult`: returns normalized holdings or structured errors with row and column references.
- `parse_csv(content: bytes) -> ParsedCSV`: returns editable input rows, optional snapshot metadata, and warnings; structural failures raise `CsvFormatError`.
- `analyze(holdings, selection) -> Analysis`: returns selected holding metrics, totals, holding count, and stock/sector allocations.
- `save_snapshot(portfolio_id, snapshot_date, holdings, replace=False) -> Snapshot`: rejects an existing date unless replacement is explicitly authorized.
- `export_snapshot(snapshot) -> bytes` and `export_analysis(analysis, metadata) -> bytes`.

For selections, `None` means all values; an empty selection means no holdings.

SQLite uses `portfolios`, `snapshots`, and `holdings` tables, foreign keys, and a unique portfolio/date constraint. Store authoritative decimal values as text. Record schema version 1; reject unsupported versions without altering them.

## 3. Implementation sequence

For each behavioral task: write the focused tests, verify the expected failure, implement, run the targeted checks, and commit the completed change. Follow `superpowers:executing-plans` for execution checkpoints and workspace handling. Do not treat this document-writing session as the start of implementation.

### Task 1 — Establish the calculation core

**Files:** Project configuration (`pyproject.toml`, `.python-version`, `uv.lock`), `src/stock_portfolio/models.py`, `src/stock_portfolio/calculations.py`, `tests/test_calculations.py`, and the existing project brief.

**Interfaces:** Define the shared types and produce `analyze(holdings, selection) -> Analysis` for the CSV, workflow, and dashboard tasks.

- [ ] Confirm the approved design and plan are available in the execution checkout. Update the brief's conflicting assumptions: persistence, total-cost input, required snapshot dates, and both editing paths.
- [ ] Establish the package, Python environment, dependency lock, pytest, and Ruff configuration.
- [ ] Write failing calculation tests for the two-row example, unequal cost-basis weighting, fractional inputs, zero denominators, and empty selections.
- [ ] Implement domain types and pure calculations, including filtering and undefined percentages.
- [ ] Verify with `uv run --locked pytest tests/test_calculations.py -q`; all targeted tests must pass.
- [ ] Commit the completed calculation-core task.

**Acceptance:** The original two-holding example, using total cost basis of $1,000 per holding, produces $2,100 value, $100 gain, 5% gain, and displayed allocations of 57.14% and 42.86%.

### Task 2 — Implement shared validation and CSV exchange

**Files:** `src/stock_portfolio/validation.py`, `src/stock_portfolio/csv_io.py`, shared models as needed, `tests/test_validation.py`, `tests/test_csv_io.py`, and synthetic sample/template CSVs.

**Interfaces:** Consume Task 1's holding, snapshot, and analysis types. Produce `validate_rows`, `parse_csv`, `export_snapshot`, and `export_analysis` as defined above.

- [ ] Add failing tests for valid input, malformed files, duplicate normalized headers/symbols, missing fields, invalid numbers, and metadata consistency.
- [ ] Implement UTF-8 and UTF-8 BOM handling, header normalization, and plain-decimal parsing. Preserve identifiers such as `NA` as text.
- [ ] Return actionable errors without silently dropping rows or substituting zero. Warn about ignored extra columns.
- [ ] Implement complete snapshot export and filtered analysis export.
- [ ] Verify with `uv run --locked pytest tests/test_validation.py tests/test_csv_io.py -q`; all targeted tests must pass.
- [ ] Commit the completed validation and CSV task.

**Export decisions:** Snapshot CSVs preserve full input precision and repeat portfolio/date/currency metadata consistently across rows. Metadata pre-fills editable import controls; metadata-free templates use those controls directly. Generated files include an `export_kind` marker; analysis reports are rejected as snapshot imports.

**Acceptance:** Exporting and re-importing a snapshot preserves normalized holdings and metadata exactly. Test inconsistent metadata, analysis-report rejection, BOMs, `NA`, and header normalization collisions explicitly.

### Task 3 — Implement transactional persistence

**Files:** `src/stock_portfolio/storage.py`, shared models as needed, and `tests/test_storage.py`.

**Interfaces:** Consume validated holdings and snapshot metadata. Produce portfolio creation/listing/deletion, snapshot listing/loading/deletion, and `save_snapshot(portfolio_id, snapshot_date, holdings, replace=False) -> Snapshot`.

- [ ] Write failing tests for portfolio creation/listing, snapshot save/load/list/delete, confirmed replacement, and portfolio deletion.
- [ ] Implement unique, trimmed, case-insensitive portfolio names and complete snapshot persistence.
- [ ] Test replacement failure midway through the operation: the original snapshot must remain intact.
- [ ] Test reopening a database and rejecting unsupported schemas without modifying data.
- [ ] Verify with `uv run --locked pytest tests/test_storage.py -q`; all targeted tests must pass.
- [ ] Commit the completed persistence task.

**Acceptance:** Repeated imports cannot silently create duplicate dates or partially overwrite saved holdings. Use temporary test databases, never the owner's real database.

### Task 4 — Implement import and editing workflows

**Files:** `app.py`, `src/stock_portfolio/workflow.py`, `src/stock_portfolio/ui.py`, `tests/test_workflow.py`, and `tests/test_app.py`.

**Interfaces:** Consume Tasks 1–3's validation, parsing, calculation, and repository operations. Produce the draft lifecycle and UI controls used by Task 5.

- [ ] Write failing tests for draft transitions, invalid drafts, discard confirmation, replacement confirmation, and save failures.
- [ ] Add portfolio/snapshot selection, sample loading, CSV upload, and an editor supporting row addition and deletion.
- [ ] Keep editable decimal fields as strings; pass CSV and editor rows through the same validator.
- [ ] Preserve edits across ordinary Streamlit reruns. Reset editor state and filters when deliberately loading another dataset.
- [ ] Clearly label draft versus saved analysis; block analysis/export/save for invalid drafts.
- [ ] Verify with `uv run --locked pytest tests/test_workflow.py tests/test_app.py -q`, including a Streamlit startup smoke test.
- [ ] Commit the completed workflow task.

**Acceptance:** Both import and editing paths can create a valid snapshot; failed saves preserve the draft. Filters cannot change what gets saved. Loading the sample does not automatically persist it.

### Task 5 — Build the dashboard and connect exports

**Files:** `src/stock_portfolio/ui.py`, `src/stock_portfolio/charts.py`, and the calculation, CSV, workflow, and app test modules as needed.

**Interfaces:** Consume the single `Analysis` result from `analyze`, the complete validated draft, and Task 2's two export functions. Do not duplicate financial calculations in UI or chart code.

- [ ] Add failing tests for shared filter behavior, report consistency, and complete snapshot export while filters are active.
- [ ] Implement headline cost basis, value, gain/loss, gain/loss percentage, and holding count.
- [ ] Add the sortable holdings table, allocation charts, and gain/loss bar chart with a zero baseline.
- [ ] Connect intersecting symbol/sector filters to one shared analysis result used by every view and report export.
- [ ] Display USD, snapshot date, manual price source, and selected scope.
- [ ] Handle empty selections, missing sectors, zero market value, and undefined percentages.
- [ ] Verify with `uv run --locked pytest tests/test_calculations.py tests/test_csv_io.py tests/test_workflow.py tests/test_app.py -q`, then check filter consistency in the browser.
- [ ] Commit the completed dashboard task.

**Acceptance:** Filtering to `DEMO_A` produces $1,000 basis, $1,200 value, $200 gain, 20% gain, and 100% allocation. Full snapshot export still includes both holdings.

### Task 6 — Finish local operation and course readiness

**Files:** Runtime configuration, `.gitignore`, `.streamlit/config.toml`, `README.md`, project documentation and synthetic course evidence, plus focused configuration tests where needed.

**Interfaces:** Configure the storage location consumed by the application and document the supported setup/run/test commands.

- [ ] Default the database to `~/.stock-portfolio-analyzer/portfolio.sqlite3`; allow `PORTFOLIO_DATA_DIR` override.
- [ ] Bind Streamlit to localhost and disable usage telemetry.
- [ ] Ignore private data directories, database files and sidecars, credentials, environment files, and generated private reports. Keep synthetic CSV fixtures tracked.
- [ ] Document setup, schema, editor behavior, snapshot replacement, exports, troubleshooting, and backup/restore with the app stopped.
- [ ] Maintain a development log and synthetic-data demo script covering import, validation, editing, saving, reopening, filtering, and export.
- [ ] Run full verification and manually exercise both input workflows in the browser.
- [ ] Review staged files for personal data and commit the completed release-preparation task.

**Acceptance:** A fresh environment launches the app using documented commands, and the course demonstration uses only synthetic data. Publishing or submitting materials is a separate action.

## 4. Verification and release checks

| Scenario | Expected result |
| --- | --- |
| Unequal cost bases: $100 and $900; gains $10 and −$90 | Portfolio gain/loss is −8%, not the average of row percentages |
| Fractional holding: quantity `0.1`, basis `0.02`, price `0.3` | Value `0.03`, gain `0.01`, gain percentage 50% |
| Zero basis or all-zero market value | Monetary totals remain valid; affected percentages unavailable |
| Empty filter selection | Clear empty state; analysis export disabled |
| Missing, malformed, negative, or nonfinite input | Actionable errors; no partial analysis or persistence |
| CSV → SQLite → CSV → import | Holdings, precision, and metadata preserved |
| Interrupted replacement | Previous saved snapshot unchanged |
| Rerun, dataset switch, and application restart | Draft behavior is predictable; saved data persists |
| Filtered dashboard followed by save | Complete draft saved |
| Git review after demonstration | Only code, documentation, and synthetic evidence staged |

Final automated checks:

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Also complete a browser walkthrough of upload, editing, confirmation dialogs, downloads, and restart persistence using a temporary data directory. Do not claim upload/editor browser behavior is verified solely from unit or startup smoke tests.

## 5. Defaults and execution handoff

- Use Python 3.14.3, already installed locally when planning. Streamlit documents support for Python 3.14: [supported Python versions](https://docs.streamlit.io/get-started/installation/command-line).
- Resolve compatible dependencies during implementation and commit `uv.lock`. Subsequent setup and execution use `--locked`: [uv locking](https://docs.astral.sh/uv/concepts/projects/sync/).
- Bound inputs to 10 MB and 10,000 holdings. Use a 50-digit Decimal context with at most 18 significant digits and eight decimal places per input; reject values beyond these documented limits.
- Raw uploaded files are not automatically retained. Backups, exports, and personal screenshots stay outside Git.
- Only the design and plan documents have been saved at this handoff. No application code or dependencies have been implemented or installed.
- Preserve the user's choice of **superpowers:executing-plans** and native execution. Do not re-run brainstorming or ask the user to choose between native and subagent-driven execution.

Suggested prompt for a new execution session:

> Use superpowers:executing-plans to implement docs/superpowers/plans/2026-10-10-stock-portfolio-analyzer.md. Read the linked approved design first. Use native execution, work through the plan task by task, and verify each milestone. Keep personal portfolio data and credentials out of Git. The design is approved, and this request authorizes execution of the plan. Do not publish or submit course materials.
