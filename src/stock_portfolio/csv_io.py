"""Strict UTF-8 CSV exchange. Raw uploaded bytes are never retained."""

import csv
import io
from dataclasses import dataclass
from datetime import date

from .models import Metadata
from .validation import FIELDS, MAX_HOLDINGS, REQUIRED, holding_rows

MAX_BYTES = 10_000_000
META = ("portfolio_name", "snapshot_date", "currency", "export_kind")


class CsvFormatError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCSV:
    rows: list[dict[str, str]]
    metadata: Metadata | None
    warnings: tuple[str, ...]


def parse_csv(content):
    if len(content) > MAX_BYTES:
        raise CsvFormatError("Upload limit is 10 MB.")
    try:
        text = content.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        headers = [h.strip().lower() for h in next(reader)]
        if len(headers) != len(set(headers)) or not set(REQUIRED) <= set(headers) or "" in headers:
            raise CsvFormatError(
                "Headers must be unique and include symbol, quantity, cost_basis, current_price."
            )
        meta_present = set(META) & set(headers)
        if meta_present and meta_present != set(META):
            raise CsvFormatError(
                "Snapshot metadata requires portfolio_name, snapshot_date, currency, export_kind."
            )
        rows, metadata = [], None
        for index, cells in enumerate(reader, 2):
            if len(cells) != len(headers):
                raise CsvFormatError(f"Row {index}: column count differs from header.")
            raw = dict(zip(headers, cells))
            if meta_present:
                if raw["export_kind"].strip() != "snapshot":
                    raise CsvFormatError("Analysis reports cannot be imported as snapshots.")
                name = raw["portfolio_name"].strip()
                if not name or raw["currency"].strip() != "USD":
                    raise CsvFormatError(f"Row {index}: portfolio name and USD currency required.")
                current = Metadata(name, date.fromisoformat(raw["snapshot_date"].strip()))
                if metadata is not None and metadata != current:
                    raise CsvFormatError("Snapshot metadata is inconsistent across rows.")
                metadata = current
            rows.append({k: raw.get(k, "") for k in FIELDS})
            if len(rows) > MAX_HOLDINGS:
                raise CsvFormatError("Maximum 10,000 holdings.")
        if not rows:
            raise CsvFormatError("CSV must contain at least one holding.")
        extra = set(headers) - set(FIELDS) - set(META)
        return ParsedCSV(
            rows, metadata, ("Ignored columns: " + ", ".join(sorted(extra)),) if extra else ()
        )
    except (UnicodeDecodeError, csv.Error, StopIteration, ValueError) as exc:
        if isinstance(exc, CsvFormatError):
            raise
        raise CsvFormatError(f"Invalid UTF-8 CSV or snapshot date: {exc}") from exc


def _metadata(metadata, kind):
    return {
        "portfolio_name": metadata.portfolio_name,
        "snapshot_date": metadata.snapshot_date.isoformat(),
        "currency": metadata.currency,
        "export_kind": kind,
    }


def _write(rows, fields):
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


def export_snapshot(snapshot):
    return _write(
        [r | _metadata(snapshot.metadata, "snapshot") for r in holding_rows(snapshot.holdings)],
        FIELDS + META,
    )


def export_analysis(analysis, metadata):
    metrics = ("market_value", "gain", "average_cost", "gain_percent", "allocation_percent")
    rows = []
    for r in analysis.holdings:
        values = {k: getattr(r, k) for k in metrics[:-1]}
        values["allocation_percent"] = analysis.stock_allocations.get(r.holding.symbol)
        rows.append(
            holding_rows([r.holding])[0]
            | _metadata(metadata, "analysis")
            | {k: "" if v is None else format(v, "f") for k, v in values.items()}
        )
    return _write(rows, FIELDS + META + metrics)
