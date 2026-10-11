"""Account setup, generic exchange, opening records and shared prices."""

from datetime import date

import streamlit as st

from ..ledger.csv_io import ImportKind as I
from ..ledger.csv_io import (
    export_allocations,
    export_events,
    export_openings,
    export_prices,
    parse_import,
    template,
)
from ..ledger.imports import ImportChoice, commit_import, prepare_import
from ..ledger.models import PriceObservation
from ..ledger.validation import decimal_input, iso_date
from ..presentation import exact, table
from ..storage import Repository
from ..ui_state import clear_draft, draft_for, text_input
from .common import impact


def onboarding(repo):
    with st.expander("Create transaction account", expanded=not repo.load_dataset().accounts):
        draft = draft_for("account")
        name = text_input(draft, "name", "New account name")
        mode = st.selectbox(
            "Starting records", ("Full history", "Opening balance / lots"), key="starting_records"
        )
        cutoff = (
            text_input(draft, "cutoff", "Opening cutoff (end of day)", str(date.today()))
            if mode != "Full history"
            else None
        )
        broker = text_input(draft, "broker", "Brokerage label (optional)")
        if st.button("Create account", disabled=not name.strip()):
            try:
                account = repo.create_account(name, iso_date(cutoff) if cutoff else None, broker)
                clear_draft(draft)
                st.session_state["_new_account"] = account.id
                st.session_state["receipt"] = (
                    "Account created. Add opening records in Data or transactions from full history."
                )
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def import_wizard(repo, account_id, as_of, kind=None):
    draft = draft_for("import:" + str(kind or "data"))
    selected = (
        I(kind)
        if kind
        else I(
            st.selectbox(
                "CSV type",
                [i.value for i in (I.opening_lots, I.opening_balances, I.allocations, I.prices)],
                key="data_import_kind",
            )
        )
    )
    scope = account_id
    if selected in {I.transactions, I.allocations}:
        multiple = st.checkbox(
            "Multiple accounts (exact account_name on every row)", key="multiple:" + draft.key
        )
        if multiple:
            scope = None
    if selected == I.prices:
        scope = None
    effective = None
    if selected in {I.opening_lots, I.opening_balances}:
        account = next(a for a in repo.load_dataset().accounts if a.id == account_id)
        effective = account.opening_date
        st.caption(
            f"Opening cutoff: {effective or 'Create an opening account first'}. Acquisition dates are never guessed."
        )
    if selected == I.broker_holdings:
        effective = as_of
    replacement = (
        st.checkbox(
            "Replace matching aggregate openings with detailed lots", key="replace:" + draft.key
        )
        if selected == I.opening_lots
        else False
    )
    st.download_button(
        "Download " + selected.value + " template",
        template(selected),
        selected.value + "-template.csv",
        "text/csv",
        key="template:" + draft.key,
    )
    upload = st.file_uploader(
        "Ledger CSV" if selected != I.broker_holdings else "Complete broker holdings CSV",
        type=["csv"],
        max_upload_size=10,
        key="upload:" + draft.key,
    )
    if upload is not None:
        signature = (upload.name, upload.size, selected.value, scope, effective, replacement)
        content = upload.getvalue()
        # Hash distinguishes replacement files with the same name and byte length.
        import hashlib

        signature = (*signature, hashlib.sha256(content).hexdigest())
        if draft.inputs.get("_upload_signature") != signature:
            draft.inputs.update(_upload_signature=signature, _bytes=content, _name=upload.name)
            draft.inputs.pop("_preview", None)
            draft.dirty = True
    complete = True
    if selected == I.broker_holdings:
        complete = st.checkbox(
            "I confirm this is the complete end-of-day statement for this account",
            key="complete_statement",
        )
    if st.button(
        "Preview CSV import", key="parse:" + draft.key, disabled="_bytes" not in draft.inputs
    ):
        try:
            parsed = parse_import(draft.inputs["_bytes"], selected, draft.inputs["_name"])
            draft.inputs["_parsed"] = parsed
            with st.spinner("Validating complete history…"):
                draft.inputs["_preview"] = prepare_import(
                    repo, parsed, scope, effective, replace_openings=replacement
                )
            draft.dirty = True
        except ValueError as exc:
            st.error(str(exc))
    preview = draft.inputs.get("_preview")
    if preview:
        st.subheader("Import review")
        for warning in preview.warnings:
            st.warning(warning)
        parsed = draft.inputs["_parsed"]
        table(list(parsed.rows), height=260)
        if preview.no_op_batch_id:
            st.info(f"Previously imported file. No-op; prior receipt {preview.no_op_batch_id}.")
        if preview.duplicate_rows:
            choices = []
            for row, count in preview.duplicate_rows.items():
                action = st.selectbox(
                    f"Row {row}: {count} matching occurrences",
                    ("Choose…", "keep", "skip"),
                    key=f"dup:{draft.key}:{preview.batch.source_hash}:{row}",
                )
                if action != "Choose…":
                    choices.append(ImportChoice(row, action))
            if st.button("Update duplicate decisions", key="decide:" + draft.key):
                draft.inputs["_preview"] = prepare_import(
                    repo, parsed, scope, effective, tuple(choices), replace_openings=replacement
                )
                st.rerun()
        for issue in preview.issues:
            st.error(f"Row {issue.row or '—'} · {issue.code}: {issue.message}")
        if preview.void_ids:
            st.warning(
                "Reviewed replacement will void the matching aggregate openings and replay dependent sale gains."
            )
        if preview.projected:
            impact(repo, preview.projected)
        if preview.proposed_prices:
            st.warning(
                "Shared price observations affect every transaction account using this symbol/date."
            )
        if st.button(
            "Confirm import",
            key="commit:" + draft.key,
            disabled=bool(preview.issues) or not complete,
        ):
            try:
                with st.spinner("Committing validated batch…"):
                    batch = commit_import(repo, preview)
                draft.inputs.pop("_preview", None)
                draft.dirty = False
                st.session_state["receipt"] = f"Import committed · receipt {batch}"
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    if draft.dirty and st.button("Cancel import", key="cancel:" + draft.key):
        clear_draft(draft)
        # Drop uploader state so a cancelled upload does not immediately recreate the draft.
        st.session_state.pop("upload:" + draft.key, None)
        st.rerun()


def render(repo, account_id, as_of, notices):
    st.subheader("Data & recovery")
    ds = repo.load_dataset()
    account = next(a for a in ds.accounts if a.id == account_id)
    st.caption(
        "Complete data exports include all active events, regardless of table filters. Import each account’s openings before all-account transactions. A database backup preserves audit history."
    )
    st.download_button(
        "Download all-account transaction data",
        export_events(ds),
        "all-account-transactions.csv",
        "text/csv",
    )
    for kind in (I.opening_lots, I.opening_balances):
        st.download_button(
            "Download " + kind.value,
            export_openings(ds, account_id, kind),
            kind.value + ".csv",
            "text/csv",
        )
    st.download_button(
        "Download allocation data",
        export_allocations(ds, account_id),
        "allocations.csv",
        "text/csv",
    )
    st.download_button(
        "Download shared prices", export_prices(repo.load_prices()), "prices.csv", "text/csv"
    )
    with st.expander("Import opening records, allocations or prices", expanded=True):
        import_wizard(repo, account_id, as_of)
    with st.expander("Add or correct a dated price"):
        st.warning("A price correction affects all transaction accounts using that observation.")
        draft = draft_for("price")
        symbol = text_input(draft, "symbol", "Price symbol")
        day = text_input(draft, "date", "Price observation date", str(as_of))
        price = text_input(draft, "price", "Observation price")
        source = text_input(draft, "source", "Price source", "Manual")
        reason = text_input(draft, "reason", "Price correction reason")
        if st.button("Preview price"):
            try:
                if not reason.strip():
                    raise ValueError("A reason/source description is required.")
                observation = PriceObservation(
                    symbol.strip().upper(), iso_date(day), decimal_input(price), source
                )
                repo.validate_prices((observation,))
                draft.inputs["_preview"] = (observation, repo.load_dataset().revision, reason)
                draft.dirty = True
            except ValueError as exc:
                st.error(str(exc))
        if draft.inputs.get("_preview"):
            p, revision, reason = draft.inputs["_preview"]
            st.info(f"{p.symbol} · {p.price_date} · {exact(p.price)} USD · {p.source_label}")
            if st.button("Confirm shared price"):
                try:
                    repo.save_prices((p,), revision, reason)
                    clear_draft(draft)
                    st.session_state["receipt"] = "Shared price saved with revision history."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if draft.dirty and st.button("Cancel price"):
            clear_draft(draft)
            st.rerun()
    with st.expander("Start account from snapshot"), Repository(repo.path) as snapshots:
        options = {
            sid: f"{name} · {day}"
            for pid, name in snapshots.list_portfolios()
            for sid, day in snapshots.list_snapshots(pid)
        }
        if not options:
            st.info("Save a snapshot first, then preview its opening balances here.")
        else:
            sid = st.selectbox("Source snapshot", list(options), format_func=options.get)
            draft = draft_for("snapshot_start")
            name = text_input(draft, "name", "Account name from snapshot")
            include = st.checkbox("Include snapshot prices as dated observations", value=False)
            if st.button("Preview opening account"):
                snapshot = snapshots.load_snapshot(sid)
                draft.inputs["_preview"] = (snapshot, name, repo.load_dataset().revision, include)
                draft.dirty = True
            if draft.inputs.get("_preview"):
                snapshot, name, revision, include = draft.inputs["_preview"]
                st.info(
                    f"New account: {name} · cutoff {snapshot.metadata.snapshot_date} · aggregate openings; acquisition dates Unknown."
                )
                table(
                    [
                        {
                            "Symbol": h.symbol,
                            "Quantity": exact(h.quantity),
                            "Total basis": exact(h.cost_basis),
                        }
                        for h in snapshot.holdings
                    ],
                    height=230,
                )
                if st.button("Confirm opening account", disabled=not name.strip()):
                    try:
                        new = repo.start_from_snapshot(snapshot, name, revision, include)
                        clear_draft(draft)
                        st.session_state["_new_account"] = new.id
                        st.session_state["receipt"] = (
                            "Opening account created; source snapshot preserved."
                        )
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
    st.caption(
        f"Account status: {'Archived' if account.archived else 'Active'}. Archive preserves transactions and history."
    )
    archive = st.checkbox("Confirm archive of this account", key="archive_confirm")
    if st.button("Archive account", disabled=not archive or account.archived):
        repo.archive_account(account_id)
        st.session_state["receipt"] = "Account archived. History retained."
        st.rerun()
