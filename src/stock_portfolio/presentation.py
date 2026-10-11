"""Safe native tables and display-only rounding. Exact values remain in exports."""

from decimal import Decimal

import pandas as pd
import streamlit as st


def money(value):
    return "Unknown" if value is None else f"${value:,.2f}"


def exact(value):
    return (
        "Unknown"
        if value is None
        else format(value, "f")
        if isinstance(value, Decimal)
        else str(value)
    )


def table(rows, *, height=420):
    if not rows:
        st.info("No records in this selection.")
        return
    frame = pd.DataFrame([{"#": i, **row} for i, row in enumerate(rows, 1)])
    st.dataframe(
        frame,
        hide_index=True,
        width="stretch",
        height=height,
        column_config={
            "#": st.column_config.NumberColumn("#", pinned=True, width="small"),
            "Symbol": st.column_config.TextColumn("Symbol", pinned=True),
        },
    )
