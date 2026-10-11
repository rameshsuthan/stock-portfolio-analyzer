"""Local SQLite storage. Replacement is one rollback-safe transaction."""

import sqlite3
from datetime import date
from pathlib import Path

from .models import Metadata, Snapshot
from .validation import FIELDS, holding_rows, validate_rows


class ReplacementRequired(ValueError):
    pass


class UnsupportedSchema(ValueError):
    pass


class Repository:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path)
        c = self.connection
        version = c.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1) or (
            version == 0
            and c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone()
        ):
            c.close()
            raise UnsupportedSchema("Unsupported database schema; database left unchanged.")
        c.execute("PRAGMA foreign_keys=ON")
        if version == 0:
            with c:
                c.executescript("""
                    BEGIN;
                    CREATE TABLE portfolios (id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                        name_key TEXT NOT NULL UNIQUE);
                    CREATE TABLE snapshots (id INTEGER PRIMARY KEY,
                        portfolio_id INTEGER NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
                        snapshot_date TEXT NOT NULL, UNIQUE(portfolio_id, snapshot_date));
                    CREATE TABLE holdings (snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
                        symbol TEXT NOT NULL, quantity TEXT NOT NULL, cost_basis TEXT NOT NULL,
                        current_price TEXT NOT NULL, company_name TEXT NOT NULL, sector TEXT NOT NULL,
                        PRIMARY KEY(snapshot_id, symbol));
                    PRAGMA user_version=1;
                    COMMIT;
                """)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def create_portfolio(self, name):
        name = name.strip()
        if not name:
            raise ValueError("Portfolio name is required.")
        try:
            with self.connection:
                return self.connection.execute(
                    "INSERT INTO portfolios(name,name_key) VALUES (?,?)", (name, name.casefold())
                ).lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError("A portfolio with that name already exists.") from exc

    def list_portfolios(self):
        return self.connection.execute(
            "SELECT id,name FROM portfolios ORDER BY name_key"
        ).fetchall()

    def list_snapshots(self, portfolio_id):
        return [
            (i, date.fromisoformat(d))
            for i, d in self.connection.execute(
                "SELECT id,snapshot_date FROM snapshots WHERE portfolio_id=? ORDER BY snapshot_date DESC",
                (portfolio_id,),
            )
        ]

    def load_snapshot(self, snapshot_id):
        row = self.connection.execute(
            """SELECT p.id,p.name,s.snapshot_date FROM snapshots s
            JOIN portfolios p ON p.id=s.portfolio_id WHERE s.id=?""",
            (snapshot_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Snapshot no longer exists.")
        values = self.connection.execute(
            """SELECT symbol,quantity,cost_basis,current_price,company_name,sector
            FROM holdings WHERE snapshot_id=? ORDER BY rowid""",
            (snapshot_id,),
        ).fetchall()
        result = validate_rows([dict(zip(FIELDS, v)) for v in values])
        if not result.valid:
            raise ValueError("Saved holdings are invalid; restore a known-good backup.")
        return Snapshot(
            Metadata(row[1], date.fromisoformat(row[2])), result.holdings, snapshot_id, row[0]
        )

    def save_snapshot(self, portfolio_id, snapshot_date, holdings, replace=False):
        if type(snapshot_date) is not date:
            raise ValueError("Prices-as-of date is required.")
        result = validate_rows(holding_rows(holdings))
        if not result.valid:
            raise ValueError("Cannot save invalid or empty holdings.")
        c = self.connection
        with c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute(
                "SELECT id FROM snapshots WHERE portfolio_id=? AND snapshot_date=?",
                (portfolio_id, snapshot_date.isoformat()),
            ).fetchone()
            if old:
                if not replace:
                    raise ReplacementRequired(
                        "This portfolio/date exists. Confirm complete replacement."
                    )
                snapshot_id = old[0]
                c.execute("DELETE FROM holdings WHERE snapshot_id=?", (snapshot_id,))
            else:
                snapshot_id = c.execute(
                    "INSERT INTO snapshots(portfolio_id,snapshot_date) VALUES (?,?)",
                    (portfolio_id, snapshot_date.isoformat()),
                ).lastrowid
            for row in holding_rows(result.holdings):
                c.execute(
                    "INSERT INTO holdings VALUES (?,?,?,?,?,?,?)",
                    (snapshot_id, *(row[f] for f in FIELDS)),
                )
        return self.load_snapshot(snapshot_id)

    def delete_snapshot(self, snapshot_id):
        with self.connection:
            self.connection.execute("DELETE FROM snapshots WHERE id=?", (snapshot_id,))

    def delete_portfolio(self, portfolio_id):
        with self.connection:
            self.connection.execute("DELETE FROM portfolios WHERE id=?", (portfolio_id,))
