"""Streamlit presentation. Editor inputs remain strings until shared validation."""

from datetime import date
from pathlib import Path
import os
import sqlite3
import pandas as pd
import streamlit as st
from .csv_io import parse_csv, CsvFormatError, export_snapshot, export_analysis
from .calculations import analyze
from .charts import allocation_chart, gain_chart
from .models import Metadata, Selection
from .storage import Repository, ReplacementRequired
from .validation import FIELDS, holding_rows
from .workflow import Draft

ROOT = Path(__file__).resolve().parents[2]


def _queue_load(rows, metadata, saved=False):
    st.session_state["load_next"] = (rows, metadata, saved)
    st.rerun()


def _apply_load():
    state = st.session_state
    if "load_next" in state:
        rows, metadata, saved = state.pop("load_next")
        state["draft"].load(rows, metadata, discard=True, saved=saved)
        state["editor_base"] = rows
        state["generation"] += 1
        state["target_name"] = metadata.portfolio_name
        state["target_date"] = metadata.snapshot_date
        for k in ("symbols", "sectors", "pending_switch", "pending_replace"):
            state.pop(k, None)


def _render(repo):
    state = st.session_state
    if "draft" not in state:
        state["draft"] = Draft()
        state["generation"] = 0
        state["editor_base"] = []
        portfolios = repo.list_portfolios()
        if portfolios:
            snapshots = repo.list_snapshots(portfolios[0][0])
            if snapshots:
                s = repo.load_snapshot(snapshots[0][0])
                state["load_next"] = (holding_rows(s.holdings), s.metadata, True)
    _apply_load()
    draft = state["draft"]
    st.title("Stock Portfolio Analyzer")
    st.caption("Local portfolios · USD · Prices supplied by you")
    action = None
    delete = None
    with st.sidebar:
        st.header("Saved portfolios")
        portfolios = repo.list_portfolios()
        names = dict(portfolios)
        selected = st.selectbox(
            "Portfolio",
            [p for p, _ in portfolios],
            format_func=names.get,
            index=0 if portfolios else None,
        )
        snapshots = repo.list_snapshots(selected) if selected is not None else []
        dates = dict(snapshots)
        sid = st.selectbox(
            "Snapshot date",
            [i for i, _ in snapshots],
            format_func=lambda i: str(dates[i]),
            index=0 if snapshots else None,
        )
        if st.button("Open selected snapshot", disabled=sid is None):
            s = repo.load_snapshot(sid)
            action = (holding_rows(s.holdings), s.metadata, True)
        if st.button("Delete selected snapshot", disabled=sid is None):
            delete = ("snapshot", sid, f"{names[selected]} / {dates[sid]}")
        if st.button("Delete selected portfolio", disabled=selected is None):
            delete = ("portfolio", selected, names[selected])
        st.divider()
        if st.button("New blank draft"):
            action = ([], Metadata("", date.today()), False)
        if st.button("Load synthetic sample"):
            action = (
                parse_csv((ROOT / "samples/demo.csv").read_bytes()).rows,
                Metadata("Synthetic demo", date.today()),
                False,
            )
        st.caption(
            "Drafts stay in this browser session until saved. Closing the browser can lose unsaved changes."
        )
    st.subheader("Import or edit holdings")
    st.caption(
        "Total cost basis is authoritative. Plain decimals only: up to 18 significant digits and 8 decimal places. Maximum 10,000 rows / 10 MB."
    )
    st.download_button(
        "Download CSV template",
        (ROOT / "samples/template.csv").read_bytes(),
        "portfolio-template.csv",
        "text/csv",
    )
    upload = st.file_uploader("Holdings CSV", type=["csv"], max_upload_size=10)
    if st.button("Import uploaded CSV", disabled=upload is None):
        try:
            parsed = parse_csv(upload.getvalue())
            action = (parsed.rows, parsed.metadata or draft.metadata, False)
            for warning in parsed.warnings:
                st.warning(warning)
        except CsvFormatError as exc:
            st.error(str(exc))
    name = st.text_input(
        "Target portfolio name", value=draft.metadata.portfolio_name, key="target_name"
    )
    as_of = st.date_input("Prices as of", value=draft.metadata.snapshot_date, key="target_date")
    frame = pd.DataFrame(state["editor_base"], columns=FIELDS).fillna("").astype(str)
    edited = st.data_editor(
        frame,
        key=f"editor_{state['generation']}",
        num_rows="dynamic",
        hide_index=True,
        column_config={f: st.column_config.TextColumn(f) for f in FIELDS},
        width="stretch",
    )
    rows = edited.fillna("").to_dict("records")
    if rows != draft.rows:
        state.pop("symbols", None)
        state.pop("sectors", None)
    draft.update(rows, Metadata(name, as_of))
    if action:
        if draft.dirty:
            state["pending_switch"] = action
        else:
            _queue_load(*action)
    if "pending_switch" in state:
        st.warning("Switching datasets will discard unsaved changes.")
        if st.button("Discard changes and switch"):
            _queue_load(*state["pending_switch"])
        if st.button("Cancel switch"):
            state.pop("pending_switch")
            st.rerun()
    if delete:
        state["pending_delete"] = delete
    if "pending_delete" in state:
        kind, ident, label = state["pending_delete"]
        st.warning(f"Permanently delete {kind}: {label}? The current draft remains in memory.")
        if st.button("Confirm deletion"):
            if kind == "snapshot":
                repo.delete_snapshot(ident)
            else:
                repo.delete_portfolio(ident)
            state.pop("pending_delete")
            draft._saved = None
            st.rerun()
        if st.button("Cancel deletion"):
            state.pop("pending_delete")
            st.rerun()
    result = draft.validation
    for error in result.errors:
        st.error(f"Row {error.row}, {error.column}: {error.message}")
    valid = result.valid and bool(name.strip()) and as_of is not None
    st.caption(
        "Unsaved draft" if draft.dirty else "Saved snapshot" if draft._saved else "Empty draft"
    )
    if st.button("Save complete snapshot", disabled=not valid):
        try:
            draft.save(repo)
            st.success("Complete snapshot saved.")
            st.rerun()
        except ReplacementRequired:
            state["pending_replace"] = draft.snapshot()
        except (ValueError, sqlite3.Error) as exc:
            st.error(f"Save failed; draft preserved. {exc}")
    pending = state.get("pending_replace")
    if pending and (not valid or pending != draft.snapshot()):
        state.pop("pending_replace")
        pending = None
    if pending:
        st.warning(
            f"Replace all saved holdings for {pending.metadata.portfolio_name} on {pending.metadata.snapshot_date}?"
        )
        if st.button("Confirm complete replacement"):
            try:
                draft.save(repo, replace=True)
                state.pop("pending_replace")
                st.rerun()
            except (ValueError, sqlite3.Error) as exc:
                st.error(f"Save failed; previous snapshot and draft preserved. {exc}")
        if st.button("Cancel replacement"):
            state.pop("pending_replace")
            st.rerun()
    if valid:
        st.info(
            f"{'Draft' if draft.dirty else 'Saved'} analysis · {as_of} · USD · Manual supplied prices"
        )
    return draft, valid


def main():
    st.set_page_config(page_title="Stock Portfolio Analyzer", page_icon="📊", layout="wide")
    data_dir = Path(
        os.environ.get("PORTFOLIO_DATA_DIR", "~/.stock-portfolio-analyzer")
    ).expanduser()
    try:
        with Repository(data_dir / "portfolio.sqlite3") as repo:
            draft, valid = _render(repo)
            if valid:
                _dashboard(draft)
    except (ValueError, sqlite3.Error, OSError) as exc:
        st.error(f"Local storage unavailable: {exc}")


def _dashboard(draft):
    snapshot = draft.snapshot()
    st.subheader("Portfolio analysis")
    symbols = sorted(h.symbol for h in snapshot.holdings)
    sectors = sorted({h.sector for h in snapshot.holdings})
    selected_symbols = st.multiselect("Symbols", symbols, default=symbols, key="symbols")
    selected_sectors = st.multiselect("Sectors", sectors, default=sectors, key="sectors")
    draft.selection = Selection(frozenset(selected_symbols), frozenset(selected_sectors))
    analysis = analyze(snapshot.holdings, draft.selection)
    st.caption("Selected holdings · Unrealized gain/loss based on supplied prices")
    values = [
        ("Cost basis", f"${analysis.cost_basis:,.2f}"),
        ("Market value", f"${analysis.market_value:,.2f}"),
        ("Unrealized gain / loss", f"${analysis.gain:,.2f}"),
        (
            "Unrealized gain / loss %",
            "N/A" if analysis.gain_percent is None else f"{analysis.gain_percent:.2f}%",
        ),
        ("Holding count", str(analysis.count)),
    ]
    for col, (label, value) in zip(st.columns(5), values):
        col.metric(label, value)
    st.download_button(
        "Download complete snapshot CSV",
        export_snapshot(snapshot),
        "complete-snapshot.csv",
        "text/csv",
    )
    st.download_button(
        "Download analysis report CSV",
        export_analysis(analysis, snapshot.metadata),
        "analysis-report.csv",
        "text/csv",
        disabled=analysis.count == 0,
    )
    st.caption(
        "Complete snapshot includes all draft holdings. Analysis report contains only the selected holdings and cannot be imported as a snapshot."
    )
    if not analysis.count:
        st.info("No holdings match these filters. Select symbols and sectors to analyze.")
        return
    table = []
    for r in analysis.holdings:
        table.append(
            {
                "Symbol": r.holding.symbol,
                "Company": r.holding.company_name,
                "Sector": r.holding.sector,
                "Quantity": str(r.holding.quantity),
                "Cost basis (USD)": float(r.holding.cost_basis),
                "Market value (USD)": float(r.market_value),
                "Unrealized gain/loss (USD)": float(r.gain),
                "Average cost (USD)": float(r.average_cost),
                "Gain/loss %": None if r.gain_percent is None else float(r.gain_percent),
            }
        )
    st.dataframe(
        pd.DataFrame(table),
        hide_index=True,
        width="stretch",
        column_config={
            k: st.column_config.NumberColumn(k, format="%.2f")
            for k in table[0]
            if "USD" in k or k == "Gain/loss %"
        },
    )
    st.caption("Blank percentage cells mean N/A (zero cost basis). Click a column header to sort.")
    if analysis.market_value:
        for col, values, title in zip(
            st.columns(2),
            [analysis.stock_allocations, analysis.sector_allocations],
            ["Stock allocation", "Sector allocation"],
        ):
            col.plotly_chart(allocation_chart(values, title), width="stretch")
    else:
        st.info("Allocation percentages are unavailable because selected market value is zero.")
    st.plotly_chart(gain_chart(analysis), width="stretch")
