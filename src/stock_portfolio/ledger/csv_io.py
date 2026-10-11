"""Generic bounded CSV contracts; data and report kinds never overlap."""

import csv
import hashlib
import io
import re
from dataclasses import dataclass
from enum import StrEnum

from .codec import dumps, primitive
from .models import EventKind as K


class ImportKind(StrEnum):
    transactions = "transactions"
    opening_lots = "opening_lots"
    opening_balances = "opening_balances"
    allocations = "allocations"
    prices = "prices"
    broker_holdings = "broker_holdings"


REQUIRED = {
    ImportKind.transactions: ("date", "transaction_type", "ticker"),
    ImportKind.opening_lots: ("lot_id", "ticker", "acquired_date", "quantity", "cost_basis"),
    ImportKind.opening_balances: ("ticker", "quantity", "cost_basis"),
    ImportKind.allocations: ("transaction_id", "lot_id", "quantity"),
    ImportKind.prices: ("ticker", "price_date", "price"),
    ImportKind.broker_holdings: ("ticker", "quantity", "cost_basis"),
}
OPTIONAL = {
    ImportKind.transactions: (
        "account_name",
        "transaction_id",
        "event_id",
        "sequence",
        "quantity",
        "price",
        "fees",
        "amount",
        "split_numerator",
        "split_denominator",
        "to_account",
        "reinvestment_of",
        "lot_allocations",
        "notes",
        "lot_reference",
    ),
    ImportKind.opening_lots: (
        "event_id",
        "sequence",
        "opening_date",
        "company_name",
        "sector",
        "lot_reference",
    ),
    ImportKind.opening_balances: (
        "event_id",
        "sequence",
        "opening_date",
        "company_name",
        "sector",
        "lot_reference",
    ),
    ImportKind.allocations: ("basis_amount",),
    ImportKind.prices: ("source_label",),
    ImportKind.broker_holdings: ("company_name", "sector"),
}


@dataclass(frozen=True)
class ParsedImport:
    kind: ImportKind
    rows: tuple[dict[str, str], ...]
    file_hash: str
    source_name: str
    warnings: tuple[str, ...]


def parse_import(content, kind, source_name="upload.csv"):
    kind = ImportKind(kind)
    if len(content) > 10_000_000:
        raise ValueError("CSV exceeds 10,000,000 bytes.")
    try:
        reader = csv.reader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
        header = next(reader)
        header = [h.strip().casefold() for h in header]
        if not header or "" in header or len(set(header)) != len(header):
            raise ValueError("Headers must be nonblank and unique after normalization.")
        if not set(REQUIRED[kind]) <= set(header):
            raise ValueError("Missing required columns: " + ", ".join(REQUIRED[kind]))
        supported = set(REQUIRED[kind]) | set(OPTIONAL[kind]) | {"export_kind", "format_version"}
        if kind != ImportKind.prices:
            supported.add("account_name")
        unknown = set(header) - supported
        rows = []
        metadata = set()
        for row in reader:
            if not row:
                continue
            if len(row) != len(header):
                raise ValueError(f"Row {reader.line_num}: missing or trailing cells.")
            values = dict(zip(header, (v.strip() for v in row)))
            if "export_kind" in header or "format_version" in header:
                if values.get("export_kind") != kind.value or values.get("format_version") != "1":
                    raise ValueError(
                        "Inconsistent/unsupported export kind or format version; reports are not inputs."
                    )
                metadata.add((values["export_kind"], values["format_version"]))
            rows.append({k: v for k, v in values.items() if k in supported})
            if len(rows) > 10_000:
                raise ValueError("CSV exceeds 10,000 rows.")
    except (UnicodeError, csv.Error, StopIteration) as exc:
        raise ValueError("Invalid UTF-8 CSV.") from exc
    name = re.split(r"[/\\]", source_name)[-1]
    name = "".join(c for c in name if c.isprintable())[:200] or "upload.csv"
    return ParsedImport(
        kind,
        tuple(rows),
        hashlib.sha256(content).hexdigest(),
        name,
        (("Unrecognized columns ignored: " + ", ".join(sorted(unknown))),) if unknown else (),
    )


def write_csv(rows, fields, kind):
    stream = io.StringIO(newline="")
    fields = (
        "export_kind",
        "format_version",
        *tuple(f for f in fields if f not in {"export_kind", "format_version"}),
    )
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "export_kind": str(kind),
                "format_version": "1",
                **{k: ("" if v is None else primitive(v)) for k, v in row.items()},
            }
        )
    return stream.getvalue().encode("utf-8")


def export_events(dataset):
    names = {a.id: a.name for a in dataset.accounts}
    rows = []
    for e in sorted(dataset.events, key=lambda e: (e.effective_date, e.day_sequence)):
        if e.kind in {K.OPENING_LOT, K.OPENING_BALANCE}:
            continue
        rows.append(
            {
                "account_name": names[e.account_id],
                "date": e.effective_date,
                "transaction_type": e.kind,
                "ticker": e.symbol,
                "event_id": e.id,
                "transaction_id": e.external_id,
                "sequence": e.day_sequence,
                "quantity": e.quantity,
                "price": e.price,
                "fees": e.fees,
                "amount": e.amount,
                "split_numerator": e.split_numerator,
                "split_denominator": e.split_denominator,
                "to_account": names.get(e.destination_account_id),
                "reinvestment_of": e.reinvestment_of,
                "lot_allocations": dumps(e.allocations) if e.allocations else "",
                "notes": e.notes,
                "lot_reference": e.id if e.kind == K.BUY else "",
            }
        )
    return write_csv(
        rows,
        (*REQUIRED[ImportKind.transactions], *OPTIONAL[ImportKind.transactions]),
        ImportKind.transactions,
    )


def export_openings(dataset, account_id, kind):
    kind = ImportKind(kind)
    if kind not in {ImportKind.opening_lots, ImportKind.opening_balances}:
        raise ValueError("Select detailed lots or aggregate openings.")
    account = next(a for a in dataset.accounts if a.id == account_id)
    event_kind = K.OPENING_LOT if kind == ImportKind.opening_lots else K.OPENING_BALANCE
    rows = [
        {
            "account_name": account.name,
            "lot_id": e.external_id or e.id,
            "ticker": e.symbol,
            "acquired_date": e.acquired_date,
            "quantity": e.quantity,
            "cost_basis": e.basis,
            "event_id": e.id,
            "sequence": e.day_sequence,
            "opening_date": e.effective_date,
            "lot_reference": e.id,
        }
        for e in dataset.events
        if e.account_id == account_id and e.kind == event_kind
    ]
    return write_csv(rows, (*REQUIRED[kind], *OPTIONAL[kind], "account_name"), kind)


def export_allocations(dataset, account_id):
    account = next(a for a in dataset.accounts if a.id == account_id)
    rows = [
        {
            "account_name": account.name,
            "transaction_id": e.external_id or e.id,
            "lot_id": a.lot_id,
            "quantity": a.quantity,
            "basis_amount": a.basis_amount,
        }
        for e in dataset.events
        if e.account_id == account_id
        for a in e.allocations
    ]
    return write_csv(
        rows,
        ("account_name", "transaction_id", "lot_id", "quantity", "basis_amount"),
        ImportKind.allocations,
    )


def export_prices(observations):
    return write_csv(
        [
            {
                "ticker": p.symbol,
                "price_date": p.price_date,
                "price": p.price,
                "source_label": p.source_label,
            }
            for p in observations
        ],
        ("ticker", "price_date", "price", "source_label"),
        ImportKind.prices,
    )


def template(kind):
    return write_csv([], (*REQUIRED[kind], *OPTIONAL[kind]), kind)
