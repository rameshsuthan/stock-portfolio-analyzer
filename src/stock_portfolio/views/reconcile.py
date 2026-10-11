from collections import Counter

import streamlit as st

from ..ledger.csv_io import export_reconciliation
from ..ledger.engine import replay
from ..ledger.reconciliation import reconcile
from ..presentation import exact, table
from .data import import_wizard


def render(repo, account_id, as_of, notices):
    st.subheader("Reconcile broker holdings")
    st.caption(
        "Compare complete end-of-day quantities and basis. A match does not certify tax lots or lifetime gains. Corrections never overwrite holdings from the statement."
    )
    statement_date = st.date_input("Broker statement date", value=as_of, key="statement_date")
    with st.expander("Import complete broker statement", expanded=True):
        import_wizard(repo, account_id, statement_date, kind="broker_holdings")
    statements = repo.load_statements(account_id)
    if not statements:
        st.info(
            "Upload a complete broker holdings CSV, select its date, and confirm completeness to begin."
        )
        return
    selected = st.selectbox(
        "Saved statement",
        [s.id for s in statements],
        index=len(statements) - 1,
        format_func=lambda id_: next(
            f"{s.as_of} · {s.source_hash[:12]} · {s.id[:8]}" for s in statements if s.id == id_
        ),
    )
    statement = next(s for s in statements if s.id == selected)
    if st.button("Compare and save evidence"):
        result = reconcile(repo.load_dataset(), statement)
        repo.save_reconciliation(result)
        st.session_state["receipt"] = "Comparison saved as immutable evidence."
        st.rerun()
    saved = [r for r in repo.load_reconciliations(account_id) if r.statement_id == selected]
    if not saved:
        return
    choice = st.selectbox(
        "Saved comparison",
        list(range(len(saved))),
        index=len(saved) - 1,
        format_func=lambda i: f"Comparison {i + 1} · economic revision {saved[i].ledger_revision}",
    )
    result = saved[choice]
    stale = result.ledger_revision != repo.load_dataset().economic_revision
    if stale:
        st.warning(
            "Stale comparison: economic history changed. This saved evidence remains unchanged."
        )
        if st.button("Recalculate and save new evidence"):
            repo.save_reconciliation(reconcile(repo.load_dataset(), statement))
            st.rerun()
    counts = Counter(r.status for r in result.rows)
    st.write(
        " · ".join(f"{count} {status.replace('_', ' ')}" for status, count in counts.items())
        or "No holdings on either side"
    )
    st.caption(
        f"{result.as_of} · policy {result.policy} · economic revision {result.ledger_revision} · absolute tolerances: quantity {result.quantity_tolerance}, basis ${result.basis_tolerance} · source SHA-256 {result.source_hash}"
    )
    table(
        [
            {
                "Symbol": r.symbol,
                "Status": r.status,
                "Local quantity": exact(r.local_quantity),
                "Broker quantity": exact(r.broker_quantity),
                "Quantity difference": exact(r.quantity_difference),
                "Local basis": exact(r.local_basis),
                "Broker basis": exact(r.broker_basis),
                "Basis difference": exact(r.basis_difference),
            }
            for r in result.rows
        ]
    )
    st.download_button(
        "Download reconciliation report",
        export_reconciliation(result),
        "reconciliation-report.csv",
        "text/csv",
    )
    if result.rows:
        symbol = st.selectbox("Inspect mismatch lots and events", [r.symbol for r in result.rows])
        current = repo.load_dataset()
        table(
            [
                {
                    "Date": str(e.effective_date),
                    "Sequence": e.day_sequence,
                    "Type": e.kind.value,
                    "Symbol": e.symbol,
                    "Quantity": exact(e.quantity),
                    "Event ID": e.id,
                }
                for e in current.events
                if e.account_id == account_id
                and e.symbol == symbol
                and e.effective_date <= statement.as_of
            ],
            height=220,
        )
        table(
            [
                {
                    "Symbol": l.symbol,
                    "Lot ID": l.id,
                    "Quantity": exact(l.quantity),
                    "Basis": exact(l.basis),
                    "Acquired": str(l.acquired_date or "Unknown"),
                }
                for l in replay(current, statement.as_of).lots
                if l.account_id == account_id and l.symbol == symbol
            ],
            height=220,
        )
        st.caption(
            "Drill-through reflects current history at the statement date. Use Transactions or Lots to make a reasoned correction, then recalculate."
        )
