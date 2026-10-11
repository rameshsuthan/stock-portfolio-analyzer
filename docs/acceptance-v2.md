# Portfolio Ledger V2 acceptance and recovery

Branch: `feature/portfolio-ledger-v2`, based on V1 planning commit `6b14063`.
Worktree: `/Users/ramesh/code/mastering-agentic-ai-v2/stock-portfolio/.worktrees/portfolio-ledger-v2`.
All automated exercises use synthetic records, temporary databases and an isolated Edge profile. No owner database was used. The V1 worktree remains available.

## Launch an isolated demonstration

```sh
cd /Users/ramesh/code/mastering-agentic-ai-v2/stock-portfolio/.worktrees/portfolio-ledger-v2
uv sync --locked
portfolio_demo_dir=$(mktemp -d /private/tmp/portfolio-ledger-v2-demo.XXXXXX)
PORTFOLIO_DATA_DIR="$portfolio_demo_dir" uv run --locked streamlit run app.py
```

Keep the printed directory if you want to reopen this demonstration. Stopping the app does not delete its database. Select **Transaction accounts** to use the ledger; **Snapshots** retains the original workflow. Fixture instructions and independent expected totals are in [samples/ledger/README.md](../samples/ledger/README.md).

## Upgrade and recovery

For an intentional upgrade, stop every app process using the intended data directory, keep your existing backup, then launch V2 with `PORTFOLIO_DATA_DIR` set explicitly to that directory. The first V1→V2 open creates and verifies a `*.pre-migration-*.db` backup before committing the migration. V1 cannot open schema 2. Returning to V1 requires restoring a V1 backup after stopping all clients.

Use **Data & recovery → Backup & offline recovery** to prepare and download a consistent backup. A database backup retains audit, receipts and reconciliation history; CSV files exchange active data only.

With **all app processes and SQLite writers stopped**:

```sh
uv run --locked python -m stock_portfolio.backup restore \
  --source /path/to/known-good-backup.sqlite3 \
  --destination /path/to/data/portfolio.sqlite3 \
  --confirm-stopped
```

The destination must already exist. Restore validates a staged copy and preserves the destination in a new `*.pre-restore-*.db` before atomic replacement. Remaining WAL/journal sidecars cause refusal. The tool relies on the operator stopping all clients; it cannot prove exclusivity over arbitrary external programs.

## Verification record

- Locked fresh isolated environment: 169 non-browser tests passed; installed UI import worked outside source cwd.
- Ruff lint, formatting and Git whitespace checks passed.
- Isolated Edge ledger scenario: imports/no-op/duplicates, trade cancel/confirm, explicit lot choices, supplied pool basis, reinvestment/split/transfer, dated prices, reconciliation mismatch/correction/staleness/recalculation, downloads/backup and restart passed.
- Isolated Edge snapshot scenario: actual upload and canvas edit, dirty navigation, replacement cancel/confirm, downloads and restart passed. Quantity 10→11 yields $2,220 value.
- 10,000-event service measurements: preview 0.613s, commit 0.399s, load/replay 0.137s. Initial full browser measurement: preview 2.217s, commit 1.567s, including UI settling. Timings describe this machine, not a cross-hardware threshold.
- Offline restore CLI exercised successfully against temporary synthetic V2 databases; both restored and pre-restore recovery contents verified.
- Combined extended Edge suite: **2 passed in 128.43s**. Includes priced 100-holding charts, filtered report download, and viewport checks at 1440×900, 1366×900, 1024×768 and 768×900. No metric overflow measured; screenshots inspected. [Synthetic evidence](evidence/ledger-v2/overview-1440.png), [charts](evidence/ledger-v2/charts-1440.png), [measurements](evidence/ledger-v2/measurements.json). Final 10,000-event browser preview 0.852s / commit 0.937s.
- Independent Astra High review is in progress.

## Manual acceptance checklist

- [ ] Open/edit old snapshots; inspect totals and row numbers with the 100-holding sample.
- [ ] Create full-history and opening-balance accounts without inventing earlier trades.
- [ ] Import transactions twice: second import is a no-op. Deliberately keep both legitimate identical occurrences.
- [ ] Verify FIFO fees: remaining 3 shares / basis 363, realized gain 542. Compare the explicit-allocation alternative.
- [ ] Partially sell an aggregate opening pool: gain stays unresolved until supplied basis and reason are recorded.
- [ ] Verify paired dividend/reinvestment, split and transfer quantities, basis, dates and income.
- [ ] Attempt a correction that invalidates a later destination-account sale: neither account should change.
- [ ] Check missing/pre-split price status; supply a suitable dated observation.
- [ ] Compare a complete historical broker statement; correct an event and confirm old evidence becomes stale.
- [ ] Filter a report, then confirm complete data exports remain complete. Restart, back up and restore only a disposable synthetic database during acceptance.

## Limits

USD, long-only local tracking with user-supplied prices and records. No tax filing/wash sales, cash balances, FX, shorts, derivatives, mergers/spinoffs, cash-in-lieu settlement, combined-account analytics or multi-user hosting. Aggregate openings deliberately preserve unknown acquisition history and basis allocation. Narrow tables scroll horizontally; chart summaries do not replace complete tables/exports. SQLite backups are unencrypted private data. Browser verification is headless Edge with fresh profiles; no live brokerage integration or personal profile is exercised.
