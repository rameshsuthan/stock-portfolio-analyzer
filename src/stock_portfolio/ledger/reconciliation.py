"""Compare immutable broker assertions to historical replay, never mutate holdings."""

from datetime import date
from decimal import Decimal as D

from .engine import replay
from .models import ReconciliationResult, ReconciliationRow
from .validation import decimal_input, precise
from .valuation import check_as_of


def validate_statement(dataset, statement):
    check_as_of(dataset, statement.account_id, statement.as_of)
    if type(statement.as_of) is not date or statement.as_of > date.today():
        raise ValueError("Statement date must be a nonfuture date.")
    seen = set()
    for h in statement.holdings:
        if not h.symbol or h.symbol != h.symbol.strip().upper() or h.symbol in seen:
            raise ValueError("Statement symbols must be unique and normalized.")
        seen.add(h.symbol)
        decimal_input(h.quantity)
        if h.basis is not None:
            decimal_input(h.basis)


@precise
def reconcile(dataset, statement, quantity_tolerance=D("0.00000001"), basis_tolerance=D("0.01")):
    validate_statement(dataset, statement)
    for tolerance in (quantity_tolerance, basis_tolerance):
        if not tolerance.is_finite() or tolerance < 0:
            raise ValueError("Tolerances must be finite and nonnegative.")
    local = {
        p.symbol: p
        for p in replay(dataset, statement.as_of).positions
        if p.account_id == statement.account_id
    }
    broker = {h.symbol: h for h in statement.holdings}
    rows = []
    for symbol in sorted(local.keys() | broker.keys()):
        l, b = local.get(symbol), broker.get(symbol)
        lq, bq = l.quantity if l else None, b.quantity if b else None
        lb, bb = l.basis if l else None, b.basis if b else None
        qdiff = lq - bq if lq is not None and bq is not None else None
        bdiff = lb - bb if lb is not None and bb is not None else None
        if l is None:
            status = "missing_local"
        elif b is None:
            status = "missing_broker"
        elif abs(qdiff) > quantity_tolerance:
            status = "mismatch"
        elif bdiff is None:
            status = "unresolved"
        elif abs(bdiff) > basis_tolerance:
            status = "mismatch"
        else:
            status = "matched"
        rows.append(ReconciliationRow(symbol, lq, bq, lb, bb, qdiff, bdiff, status))
    return ReconciliationResult(
        statement.id,
        statement.account_id,
        statement.as_of,
        statement.source_hash,
        dataset.economic_revision,
        "fifo-v1",
        quantity_tolerance,
        basis_tolerance,
        tuple(rows),
    )
