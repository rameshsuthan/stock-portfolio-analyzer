"""Shared review/confirmation controls; all calculations and writes stay in services."""

from datetime import date

import streamlit as st

from ..ledger.codec import primitive
from ..ledger.engine import replay
from ..ledger.models import InvalidLedger
from ..presentation import exact, table
from ..ui_state import clear_draft


def impact(repo, result):
    names = {a.id: a.name for a in repo.load_dataset().accounts}
    st.caption(
        "Projected positions across affected ledger history (including destination accounts)"
    )
    table(
        [
            {
                "Account": names[p.account_id],
                "Symbol": p.symbol,
                "Quantity": exact(p.quantity),
                "Basis": exact(p.basis),
                "Status": "Unresolved basis" if p.basis is None else "Known basis",
            }
            for p in result.positions
        ],
        height=250,
    )
    if result.disposals:
        with st.expander("Projected sale gains and consumed lots"):
            table(
                [
                    {
                        "Event": d.event_id,
                        "Symbol": d.symbol,
                        "Proceeds": exact(d.proceeds),
                        "Basis": exact(d.basis),
                        "Gain": exact(d.gain),
                        "Method": d.method,
                    }
                    for d in result.disposals
                ],
                height=220,
            )
    for issue in result.issues:
        st.warning(issue.message)


def operation_controls(repo, draft, build, *, label="operation"):
    if st.button(f"Preview {label}", key=f"preview:{draft.key}"):
        try:
            events, voids, reason = build()
            if not reason.strip():
                raise ValueError("A correction/source reason is required.")
            candidate = repo.proposed_dataset(events, voids)
            projected = replay(
                candidate, max((e.effective_date for e in candidate.events), default=date.min)
            )
            draft.inputs["_preview"] = (events, voids, reason, candidate.revision, projected)
            draft.dirty = True
        except ValueError as exc:
            st.error(str(exc))
    pending = draft.inputs.get("_preview")
    if pending:
        events, voids, reason, revision, projected = pending
        st.subheader("Review before saving")
        st.json({"events": primitive(events), "void_ids": voids, "reason": reason}, expanded=False)
        impact(repo, projected)
        if st.button(f"Confirm {label}", key=f"confirm:{draft.key}"):
            try:
                repo.apply_operation(events, voids, revision, reason)
                clear_draft(draft)
                st.session_state["receipt"] = "Operation committed. Revision history preserved."
                st.rerun()
            except (ValueError, InvalidLedger) as exc:
                st.error(str(exc))
    if draft.dirty and st.button(f"Cancel {label}", key=f"cancel:{draft.key}"):
        clear_draft(draft)
        st.rerun()
