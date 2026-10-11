# Independent Portfolio Ledger V2 review

Reviewer: **GPT-6 Astra, High reasoning**, one fresh-context whole-branch review of `6b140639..b958caa`. No implementation delegation and no second review. The reviewer independently ran the original suite: 169 passed / 2 browser deselected. Verdict before fixes: changes requested; no Critical findings, seven Important and four Minor findings.

## Important findings and regression fixes

| Finding | Fix | Observed RED→GREEN regression |
|---|---|---|
| Decimal spelling bypassed duplicate detection | Compare immutable economic event values numerically; persisted decimal strings remain exact | `test_numeric_scale_does_not_bypass_duplicate_occurrence_review` |
| Changed keep/skip controls could commit old choices | Disable confirmation until visible choices match the reviewed decisions | `test_changed_duplicate_choice_requires_new_review` |
| Transfer destination could use pre-split shared price | Invalidate symbol observations dated before any recorded split, including transfer chains | `test_split_price_guard_survives_full_transfer_to_empty_account` (plus partial-chain coverage) |
| Snapshot mutations left conversion previews valid | Advance global revision transactionally; retain economic revision; re-read source at confirmation | `test_snapshot_mutations_invalidate_conversion_preview`, `test_snapshot_conversion_revalidates_source_contents_with_current_revision` |
| Changed snapshot source/options retained old conversion preview | Bind preview to source/name/include-price inputs; show proposed shared price writes | `test_snapshot_option_change_invalidates_conversion_preview` |
| Creating an account stranded another dirty draft | Route automatic account navigation through the common dirty-navigation guard | `test_creating_account_preserves_other_draft_and_guards_navigation` |
| Corrupt destination prevented restoration of valid backup | Preserve invalid destination bytes before replacing it with validated staged source; retain sidecar refusal and atomic-failure protection | `test_restore_valid_backup_over_corrupt_destination_preserves_raw_original` (success and injected failure) |

The author verified every Important finding with a failing regression before the fix. Post-fix full-suite and affected Edge results are recorded in [acceptance-v2.md](acceptance-v2.md). This is author verification of the fixes, not a claim that Astra re-reviewed them.

## Deferred minor findings

- Financial columns in some transaction/lot/reconciliation tables sort lexically because their exact displayed values are strings; numerical values remain correct in calculations and exports.
- Import review displays source rows without a separate normalized, generated-sequence editor. Supply explicit CSV sequences or correct events through the transaction editor.
- Repeated-file review shows the previous receipt but does not display its prior keep/skip dispositions.
- Ledger overview shows the gains chart without a separate losses chart; losses remain in the table and reports.

## Decisions on behaviors the reviewer declined to judge

- Out-of-scope tax correctness, live pricing, cash accounting, unsupported corporate actions and combined-account analytics remain excluded. Cost if wrong: those uses require a later release, not inferred results now.
- Restore retains the documented stopped-writer prerequisite. Cost if wrong: an external writer can invalidate offline-replacement assumptions.
- No additional speculative malicious-schema/extreme-programmatic-input work was added without a concrete defect. Existing bounded input, schema/integrity and replay validation remain; the confirmed corrupt-destination defect was fixed. Cost if wrong: an adversarial edge case may require further hardening.
- Missing historical pool allocations stay unresolved rather than inferred from residual totals. Cost if wrong: users must supply supported allocations before complete gain reporting.
- Installation support is the documented locked editable `uv sync` workflow. Noneditable-wheel sample packaging is not certified. Cost if wrong: a wheel-only install may need sample-resource packaging work.
- Browser certification is the author's actual isolated Edge execution and screenshots. The independent reviewer inspected the harness but did not rerun it. Cost if wrong: browser assurance is not independently duplicated.
