"""Immutable domain values; decimals never depend on presentation floats."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: Decimal
    cost_basis: Decimal
    current_price: Decimal
    company_name: str = ""
    sector: str = "Unknown"


@dataclass(frozen=True)
class Selection:
    symbols: frozenset[str] | None = None
    sectors: frozenset[str] | None = None


@dataclass(frozen=True)
class Metadata:
    portfolio_name: str
    snapshot_date: date
    currency: str = "USD"


@dataclass(frozen=True)
class Snapshot:
    metadata: Metadata
    holdings: tuple[Holding, ...]
    id: int | None = None
    portfolio_id: int | None = None


@dataclass(frozen=True)
class HoldingMetrics:
    holding: Holding
    market_value: Decimal
    gain: Decimal
    average_cost: Decimal
    gain_percent: Decimal | None


@dataclass(frozen=True)
class Analysis:
    holdings: tuple[HoldingMetrics, ...]
    cost_basis: Decimal
    market_value: Decimal
    gain: Decimal
    gain_percent: Decimal | None
    stock_allocations: dict[str, Decimal]
    sector_allocations: dict[str, Decimal]

    @property
    def count(self):
        return len(self.holdings)
