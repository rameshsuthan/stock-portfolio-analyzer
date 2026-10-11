"""Input shape validation, distinct from chronological replay."""

import re
from datetime import date
from decimal import Decimal, localcontext
from uuid import UUID

from .models import EventKind as K
from .models import Issue

OPENINGS = {K.OPENING_LOT, K.OPENING_BALANCE}


def decimal_input(value, *, positive=False):
    text = str(value)
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", text):
        raise ValueError("Enter a plain decimal.")
    number = Decimal(text)
    if len(number.as_tuple().digits) > 18 or number.as_tuple().exponent < -8:
        raise ValueError("Maximum 18 significant digits and 8 decimal places.")
    if number < 0 or (positive and number == 0):
        raise ValueError("Quantity must be positive; other amounts nonnegative.")
    return number


def iso_date(text):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("Use YYYY-MM-DD dates.")
    return date.fromisoformat(text)


def validate_events(dataset, today=None):
    issues, ids, sequences, external, openings = [], set(), set(), set(), {}
    accounts = {a.id: a for a in dataset.accounts}
    for a in dataset.accounts:
        if (
            a.currency != "USD"
            or not a.name.strip()
            or (today and a.opening_date and a.opening_date > today)
        ):
            issues.append(
                Issue(
                    "account", "Invalid account currency, name or opening cutoff.", account_id=a.id
                )
            )
    for e in dataset.events:

        def error(code, message, e=e):
            issues.append(
                Issue(code, message, event_id=e.id, account_id=e.account_id, symbol=e.symbol)
            )

        try:
            UUID(e.id)
            if e.id in ids:
                raise ValueError("Duplicate event identity.")
            ids.add(e.id)
            if e.account_id not in accounts:
                raise ValueError("Unknown account.")
            a = accounts[e.account_id]
            if not isinstance(e.kind, K) or not e.symbol or e.symbol != e.symbol.strip().upper():
                raise ValueError("Unsupported event type or unnormalized symbol.")
            if type(e.effective_date) is not date or (today and e.effective_date > today):
                raise ValueError("Invalid or future economic date.")
            if type(e.day_sequence) is not int or e.day_sequence < 1:
                raise ValueError("Sequence must be a positive integer.")
            key = (e.effective_date, e.day_sequence)
            if key in sequences:
                raise ValueError("Active day sequences must be globally unique.")
            sequences.add(key)
            if e.external_id:
                key = (e.account_id, e.external_id)
                if key in external:
                    raise ValueError("Duplicate account-scoped external ID.")
                external.add(key)
            required = {
                K.BUY: {"quantity", "price"},
                K.SELL: {"quantity", "price"},
                K.OPENING_LOT: {"quantity", "basis", "acquired_date"},
                K.OPENING_BALANCE: {"quantity", "basis"},
                K.DIVIDEND: {"amount"},
                K.SPLIT: {"split_numerator", "split_denominator"},
                K.TRANSFER: {"quantity", "destination_account_id"},
            }[e.kind]
            fields = {
                "quantity",
                "price",
                "basis",
                "amount",
                "acquired_date",
                "split_numerator",
                "split_denominator",
                "destination_account_id",
            }
            for field in fields:
                value = getattr(e, field)
                if field in required and value is None:
                    raise ValueError(f"{field} is required.")
                if field not in required and value is not None:
                    raise ValueError(f"{field} is irrelevant for {e.kind}.")
            for field in ("quantity", "price", "basis", "amount", "fees"):
                value = getattr(e, field)
                if value is not None:
                    if not isinstance(value, Decimal):
                        raise ValueError("Numeric inputs must be Decimal.")
                    decimal_input(value, positive=field == "quantity")
            if e.kind not in {K.BUY, K.SELL} and e.fees != 0:
                raise ValueError("Fees only apply to BUY/SELL.")
            if e.allocations and e.kind not in {K.SELL, K.TRANSFER}:
                raise ValueError("Allocations only apply to sales/transfers.")
            seen_lots = set()
            for allocation in e.allocations:
                if allocation.lot_id in seen_lots:
                    raise ValueError("A lot may appear only once per allocation.")
                seen_lots.add(allocation.lot_id)
                decimal_input(allocation.quantity, positive=True)
                if allocation.basis_amount is not None:
                    decimal_input(allocation.basis_amount)
            if e.kind in OPENINGS:
                if not a.opening_date or e.effective_date != a.opening_date:
                    raise ValueError("Opening records must match the account cutoff.")
                if e.acquired_date and (
                    type(e.acquired_date) is not date or e.acquired_date > a.opening_date
                ):
                    raise ValueError("Acquired date must be on/before cutoff.")
                key = (a.id, e.symbol)
                previous = openings.setdefault(key, [])
                if previous and (e.kind == K.OPENING_BALANCE or K.OPENING_BALANCE in previous):
                    raise ValueError("Use detailed lots or one aggregate opening, never both.")
                previous.append(e.kind)
            elif a.opening_date and e.effective_date <= a.opening_date:
                raise ValueError("Activity must be strictly after opening cutoff.")
            if e.reinvestment_of and e.kind != K.BUY:
                raise ValueError("Only a BUY may link to a dividend.")
        except (ValueError, TypeError, ArithmeticError) as exc:
            error("invalid_event", str(exc))
    return tuple(issues)


def precise(function):
    """Scope all derived arithmetic, leaving the process Decimal context untouched."""
    from functools import wraps

    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext() as context:
            context.prec = 50
            return function(*args, **kwargs)

    return wrapped
