"""Pure calculations at 50 digits; rounding is presentation only."""

from decimal import Decimal, localcontext
from .models import Analysis, HoldingMetrics, Selection


def analyze(holdings, selection=None):
    selection = selection or Selection()
    with localcontext() as ctx:
        ctx.prec = 50
        rows = []
        sectors = {}
        for h in holdings:
            if selection.symbols is not None and h.symbol not in selection.symbols:
                continue
            if selection.sectors is not None and h.sector not in selection.sectors:
                continue
            value = h.quantity * h.current_price
            gain = value - h.cost_basis
            rows.append(
                HoldingMetrics(
                    h,
                    value,
                    gain,
                    h.cost_basis / h.quantity,
                    gain / h.cost_basis * 100 if h.cost_basis else None,
                )
            )
            sectors[h.sector] = sectors.get(h.sector, Decimal(0)) + value
        basis = sum((r.holding.cost_basis for r in rows), Decimal(0))
        value = sum((r.market_value for r in rows), Decimal(0))
        gain = value - basis
        return Analysis(
            tuple(rows),
            basis,
            value,
            gain,
            gain / basis * 100 if basis else None,
            {r.holding.symbol: r.market_value / value * 100 for r in rows} if value else {},
            {k: v / value * 100 for k, v in sectors.items()} if value else {},
        )
