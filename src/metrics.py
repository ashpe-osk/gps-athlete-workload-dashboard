"""
metrics.py
----------
Every calculation the dashboard uses. Pure functions: no Streamlit, no file access.
Input is the CLEAN table from cleaning.py (use rows where use_in_analysis is True).

Aggregation rules
  total  -> sum of valid values (NaN if none are valid; never 0 by default)
  peak   -> maximum of valid values
  rate   -> recomputed from totals (pooled), never a bare average of match rates
Missing values are skipped, and the number of valid sessions is always reported.
"""
import numpy as np
import pandas as pd

# Column: (display label, aggregation, unit).
METRIC_INFO = {
    "minutes_played":    ("Minutes played",        "total", "min"),
    "total_distance_km": ("Total distance",        "total", "km"),
    "distance_per_min":  ("Distance per minute",   "rate",  "m/min"),
    "hsr_distance_m":    ("High-speed running",    "total", "m"),
    "top_speed_kmh":     ("Top speed",             "peak",  "km/h"),
    "sprint_count":      ("Sprints",               "total", "count"),
    "accel_count":       ("Accelerations",         "total", "count"),
    "decel_count":       ("Decelerations",         "total", "count"),
    "peak_accel_ms2":    ("Peak acceleration",     "peak",  "m/s2"),
    "player_load_au":    ("Player Load",           "total", "AU"),
}

VOLUME_COLUMNS = ["total_distance_km", "hsr_distance_m", "sprint_count",
                  "accel_count", "decel_count", "player_load_au"]
TREND_METRICS = ["total_distance_km", "distance_per_min", "hsr_distance_m",
                 "sprint_count", "player_load_au", "accel_count", "decel_count"]
HISTORICAL_METRICS = [
    column for column in METRIC_INFO
    if column != "minutes_played"
]

ROLLING_WINDOW = 3
MIN_PRIOR_SESSIONS = 3            # needed before comparing with own history
MIN_SESSIONS_FOR_CONSISTENCY = 4  # below this, variability is flagged low-confidence
MIN_SESSIONS_FOR_REFERENCE_BAND = 6
MIN_MINUTES_FOR_RATES = 45        # per-90 values only for sessions at least this long
MIN_TOTAL_MINUTES_FOR_COMPARISON = 180


def usable_sessions(df: pd.DataFrame) -> pd.DataFrame:
    """Sessions that passed the data-quality screen, oldest first."""
    return df[df["use_in_analysis"]].sort_values(["athlete_id", "match_date"]).reset_index(drop=True)


def filter_sessions_by_date(
    df: pd.DataFrame,
    start_date,
    end_date,
) -> pd.DataFrame:
    """Filter sessions to an inclusive date range without replacing missing values."""
    filtered = df.copy()
    dates = pd.to_datetime(filtered["match_date"], errors="coerce")
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    return filtered.loc[(dates >= start) & (dates <= end)].copy()


def add_per90_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add <metric>_per90 for volume metrics. Short sessions (< MIN_MINUTES_FOR_RATES) stay missing."""
    df = df.copy()
    long_enough = df["minutes_played"] >= MIN_MINUTES_FOR_RATES
    for column in VOLUME_COLUMNS:
        values = df[column].astype("Float64")
        df[f"{column}_per90"] = (values / df["minutes_played"] * 90).where(long_enough).astype(float)
    return df


def safe_sum(series: pd.Series) -> float:
    """Sum of valid values; NaN (not 0) when nothing is valid."""
    return float(series.sum(min_count=1)) if series.notna().any() else np.nan


def pooled_rate(numerator: pd.Series, minutes: pd.Series, per: float = 1.0) -> float:
    """Total numerator / total minutes, using only sessions where BOTH are valid."""
    both = numerator.notna() & minutes.notna()
    total_minutes = minutes[both].sum()
    if both.sum() == 0 or total_minutes == 0:
        return np.nan
    return float(numerator[both].astype(float).sum() / total_minutes * per)


def pct_change_vs_previous(series: pd.Series) -> pd.Series:
    """% change vs the previous session that HAS a value for this metric."""
    valid = series.dropna().astype(float)
    previous = valid.shift(1)
    change = (valid - previous) / previous.where(previous != 0) * 100
    return change.reindex(series.index)


def rolling_mean(series: pd.Series, window: int = ROLLING_WINDOW) -> pd.Series:
    """Rolling average over the last `window` valid sessions. Missing until enough sessions exist."""
    valid = series.dropna().astype(float)
    return valid.rolling(window, min_periods=window).mean().reindex(series.index)


def compare_with_own_history(athlete_df: pd.DataFrame, column: str, match_id: str) -> dict:
    """Compare one match with the average of the athlete's EARLIER valid sessions."""
    athlete_df = athlete_df.sort_values("match_date")
    row = athlete_df[athlete_df["match_id"] == match_id]
    if row.empty:
        raise ValueError(f"No session for match_id {match_id}")
    current_date = row.iloc[0]["match_date"]
    current = row.iloc[0][column]
    prior = athlete_df.loc[athlete_df["match_date"] < current_date, column].dropna().astype(float)

    result = {"column": column, "current": np.nan if pd.isna(current) else float(current),
              "prior_mean": float(prior.mean()) if len(prior) else np.nan,
              "prior_n": int(len(prior)), "pct_diff": np.nan}
    if pd.isna(current):
        result["status"] = "missing"
    elif len(prior) < MIN_PRIOR_SESSIONS:
        result["status"] = "insufficient history"
    else:
        result["status"] = "ok"
        if result["prior_mean"] != 0:
            result["pct_diff"] = (result["current"] - result["prior_mean"]) / result["prior_mean"] * 100
    return result


def historical_baseline_summary(
    athlete_df: pd.DataFrame,
    column: str,
    match_id: str | None = None,
) -> dict:
    """Summarize a latest or selected session against prior eligible valid sessions."""
    eligible = usable_sessions(athlete_df) if "use_in_analysis" in athlete_df else athlete_df.sort_values("match_date")
    if eligible.empty:
        raise ValueError("No analysis-eligible sessions")

    if match_id is None:
        row = eligible.iloc[-1:]
    else:
        matching = eligible[eligible["match_id"] == match_id]
        if matching.empty:
            raise ValueError(f"No session for match_id {match_id}")
        row = matching.iloc[-1:]

    current_date = row.iloc[0]["match_date"]
    current = row.iloc[0][column] if column in eligible else np.nan
    prior = eligible.loc[
        eligible["match_date"] < current_date,
        column,
    ].dropna().astype(float)

    previous = np.nan
    if not prior.empty:
        previous = float(prior.iloc[-1])

    mean = float(prior.mean()) if len(prior) else np.nan
    median = float(prior.median()) if len(prior) else np.nan
    pct_previous = np.nan
    pct_baseline = np.nan
    if not pd.isna(current) and not pd.isna(previous) and previous != 0:
        pct_previous = (float(current) - previous) / previous * 100
    if not pd.isna(current) and not pd.isna(mean) and mean != 0:
        pct_baseline = (float(current) - mean) / mean * 100

    return {
        "column": column,
        "match_id": str(row.iloc[0]["match_id"]),
        "latest": np.nan if pd.isna(current) else float(current),
        "previous": previous,
        "historical_mean": mean,
        "historical_median": median,
        "pct_previous": pct_previous,
        "pct_baseline": pct_baseline,
        "baseline_n": int(len(prior)),
    }


def historical_baseline_table(
    athlete_df: pd.DataFrame,
    match_id: str | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """One row per metric for latest/selected-session historical comparisons."""
    selected_columns = columns or HISTORICAL_METRICS
    selected_columns = [
        column for column in selected_columns
        if column in athlete_df.columns
    ]
    return pd.DataFrame([
        historical_baseline_summary(athlete_df, column, match_id)
        for column in selected_columns
    ])


def match_vs_history(df: pd.DataFrame, athlete_id: str, match_id: str) -> pd.DataFrame:
    """One row per metric: this match vs the athlete's own earlier sessions."""
    athlete_df = add_per90_columns(usable_sessions(df[df["athlete_id"] == athlete_id]))
    columns = list(METRIC_INFO) + [f"{c}_per90" for c in VOLUME_COLUMNS]
    return pd.DataFrame([compare_with_own_history(athlete_df, c, match_id) for c in columns])


def combined_stats(athlete_df: pd.DataFrame) -> pd.DataFrame:
    """Combined statistics for one athlete's usable sessions, with the aggregation method stated."""
    n_sessions = len(athlete_df)
    rows = []
    for column, (label, kind, unit) in METRIC_INFO.items():
        values = athlete_df[column]
        n_valid = int(values.notna().sum())
        if column == "distance_per_min":
            value = pooled_rate(athlete_df["total_distance_km"] * 1000, athlete_df["minutes_played"])
            method = "total distance / total minutes"
        elif kind == "peak":
            value = float(values.max()) if n_valid else np.nan
            method = "best (maximum)"
        else:
            value = safe_sum(values)
            method = "total (sum of valid sessions)"
        rows.append({"metric": label, "column": column, "value": value, "unit": unit,
                     "method": method, "n_valid": n_valid, "n_sessions": n_sessions})
    return pd.DataFrame(rows)


def mean_of_match_rates(athlete_df: pd.DataFrame) -> float:
    """Simple average of per-match distance per minute (shown beside the pooled rate)."""
    return float(athlete_df["distance_per_min"].mean()) if athlete_df["distance_per_min"].notna().any() else np.nan


def consistency_summary(series: pd.Series) -> dict:
    """Mean, standard deviation and coefficient of variation (CV = sd / mean x 100)."""
    valid = series.dropna().astype(float)
    n = len(valid)
    mean = float(valid.mean()) if n else np.nan
    sd = float(valid.std(ddof=1)) if n >= 2 else np.nan
    cv = sd / mean * 100 if n >= 2 and mean != 0 else np.nan
    return {"n": n, "mean": mean, "sd": sd, "cv_pct": cv, "low_confidence": n < MIN_SESSIONS_FOR_CONSISTENCY}


def consistency_table(athlete_df: pd.DataFrame) -> pd.DataFrame:
    """Variability of each trend metric. Volume metrics are also given per 90 so that
    different minutes played do not inflate the variation."""
    athlete_df = add_per90_columns(athlete_df)
    rows = []
    for column in TREND_METRICS:
        row = {"metric": METRIC_INFO[column][0], "basis": "per match"}
        row.update(consistency_summary(athlete_df[column]))
        rows.append(row)
        if column in VOLUME_COLUMNS:
            row = {"metric": METRIC_INFO[column][0], "basis": "per 90 (sessions >= 45 min)"}
            row.update(consistency_summary(athlete_df[f"{column}_per90"]))
            rows.append(row)
    return pd.DataFrame(rows)


def comparison_table(df: pd.DataFrame, athlete_ids: list):
    """Per-90 and pooled-rate comparison plus a list of warnings about comparability."""
    rows, warnings = [], []
    sessions = usable_sessions(df)
    for athlete_id in athlete_ids:
        a = sessions[sessions["athlete_id"] == athlete_id]
        minutes = a["minutes_played"]
        rows.append({
            "athlete_id": athlete_id, "athlete_name": a["athlete_name"].iloc[0], "position": a["position"].iloc[0],
            "sessions": len(a), "total_minutes": float(minutes.sum()),
            "distance_per_min": pooled_rate(a["total_distance_km"] * 1000, minutes),
            "hsr_m_per90": pooled_rate(a["hsr_distance_m"], minutes, 90),
            "sprints_per90": pooled_rate(a["sprint_count"], minutes, 90),
            "accels_per90": pooled_rate(a["accel_count"], minutes, 90),
            "decels_per90": pooled_rate(a["decel_count"], minutes, 90),
            "player_load_per90": pooled_rate(a["player_load_au"], minutes, 90),
            "top_speed_best_kmh": float(a["top_speed_kmh"].max()) if a["top_speed_kmh"].notna().any() else np.nan,
        })
        if len(a) < MIN_PRIOR_SESSIONS:
            warnings.append(f"{rows[-1]['athlete_name']} has only {len(a)} usable sessions.")
        if minutes.sum() < MIN_TOTAL_MINUTES_FOR_COMPARISON:
            warnings.append(f"{rows[-1]['athlete_name']} has under {MIN_TOTAL_MINUTES_FOR_COMPARISON} total minutes.")
    table = pd.DataFrame(rows)
    positions = set(table["position"])
    if "Goalkeeper" in positions and len(positions) > 1:
        warnings.append("Goalkeepers and outfield players are not comparable on running metrics.")
    elif len(positions) > 1:
        warnings.append("Athletes play different positions; compare with caution.")
    return table, warnings
