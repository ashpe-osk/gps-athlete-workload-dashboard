"""
charts.py
---------
Plotly figure builders. They take data and return a figure; they know nothing about Streamlit.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import metrics as m
from .quality import STATUS_LEVELS
from .theme import BRAND, colors_for

ACCENT = BRAND


def _style(fig: go.Figure, title: str, y_label: str, theme: str = "Light") -> go.Figure:
    colors = colors_for(theme)
    fig.update_layout(
        template="plotly_dark" if theme == "Dark" else "plotly_white",
        title=dict(text=title, font=dict(size=16, color=colors["text"])),
        height=360, margin=dict(l=18, r=18, t=58, b=58),
        paper_bgcolor=colors["surface"], plot_bgcolor=colors["surface"],
        font=dict(family="Arial, sans-serif", color=colors["text"], size=12),
        legend=dict(
            orientation="h",
            x=0,
            y=-0.28,
            title=None,
            font=dict(color=colors["text"], size=11),
        ),
        yaxis_title=y_label, xaxis_title=None,
    )
    fig.update_xaxes(
        showgrid=False, linecolor=colors["border"], tickfont=dict(color=colors["muted"])
    )
    fig.update_yaxes(
        gridcolor=colors["grid"], zerolinecolor=colors["border"],
        tickfont=dict(color=colors["muted"]),
    )
    return fig


def trend_chart(athlete_df, column: str, title: str, y_label: str,
                decimals: int = 1, show_rolling: bool = True,
                theme: str = "Light", show_labels: bool = False,
                show_reference_band: bool = True) -> go.Figure:
    """One metric across matches.
    - Line breaks where a value is missing (it is never drawn as zero).
    - Diamonds mark sessions whose minutes are approximate.
    - Dashed line = rolling average of the last 3 valid sessions."""
    values = athlete_df[column].astype(float)
    colors = colors_for(theme)
    symbols = ["diamond" if est else "circle" for est in athlete_df["minutes_estimated"]]
    minutes = [f"~{int(v)}" if est else f"{int(v)}"
               for v, est in zip(athlete_df["minutes_played"], athlete_df["minutes_estimated"])]
    custom = np.column_stack([athlete_df["opponent"], athlete_df["home_away"], minutes])

    fig = go.Figure()
    valid = values.dropna().astype(float)
    if len(valid) >= m.MIN_SESSIONS_FOR_REFERENCE_BAND:
        mean = float(valid.mean())
        sd = float(valid.std(ddof=1))
        date_start = athlete_df["match_date"].min()
        date_end = athlete_df["match_date"].max()
        if show_reference_band and sd > 0:
            fig.add_trace(go.Scatter(
                x=[date_start, date_end, date_end, date_start],
                y=[mean - sd, mean - sd, mean + sd, mean + sd],
                mode="lines",
                fill="toself",
                fillcolor=colors["rolling"],
                opacity=0.10,
                line=dict(width=0),
                name="Descriptive mean ± 1 SD",
                legendrank=4,
                hoverinfo="skip",
            ))
        fig.add_trace(go.Scatter(
            x=[date_start, date_end],
            y=[mean, mean],
            mode="lines",
            name="Historical mean",
            legendrank=3,
            line=dict(color=colors["rolling"], width=1.5, dash="dot"),
            hovertemplate=f"Historical mean: %{{y:.{decimals}f}}<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=athlete_df["match_date"], y=values,
        mode="lines+markers" + ("+text" if show_labels else ""),
        text=[f"{value:.{decimals}f}" if pd.notna(value) else "" for value in values],
        textposition="top center",
        name="Session values",
        legendrank=1,
        connectgaps=False,         line=dict(color=colors["chart_accent"], width=2),
        marker=dict(size=10, symbol=symbols, line=dict(width=1.5, color="white")),
        customdata=custom,
        hovertemplate=("%{x|%d %b %Y}<br>vs %{customdata[0]} (%{customdata[1]})<br>"
                       f"%{{y:.{decimals}f}}<br>Minutes: %{{customdata[2]}}<extra></extra>"),
    ))
    if show_rolling:
        rolled = m.rolling_mean(athlete_df[column])
        if rolled.notna().any():
            fig.add_trace(go.Scatter(
                x=athlete_df["match_date"], y=rolled, mode="lines",
                name="Rolling average (3 sessions)",
                legendrank=2,
                connectgaps=True, line=dict(color=colors["rolling"], width=2, dash="dash"),
                hovertemplate=f"Rolling avg: %{{y:.{decimals}f}}<extra></extra>",
            ))
    changes = m.pct_change_vs_previous(values)
    latest_positions = np.flatnonzero(values.notna().to_numpy())
    if len(latest_positions) >= 2:
        latest_idx = int(latest_positions[-1])
        change = changes.iloc[latest_idx]
        if pd.notna(change):
            fig.add_annotation(
                x=athlete_df["match_date"].iloc[latest_idx],
                y=values.iloc[latest_idx],
                text=f"{change:+.1f}% vs previous",
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=-35,
                bgcolor=colors["surface"],
                bordercolor=colors["border"],
                font=dict(color=colors["text"]),
            )
    return _style(fig, title, y_label, theme)


def match_intensity_scatter(athlete_df: pd.DataFrame, theme: str = "Light") -> go.Figure:
    """Relate minutes to distance rate while retaining opponent context."""
    colors_for_theme = colors_for(theme)
    data = athlete_df.dropna(subset=["minutes_played", "distance_per_min"]).copy()
    colors = {
        "top": colors_for_theme["series"][1],
        "middle": colors_for_theme["series"][2],
        "bottom": colors_for_theme["chart_accent"],
    }
    fig = go.Figure()
    for band in ("top", "middle", "bottom"):
        group = data[data["opponent_table_band"] == band]
        if group.empty:
            continue
        minutes = [
            f"~{int(value)}" if estimated else f"{int(value)}"
            for value, estimated in zip(group["minutes_played"], group["minutes_estimated"])
        ]
        custom = np.column_stack([
            group["match_date"].dt.strftime("%d %b %Y"),
            group["opponent"],
            minutes,
            [
                f"{int(value)} m" if pd.notna(value) else "Not recorded"
                for value in group["hsr_distance_m"]
            ],
        ])
        fig.add_trace(go.Scatter(
            x=group["minutes_played"],
            y=group["distance_per_min"],
            mode="markers",
            name=f"{band.title()} opponent band",
            customdata=custom,
            marker=dict(
                color=colors[band],
                size=11,
                symbol=["diamond" if flag else "circle" for flag in group["minutes_estimated"]],
                line=dict(color="white", width=1.5),
            ),
            hovertemplate=(
                "%{customdata[0]} vs %{customdata[1]}<br>"
                "Minutes: %{customdata[2]}<br>"
                "Distance rate: %{y:.1f} m/min<br>"
                "HSR: %{customdata[3]}<extra></extra>"
            ),
        ))
    fig.update_xaxes(title_text="Minutes played", rangemode="tozero")
    fig.update_yaxes(title_text="Distance per minute (m/min)")
    return _style(
        fig, "Match intensity · minutes vs distance rate",
        "Distance per minute (m/min)", theme,
    )


def workload_composition_chart(athlete_df: pd.DataFrame, theme: str = "Light") -> go.Figure:
    """Stack total distance into high-speed and remaining distance by session."""
    colors = colors_for(theme)
    data = athlete_df.dropna(subset=["total_distance_km", "hsr_distance_m"]).copy()
    data = data[data["hsr_distance_m"] <= data["total_distance_km"] * 1000]
    data["high_speed_km"] = data["hsr_distance_m"].astype(float) / 1000
    data["other_distance_km"] = (data["total_distance_km"] - data["high_speed_km"]).clip(lower=0)
    labels = data["match_date"].dt.strftime("%d %b")
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=labels, y=data["other_distance_km"], name="Other distance",
        marker_color=colors["neutral_bar"], customdata=data["opponent"],
        hovertemplate="%{x} vs %{customdata}<br>Other: %{y:.2f} km<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=labels, y=data["high_speed_km"], name="High-speed running",
        marker_color=colors["chart_accent"], customdata=data["opponent"],
        hovertemplate="%{x} vs %{customdata}<br>HSR: %{y:.2f} km<extra></extra>",
    ))
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title_text="Distance (km)")
    fig.update_xaxes(title_text="Match date")
    return _style(fig, "Distance composition by match", "Distance (km)", theme)


def consistency_heatmap(athlete_df: pd.DataFrame, theme: str = "Light") -> go.Figure:
    """Show within-athlete standardized workload variation across valid sessions."""
    columns = [
        ("total_distance_km_per90", "Distance / 90"),
        ("hsr_distance_m_per90", "HSR / 90"),
        ("sprint_count_per90", "Sprints / 90"),
        ("accel_count_per90", "Accelerations / 90"),
        ("decel_count_per90", "Decelerations / 90"),
        ("player_load_au_per90", "Player Load / 90"),
    ]
    valid_columns = [(column, label) for column, label in columns if column in athlete_df]
    dates = athlete_df["match_date"].dt.strftime("%d %b %Y")
    colors = colors_for(theme)
    z_values = []
    hover_values = []
    for column, _ in valid_columns:
        values = pd.to_numeric(athlete_df[column], errors="coerce")
        sd = values.std()
        z_values.append((values - values.mean()) / sd if pd.notna(sd) and sd > 0 else values * 0)
        hover_values.append(values.to_numpy())
    z_matrix = np.column_stack([values.to_numpy() for values in z_values])
    value_matrix = np.column_stack(hover_values)
    fig = go.Figure(go.Heatmap(
        z=z_matrix,
        x=[label for _, label in valid_columns],
        y=dates,
        customdata=value_matrix,
        colorscale=[[0, colors["series"][1]], [0.5, colors["heatmap_mid"]],
                    [1, colors["chart_accent"]]],
        zmin=-2,
        zmax=2,
        zmid=0,
        colorbar=dict(title="Within-athlete<br>SD", thickness=12),
        hovertemplate="%{y}<br>%{x}: %{customdata:.2f}<br>Deviation: %{z:.2f} SD<extra></extra>",
    ))
    fig.update_layout(height=max(340, min(520, 28 * len(athlete_df) + 110)))
    fig.update_yaxes(autorange="reversed", title_text="Match")
    return _style(fig, "Workload pattern · standardized per 90", "", theme)


def comparison_radar_chart(comparison: pd.DataFrame, theme: str = "Light") -> go.Figure:
    """Compare selected athletes by cohort-relative percentile, not mixed raw units."""
    metrics = [
        ("distance_per_min", "Distance / min"),
        ("hsr_m_per90", "HSR / 90"),
        ("sprints_per90", "Sprints / 90"),
        ("accels_per90", "Accelerations / 90"),
        ("decels_per90", "Decelerations / 90"),
        ("player_load_per90", "Player Load / 90"),
    ]
    colors = colors_for(theme)
    labels = [label for column, label in metrics if column in comparison]
    fig = go.Figure()
    for idx, row in comparison.reset_index(drop=True).iterrows():
        scores = []
        for column, _ in metrics:
            values = pd.to_numeric(comparison[column], errors="coerce")
            value = row[column]
            if pd.isna(value):
                scores.append(None)
            elif values.dropna().nunique() <= 1:
                scores.append(50.0)
            else:
                scores.append(float(values.rank(pct=True, method="average").loc[row.name] * 100))
        closed_scores = scores + [scores[0]]
        fig.add_trace(go.Scatterpolar(
            r=closed_scores,
            theta=labels + [labels[0]],
            fill="toself",
            name=row["athlete_name"],
            line=dict(color=colors["series"][idx % len(colors["series"])], width=2),
            opacity=0.72,
            hovertemplate="%{theta}: %{r:.0f}th percentile<extra>%{fullData.name}</extra>",
        ))
    fig.update_layout(
        polar=dict(
            bgcolor=colors["surface"],
            radialaxis=dict(visible=True, range=[0, 100], tickvals=[25, 50, 75, 100],
                            gridcolor=colors["grid"], tickfont=dict(color=colors["muted"])),
            angularaxis=dict(gridcolor=colors["grid"], tickfont=dict(color=colors["text"])),
        ),
        showlegend=True,
    )
    return _style(fig, "Workload profile · cohort percentiles", "", theme)


def comparison_box_chart(
    sessions: pd.DataFrame,
    athlete_ids: list[str],
    column: str,
    title: str,
    y_label: str,
    theme: str = "Light",
) -> go.Figure:
    """Show session-level distribution for a selected metric, preserving outliers."""
    data = m.add_per90_columns(m.usable_sessions(sessions))
    data = data[data["athlete_id"].isin(athlete_ids)]
    colors = colors_for(theme)
    fig = go.Figure()
    for idx, (athlete_id, group) in enumerate(data.groupby("athlete_id", sort=False)):
        values = pd.to_numeric(group[column], errors="coerce")
        valid = values.notna()
        fig.add_trace(go.Box(
            y=values[valid],
            name=str(group["athlete_name"].iloc[0]),
            boxpoints="all",
            jitter=0.25,
            pointpos=0,
            marker=dict(color=colors["series"][idx % len(colors["series"])], size=6),
            line=dict(color=colors["series"][idx % len(colors["series"])]),
            customdata=np.column_stack([
                group.loc[valid, "match_date"].dt.strftime("%d %b %Y"),
                group.loc[valid, "opponent"],
            ]),
            hovertemplate="%{customdata[0]} vs %{customdata[1]}<br>%{y:.2f}<extra>%{fullData.name}</extra>",
        ))
    fig.update_layout(showlegend=False, boxmode="group")
    return _style(fig, title, y_label, theme)


def comparison_bubble_chart(comparison: pd.DataFrame, theme: str = "Light") -> go.Figure:
    """Relate distance rate and sprint rate; bubble size reflects Player Load / 90."""
    fig = go.Figure()
    valid = comparison.dropna(subset=["distance_per_min", "sprints_per90", "player_load_per90"])
    positions = valid.groupby("position", sort=False)
    max_load = float(valid["player_load_per90"].max()) if not valid.empty else 0
    size_ref = 2 * max_load / (38 ** 2) if max_load > 0 else 1
    colors = colors_for(theme)
    for idx, (position, group) in enumerate(positions):
        fig.add_trace(go.Scatter(
            x=group["distance_per_min"],
            y=group["sprints_per90"],
            mode="markers+text",
            name=position,
            text=group["athlete_name"],
            textposition="top center",
            marker=dict(
                size=group["player_load_per90"],
                sizemode="area",
                sizeref=size_ref,
                sizemin=10,
                color=colors["series"][idx % len(colors["series"])],
                opacity=0.78,
                line=dict(color="white", width=1.5),
            ),
            customdata=np.column_stack([group["position"], group["sessions"], group["player_load_per90"]]),
            hovertemplate=(
                "%{text}<br>%{customdata[0]}<br>Distance: %{x:.1f} m/min"
                "<br>Sprints: %{y:.1f} / 90<br>Sessions: %{customdata[1]}"
                "<br>Player Load: %{customdata[2]:.1f} / 90<extra></extra>"
            ),
        ))
    fig.update_xaxes(title_text="Distance per minute (m/min)")
    fig.update_yaxes(title_text="Sprints per 90")
    return _style(
        fig, "Rate profile · bubble size = Player Load / 90",
        "Sprints per 90", theme,
    )


def quality_map_chart(sessions: pd.DataFrame, theme: str = "Light") -> go.Figure:
    """Map each athlete's session status across the match schedule."""
    data = sessions.copy()
    data["match_date"] = pd.to_datetime(data["match_date"])
    data["status_level"] = data["quality_status"].map(STATUS_LEVELS).fillna(3).astype(int)
    data = data.sort_values(["match_date", "match_id", "athlete_name"])
    match_ids = data.drop_duplicates("match_id")["match_id"].tolist()
    dates = data.drop_duplicates("match_id").set_index("match_id")["match_date"]
    x_labels = [
        f"{dates[mid]:%d %b}<br>{mid.split('-')[1]} {mid.rsplit('-', 1)[-1]}"
        for mid in match_ids
    ]
    athlete_names = sorted(data["athlete_name"].unique())
    z = np.full((len(athlete_names), len(match_ids)), np.nan)
    custom = np.full((len(athlete_names), len(match_ids)), "", dtype=object)
    y_index = {name: idx for idx, name in enumerate(athlete_names)}
    x_index = {match_id: idx for idx, match_id in enumerate(match_ids)}
    for row in data.itertuples():
        yi, xi = y_index[row.athlete_name], x_index[row.match_id]
        z[yi, xi] = row.status_level
        custom[yi, xi] = row.quality_status.replace("_", " ")
    colors = colors_for(theme)
    ramp = colors["quality"]
    colorscale = [
        [0.00, ramp[0]], [0.24, ramp[0]],
        [0.25, ramp[1]], [0.49, ramp[1]],
        [0.50, ramp[2]], [0.74, ramp[2]],
        [0.75, ramp[3]], [0.99, ramp[3]],
        [1.00, ramp[4]],
    ]
    fig = go.Figure(go.Heatmap(
        z=z,
        x=x_labels,
        y=athlete_names,
        customdata=custom,
        zmin=0,
        zmax=4,
        colorscale=colorscale,
        colorbar=dict(
            title="Session status",
            tickvals=[0, 1, 2, 3, 4],
            ticktext=["Complete", "Approx. min", "Missing", "Invalid", "Dropout"],
            thickness=12,
        ),
        hovertemplate="%{y}<br>%{x}<br>Status: %{customdata}<extra></extra>",
        xgap=2,
        ygap=2,
    ))
    fig.update_layout(height=max(320, min(460, 45 * len(athlete_names) + 120)))
    fig.update_yaxes(autorange="reversed", title_text=None)
    return _style(fig, "Session quality map · schedule by athlete", "", theme)
