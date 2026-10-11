"""Consistent backups and offline restore. Stop every app/SQLite writer before restore."""

import argparse
import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from uuid import uuid4


def _validate(connection):
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Invalid backup integrity.")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in (1, 2):
        raise ValueError("Unsupported backup schema.")
    # Build the expected schema in memory, avoiding duplicated schema definitions.
    from .database import LEDGER_SCHEMA, SNAPSHOT_SCHEMA

    with closing(sqlite3.connect(":memory:")) as expected:
        for statement in (*SNAPSHOT_SCHEMA, *(LEDGER_SCHEMA if version == 2 else ())):
            expected.execute(statement)
        tables = [
            r[0] for r in expected.execute("SELECT name FROM sqlite_master WHERE type='table'")
        ]
        for table in tables:
            expected_columns = expected.execute(f'PRAGMA table_info("{table}")').fetchall()
            actual_columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            if expected_columns != actual_columns:
                raise ValueError("Invalid backup schema: required tables/columns differ.")
    if connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Invalid backup schema references.")
    if version == 2:
        rows = connection.execute(
            "SELECT id,revision,economic_revision FROM ledger_state"
        ).fetchall()
        if len(rows) != 1 or rows[0][0] != 1 or not 0 <= rows[0][2] <= rows[0][1]:
            raise ValueError("Invalid backup schema state counters.")


def create_backup(source: Path, destination: Path) -> Path:
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or destination.exists():
        raise ValueError("Backup destination must be a new file different from source.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src:
            _validate(src)
            with closing(sqlite3.connect(destination)) as dst:
                src.backup(dst)
                _validate(dst)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def restore_backup(source: Path, destination: Path) -> Path:
    """Caller must stop all app processes; no claim of exclusivity over external clients."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Restore source and destination must differ.")
    if not destination.is_file():
        raise ValueError("Destination must exist so a recovery backup can be preserved.")
    # Refuse surviving WAL files rather than applying an old journal to the replacement.
    if any(Path(str(destination) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("Stop all SQLite clients and checkpoint the destination before restore.")
    fd, name = tempfile.mkstemp(prefix=".restore-", suffix=".db", dir=destination.parent)
    os.close(fd)
    staged = Path(name)
    staged.unlink()
    recovery = destination.with_name(f"{destination.stem}.pre-restore-{uuid4().hex}.db")
    try:
        create_backup(source, staged)
        create_backup(destination, recovery)
        os.replace(staged, destination)
    finally:
        staged.unlink(missing_ok=True)
    return recovery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["restore"])
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--confirm-stopped", action="store_true", required=True)
    args = parser.parse_args()
    recovery = restore_backup(args.source, args.destination)
    print(f"Restored. Pre-restore recovery backup: {recovery}")


if __name__ == "__main__":
    main()
