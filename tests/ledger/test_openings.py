from dataclasses import replace
from datetime import date
from decimal import Decimal as D
from decimal import localcontext

import pytest
from conftest import END, A, dataset, event

from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.models import InvalidLedger, LotAllocation

OPEN = replace(A, opening_date=date(2025, 1, 1))


def pool():
    return event("pool", "OPENING_BALANCE", quantity="10", basis="1000")


def test_unknown_opening_basis_is_not_prorated():
    p = pool()
    sale = event("s", "SELL", day=2, quantity="4", price="150")
    result = replay(dataset(p, sale, accounts=(OPEN,)), END)
    assert (result.positions[0].quantity, result.positions[0].basis) == (D(6), None)
    assert (result.disposals[0].proceeds, result.disposals[0].gain) == (D(600), None)
    result = replay(
        dataset(
            p, replace(sale, allocations=(LotAllocation(p.id, D(4), D(400)),)), accounts=(OPEN,)
        ),
        END,
    )
    assert (result.positions[0].basis, result.disposals[0].gain) == (D(600), D(200))
    result = replay(dataset(p, replace(sale, quantity=D(10)), accounts=(OPEN,)), END)
    assert (result.disposals[0].basis, result.disposals[0].gain) == (D(1000), D(500))


def test_all_disposed_pool_keeps_prior_unresolved_sales():
    result = replay(
        dataset(
            pool(),
            event("s1", "SELL", day=2, quantity="4", price="1"),
            event("s2", "SELL", day=3, quantity="6", price="1"),
            accounts=(OPEN,),
        ),
        END,
    )
    assert result.positions == ()
    assert all(d.gain is None for d in result.disposals)
    assert result.lots[0].basis == 0


def test_conservation_three_fractional_basis_sales():
    opening = event("lot", "OPENING_LOT", quantity="3", basis="1", acquired_date=date(2020, 1, 1))
    result = replay(
        dataset(
            opening,
            *(event(f"s{i}", "SELL", day=i, quantity="1", price="1") for i in (2, 3, 4)),
            accounts=(OPEN,),
        ),
        END,
    )
    with localcontext() as ctx:
        ctx.prec = 50
        assert sum(d.basis for d in result.disposals) == D(1)
    assert result.positions == ()
    assert result.lots[0].basis == 0


def test_dated_fifo_zero_basis_and_unaffected_symbol():
    new = event("new", "OPENING_LOT", quantity="1", basis="100", acquired_date=date(2024, 1, 1))
    old = event(
        "old", "OPENING_LOT", seq=2, quantity="1", basis="0", acquired_date=date(2020, 1, 1)
    )
    result = replay(
        dataset(new, old, event("sale", "SELL", day=2, quantity="1", price="5"), accounts=(OPEN,)),
        END,
    )
    assert result.disposals[0].basis == 0
    result = replay(
        dataset(
            pool(),
            event("other", day=2, symbol="XYZ", quantity="1", price="3"),
            event("sale", "SELL", day=3, quantity="1", price="2"),
            accounts=(OPEN,),
        ),
        END,
    )
    assert {p.symbol: p.basis for p in result.positions} == {"ABC": None, "XYZ": D(3)}


@pytest.mark.parametrize(
    "case",
    [
        "cutoff",
        "future_acquired",
        "mixed",
        "double_pool",
        "no_cutoff",
        "missing_basis",
        "over_basis",
        "incomplete_basis",
    ],
)
def test_invalid_opening_history(case):
    p = pool()
    events = [p]
    accounts = (OPEN,)
    if case == "cutoff":
        events.append(event("b", seq=2, quantity="1", price="1"))
    elif case == "future_acquired":
        events = [replace(p, kind=type(p.kind).OPENING_LOT, acquired_date=END)]
    elif case == "mixed":
        events.append(
            event(
                "lot", "OPENING_LOT", seq=2, quantity="1", basis="1", acquired_date=date(2020, 1, 1)
            )
        )
    elif case == "double_pool":
        events.append(replace(p, id=event("p2").id, day_sequence=2))
    elif case == "no_cutoff":
        accounts = (A,)
    elif case == "missing_basis":
        events = [replace(p, basis=None)]
    else:
        amount = D(1001) if case == "over_basis" else D(999)
        events.append(
            event(
                "sale",
                "SELL",
                day=2,
                quantity="10",
                price="1",
                allocations=(LotAllocation(p.id, D(10), amount),),
            )
        )
    with pytest.raises(InvalidLedger):
        replay(dataset(*events, accounts=accounts), END)
