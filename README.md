# Stock Portfolio Analyzer

A local, single-user Streamlit app for long USD stocks and ETFs. Portfolio Ledger V2 retains editable snapshots and adds separate transaction accounts with revisioned events, FIFO or explicit lot allocations, dated prices, and broker holdings reconciliation. No live prices, brokerage connections, cloud service, telemetry, or in-app AI.

## Setup and launch

Install Python 3.14.3 and uv, then run from this repository root:

```sh
uv sync --locked
uv run --locked streamlit run app.py
```

Open http://127.0.0.1:8501. The committed configuration binds to localhost and disables usage telemetry. Launch from the repository root so Streamlit reads `.streamlit/config.toml`.

The default database is `~/.stock-portfolio-analyzer/portfolio.sqlite3`, outside Git. Override it for isolated testing:

```sh
PORTFOLIO_DATA_DIR=/tmp/portfolio-analyzer-demo uv run --locked streamlit run app.py
```

Use a new temporary directory for each disposable demonstration. The app creates it. Stop the server with Ctrl-C. Only run one server against a given data directory.

## Transaction accounts

Choose **Transaction accounts** in the sidebar. Create a full-history account or select an end-of-day opening cutoff. Opening activity must precede subsequent trades; an aggregate opening does not invent acquisition dates or prorate unknown sale basis.

- **Overview:** dated holdings, complete totals or known subtotals, separate realized/unrealized gains and recorded dividends. Missing or pre-split prices remain unknown; prices older than seven calendar days are labeled stale.
- **Transactions:** preview and confirm BUY/SELL, dividends, paired reinvestment, splits and tracked-account transfers. Revise, void or revive with a reason. Linked events are saved together; invalid historical corrections roll back across accounts.
- **Lots & realized gains:** inspect provenance and consumed lots; fully allocate a sale/transfer or supply supported aggregate-pool basis. A partial allocation is rejected.
- **Reconcile:** select a statement date, upload complete broker holdings and confirm completeness. Compare at that date. Saved comparisons remain immutable; economic corrections mark them stale. Recalculate creates new evidence.
- **Data & recovery:** separate opening/price imports, shared price corrections, complete exports, snapshot-to-opening conversion, audit history, archiving and database backup.

CSV selection alone never writes data. Preview shows errors, duplicate occurrences and projected positions; confirmation checks the database revision again. The same committed file is a no-op. IDs are account-scoped; conflicting or voided IDs require an explicit correction. Identical ID-less rows require deliberate keep/skip choices, because repeated trades can be legitimate.

Use the [synthetic ledger pack](samples/ledger/README.md) for examples. Transaction headers start with `date,transaction_type,ticker`; BUY/SELL also require `quantity,price`, with fees defaulting to zero. The original five-column `ticker,date,transaction_type,quantity,price` sample is accepted. Multiple accounts requires exact existing `account_name` values. Transfers name a tracked destination in `to_account`. Templates are downloadable in the app; the full contracts are in the [V2 design](docs/superpowers/specs/2026-10-11-portfolio-ledger-v2-design.md).

Complete transaction exports cover all tracked accounts and include stable IDs and allocations. In a fresh dataset create matching account names/cutoffs, import every account's detailed/aggregate opening exports first, then the all-account transaction data and global prices. Reports have distinct kinds and cannot be used as input files. A database backup is the complete recovery format including audit and comparison history.

## Snapshot import, edit, and save

1. Load the synthetic sample, upload a CSV and click **Import uploaded CSV**, or start a blank draft.
2. Review the target portfolio name and required prices-as-of date. Exported snapshot metadata pre-fills these editable controls. Templates without metadata use the current controls.
3. Edit cells in the table. All input columns are text so browser floats cannot alter authoritative decimals. Add a holding using the bottom row; select rows using their checkboxes and use the table's delete action to remove them. Commit a cell with Enter or Tab.
4. Fix every validation error before analysis, saving, or exporting. Errors reference CSV row numbers (header is row 1). Structural errors require re-upload; row errors can be corrected in the editor.
5. Click **Save complete snapshot**. Existing portfolio/date combinations require **Confirm complete replacement**; rows absent from the draft are removed atomically. Cancel leaves saved data unchanged.

Ordinary reruns retain edits. Switching via sample, new draft, import, or opening a saved snapshot requires explicit discard acknowledgment when changes are unsaved. Closing/reloading the browser may lose unsaved drafts. Startup loads the latest date of the first alphabetically listed portfolio; each portfolio selector offers its latest date first. Open older snapshots individually. Deletions require confirmation; the current draft remains available to save again.

Portfolio names are trimmed and unique ignoring case. Each snapshot requires at least one holding; one normalized symbol may occur only once per snapshot. The same symbol can appear in different portfolios.

## CSV contract

See [template](samples/template.csv) and [synthetic sample](samples/demo.csv).

| Column | Rule |
| --- | --- |
| `symbol` | Required, trimmed, uppercase, unique |
| `quantity` | Required positive decimal; fractional shares allowed |
| `cost_basis` | Required nonnegative **total** acquisition cost |
| `current_price` | Required nonnegative supplied per-share price |
| `company_name` | Optional; defaults to symbol |
| `sector` | Optional; defaults to `Unknown` |

UTF-8 and UTF-8 BOM are accepted. Headers ignore case and surrounding whitespace; duplicate normalized headers are rejected. Extra columns are reported as ignored. Identifiers such as `NA` remain text. Numbers must be plain decimals, without currency symbols, thousands separators, exponents, NaN, or infinity. Limits: 10,000,000 upload bytes, 10,000 holdings, 18 significant digits and eight decimal places per input. Calculation precision is 50 digits; display rounding is separate.

**Complete snapshot CSV** always includes all draft holdings and exact decimal inputs, plus repeated `portfolio_name`, `snapshot_date`, `currency=USD`, and `export_kind=snapshot`. Import validates metadata consistency. **Analysis report CSV** includes only the intersecting symbol/sector selection, with calculated metrics and `export_kind=analysis`; it is a report, not an importable snapshot. Undefined percentages are blank in reports and N/A in the dashboard. Store personal downloads outside this repository. Only open trusted CSV text in spreadsheet software, which may interpret text beginning with formula characters.

## Reading and editing a portfolio

Use **Edit holdings** to upload CSVs, update inputs, and save the complete snapshot. Use **Analysis** for totals, filters, downloads, and charts. Both tables show row numbers; the analysis table retains the original holding number after filtering or sorting. CSV validation row numbers include the header, so they are one higher. Financial columns come first in the analysis table; scroll horizontally for company and sector details.

Totals display full amounts. Stock allocation shows the ten largest holdings plus an aggregate “Other holdings”; hover for percentages. Sector bars include every sector, and separate gain/loss charts show up to ten positions each by dollar amount. Tables and reports retain all selected holdings.

## Calculations and scope

Market value is quantity × price. Gain/loss is value − total cost basis. Average cost is basis ÷ quantity. Portfolio gain percentage is aggregate gain ÷ aggregate basis, never the average of holding percentages. Zero cost basis produces undefined gain percentages. Allocation divides selected market values by their sum; zero total value omits allocation charts. ETF sectors describe the supplied fund classification without looking through to underlying holdings.

Filters intersect and affect metrics, the sortable table, charts, and analysis report. They never reduce saved snapshots or complete exports. Changes to holdings reset filters. Empty filter controls mean all symbols or sectors; Reset filters clears both controls. An intersection with no matches shows an empty state and disables analysis download.

Snapshot mode reports only supplied holdings and unrealized gains. Transaction mode supports the scoped events above. Neither mode implements cash balances, tax filing, wash-sale adjustments, mergers/spinoffs, return of capital, fractional-share cash-in-lieu, shorts, derivatives, FX, return rates, benchmarks, combined-account analytics, hosting, or multi-user access. Unsupported history must be resolved externally, never silently forced to reconcile.

## Storage, privacy, and backup

SQLite schema version 2 retains the original snapshot tables and adds accounts, immutable event identities/revisions/heads, audit operations, price revisions, import receipts, statements and comparison evidence. Decimal storage is text. Opening a genuine V1 database first creates and verifies a local SQLite backup; the schema migration and version change then commit together. A failed backup or migration leaves V1 unchanged. Unknown versions are rejected. V1 code intentionally rejects schema 2.

Upgrade: stop all existing app processes, run `uv sync --locked` in the V2 worktree, then launch using the intended `PORTFOLIO_DATA_DIR`. First test with a disposable synthetic directory. Keep the automatically generated `*.pre-migration-*.db` privately for recovery.
Raw uploads are held in session memory and are not automatically written to disk. The database is local and unencrypted; protect your OS account and disk. Private data, SQLite files and sidecars, credentials, environment files, exports, reports, and backups are ignored by Git. Only synthetic CSVs belong in commits.

To back up while running, use **Data & recovery → Prepare consistent database backup → Download database backup**. This uses SQLite's backup API, including committed WAL content. Downloaded files are private. Prepare a new artifact after further changes.

To restore, stop **every app process and other SQLite writer**, then run:

```sh
uv run --locked python -m stock_portfolio.backup restore \
  --source /path/to/known-good-backup.sqlite3 \
  --destination /path/to/data/portfolio.sqlite3 \
  --confirm-stopped
```

The destination must exist. A corrupt or unsupported destination is preserved byte-for-byte for recovery analysis before replacement. Source integrity/schema are checked in a temporary copy; the current destination gets a `*.pre-restore-*.db` recovery backup before atomic replacement. If sidecars remain, stop/checkpoint the owning SQLite clients before retrying. The tool does not stop arbitrary processes or claim exclusive access to other clients. Never reset `user_version`, hand-edit the database, or copy a live main database file alone.

## Verification

V2 results, synthetic screenshots, launch/recovery commands and the manual checklist: [acceptance record](docs/acceptance-v2.md).

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
git diff --check
# Explicit browser suite; requires Microsoft Edge installed:
uv run --locked pytest tests/browser/test_ledger_acceptance.py -m browser -q -s
# Optional isolated bundled Chromium fallback:
uv run --locked playwright install chromium
PORTFOLIO_BROWSER_CHANNEL=chromium uv run --locked pytest tests/browser/test_ledger_acceptance.py -m browser -q -s
```

Normal pytest excludes the marked browser suite; it is not counted as a passing browser test. The explicit harness starts/stops its own server, temporary database and fresh browser profile. Optional `PORTFOLIO_BROWSER_EVIDENCE=/private/tmp/portfolio-evidence` retains synthetic screenshots and timing measurements. Tests use synthetic data and temporary databases. They cover independent calculation examples, strict validation, precision round trips, interrupted replacement rollback, schema rejection, restart persistence, session transitions, and Streamlit integration. Canvas editor test events use browser-shaped widget deltas; actual browser upload/edit verification is recorded separately in [development log](docs/development-log.md).

For a manual check, upload `samples/demo.csv`, confirm $2,000 basis / $2,100 value / $100 gain / 5%, edit quantity, save and reopen, then filter to DEMO_A and compare $1,000 / $1,200 / $200 / 20%. Full export must still contain both rows. Follow [demo script](docs/demo-script.md) for the full acceptance walkthrough.

## Troubleshooting

- Run from the repository root and use `uv sync --locked` to restore the recorded environment. Do not regenerate the lockfile for ordinary setup.
- If port 8501 is occupied, stop the other instance or add `--server.port 8502`.
- If storage cannot open, check the override directory and file permissions. For an unsupported schema, use a compatible release or restore a known-good backup; never reset `user_version`.
- A locked database usually means another app process is writing to it; stop it and retry. The draft remains available.
- Invalid numeric cells block the whole analysis; correcting the table is preferable to silently excluding holdings.

See the [approved V2 design](docs/superpowers/specs/2026-10-11-portfolio-ledger-v2-design.md), [implementation plan](docs/superpowers/plans/2026-10-11-portfolio-ledger-v2.md), and [resumable progress record](docs/implementation-progress-v2.md). V1 specs/evidence are retained as historical records. Course publication and submission remain separate manual actions.
