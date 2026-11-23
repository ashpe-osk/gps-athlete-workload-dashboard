"""Build publication-conscious, traceable athlete reports from cleaned sessions."""
import pandas as pd

from . import metrics as m
from .formatting import format_metric, format_percent
from .quality import quality_summary


def build_report(sessions: pd.DataFrame, issues: pd.DataFrame, athlete_id: str) -> dict:
    """Build a reproducible report payload for one athlete."""
    athlete_all = sessions[sessions["athlete_id"] == athlete_id].sort_values("match_date")
    if athlete_all.empty:
        raise ValueError(f"No sessions found for athlete_id {athlete_id}")

    athlete_usable = m.add_per90_columns(m.usable_sessions(athlete_all))
    stats = m.combined_stats(athlete_usable)
    start_date = athlete_all["match_date"].min()
    end_date = athlete_all["match_date"].max()
    athlete_issues = issues[
        issues["session_id"].isin(athlete_all["session_id"])
    ] if "session_id" in issues else issues

    consistency = m.consistency_table(athlete_usable)
    latest_baseline = (
        m.historical_baseline_table(
            athlete_usable,
            match_id=athlete_usable.iloc[-1]["match_id"],
        )
        if not athlete_usable.empty
        else pd.DataFrame()
    )

    report_payload = {
        "athlete_id": athlete_id,
        "athlete_name": str(athlete_all.iloc[0]["athlete_name"]),
        "position": str(athlete_all.iloc[0]["position"]),
        "club": str(athlete_all.iloc[0]["club"]),
        "period_start": start_date,
        "period_end": end_date,
        "sessions": athlete_usable,
        "all_sessions": athlete_all,
        "metrics": stats,
        "consistency": consistency,
        "latest_baseline": latest_baseline,
        "quality": quality_summary(athlete_all, athlete_issues),
        "issues": athlete_issues.copy(),
    }
    report_payload["observations"] = build_observations_table(report_payload)
    report_payload["notes"] = build_report_notes(report_payload)
    return report_payload


def build_observations_table(report: dict) -> pd.DataFrame:
    """Build a compact, metric-level table of changes and relative variation flags."""
    consistency = report["consistency"]
    per_match = consistency.loc[
        consistency["basis"] == "per match",
        ["metric", "n", "cv_pct", "low_confidence"],
    ].dropna(subset=["cv_pct"])
    reliable_cv = per_match.loc[
        (~per_match["low_confidence"].astype(bool))
        & (per_match["n"] >= m.MIN_SESSIONS_FOR_CONSISTENCY),
        "cv_pct",
    ]
    cv_threshold = float(reliable_cv.median() * 1.5) if len(reliable_cv) >= 2 else float("inf")
    cv_by_metric = per_match.set_index("metric")

    rows = []
    for metric_order, baseline in enumerate(report["latest_baseline"].itertuples(index=False)):
        metric = m.METRIC_INFO[baseline.column][0]
        cv = cv_by_metric.loc[metric, "cv_pct"] if metric in cv_by_metric.index else float("nan")
        low_confidence = (
            bool(cv_by_metric.loc[metric, "low_confidence"])
            if metric in cv_by_metric.index
            else True
        )
        flag = (
            f"High variation (CV {cv:.0f}%)"
            if pd.notna(cv) and not low_confidence and cv > cv_threshold
            else ""
        )
        changes = [
            abs(change)
            for change in (baseline.pct_previous, baseline.pct_baseline)
            if pd.notna(change)
        ]
        rows.append({
            "column": baseline.column,
            "Metric": metric,
            "Latest": format_metric(baseline.column, baseline.latest),
            "pct_previous": baseline.pct_previous,
            "vs previous session": _format_change(baseline.pct_previous),
            "pct_historical_mean": baseline.pct_baseline,
            "vs historical mean": _format_change(baseline.pct_baseline),
            "Flag": flag,
            "baseline_n": baseline.baseline_n,
            "_change_magnitude": max(changes) if changes else float("nan"),
            "_metric_order": metric_order,
        })

    table = pd.DataFrame(rows)
    if table.empty:
        return table
    table = table.sort_values(
        ["_change_magnitude", "_metric_order"],
        ascending=[False, True],
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)
    return table


def _format_change(value) -> str:
    if pd.isna(value):
        return "—"
    if abs(float(value)) < 0.05:
        return "– 0.0%"
    arrow = "▲" if value > 0 else "▼"
    percentage = format_percent(value)
    return f"{arrow} {percentage}"


def build_report_notes(report: dict) -> str:
    """Summarize the highest relative CVs and data-quality counts in one line."""
    consistency = report["consistency"]
    per_match = consistency.loc[
        consistency["basis"] == "per match",
        ["metric", "n", "cv_pct", "low_confidence"],
    ]
    reliable = per_match.loc[
        per_match["cv_pct"].notna()
        & (~per_match["low_confidence"].astype(bool))
        & (per_match["n"] >= m.MIN_SESSIONS_FOR_CONSISTENCY)
    ]
    median_cv = float(reliable["cv_pct"].median()) if len(reliable) >= 2 else float("inf")
    high_variation = reliable.loc[reliable["cv_pct"] > median_cv * 1.5].sort_values(
        "cv_pct", ascending=False,
    )
    if high_variation.empty:
        variation = "No high-variation metrics flagged"
    else:
        values = ", ".join(
            f"{row.metric} {row.cv_pct:.1f}%"
            for row in high_variation.head(3).itertuples(index=False)
        )
        variation = f"Highest variation: {values}"

    quality = report["quality"]
    excluded = int(quality["excluded_sessions"])
    missing = int(quality["missing_measurements"])
    invalid = int(quality["invalid_measurements"])
    notes = [
        variation,
        f"{excluded} {'session' if excluded == 1 else 'sessions'} excluded",
        f"{missing} missing {'value' if missing == 1 else 'values'}",
    ]
    if invalid:
        notes.append(f"{invalid} invalid {'value' if invalid == 1 else 'values'}")
    return " | ".join(notes)


def render_report_markdown(report: dict) -> str:
    """Render a concise, chart-linked Markdown companion to the downloadable PDF."""
    start = report["period_start"].strftime("%d %b %Y")
    end = report["period_end"].strftime("%d %b %Y")
    latest = report["sessions"].iloc[-1] if not report["sessions"].empty else None
    latest_context = (
        f"{latest['match_date']:%d %b %Y} latest"
        if latest is not None
        else "no eligible session available"
    )
    lines = [
        f"# Athlete workload report: {report['athlete_name']}",
        "",
        f"**{report['position']} · {report['club']} · {report['athlete_id']}**",
        f"**Reporting period:** {start} – {end}",
        "",
        f"Based on {len(report['sessions'])} eligible sessions ({latest_context}).",
        "",
        "## Automated observations",
        "",
        "| Metric | Latest | vs previous session | vs historical mean | Flag |",
        "|---|---:|---:|---:|---|",
    ]
    for _, row in report["observations"].iterrows():
        lines.append(
            f"| {row['Metric']} | {row['Latest']} | {row['vs previous session']} | "
            f"{row['vs historical mean']} | {row['Flag']} |"
        )
    lines.extend([
        "",
        f"**Notes:** {report['notes']}",
        "",
        "## Latest session vs historical baseline",
        "",
        "| Metric | Latest | Previous valid | Historical mean | Historical median | Change vs mean | Baseline n |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in report["latest_baseline"].itertuples(index=False):
        lines.append(
            f"| {m.METRIC_INFO[row.column][0]} | {format_metric(row.column, row.latest)} | "
            f"{format_metric(row.column, row.previous)} | {format_metric(row.column, row.historical_mean)} | "
            f"{format_metric(row.column, row.historical_median)} | "
            f"{format_percent(row.pct_baseline) or '—'} | {row.baseline_n} |"
        )
    lines.extend([
        "",
        "Trend charts and eligible-session detail are included in the PDF report.",
        "",
        "> Synthetic demo data; GPS values are subject to device and measurement limitations; "
        "not for selection, medical, or training decisions.",
    ])
    return "\n".join(lines)
