"""
app.py
------
Streamlit interface ONLY. All calculations live in src/metrics.py.
Run from the project root:   streamlit run app/app.py
"""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import charts  # noqa: E402
import metrics as m  # noqa: E402
from cleaning import clean_pipeline  # noqa: E402

st.set_page_config(page_title="GPS Workload Dashboard (Synthetic Demo)", page_icon="📊", layout="wide")

NUMBER_FORMATS = {
    "minutes_played": "{:.0f}", "total_distance_km": "{:.2f}", "distance_per_min": "{:.1f}",
    "hsr_distance_m": "{:,.0f}", "top_speed_kmh": "{:.1f}", "sprint_count": "{:.0f}",
    "accel_count": "{:.0f}", "decel_count": "{:.0f}", "peak_accel_ms2": "{:.1f}", "player_load_au": "{:,.1f}",
}


def fmt(column: str, value) -> str:
    """Format a value with its unit. Missing values show as a dash, never 0."""
    if pd.isna(value):
        return "—"
    unit = m.METRIC_INFO[column][2]
    return f"{NUMBER_FORMATS[column].format(float(value))} {unit}"


def fmt_pct(value) -> str | None:
    return None if pd.isna(value) else f"{value:+.1f}%"


@st.cache_data
def load_clean():
    clean_df, issues_df = clean_pipeline()
    return clean_df, issues_df


clean_df, issues_df = load_clean()

# ------------------------------------------------------------------ header
st.title("GPS Athlete Performance and Workload Dashboard")
st.warning(
    "**SYNTHETIC DEMO DATA.** Club names are public league context only. All athletes, fixtures, dates and "
    "GPS values are fictional. Independent portfolio prototype, not an official GameOn Collective product."
)

# ------------------------------------------------------------------ sidebar
athletes = clean_df[["athlete_id", "athlete_name", "position", "club"]].drop_duplicates().sort_values("athlete_id")
labels = {r.athlete_id: f"{r.athlete_name} ({r.position})" for r in athletes.itertuples()}
selected_id = st.sidebar.selectbox("Athlete", options=list(labels), format_func=labels.get)
st.sidebar.caption("Sessions flagged as possible sensor dropout are excluded from trends and averages.")

athlete_all = clean_df[clean_df["athlete_id"] == selected_id].sort_values("match_date").reset_index(drop=True)
athlete_use = m.add_per90_columns(m.usable_sessions(athlete_all))
athlete_info = athlete_all.iloc[0]
n_excluded = len(athlete_all) - len(athlete_use)

if athlete_use.empty:
    st.info("This athlete has no usable sessions yet.")
    st.stop()

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

# ------------------------------------------------------------------ D. Performance Trends
with tabs[3]:
    t1, t2 = st.columns(2)
    per90_on = t1.checkbox("Adjust volume metrics to per 90 minutes", value=False,
                           help="Removes the effect of playing fewer minutes. Sessions under 45 min are left out.")
    rolling_on = t2.checkbox("Show rolling average (3 sessions)", value=True)

    trend_columns = ["total_distance_km", "hsr_distance_m", "sprint_count", "player_load_au", "distance_per_min"]
    grid = st.columns(2)
    for i, column in enumerate(trend_columns):
        use_column = f"{column}_per90" if per90_on and column in m.VOLUME_COLUMNS else column
        label, _, unit = m.METRIC_INFO[column]
        suffix = " per 90" if use_column != column else ""
        decimals = 2 if column == "total_distance_km" else 1 if column in ("distance_per_min", "player_load_au") else 0
        fig = charts.trend_chart(athlete_use, use_column, f"{label}{suffix}", f"{unit}{suffix}", decimals, rolling_on)
        with grid[i % 2]:
            st.plotly_chart(fig, width="stretch")
            n_valid = int(athlete_use[use_column].notna().sum())
            st.caption(f"Based on {n_valid} of {len(athlete_use)} sessions. Gaps = no valid measurement.")
    st.caption("◆ = minutes approximate. Dashed line = average of the last 3 valid sessions (appears once 3 exist). "
               + (f"{n_excluded} session(s) excluded for suspected sensor dropout." if n_excluded else ""))

    with st.expander("Match-to-match % change"):
        change_table = pd.DataFrame({"Date": athlete_use["match_date"].dt.strftime("%d %b %Y")})
        for column in trend_columns:
            change_table[m.METRIC_INFO[column][0]] = m.pct_change_vs_previous(athlete_use[column]).round(1)
        st.dataframe(change_table, hide_index=True, width="stretch")
        st.caption("Change vs the previous session that has a value for that metric. Blank = no earlier value.")

# ------------------------------------------------------------------ placeholders (next build step)
for tab, name in zip(tabs[4:], ["Workload & Consistency", "Comparison", "Report", "Data Quality"]):
    with tab:
        st.info(f"{name} is built in the next step.")
