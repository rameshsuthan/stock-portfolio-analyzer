import pytest

from stock_portfolio.ledger.csv_io import ImportKind as I
from stock_portfolio.ledger.csv_io import parse_import


def test_bom_normalized_headers_na_and_visible_unknown_columns():
    result = parse_import(
        b"\xef\xbb\xbf TICKER ,DATE,Transaction_Type,quantity,price,extra\nNA,2025-01-01,BUY,1,2,x\n",
        I.transactions,
        "/private/synthetic.csv",
    )
    assert result.rows[0]["ticker"] == "NA"
    assert result.source_name == "synthetic.csv"
    assert result.warnings and "extra" not in result.rows[0]


@pytest.mark.parametrize(
    "content",
    [
        b"ticker,TICKER,date,transaction_type\nA,A,2025-01-01,BUY\n",
        b"ticker,date,transaction_type\nA,2025-01-01\n",
        b"ticker,date,transaction_type\nA,2025-01-01,BUY,extra\n",
        b"ticker,date,transaction_type,export_kind,format_version\nA,2025-01-01,BUY,holdings_report,1\n",
        b"ticker,date,transaction_type,export_kind,format_version\nA,2025-01-01,BUY,transactions,99\n",
        b"x" * 10_000_001,
        b"ticker,date,transaction_type\n" + b"A,2025-01-01,BUY\n" * 10_001,
    ],
)
def test_reject_invalid_csv_contract(content):
    with pytest.raises(ValueError):
        parse_import(content, I.transactions)
