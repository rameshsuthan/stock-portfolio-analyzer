import csv
import io
from datetime import date
from decimal import Decimal as D

import pytest

from stock_portfolio.calculations import analyze
from stock_portfolio.csv_io import CsvFormatError, export_analysis, export_snapshot, parse_csv
from stock_portfolio.models import Holding, Metadata, Selection, Snapshot
from stock_portfolio.validation import validate_rows

HEADER = b"symbol,quantity,cost_basis,current_price\n"


def test_bom_headers_na_and_extra():
    p = parse_csv(
        b"\xef\xbb\xbf Symbol ,Quantity,cost_basis,current_price,unused\nNA,.1,.02,.3,x\n"
    )
    assert validate_rows(p.rows).holdings[0].symbol == "NA"
    assert p.warnings and p.metadata is None


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"\xff",
        b"symbol, SYMBOL,quantity,cost_basis,current_price\nA,A,1,1,1\n",
        b"symbol,quantity\nA,1\n",
        HEADER + b"A,1,2,3,4\n",
        HEADER + b"A,1,2\n",
        HEADER + b'"A,1,2,3\n',
        HEADER + b"\n",
        b"x" * 10000001,
    ],
    ids=[str(i) for i in range(9)],
)
def test_structural_errors(content):
    with pytest.raises(CsvFormatError):
        parse_csv(content)


def test_editable_bad_numbers_are_preserved():
    p = parse_csv(HEADER + b"A,oops,1,2\n")
    assert p.rows[0]["quantity"] == "oops"
    assert not validate_rows(p.rows).valid


def snapshot():
    return Snapshot(
        Metadata("Demo", date(2026, 10, 10)),
        (
            Holding(
                "NA", D("0.12345678"), D("1234567890.12345678"), D("1.23000000"), "NA", "Unknown"
            ),
            Holding("B", D(1), D(0), D(0), "B", "Other"),
        ),
    )


def test_round_trip_precision_and_metadata():
    s = snapshot()
    p = parse_csv(export_snapshot(s))
    assert p.metadata == s.metadata
    assert validate_rows(p.rows).holdings == s.holdings
    assert b"1.23000000" in export_snapshot(s)


def test_reject_analysis_and_inconsistent_metadata():
    s = snapshot()
    with pytest.raises(CsvFormatError):
        parse_csv(export_analysis(analyze(s.holdings), s.metadata))
    data = export_snapshot(s).replace(b"Demo,2026", b"Other,2026", 1)
    with pytest.raises(CsvFormatError):
        parse_csv(data)
    with pytest.raises(CsvFormatError):
        parse_csv(HEADER.rstrip() + b",portfolio_name\nA,1,1,1,Demo\n")


def test_analysis_selection_and_blank_undefined():
    s = snapshot()
    data = export_analysis(analyze(s.holdings, Selection(frozenset({"B"}))), s.metadata)
    rows = list(csv.DictReader(io.StringIO(data.decode())))
    assert len(rows) == 1 and rows[0]["symbol"] == "B"
    assert rows[0]["gain_percent"] == "" and rows[0]["export_kind"] == "analysis"
