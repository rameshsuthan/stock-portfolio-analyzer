"""Dated end-of-day observations and explicitly incomplete totals."""

from decimal import Decimal as D

from .models import AccountValuation, Issue, ValuedPosition
from .models import EventKind as K
from .validation import precise


def check_as_of(dataset, account_id, as_of):
    account = next((a for a in dataset.accounts if a.id == account_id), None)
    if account is None:
        raise ValueError("Unknown account.")
    if account.opening_date and as_of < account.opening_date:
        raise ValueError("Date precedes opening cutoff; earlier holdings are not known.")
    return account


@precise
def value_account(dataset, replayed, prices, account_id, as_of):
    check_as_of(dataset, account_id, as_of)
    latest = {}
    for p in prices:
        if p.price_date <= as_of and (
            p.symbol not in latest or p.price_date > latest[p.symbol].price_date
        ):
            latest[p.symbol] = p
    split_dates = {}
    for e in dataset.events:
        if e.kind == K.SPLIT and e.account_id == account_id and e.effective_date <= as_of:
            split_dates[e.symbol] = max(
                split_dates.get(e.symbol, e.effective_date), e.effective_date
            )
    holdings = []
    for p in replayed.positions:
        if p.account_id != account_id:
            continue
        observation = latest.get(p.symbol)
        issues = list(p.issues)
        if (
            observation
            and p.symbol in split_dates
            and observation.price_date < split_dates[p.symbol]
        ):
            issues.append(
                Issue(
                    "pre_split_price",
                    "Supply a price dated on or after the split.",
                    account_id=account_id,
                    symbol=p.symbol,
                )
            )
            observation = None
        if observation is None:
            issues.append(
                Issue(
                    "missing_price",
                    "No usable dated price observation.",
                    account_id=account_id,
                    symbol=p.symbol,
                )
            )
        elif (as_of - observation.price_date).days > 7:
            issues.append(
                Issue(
                    "stale_price",
                    "Price is older than 7 calendar days.",
                    account_id=account_id,
                    symbol=p.symbol,
                )
            )
        market = p.quantity * observation.price if observation else None
        gain = market - p.basis if market is not None and p.basis is not None else None
        holdings.append(
            ValuedPosition(
                p,
                observation.price if observation else None,
                observation.price_date if observation else None,
                market,
                gain,
                tuple(issues),
            )
        )
    basis = sum((h.position.basis for h in holdings if h.position.basis is not None), D(0))
    market = sum((h.market_value for h in holdings if h.market_value is not None), D(0))
    total_basis = basis if all(h.position.basis is not None for h in holdings) else None
    total_value = market if all(h.market_value is not None for h in holdings) else None
    gain = (
        total_value - total_basis if total_basis is not None and total_value is not None else None
    )
    sales = [d for d in replayed.disposals if d.account_id == account_id]
    realized = (
        sum((d.gain for d in sales), D(0)) if all(d.gain is not None for d in sales) else None
    )
    return AccountValuation(
        account_id,
        as_of,
        tuple(holdings),
        basis,
        market,
        total_basis,
        total_value,
        gain,
        realized,
        replayed.dividends.get(account_id, D(0)),
        tuple(i for h in holdings for i in h.issues) + tuple(i for d in sales for i in d.issues),
    )
