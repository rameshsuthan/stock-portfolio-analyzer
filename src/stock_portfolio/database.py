"""Shared SQLite schema boundary; migrations never run without a verified backup."""

import sqlite3
from pathlib import Path
from uuid import uuid4

from .backup import create_backup


class UnsupportedSchema(ValueError):
    pass


SNAPSHOT_SCHEMA = (
    "CREATE TABLE portfolios (id INTEGER PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL UNIQUE)",
    """CREATE TABLE snapshots (id INTEGER PRIMARY KEY, portfolio_id INTEGER NOT NULL
       REFERENCES portfolios(id) ON DELETE CASCADE, snapshot_date TEXT NOT NULL,
       UNIQUE(portfolio_id, snapshot_date))""",
    """CREATE TABLE holdings (snapshot_id INTEGER NOT NULL REFERENCES snapshots(id)
       ON DELETE CASCADE, symbol TEXT NOT NULL, quantity TEXT NOT NULL, cost_basis TEXT NOT NULL,
       current_price TEXT NOT NULL, company_name TEXT NOT NULL, sector TEXT NOT NULL,
       PRIMARY KEY(snapshot_id, symbol))""",
)

LEDGER_SCHEMA = (
    """CREATE TABLE accounts (id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT NOT NULL
       UNIQUE, opening_date TEXT, archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
       currency TEXT NOT NULL CHECK(currency='USD'), broker_label TEXT NOT NULL)""",
    """CREATE TABLE ledger_state (id INTEGER PRIMARY KEY CHECK(id=1), revision INTEGER NOT NULL,
       economic_revision INTEGER NOT NULL)""",
    "INSERT INTO ledger_state VALUES (1,0,0)",
    """CREATE TABLE audit_operations (id TEXT PRIMARY KEY, reason TEXT NOT NULL,
       provenance TEXT NOT NULL, recorded_at TEXT NOT NULL)""",
    """CREATE TABLE ledger_event_identities (id TEXT PRIMARY KEY, account_id TEXT NOT NULL
       REFERENCES accounts(id), external_id TEXT, UNIQUE(account_id,external_id))""",
    """CREATE TABLE ledger_event_revisions (event_id TEXT NOT NULL REFERENCES ledger_event_identities(id),
       version INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','void')),
       payload TEXT NOT NULL, effective_date TEXT NOT NULL, operation_id TEXT NOT NULL
       REFERENCES audit_operations(id), PRIMARY KEY(event_id,version))""",
    """CREATE TABLE ledger_event_heads (event_id TEXT PRIMARY KEY REFERENCES ledger_event_identities(id),
       version INTEGER NOT NULL, FOREIGN KEY(event_id,version)
       REFERENCES ledger_event_revisions(event_id,version))""",
    """CREATE TABLE price_observations (symbol TEXT NOT NULL, price_date TEXT NOT NULL,
       price TEXT NOT NULL, source_label TEXT NOT NULL, PRIMARY KEY(symbol,price_date))""",
    """CREATE TABLE price_revisions (symbol TEXT NOT NULL, price_date TEXT NOT NULL,
       version INTEGER NOT NULL, payload TEXT NOT NULL, operation_id TEXT NOT NULL
       REFERENCES audit_operations(id), PRIMARY KEY(symbol,price_date,version))""",
    """CREATE TABLE import_batches (id TEXT PRIMARY KEY, account_ids TEXT NOT NULL, kind TEXT NOT NULL,
       source_hash TEXT NOT NULL, source_name TEXT NOT NULL, effective_date TEXT,
       operation_id TEXT NOT NULL REFERENCES audit_operations(id))""",
    """CREATE TABLE import_rows (batch_id TEXT NOT NULL REFERENCES import_batches(id),
       row_number INTEGER NOT NULL, payload TEXT NOT NULL, disposition TEXT NOT NULL,
       PRIMARY KEY(batch_id,row_number))""",
    """CREATE TABLE broker_statements (id TEXT PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(id),
       as_of TEXT NOT NULL, source_hash TEXT NOT NULL)""",
    """CREATE TABLE broker_statement_rows (statement_id TEXT NOT NULL REFERENCES broker_statements(id),
       symbol TEXT NOT NULL, quantity TEXT NOT NULL, basis TEXT, PRIMARY KEY(statement_id,symbol))""",
    """CREATE TABLE reconciliation_runs (id TEXT PRIMARY KEY, statement_id TEXT NOT NULL
       REFERENCES broker_statements(id), account_id TEXT NOT NULL REFERENCES accounts(id),
       payload TEXT NOT NULL, recorded_at TEXT NOT NULL)""",
    """CREATE TABLE reconciliation_rows (run_id TEXT NOT NULL REFERENCES reconciliation_runs(id),
       symbol TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(run_id,symbol))""",
    "CREATE INDEX events_by_account ON ledger_event_identities(account_id,external_id)",
    "CREATE INDEX events_by_date ON ledger_event_revisions(effective_date)",
    "CREATE INDEX batches_by_hash ON import_batches(source_hash,kind,account_ids)",
)


def _create_ledger_schema(connection):
    for statement in LEDGER_SCHEMA:
        connection.execute(statement)


def open_database(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    try:
        version = c.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2) or (
            version == 0
            and c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
        ):
            raise UnsupportedSchema("Unsupported database schema; database left unchanged.")
        if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise UnsupportedSchema("Database integrity check failed.")
        c.execute("PRAGMA foreign_keys=ON")
        if version == 1:
            create_backup(path, path.with_name(f"{path.stem}.pre-migration-{uuid4().hex}.db"))
        if version < 2:
            with c:
                c.execute("BEGIN IMMEDIATE")
                if version == 0:
                    for statement in SNAPSHOT_SCHEMA:
                        c.execute(statement)
                _create_ledger_schema(c)
                c.execute("PRAGMA user_version=2")
        return c
    except BaseException:
        c.close()
        raise
