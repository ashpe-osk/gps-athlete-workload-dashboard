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
    report_payload["narrative"] = build_narrative(report_payload)
    return report_payload


def build_narrative(report: dict) -> list[dict[str, str]]:
    """Create concise, evidence-labeled observations without tactical or medical claims."""
    observations = []
    latest_baseline = report["latest_baseline"]
    if latest_baseline is not None and not latest_baseline.empty:
        for row in latest_baseline.itertuples(index=False):
            label = m.METRIC_INFO[row.column][0]
            changes = []
            if pd.notna(row.pct_previous):
                changes.append(f"{row.pct_previous:+.1f}% from the previous valid session")
            if pd.notna(row.pct_baseline):
                changes.append(f"{row.pct_baseline:+.1f}% from the historical mean")
            if changes:
                observations.append({
                    "section": "Statistical observation",
                    "text": f"{label}: " + "; ".join(changes) + f" (baseline n={row.baseline_n}).",
                })

    consistency = report["consistency"]
    per_match = consistency.loc[
        consistency["basis"] == "per match",
        ["metric", "n", "cv_pct", "low_confidence"],
    ].dropna(subset=["cv_pct"])
    if len(per_match) >= 2:
        median_cv = float(per_match["cv_pct"].median())
        high = per_match[
            (per_match["cv_pct"] >= median_cv * 1.5)
            & (~per_match["low_confidence"].astype(bool))
        ].sort_values("cv_pct", ascending=False)
        if not high.empty:
            names = ", ".join(
                f"{row.metric} ({row.cv_pct:.1f}% CV)"
                for row in high.head(3).itertuples(index=False)
            )
            observations.append({
                "section": "Statistical observation",
                "text": f"Higher variation was observed in: {names}. These are relative descriptive comparisons, not workload limits.",
            })

    quality = report["quality"]
    excluded = int(quality["excluded_sessions"])
    missing = int(quality["missing_measurements"])
    invalid = int(quality["invalid_measurements"])
    observations.append({
        "section": "Statistical observation",
        "text": (
            f"{excluded} session(s) were excluded by the data-quality screen; "
            f"{missing} missing and {invalid} invalid measurement issue records were present."
        ),
    })
    observations.append({
        "section": "Interpretation",
        "text": (
            "Observed differences describe this synthetic dataset only. Device configuration, small samples, "
            "playing context, and missing observations limit interpretation; no tactical or medical conclusion is implied."
        ),
    })
    return observations


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
        "## Performance overview",
        "",
        (
            f"Latest eligible session: {report['sessions'].iloc[-1]['match_date']:%d %b %Y}. "
            "The automated observations below compare valid measurements with the previous valid session "
            "and with earlier athlete-specific historical observations."
            if not report["sessions"].empty
            else "No analysis-eligible sessions were available."
        ),
        "",
        "## Statistical observations",
        "",
    ]
    for observation in build_narrative(report):
        if observation["section"] == "Statistical observation":
            lines.append(f"- {observation['text']}")

    lines.extend([
        "",
        "## Interpretive limitations",
        "",
    ])
    for observation in build_narrative(report):
        if observation["section"] == "Interpretation":
            lines.append(f"- {observation['text']}")

    lines.extend([
        "## Combined metrics",
        "",
        "| Metric | Value | Aggregation | Valid sessions |",
        "|---|---:|---|---:|",
    ])
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
