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

All 11 tasks complete. Implementation and important review fixes are committed. Branch/worktree retained for owner inspection and manual acceptance.

## Review / browser

Complete: one independent GPT-6 Astra High whole-branch review; all seven Important findings fixed, four Minor items deferred. Final normal suite179passed; isolated Edge2passed.

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

### Task 11 implementation and acceptance record
Base 47ce8f4. Added dev-only Playwright 1.63.0 (runtime lock versions unchanged), synthetic fixtures/hand-calculated JSON, explicit browser marker and ephemeral server/profile harness. Fixture checks: 7 passed; 10,000 rows preview 0.613s / commit 0.399s / load+replay 0.137s on this machine.
Acceptance RED→GREEN safeguard: incomplete schema-2 backup (missing reconciliation_rows) was accepted; new test failed, schema validation now compares every required table/column with an in-memory canonical schema. Migration/backup checks 9 passed. SQLite backup connections now close explicitly.
Browser: Edge installed. Localhost bind required sandbox escalation; isolated launch/onboarding smoke passed. Full workflow exposed untracked expander panels collapsing after reruns; panels now have explicit state, focused UI suite 7 passed. Full Edge workflow running again; do not claim acceptance complete yet.
Docs updated for V2 workflows, safe migration/restore, explicit browser command and synthetic pack; historical V1 records retained. Remaining: finish actual browser upload/edit/allocations/reconciliation/download/restart/snapshot canvas/sizes, fresh install, one independent Astra High review, important fixes, final checks/commit.

Acceptance hardening: filtered holdings reports now honor selected symbols; detailed-opening export/import preserves absent external identity; simultaneous previews use distinct control keys. Each new behavioral regression failed before its fix. Full non-browser suite: 169 passed, 2 explicitly deselected browser scenarios.
Task 11: Ruling: metadata-identified opening-lot exports may leave external lot_id blank when the event has none; ordinary opening CSVs still require it — preserves lossless identity instead of fabricating one — cost if wrong: exported-file compatibility needs a format revision.

Browser acceptance: isolated Edge ledger scenario passed (103.47s), including two accounts, uploads/no-op/occurrence decisions, cancel/confirm trade edit, explicit lots, reinvestment/split/transfer, prices, mismatch correction/stale/recalculation, inspected downloads/backup, opening-pool basis resolution, 10,000-event import and restart. Browser preview 2.217s / commit 1.567s. Snapshot scenario passed separately with actual canvas editing, navigation guard, cancel/confirm replacement, downloads and restart. Harness issues resolved by waiting for scroll completion, searching virtualized selectors, and checking the visible canvas editor. Combined suite extended to capture priced 100-holding charts and filtered downloads is running.
Fresh isolated locked environment: 169 passed / 2 browser deselected; installed UI import outside source cwd passed. Ruff check/format and whitespace checks passed. V1 and main remain clean, unchanged. Final independent review next.

Combined extended isolated Edge suite: 2 passed in 128.43s. Priced 100-holding charts, filtered downloads, four viewport measurements and synthetic screenshots inspected; no summary overflow. Final browser 10k preview 0.852s / commit 0.937s. Offline restore CLI passed on temporary synthetic data, including recovery-file content verification. Evidence and commands: [acceptance-v2.md](acceptance-v2.md). One independent GPT-6 Astra High review dispatched against 6b14063..b958caa; pending findings.

## Final review and fix pass
One independent GPT-6 Astra High review of 6b14063..b958caa returned 0 Critical, 7 Important, 4 Minor. All seven Important findings entered the single fix pass. See review-v2.md for exact regression mapping; every finding reproduced RED before GREEN. Initial post-fix full suite: 178 passed / 2 browser deselected. Added partial transfer-chain coverage subsequently. Affected browser rerun is in progress; no second review is claimed.
Final: fixed decimal-scale duplicate bypass — test_numeric_scale_does_not_bypass_duplicate_occurrence_review RED→GREEN.
Final: fixed outdated duplicate decisions — test_changed_duplicate_choice_requires_new_review RED→GREEN.
Final: fixed transferred split-price validity — test_split_price_guard_survives_full_transfer_to_empty_account RED→GREEN; partial chains additionally verified.
Final: fixed snapshot revision/source staleness — test_snapshot_mutations_invalidate_conversion_preview and test_snapshot_conversion_revalidates_source_contents_with_current_revision RED→GREEN.
Final: fixed changed conversion options — test_snapshot_option_change_invalidates_conversion_preview RED→GREEN; proposed price writes now visible.
Final: fixed automatic account navigation bypass — test_creating_account_preserves_other_draft_and_guards_navigation RED→GREEN.
Final: fixed corrupt destination recovery — test_restore_valid_backup_over_corrupt_destination_preserves_raw_original RED→GREEN for success and injected replacement failure.
Final: minor (deferred): some exact financial table columns sort lexically; calculations and exported values remain correct.
Final: minor (deferred): import review lacks generated-sequence display/editor; explicit CSV sequences and transaction correction remain available.
Final: minor (deferred): repeated-file no-op shows prior receipt but not prior occurrence dispositions.
Final: minor (deferred): ledger overview lacks a separate losses chart; tables/reports retain losses.
Final: Ruling: tax/live-price/cash/unsupported-action/combined-account behaviors remain excluded — approved scope does not invent those results — cost if wrong: future feature work is required.
Final: Ruling: restore requires all external writers stopped — local CLI cannot prove exclusivity over arbitrary clients — cost if wrong: external writes can invalidate recovery assumptions.
Final: Ruling: no speculative malicious-schema/extreme-programmatic-input hardening beyond concrete defects — existing input/schema/replay checks remain and corrupt-destination recovery is fixed — cost if wrong: adversarial edge cases may require later hardening.
Final: Ruling: historical pool allocations stay unresolved rather than inferred from residual totals — preserves the approved uncertainty policy — cost if wrong: manual supported allocation work remains necessary.
Final: Ruling: certify the documented locked editable uv installation; noneditable-wheel sample packaging remains unverified — matches the delivered launch workflow — cost if wrong: wheel-only installs may need resource packaging work.
Final: Ruling: actual browser certification is the author's isolated Edge execution, not a second independent browser run — reviewer inspected harness and reviewed code independently — cost if wrong: browser assurance is not independently duplicated.

Final verification: 179 passed / 2 explicitly deselected browser tests in the fresh locked environment; explicit post-review Edge suite 2 passed in 144.24s, including affected navigation/duplicate/conversion flows. Ruff lint/format and diff whitespace checks passed. Final browser10k preview0.747s / commit0.942s. Corrupt-destination restore CLI passed with byte-for-byte preservation of damaged original. All seven fixes verified with full suite179/179. No Critical/Important findings remain; four deferred Minor items and all six declined-review rulings are recorded above.

## Final completion ledger

- Task 1: complete (commits 6b14063..d40b51c, tests: uv run --locked pytest -q → 66 passed in 1.73s)
- Task 2: complete (commits d40b51c..21b525c, tests: uv run --locked pytest -q → 93 passed in 1.64s)
- Task 3: complete (commits 21b525c..6363948, tests: uv run --locked pytest -q → 104 passed in 1.49s)
- Task 4: complete (commits 6363948..1fb232b, tests: uv run --locked pytest -q → 111 passed in 1.66s)
- Task 5: complete (commits 1fb232b..d5f33b7, tests: uv run --locked pytest -q → 134 passed in 1.71s)
- Task 6: complete (commits d5f33b7..afe8ba0, tests: uv run --locked pytest -q → 138 passed in 1.61s)
- Task 7: complete (commits afe8ba0..4353214, tests: uv run --locked pytest -q → 148 passed in 1.93s)
- Task 8: complete (commits 4353214..4cfc5c7, tests: uv run --locked pytest -q → 150 passed in 1.85s)
- Task 9: complete (commits 4cfc5c7..a424553, tests: uv run --locked pytest -q → 155 passed in 2.13s)
- Task 10: complete (commits a424553..47ce8f4, tests: uv run --locked pytest -q → 157 passed in 2.40s)
- Task 11: complete (commits 47ce8f4..1363173, tests: uv run --locked pytest -q → 179 passed, 2 deselected in 4.21s)

Final implementation/fix head: 1363173. No merge, push, publication, V1 worktree removal or course submission. Main and V1 remain unchanged. Persistent setup/recovery/checklist: acceptance-v2.md; independent findings/fixes/minors: review-v2.md. No required implementation work remains.
