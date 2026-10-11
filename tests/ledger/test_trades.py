from dataclasses import replace
from decimal import Decimal as D

import pytest
from conftest import END, dataset, event

from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.models import InvalidLedger, LotAllocation


def buys():
    return event("b1", quantity="10", price="100", fees="10"), event(
        "b2", day=2, quantity="5", price="120", fees="5"
    )


def test_fifo_partial_sale_includes_fees():
    result = replay(
        dataset(*buys(), event("s", "SELL", day=3, quantity="12", price="150", fees="6")), END
    )
    sale = result.disposals[0]
    assert (sale.proceeds, sale.basis, sale.gain, sale.method) == (D(1794), D(1252), D(542), "FIFO")
    assert (result.positions[0].quantity, result.positions[0].basis) == (D(3), D(363))
    assert sum(m.quantity for m in sale.matches) == D(12)


def test_explicit_lots_override_fifo():
    b1, b2 = buys()
    sale = event(
        "s",
        "SELL",
        day=3,
        quantity="8",
        price="150",
        fees="4",
        allocations=(LotAllocation(b2.id, D(5)), LotAllocation(b1.id, D(3))),
    )
    result = replay(dataset(b1, b2, sale), END)
    assert (result.disposals[0].basis, result.disposals[0].gain) == (D(908), D(288))
    assert result.disposals[0].method == "Explicit"
    assert (result.positions[0].quantity, result.positions[0].basis) == (D(7), D(707))


@pytest.mark.parametrize(
    "mutation", ["partial", "future", "wrong_account", "overdrawn", "basis_override"]
)
def test_invalid_explicit_allocations(mutation):
    b1, b2 = buys()
    allocation = LotAllocation(b1.id, D(8))
    if mutation == "partial":
        allocation = replace(allocation, quantity=D(7))
    elif mutation == "future":
        b1 = replace(b1, effective_date=END)
    elif mutation == "wrong_account":
        b1 = replace(b1, account_id="b")
    elif mutation == "overdrawn":
        allocation = replace(allocation, lot_id=b2.id)
    else:
        allocation = replace(allocation, basis_amount=D(1))
    with pytest.raises(InvalidLedger):
        replay(
            dataset(
                b1,
                b2,
                event("s", "SELL", day=3, quantity="8", price="1", allocations=(allocation,)),
            ),
            END,
        )


@pytest.mark.parametrize(
    "quantity,price,fees",
    [
        ("-1", "2", "0"),
        ("0", "2", "0"),
        ("1", "-2", "0"),
        ("1", "2", "-1"),
        ("1.000000001", "2", "0"),
        ("NaN", "2", "0"),
    ],
)
def test_invalid_numeric_inputs(quantity, price, fees):
    with pytest.raises(InvalidLedger):
        replay(dataset(event("bad", quantity=quantity, price=price, fees=fees)), END)


def test_chronology_oversell_collision_and_full_liquidation():
    b = event("b", day=2, quantity="1", price="1")
    with pytest.raises(InvalidLedger):
        replay(dataset(event("s", "SELL", quantity="1", price="2"), b), END)
    with pytest.raises(InvalidLedger):
        replay(dataset(b, replace(b, id=event("other").id)), END)
    result = replay(
        dataset(b, event("s", "SELL", day=2, seq=2, quantity="1", price="0", fees="2")), END
    )
    assert result.positions == ()
    assert result.disposals[0].proceeds == -2
    assert result.disposals[0].gain == -3


def test_fee_residual_is_assigned_to_final_match():
    first = event("one", quantity="1", price="1")
    second = event("two", day=2, quantity="2", price="1")
    result = replay(
        dataset(first, second, event("sale", "SELL", day=3, quantity="3", price="2", fees="1")), END
    )
    from decimal import localcontext

    with localcontext() as ctx:
        ctx.prec = 50
        assert sum(result.disposals[0].match_proceeds) == D(5)
        assert result.disposals[0].match_proceeds[0] == D(2) - D(1) / D(3)
