"""Immutable ledger values. Decimal/date stay typed until serialization."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum


class EventKind(StrEnum):
    OPENING_LOT = "OPENING_LOT"
    OPENING_BALANCE = "OPENING_BALANCE"
    BUY = "BUY"
    SELL = "SELL"
    DIVIDEND = "DIVIDEND"
    SPLIT = "SPLIT"
    TRANSFER = "TRANSFER"


@dataclass(frozen=True)
class Account:
    id: str
    name: str
    opening_date: date | None = None
    archived: bool = False
    currency: str = "USD"
    broker_label: str = ""


@dataclass(frozen=True)
class LotAllocation:
    lot_id: str
    quantity: Decimal
    basis_amount: Decimal | None = None


@dataclass(frozen=True)
class LedgerEvent:
    id: str
    account_id: str
    effective_date: date
    day_sequence: int
    kind: EventKind
    symbol: str
    quantity: Decimal | None = None
    price: Decimal | None = None
    fees: Decimal = Decimal(0)
    amount: Decimal | None = None
    basis: Decimal | None = None
    acquired_date: date | None = None
    split_numerator: int | None = None
    split_denominator: int | None = None
    destination_account_id: str | None = None
    allocations: tuple[LotAllocation, ...] = ()
    reinvestment_of: str | None = None
    external_id: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class LedgerDataset:
    accounts: tuple[Account, ...]
    events: tuple[LedgerEvent, ...]
    revision: int
    economic_revision: int


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    row: int | None = None
    event_id: str | None = None
    account_id: str | None = None
    symbol: str | None = None


class InvalidLedger(ValueError):
    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__("; ".join(i.message for i in self.issues))


@dataclass(frozen=True)
class Lot:
    id: str
    account_id: str
    symbol: str
    acquired_date: date | None
    acquisition_order: tuple[date, int, str]
    quantity: Decimal
    basis: Decimal | None
    origin_event_id: str
    source_lot_id: str | None = None
    aggregate: bool = False
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True)
class Position:
    account_id: str
    symbol: str
    quantity: Decimal
    basis: Decimal | None
    lot_ids: tuple[str, ...]
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True)
class Disposal:
    event_id: str
    account_id: str
    symbol: str
    quantity: Decimal
    proceeds: Decimal
    basis: Decimal | None
    gain: Decimal | None
    method: str
    matches: tuple[LotAllocation, ...]
    issues: tuple[Issue, ...] = ()
    match_proceeds: tuple[Decimal, ...] = ()


@dataclass(frozen=True)
class Reinvestment:
    dividend_event_id: str
    buy_event_id: str
    amount: Decimal
    purchase_cost: Decimal
    remainder: Decimal


@dataclass(frozen=True)
class ReplayResult:
    lots: tuple[Lot, ...]
    positions: tuple[Position, ...]
    disposals: tuple[Disposal, ...]
    dividends: dict[str, Decimal]
    reinvestments: tuple[Reinvestment, ...]
    issues: tuple[Issue, ...]


@dataclass(frozen=True)
class PriceObservation:
    symbol: str
    price_date: date
    price: Decimal
    source_label: str = "Manual"


@dataclass(frozen=True)
class ValuedPosition:
    position: Position
    price: Decimal | None
    price_date: date | None
    market_value: Decimal | None
    unrealized_gain: Decimal | None
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True)
class AccountValuation:
    account_id: str
    as_of: date
    holdings: tuple[ValuedPosition, ...]
    known_basis: Decimal
    known_value: Decimal
    total_basis: Decimal | None
    total_value: Decimal | None
    unrealized_gain: Decimal | None
    realized_gain: Decimal | None
    dividends: Decimal
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True)
class BrokerHolding:
    symbol: str
    quantity: Decimal
    basis: Decimal | None


@dataclass(frozen=True)
class BrokerStatement:
    id: str
    account_id: str
    as_of: date
    holdings: tuple[BrokerHolding, ...]
    source_hash: str


@dataclass(frozen=True)
class ReconciliationRow:
    symbol: str
    local_quantity: Decimal | None
    broker_quantity: Decimal | None
    local_basis: Decimal | None
    broker_basis: Decimal | None
    quantity_difference: Decimal | None
    basis_difference: Decimal | None
    status: str


@dataclass(frozen=True)
class ReconciliationResult:
    statement_id: str
    account_id: str
    as_of: date
    source_hash: str
    ledger_revision: int
    policy: str
    quantity_tolerance: Decimal
    basis_tolerance: Decimal
    rows: tuple[ReconciliationRow, ...]
