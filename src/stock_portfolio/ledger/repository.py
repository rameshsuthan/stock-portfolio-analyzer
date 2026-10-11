"""Atomic revisioned source of truth. Every proposed history is replayed before writing."""

import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from ..database import open_database
from .codec import dumps, event_from_json
from .engine import replay
from .models import Account, InvalidLedger, Issue, LedgerDataset
from .models import EventKind as K
from .validation import precise, validate_events


class StaleRevision(ValueError):
    pass


class IdentityConflict(ValueError):
    pass


class LedgerRepository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.connection = open_database(path)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def load_dataset(self):
        accounts = tuple(
            Account(i, n, date.fromisoformat(d) if d else None, bool(a), c, b)
            for i, n, d, a, c, b in self.connection.execute(
                "SELECT id,name,opening_date,archived,currency,broker_label FROM accounts ORDER BY name_key"
            )
        )
        events = tuple(
            event_from_json(r[0])
            for r in self.connection.execute("""
            SELECT r.payload FROM ledger_event_heads h JOIN ledger_event_revisions r
            ON r.event_id=h.event_id AND r.version=h.version WHERE r.status='active'
            ORDER BY r.effective_date,r.event_id""")
        )
        rev, economic = self.connection.execute(
            "SELECT revision,economic_revision FROM ledger_state WHERE id=1"
        ).fetchone()
        return LedgerDataset(accounts, events, rev, economic)

    def _audit(self, reason, provenance=None):
        if not reason or not reason.strip():
            raise ValueError("A reason is required.")
        operation = str(uuid4())
        self.connection.execute(
            "INSERT INTO audit_operations VALUES (?,?,?,?)",
            (operation, reason.strip(), dumps(provenance or {}), datetime.now(UTC).isoformat()),
        )
        return operation

    def _bump(self, economic=False):
        self.connection.execute(
            "UPDATE ledger_state SET revision=revision+1,economic_revision=economic_revision+? WHERE id=1",
            (int(economic),),
        )

    def _check_revision(self, expected):
        actual = self.connection.execute("SELECT revision FROM ledger_state WHERE id=1").fetchone()[
            0
        ]
        if expected != actual:
            raise StaleRevision(
                "Data changed after preview. Recompute the preview before confirming."
            )

    def create_account(self, name, opening_date=None, broker_label=""):
        name = name.strip()
        if not name or (
            opening_date is not None
            and (type(opening_date) is not date or opening_date > date.today())
        ):
            raise ValueError("Account name and a nonfuture opening cutoff are required.")
        account = Account(str(uuid4()), name, opening_date, broker_label=broker_label.strip())
        try:
            with self.connection:
                self.connection.execute("BEGIN IMMEDIATE")
                self.connection.execute(
                    "INSERT INTO accounts VALUES (?,?,?,?,?,?,?)",
                    (
                        account.id,
                        name,
                        name.casefold(),
                        opening_date.isoformat() if opening_date else None,
                        0,
                        "USD",
                        account.broker_label,
                    ),
                )
                self._audit("Create account")
                self._bump()
        except sqlite3.IntegrityError as exc:
            raise ValueError("An account with that name already exists.") from exc
        return account

    def archive_account(self, account_id):
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            changed = self.connection.execute(
                "UPDATE accounts SET archived=1 WHERE id=? AND archived=0", (account_id,)
            ).rowcount
            if not changed:
                raise ValueError("Account is missing or already archived.")
            self._audit("Archive account")
            self._bump()

    def identities(self):
        return tuple(
            dict(zip(("id", "account_id", "external_id", "status", "payload"), r))
            for r in self.connection.execute("""SELECT i.id,i.account_id,i.external_id,r.status,r.payload
            FROM ledger_event_identities i JOIN ledger_event_heads h ON h.event_id=i.id
            JOIN ledger_event_revisions r ON r.event_id=h.event_id AND r.version=h.version""")
        )

    @precise
    def proposed_dataset(self, upserts, void_ids):
        old = self.load_dataset()
        identities = {r["id"]: r for r in self.identities()}
        external = {
            (r["account_id"], r["external_id"]): r["id"]
            for r in identities.values()
            if r["external_id"]
        }
        accounts = {a.id: a for a in old.accounts}
        if len({e.id for e in upserts}) != len(upserts) or len(set(void_ids)) != len(void_ids):
            raise IdentityConflict("Repeated identity in one operation.")
        touched = {e.id for e in upserts} | set(void_ids)
        if {e.id for e in upserts} & set(void_ids):
            raise IdentityConflict("Cannot revise and void the same event together.")
        for e in upserts:
            existing = identities.get(e.id)
            if existing and (existing["account_id"], existing["external_id"]) != (
                e.account_id,
                e.external_id,
            ):
                raise IdentityConflict("Event account and external identity are immutable.")
            if e.external_id and external.get((e.account_id, e.external_id), e.id) != e.id:
                raise IdentityConflict("External ID already belongs to another event.")
            if not existing and any(
                accounts.get(i) and accounts[i].archived
                for i in (e.account_id, e.destination_account_id)
            ):
                raise ValueError("Archived accounts cannot receive new events.")
        for id_ in void_ids:
            if id_ not in identities or identities[id_]["status"] != "active":
                raise IdentityConflict("Only an active known event can be voided.")
        for e in (*old.events, *upserts):
            if (
                e.reinvestment_of
                and touched & {e.id, e.reinvestment_of}
                and not {e.id, e.reinvestment_of} <= touched
            ):
                raise InvalidLedger(
                    (Issue("linked_group", "Revise or void the entire linked reinvestment group."),)
                )
        proposed = {e.id: e for e in old.events if e.id not in touched}
        proposed.update({e.id: e for e in upserts})
        for pool in old.events:
            if pool.kind == K.OPENING_BALANCE and pool.id in void_ids:
                lots = [
                    e
                    for e in proposed.values()
                    if e.account_id == pool.account_id
                    and e.symbol == pool.symbol
                    and e.kind == K.OPENING_LOT
                ]
                if lots and (sum(e.quantity for e in lots), sum(e.basis for e in lots)) != (
                    pool.quantity,
                    pool.basis,
                ):
                    raise InvalidLedger(
                        (
                            Issue(
                                "opening_totals",
                                "Detailed replacement must preserve opening quantity and basis.",
                            ),
                        )
                    )
        result = LedgerDataset(
            old.accounts, tuple(proposed.values()), old.revision, old.economic_revision
        )
        issues = validate_events(result, today=date.today())
        if issues:
            raise InvalidLedger(issues)
        replay(result, max((e.effective_date for e in result.events), default=date.min))
        return result

    def _write_events(self, upserts, void_ids, operation):
        c = self.connection
        for event in upserts:
            c.execute(
                "INSERT OR IGNORE INTO ledger_event_identities VALUES (?,?,?)",
                (event.id, event.account_id, event.external_id),
            )
        changes = [(e.id, "active", dumps(e), e.effective_date.isoformat()) for e in upserts]
        for id_ in void_ids:
            row = c.execute(
                """SELECT r.payload,r.effective_date FROM ledger_event_heads h JOIN ledger_event_revisions r
                 ON r.event_id=h.event_id AND r.version=h.version WHERE h.event_id=?""",
                (id_,),
            ).fetchone()
            changes.append((id_, "void", *row))
        for id_, status, payload, day in changes:
            version = c.execute(
                "SELECT coalesce(max(version),0)+1 FROM ledger_event_revisions WHERE event_id=?",
                (id_,),
            ).fetchone()[0]
            c.execute(
                "INSERT INTO ledger_event_revisions VALUES (?,?,?,?,?,?)",
                (id_, version, status, payload, day, operation),
            )
            c.execute(
                "INSERT INTO ledger_event_heads VALUES (?,?) ON CONFLICT(event_id) DO UPDATE SET version=excluded.version",
                (id_, version),
            )

    def apply_operation(self, upserts, void_ids, expected_revision, reason, provenance=None):
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            self._check_revision(expected_revision)
            self.proposed_dataset(upserts, void_ids)
            operation = self._audit(reason, provenance)
            self._write_events(upserts, void_ids, operation)
            self._bump(economic=bool(upserts or void_ids))
        return self.load_dataset().revision

    def history(self, event_id):
        keys = (
            "version",
            "status",
            "payload",
            "reason",
            "operation_id",
            "provenance",
            "recorded_at",
        )
        return tuple(
            dict(zip(keys, row))
            for row in self.connection.execute(
                """
            SELECT r.version,r.status,r.payload,a.reason,a.id,a.provenance,a.recorded_at
            FROM ledger_event_revisions r JOIN audit_operations a ON a.id=r.operation_id
            WHERE r.event_id=? ORDER BY r.version""",
                (event_id,),
            )
        )

    def find_import_batch(self, batch, effective_date):
        row = self.connection.execute(
            """SELECT id FROM import_batches WHERE account_ids=? AND kind=?
            AND source_hash=? AND effective_date IS ? ORDER BY rowid LIMIT 1""",
            (
                dumps(batch.account_ids),
                batch.kind,
                batch.source_hash,
                effective_date.isoformat() if effective_date else None,
            ),
        ).fetchone()
        return row[0] if row else None

    def commit_import_batch(self, preview):
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            self._check_revision(preview.expected_revision)
            if preview.issues:
                raise InvalidLedger(preview.issues)
            existing = self.find_import_batch(preview.batch, preview.effective_date)
            if existing:
                return existing
            self.proposed_dataset(preview.proposed_events, preview.void_ids)
            operation = self._audit(
                "Confirm CSV import",
                {
                    "source_hash": preview.batch.source_hash,
                    "source_name": preview.batch.source_name,
                },
            )
            self._write_events(preview.proposed_events, preview.void_ids, operation)
            self._write_prices(preview.proposed_prices, operation)
            if preview.proposed_statement:
                self._write_statement(preview.proposed_statement)
            batch = preview.batch
            self.connection.execute(
                "INSERT INTO import_batches VALUES (?,?,?,?,?,?,?)",
                (
                    batch.id,
                    dumps(batch.account_ids),
                    batch.kind,
                    batch.source_hash,
                    batch.source_name,
                    preview.effective_date.isoformat() if preview.effective_date else None,
                    operation,
                ),
            )
            choices = {c.row: c.action for c in batch.choices}
            for number, row in enumerate(batch.rows, 2):
                self.connection.execute(
                    "INSERT INTO import_rows VALUES (?,?,?,?)",
                    (batch.id, number, dumps(row), choices.get(number, "keep")),
                )
            self._bump(economic=bool(preview.proposed_events or preview.void_ids))
        return batch.id

    def validate_prices(self, observations):
        from .validation import decimal_input

        seen = set()
        for p in observations:
            if (
                not p.symbol
                or p.symbol != p.symbol.strip().upper()
                or type(p.price_date) is not date
                or p.price_date > date.today()
            ):
                raise ValueError("Price requires normalized symbol and a nonfuture date.")
            decimal_input(p.price)
            if (p.symbol, p.price_date) in seen:
                raise ValueError("Duplicate symbol/date price in one batch.")
            seen.add((p.symbol, p.price_date))

    def _write_prices(self, observations, operation):
        self.validate_prices(observations)
        for p in observations:
            day = p.price_date.isoformat()
            version = self.connection.execute(
                "SELECT coalesce(max(version),0)+1 FROM price_revisions WHERE symbol=? AND price_date=?",
                (p.symbol, day),
            ).fetchone()[0]
            self.connection.execute(
                "INSERT INTO price_revisions VALUES (?,?,?,?,?)",
                (p.symbol, day, version, dumps(p), operation),
            )
            self.connection.execute(
                "INSERT INTO price_observations VALUES (?,?,?,?) ON CONFLICT(symbol,price_date) DO UPDATE SET price=excluded.price,source_label=excluded.source_label",
                (p.symbol, day, format(p.price, "f"), p.source_label),
            )

    def save_prices(self, observations, expected_revision, reason):
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            self._check_revision(expected_revision)
            self.validate_prices(observations)
            operation = self._audit(reason)
            self._write_prices(observations, operation)
            self._bump()

    def load_prices(self):
        from decimal import Decimal

        from .models import PriceObservation

        return tuple(
            PriceObservation(s, date.fromisoformat(d), Decimal(p), label)
            for s, d, p, label in self.connection.execute(
                "SELECT symbol,price_date,price,source_label FROM price_observations ORDER BY symbol,price_date"
            )
        )

    def price_history(self, symbol, price_date):
        return tuple(
            dict(zip(("version", "payload", "reason", "recorded_at"), r))
            for r in self.connection.execute(
                """
            SELECT p.version,p.payload,a.reason,a.recorded_at FROM price_revisions p
            JOIN audit_operations a ON a.id=p.operation_id WHERE symbol=? AND price_date=? ORDER BY version""",
                (symbol, price_date.isoformat()),
            )
        )

    def _write_statement(self, statement):
        from .reconciliation import validate_statement

        validate_statement(self.load_dataset(), statement)
        if self.connection.execute(
            "SELECT 1 FROM broker_statements WHERE id=?", (statement.id,)
        ).fetchone():
            raise ValueError("Broker statements are immutable; import a new assertion.")
        self.connection.execute(
            "INSERT INTO broker_statements VALUES (?,?,?,?)",
            (
                statement.id,
                statement.account_id,
                statement.as_of.isoformat(),
                statement.source_hash,
            ),
        )
        for h in statement.holdings:
            self.connection.execute(
                "INSERT INTO broker_statement_rows VALUES (?,?,?,?)",
                (
                    statement.id,
                    h.symbol,
                    format(h.quantity, "f"),
                    format(h.basis, "f") if h.basis is not None else None,
                ),
            )

    def save_statement(self, statement):
        """Persist a caller-confirmed complete end-of-day assertion."""
        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            self._write_statement(statement)
            self._audit("Save complete broker statement", {"source_hash": statement.source_hash})
            self._bump()
        return statement.id

    def load_statements(self, account_id):
        from decimal import Decimal as D

        from .models import BrokerHolding, BrokerStatement

        return tuple(
            BrokerStatement(
                id_,
                a,
                date.fromisoformat(day),
                tuple(
                    BrokerHolding(s, D(q), D(b) if b is not None else None)
                    for s, q, b in self.connection.execute(
                        "SELECT symbol,quantity,basis FROM broker_statement_rows WHERE statement_id=? ORDER BY symbol",
                        (id_,),
                    )
                ),
                hash_,
            )
            for id_, a, day, hash_ in self.connection.execute(
                "SELECT id,account_id,as_of,source_hash FROM broker_statements WHERE account_id=? ORDER BY rowid",
                (account_id,),
            )
        )

    def save_reconciliation(self, result):
        from .reconciliation import reconcile

        with self.connection:
            self.connection.execute("BEGIN IMMEDIATE")
            statement = next(
                (s for s in self.load_statements(result.account_id) if s.id == result.statement_id),
                None,
            )
            if (
                statement is None
                or reconcile(
                    self.load_dataset(),
                    statement,
                    result.quantity_tolerance,
                    result.basis_tolerance,
                )
                != result
            ):
                raise StaleRevision("Comparison changed; recalculate before saving.")
            id_ = str(uuid4())
            self.connection.execute(
                "INSERT INTO reconciliation_runs VALUES (?,?,?,?,?)",
                (
                    id_,
                    result.statement_id,
                    result.account_id,
                    dumps(result),
                    datetime.now(UTC).isoformat(),
                ),
            )
            for row in result.rows:
                self.connection.execute(
                    "INSERT INTO reconciliation_rows VALUES (?,?,?)", (id_, row.symbol, dumps(row))
                )
            self._audit("Save reconciliation evidence")
            self._bump()
        return id_

    def load_reconciliations(self, account_id):
        import json
        from decimal import Decimal as D

        from .models import ReconciliationResult, ReconciliationRow

        results = []
        for (payload,) in self.connection.execute(
            "SELECT payload FROM reconciliation_runs WHERE account_id=? ORDER BY rowid",
            (account_id,),
        ):
            value = json.loads(payload)
            value["as_of"] = date.fromisoformat(value["as_of"])
            for f in ("quantity_tolerance", "basis_tolerance"):
                value[f] = D(value[f])
            rows = []
            for r in value["rows"]:
                rows.append(
                    ReconciliationRow(
                        **{
                            k: (D(v) if v is not None and k not in {"symbol", "status"} else v)
                            for k, v in r.items()
                        }
                    )
                )
            value["rows"] = tuple(rows)
            results.append(ReconciliationResult(**value))
        return tuple(results)
