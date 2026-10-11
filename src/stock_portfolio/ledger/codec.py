"""Canonical exact serialization; never route financial values through floats."""

import json
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from .models import EventKind, LedgerEvent, LotAllocation


def primitive(value):
    if is_dataclass(value):
        return primitive(asdict(value))
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Nonfinite numbers are not supported.")
        return format(value, "f")
    if isinstance(value, float):
        raise ValueError("Binary float is not a ledger storage value.")  # noqa: TRY004
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: primitive(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [primitive(v) for v in value]
    return value


def dumps(value):
    return json.dumps(
        primitive(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def event_from_json(payload):
    values = json.loads(payload)
    for field in ("quantity", "price", "fees", "amount", "basis"):
        if values.get(field) is not None:
            values[field] = Decimal(values[field])
    for field in ("effective_date", "acquired_date"):
        if values.get(field):
            values[field] = date.fromisoformat(values[field])
    values["kind"] = EventKind(values["kind"])
    values["allocations"] = tuple(
        LotAllocation(
            a["lot_id"],
            Decimal(a["quantity"]),
            Decimal(a["basis_amount"]) if a.get("basis_amount") is not None else None,
        )
        for a in values.get("allocations", ())
    )
    return LedgerEvent(**values)
