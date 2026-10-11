import streamlit as st

from ..calculations import analyze
from ..charts import allocation_chart, gain_chart, sector_chart
from ..ledger.codec import primitive
from ..ledger.csv_io import export_holdings_report, export_realized_report
from ..ledger.engine import replay
from ..ledger.valuation import value_account
from ..models import Holding
from ..presentation import exact, money, table


def render(repo, account_id, as_of, notices):
    ds = repo.load_dataset()
    result = replay(ds, as_of)
    value = value_account(ds, result, repo.load_prices(), account_id, as_of)
    account = next(a for a in ds.accounts if a.id == account_id)
    st.subheader("Account overview")
    st.caption(
        f"Recorded gains and dividends since {'opening cutoff ' + str(account.opening_date) if account.opening_date else 'tracking start (full history)'} · USD"
    )
    metrics = [
        (
            "Total basis" if value.total_basis is not None else "Known basis subtotal",
            money(value.known_basis),
        ),
        (
            "Total market value" if value.total_value is not None else "Known value subtotal",
            money(value.known_value),
        ),
        ("Unrealized gain / loss", money(value.unrealized_gain)),
        ("Realized gain / loss", money(value.realized_gain)),
        ("Recorded dividends", money(value.dividends)),
    ]
    for col, (label, amount) in zip([*st.columns(2), *st.columns(3)], metrics):
        col.metric(label, amount)
    unpriced = sum(h.market_value is None for h in value.holdings)
    unknown = sum(h.position.basis is None for h in value.holdings)
    st.caption(
        f"{len(value.holdings)} current holdings · {unpriced} missing prices · {unknown} unresolved bases"
    )
    if unpriced or unknown:
        st.warning(
            "Incomplete data: known subtotals exclude unknown amounts. Add dated prices or resolve lot basis in Data / Lots."
        )
    query = st.text_input("Filter holdings by symbol", key="overview_filter").upper().strip()
    holdings = [h for h in value.holdings if query in h.position.symbol]
    table(
        [
            {
                "Symbol": h.position.symbol,
                "Quantity": exact(h.position.quantity),
                "Basis (USD)": None if h.position.basis is None else float(h.position.basis),
                "Market value (USD)": None if h.market_value is None else float(h.market_value),
                "Unrealized (USD)": None if h.unrealized_gain is None else float(h.unrealized_gain),
                "Price": exact(h.price),
                "Price date": str(h.price_date or "Unknown"),
                "Status": "; ".join(i.code.replace("_", " ") for i in h.issues) or "Complete",
            }
            for h in holdings
        ]
    )
    st.download_button(
        "Download holdings report",
        export_holdings_report(value, symbols={h.position.symbol for h in holdings}),
        "holdings-report.csv",
        "text/csv",
    )
    st.download_button(
        "Download realized report",
        export_realized_report(result, account_id, as_of),
        "realized-report.csv",
        "text/csv",
    )
    if holdings:
        symbol = st.selectbox("Exact holding details", [h.position.symbol for h in holdings])
        st.json(primitive(next(h for h in holdings if h.position.symbol == symbol)), expanded=False)
        st.caption("Inspect acquisition dates and sale allocations in Lots & realized gains.")
    if (
        value.total_basis is not None
        and value.total_value is not None
        and value.total_value
        and holdings
    ):
        analysis = analyze(
            tuple(
                Holding(h.position.symbol, h.position.quantity, h.position.basis, h.price)
                for h in holdings
            )
        )
        st.plotly_chart(
            allocation_chart(analysis.stock_allocations, "Stock allocation"), width="stretch"
        )
        st.plotly_chart(sector_chart(analysis.sector_allocations), width="stretch")
        st.plotly_chart(gain_chart(analysis), width="stretch")
    if not value.holdings:
        st.info(
            "No current holdings. Add opening records or transactions; closed sales remain in realized gains."
        )
