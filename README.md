# Stock Portfolio Analyzer

A local, single-user Streamlit app for independent named portfolios of long USD stocks and ETFs. Import or edit complete dated snapshots, save them locally, and inspect allocation and **unrealized gain/loss based on supplied prices**. No live prices, brokerage connections, external services, API keys, trading, or in-app AI.

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

## Import, edit, and save

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

V1 excludes transactions, realized gains, cash, shorts, derivatives, multiple currencies, historical performance, benchmark comparisons, combined-account analysis, hosting, and multi-user access.

## Storage, privacy, and backup

SQLite schema version 1 has `portfolios`, `snapshots`, and `holdings`, foreign keys with cascade deletion, a unique portfolio/date constraint, and TEXT decimal columns. Unsupported versions are rejected without modifying their database. Replacement uses one transaction; failed replacement restores previous rows. Failed saves leave the session draft available.

Raw uploads are held in session memory and are not automatically written to disk. The database is local and unencrypted; protect your OS account and disk. Private data, SQLite files and sidecars, credentials, environment files, exports, reports, and backups are ignored by Git. Only synthetic CSVs belong in commits.

To back up: stop **every app process** using the database, copy the entire data directory (including any SQLite sidecars) to a private backup location, then restart. To restore: stop the app, preserve a copy of the current directory, replace the data directory with the whole backup, and restart with the same `PORTFOLIO_DATA_DIR`. Do not copy a live database file alone or hand-edit its schema version.

## Verification

```sh
uv sync --locked
uv run --locked pytest -q
uv run --locked ruff check .
uv run --locked ruff format --check .
```

Tests use synthetic data and temporary databases. They cover independent calculation examples, strict validation, precision round trips, interrupted replacement rollback, schema rejection, restart persistence, session transitions, and Streamlit integration. Canvas editor test events use browser-shaped widget deltas; actual browser upload/edit verification is recorded separately in [development log](docs/development-log.md).

For a manual check, upload `samples/demo.csv`, confirm $2,000 basis / $2,100 value / $100 gain / 5%, edit quantity, save and reopen, then filter to DEMO_A and compare $1,000 / $1,200 / $200 / 20%. Full export must still contain both rows. Follow [demo script](docs/demo-script.md) for the full acceptance walkthrough.

## Troubleshooting

- Run from the repository root and use `uv sync --locked` to restore the recorded environment. Do not regenerate the lockfile for ordinary setup.
- If port 8501 is occupied, stop the other instance or add `--server.port 8502`.
- If storage cannot open, check the override directory and file permissions. For an unsupported schema, use a compatible release or restore a known-good backup; never reset `user_version`.
- A locked database usually means another app process is writing to it; stop it and retry. The draft remains available.
- Invalid numeric cells block the whole analysis; correcting the table is preferable to silently excluding holdings.

See the [approved design](docs/superpowers/specs/2026-10-10-stock-portfolio-analyzer-design.md) and [implementation plan](docs/superpowers/plans/2026-10-10-stock-portfolio-analyzer.md). Course publication and submission remain separate manual actions.
