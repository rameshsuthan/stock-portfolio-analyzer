"""Session previews with explicit duplicate choices and revision-bound confirmation."""

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date
from uuid import uuid4

from .codec import dumps, event_from_json, primitive
from .csv_io import ImportKind as I
from .engine import replay
from .models import (
    BrokerHolding,
    BrokerStatement,
    InvalidLedger,
    Issue,
    LedgerEvent,
    LotAllocation,
    PriceObservation,
    ReplayResult,
)
from .models import EventKind as K
from .repository import IdentityConflict
from .validation import decimal_input, iso_date


@dataclass(frozen=True)
class ImportChoice:
    row: int
    action: str


@dataclass(frozen=True)
class ImportBatch:
    id: str
    account_ids: tuple[str, ...]
    kind: I
    source_hash: str
    source_name: str
    rows: tuple[dict[str, str], ...]
    choices: tuple[ImportChoice, ...]


@dataclass(frozen=True)
class ImportPreview:
    id: str
    kind: I
    account_id: str | None
    effective_date: date | None
    expected_revision: int
    issues: tuple[Issue, ...]
    warnings: tuple[str, ...]
    duplicate_rows: dict[int, int]
    proposed_events: tuple[LedgerEvent, ...]
    void_ids: tuple[str, ...]
    proposed_prices: tuple[PriceObservation, ...]
    proposed_statement: BrokerStatement | None
    projected: ReplayResult | None
    batch: ImportBatch
    no_op_batch_id: str | None = None


def fingerprint(event):
    values = primitive(event)
    for key in ("id", "external_id", "day_sequence", "notes"):
        values.pop(key)
    return dumps(values)


def _allocations(text):
    if not text:
        return ()
    rows = json.loads(text)
    if not isinstance(rows, list):
        raise ValueError("lot_allocations must be a JSON array.")  # noqa: TRY004
    result = []
    for r in rows:
        if not isinstance(r, dict) or set(r) - {"lot_id", "quantity", "basis_amount"}:
            raise ValueError("Invalid allocation fields.")
        if not isinstance(r.get("quantity"), str) or (
            r.get("basis_amount") is not None and not isinstance(r["basis_amount"], str)
        ):
            raise ValueError("Allocation amounts must be decimal strings.")
        result.append(
            LotAllocation(
                r["lot_id"],
                decimal_input(r["quantity"], positive=True),
                decimal_input(r["basis_amount"]) if r.get("basis_amount") is not None else None,
            )
        )
    return tuple(result)


def prepare_import(repo, parsed, account_id, effective_date=None, choices=()):
    dataset = repo.load_dataset()
    accounts = {a.id: a for a in dataset.accounts}
    names = {a.name: a for a in dataset.accounts}
    issues, rows, scopes, prices, holdings = [], [], set(), [], []
    proposed, duplicates, dispositions = [], {}, {c.row: c.action for c in choices}
    identity = {r["id"]: r for r in repo.identities()}
    external = {
        (r["account_id"], r["external_id"]): r for r in identity.values() if r["external_id"]
    }
    registry = defaultdict(set)
    for r in identity.values():
        registry[(r["account_id"], r["id"])].add(r["id"])
        if r["external_id"]:
            registry[(r["account_id"], r["external_id"])].add(r["id"])
    next_sequence = defaultdict(int)
    for e in dataset.events:
        next_sequence[e.effective_date] = max(next_sequence[e.effective_date], e.day_sequence)

    def scope(row):
        if parsed.kind == I.prices:
            return None
        if account_id is None:
            if (
                parsed.kind not in {I.transactions, I.allocations}
                or row.get("account_name") not in names
            ):
                raise ValueError(
                    "Multiple accounts requires an exact existing account_name on every row."
                )
            account = names[row["account_name"]]
        else:
            account = accounts.get(account_id)
            if account is None or (row.get("account_name") and row["account_name"] != account.name):
                raise ValueError("Account metadata does not match selected account.")
        scopes.add(account.id)
        return account

    for number, row in enumerate(parsed.rows, 2):
        try:
            a = scope(row)
            if parsed.kind == I.prices:
                prices.append(
                    PriceObservation(
                        row["ticker"].upper(),
                        iso_date(row["price_date"]),
                        decimal_input(row["price"]),
                        row.get("source_label") or "CSV",
                    )
                )
                continue
            if parsed.kind == I.broker_holdings:
                holdings.append(
                    BrokerHolding(
                        row["ticker"].upper(),
                        decimal_input(row["quantity"]),
                        decimal_input(row["cost_basis"]) if row["cost_basis"] else None,
                    )
                )
                continue
            if parsed.kind == I.allocations:
                rows.append((number, a, row))
                continue
            opening = parsed.kind in {I.opening_lots, I.opening_balances}
            day = effective_date if opening else iso_date(row["date"])
            if opening and (
                day is None
                or day != a.opening_date
                or (row.get("opening_date") and iso_date(row["opening_date"]) != day)
            ):
                raise ValueError("Select the matching account opening cutoff.")
            kind = (
                (K.OPENING_LOT if parsed.kind == I.opening_lots else K.OPENING_BALANCE)
                if opening
                else K(row["transaction_type"].upper())
            )
            if not opening and kind in {K.OPENING_LOT, K.OPENING_BALANCE}:
                raise ValueError("Use the separate opening importer.")
            ext = row.get("lot_id") if parsed.kind == I.opening_lots else row.get("transaction_id")
            ext = ext or None
            incoming_id = row.get("event_id")
            existing = (
                identity.get(incoming_id)
                if incoming_id
                else external.get((a.id, ext))
                if ext
                else None
            )
            if (
                incoming_id
                and incoming_id in identity
                and identity[incoming_id]["account_id"] != a.id
            ):
                raise IdentityConflict("Internal event ID belongs to another account.")
            if (
                incoming_id
                and ext
                and (a.id, ext) in external
                and external[(a.id, ext)]["id"] != incoming_id
            ):
                raise IdentityConflict("Conflicting internal and external IDs.")
            id_ = incoming_id or (existing["id"] if existing else str(uuid4()))
            if row.get("lot_reference") and row["lot_reference"] != id_:
                raise ValueError("Lot reference must equal its originating event ID.")
            old = event_from_json(existing["payload"]) if existing else None
            seq = (
                int(row["sequence"])
                if row.get("sequence")
                else old.day_sequence
                if old
                else next_sequence[day] + 1
            )
            next_sequence[day] = max(next_sequence[day], seq)
            values = {}
            for field in ("quantity", "price", "fees", "amount"):
                if row.get(field):
                    values[field] = decimal_input(row[field], positive=field == "quantity")
            if opening:
                values["basis"] = decimal_input(row["cost_basis"])
                if parsed.kind == I.opening_lots:
                    if not ext:
                        raise ValueError("Detailed opening lot_id is required.")
                    values["acquired_date"] = iso_date(row["acquired_date"])
            for field in ("split_numerator", "split_denominator"):
                if row.get(field):
                    values[field] = int(row[field])
            if row.get("to_account"):
                if row["to_account"] not in names:
                    raise ValueError("Unknown exact destination account name.")
                values["destination_account_id"] = names[row["to_account"]].id
            if row.get("reinvestment_of") and not (ext or incoming_id):
                raise ValueError("Linked reinvestment CSV rows require event/transaction IDs.")
            e = LedgerEvent(
                id_,
                a.id,
                day,
                seq,
                kind,
                row["ticker"].upper(),
                **values,
                external_id=ext,
                notes=row.get("notes", ""),
                allocations=_allocations(row.get("lot_allocations", "")),
                reinvestment_of=row.get("reinvestment_of") or None,
            )
            rows.append((number, e, existing))
            registry[(a.id, id_)].add(id_)
            if ext:
                registry[(a.id, ext)].add(id_)
        except (ValueError, KeyError, TypeError) as exc:
            issues.append(
                Issue(
                    "identity_conflict" if isinstance(exc, IdentityConflict) else "invalid_row",
                    str(exc),
                    row=number,
                )
            )
    if account_id is not None and parsed.kind != I.prices:
        scopes.add(account_id)
    batch = ImportBatch(
        str(uuid4()),
        tuple(sorted(scopes)),
        parsed.kind,
        parsed.file_hash,
        parsed.source_name,
        parsed.rows,
        choices,
    )
    old_batch = repo.find_import_batch(batch, effective_date)
    if old_batch:
        return ImportPreview(
            str(uuid4()),
            parsed.kind,
            account_id,
            effective_date,
            dataset.revision,
            (),
            parsed.warnings,
            {},
            (),
            (),
            (),
            None,
            None,
            batch,
            old_batch,
        )

    def resolve(account, reference):
        candidates = registry.get((account, reference), set())
        if len(candidates) != 1:
            raise ValueError("Unknown or ambiguous account-scoped event reference.")
        return next(iter(candidates))

    if parsed.kind == I.allocations:
        groups = defaultdict(list)
        active = {e.id: e for e in dataset.events}
        for number, a, row in rows:
            try:
                id_ = resolve(a.id, row["transaction_id"])
                if id_ not in active or active[id_].kind not in {K.SELL, K.TRANSFER}:
                    raise ValueError("Allocations require an active sale/transfer.")
                groups[id_].append(
                    LotAllocation(
                        row["lot_id"],
                        decimal_input(row["quantity"], positive=True),
                        decimal_input(row["basis_amount"]) if row.get("basis_amount") else None,
                    )
                )
            except (ValueError, KeyError) as exc:
                issues.append(Issue("invalid_row", str(exc), row=number))
        proposed = [
            replace(active[id_], allocations=tuple(values)) for id_, values in groups.items()
        ]
    elif parsed.kind in {I.transactions, I.opening_lots, I.opening_balances}:
        resolved = []
        for number, e, existing in rows:
            try:
                if e.reinvestment_of:
                    e = replace(e, reinvestment_of=resolve(e.account_id, e.reinvestment_of))
                if existing:
                    if existing["status"] == "void" or event_from_json(existing["payload"]) != e:
                        raise IdentityConflict(
                            "Existing ID differs or is voided; use explicit correction/revival."
                        )
                    dispositions[number] = "skip"
                else:
                    resolved.append((number, e))
            except ValueError as exc:
                issues.append(Issue("identity_conflict", str(exc), row=number))
        counts = Counter(fingerprint(e) for e in dataset.events)
        within = Counter(fingerprint(e) for _, e in resolved)
        for number, e in resolved:
            key = fingerprint(e)
            if (
                not e.external_id
                and not parsed.rows[number - 2].get("event_id")
                and (counts[key] or within[key] > 1)
            ):
                duplicates[number] = counts[key] + within[key]
                if dispositions.get(number) not in {"keep", "skip"}:
                    issues.append(
                        Issue(
                            "possible_duplicate",
                            "Choose keep or skip for this possible duplicate occurrence.",
                            row=number,
                        )
                    )
            if dispositions.get(number) != "skip":
                proposed.append(e)
            dispositions.setdefault(number, "keep")
    if prices:
        try:
            repo.validate_prices(prices)
        except ValueError as exc:
            issues.append(Issue("invalid_price", str(exc)))
    projected, statement = None, None
    if parsed.kind == I.broker_holdings:
        if effective_date is None or account_id is None:
            issues.append(Issue("statement_date", "Select account and statement date."))
        else:
            statement = BrokerStatement(
                str(uuid4()), account_id, effective_date, tuple(holdings), parsed.file_hash
            )
    if statement:
        from .reconciliation import validate_statement

        try:
            validate_statement(dataset, statement)
        except ValueError as exc:
            issues.append(Issue("invalid_statement", str(exc)))
    if not issues and proposed:
        try:
            candidate = repo.proposed_dataset(tuple(proposed), ())
            projected = replay(
                candidate, max((e.effective_date for e in candidate.events), default=date.min)
            )
        except (InvalidLedger, ValueError) as exc:
            event_rows = {e.id: n for n, e, *_ in rows if isinstance(e, LedgerEvent)}
            failures = (
                exc.issues
                if isinstance(exc, InvalidLedger)
                else (Issue("invalid_history", str(exc)),)
            )
            issues.extend(replace(i, row=event_rows.get(i.event_id, 2)) for i in failures)
    batch = replace(
        batch, choices=tuple(ImportChoice(n, a) for n, a in sorted(dispositions.items()))
    )
    return ImportPreview(
        str(uuid4()),
        parsed.kind,
        account_id,
        effective_date,
        dataset.revision,
        tuple(issues),
        parsed.warnings,
        duplicates,
        tuple(proposed),
        (),
        tuple(prices),
        statement,
        projected,
        batch,
    )


def commit_import(repo, preview):
    return repo.commit_import_batch(preview)
