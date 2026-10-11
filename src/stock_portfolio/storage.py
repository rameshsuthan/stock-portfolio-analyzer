"""Local SQLite storage. Replacement is one rollback-safe transaction."""

import sqlite3
from datetime import date

from .database import UnsupportedSchema, open_database  # noqa: F401
from .models import Metadata, Snapshot
from .validation import FIELDS, holding_rows, validate_rows


class ReplacementRequired(ValueError):
    pass


class Repository:
    def __init__(self, path):
        self.connection = open_database(path)

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
                id_ = self.connection.execute(
                    "INSERT INTO portfolios(name,name_key) VALUES (?,?)", (name, name.casefold())
                ).lastrowid
                self.connection.execute("UPDATE ledger_state SET revision=revision+1 WHERE id=1")
                return id_
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
            c.execute("UPDATE ledger_state SET revision=revision+1 WHERE id=1")
        return self.load_snapshot(snapshot_id)

    def delete_snapshot(self, snapshot_id):
        with self.connection:
            changed = self.connection.execute(
                "DELETE FROM snapshots WHERE id=?", (snapshot_id,)
            ).rowcount
            if changed:
                self.connection.execute("UPDATE ledger_state SET revision=revision+1 WHERE id=1")

    def delete_portfolio(self, portfolio_id):
        with self.connection:
            changed = self.connection.execute(
                "DELETE FROM portfolios WHERE id=?", (portfolio_id,)
            ).rowcount
            if changed:
                self.connection.execute("UPDATE ledger_state SET revision=revision+1 WHERE id=1")
