"""Create a polished, athlete-specific PDF report with vector trend charts."""
from html import escape
from io import BytesIO

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import metrics as m
from .formatting import format_metric, format_percent
from .theme import BRAND


PAGE_WIDTH, PAGE_HEIGHT = letter
INK = colors.HexColor("#17212B")
MUTED = colors.HexColor("#64748B")
PALE = colors.HexColor("#F4F6F8")
GRID = colors.HexColor("#E5EAF0")
ACCENT = colors.HexColor(BRAND)
BLUE = colors.HexColor("#2563EB")
GREEN = colors.HexColor("#047857")
CHART_COLORS = [ACCENT, BLUE, GREEN]


class MetricTrendChart(Flowable):
    """Draw a compact per-athlete time series while preserving missing-data gaps."""

    def __init__(self, sessions: pd.DataFrame, column: str, width: float, height: float = 178):
        super().__init__()
        self.sessions = sessions
        self.column = column
        self.width = width
        self.height = height

    def wrap(self, available_width, available_height):
        return min(self.width, available_width), self.height

    def draw(self):
        canvas = self.canv
        width, height = self.width, self.height
        label, _, unit = m.METRIC_INFO[self.column]
        sessions = self.sessions
        values = pd.to_numeric(sessions[self.column], errors="coerce").to_numpy(dtype=float)
        valid = np.isfinite(values)

        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.setFillColor(colors.white)
        canvas.roundRect(0, 0, width, height, 7, stroke=1, fill=1)
        canvas.setFillColor(INK)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawString(10, height - 15, f"{label} ({unit})")

        if not valid.any():
            canvas.setFillColor(MUTED)
            canvas.setFont("Helvetica", 8)
            canvas.drawCentredString(width / 2, height / 2, "No valid measurements in eligible sessions")
            canvas.restoreState()
            return

        left, right = 42, width - 12
        bottom, top = 31, height - 37
        observed = values[valid]
        low, high = float(observed.min()), float(observed.max())
        span = high - low
        padding = span * 0.12 if span else max(abs(high) * 0.12, 1.0)
        low -= padding
        high += padding

        def y_coord(value):
            return bottom + (value - low) / (high - low) * (top - bottom)

        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(MUTED)
        for step in range(4):
            value = low + (high - low) * step / 3
            y = y_coord(value)
            canvas.setStrokeColor(GRID)
            canvas.setLineWidth(0.5)
            canvas.line(left, y, right, y)
            canvas.drawRightString(left - 4, y - 2, f"{value:.1f}")

        count = len(values)
        x_positions = (
            [left + (right - left) * index / (count - 1) for index in range(count)]
            if count > 1
            else [(left + right) / 2]
        )

        mean = float(observed.mean())
        if len(observed) >= m.MIN_SESSIONS_FOR_REFERENCE_BAND:
            mean_y = y_coord(mean)
            canvas.saveState()
            canvas.setStrokeColor(BLUE)
            canvas.setDash(2, 2)
            canvas.setLineWidth(0.8)
            canvas.line(left, mean_y, right, mean_y)
            canvas.restoreState()
            canvas.setFillColor(BLUE)
            canvas.setFont("Helvetica", 6)
            canvas.drawRightString(right, min(top - 3, mean_y + 3), "Historical mean")

        canvas.setStrokeColor(ACCENT)
        canvas.setFillColor(ACCENT)
        canvas.setLineWidth(1.5)
        previous = None
        for index, value in enumerate(values):
            if not np.isfinite(value):
                previous = None
                continue
            point = (x_positions[index], y_coord(value))
            if previous is not None:
                canvas.line(previous[0], previous[1], point[0], point[1])
            canvas.circle(point[0], point[1], 2.2, stroke=0, fill=1)
            previous = point

        date_indexes = sorted(set(
            np.linspace(0, count - 1, num=min(5, count), dtype=int).tolist()
        ))
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.5)
        for index in date_indexes:
            date_label = pd.Timestamp(sessions.iloc[index]["match_date"]).strftime("%d %b")
            canvas.drawCentredString(x_positions[index], bottom - 12, date_label)

        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(
            left,
            8,
            f"{int(valid.sum())} valid of {count} eligible sessions"
            + (f" | mean n={int(valid.sum())}" if valid.sum() >= m.MIN_SESSIONS_FOR_REFERENCE_BAND else ""),
        )
        canvas.restoreState()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=23, leading=27, textColor=INK, alignment=TA_LEFT, spaceAfter=5,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle", parent=base["Normal"], fontSize=10, leading=14,
            textColor=MUTED, spaceAfter=4,
        ),
        "section": ParagraphStyle(
            "ReportSection", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=13, leading=16, textColor=INK, spaceBefore=8, spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "ReportBody", parent=base["BodyText"], fontSize=8.5, leading=12,
            textColor=INK, spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "ReportSmall", parent=base["BodyText"], fontSize=7.2, leading=9.5,
            textColor=MUTED, spaceAfter=3,
        ),
        "callout": ParagraphStyle(
            "ReportCallout", parent=base["BodyText"], fontName="Helvetica-Bold",
            fontSize=8.3, leading=11, textColor=colors.HexColor("#593A00"),
        ),
    }


def _table(data, widths, header=True, font_size=7.5):
    table = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("GRID", (0, 0), (-1, -1), 0.35, GRID),
    ]
    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), PALE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    table.setStyle(TableStyle(commands))
    return table


def _page_chrome(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_HEIGHT - 7, PAGE_WIDTH, 7, stroke=0, fill=1)
    canvas.setStrokeColor(GRID)
    canvas.line(doc.leftMargin, 30, PAGE_WIDTH - doc.rightMargin, 30)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(doc.leftMargin, 19, "SYNTHETIC DATA | Independent portfolio prototype")
    canvas.drawRightString(PAGE_WIDTH - doc.rightMargin, 19, f"Page {doc.page}")
    canvas.restoreState()


def _metric_rows(report):
    rows = [["Metric", "Combined value", "Valid sessions", "Aggregation"]]
    for row in report["metrics"].itertuples(index=False):
        rows.append([
            row.metric,
            format_metric(row.column, row.value),
            f"{row.n_valid} of {row.n_sessions}",
            row.method,
        ])
    return rows


def _baseline_rows(report):
    rows = [[
        "Metric", "Latest", "Previous", "Historical mean",
        "Historical median", "Change vs mean", "Baseline n",
    ]]
    for row in report["latest_baseline"].itertuples(index=False):
        rows.append([
            m.METRIC_INFO[row.column][0],
            format_metric(row.column, row.latest),
            format_metric(row.column, row.previous),
            format_metric(row.column, row.historical_mean),
            format_metric(row.column, row.historical_median),
            format_percent(row.pct_baseline) or "-",
            str(row.baseline_n),
        ])
    return rows


def _chart_grid(sessions, columns, width):
    chart_width = (width - 10) / 2
    charts = [
        MetricTrendChart(sessions, column, chart_width)
        for column in columns
    ]
    data = []
    for index in range(0, len(charts), 2):
        left = charts[index]
        right = charts[index + 1] if index + 1 < len(charts) else ""
        data.append([left, right])
    table = Table(
        data,
        colWidths=[chart_width + 5, chart_width + 5],
        rowHeights=[186] * len(data),
        hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def render_report_pdf(report: dict) -> bytes:
    """Render a professional, multi-page PDF with charts for the selected athlete."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.48 * inch,
        bottomMargin=0.58 * inch,
        title=f"Athlete Workload Report - {report['athlete_name']}",
        author="GPS Workload Intelligence - Synthetic Prototype",
    )
    styles = _styles()
    story = []
    athlete_name = escape(str(report["athlete_name"]))
    latest = report["sessions"].iloc[-1] if not report["sessions"].empty else None

    story.append(Paragraph("ATHLETE WORKLOAD REPORT", styles["title"]))
    story.append(Paragraph(
        f"{athlete_name} &nbsp;|&nbsp; {escape(str(report['position']))} "
        f"&nbsp;|&nbsp; {escape(str(report['club']))} &nbsp;|&nbsp; "
        f"ID: {escape(str(report['athlete_id']))}",
        styles["subtitle"],
    ))
    story.append(Paragraph(
        f"Reporting period: {report['period_start']:%d %b %Y} to {report['period_end']:%d %b %Y}",
        styles["subtitle"],
    ))
    story.append(Spacer(1, 7))

    disclaimer = Table([[
        Paragraph(
            "<b>SYNTHETIC DEMO DATA.</b> Fictional athlete, fixture and GPS information. "
            "Independent portfolio prototype; not an official GameOn Collective product "
            "or a real-athlete assessment.",
            styles["callout"],
        )
    ]], colWidths=[doc.width])
    disclaimer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF4DB")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#F2D18B")),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(disclaimer)

    story.append(Paragraph("Performance overview", styles["section"]))
    eligible_count = len(report["sessions"])
    recorded_count = len(report["all_sessions"])
    if latest is not None:
        minutes = f"{int(latest['minutes_played'])} min"
        if bool(latest["minutes_estimated"]):
            minutes = "~" + minutes
        overview = (
            f"The latest analysis-eligible session was on {latest['match_date']:%d %b %Y} "
            f"against {escape(str(latest['opponent']))} ({minutes}). "
            f"{eligible_count} of {recorded_count} recorded sessions passed the analysis-eligibility screen."
        )
    else:
        overview = f"No analysis-eligible sessions were available among {recorded_count} recorded sessions."
    story.append(Paragraph(overview, styles["body"]))

    key_columns = [
        "total_distance_km", "distance_per_min", "hsr_distance_m",
        "sprint_count", "player_load_au", "top_speed_kmh",
    ]
    stats = report["metrics"].set_index("column")
    kpi_data = []
    for start in range(0, len(key_columns), 3):
        kpi_row = []
        for column in key_columns[start:start + 3]:
            metric = stats.loc[column]
            kpi_row.append(Paragraph(
                f"<font color='#64748B'>{escape(str(metric['metric']))}</font><br/>"
                f"<b>{escape(format_metric(column, metric['value']))}</b><br/>"
                f"<font size='7' color='#64748B'>{int(metric['n_valid'])} valid sessions</font>",
                styles["body"],
            ))
        kpi_data.append(kpi_row)
    kpi_table = Table(kpi_data, colWidths=[doc.width / 3] * 3)
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE),
        ("BOX", (0, 0), (-1, -1), 0.5, GRID),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, GRID),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)

    story.append(Paragraph("Automated observations", styles["section"]))
    comparison_count = 0
    for observation in report.get("narrative", []):
        text_value = str(observation["text"])
        if "from the previous valid session" in text_value or "from the historical mean" in text_value:
            if comparison_count >= 3:
                continue
            comparison_count += 1
        label = escape(str(observation["section"]))
        text = escape(text_value)
        story.append(Paragraph(f"<b>{label}:</b> {text}", styles["body"]))

    if not report["latest_baseline"].empty:
        story.append(Paragraph("Latest session: selected historical comparisons", styles["section"]))
        story.append(_table(
            _baseline_rows(report),
            [74, 56, 56, 64, 64, 61, 43],
            font_size=6.5,
        ))

    story.append(PageBreak())
    story.append(Paragraph("Session trends", styles["title"]))
    story.append(Paragraph(
        "The comparison table on the previous page covers all available metrics. Historical statistics "
        "exclude the evaluated session; baseline n counts valid prior sessions for each metric.",
        styles["small"],
    ))
    story.append(Paragraph(
        "Eligible sessions only. Lines break at missing measurements; no missing value is treated as zero. "
        "Historical-average lines appear only when at least "
        f"{m.MIN_SESSIONS_FOR_REFERENCE_BAND} valid observations are available.",
        styles["body"],
    ))
    story.append(Spacer(1, 5))
    primary_charts = [
        "total_distance_km", "hsr_distance_m", "sprint_count", "player_load_au",
    ]
    story.append(_chart_grid(report["sessions"], primary_charts, doc.width))

    story.append(PageBreak())
    story.append(Paragraph("Additional individual trends", styles["title"]))
    story.append(_chart_grid(
        report["sessions"],
        ["distance_per_min", "accel_count", "decel_count"],
        doc.width,
    ))

    story.append(PageBreak())
    story.append(Paragraph("Combined metrics and data context", styles["title"]))
    story.append(Paragraph("Combined metrics", styles["section"]))
    story.append(_table(
        _metric_rows(report),
        [112, 90, 75, doc.width - 277],
        font_size=6.8,
    ))

    quality = report["quality"]
    story.append(Paragraph("Data quality and limitations", styles["section"]))
    quality_summary = (
        f"{quality['usable_sessions']} eligible of {quality['total_sessions']} sessions; "
        f"{quality['excluded_sessions']} excluded; "
        f"{quality['missing_measurements']} missing and {quality['invalid_measurements']} invalid "
        "measurement issue records; "
        f"{quality['approximate_minutes']} approximate-minute records."
    )
    story.append(Paragraph(escape(quality_summary), styles["body"]))
    story.append(Paragraph(
        "These descriptive statistics are specific to this synthetic sample. GPS values depend on device "
        "configuration, sampling and processing; missing observations and small samples limit interpretation. "
        "The report does not infer tactical effectiveness, medical status, fatigue, or injury risk and should "
        "not be used for selection, medical, or training decisions.",
        styles["small"],
    ))

    doc.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome)
    return buffer.getvalue()
