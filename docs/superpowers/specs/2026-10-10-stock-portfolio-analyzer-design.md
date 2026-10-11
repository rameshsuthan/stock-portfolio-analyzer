# Stock Portfolio Analyzer — Approved Design

**Date:** 2026-10-10

**Status:** Design approved in conversation. Application implementation has not started.

**Implementation plan:** [Stock Portfolio Analyzer Implementation Plan](../plans/2026-10-10-stock-portfolio-analyzer.md)

**Starting references:** [Project brief](../../../Stock%20Portfolio%20Analyzer%20-%20Project%20Brief.md) and [course handout](../../../Week%201%20Project%20Handout%20%28Oct%202026%29.md).

This design supersedes conflicting proposed defaults in the original brief. It preserves the distinction between course requirements and personal-use product choices.

## Purpose and release boundary

Build an intermediate-level, maintainable local application that the owner can trust with personal holdings, reopen later, and update through repeatable imports or table edits. The course submission is the first demonstration, not the end of the application's useful life.

The first usable release supports independent named portfolios of long USD stocks and ETFs, including fractional shares. Each portfolio snapshot contains one consolidated row per symbol. The same symbol may appear in different portfolios. Analyze one portfolio and one snapshot at a time.

V1 includes CSV imports, table editing, saved dated snapshots, allocation, unrealized gain/loss, and exports. Live prices, brokerage integrations, transaction history, realized gains, cash, multiple currencies, short positions, derivatives, benchmark comparisons, combined-account analysis, hosting, and in-app AI remain later work.

## Confirmed workflow decisions

- Start with an app-defined CSV template, rather than a brokerage-specific importer.
- Support both CSV replacement and in-app editing in v1.
- Use total cost basis as authoritative input; derive average cost per share.
- Store named portfolios and dated snapshots in SQLite.
- Keep one snapshot per portfolio/date; confirm replacement for same-date corrections.
- Use native execution through `superpowers:executing-plans` after the implementation plan is reviewed.

## Data and calculations

| Field | Rule |
| --- | --- |
| `symbol` | Required; trim surrounding whitespace, normalize to uppercase, and require uniqueness within the snapshot. |
| `quantity` | Required positive decimal; fractional shares are allowed. |
| `cost_basis` | Required nonnegative total acquisition cost for the holding. |
| `current_price` | Required nonnegative price per share supplied by the user. |
| `company_name` | Optional; use the symbol when missing or blank. |
| `sector` | Optional; use `Unknown` when missing or blank. |

ETF sectors describe the fund as entered, without looking through to its underlying holdings.

- Holding market value = quantity × current price.
- Holding unrealized gain/loss = market value − cost basis.
- Average cost per share = cost basis ÷ quantity.
- Gain/loss percentage = gain/loss ÷ cost basis × 100 when cost basis is positive.
- Portfolio cost basis and market value are sums over the active selection.
- Portfolio gain/loss percentage comes from portfolio totals, never an average of holding percentages.
- Stock and sector allocation percentages use the active selection's market value as the denominator.
- Undefined percentages are `None` internally, `N/A` in the interface, and blank in analysis CSVs.

Preserve decimal inputs through calculation, database storage, and complete snapshot export. Round displayed money and percentages to two decimal places. Never use displayed or browser floating-point values as authoritative calculation inputs.

If the selected market value is zero, explain that allocation percentages are unavailable and omit allocation charts. Empty filter results have an explicit empty state. Label all results as unrealized gain/loss based on supplied prices, not total return or investment performance.

## Import, editing, and saving

Accept UTF-8 CSVs, including UTF-8 BOM files. Normalize header whitespace and case. Reject malformed CSVs, duplicate normalized headers, missing required fields, nonfinite values, invalid numeric values, and duplicate normalized symbols. Plain decimal input is required; currency symbols and thousands separators are not accepted. Report extra columns as ignored. Preserve text identifiers such as `NA` instead of interpreting them as missing values.

Both input paths call the same validator. Validation identifies affected rows and columns, never silently drops rows, and never substitutes zero for invalid data. Structural CSV errors require correction and re-upload; editable row errors can be corrected in the app. Invalid drafts cannot be saved, exported as valid snapshots, or analyzed as an apparently complete portfolio.

The editor supports adding, changing, and removing holdings. At least one valid holding is required to save a snapshot. Require a portfolio name and prices-as-of date. Distinguish draft analysis from saved data.

Each save is a complete snapshot, independent of dashboard filters. Replacing an existing portfolio/date requires explicit confirmation and an atomic transaction. Holdings absent from the replacement draft are absent from the saved replacement. A failed save preserves the draft and the previous saved snapshot.

Drafts stay in session memory until saved. Ordinary Streamlit reruns preserve edits. Switching datasets requires acknowledgment before discarding unsaved changes; closing the browser can lose unsaved drafts. Load the latest snapshot date by default and allow older snapshots to be opened individually. Confirm deletion of snapshots and portfolios.

## Persistence and exports

Use Python's built-in SQLite support with tables for portfolios, snapshots, and holdings, foreign keys, and a unique portfolio/date constraint. Store decimal values in text columns to avoid float conversion. Use schema version 1 and reject unsupported schema versions without modifying the database. A database server, ORM, and separate API service are unnecessary.

Provide two distinct downloads:

1. **Complete snapshot CSV:** ignores dashboard filters and preserves authoritative holdings plus portfolio name, date, and currency metadata. Importing it pre-fills editable target/date controls for review. Metadata must be consistent across rows.
2. **Analysis CSV:** contains the selected holdings and calculated metrics. Label it as a report. Generated exports have an `export_kind` marker; reject analysis reports as snapshot imports.

Metadata-free templates receive their portfolio and date from the interface. Complete snapshot CSV round trips must preserve normalized holdings, metadata, and numeric precision. Document whole-database backup and restore with the application stopped.

## Interface and component boundaries

Provide a portfolio/snapshot selector, an import/editor area, and an analysis area. Show cost basis, value, unrealized gain/loss amount and percentage, holding count, a sortable holdings table, stock and sector allocation, and a gain/loss chart with a visible zero baseline.

Symbol and sector filters intersect and consistently affect metrics, charts, the table, and analysis export. Label filtered results as applying to the selected holdings. Reset filters when the underlying holdings change. Full snapshot export and saving always use the complete draft. Show currency, snapshot date, and manual price source.

Keep CSV handling, validation, pure calculations, SQLite access, draft workflow, and rendering in separate modules. pandas provides tabular presentation and Plotly provides charts. Use string-backed decimal inputs in Streamlit's editor, passing values through shared validation before calculations.

## Local operation, privacy, and setup

Store the database outside the repository at `~/.stock-portfolio-analyzer/portfolio.sqlite3` by default, with `PORTFOLIO_DATA_DIR` as an override. Raw uploaded files are not automatically retained. Ignore private data directories, databases and sidecars, credentials, environment files, and generated private reports in Git. Commit only synthetic sample data and demonstration evidence.

Bind the application to localhost and disable usage telemetry. No external services or API credentials are needed for v1.

Use the installed Python 3.14.3 with a project environment and committed `uv.lock`. Document locked setup, launch, and verification commands. Streamlit documents Python 3.14 support, and uv supports enforcing the committed lockfile:

- [Streamlit Python support](https://docs.streamlit.io/get-started/installation/command-line)
- [Streamlit editor API](https://docs.streamlit.io/develop/api-reference/data/st.data_editor)
- [uv locking and syncing](https://docs.astral.sh/uv/concepts/projects/sync/)

The implementation plan sets these practical bounds: 10 MB per upload, 10,000 holdings, a 50-digit Decimal context, and at most 18 significant digits and eight decimal places per numeric input. Reject values beyond the documented bounds rather than silently rounding them.

## Acceptance and course milestone

Independently verify calculations, fractional shares, unequal cost-basis weighting, zero denominators, invalid imports, filter consistency, CSV/database round trips, restart persistence, atomic replacement rollback, and both editing workflows.

The two-row example uses `DEMO_A` with quantity 10, total cost basis 1000, and price 120; and `DEMO_B` with quantity 5, total cost basis 1000, and price 180. Expected portfolio totals are cost basis 2000, value 2100, unrealized gain 100, and gain percentage 5%. Display allocations as 57.14% and 42.86%.

Use synthetic holdings for screenshots, the development log, and a video demo of no more than five minutes. Prepare practical project documentation and course evidence. Publishing the repository or submitting course materials is a separate action.
