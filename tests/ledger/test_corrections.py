from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest
from conftest import END, event
from test_repository import apply

from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.models import InvalidLedger
from stock_portfolio.ledger.repository import LedgerRepository


def test_historical_correction_revalidates_both_accounts_atomically(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a, b = repo.create_account("A"), repo.create_account("B")
        buy = event("buy", account=a.id, quantity="10", price="100")
        transfer = event(
            "transfer", "TRANSFER", day=2, account=a.id, quantity="8", destination_account_id=b.id
        )
        sale = event("sale", "SELL", day=3, account=b.id, quantity="6", price="150")
        apply(repo, buy, transfer, sale)
        before = repo.load_dataset()
        with pytest.raises(InvalidLedger):
            apply(repo, replace(buy, quantity=D(5)))
        with pytest.raises(InvalidLedger):
            apply(repo, void=(transfer.id,))
        assert repo.load_dataset() == before
        assert len(repo.history(buy.id)) == 1
        apply(repo, replace(buy, price=D(110)))
        assert repo.load_dataset().economic_revision == before.economic_revision + 1
        assert replay(repo.load_dataset(), END).disposals[0].gain == 240
        assert len(repo.history(buy.id)) == 2


def test_linked_reinvestment_revisions_and_voids_require_whole_group(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A")
        dividend = event("div", "DIVIDEND", account=a.id, amount="50")
        buy = event(
            "buy", seq=2, account=a.id, quantity=".4", price="120", reinvestment_of=dividend.id
        )
        apply(repo, dividend, buy)
        with pytest.raises(InvalidLedger):
            apply(repo, replace(buy, price=D(110)))
        with pytest.raises(InvalidLedger):
            apply(repo, void=(buy.id,))
        apply(repo, dividend, replace(buy, price=D(110)))
        apply(repo, void=(buy.id, dividend.id))
        assert repo.load_dataset().events == ()


def test_opening_pool_replacement_requires_equal_totals_and_replays(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("A", date(2025, 1, 1))
        pool = event("pool", "OPENING_BALANCE", account=a.id, quantity="10", basis="1000")
        sale = event("sale", "SELL", day=2, account=a.id, quantity="4", price="150")
        apply(repo, pool, sale)
        lot = event(
            "lot",
            "OPENING_LOT",
            account=a.id,
            quantity="10",
            basis="1000",
            acquired_date=date(2020, 1, 1),
        )
        with pytest.raises(InvalidLedger):
            apply(repo, replace(lot, basis=D(999)), void=(pool.id,))
        apply(repo, lot, void=(pool.id,))
        assert replay(repo.load_dataset(), END).disposals[0].gain == 200
