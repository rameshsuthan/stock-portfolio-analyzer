import sqlite3

import pytest

from stock_portfolio import database


def make_v1(path):
    with sqlite3.connect(path) as c:
        c.executescript("""
        CREATE TABLE portfolios (id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            name_key TEXT NOT NULL UNIQUE);
        CREATE TABLE snapshots (id INTEGER PRIMARY KEY,
            portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
            snapshot_date TEXT NOT NULL, UNIQUE(portfolio_id, snapshot_date));
        CREATE TABLE holdings (snapshot_id INTEGER NOT NULL REFERENCES snapshots(id)
            ON DELETE CASCADE, symbol TEXT NOT NULL, quantity TEXT NOT NULL,
            cost_basis TEXT NOT NULL, current_price TEXT NOT NULL,
            company_name TEXT NOT NULL, sector TEXT NOT NULL, PRIMARY KEY(snapshot_id,symbol));
        INSERT INTO portfolios VALUES (1,'Synthetic Ω','synthetic ω');
        INSERT INTO snapshots VALUES (1,1,'2025-01-01'),(2,1,'2025-02-01');
        INSERT INTO holdings VALUES (1,'NA','.12345678','1.23000000','2','NA','Unknown'),
            (2,'NA','1','0','3','NA','Unknown');
        PRAGMA user_version=1;
        """)


def records(path):
    with sqlite3.connect(path) as c:
        return tuple(
            c.execute(f"SELECT * FROM {t}").fetchall()
            for t in ("portfolios", "snapshots", "holdings")
        )


def test_migrates_v1_with_verified_backup(tmp_path):
    path = tmp_path / "demo.db"
    make_v1(path)
    before = records(path)
    c = database.open_database(path)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 2
    assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    c.close()
    assert records(path) == before
    backups = list(tmp_path.glob("*.pre-migration-*.db"))
    assert len(backups) == 1
    assert records(backups[0]) == before


@pytest.mark.parametrize("failure", ["backup", "migration", "version"])
def test_failed_migration_preserves_original(tmp_path, monkeypatch, failure):
    path = tmp_path / "demo.db"
    make_v1(path)
    if failure == "version":
        with sqlite3.connect(path) as c:
            c.execute("PRAGMA user_version=99")
    before = path.read_bytes()

    def fail(*args):
        if failure == "migration":
            args[0].execute("CREATE TABLE transient (x)")
        raise RuntimeError("injected")

    if failure == "backup":
        monkeypatch.setattr(database, "create_backup", fail)
    if failure == "migration":
        monkeypatch.setattr(database, "_create_ledger_schema", fail)
    with pytest.raises((ValueError, RuntimeError)):
        database.open_database(path)
    assert path.read_bytes() == before
