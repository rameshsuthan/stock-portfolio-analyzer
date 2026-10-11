from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from uuid import NAMESPACE_URL, uuid5

import pytest
from conftest import END, A, B, dataset, event

from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.models import Account, InvalidLedger, LotAllocation


def test_transfer_preserves_dates_basis_and_no_income():
    buy = event("buy", quantity="10", price="100")
    transfer = event("transfer", "TRANSFER", day=2, quantity="4", destination_account_id="b")
    result = replay(dataset(buy, transfer), END)
    assert {p.account_id: (p.quantity, p.basis) for p in result.positions} == {
        "a": (D(6), D(600)),
        "b": (D(4), D(400)),
    }
    target = result.lots[-1]
    assert target.id == str(uuid5(NAMESPACE_URL, f"transfer:{transfer.id}:lot:{buy.id}"))
    assert target.acquired_date == buy.effective_date
    assert target.source_lot_id == buy.id
    assert result.disposals == () and result.dividends == {}
    sale = event("sale", "SELL", day=2, seq=2, account="b", quantity="4", price="110")
    assert replay(dataset(buy, transfer, sale), END).disposals[0].gain == 40


def test_multilot_explicit_transfer_and_invalid_dependencies():
    b1 = event("b1", quantity="10", price="100")
    b2 = event("b2", day=2, quantity="5", price="120")
    t = event(
        "t",
        "TRANSFER",
        day=3,
        quantity="7",
        destination_account_id="b",
        allocations=(LotAllocation(b2.id, D(5)), LotAllocation(b1.id, D(2))),
    )
    result = replay(dataset(b1, b2, t), END)
    assert len([l for l in result.lots if l.account_id == "b"]) == 2
    assert {p.account_id: p.basis for p in result.positions} == {"a": D(800), "b": D(800)}
    for bad in (
        replace(t, destination_account_id="a"),
        replace(t, destination_account_id="missing"),
        replace(t, quantity=D(20), allocations=()),
    ):
        with pytest.raises(InvalidLedger):
            replay(dataset(b1, b2, bad), END)
    with pytest.raises(InvalidLedger):
        replay(dataset(b1, b2, t, accounts=(A, replace(B, opening_date=date(2025, 1, 3)))), END)


def test_aggregate_transfer_uncertainty_and_resolution_propagates():
    opening = event("pool", "OPENING_BALANCE", quantity="10", basis="1000")
    transfer = event("t", "TRANSFER", day=2, quantity="4", destination_account_id="b")
    descendant = event(
        "t2", "TRANSFER", day=3, account="b", quantity="4", destination_account_id="c"
    )
    accounts = (replace(A, opening_date=date(2025, 1, 1)), B, Account("c", "Gamma"))
    result = replay(dataset(opening, transfer, descendant, accounts=accounts), END)
    assert {p.account_id: p.basis for p in result.positions} == {"a": None, "c": None}
    fixed = replace(transfer, allocations=(LotAllocation(opening.id, D(4), D(400)),))
    result = replay(dataset(opening, fixed, descendant, accounts=accounts), END)
    assert {p.account_id: p.basis for p in result.positions} == {"a": D(600), "c": D(400)}
    full = replay(dataset(opening, replace(transfer, quantity=D(10)), accounts=accounts), END)
    assert full.positions[0].basis == 1000
