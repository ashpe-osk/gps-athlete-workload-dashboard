"""
app.py
------
Streamlit interface ONLY. All calculations live in src/metrics.py.
Run from the project root:   streamlit run app/app.py
"""
import importlib
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit adds the app directory to sys.path; add the repository root for package imports.
ROOT = Path(__file__).resolve().parents[1]
root_path = str(ROOT)
if root_path in sys.path:
    sys.path.remove(root_path)
sys.path.insert(0, root_path)

from src import charts, metrics as m, quality, theme as theme_module  # noqa: E402
from src import formatting as formatting_module  # noqa: E402
from src.cleaning import clean_pipeline  # noqa: E402
from src import report as report_builder  # noqa: E402
from src import pdf_report as pdf_report_builder  # noqa: E402

# Streamlit keeps imported modules in sys.modules across reruns.
theme_module = importlib.reload(theme_module)
charts = importlib.reload(charts)
m = importlib.reload(m)
formatting_module = importlib.reload(formatting_module)
classify_change = formatting_module.classify_change
format_metric = formatting_module.format_metric
format_percent = formatting_module.format_percent
report_builder = importlib.reload(report_builder)
pdf_report_builder = importlib.reload(pdf_report_builder)
app_css = theme_module.app_css

st.set_page_config(
    page_title="GPS Workload Dashboard (Synthetic Demo)",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

def fmt(column: str, value) -> str:
    """Keep the original app helper while sharing its formatting implementation."""
    return format_metric(column, value)


def fmt_pct(value) -> str | None:
    return format_percent(value)


@st.cache_data
def load_clean():
    clean_df, issues_df = clean_pipeline()
    return clean_df, issues_df


clean_df, issues_df = load_clean()

display_theme = st.sidebar.radio(
    "Display theme",
    options=["Light", "Dark"],
    horizontal=True,
    key="display_theme",
)

# ------------------------------------------------------------------ header
st.markdown(
    f"""
    <style>{app_css(display_theme)}</style>
    <div class="brand-hero">
      <div class="brand-kicker">Performance intelligence · synthetic prototype</div>
      <div class="brand-title" role="heading" aria-level="1">GPS Workload Intelligence</div>
      <p>Match analytics · athlete workload · data integrity</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.warning(
    "**SYNTHETIC DEMO DATA.** Club names are public league context only. All athletes, fixtures, dates and "
    "GPS values are fictional."
)

# ------------------------------------------------------------------ sidebar
athletes = clean_df[["athlete_id", "athlete_name", "position", "club"]].drop_duplicates().sort_values("athlete_id")
labels = {r.athlete_id: f"{r.athlete_name} ({r.position})" for r in athletes.itertuples()}
with st.sidebar.container(border=True, key="player-selection-card"):
    st.markdown("#### Player selection")
    selected_id = st.selectbox("Athlete", options=list(labels), format_func=labels.get)
    st.caption("Sessions flagged as possible sensor dropout are excluded from trends and averages.")

athlete_all = clean_df[clean_df["athlete_id"] == selected_id].sort_values("match_date").reset_index(drop=True)
athlete_use = m.add_per90_columns(m.usable_sessions(athlete_all))
athlete_info = athlete_all.iloc[0]
n_excluded = len(athlete_all) - len(athlete_use)

if athlete_use.empty:
    st.info("This athlete has no usable sessions yet.")
    st.stop()

range_min = athlete_use["match_date"].min().date()
range_max = athlete_use["match_date"].max().date()
with st.sidebar.container(border=True, key="date-range-card"):
    st.markdown("#### Analysis date range")
    date_range = st.date_input(
        "Dates",
        value=(range_min, range_max),
        min_value=range_min,
        max_value=range_max,
        key="analysis_date_range",
    )

if isinstance(date_range, tuple) and len(date_range) == 2:
    range_start, range_end = date_range
else:
    range_start, range_end = range_min, range_max
athlete_range = m.filter_sessions_by_date(athlete_use, range_start, range_end)

tabs = st.tabs(["Overview", "Athlete Profile", "Match Analysis", "Performance Trends",
                "Workload & Consistency", "Comparison", "Report", "Data Quality"])

# ------------------------------------------------------------------ A. Overview
with tabs[0]:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Athletes", clean_df["athlete_id"].nunique())
    c2.metric("Recorded matches", clean_df["match_id"].nunique())
    c3.metric("Total sessions", len(clean_df))
    c4.metric("Usable sessions", int(clean_df["use_in_analysis"].sum()),
              help="Sessions that passed the data-quality screen.")
    latest = athlete_use.iloc[-1]
    est = " (minutes approximate)" if latest["minutes_estimated"] else ""
    st.subheader(f"Latest recorded performance: {athlete_info['athlete_name']}")
    st.caption(f"{latest['match_date']:%d %b %Y} vs {latest['opponent']} ({latest['home_away']}) · "
               f"{int(latest['minutes_played'])} min{est}. Arrows show change vs the previous session with a value.")

    kpis = ["total_distance_km", "distance_per_min", "hsr_distance_m", "sprint_count", "player_load_au", "top_speed_kmh"]
    cols = st.columns(3)
    for i, column in enumerate(kpis):
        change = m.pct_change_vs_previous(athlete_use[column]).iloc[-1]
        cols[i % 3].metric(m.METRIC_INFO[column][0], fmt(column, latest[column]),
                           delta=fmt_pct(change), delta_color="off")

    st.subheader("Latest session for every athlete")
    latest_rows = m.usable_sessions(clean_df).groupby("athlete_id").tail(1)
    st.dataframe(pd.DataFrame({
        "Athlete": latest_rows["athlete_name"], "Position": latest_rows["position"],
        "Date": latest_rows["match_date"].dt.strftime("%d %b %Y"), "Opponent": latest_rows["opponent"],
        "Minutes": latest_rows["minutes_played"], "Distance (km)": latest_rows["total_distance_km"],
        "Sprints": latest_rows["sprint_count"], "Player Load (AU)": latest_rows["player_load_au"],
    }), hide_index=True, width="stretch")

# ------------------------------------------------------------------ B. Athlete Profile
with tabs[1]:
    st.subheader(athlete_info["athlete_name"])
    p1, p2, p3 = st.columns(3)
    p1.metric("Position", athlete_info["position"])
    p2.metric("Club", athlete_info["club"])
    p3.metric("Athlete ID", athlete_info["athlete_id"])

    st.markdown("#### Combined statistics")
    stats = m.combined_stats(athlete_use)
    st.dataframe(pd.DataFrame({
        "Metric": stats["metric"],
        "Value": [fmt(c, v) for c, v in zip(stats["column"], stats["value"])],
        "How it is combined": stats["method"],
        "Sessions with data": [f"{a} of {b}" for a, b in zip(stats["n_valid"], stats["n_sessions"])],
    }), hide_index=True, width="stretch")
    pooled = stats.set_index("column").loc["distance_per_min", "value"]
    st.caption(f"Distance per minute is total distance ÷ total minutes ({pooled:.1f} m/min). "
               f"The simple average of match rates is {m.mean_of_match_rates(athlete_use):.1f} m/min; "
               "the two differ when minutes vary between matches.")
    n_est = int(athlete_use["minutes_estimated"].sum())
    if n_est:
        st.caption(f"{n_est} of {len(athlete_use)} sessions use approximate minutes (marked ~).")

    st.markdown("#### Match history")
    minutes_text = [f"~{int(v)}" if e else f"{int(v)}"
                    for v, e in zip(athlete_all["minutes_played"], athlete_all["minutes_estimated"])]
    st.dataframe(pd.DataFrame({
        "Date": athlete_all["match_date"].dt.strftime("%d %b %Y"), "Opponent": athlete_all["opponent"],
        "H/A": athlete_all["home_away"], "Minutes": minutes_text,
        "Distance (km)": athlete_all["total_distance_km"], "m/min": athlete_all["distance_per_min"],
        "HSR (m)": athlete_all["hsr_distance_m"], "Sprints": athlete_all["sprint_count"],
        "Player Load": athlete_all["player_load_au"], "Data status": athlete_all["quality_status"],
    }), hide_index=True, width="stretch")

# ------------------------------------------------------------------ C. Match Analysis
with tabs[2]:
    options = athlete_all.sort_values("match_date", ascending=False)
    names = {r.match_id: f"{r.match_date:%d %b %Y} vs {r.opponent} ({r.home_away})"
                         + (" ⚠" if r.possible_dropout else "") for r in options.itertuples()}
    match_id = st.selectbox("Select a match", options=list(names), format_func=names.get)
    row = athlete_all[athlete_all["match_id"] == match_id].iloc[0]
    st.caption(f"{row['competition']} · {row['club']} vs {row['opponent']}")

    history = None
    if row["possible_dropout"]:
        st.warning("This session is flagged as a possible sensor dropout (distance far below this athlete's "
                   "usual level). Values are shown for transparency but are excluded from history comparisons.")
    else:
        history = m.match_vs_history(clean_df, selected_id, match_id).set_index("column")
    if row["minutes_estimated"]:
        st.info("Minutes for this session are approximate, so per-minute values are approximate too.")

    cols = st.columns(3)
    for i, column in enumerate(m.METRIC_INFO):
        label = m.METRIC_INFO[column][0]
        delta, help_text = None, None
        if history is not None:
            h = history.loc[column]
            if h["status"] == "ok":
                delta = fmt_pct(h["pct_diff"])
                help_text = f"Compared with the average of {h['prior_n']} earlier sessions."
            elif h["status"] == "insufficient history":
                help_text = f"Only {h['prior_n']} earlier sessions: not enough for a comparison."
        cols[i % 3].metric(label, fmt(column, row[column]), delta=delta, delta_color="off", help=help_text)

    if history is not None:
        with st.expander("Adjusted for minutes played (per 90)"):
            per90 = history[history.index.str.endswith("_per90")].reset_index()
            st.dataframe(pd.DataFrame({
                "Metric": [m.METRIC_INFO[c.replace("_per90", "")][0] for c in per90["column"]],
                "This match (per 90)": per90["current"].round(1),
                "Own earlier average (per 90)": per90["prior_mean"].round(1),
                "Difference": [fmt_pct(v) or "—" for v in per90["pct_diff"]],
                "Earlier sessions": per90["prior_n"],
            }), hide_index=True, width="stretch")
            st.caption("Per-90 values exist only for sessions of at least 45 minutes.")

        with st.expander("Historical baseline for this session"):
            baseline = m.historical_baseline_table(
                athlete_use,
                match_id=match_id,
            )
            baseline_display = pd.DataFrame({
                "Metric": [m.METRIC_INFO[c][0] for c in baseline["column"]],
                "This session": [fmt(c, v) for c, v in zip(baseline["column"], baseline["latest"])],
                "Previous valid": [fmt(c, v) for c, v in zip(baseline["column"], baseline["previous"])],
                "Historical mean": [fmt(c, v) for c, v in zip(baseline["column"], baseline["historical_mean"])],
                "Historical median": [fmt(c, v) for c, v in zip(baseline["column"], baseline["historical_median"])],
                "vs previous": [fmt_pct(v) or "—" for v in baseline["pct_previous"]],
                "vs baseline": [fmt_pct(v) or "—" for v in baseline["pct_baseline"]],
                "Baseline sessions": baseline["baseline_n"],
            })
            st.dataframe(baseline_display, hide_index=True, width="stretch")
            st.caption(
                "Baseline statistics use earlier analysis-eligible sessions only and exclude the session being evaluated. "
                "Missing values remain missing; each baseline row reports the number of valid contributing sessions."
            )

# ------------------------------------------------------------------ D. Performance Trends
with tabs[3]:
    t1, t2, t3 = st.columns(3)
    per90_on = t1.checkbox("Adjust volume metrics to per 90 minutes", value=False,
                           help="Removes the effect of playing fewer minutes. Sessions under 45 min are left out.")
    rolling_on = t2.checkbox("Show rolling average (3 sessions)", value=True)
    labels_on = t3.checkbox("Show data labels", value=False)

    trend_columns = [
        "total_distance_km", "hsr_distance_m", "sprint_count",
        "player_load_au", "distance_per_min", "accel_count", "decel_count",
    ]
    grid = st.columns(2)
    if athlete_range.empty:
        st.info("No analysis-eligible sessions fall within the selected date range.")
    else:
        for i, column in enumerate(trend_columns):
            use_column = f"{column}_per90" if per90_on and column in m.VOLUME_COLUMNS else column
            label, _, unit = m.METRIC_INFO[column]
            suffix = " per 90" if use_column != column else ""
            decimals = 2 if column == "total_distance_km" else 1 if column in ("distance_per_min", "player_load_au") else 0
            fig = charts.trend_chart(
                athlete_range, use_column, f"{label}{suffix}", f"{unit}{suffix}",
                decimals, rolling_on, display_theme, labels_on,
            )
            with grid[i % 2]:
                st.plotly_chart(fig, width="stretch")
                n_valid = int(athlete_range[use_column].notna().sum())
                st.caption(f"Based on {n_valid} of {len(athlete_range)} sessions. Gaps = no valid measurement.")
    st.caption("◆ = minutes approximate. Dashed line = average of the last 3 valid sessions (appears once 3 exist). "
               "Reference bands, when shown, are descriptive mean +/- 1 SD bands requiring at least "
               f"{m.MIN_SESSIONS_FOR_REFERENCE_BAND} valid observations. "
               + (f"{n_excluded} session(s) excluded for suspected sensor dropout." if n_excluded else ""))

    st.markdown("#### Match intensity profile")
    st.plotly_chart(
        charts.match_intensity_scatter(athlete_range, display_theme),
        width="stretch",
    )
    st.caption(
        "Each point is an analysis-eligible match. Compare playing time with distance rate; "
        "color shows opponent table band and diamonds mark approximate minutes."
    )

    with st.expander("Match-to-match % change"):
        change_table = pd.DataFrame({"Date": athlete_range["match_date"].dt.strftime("%d %b %Y")})
        for column in trend_columns:
            change_table[m.METRIC_INFO[column][0]] = m.pct_change_vs_previous(athlete_range[column]).round(1)
        st.dataframe(change_table, hide_index=True, width="stretch")
        st.caption("Change vs the previous session that has a value for that metric. Blank = no earlier value.")

# ------------------------------------------------------------------ E. Workload & Consistency
with tabs[4]:
    st.subheader("Workload consistency")
    if athlete_range.empty:
        st.info("No analysis-eligible sessions fall within the selected date range.")
    st.caption(
        "Variation is summarized as coefficient of variation (CV). Volume metrics are shown per 90 "
        "where sessions are long enough, so playing time has less influence."
    )
    consistency = m.consistency_table(athlete_range)
    consistency_display = consistency.rename(columns={
        "metric": "Metric", "basis": "Basis", "n": "Valid sessions",
        "mean": "Mean", "sd": "Standard deviation", "cv_pct": "CV (%)",
        "low_confidence": "Low confidence",
    })
    st.dataframe(
        consistency_display,
        hide_index=True,
        width="stretch",
        column_config={
            "Mean": st.column_config.NumberColumn(format="%.2f"),
            "Standard deviation": st.column_config.NumberColumn(format="%.2f"),
            "CV (%)": st.column_config.NumberColumn(format="%.1f%%"),
            "Low confidence": st.column_config.CheckboxColumn(),
        },
    )
    st.caption(
        f"Low confidence means fewer than {m.MIN_SESSIONS_FOR_CONSISTENCY} valid sessions. "
        "CV describes variability; it is not a target or a quality grade."
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            charts.consistency_heatmap(athlete_range, display_theme),
            width="stretch",
        )
        st.caption("Color shows within-athlete standard deviations from the athlete's own mean.")
    with right:
        st.plotly_chart(
            charts.workload_composition_chart(athlete_range, display_theme),
            width="stretch",
        )
        st.caption("High-speed distance is a subset of total distance. Sessions missing either value are omitted.")

# ------------------------------------------------------------------ F. Comparison
with tabs[5]:
    st.subheader("Compare athlete workload")
    st.caption(
        "Per-90 and pooled rates make playing time more comparable, but do not adjust for role, "
        "opposition, tactics, or device configuration."
    )
    athlete_labels = {
        row.athlete_id: f"{row.athlete_name} · {row.position}"
        for row in athletes.itertuples()
    }
    same_position = athletes.loc[athletes["position"] == athlete_info["position"], "athlete_id"].tolist()
    selected_comparison = st.multiselect(
        "Athletes to compare",
        options=list(athlete_labels),
        default=[selected_id] + [item for item in same_position if item != selected_id][:2],
        format_func=athlete_labels.get,
    )
    if not selected_comparison:
        st.info("Select at least one athlete to see comparisons.")
    else:
        comparison, comparison_warnings = m.comparison_table(clean_df, selected_comparison)
        for warning in comparison_warnings:
            st.warning(warning)

        comparison_display = comparison.rename(columns={
            "athlete_name": "Athlete", "position": "Position", "sessions": "Sessions",
            "total_minutes": "Minutes", "distance_per_min": "Distance (m/min)",
            "hsr_m_per90": "HSR (m/90)", "sprints_per90": "Sprints (/90)",
            "accels_per90": "Accelerations (/90)", "decels_per90": "Decelerations (/90)",
            "player_load_per90": "Player Load (/90)", "top_speed_best_kmh": "Best speed (km/h)",
        })
        display_columns = [
            "Athlete", "Position", "Sessions", "Minutes", "Distance (m/min)",
            "HSR (m/90)", "Sprints (/90)", "Accelerations (/90)",
            "Decelerations (/90)", "Player Load (/90)", "Best speed (km/h)",
        ]
        st.dataframe(
            comparison_display[display_columns],
            hide_index=True,
            width="stretch",
            column_config={
                column: st.column_config.NumberColumn(format="%.1f")
                for column in display_columns[3:]
            },
        )
        st.caption("Radar axes are cohort percentiles for the selected group, not league rankings or performance targets.")
        left, right = st.columns(2)
        with left:
            st.plotly_chart(
                charts.comparison_radar_chart(comparison, display_theme),
                width="stretch",
            )
        with right:
            st.plotly_chart(
                charts.comparison_bubble_chart(comparison, display_theme),
                width="stretch",
            )

        distribution_options = {
            "Distance per minute": ("distance_per_min", "Distance per minute (m/min)"),
            "High-speed running per 90": ("hsr_distance_m_per90", "HSR (m / 90 min)"),
            "Sprints per 90": ("sprint_count_per90", "Sprints / 90 min"),
            "Player Load per 90": ("player_load_au_per90", "Player Load / 90 min"),
        }
        distribution_label = st.selectbox(
            "Session distribution",
            options=list(distribution_options),
            key="comparison_distribution",
        )
        distribution_column, distribution_unit = distribution_options[distribution_label]
        st.plotly_chart(
            charts.comparison_box_chart(
                clean_df, selected_comparison, distribution_column,
                f"{distribution_label} · session distribution",
                distribution_unit, display_theme,
            ),
            width="stretch",
        )
        st.caption("Boxes show the interquartile range and median; points are individual usable sessions.")

# ------------------------------------------------------------------ G. Report
with tabs[6]:
    st.subheader("Athlete workload report")
    report_data = report_builder.build_report(clean_df, issues_df, selected_id)
    report_markdown = report_builder.render_report_markdown(report_data)
    st.markdown(f"**{report_data['athlete_name']} · {report_data['position']} · {report_data['club']}**")
    st.caption(
        f"{report_data['period_start']:%d %b %Y} – {report_data['period_end']:%d %b %Y} · "
        "reporting period"
    )
    report_metrics = report_data["metrics"]
    report_stats = report_metrics.set_index("column")
    report_kpis = [
        "total_distance_km", "distance_per_min", "hsr_distance_m",
        "sprint_count", "player_load_au", "top_speed_kmh",
    ]
    for row_start in (0, 3):
        kpi_columns = st.columns(3)
        for index, column in enumerate(report_kpis[row_start:row_start + 3]):
            stat = report_stats.loc[column]
            kpi_columns[index].metric(
                str(stat["metric"]),
                fmt(column, stat["value"]),
            )
            if int(stat["n_valid"]) != len(report_data["sessions"]):
                kpi_columns[index].caption(
                    f"{int(stat['n_valid'])} of {len(report_data['sessions'])} sessions"
                )
    latest = (
        report_data["sessions"].iloc[-1]["match_date"].strftime("%d %b %Y")
        if not report_data["sessions"].empty
        else "not available"
    )
    st.caption(f"Based on {len(report_data['sessions'])} eligible sessions ({latest} latest).")

    st.markdown("#### Automated observations")
    observations = report_data["observations"][[
        "Metric", "Latest", "vs previous session", "vs historical mean", "Flag",
    ]].copy()
    report_colors = theme_module.colors_for(display_theme)

    def observation_color(value):
        color_token, bold = classify_change(value)
        weight = "700" if bold else "400"
        return f"color: {report_colors[color_token]}; font-weight: {weight};"

    observation_style = (
        observations.style
        .map(observation_color, subset=["vs previous session", "vs historical mean"])
        .set_properties(
            subset=["Latest", "vs previous session", "vs historical mean"],
            **{"text-align": "right", "font-variant-numeric": "tabular-nums"},
        )
        .set_table_styles([
            {
                "selector": "thead th",
                "props": [
                    ("text-align", "left"),
                    ("border-bottom", "2px solid var(--control-border)"),
                ],
            },
            {
                "selector": "tbody td",
                "props": [
                    ("border-bottom", "1px solid var(--border)"),
                    ("font-variant-numeric", "tabular-nums"),
                ],
            },
            {
                "selector": "tbody tr:nth-child(even)",
                "props": [("background-color", "var(--surface-tint)")],
            },
        ])
    )
    st.dataframe(
        observation_style,
        hide_index=True,
        width="stretch",
        column_config={
            "Metric": st.column_config.TextColumn(width="medium"),
            "Latest": st.column_config.TextColumn(width="small"),
            "vs previous session": st.column_config.TextColumn(width="small"),
            "vs historical mean": st.column_config.TextColumn(width="small"),
            "Flag": st.column_config.TextColumn(width="medium"),
        },
    )
    st.caption(theme_module.CHANGE_LEGEND)
    st.caption(f"Notes: {report_data['notes']}")

    st.markdown("#### Latest session vs historical baseline")
    baseline = report_data["latest_baseline"]
    baseline_display = pd.DataFrame({
        "Metric": [m.METRIC_INFO[column][0] for column in baseline["column"]],
        "Latest": [fmt(column, value) for column, value in zip(baseline["column"], baseline["latest"])],
        "Previous valid": [fmt(column, value) for column, value in zip(baseline["column"], baseline["previous"])],
        "Historical mean": [fmt(column, value) for column, value in zip(baseline["column"], baseline["historical_mean"])],
        "Historical median": [fmt(column, value) for column, value in zip(baseline["column"], baseline["historical_median"])],
        "Change vs mean": [fmt_pct(value) or "—" for value in baseline["pct_baseline"]],
        "Baseline n": baseline["baseline_n"],
    })
    baseline_style = baseline_display.style.map(
        observation_color,
        subset=["Change vs mean"],
    ).set_properties(
        subset=["Change vs mean"],
        **{"text-align": "right", "font-variant-numeric": "tabular-nums"},
    )
    st.dataframe(baseline_style, hide_index=True, width="stretch")
    st.caption("Historical baseline excludes the evaluated session. n is the valid prior-session count per metric.")

    report_pdf = pdf_report_builder.render_report_pdf(report_data)
    pdf_button, markdown_button, csv_button = st.columns(3)
    pdf_button.download_button(
        "Download report (.pdf)",
        data=report_pdf,
        file_name=f"{selected_id.lower()}_workload_report.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
    )
    markdown_button.download_button(
        "Download report (.md)",
        data=report_markdown,
        file_name=f"{selected_id.lower()}_workload_report.md",
        mime="text/markdown",
        use_container_width=True,
    )
    report_csv = report_metrics.to_csv(index=False).encode("utf-8")
    csv_button.download_button(
        "Download metrics (.csv)",
        data=report_csv,
        file_name=f"{selected_id.lower()}_workload_metrics.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption(
        "GPS values are subject to device-configuration and small-sample limitations. "
        "Synthetic demo data; not for selection, medical, or training decisions."
    )

# ------------------------------------------------------------------ H. Data Quality
with tabs[7]:
    st.subheader("Data quality & audit trail")
    summary = quality.quality_summary(clean_df, issues_df)
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Issue records", summary["issue_records"])
    q2.metric("Affected sessions", summary["affected_sessions"])
    q3.metric("Analysis eligible", summary["usable_sessions"])
    q4.metric("Excluded", summary["excluded_sessions"])
    st.caption(
        "Sessions flagged for possible sensor dropout are excluded from trends and averages. "
        "All issue records remain visible here; this is a screening aid, not sensor certification."
    )
    st.plotly_chart(
        charts.quality_map_chart(clean_df, display_theme),
        width="stretch",
    )
    issue_counts = pd.DataFrame([
        {
            "Issue": quality.ISSUE_LABELS.get(issue_type, issue_type.replace("_", " ").title()),
            "Records": count,
        }
        for issue_type, count in summary["issue_counts"].items()
    ]).sort_values("Records", ascending=False)
    st.markdown("#### Issue register")
    if issue_counts.empty:
        st.success("No quality issues were recorded.")
    else:
        st.dataframe(issue_counts, hide_index=True, width="stretch")
        register = quality.issue_register(clean_df, issues_df)
        register_display = register.rename(columns={
            "match_date": "Date", "athlete_name": "Athlete", "position": "Position",
            "opponent": "Opponent", "issue_label": "Issue", "column": "Field",
            "detail": "Detail", "quality_status": "Session status", "use_in_analysis": "Included",
        })
        register_columns = [
            column for column in [
                "Date", "Athlete", "Position", "Opponent", "Issue", "Field",
                "Detail", "Session status", "Included",
            ] if column in register_display
        ]
        st.dataframe(
            register_display[register_columns],
            hide_index=True,
            width="stretch",
            column_config={"Date": st.column_config.DateColumn(format="DD MMM YYYY")},
        )
        st.download_button(
            "Download issue register (.csv)",
            data=register.to_csv(index=False).encode("utf-8"),
            file_name="gps_data_quality_issue_register.csv",
            mime="text/csv",
        )
