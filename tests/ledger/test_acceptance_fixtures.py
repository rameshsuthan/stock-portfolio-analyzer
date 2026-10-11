import json
import time
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from stock_portfolio.ledger.csv_io import ImportKind as I
from stock_portfolio.ledger.csv_io import parse_import
from stock_portfolio.ledger.engine import replay
from stock_portfolio.ledger.imports import commit_import, prepare_import
from stock_portfolio.ledger.repository import LedgerRepository
from stock_portfolio.ledger.valuation import value_account

ROOT = Path("samples/ledger")
EXPECTED = json.loads((ROOT / "expected_results.json").read_text())


def test_independently_calculated_linked_account_fixture(tmp_path):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a, b = repo.create_account("Synthetic A"), repo.create_account("Synthetic B")
        p = prepare_import(
            repo, parse_import((ROOT / "linked_accounts.csv").read_bytes(), I.transactions), None
        )
        assert not p.issues
        commit_import(repo, p)
        commit_import(
            repo,
            prepare_import(repo, parse_import((ROOT / "prices.csv").read_bytes(), I.prices), None),
        )
        ds = repo.load_dataset()
        result = replay(ds, date(2025, 1, 7))
        for account in (a, b):
            value = value_account(ds, result, repo.load_prices(), account.id, date(2025, 1, 7))
            expected = EXPECTED["linked"][account.name]
            assert value.holdings[0].position.quantity == D(expected["quantity"])
            assert value.total_basis == D(expected["basis"])
            assert value.realized_gain == D(expected["realized"])
            assert value.dividends == D(expected["dividends"])
            assert value.total_value == D(expected["market_value"])


@pytest.mark.parametrize(
    "filename,key", [("holdings_100.csv", "hundred"), ("events_10000.csv", "ten_thousand")]
)
def test_large_imports_have_independent_totals_and_record_timings(tmp_path, filename, key):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("Synthetic")
        started = time.perf_counter()
        p = prepare_import(repo, parse_import((ROOT / filename).read_bytes(), I.transactions), a.id)
        preview_seconds = time.perf_counter() - started
        assert not p.issues
        started = time.perf_counter()
        commit_import(repo, p)
        commit_seconds = time.perf_counter() - started
        started = time.perf_counter()
        result = replay(repo.load_dataset(), date(2025, 1, 1))
        replay_seconds = time.perf_counter() - started
        expected = EXPECTED[key]
        assert len(result.positions) == expected["holdings"]
        assert sum(p.quantity for p in result.positions) == D(expected["quantity"])
        assert sum(p.basis for p in result.positions) == D(expected["basis"])
        print(
            json.dumps(
                {
                    "fixture": filename,
                    "preview_seconds": preview_seconds,
                    "commit_seconds": commit_seconds,
                    "replay_seconds": replay_seconds,
                }
            )
        )


@pytest.mark.parametrize("filename,code", EXPECTED["invalid"].items())
def test_invalid_fixture_issue_codes(tmp_path, filename, code):
    with LedgerRepository(tmp_path / "demo.db") as repo:
        a = repo.create_account("Synthetic")
        if code == "parse_error":
            with pytest.raises(ValueError):
                parse_import((ROOT / "invalid" / filename).read_bytes(), I.transactions)
        else:
            p = prepare_import(
                repo, parse_import((ROOT / "invalid" / filename).read_bytes(), I.transactions), a.id
            )
            assert code in {issue.code for issue in p.issues}
            assert repo.load_dataset().events == ()
