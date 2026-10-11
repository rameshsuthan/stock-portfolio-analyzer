import sqlite3
from datetime import date
from decimal import Decimal as D

import pytest

from stock_portfolio.csv_io import export_snapshot, parse_csv
from stock_portfolio.models import Holding
from stock_portfolio.storage import ReplacementRequired, Repository, UnsupportedSchema
from stock_portfolio.validation import validate_rows

DAY = date(2026, 10, 10)
ROWS = (Holding("A", D(".12345678"), D("1.23000000"), D(2), "A", "Unknown"),)


def test_portfolios_casefold_unique_and_delete(tmp_path):
    with Repository(tmp_path / "test.db") as repo:
        p = repo.create_portfolio(" Demo ")
        assert repo.list_portfolios() == [(p, "Demo")]
        with pytest.raises(ValueError):
            repo.create_portfolio("demo")
        with pytest.raises(ValueError):
            repo.create_portfolio(" ")
        repo.save_snapshot(p, DAY, ROWS)
        repo.delete_portfolio(p)
        assert repo.list_portfolios() == []
        assert repo.connection.execute("SELECT count(*) FROM holdings").fetchone()[0] == 0


def test_snapshot_roundtrip_restart_and_latest(tmp_path):
    path = tmp_path / "test.db"
    with Repository(path) as repo:
        p = repo.create_portfolio("Demo")
        old = repo.save_snapshot(p, date(2025, 1, 1), ROWS)
        saved = repo.save_snapshot(p, DAY, ROWS)
    with Repository(path) as repo:
        assert repo.load_snapshot(saved.id) == saved
        assert repo.list_snapshots(p)[0] == (saved.id, DAY)
        imported = parse_csv(export_snapshot(repo.load_snapshot(saved.id)))
        assert validate_rows(imported.rows).holdings == ROWS
        repo.delete_snapshot(old.id)
        assert repo.list_snapshots(p) == [(saved.id, DAY)]


def test_confirmation_and_complete_replacement(tmp_path):
    with Repository(tmp_path / "test.db") as repo:
        p = repo.create_portfolio("Demo")
        s = repo.save_snapshot(p, DAY, ROWS)
        replacement = (Holding("B", D(1), D(2), D(3), "B", "Other"),)
        with pytest.raises(ReplacementRequired):
            repo.save_snapshot(p, DAY, replacement)
        assert repo.load_snapshot(s.id).holdings == ROWS
        repo.save_snapshot(p, DAY, replacement, replace=True)
        assert repo.load_snapshot(s.id).holdings == replacement


def test_mid_insert_failure_rolls_back_deleted_rows(tmp_path):
    with Repository(tmp_path / "test.db") as repo:
        p = repo.create_portfolio("Demo")
        s = repo.save_snapshot(p, DAY, ROWS)
        repo.connection.execute(
            "CREATE TRIGGER fail_insert BEFORE INSERT ON holdings WHEN NEW.symbol = 'FAIL' BEGIN SELECT RAISE(ABORT, 'injected disk failure'); END"
        )
        replacement = ROWS + (Holding("FAIL", D(1), D(1), D(1), "FAIL", "Unknown"),)
        with pytest.raises(sqlite3.IntegrityError):
            repo.save_snapshot(p, DAY, replacement, replace=True)
        assert repo.load_snapshot(s.id).holdings == ROWS


def test_unknown_schema_is_untouched(tmp_path):
    path = tmp_path / "future.db"
    with sqlite3.connect(path) as con:
        con.execute("PRAGMA user_version = 99")
        con.execute("CREATE TABLE future (value TEXT)")
        con.execute("INSERT INTO future VALUES ('precious')")
    before = path.read_bytes()
    with pytest.raises(UnsupportedSchema):
        Repository(path)
    assert path.read_bytes() == before


def test_invalid_holdings_cannot_persist(tmp_path):
    with Repository(tmp_path / "test.db") as repo:
        p = repo.create_portfolio("Demo")
        with pytest.raises(ValueError):
            repo.save_snapshot(p, DAY, ())
        assert repo.list_snapshots(p) == []
