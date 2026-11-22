"""Build publication-conscious, traceable athlete reports from cleaned sessions."""
import pandas as pd

from . import metrics as m
from .formatting import format_metric
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

    return {
        "athlete_id": athlete_id,
        "athlete_name": str(athlete_all.iloc[0]["athlete_name"]),
        "position": str(athlete_all.iloc[0]["position"]),
        "club": str(athlete_all.iloc[0]["club"]),
        "period_start": start_date,
        "period_end": end_date,
        "sessions": athlete_usable,
        "all_sessions": athlete_all,
        "metrics": stats,
        "quality": quality_summary(athlete_all, athlete_issues),
        "issues": athlete_issues.copy(),
    }


def render_report_markdown(report: dict) -> str:
    """Render a concise Markdown report with its data limitations stated prominently."""
    start = report["period_start"].strftime("%d %b %Y")
    end = report["period_end"].strftime("%d %b %Y")
    usable = len(report["sessions"])
    total = len(report["all_sessions"])
    lines = [
        f"# Athlete workload report: {report['athlete_name']}",
        "",
        f"**{report['position']} · {report['club']} · {report['athlete_id']}**",
        f"**Reporting period:** {start} – {end}",
        "",
        "> **SYNTHETIC DEMO DATA.** This report contains fictional athlete, fixture, and GPS data. "
        "It is not a real-world performance assessment or an official GameOn product.",
        "",
        "## Summary",
        "",
        f"{usable} of {total} recorded sessions passed the analysis eligibility screen. "
        "Totals and pooled rates use available measurements; peaks use the maximum valid value. "
        "Missing measurements are not interpreted as zero.",
        "",
        "## Combined metrics",
        "",
        "| Metric | Value | Aggregation | Valid sessions |",
        "|---|---:|---|---:|",
    ]
    for row in report["metrics"].itertuples(index=False):
        lines.append(
            f"| {row.metric} | {format_metric(row.column, row.value)} | "
            f"{row.method} | {row.n_valid}/{row.n_sessions} |"
        )

    quality = report["quality"]
    lines.extend([
        "",
        "## Data quality",
        "",
        f"- Sessions excluded from analysis: {quality['excluded_sessions']}",
        f"- Missing measurement issue records: {quality['missing_measurements']}",
        f"- Invalid measurement issue records: {quality['invalid_measurements']}",
        f"- Approximate-minute issue records: {quality['approximate_minutes']}",
        f"- Other issue records: {quality['issue_records'] - quality['missing_measurements'] - quality['invalid_measurements'] - quality['approximate_minutes']}",
        "",
        "## Interpretation",
        "",
        "GPS-derived metrics depend on device configuration, sampling, and processing. Compare athletes "
        "only when measurement protocols and playing context are sufficiently aligned. This synthetic "
        "prototype is for demonstration and should not be used for selection, medical, or training decisions.",
        "",
    ])
    return "\n".join(lines)
