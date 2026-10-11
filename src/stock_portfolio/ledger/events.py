"""Non-trade handlers operating on the same replay lot book."""

from dataclasses import replace
from decimal import Decimal as D
from fractions import Fraction
from uuid import NAMESPACE_URL, uuid5

from .lots import Pool, invalid
from .models import EventKind as K
from .models import Issue, Reinvestment


def reinvestment(event, seen, linked):
    dividend = seen.get(event.reinvestment_of)
    if (
        dividend is None
        or dividend.kind != K.DIVIDEND
        or dividend.account_id != event.account_id
        or dividend.symbol != event.symbol
        or dividend.effective_date != event.effective_date
        or dividend.id in linked
    ):
        invalid(
            event, "Reinvestment must reference one prior same-day dividend in this account/symbol."
        )
    cost = event.quantity * event.price + event.fees
    if cost > dividend.amount:
        invalid(event, "Reinvestment cost exceeds dividend amount.")
    linked.add(dividend.id)
    return Reinvestment(dividend.id, event.id, dividend.amount, cost, dividend.amount - cost)


def split(event, book):
    lots = book.available(event.account_id, event.symbol)
    if not lots:
        invalid(event, "Split requires held shares.")
    for value in (event.split_numerator, event.split_denominator):
        if type(value) is not int or value <= 0:
            invalid(event, "Split numerator and denominator must be positive integers.")
    for lot in lots:
        exact = Fraction(lot.quantity) * Fraction(event.split_numerator, event.split_denominator)
        if (exact * 100_000_000).denominator != 1:
            invalid(event, "Split requires unsupported cash-in-lieu/rounding settlement.")
        quantity = D(exact.numerator) / D(exact.denominator)
        book.lots[lot.id] = replace(lot, quantity=quantity)


def transfer(event, book, accounts):
    destination = accounts.get(event.destination_account_id)
    if destination is None or destination.id == event.account_id or destination.currency != "USD":
        invalid(event, "Transfer requires a different tracked USD destination account.")
    if destination.opening_date and event.effective_date <= destination.opening_date:
        invalid(event, "Transfer must be after destination opening cutoff.")
    for lot, quantity, basis in book.consume(event):
        target_id = str(uuid5(NAMESPACE_URL, f"transfer:{event.id}:lot:{lot.id}"))
        issues = (
            ()
            if basis is not None
            else (
                Issue(
                    "unknown_basis",
                    "Resolve basis on the source transfer to propagate here.",
                    account_id=destination.id,
                    symbol=event.symbol,
                ),
            )
        )
        target = replace(
            lot,
            id=target_id,
            account_id=destination.id,
            quantity=quantity,
            basis=basis,
            source_lot_id=lot.id,
            issues=issues,
        )
        book.add(target, Pool(basis, unresolved=basis is None) if lot.aggregate else None)
