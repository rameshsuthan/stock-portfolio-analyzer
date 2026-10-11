from decimal import Decimal as D

from stock_portfolio.calculations import analyze
from stock_portfolio.models import Holding, Selection


def holding(symbol, quantity, basis, price, sector="Unknown"):
    return Holding(symbol, D(quantity), D(basis), D(price), symbol, sector)


def test_demo_totals_and_allocations():
    a = analyze([holding("DEMO_A", "10", "1000", "120"), holding("DEMO_B", "5", "1000", "180")])
    assert (a.cost_basis, a.market_value, a.gain, a.gain_percent, a.count) == (
        2000,
        2100,
        100,
        5,
        2,
    )
    assert [f"{v:.2f}" for v in a.stock_allocations.values()] == ["57.14", "42.86"]


def test_weighted_percentage():
    a = analyze([holding("A", "1", "100", "110"), holding("B", "1", "900", "810")])
    assert a.gain_percent == -8


def test_fractional_decimal_and_average_cost():
    a = analyze([holding("A", ".1", ".02", ".3")])
    assert (a.market_value, a.gain, a.gain_percent) == (D(".03"), D(".01"), 50)
    assert a.holdings[0].average_cost == D(".2")


def test_undefined_and_empty():
    a = analyze([holding("A", "1", "0", "0")])
    assert a.gain_percent is None
    assert a.stock_allocations == {}
    assert a.holdings[0].gain_percent is None
    a = analyze([holding("A", "1", "10", "20")], Selection(symbols=frozenset()))
    assert a.count == 0 and a.market_value == 0 and a.gain_percent is None


def test_intersecting_filters():
    rows = [holding("A", "1", "10", "20", "Tech"), holding("B", "1", "30", "40", "Health")]
    a = analyze(rows, Selection(frozenset({"A", "B"}), frozenset({"Tech"})))
    assert a.count == 1 and a.market_value == 20
    assert a.sector_allocations == {"Tech": 100}
