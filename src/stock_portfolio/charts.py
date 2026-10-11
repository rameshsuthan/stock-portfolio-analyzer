"""Charts consume computed metrics; floats are presentation-only copies."""

import plotly.graph_objects as go


def allocation_chart(values, title):
    fig = go.Figure(
        go.Pie(
            labels=list(values),
            values=[float(v) for v in values.values()],
            hole=0.45,
            textinfo="label+percent",
            sort=False,
        )
    )
    fig.update_layout(title=title, margin=dict(t=50, b=20, l=20, r=20))
    return fig


def gain_chart(analysis):
    fig = go.Figure(
        go.Bar(
            x=[r.holding.symbol for r in analysis.holdings],
            y=[float(r.gain) for r in analysis.holdings],
            marker_color=["#14866d" if r.gain >= 0 else "#bc4655" for r in analysis.holdings],
        )
    )
    fig.update_layout(
        title="Unrealized gain / loss by holding",
        yaxis_title="USD",
        yaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor="#555"),
    )
    return fig
