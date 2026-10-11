# Portfolio Ledger V2 implementation progress

Plan: docs/superpowers/plans/2026-10-11-portfolio-ledger-v2.md
Spec: docs/superpowers/specs/2026-10-11-portfolio-ledger-v2-design.md
Branch: feature/portfolio-ledger-v2. Base: 6b140639d788047bb3a76d656faff8fb560df75c.
Worktree: /Users/ramesh/code/mastering-agentic-ai-v2/stock-portfolio/.worktrees/portfolio-ledger-v2

Baseline: V1 and root clean. uv sync --locked; pytest 58 passed; Ruff check and format passed.
All exercises use synthetic records and temporary databases. V1 remains untouched.

## Pre-flight interfaces

| Producer → consumer | Check |
|---|---|
| 1 → 4,8,10 | Shared schema/connection and verified backup; retain snapshot tables |
| 2 → 3,4,5,6,7 | Frozen public models and replay; pure replay has no clock; services validate today |
| 3 → 4,5,9 | Stable transfer lot UUID5, complete reinvestment groups and cross-account replay |
| 4 → 5,6,7,9 | Atomic internal transaction helper; global vs economic revision distinction |
| 5 → 6,7,9 | Price/statement previews must not commit until corresponding services exist |
| 6,7 → 9,10 | None means unknown; reports distinct from input; immutable reconciliation |
| 8 → 9,10,11 | Session drafts outlive widgets; global visible navigation guard |
| 1–10 → 11 | Full regression, synthetic browser acceptance, one independent review |

No blocking interface conflicts found. Approved design/plan supersede earlier planning-only status.

## Tasks

1. In progress — migration and recovery. Next: RED tests.
2–11. Pending in order.

## Review / browser

Pending. Reviewer requested: GPT-6 Astra, High, one whole-branch review.

### Task 1 complete
RED: focused tests failed on missing database/backup modules. GREEN: migration/backup/storage 14 passed; full suite 66 passed; Ruff clean after formatting.
Implemented transactional V1→V2 with pre-migration backup, schema constraints, shared connection, SQLite backup API, offline staged atomic restore and preserved recovery file. Injected backup/migration/replacement failures preserve originals. Commit: this task commit (see git log).
Environment: use UV_CACHE_DIR=/private/tmp/portfolio-v2-uv-cache for sandbox-writable uv cache.
Next: Task 2, pure trades/opening replay.

### Task 2 complete
Base d40b51c. RED: missing replay/models; fee-slice test subsequently failed on absent match_proceeds. GREEN: 27 trade/opening tests; full suite 93 passed. FIFO 1794/1252/542 and explicit 908/288 verified; precision-50 residual conservation; unknown pools do not prorate.
Task 2: Ruling: aggregate-to-detailed replacement total checks belong to Task 4's atomic mutation boundary, where the old and proposed datasets coexist; replay validates each representation now — avoids inventing mutation semantics in pure replay — cost if wrong: replacement test arrives two tasks later.
Added optional Disposal.match_proceeds to expose proportional fee allocation and final residuals without changing required signatures.
Next: Task 3 additional events.

### Task 3 complete
Base 21b525c. RED: five missing-handler failures in event/transfer tests; GREEN: all 11 event/transfer cases, full suite 104 passed. Forward/reverse splits use exact rational representability checks; linked dividends and transfer-derived UUID5 lots verified. Source correction replays transfer descendants; no transfer income.
Next: Task 4 revisioned persistence, grouped corrections and replacement totals.

### Task 4 complete
Base 6363948. RED: missing codec/repository; GREEN: 7 persistence/correction integration tests; full suite 111 passed. SQLite trigger rollback preserves identities, heads, audits and counters. Restart preserves exact decimals; invalid cross-account corrections and partial reinvestment changes are rejected. Task 2 deferred opening replacement contract now verified.
Next: Task 5 generic CSV previews and atomic batch exchange.

### Task 5 complete
Base 1fb232b. RED: missing exchange/import modules; GREEN: 23 CSV/import/export tests, full suite 134 passed. Verified repeated-file no-op, explicit identical occurrence decisions, external identity conflicts, exact cross-account lot/transfer round trip, stale previews and injected batch-record rollback. CSV boundaries retain NA, normalize headers, bound bytes/rows and reject report metadata. Prices/statements deliberately blocked at commit until Tasks 6/7.
Next: Task 6 dated price persistence and completeness-aware valuation.

### Task 6 complete
Base d5f33b7. RED: missing valuation/report API; GREEN: 4 valuation integration tests, full suite 138 passed. Latest eligible observation, stale/pre-split/missing price, unknown-vs-zero values, known subtotals, opening cutoff and report markers verified. Price changes retain revisions and invalidate previews without changing economic revision.
Next: Task 7 dated brokerage statements and immutable reconciliation evidence.

### Task 7 complete
Base afe8ba0. RED: missing reconciliation module; intermediate timestamp NameError traced to Ruff's existing UTC import and corrected. GREEN: 10 dated/tolerance/evidence cases, full suite 148 passed. Saved comparisons remain unchanged after economic edits; price edits do not stale them. Statement persistence never modifies events. Caller-confirmed completeness is part of save_statement's service contract; the owner-facing checkbox is verified with the Task 10 UI.
Next: Task 8 shell and guarded snapshot/ledger navigation.

### Task 8 complete
Base 4353214. RED: missing UI state module. GREEN: 14 snapshot/navigation/installed-entrypoint tests; full suite 150 passed. Retained V1 assertions unchanged; shell defaults to Snapshots, blocks dirty navigation with outside-tab controls, and keeps normalized ledger drafts independent of widget lifecycle. Snapshot replacement confirmation moved out of hidden edit tab. Native blue theme added.
Next: Task 9 transaction onboarding, entry/import/lot/overview/data views and UI behavior tests.

### Task 9 complete
Base 4cfc5c7. RED: absent onboarding controls/snapshot conversion; later opening replacement preview parameter failed. GREEN: 5 UI/workflow tests, full suite 155 passed. Added account onboarding; trade/revision/void/revival previews; paired reinvestment; split/transfer entry; CSV review/duplicate choices; allocation and supplied-pool basis editor; derived overview; exact details; opening/price/data exports; atomic snapshot conversion; reviewed aggregate-to-detail replacement. New shared views/common.py centralizes preview/confirmation controls.
Next: Task 10 reconciliation, audit, backup and recovery UI. Browser verification remains pending Task 11.

### Task 10 complete
Base a424553. RED: missing reconciliation controls and audit view; GREEN: 2 additional UI scenarios, full suite 157 passed; Ruff check/format and diff whitespace check passed. Completeness confirmation gates statement import; saved evidence shows stale state and recalculates into a new result. Added current-history lot/event drill-through, immutable audit old/new/reason display, SQLite backup download and configured-path offline restore instructions. Backup bytes were reopened and integrity-checked in a temporary test directory. Shared snapshot money formatting consolidated.
Test adjustment: inspect the actual Reason column rather than pandas' truncated string representation.
Next: Task 11 synthetic fixtures, isolated Edge browser workflows, performance, fresh install, documentation, one Astra High whole-branch review and important fixes.
