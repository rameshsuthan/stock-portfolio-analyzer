import os
import sqlite3

import pytest
from test_migrations import make_v1, records

from stock_portfolio.backup import create_backup, restore_backup


def test_backup_includes_live_wal_and_restore_preserves_destination(tmp_path):
    source, dest, backup = (tmp_path / n for n in ("source.db", "dest.db", "backup.db"))
    make_v1(source)
    make_v1(dest)
    c = sqlite3.connect(source)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("UPDATE portfolios SET name='Synthetic changed'")
    c.commit()
    create_backup(source, backup)
    assert records(backup) == records(source)
    old = records(dest)
    recovery = restore_backup(backup, dest)
    assert records(dest) == records(source)
    assert records(recovery) == old
    c.close()


@pytest.mark.parametrize("failure", ["corrupt", "newer", "replace"])
def test_restore_failure_preserves_destination(tmp_path, monkeypatch, failure):
    source, dest = tmp_path / "source.db", tmp_path / "dest.db"
    make_v1(source)
    make_v1(dest)
    before = dest.read_bytes()
    if failure == "corrupt":
        source.write_bytes(b"not sqlite")
    elif failure == "newer":
        with sqlite3.connect(source) as c:
            c.execute("PRAGMA user_version=99")
    else:

        def fail(*args):
            raise OSError("injected replace failure")

        monkeypatch.setattr(os, "replace", fail)
    with pytest.raises((ValueError, sqlite3.DatabaseError, OSError)):
        restore_backup(source, dest)
    assert dest.read_bytes() == before
