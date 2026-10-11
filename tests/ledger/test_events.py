from dataclasses import replace
from decimal import Decimal as D

import pytest
from conftest import END, dataset, event

from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.models import InvalidLedger


def test_dividend_reinvestment_and_uninvested_remainder():
    dividend = event("div", "DIVIDEND", amount="50")
    buy = event("buy", seq=2, quantity=".4", price="120", fees="1", reinvestment_of=dividend.id)
    result = replay(dataset(dividend, buy), END)
    assert result.dividends == {"a": D(50)}
    assert (result.positions[0].quantity, result.positions[0].basis) == (D(".4"), D(49))
    assert result.reinvestments[0].remainder == 1
    assert replay(dataset(replace(buy, reinvestment_of=None)), END).dividends == {}


@pytest.mark.parametrize(
    "case", ["missing", "account", "symbol", "sequence", "expensive", "duplicate"]
)
def test_invalid_reinvestment_links(case):
    dividend = event("div", "DIVIDEND", amount="50")
    buy = event("buy", seq=2, quantity=".4", price="120", fees="1", reinvestment_of=dividend.id)
    if case == "missing":
        buy = replace(buy, reinvestment_of="missing")
    if case == "account":
        buy = replace(buy, account_id="b")
    if case == "symbol":
        buy = replace(buy, symbol="OTHER")
    if case == "sequence":
        dividend, buy = replace(dividend, day_sequence=2), replace(buy, day_sequence=1)
    if case == "expensive":
        buy = replace(buy, fees=D(3))
    events = [dividend, buy]
    if case == "duplicate":
        events.append(replace(buy, id=event("b2").id, day_sequence=3))
    with pytest.raises(InvalidLedger):
        replay(dataset(*events), END)


def test_split_preserves_basis_dates_and_rejects_fractional_settlement():
    buy = event("buy", quantity="10", price="100")
    split = event("split", "SPLIT", day=2, split_numerator=2, split_denominator=1)
    reverse = event("reverse", "SPLIT", day=3, split_numerator=1, split_denominator=4)
    result = replay(dataset(buy, split), END)
    assert (result.positions[0].quantity, result.positions[0].basis) == (D(20), D(1000))
    result = replay(dataset(buy, split, reverse), END)
    assert (result.positions[0].quantity, result.positions[0].basis) == (D(5), D(1000))
    assert result.lots[0].acquired_date == buy.effective_date
    with pytest.raises(InvalidLedger, match="cash-in-lieu"):
        replay(
            dataset(
                replace(buy, quantity=D(1)), replace(split, split_numerator=1, split_denominator=3)
            ),
            END,
        )
    with pytest.raises(InvalidLedger):
        replay(dataset(split), END)
    with pytest.raises(InvalidLedger):
        replay(dataset(buy, replace(split, split_numerator=0)), END)
