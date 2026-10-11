from dataclasses import replace
from datetime import date
from decimal import Decimal as D

from conftest import END, event
from test_repository import apply

from stock_portfolio.ledger.csv_io import ImportKind as I
from stock_portfolio.ledger.csv_io import export_events, export_openings, parse_import
from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.imports import commit_import, prepare_import
from stock_portfolio.ledger.models import LotAllocation
from stock_portfolio.ledger.repository import LedgerRepository


def test_all_account_export_roundtrip_preserves_openings_allocations_and_transfer_ids(tmp_path):
    with (
        LedgerRepository(tmp_path / "source.db") as source,
        LedgerRepository(tmp_path / "target.db") as target,
    ):
        a, b = source.create_account("A", date(2025, 1, 1)), source.create_account("B")
        aa, bb = target.create_account("A", date(2025, 1, 1)), target.create_account("B")
        opening = event(
            "opening",
            "OPENING_LOT",
            account=a.id,
            quantity="10",
            basis="1000",
            acquired_date=date(2020, 1, 1),
            external_id="original-lot",
        )
        transfer = event(
            "transfer",
            "TRANSFER",
            day=2,
            account=a.id,
            quantity="4",
            destination_account_id=b.id,
            allocations=(LotAllocation(opening.id, D(4)),),
            external_id="t",
        )
        apply(source, opening, transfer)
        destlot = next(l for l in replay(source.load_dataset(), END).lots if l.account_id == b.id)
        sale = event(
            "sale",
            "SELL",
            day=3,
            account=b.id,
            quantity="2",
            price="150",
            external_id="s",
            allocations=(LotAllocation(destlot.id, D(2)),),
        )
        apply(source, sale)
        p = prepare_import(
            target,
            parse_import(
                export_openings(source.load_dataset(), a.id, I.opening_lots), I.opening_lots
            ),
            aa.id,
            date(2025, 1, 1),
        )
        assert not p.issues
        commit_import(target, p)
        p = prepare_import(
            target, parse_import(export_events(source.load_dataset()), I.transactions), None
        )
        assert not p.issues
        commit_import(target, p)
        mapping = {a.id: aa.id, b.id: bb.id}
        expected = {
            e.id: replace(
                e,
                account_id=mapping[e.account_id],
                destination_account_id=mapping.get(e.destination_account_id),
            )
            for e in source.load_dataset().events
        }
        assert {e.id: e for e in target.load_dataset().events} == expected
        assert replay(target.load_dataset(), END).disposals[0].gain == 100
