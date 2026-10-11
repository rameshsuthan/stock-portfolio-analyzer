"""Local application shell; each workflow owns a view, never its own database setup."""

import os
import sqlite3
from datetime import date
from pathlib import Path

import streamlit as st

from .ledger.repository import LedgerRepository
from .storage import Repository
from .ui_state import dirty, guard_navigation, resolve_navigation
from .views import snapshots

PAGES = ("Overview", "Transactions", "Lots & realized gains", "Reconcile", "Data & recovery")


def main():
    st.set_page_config(page_title="Stock Portfolio Analyzer", page_icon="📊", layout="wide")
    st.html("""<style>
    [data-testid="stMetricValue"] {white-space: normal; overflow: visible;}
    [data-testid="stMetricValue"] p {white-space: normal; overflow-wrap: anywhere; font-size: clamp(1.3rem, 2.5vw, 2.25rem);}
    </style>""")
    data_dir = Path(
        os.environ.get("PORTFOLIO_DATA_DIR", "~/.stock-portfolio-analyzer")
    ).expanduser()
    try:
        with (
            LedgerRepository(data_dir / "portfolio.sqlite3") as ledger,
            Repository(data_dir / "portfolio.sqlite3") as snapshot_repo,
        ):
            state = st.session_state
            state.setdefault("context", ("Snapshots", None, "Overview"))
            state.setdefault("nav_mode", state["context"][0])
            accounts = ledger.load_dataset().accounts
            names = {a.id: a.name + (" (archived)" if a.archived else "") for a in accounts}
            with st.sidebar:
                mode = st.selectbox("Mode", ("Snapshots", "Transaction accounts"), key="nav_mode")
                if mode == "Transaction accounts":
                    account = st.selectbox(
                        "Account",
                        list(names),
                        format_func=names.get,
                        index=0 if names else None,
                        key="nav_account",
                    )
                    page = st.radio("Workspace", PAGES, key="nav_page")
                else:
                    account, page = None, "Overview"
            requested = (mode, account, page)
            st.title("Stock Portfolio Analyzer")
            st.caption("Local portfolios · USD · Prices supplied by you")
            notices = st.container()
            if guard_navigation(state["context"], requested, dirty()):
                state["context"] = requested
            elif requested != state["context"]:
                state["pending_navigation"] = requested
            with notices:
                if "receipt" in state:
                    st.success(state["receipt"])
                if "pending_navigation" in state:
                    st.warning(
                        "Unsaved draft. Discard explicitly to navigate, or keep editing in the current context."
                    )
                    st.button(
                        "Discard draft and navigate", on_click=resolve_navigation, args=(True,)
                    )
                    st.button("Keep editing", on_click=resolve_navigation, args=(False,))
            mode, account, page = state["context"]
            if mode == "Snapshots":
                snapshots.render(snapshot_repo, notices)
            else:
                as_of = st.date_input("Account as of", value=date.today(), key="ledger_as_of")
                st.caption(
                    f"{names.get(account, 'Choose or create an account')} · {as_of} · {page} · {'Draft pending' if dirty() else 'Saved data'}"
                )
                st.info(
                    "Transaction account workspace. Account setup and entry follow in the next implementation task."
                )
    except (ValueError, sqlite3.Error, OSError) as exc:
        st.error(f"Local operation unavailable; inputs preserved. {exc}")
