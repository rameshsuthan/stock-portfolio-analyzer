"""Deterministic, precision-50 replay. No database, UI, or clock dependency."""

from decimal import Decimal as D

from .lots import LotBook, invalid
from .models import Disposal, InvalidLedger, Issue, Lot, LotAllocation, Position, ReplayResult
from .models import EventKind as K
from .validation import precise, validate_events


@precise
def replay(dataset, as_of):
    issues = validate_events(dataset)
    if issues:
        raise InvalidLedger(issues)
    book, disposals = LotBook(), []
    for e in sorted(dataset.events, key=lambda e: (e.effective_date, e.day_sequence)):
        if e.effective_date > as_of:
            continue
        if e.kind in {K.BUY, K.OPENING_LOT, K.OPENING_BALANCE}:
            basis = e.quantity * e.price + e.fees if e.kind == K.BUY else e.basis
            acquired = e.effective_date if e.kind == K.BUY else e.acquired_date
            book.add(
                Lot(
                    e.id,
                    e.account_id,
                    e.symbol,
                    acquired,
                    (e.effective_date, e.day_sequence, e.id),
                    e.quantity,
                    basis,
                    e.id,
                    aggregate=e.kind == K.OPENING_BALANCE,
                )
            )
        elif e.kind == K.SELL:
            slices = book.consume(e)
            known = all(basis is not None for _, _, basis in slices)
            basis = sum((basis for _, _, basis in slices), D(0)) if known else None
            proceeds = e.quantity * e.price - e.fees
            issues = (
                ()
                if known
                else (
                    Issue(
                        "unknown_basis", "Sale basis unresolved; no gain estimate.", event_id=e.id
                    ),
                )
            )
            match_proceeds, fee_left = [], e.fees
            for index, (_, quantity, _) in enumerate(slices):
                fee = fee_left if index == len(slices) - 1 else e.fees * quantity / e.quantity
                fee_left -= fee
                match_proceeds.append(quantity * e.price - fee)
            disposals.append(
                Disposal(
                    e.id,
                    e.account_id,
                    e.symbol,
                    e.quantity,
                    proceeds,
                    basis,
                    proceeds - basis if known else None,
                    "Explicit" if e.allocations else "FIFO",
                    tuple(LotAllocation(lot.id, q, b) for lot, q, b in slices),
                    issues,
                    tuple(match_proceeds),
                )
            )
        else:
            invalid(e, "Unsupported event handler.")
    positions = []
    for (account, symbol), ids in book.by_position.items():
        lots = [book.lots[i] for i in ids if book.lots[i].quantity]
        if not lots:
            continue
        basis = (
            sum((l.basis for l in lots), D(0)) if all(l.basis is not None for l in lots) else None
        )
        issues = tuple(i for l in lots for i in l.issues)
        positions.append(
            Position(
                account,
                symbol,
                sum((l.quantity for l in lots), D(0)),
                basis,
                tuple(l.id for l in lots),
                issues,
            )
        )
    issues = tuple(i for p in positions for i in p.issues) + tuple(
        i for d in disposals for i in d.issues
    )
    return ReplayResult(
        tuple(book.lots.values()), tuple(positions), tuple(disposals), {}, (), issues
    )
