"""Consistent backups and offline restore. Stop every app/SQLite writer before restore."""

import argparse
import os
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4


def _validate(connection):
    if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise ValueError("Invalid backup integrity.")
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version not in (1, 2):
        raise ValueError("Unsupported backup schema.")
    required = {"portfolios", "snapshots", "holdings"}
    if version == 2:
        required |= {"accounts", "ledger_state", "ledger_event_revisions", "ledger_event_heads"}
    tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not required <= tables or connection.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("Invalid backup schema or references.")


def create_backup(source: Path, destination: Path) -> Path:
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve() or destination.exists():
        raise ValueError("Backup destination must be a new file different from source.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as src:
            _validate(src)
            with sqlite3.connect(destination) as dst:
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
