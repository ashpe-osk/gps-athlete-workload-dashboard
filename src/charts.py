"""
charts.py
---------
Plotly figure builders. They take data and return a figure; they know nothing about Streamlit.
"""
import numpy as np
import plotly.graph_objects as go

import metrics as m

ACCENT = "#2EC4B6"
ROLLING = "#FFB703"


def _style(fig: go.Figure, title: str, y_label: str) -> go.Figure:
    fig.update_layout(
        template="plotly_dark", title=dict(text=title, font=dict(size=16)),
        height=340, margin=dict(l=10, r=10, t=50, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.2), yaxis_title=y_label, xaxis_title=None,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(255,255,255,0.08)")
    return fig


def trend_chart(athlete_df, column: str, title: str, y_label: str,
                decimals: int = 1, show_rolling: bool = True) -> go.Figure:
    """One metric across matches.
    - Line breaks where a value is missing (it is never drawn as zero).
    - Diamonds mark sessions whose minutes are approximate.
    - Dashed line = rolling average of the last 3 valid sessions."""
    values = athlete_df[column].astype(float)
    symbols = ["diamond" if est else "circle" for est in athlete_df["minutes_estimated"]]
    minutes = [f"~{int(v)}" if est else f"{int(v)}"
               for v, est in zip(athlete_df["minutes_played"], athlete_df["minutes_estimated"])]
    custom = np.column_stack([athlete_df["opponent"], athlete_df["home_away"], minutes])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=athlete_df["match_date"], y=values, mode="lines+markers", name="Match value",
        connectgaps=False, line=dict(color=ACCENT, width=2),
        marker=dict(size=10, symbol=symbols, line=dict(width=1, color="white")),
        customdata=custom,
        hovertemplate=("%{x|%d %b %Y}<br>vs %{customdata[0]} (%{customdata[1]})<br>"
                       f"%{{y:.{decimals}f}}<br>Minutes: %{{customdata[2]}}<extra></extra>"),
    ))
    if show_rolling:
        rolled = m.rolling_mean(athlete_df[column])
        if rolled.notna().any():
            fig.add_trace(go.Scatter(
                x=athlete_df["match_date"], y=rolled, mode="lines", name="Rolling avg (3 sessions)",
                connectgaps=True, line=dict(color=ROLLING, width=2, dash="dash"),
                hovertemplate=f"Rolling avg: %{{y:.{decimals}f}}<extra></extra>",
            ))
    return _style(fig, title, y_label)
