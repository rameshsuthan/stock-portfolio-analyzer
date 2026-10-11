"""Charts consume computed metrics; floats are presentation-only copies."""

from decimal import Decimal, localcontext

import plotly.graph_objects as go


def allocation_chart(values, title):
    items = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    if len(items) > 10:
        with localcontext() as ctx:
            ctx.prec = 50
            remainder = sum((value for _, value in items[10:]), Decimal(0))
        items = items[:10] + [("Other holdings", remainder)]
    fig = go.Figure(
        go.Pie(
            labels=[label for label, _ in items],
            values=[float(value) for _, value in items],
            hole=0.55,
            textinfo="text",
            text=[f"{label}<br>{value:.2f}%" for label, value in items],
            textposition="none",
            hovertemplate="%{label}: %{value:.2f}%<extra></extra>",
            sort=False,
        )
    )
    fig.update_layout(title=title, height=440, margin={"t": 50, "b": 20, "l": 20, "r": 20})
    return fig


def sector_chart(values):
    items = sorted(values.items(), key=lambda item: (-item[1], item[0]))
    fig = go.Figure(
        go.Bar(
            y=[label for label, _ in items],
            x=[float(value) for _, value in items],
            orientation="h",
            texttemplate="%{x:.2f}%",
            textposition="auto",
            hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
            marker_color="#4976b8",
        )
    )
    fig.update_layout(
        title="Sector allocation",
        height=max(360, 32 * len(items) + 100),
        yaxis={"autorange": "reversed", "automargin": True},
        xaxis_title="Share of selected market value (%)",
        margin={"t": 50, "b": 50, "l": 20, "r": 20},
    )
    return fig


def gain_chart(analysis, losses=False):
    rows = sorted(
        (r for r in analysis.holdings if (r.gain < 0 if losses else r.gain > 0)),
        key=lambda r: (r.gain if losses else -r.gain, r.holding.symbol),
    )[:10]
    fig = go.Figure(
        go.Bar(
            y=[r.holding.symbol for r in rows],
            x=[float(r.gain) for r in rows],
            orientation="h",
            marker_color="#bc4655" if losses else "#14866d",
            hovertemplate="%{y}: $%{x:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Largest unrealized losses" if losses else "Largest unrealized gains",
        height=max(280, len(rows) * 32 + 100),
        xaxis_title="USD",
        yaxis={"autorange": "reversed", "automargin": True},
        xaxis={"zeroline": True, "zerolinewidth": 2, "zerolinecolor": "#555"},
        margin={"t": 50, "b": 50, "l": 20, "r": 20},
    )
    if not rows:
        fig.add_annotation(
            text="No losses in selection" if losses else "No gains in selection",
            showarrow=False,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
        )
    return fig
