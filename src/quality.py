"""Data-quality summaries and issue registers for the dashboard and exports."""
import pandas as pd


ISSUE_LABELS = {
    "possible_dropout": "Possible sensor dropout",
    "invalid_value": "Invalid measurement",
    "missing_value": "Missing measurement",
    "rate_mismatch": "Distance-rate mismatch",
    "estimated_minutes": "Approximate minutes",
    "duplicate_record": "Duplicate source record",
}

STATUS_LEVELS = {
    "complete": 0,
    "estimated_minutes": 1,
    "missing_value": 2,
    "invalid_value": 3,
    "possible_dropout": 4,
}


def quality_summary(sessions: pd.DataFrame, issues: pd.DataFrame) -> dict:
    """Summarize issue records and analysis eligibility without inventing a quality score."""
    issue_counts = (
        issues["issue_type"].value_counts().to_dict()
        if "issue_type" in issues
        else {}
    )
    return {
        "total_sessions": int(len(sessions)),
        "usable_sessions": int(sessions["use_in_analysis"].sum()),
        "excluded_sessions": int((~sessions["use_in_analysis"]).sum()),
        "affected_sessions": int(sessions.loc[sessions["issue_count"] > 0, "session_id"].nunique()),
        "issue_records": int(len(issues)),
        "missing_measurements": int(issue_counts.get("missing_value", 0)),
        "invalid_measurements": int(issue_counts.get("invalid_value", 0)),
        "possible_dropouts": int(issue_counts.get("possible_dropout", 0)),
        "approximate_minutes": int(issue_counts.get("estimated_minutes", 0)),
        "duplicate_records": int(issue_counts.get("duplicate_record", 0)),
        "issue_counts": issue_counts,
    }


def issue_register(sessions: pd.DataFrame, issues: pd.DataFrame) -> pd.DataFrame:
    """Join issue events with session context for a transparent review table."""
    context_columns = [
        "session_id", "athlete_id", "athlete_name", "position", "club",
        "match_date", "opponent", "quality_status", "use_in_analysis",
    ]
    context = sessions[[c for c in context_columns if c in sessions.columns]].drop_duplicates("session_id")
    register = issues.merge(context, on="session_id", how="left", validate="many_to_one")
    if "match_date" in register:
        register["match_date"] = pd.to_datetime(register["match_date"], errors="coerce")
    register["issue_label"] = register["issue_type"].map(ISSUE_LABELS).fillna(register["issue_type"])
    return register.sort_values(
        ["match_date", "athlete_name", "issue_type"],
        na_position="last",
    ).reset_index(drop=True)
