# Portfolio Ledger V2 — Next-session Handoff

Open the existing implemented project at:

`/Users/ramesh/code/mastering-agentic-ai-v2/stock-portfolio/.worktrees/portfolio-v1`

The implementation is on `feature/portfolio-v1`; `main` is older planning scaffolding. The next session must create a new V2 worktree from this implementation plus the planning artifacts. Do not discard or clean the V1 worktree.

Read the design and plan before using the prompt below. Sending the prompt approves those artifacts for implementation; no implementation was performed while preparing them.

## Copy-ready implementation prompt

```text
Use superpowers:executing-plans to implement Portfolio Ledger V2.

Read first:
docs/superpowers/specs/2026-10-11-portfolio-ledger-v2-design.md
Then execute:
docs/superpowers/plans/2026-10-11-portfolio-ledger-v2.md

I approve this design and implementation plan and authorize implementation of the complete release described there, including its migration safeguards, scoped cleanup, and Streamlit UI polish.

Use native execution: implement the tasks yourself, sequentially. Do not restart brainstorming, ask me to choose an execution method, or request routine confirmation between tasks.

Before implementation:
- Inspect repository status, instructions, and worktrees; preserve existing changes.
- The usable V1 is on feature/portfolio-v1 (baseline 35662c6 plus planning commits), not main. Verify the source branch contains the implemented app and these planning documents.
- If the planning documents are untracked, commit only those documents so the new implementation worktree has them.
- Create or verify an isolated feature/portfolio-ledger-v2 branch/worktree from that V1 implementation. Do not merge or remove the V1 worktree.
- Read any existing docs/implementation-progress-v2.md and resume completed work rather than repeating it.

Execute all 11 tasks in order using test-first behavioral changes, each task's checks, full-suite verification, and small focused commits. Maintain docs/implementation-progress-v2.md with task status, commit IDs, RED/GREEN evidence, browser/review status, adjustments and reasons, and the next action for an interrupted session.

Honor the confirmed product decisions: generic CSV imports; separate accounts; FIFO plus explicit lot selection; buys/sells/fees, dividends/reinvestment, splits, and internal transfers; existing snapshot mode retained; no guessed opening-lot basis or gains. Keep Streamlit and implement the planned navigation, import previews, readable tables, lot explanations, and reconciliation views.

Preserve personal data, existing snapshot contracts, and relevant tests. Perform only the cleanup specified by the plan. Use synthetic records and temporary databases for every test, migration/recovery exercise, screenshot, and browser check. Do not test against or restore the owner's real database. No live pricing, tax-reporting expansion, brokerage connections, or frontend rewrite.

After implementation, perform one independent whole-branch review using GPT-6 Astra with High reasoning if available. Address important findings with regression tests and rerun the relevant checks. Use an isolated Edge/Playwright browser for actual uploads, editing, allocation, transfers, reconciliation, downloads, and retained snapshot workflows; permission for this fallback is already granted. Verify the specified window sizes and capture synthetic evidence. Report any unavailable reviewer/browser capability honestly.

Finish with setup, launch, upgrade and recovery commands; test and browser results; deviations, limitations and unresolved findings; and the manual acceptance checklist. Keep the completed branch/worktree. Do not merge, push, publish, or submit course materials.
```

## Confirmed interview answers

- Goal: reconcile calculations with brokerage records, not tax filing.
- Starting records: full histories and opening holdings/lots, depending on account.
- Format: generic CSV first.
- UI: polish Streamlit; no custom frontend rewrite.
- Compatibility: keep editable snapshot mode alongside transaction accounts.
- Disposal basis: FIFO default plus explicit lot selection.
- Additional events: dividends, reinvestment, splits, and transfers between tracked accounts.
- Incomplete opening lots: retain quantities and mark affected basis/gains unresolved until lot detail or an explicit sale-basis amount is supplied.

## Pre-implementation review notes

The release deliberately does not implement every brokerage/tax event. Wash-sale adjustments, mergers, return of capital, external transfers with missing provenance, and fractional-share cash-in-lieu can remain unsupported differences. The application must disclose unsupported inputs and incomplete results, not silently convert them into matches. All-account transaction CSV export/import is included specifically to preserve dependent transfer history atomically; it does not add combined-account analytics.
