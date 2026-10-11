# Development log — 2026-10-10

**Current status:** Implementation, independent review fixes, and browser acceptance complete. Final suite: 54 passing tests. See the completed browser acceptance section below.

## Authorized scope and execution

The owner approved the linked design and six-task plan, requested sequential native implementation with test-first behavioral changes, small commits, an independent GPT-6 Astra High review, and real browser verification. No merge, push, publication, or course submission is authorized.

The original checkout contained two untracked planning documents and no application. Those documents were committed separately before creating `feature/portfolio-v1` in `.worktrees/portfolio-v1`. The original course documents were preserved; the project brief now points to the superseding approved design.

## Iterations and verification

1. Calculation tests first failed against the missing implementation; then 5 passed. Decimal calculations cover the two-row example, unequal cost weighting, fractional shares, zero denominators, and intersecting/empty selections.
2. Validation and CSV tests first failed; then 29 focused tests passed. Covered BOMs, `NA`, normalized header collisions, malformed CSV, invalid decimals, limits, metadata consistency, report rejection, and precise snapshot round trips.
3. Persistence tests first failed; then 6 passed. A SQLite trigger aborts the second replacement insert after old rows are deleted; the transaction restores the original snapshot. Reopening and unsupported-schema byte preservation are tested using temporary databases.
4. Workflow/UI tests first failed; then 8 passed. The installed AppTest does not serialize the canvas editor on reruns; integration tests supply browser-shaped WidgetStates. This is not a substitute for actual browser editing. Data-directory configuration was introduced here to ensure tests never use personal storage.
5. Dashboard and chart tests first failed; then the full suite passed 51 tests. One shared analysis drives all views and the report; saving/full export retain every holding. Chart floats are display-only copies.
6. Added locked setup, local-only configuration, private-data ignore rules, backup/restore guidance, and a synthetic demonstration script. Final results and independent review are recorded below as they complete.

## Implementation adjustments

- Introduced the default directory and `PORTFOLIO_DATA_DIR` override in Task 4 rather than Task 6 to isolate UI tests. Cost if wrong: configuration can be relocated without changing storage semantics.
- Deferred Task 5's browser filter check to the final walkthrough because macOS Computer Use permissions were pending. Cost if wrong: browser-only issues remain unknown until that gate.

## Evidence status

Automated evidence uses only synthetic holdings and temporary databases. Browser access was initially blocked by macOS Accessibility/Screen Recording permissions; actual browser outcomes will be recorded only after observed. No screenshots or video are claimed yet. No personal database has been used for verification.

## Independent review and fix pass

GPT-6 Astra with High reasoning independently reviewed the complete branch (`9d2666f..5f9e391`) and reran all 51 original tests. It found no calculation or transactional data-loss defect. Findings:

- Important: the development environment had a stale editable wheel built when the source directory was still empty. Pytest's source-path setting hid a standalone import failure. A new isolated subprocess import test failed first, then passed after `uv sync --locked --reinstall-package stock-portfolio-analyzer`. A separate fresh environment installed all 42 packages with `uv sync --locked` and imported the app successfully without source-path assistance. Fresh builds were already correct; no packaging workaround was required.
- The reviewer rated disappearing ignored-column warnings Minor; the executor regraded it Important because users must see discarded input columns. A real AppTest upload reproduced the missing warning; storing warnings with the loaded draft fixes it across reruns and resets them when switching datasets. The regression failed before the fix and passed afterward.

The fix pass leaves **53 tests passing**, Ruff lint passing, and formatted source. No deferred minor review findings remain. No second review was dispatched.

Review rulings: actual browser behavior remains a separate acceptance gate; explicitly excluded product features remain outside v1; CSV text remains exact with documented spreadsheet formula risk; the course demo script is prepared but no video or publication is claimed. The cost of these choices is respectively pending browser assurance, future work for excluded uses, care opening untrusted CSVs in spreadsheet software, and a remaining owner-recorded video.

## Browser verification status

A localhost Streamlit server was started with a temporary data directory and telemetry disabled. Native browser control repeatedly reported that macOS Accessibility/Screen Recording permissions were not granted, including after the owner reported enabling them and after reconnection. Chrome and in-app browser connector surfaces were unavailable. Permission to use a separate Playwright browser was requested; until it is authorized and exercised, CSV upload, canvas editing, confirmation dialogs, downloads, and restart behavior **are not browser-verified**. Automated coverage and server startup are not substitutes for that walkthrough.

## Completed browser acceptance — Playwright / Edge

The owner explicitly authorized Playwright after the native browser extension/permissions failure. Used an isolated headless Microsoft Edge browser and a disposable `/private/tmp` SQLite directory; no personal browser profile or portfolio database was used. Playwright was installed only in a disposable verification environment, not added to application dependencies.

Observed passes:

- Uploaded the actual synthetic CSV through the file input; expected totals appeared: $2,000 basis, $2,100 value, $100 gain, 5%.
- Edited a real canvas cell to `oops`; row-specific validation appeared and save was disabled. The invalid edit survived a rerun. Correcting quantity to 11 produced $2,220 value.
- Added a fractional DEMO_C holding (0.5 shares, $10 basis, $30 price), producing $2,115 total value. Selected and deleted rows through the table toolbar and returned to $2,100.
- Canceled and confirmed unsaved-draft navigation. Saved snapshots; canceled same-date replacement and confirmed replacement after the UI settled.
- Filtered to DEMO_A: $1,000 basis, $1,200 value, $200 gain, 20%, one holding. Intersecting with Healthcare showed the empty state and disabled the report.
- Downloaded both CSV files through browser download events. The report had only DEMO_A and 100% allocation; complete snapshot retained both holdings and metadata. Re-imported the complete CSV; metadata was restored. Importing the analysis report was rejected.
- Saved a second date, stopped the Streamlit process, restarted against the same temporary database, and reloaded the browser. Latest date and saved totals appeared; the older date could be opened separately.
- Canceled deletion, confirmed deletion of the disposable older snapshot, and confirmed deletion of the disposable portfolio. The draft remained available; SQLite inspection confirmed cascaded removal of test holdings.

Browser discovery: Plotly's default pie labels displayed 57.1% / 42.9%. The approved design requires two decimals. Added a failing label regression, then formatted labels directly from Decimal allocations. The full suite passed **54 tests**, and the restarted browser visibly showed **57.14% / 42.86%**. This was a browser-discovered correction after the independent review, not a second review pass.

Some scripted actions initially raced Streamlit rerenders or focused a canvas cell before its editor opened. Repeating them with settled UI state and visible cell-editor checks passed; no production workaround was needed.

[Verified synthetic dashboard screenshot](evidence/synthetic-dashboard.png). No video was recorded or submitted. Browser acceptance is now complete; the prior blocked status above is historical. Scope remains local desktop v1, and no merge, push, hosting, or publication occurred.

## 2026-10-11 — large-portfolio UI refinement

Approved after reproducing the user's 100-stock layout concerns. The Analysis tab now starts with compact filters and full monetary totals; Edit holdings contains import, inputs, and saving. Both tables have row numbers, and financial columns appear first in the analysis table. Empty filters mean all; Reset filters restores all holdings. Stock allocation groups positions after the largest ten into Other holdings. Sector bars and separate gain/loss charts replace crowded 100-position plots; complete data remains in tables and CSVs.

Four regression tests were developed with observed failures before the corresponding fixes. The final suite passes 58 tests, with Ruff lint/format checks passing. A browser-only interaction regression (sidebar confirmation hidden in the Edit tab) was reproduced, covered by a regression test, fixed by rendering confirmations above tabs, and checked again in Edge.

Isolated headless Edge/Playwright used only synthetic CSVs and `/private/tmp/portfolio-ui-refinement` SQLite data. Uploaded `real_symbols_100.csv`; observed basis $16,233,618.53, market value $16,368,367.89, gain $134,749.36, 0.83%, 100 holdings. At widths 1366, 1024, and 768, metric content fits without horizontal overflow. Edited AAPL quantity 459.01→460.01 through the actual canvas editor: total becomes $16,368,525.69. Complete download retained 100 rows and exact edited quantity; AAPL filtering, Reset filters, saving and switching tabs passed. Sidebar discard confirmation/cancel is visible from Analysis.

Screenshots: [dashboard](evidence/portfolio-100-dashboard.png), [charts](evidence/portfolio-100-charts.png). Narrow tables require horizontal scrolling; charts deliberately summarize positions while tables/reports retain all selected holdings. Restart an already-running Streamlit process to load the changed Python modules.

## 2026-10-11 — Portfolio Ledger V2 implementation

Executed the approved eleven-task plan sequentially in `feature/portfolio-ledger-v2`, based on V1 planning commit `6b14063`. Focused commits preserve the migration, pure replay, event types, revisioned repository, CSV exchange, valuation, reconciliation, shell, entry/lot workflows, and recovery UI boundaries. The detailed resumable record is [implementation-progress-v2.md](implementation-progress-v2.md).

Cleanup inventory: centralized the database schema/connection in `database.py`; removed duplicate initialization from snapshot storage; extracted snapshot UI while retaining its contracts/tests; consolidated money/table formatting; replaced obsolete global unsupported-feature copy with mode-specific guidance; retained historical planning documents with status notices, course materials, privacy ignores, lockfile and snapshot fixtures. No owner files, databases, or V1 worktree were removed.

Acceptance uses synthetic fixtures and temporary databases exclusively. The fresh isolated locked environment passes 169 non-browser tests; the installed `stock_portfolio.ui` entrypoint imports from outside the source directory. Playwright is a development dependency only. Real Edge acceptance and the independent whole-branch review are recorded below when complete.

Combined extended isolated Edge suite: 2 passed in 128.43s. Priced 100-holding charts, filtered downloads, four viewport measurements and synthetic screenshots inspected; no summary overflow. Final browser 10k preview 0.852s / commit 0.937s. Offline restore CLI passed on temporary synthetic data, including recovery-file content verification. Evidence and commands: [acceptance-v2.md](acceptance-v2.md). One independent GPT-6 Astra High review dispatched against 6b14063..b958caa; pending findings.
