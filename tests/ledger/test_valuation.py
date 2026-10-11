from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from conftest import END, A, dataset, event

from stock_portfolio.ledger.csv_io import ImportKind as I
from stock_portfolio.ledger.csv_io import (
    export_holdings_report,
    export_realized_report,
    parse_import,
)
from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.imports import commit_import, prepare_import
from stock_portfolio.ledger.models import PriceObservation as P
from stock_portfolio.ledger.repository import LedgerRepository, StaleRevision
from stock_portfolio.ledger.valuation import value_account


def value(ds, prices=(), as_of=END):
    return value_account(ds, replay(ds, as_of), prices, "a", as_of)


def test_latest_price_date_missing_zero_and_stale():
    ds = dataset(event("buy", quantity="10", price="100"))
    prices = (P("ABC", date(2025, 1, 2), D(120)), P("ABC", date(2025, 1, 4), D(150)))
    result = value(ds, prices, date(2025, 1, 3))
    assert (result.total_value, result.unrealized_gain, result.holdings[0].price_date) == (
        D(1200),
        D(200),
        date(2025, 1, 2),
    )
    assert value(ds, prices, date(2025, 1, 1)).total_value is None
    assert value(ds, (P("ABC", END, D(0)),)).total_value == 0
    assert any(i.code == "stale_price" for i in value(ds, prices).issues)


def test_pre_split_price_is_unusable_until_split_date_observation():
    ds = dataset(
        event("buy", quantity="10", price="100"),
        event("split", "SPLIT", day=3, split_numerator=2, split_denominator=1),
    )
    assert value(ds, (P("ABC", date(2025, 1, 2), D(120)),), date(2025, 1, 3)).total_value is None
    assert value(ds, (P("ABC", date(2025, 1, 3), D(60)),), date(2025, 1, 3)).total_value == 1200


def test_opening_cutoff_unknown_basis_subtotals_and_report_markers():
    a = replace(A, opening_date=date(2025, 1, 2))
    ds = dataset(
        event("opening", "OPENING_BALANCE", day=2, quantity="10", basis="1000"),
        event("sale", "SELL", day=3, quantity="4", price="150"),
        event("other", day=4, symbol="XYZ", quantity="1", price="5"),
        accounts=(a,),
    )
    with pytest.raises(ValueError):
        value(ds, as_of=date(2025, 1, 1))
    v = value(ds, (P("ABC", END, D(120)),))
    assert (
        v.known_value,
        v.known_basis,
        v.total_value,
        v.total_basis,
        v.unrealized_gain,
        v.realized_gain,
    ) == (D(720), D(5), None, None, None, None)
    report = export_holdings_report(v)
    assert b"holdings_report" in report and b"unknown_basis" in report
    with pytest.raises(ValueError):
        parse_import(report, I.opening_balances)
    assert b"realized_report" in export_realized_report(replay(ds, END), "a", END)


def test_price_corrections_keep_history_stale_previews_not_economic_revision(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        p = prepare_import(
            repo,
            parse_import(
                b"ticker,date,transaction_type,quantity,price\nABC,2025-01-01,BUY,10,100\n",
                I.transactions,
            ),
            a.id,
        )
        revision = repo.load_dataset().revision
        repo.save_prices((P("ABC", date(2025, 1, 1), D(120)),), revision, "Synthetic first price")
        with pytest.raises(StaleRevision):
            commit_import(repo, p)
        repo.save_prices(
            (P("ABC", date(2025, 1, 1), D(125)),),
            repo.load_dataset().revision,
            "Synthetic correction",
        )
        assert repo.load_prices()[0].price == 125
        assert repo.load_dataset().economic_revision == 0
        assert len(repo.price_history("ABC", date(2025, 1, 1))) == 2
        p = prepare_import(
            repo, parse_import(b"ticker,price_date,price\nABC,2025-01-02,130\n", I.prices), None
        )
        commit_import(repo, p)
        assert len(repo.load_prices()) == 2


def test_filtered_holdings_report_preserves_unknowns_and_exact_derived_values():
    import csv
    import io

    ds = dataset(
        event("one", quantity="1", price="100"),
        event("two", day=2, symbol="XYZ", quantity="1", price="20"),
    )
    v = value(ds)
    rows = list(csv.DictReader(io.StringIO(export_holdings_report(v, symbols={"ABC"}).decode())))
    assert len(rows) == 1 and rows[0]["ticker"] == "ABC"
    assert rows[0]["market_value"] == "" and rows[0]["cost_basis"] == "100"


def test_split_price_guard_survives_full_transfer_to_empty_account():
    ds = dataset(
        event("source-buy", quantity="10", price="100"),
        event("source-split", "SPLIT", day=2, split_numerator=2, split_denominator=1),
        event("source-transfer", "TRANSFER", day=3, quantity="20", destination_account_id="b"),
    )
    day = date(2025, 1, 3)
    result = replay(ds, day)
    stale = value_account(ds, result, (P("ABC", date(2025, 1, 1), D(100)),), "b", day)
    assert stale.total_value is None
    assert "pre_split_price" in {i.code for i in stale.issues}
    current = value_account(ds, result, (P("ABC", date(2025, 1, 2), D(50)),), "b", day)
    assert current.total_value == 1000
    assert current.total_basis == 1000


def test_split_price_guard_covers_partial_transfer_chains():
    from conftest import B

    from stock_portfolio.ledger.models import Account

    ds = dataset(
        event("chain-buy", quantity="10", price="100"),
        event("chain-split", "SPLIT", day=2, split_numerator=2, split_denominator=1),
        event("chain-ab", "TRANSFER", day=3, quantity="12", destination_account_id="b"),
        event("chain-bc", "TRANSFER", day=4, account="b", quantity="4", destination_account_id="c"),
        accounts=(A, B, Account("c", "Gamma")),
    )
    day = date(2025, 1, 4)
    result = replay(ds, day)
    for account, expected_value in [("a", 400), ("b", 400), ("c", 200)]:
        stale = value_account(ds, result, (P("ABC", date(2025, 1, 1), D(100)),), account, day)
        assert stale.total_value is None and any(i.code == "pre_split_price" for i in stale.issues)
        current = value_account(ds, result, (P("ABC", date(2025, 1, 2), D(50)),), account, day)
        assert current.total_value == expected_value
