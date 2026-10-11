# Portfolio Ledger V2 local acceptance

Launch from the V2 worktree with a fresh temporary `PORTFOLIO_DATA_DIR`. Follow [the synthetic ledger pack](../samples/ledger/README.md) for account/import/reconciliation examples and the [V2 manual checklist](superpowers/plans/2026-10-11-portfolio-ledger-v2.md#manual-acceptance-checklist). Verify both modes, cancellation and dirty navigation, dependent correction rejection, downloads, restart, backup and offline restore with synthetic files only. No course recording or submission is performed by this implementation.

The original V1 demonstration script below is retained for the **Snapshots → Analysis / Edit holdings** workflow.

# Synthetic demonstration and manual acceptance

Use only `samples/demo.csv` and a fresh temporary `PORTFOLIO_DATA_DIR`. Record no personal holdings, file paths, account details, or credentials. Target video length: 4:30, maximum five minutes. This is a prepared script, not a claim that a video has been recorded or submitted.

- **0:00–0:30:** Explain local USD snapshots and manually supplied prices. Show the template and upload the synthetic CSV. Enter `Course demo` and a date.
- **0:30–1:10:** Verify $2,000 basis, $2,100 value, $100 unrealized gain, 5%, and allocation 57.14% / 42.86%. Explain total cost basis versus average cost.
- **1:10–1:50:** Change a quantity to `oops`; show row/column error and blocked analysis/save. Correct it. Add a fractional holding, edit its price, and remove it. Click another control to prove the edit survives reruns.
- **1:50–2:30:** Save the complete snapshot. Correct one value and demonstrate same-date replacement confirmation; cancel once, then confirm. Start a new draft while dirty; cancel discard and show the edit remains.
- **2:30–3:10:** Restart using the same temporary directory and reopen the saved date. Add a second date and demonstrate choosing the older one.
- **3:10–3:50:** Restore the original two-row sample if necessary. Filter to DEMO_A: $1,000 / $1,200 / $200 / 20%. Intersect with Healthcare to demonstrate the empty state. Clear/reset filters.
- **3:50–4:30:** Download the filtered report and complete snapshot; show that the snapshot still has two rows. Re-import the complete file and inspect prefilled metadata. Explain that analysis reports cannot be imported. Show deletion confirmation and cancel. Summarize SQLite precision and test coverage.

Acceptance checklist:

- [ ] CSV upload and metadata review work in the browser.
- [ ] Add/change/delete string-backed cells; invalid values block analysis and saving.
- [ ] Ordinary reruns preserve edits; switching requires discard acknowledgment.
- [ ] Same-date replacement is explicit; cancel preserves old data.
- [ ] Saved data persists after stopping and restarting the server.
- [ ] All dashboard views and report reflect the same intersecting selection.
- [ ] Complete export and saving include all rows despite filters.
- [ ] Both downloads work and complete CSV re-import preserves metadata/precision.
- [ ] Confirmed deletion and cancel paths are clear.
- [ ] Only synthetic evidence is included in course materials; nothing is published automatically.
