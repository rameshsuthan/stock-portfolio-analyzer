# Development log — 2026-10-10

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
