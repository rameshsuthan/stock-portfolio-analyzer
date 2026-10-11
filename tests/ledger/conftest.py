from datetime import date
from decimal import Decimal as D
from uuid import NAMESPACE_URL, uuid5

from stock_portfolio.ledger.models import Account, EventKind, LedgerDataset, LedgerEvent

DAY = date(2025, 1, 1)
END = date(2025, 12, 31)
A = Account("a", "Alpha")
B = Account("b", "Beta")


def event(name, kind="BUY", day=1, seq=1, account="a", symbol="ABC", **kwargs):
    for key in ("quantity", "price", "fees", "amount", "basis"):
        if key in kwargs and kwargs[key] is not None:
            kwargs[key] = D(kwargs[key])
    return LedgerEvent(
        str(uuid5(NAMESPACE_URL, name)),
        account,
        date(2025, 1, day),
        seq,
        EventKind(kind),
        symbol,
        **kwargs,
    )


def dataset(*events, accounts=(A, B)):
    return LedgerDataset(accounts, tuple(events), 0, 0)
