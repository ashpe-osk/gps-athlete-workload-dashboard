"""
cleaning.py
-----------
Turns the raw synthetic CSV into an analysis-ready table and a list of data-quality issues.

Golden rules:
  * Missing values stay missing (NaN). They are NEVER replaced with zero.
  * We never silently delete information. Every problem is logged as an "issue".
  * Impossible values are blanked to NaN (and logged); the rest of that row is kept.

Run from the project root:   python src/cleaning.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "data" / "raw" / "gps_sessions_synthetic.csv"
PROCESSED_DIR = ROOT / "data" / "processed"

# GPS metrics checked for missing values.
METRIC_COLUMNS = [
    "total_distance_km", "distance_per_min", "hsr_distance_m", "top_speed_kmh",
    "sprint_count", "accel_count", "decel_count", "peak_accel_ms2", "player_load_au",
]

# Broad plausibility bounds, not performance benchmarks.
VALID_RANGES = {
    "minutes_played": (1, 130),
    "total_distance_km": (0, 16),
    "distance_per_min": (0, 200),
    "hsr_distance_m": (0, 2500),
    "top_speed_kmh": (0, 38),
    "sprint_count": (0, 120),
    "accel_count": (0, 250),
    "decel_count": (0, 250),
    "peak_accel_ms2": (0, 10),
    "player_load_au": (0, 600),
}

# Flag rates below this fraction of the athlete's own median.
DROPOUT_RATIO = 0.70

# Relative tolerance for reported and recomputed distance rates.
RATE_MISMATCH_TOLERANCE = 0.05


def make_issue(session_id, issue_type, column, detail):
    """One problem found in one session. Collected into a table later."""
    return {"session_id": session_id, "issue_type": issue_type, "column": column, "detail": detail}


def load_raw(path=RAW_PATH) -> pd.DataFrame:
    """Read the CSV. Dates become real dates so we can sort and calculate with them."""
    return pd.read_csv(path, parse_dates=["match_date"])


def remove_duplicates(df: pd.DataFrame):
    """Keep the first row for each session_id. Log every extra copy."""
    issues = []
    is_extra_copy = df.duplicated(subset="session_id", keep="first")
    for idx in df.index[is_extra_copy]:
        extra = df.loc[idx]
        first = df[df["session_id"] == extra["session_id"]].iloc[0]
        kind = "exact copy" if extra.equals(first) else "same session_id but DIFFERENT values"
        issues.append(make_issue(extra["session_id"], "duplicate_record", "all", f"{kind}; extra row removed"))
    return df[~is_extra_copy].copy(), issues


def find_missing(df: pd.DataFrame):
    issues = []
    for column in METRIC_COLUMNS + ["minutes_played"]:
        for session_id in df.loc[df[column].isna(), "session_id"]:
            issues.append(make_issue(session_id, "missing_value", column, "not recorded"))
    return issues


def blank_invalid_values(df: pd.DataFrame):
    issues = []
    for column, (low, high) in VALID_RANGES.items():
        outside = df[column].notna() & ((df[column] < low) | (df[column] > high))
        for idx in df.index[outside]:
            issues.append(make_issue(
                df.loc[idx, "session_id"], "invalid_value", column,
                f"{df.loc[idx, column]} outside plausible range {low}-{high}; set to missing"))
        df.loc[outside, column] = np.nan
    return df, issues


def find_possible_dropouts(df: pd.DataFrame):
    issues = []
    own_median = df.groupby("athlete_id")["distance_per_min"].transform("median")
    ratio = df["distance_per_min"] / own_median
    for idx in df.index[ratio < DROPOUT_RATIO]:
        issues.append(make_issue(
            df.loc[idx, "session_id"], "possible_dropout", "distance_per_min",
            f"{ratio[idx]:.0%} of this athlete's median distance per minute"))
    return issues


def find_rate_mismatches(df: pd.DataFrame):
    issues = []
    recomputed = df["total_distance_km"] * 1000 / df["minutes_played"]
    relative_gap = (df["distance_per_min"] - recomputed).abs() / recomputed
    for idx in df.index[relative_gap > RATE_MISMATCH_TOLERANCE]:
        issues.append(make_issue(df.loc[idx, "session_id"], "rate_mismatch", "distance_per_min",
                                 "reported rate disagrees with distance / minutes"))
    return issues


def find_estimated_minutes(df: pd.DataFrame):
    return [make_issue(sid, "estimated_minutes", "minutes_played", "minutes are approximate")
            for sid in df.loc[df["minutes_estimated"], "session_id"]]


def add_session_flags(df: pd.DataFrame, issues: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    by_session = issues.groupby("session_id")["issue_type"]
    df["issue_count"] = df["session_id"].map(by_session.size()).fillna(0).astype(int)
    df["has_missing"] = df["session_id"].isin(issues.loc[issues["issue_type"] == "missing_value", "session_id"])
    df["has_invalid"] = df["session_id"].isin(issues.loc[issues["issue_type"] == "invalid_value", "session_id"])
    df["possible_dropout"] = df["session_id"].isin(issues.loc[issues["issue_type"] == "possible_dropout", "session_id"])

    # Priority: dropout, invalid, missing, then approximate minutes.
    df["quality_status"] = np.select(
        [df["possible_dropout"], df["has_invalid"], df["has_missing"], df["minutes_estimated"]],
        ["possible_dropout", "invalid_value", "missing_value", "estimated_minutes"],
        default="complete",
    )
    # Exclude suspected dropouts from analysis.
    df["use_in_analysis"] = ~df["possible_dropout"]

    # Preserve missing counts as nullable integers.
    for column in ["sprint_count", "accel_count", "decel_count", "hsr_distance_m"]:
        df[column] = df[column].round().astype("Int64")
    return df


def clean_pipeline(path=RAW_PATH):
    """Return (clean_dataframe, issues_dataframe)."""
    df = load_raw(path)
    df, issues = remove_duplicates(df)
    issues += find_missing(df)
    df, invalid_issues = blank_invalid_values(df)
    issues += invalid_issues
    issues += find_possible_dropouts(df)
    issues += find_rate_mismatches(df)
    issues += find_estimated_minutes(df)

    issues_df = pd.DataFrame(issues, columns=["session_id", "issue_type", "column", "detail"])
    clean_df = add_session_flags(df, issues_df)
    clean_df = clean_df.sort_values(["athlete_id", "match_date"]).reset_index(drop=True)
    return clean_df, issues_df


def main():
    clean_df, issues_df = clean_pipeline()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(PROCESSED_DIR / "gps_sessions_clean.csv", index=False)
    issues_df.to_csv(PROCESSED_DIR / "data_quality_issues.csv", index=False)

    print(f"Clean sessions: {len(clean_df)}  |  usable in analysis: {int(clean_df['use_in_analysis'].sum())}")
    print("\nIssues found by type:")
    print(issues_df["issue_type"].value_counts().to_string())
    print("\nSession status:")
    print(clean_df["quality_status"].value_counts().to_string())


if __name__ == "__main__":
    main()
