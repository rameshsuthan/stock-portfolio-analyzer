"""Mutable replay-only lot book. Public results are immutable."""

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal as D

from .models import InvalidLedger, Issue, LotAllocation


def invalid(event, message, code="invalid_history"):
    raise InvalidLedger(
        (Issue(code, message, event_id=event.id, account_id=event.account_id, symbol=event.symbol),)
    )


@dataclass
class Pool:
    original_basis: D | None
    assigned: D = D(0)
    unresolved: bool = False


class LotBook:
    def __init__(self):
        self.lots = {}
        self.by_position = {}
        self.pools = {}

    def add(self, lot, pool=None):
        self.lots[lot.id] = lot
        self.by_position.setdefault((lot.account_id, lot.symbol), []).append(lot.id)
        if lot.aggregate:
            self.pools[lot.id] = pool or Pool(lot.basis)

    def available(self, account, symbol):
        return [
            self.lots[i]
            for i in self.by_position.get((account, symbol), ())
            if self.lots[i].quantity > 0
        ]

    def consume(self, event):
        available = self.available(event.account_id, event.symbol)
        if sum((lot.quantity for lot in available), D(0)) < event.quantity:
            invalid(
                event, "Quantity exceeds shares available at this point in history.", "oversell"
            )
        if event.allocations:
            selections = event.allocations
            if sum((a.quantity for a in selections), D(0)) != event.quantity:
                invalid(event, "Explicit allocations must cover the entire quantity.")
        else:
            selections, left = [], event.quantity
            for lot in sorted(
                available, key=lambda l: (l.acquired_date or date.min, l.acquisition_order, l.id)
            ):
                q = min(left, lot.quantity)
                if q:
                    selections.append(LotAllocation(lot.id, q))
                    left -= q
                if not left:
                    break
        slices = []
        for a in selections:
            lot = self.lots.get(a.lot_id)
            if (
                lot is None
                or lot.account_id != event.account_id
                or lot.symbol != event.symbol
                or a.quantity > lot.quantity
            ):
                invalid(event, "Allocation references an unavailable or overdrawn lot.")
            left = lot.quantity - a.quantity
            if not lot.aggregate:
                if a.basis_amount is not None:
                    invalid(event, "Exact lot basis cannot be overridden.")
                basis = lot.basis if not left else lot.basis * a.quantity / lot.quantity
                remainder = lot.basis - basis
            else:
                pool = self.pools[lot.id]
                basis = a.basis_amount
                if basis is None and not left and lot.basis is not None:
                    basis = lot.basis
                if basis is None:
                    pool.unresolved = True
                else:
                    if pool.original_basis is None:
                        invalid(
                            event,
                            "Resolve the source transfer basis before assigning descendant basis.",
                        )
                    pool.assigned += basis
                    if pool.assigned > pool.original_basis:
                        invalid(event, "Supplied basis exceeds original pool basis.")
                if not left and not pool.unresolved and pool.assigned != pool.original_basis:
                    invalid(event, "Fully consumed pool allocations must equal original basis.")
                remainder = None if pool.unresolved else pool.original_basis - pool.assigned
                if not left:
                    remainder = D(0)
            issues = (
                ()
                if remainder is not None
                else (
                    Issue(
                        "unknown_basis",
                        "Unresolved aggregate consumption; supply basis or detailed lots.",
                        account_id=lot.account_id,
                        symbol=lot.symbol,
                    ),
                )
            )
            self.lots[lot.id] = replace(lot, quantity=left, basis=remainder, issues=issues)
            slices.append((lot, a.quantity, basis))
        return slices
