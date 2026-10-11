"""One validator for editor rows, imports, and persistence boundaries."""

import re
from dataclasses import dataclass
from decimal import Decimal

from .models import Holding

FIELDS = ("symbol", "quantity", "cost_basis", "current_price", "company_name", "sector")
REQUIRED = FIELDS[:4]
MAX_HOLDINGS = 10_000


@dataclass(frozen=True)
class ValidationError:
    row: int
    column: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    holdings: tuple[Holding, ...]
    errors: tuple[ValidationError, ...]

    @property
    def valid(self):
        return not self.errors


def validate_rows(rows):
    rows = list(rows)
    if not 1 <= len(rows) <= MAX_HOLDINGS:
        return ValidationResult((), (ValidationError(0, "rows", "Use 1 to 10,000 holdings."),))
    errors, holdings, seen = [], [], set()
    for number, row in enumerate(rows, 2):
        values = {k: "" if row.get(k) is None else str(row.get(k, "")).strip() for k in FIELDS}
        symbol = values["symbol"].upper()
        if not symbol or symbol in seen:
            errors.append(
                ValidationError(number, "symbol", "Symbol is required and must be unique.")
            )
        seen.add(symbol)
        numbers = {}
        for field in REQUIRED[1:]:
            value = values[field]
            if not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
                errors.append(
                    ValidationError(
                        number,
                        field,
                        "Enter a plain decimal, without currency symbols or separators.",
                    )
                )
                continue
            d = Decimal(value)
            if len(d.as_tuple().digits) > 18 or d.as_tuple().exponent < -8:
                errors.append(
                    ValidationError(
                        number, field, "Maximum 18 significant digits and 8 decimal places."
                    )
                )
            elif d < 0 or (field == "quantity" and d == 0):
                errors.append(
                    ValidationError(
                        number,
                        field,
                        "Quantity must be positive; cost and price must be nonnegative.",
                    )
                )
            else:
                numbers[field] = d
        if len(numbers) == 3:
            holdings.append(
                Holding(
                    symbol,
                    **numbers,
                    company_name=values["company_name"] or symbol,
                    sector=values["sector"] or "Unknown",
                )
            )
    return ValidationResult(() if errors else tuple(holdings), tuple(errors))


def holding_rows(holdings):
    return [
        {
            k: format(getattr(h, k), "f") if isinstance(getattr(h, k), Decimal) else getattr(h, k)
            for k in FIELDS
        }
        for h in holdings
    ]
