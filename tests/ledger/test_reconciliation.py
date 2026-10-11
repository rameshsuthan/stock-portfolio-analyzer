from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from conftest import END, dataset, event
from test_repository import apply

from stock_portfolio.ledger.models import BrokerHolding as H
from stock_portfolio.ledger.models import BrokerStatement as S
from stock_portfolio.ledger.models import PriceObservation
from stock_portfolio.ledger.reconciliation import reconcile
from stock_portfolio.ledger.repository import LedgerRepository


def test_reconcile_uses_statement_date_and_union_of_symbols():
    ds = dataset(
        event("buy", quantity="10", price="100"),
        event("sale", "SELL", day=3, quantity="4", price="150"),
    )
    result = reconcile(
        ds,
        S("s", "a", date(2025, 1, 2), (H("ABC", D(10), D(1000)), H("OTHER", D(1), None)), "hash"),
    )
    rows = {r.symbol: r for r in result.rows}
    assert rows["ABC"].status == "matched" and rows["ABC"].local_quantity == 10
    assert rows["OTHER"].status == "missing_local"
    assert result.policy == "fifo-v1"
    result = reconcile(ds, S("s", "a", END, (), "hash"))
    assert result.rows[0].status == "missing_broker"


@pytest.mark.parametrize(
    "quantity,basis,status",
    [
        ("10.00000001", "1000.01", "matched"),
        ("10.00000002", "1000", "mismatch"),
        ("10", "1000.01000001", "mismatch"),
        ("10", None, "unresolved"),
        ("11", None, "mismatch"),
        ("0", "0", "mismatch"),
    ],
)
def test_tolerances_and_unknown_status_precedence(quantity, basis, status):
    ds = dataset(event("b", quantity="10", price="100"))
    row = reconcile(
        ds, S("s", "a", END, (H("ABC", D(quantity), D(basis) if basis else None),), "hash")
    ).rows[0]
    assert row.status == status
    assert row.quantity_difference == D(10) - D(quantity)


@pytest.mark.parametrize(
    "holdings", [(H("ABC", D(-1), D(0)),), (H("ABC", D(1), None), H("ABC", D(2), None))]
)
def test_invalid_statements(holdings):
    with pytest.raises(ValueError):
        reconcile(dataset(), S("s", "a", END, holdings, "hash"))


def test_saved_evidence_is_immutable_and_economic_revision_drives_staleness(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        buy = event("b", account=a.id, quantity="10", price="100")
        apply(repo, buy)
        statement = S("statement", a.id, END, (H("ABC", D(10), D(1000)),), "synthetic-hash")
        repo.save_statement(statement)
        result = reconcile(repo.load_dataset(), statement)
        repo.save_reconciliation(result)
        repo.save_prices(
            (PriceObservation("ABC", END, D(120)),), repo.load_dataset().revision, "Synthetic price"
        )
        assert result.ledger_revision == repo.load_dataset().economic_revision
        apply(repo, replace(buy, price=D(110)))
        assert result.ledger_revision != repo.load_dataset().economic_revision
        assert repo.load_reconciliations(a.id) == (result,)
        updated = reconcile(repo.load_dataset(), statement)
        repo.save_reconciliation(updated)
        assert repo.load_reconciliations(a.id) == (result, updated)
        assert updated.rows[0].status == "mismatch"
        with pytest.raises(ValueError):
            repo.save_statement(replace(statement, holdings=()))
