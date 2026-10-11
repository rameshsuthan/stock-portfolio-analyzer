from dataclasses import replace
from decimal import Decimal as D

import streamlit as st

from ..ledger.engine import replay
from ..ledger.models import EventKind as K
from ..ledger.models import LotAllocation
from ..ledger.validation import decimal_input
from ..presentation import exact, table
from ..ui_state import draft_for, text_input
from .common import operation_controls


def render(repo, account_id, as_of, notices):
    ds = repo.load_dataset()
    result = replay(ds, as_of)
    st.subheader("Lots & realized gains")
    st.caption(
        "FIFO is the default. Unknown acquisition dates identify aggregate openings. User supplied basis is not broker-verified."
    )
    table(
        [
            {
                "Symbol": l.symbol,
                "Quantity": exact(l.quantity),
                "Remaining basis": exact(l.basis),
                "Acquired": str(l.acquired_date or "Unknown"),
                "Lot ID": l.id,
                "Origin event": l.origin_event_id,
                "Source lot": l.source_lot_id or "",
                "Status": "Aggregate pool" if l.aggregate else "Exact lot",
            }
            for l in result.lots
            if l.account_id == account_id
        ]
    )
    table(
        [
            {
                "Symbol": d.symbol,
                "Proceeds": exact(d.proceeds),
                "Disposed basis": exact(d.basis),
                "Realized gain": exact(d.gain),
                "Method": d.method,
                "Event ID": d.event_id,
                "Consumed lots": ", ".join(a.lot_id for a in d.matches),
            }
            for d in result.disposals
            if d.account_id == account_id
        ]
    )
    candidates = [
        e for e in ds.events if e.account_id == account_id and e.kind in {K.SELL, K.TRANSFER}
    ]
    if not candidates:
        st.info("Add a sale or transfer to review or change its allocation.")
        return
    selected = st.selectbox(
        "Sale or transfer allocation",
        [e.id for e in candidates],
        format_func=lambda id_: next(
            f"{e.effective_date} · {e.kind} · {e.symbol} · {e.quantity} · {id_[:8]}"
            for e in candidates
            if e.id == id_
        ),
    )
    e = next(e for e in candidates if e.id == selected)
    before = replace(
        ds,
        events=tuple(
            x
            for x in ds.events
            if (x.effective_date, x.day_sequence) < (e.effective_date, e.day_sequence)
        ),
    )
    available = [
        l
        for l in replay(before, e.effective_date).lots
        if l.account_id == account_id and l.symbol == e.symbol and l.quantity > 0
    ]
    draft = draft_for("allocation:" + e.id)
    allocations = []
    existing = {a.lot_id: a for a in e.allocations}
    for lot in available:
        st.caption(
            f"Lot {lot.id} · available {exact(lot.quantity)} · basis {exact(lot.basis)} · acquired {lot.acquired_date or 'Unknown'}"
        )
        allocation = existing.get(lot.id)
        quantity = text_input(
            draft,
            "quantity:" + lot.id,
            f"Quantity from {lot.id[:8]}",
            exact(allocation.quantity) if allocation else "0",
        )
        basis = (
            text_input(
                draft,
                "basis:" + lot.id,
                f"User supplied pool basis for {lot.id[:8]}",
                exact(allocation.basis_amount)
                if allocation and allocation.basis_amount is not None
                else "",
            )
            if lot.aggregate
            else ""
        )
        allocations.append((lot.id, quantity, basis))
    reason = text_input(draft, "reason", "Allocation reason / source")

    def build():
        chosen = tuple(
            LotAllocation(id_, decimal_input(q, positive=True), decimal_input(b) if b else None)
            for id_, q, b in allocations
            if q and D(q) != 0
        )
        if not chosen:
            raise ValueError(
                "Select complete lot quantities; total must equal the sale/transfer quantity."
            )
        return (replace(e, allocations=chosen),), (), reason

    operation_controls(repo, draft, build, label="allocation")
