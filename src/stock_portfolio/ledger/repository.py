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
