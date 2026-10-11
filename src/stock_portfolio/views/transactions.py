from datetime import date
from uuid import uuid4

import streamlit as st

from ..ledger.codec import event_from_json
from ..ledger.models import EventKind as K
from ..ledger.models import LedgerEvent
from ..ledger.validation import decimal_input, iso_date
from ..presentation import exact, table
from ..ui_state import draft_for, text_input
from .common import operation_controls


def render(repo, account_id, as_of, notices):
    from .data import import_wizard

    ds = repo.load_dataset()
    active = {e.id: e for e in ds.events}
    accounts = {a.id: a.name for a in ds.accounts}
    st.subheader("Transactions")
    query = st.text_input("Filter transactions by symbol or note", key="event_filter").casefold()
    events = [
        e
        for e in ds.events
        if e.account_id == account_id
        and e.effective_date <= as_of
        and (query in e.symbol.casefold() or query in e.notes.casefold())
    ]
    table(
        [
            {
                "Date": str(e.effective_date),
                "Sequence": e.day_sequence,
                "Symbol": e.symbol,
                "Type": e.kind.value,
                "Quantity": exact(e.quantity),
                "Price": exact(e.price),
                "Fees": exact(e.fees),
                "Amount": exact(e.amount),
                "Destination": accounts.get(e.destination_account_id, ""),
                "Event ID": e.id,
                "Notes": e.notes,
            }
            for e in sorted(events, key=lambda e: (e.effective_date, e.day_sequence))
        ]
    )
    with st.expander(
        "Add, revise or void an event",
        expanded=True,
        key="panel:transactions.py:Add, revise or void an event",
        on_change="rerun",
    ):
        action = st.selectbox(
            "Event action", ("Add", "Revise", "Void", "Revive"), key="event_action"
        )
        old = None
        if action != "Add":
            identities = [
                r
                for r in repo.identities()
                if r["account_id"] == account_id and (r["status"] == "void") == (action == "Revive")
            ]
            if not identities:
                st.info("No events available for this action.")
            else:
                selected = st.selectbox(
                    "Event to change",
                    [r["id"] for r in identities],
                    format_func=lambda id_: (
                        f"{event_from_json(next(r['payload'] for r in identities if r['id'] == id_)).kind} · {id_}"
                    ),
                )
                old = event_from_json(next(r["payload"] for r in identities if r["id"] == selected))
        if action == "Add" or old:
            draft = draft_for("event:" + action + (":" + old.id if old else ""))
            allowed = [k.value for k in K]
            kind = st.selectbox(
                "Event type",
                allowed,
                index=allowed.index(old.kind.value) if old else 2,
                key="event_kind:" + draft.key,
                disabled=bool(old),
            )
            if draft.inputs.get("_kind", kind) != kind:
                draft.inputs.pop("_preview", None)
            draft.inputs["_kind"] = kind
            day = text_input(
                draft, "date", "Effective date", str(old.effective_date if old else date.today())
            )
            symbol = text_input(draft, "symbol", "Symbol", old.symbol if old else "")
            sequence = text_input(
                draft,
                "sequence",
                "Day sequence (blank appends)",
                str(old.day_sequence) if old else "",
            )
            quantity = price = fees = amount = basis = acquired = numerator = denominator = (
                destination
            ) = link = ""
            if kind in {"BUY", "SELL", "TRANSFER", "OPENING_LOT", "OPENING_BALANCE"}:
                quantity = text_input(
                    draft,
                    "quantity",
                    "Quantity",
                    exact(old.quantity) if old and old.quantity is not None else "",
                )
            if kind in {"BUY", "SELL"}:
                price = text_input(draft, "price", "Trade price", exact(old.price) if old else "")
                fees = text_input(draft, "fees", "Trade fees", exact(old.fees) if old else "0")
            if kind in {"OPENING_LOT", "OPENING_BALANCE"}:
                basis = text_input(
                    draft, "basis", "Opening total basis", exact(old.basis) if old else ""
                )
            if kind == "OPENING_LOT":
                acquired = text_input(
                    draft,
                    "acquired",
                    "Actual acquisition date",
                    str(old.acquired_date) if old else "",
                )
            if kind == "DIVIDEND":
                amount = text_input(
                    draft, "amount", "Dividend amount", exact(old.amount) if old else ""
                )
            if kind == "SPLIT":
                numerator = text_input(
                    draft, "numerator", "Split numerator", str(old.split_numerator) if old else "2"
                )
                denominator = text_input(
                    draft,
                    "denominator",
                    "Split denominator",
                    str(old.split_denominator) if old else "1",
                )
                st.info(
                    "Record this split in every affected account. Unsupported cash-in-lieu is rejected."
                )
            if kind == "TRANSFER":
                destination = text_input(
                    draft,
                    "destination",
                    "Destination account name",
                    accounts.get(old.destination_account_id, "") if old else "",
                )
            if kind == "BUY":
                link = text_input(
                    draft,
                    "link",
                    "Reinvestment dividend event ID (optional)",
                    old.reinvestment_of or "" if old else "",
                )
            notes = text_input(draft, "notes", "Notes", old.notes if old else "")
            reason = text_input(
                draft, "reason", "Reason / source", "Manual entry" if action == "Add" else ""
            )

            def build():
                effective = iso_date(day)
                seq = (
                    int(sequence)
                    if sequence
                    else max(
                        (e.day_sequence for e in ds.events if e.effective_date == effective),
                        default=0,
                    )
                    + 1
                )
                values = {}
                for field, val in [
                    ("quantity", quantity),
                    ("price", price),
                    ("fees", fees),
                    ("amount", amount),
                    ("basis", basis),
                ]:
                    if val:
                        values[field] = decimal_input(val, positive=field == "quantity")
                if acquired:
                    values["acquired_date"] = iso_date(acquired)
                if numerator:
                    values.update(
                        split_numerator=int(numerator), split_denominator=int(denominator)
                    )
                if destination:
                    values["destination_account_id"] = next(
                        (id_ for id_, name in accounts.items() if name == destination), None
                    )
                    if values["destination_account_id"] is None:
                        raise ValueError("Use an exact existing destination account name.")
                event = LedgerEvent(
                    old.id if old else str(uuid4()),
                    account_id,
                    effective,
                    seq,
                    K(kind),
                    symbol.strip().upper(),
                    **values,
                    notes=notes,
                    external_id=old.external_id if old else None,
                    allocations=old.allocations if old else (),
                    reinvestment_of=link or None,
                )
                linked = []
                if old:
                    linked = [
                        e
                        for e in ds.events
                        if e.reinvestment_of == old.id or e.id == old.reinvestment_of
                    ]
                if action == "Void":
                    return (), tuple(e.id for e in [old, *linked]), reason
                if event.reinvestment_of and event.reinvestment_of in active:
                    linked = [active[event.reinvestment_of]]
                return (event, *linked), (), reason

            operation_controls(repo, draft, build)
    with st.expander(
        "Record dividend and reinvestment together",
        key="panel:transactions.py:Record dividend and reinvestment together",
        on_change="rerun",
    ):
        draft = draft_for("reinvestment")
        day = text_input(draft, "date", "Reinvestment date", str(date.today()))
        symbol = text_input(draft, "symbol", "Reinvestment symbol")
        amount = text_input(draft, "amount", "Cash dividend received")
        quantity = text_input(draft, "quantity", "Reinvested quantity")
        price = text_input(draft, "price", "Reinvestment price")
        fees = text_input(draft, "fees", "Reinvestment fees", "0")
        reason = text_input(draft, "reason", "Reinvestment source", "Manual reinvestment")

        def build_reinvestment():
            day_ = iso_date(day)
            seq = (
                max((e.day_sequence for e in ds.events if e.effective_date == day_), default=0) + 1
            )
            div = LedgerEvent(
                str(uuid4()),
                account_id,
                day_,
                seq,
                K.DIVIDEND,
                symbol.strip().upper(),
                amount=decimal_input(amount),
            )
            buy = LedgerEvent(
                str(uuid4()),
                account_id,
                day_,
                seq + 1,
                K.BUY,
                symbol.strip().upper(),
                quantity=decimal_input(quantity, positive=True),
                price=decimal_input(price),
                fees=decimal_input(fees),
                reinvestment_of=div.id,
            )
            return (div, buy), (), reason

        operation_controls(repo, draft, build_reinvestment, label="reinvestment")
    with st.expander(
        "Import transactions CSV",
        expanded=True,
        key="panel:transactions.py:Import transactions CSV",
        on_change="rerun",
    ):
        import_wizard(repo, account_id, as_of, kind="transactions")
