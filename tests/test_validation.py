import pytest

from stock_portfolio.validation import validate_rows


def row(**changes):
    return dict(symbol=" a ", quantity=".1", cost_basis=".02", current_price=".3", **changes)


def test_normalization_and_defaults():
    r = validate_rows([row()])
    assert r.valid and r.holdings[0].symbol == "A"
    assert r.holdings[0].company_name == "A" and r.holdings[0].sector == "Unknown"


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", "0"),
        ("quantity", "-1"),
        ("cost_basis", "-1"),
        ("current_price", "NaN"),
        ("quantity", "Infinity"),
        ("quantity", "1e3"),
        ("cost_basis", "$1"),
        ("cost_basis", "1,000"),
        ("current_price", ""),
        ("quantity", "0.000000001"),
        ("cost_basis", "1234567890123456789"),
        ("symbol", ""),
    ],
)
def test_invalid_input_has_row_and_column(field, value):
    source = row()
    source[field] = value
    r = validate_rows([source])
    assert not r.valid and not r.holdings
    assert any(e.row == 2 and e.column == field for e in r.errors)


def test_duplicate_missing_and_empty():
    assert not validate_rows([row(), row()]).valid
    assert not validate_rows([{"symbol": "A"}]).valid
    assert not validate_rows([]).valid


def test_bounds_and_no_partial_results():
    assert not validate_rows([row()] * 10001).valid
    bad = row()
    bad["symbol"] = "B"
    bad["quantity"] = "oops"
    assert not validate_rows([row(), bad]).holdings
