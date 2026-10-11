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
