"""
Render validated ChartSpec + DataFrame → Plotly figures (Bar / Line / Pie).
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.dashboard.chart_specs import ChartSpec


def render_chart(spec: ChartSpec, df: pd.DataFrame) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data in this date range.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14),
        )
        fig.update_layout(title=spec.title, height=360)
        return fig

    cat = spec.category_key or df.columns[0]
    val = spec.value_key or df.columns[1]

    if spec.kind == "line":
        fig = px.line(
            df,
            x=cat,
            y=val,
            markers=True,
            title=spec.title,
            labels={cat: spec.x_label or cat, val: spec.y_label or val},
        )
    elif spec.kind == "bar":
        fig = px.bar(
            df,
            x=cat,
            y=val,
            title=spec.title,
            labels={cat: spec.x_label or cat, val: spec.y_label or val},
        )
        fig.update_layout(xaxis_tickangle=-35)
    elif spec.kind == "pie":
        fig = px.pie(
            df,
            names=cat,
            values=val,
            title=spec.title,
            hole=0.25,
        )
    else:
        raise ValueError(f"Unsupported chart kind: {spec.kind}")

    fig.update_layout(height=400, margin=dict(t=50, b=80, l=60, r=40))
    return fig


def figures_for_dashboard(
    specs: list[ChartSpec],
    data: dict[str, pd.DataFrame],
) -> dict[str, go.Figure]:
    out: dict[str, go.Figure] = {}
    for spec in specs:
        df = data.get(spec.chart_id, pd.DataFrame())
        out[spec.chart_id] = render_chart(spec, df)
    return out
