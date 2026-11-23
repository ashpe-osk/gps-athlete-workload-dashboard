"""Create a polished, athlete-specific PDF report with vector trend charts."""
from html import escape
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import metrics as m
from .formatting import DECIMAL_PLACES, classify_change, format_metric, format_percent
from .theme import CHANGE_LEGEND, REPORT_COLORS, colors_for


PAGE_WIDTH, PAGE_HEIGHT = letter
FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_NAMES = {
    "regular": "Inter-Regular",
    "medium": "Inter-Medium",
    "semibold": "Inter-SemiBold",
    "bold": "Inter-Bold",
}
INK = colors.HexColor(REPORT_COLORS["ink"])
SECONDARY = colors.HexColor(REPORT_COLORS["secondary"])
MUTED = colors.HexColor(REPORT_COLORS["muted"])
PALE = colors.HexColor(REPORT_COLORS["pale"])
GRID = colors.HexColor(REPORT_COLORS["grid"])
ACCENT = colors.HexColor(REPORT_COLORS["accent"])
BLUE = colors.HexColor(REPORT_COLORS["blue"])
PAPER = colors.HexColor(REPORT_COLORS["paper"])
LIGHT_CHANGE_COLORS = colors_for("Light")


def _register_fonts():
    """Register embedded Inter faces with tabular numeral glyphs."""
    registered = set(pdfmetrics.getRegisteredFontNames())
    for font_name in FONT_NAMES.values():
        if font_name not in registered:
            path = FONT_DIR / f"{font_name}.ttf"
            pdfmetrics.registerFont(TTFont(font_name, str(path)))
    pdfmetrics.registerFontFamily(
        "Inter",
        normal=FONT_NAMES["regular"],
        bold=FONT_NAMES["bold"],
        italic=FONT_NAMES["medium"],
        boldItalic=FONT_NAMES["semibold"],
    )


class NoWrapText(Flowable):
    """Draw a single-line table value or note without allowing a line break."""

    def __init__(
        self,
        text: str,
        font_name: str,
        font_size: float,
        color=INK,
        align: str = "LEFT",
        badge: bool = False,
        padding: float = 0,
        allow_condense: bool = False,
    ):
        super().__init__()
        self.text = text
        self.font_name = font_name
        self.font_size = font_size
        self.color = color
        self.align = align
        self.badge = badge
        self.padding = padding
        self.allow_condense = allow_condense
        self.text_width = pdfmetrics.stringWidth(text, font_name, font_size)
        self.horizontal_scale = 1.0

    def wrap(self, available_width, _):
        text_width = self.text_width + (2 * self.padding if self.badge else 0)
        self.horizontal_scale = min(1.0, available_width / text_width) if text_width else 1.0
        if self.horizontal_scale < 1 and (
            not self.allow_condense or self.horizontal_scale < 0.9
        ):
            raise ValueError(f"Non-wrapping text does not fit: {self.text!r}")
        self.width = (
            text_width * self.horizontal_scale
            if self.badge
            else available_width
        )
        self.height = self.font_size + (5 if self.badge else 3)
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        if self.badge:
            canvas.setFillColor(PALE)
            canvas.setStrokeColor(GRID)
            canvas.roundRect(0, 0, self.width, self.height, 4, stroke=1, fill=1)
        canvas.setFillColor(self.color)
        text_width = self.text_width * self.horizontal_scale
        if self.badge:
            x = self.padding
        elif self.align == "RIGHT":
            x = self.width - text_width
        else:
            x = 0
        baseline = (self.height - self.font_size) / 2
        text = canvas.beginText(x, baseline)
        text.setFont(self.font_name, self.font_size)
        text.setHorizScale(self.horizontal_scale * 100)
        text.textOut(self.text)
        canvas.drawText(text)
        canvas.restoreState()


class MetricTrendChart(Flowable):
    """Draw a compact per-athlete time series while preserving missing-data gaps."""

    def __init__(self, sessions: pd.DataFrame, column: str, width: float, height: float = 150):
        super().__init__()
        self.sessions = sessions
        self.column = column
        self.width = width
        self.height = height

    def wrap(self, available_width, _):
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
        canvas.setFillColor(PAPER)
        canvas.roundRect(0, 0, width, height, 7, stroke=1, fill=1)
        canvas.setFillColor(INK)
        canvas.setFont(FONT_NAMES["semibold"], 11)
        canvas.drawString(10, height - 15, f"{label} ({unit})")
        self._draw_legend(canvas, height)

        if not valid.any():
            canvas.setFillColor(MUTED)
            canvas.setFont(FONT_NAMES["regular"], 9)
            canvas.drawCentredString(width / 2, height / 2, "No valid measurements in eligible sessions")
            canvas.restoreState()
            return

        left, right = 35, width - 17
        bottom, top = 31, height - 57
        observed = values[valid]
        low, high = float(observed.min()), float(observed.max())
        span = high - low
        padding = span * 0.12 if span else max(abs(high) * 0.12, 1.0)
        low -= padding
        high += padding

        def y_coord(value):
            return bottom + (value - low) / (high - low) * (top - bottom)

        canvas.setFont(FONT_NAMES["regular"], 9)
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

        date_indexes = range(count)
        date_labels = [
            pd.Timestamp(sessions.iloc[index]["match_date"]).strftime("%d %b")
            for index in date_indexes
        ]
        date_widths = [
            pdfmetrics.stringWidth(label, FONT_NAMES["regular"], 9)
            for label in date_labels
        ]
        date_spacing = (right - left) / (count - 1) if count > 1 else width
        split_date_labels = max(date_widths, default=0) > date_spacing
        if split_date_labels:
            date_labels = [
                pd.Timestamp(sessions.iloc[index]["match_date"]).strftime("%d/%m")
                for index in date_indexes
            ]
            date_widths = [
                pdfmetrics.stringWidth(label, FONT_NAMES["regular"], 9)
                for label in date_labels
            ]
            split_date_labels = max(date_widths, default=0) > date_spacing

        canvas.setFillColor(MUTED)
        canvas.setFont(FONT_NAMES["regular"], 9)
        for index, date_label in zip(date_indexes, date_labels):
            if split_date_labels:
                date = pd.Timestamp(sessions.iloc[index]["match_date"])
                canvas.drawCentredString(x_positions[index], bottom - 12, date.strftime("%d"))
                canvas.drawCentredString(x_positions[index], bottom - 22, date.strftime("%b"))
            else:
                canvas.drawCentredString(x_positions[index], bottom - 12, date_label)

        canvas.setFillColor(MUTED)
        canvas.restoreState()

    @staticmethod
    def _draw_legend(canvas, height):
        legend_y = height - 33
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.5)
        canvas.line(10, legend_y + 3, 22, legend_y + 3)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT_NAMES["regular"], 9)
        canvas.drawString(26, legend_y, "Metric")
        canvas.saveState()
        canvas.setStrokeColor(BLUE)
        canvas.setDash(2, 2)
        canvas.setLineWidth(1)
        canvas.line(77, legend_y + 3, 89, legend_y + 3)
        canvas.restoreState()
        canvas.setFillColor(MUTED)
        canvas.drawString(93, legend_y, "Historical mean")


class ChartLegendKey(Flowable):
    """Explain the session and historical-reference lines in the empty grid cell."""

    def __init__(self, width: float, height: float = 150):
        super().__init__()
        self.width = width
        self.height = height

    def wrap(self, available_width, _):
        return min(self.width, available_width), self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.setFillColor(PAPER)
        canvas.roundRect(0, 0, self.width, self.height, 7, stroke=1, fill=1)
        canvas.setFillColor(INK)
        canvas.setFont(FONT_NAMES["semibold"], 11)
        canvas.drawString(10, self.height - 19, "How to read these charts")
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1.5)
        canvas.line(12, self.height - 43, 32, self.height - 43)
        canvas.setFillColor(INK)
        canvas.setFont(FONT_NAMES["regular"], 9)
        canvas.drawString(39, self.height - 46, "Metric")
        canvas.saveState()
        canvas.setStrokeColor(BLUE)
        canvas.setDash(2, 2)
        canvas.setLineWidth(1)
        canvas.line(12, self.height - 66, 32, self.height - 66)
        canvas.restoreState()
        canvas.setFillColor(INK)
        canvas.drawString(39, self.height - 69, "Historical mean")
        canvas.setFillColor(MUTED)
        canvas.drawString(12, self.height - 94, "Reference shown with at least")
        canvas.drawString(
            12, self.height - 107,
            f"{m.MIN_SESSIONS_FOR_REFERENCE_BAND} valid measurements.",
        )
        canvas.drawString(12, self.height - 130, "Each date is one eligible session;")
        canvas.drawString(12, self.height - 143, "gaps show missing measurements.")
        canvas.restoreState()


class KpiCard(Flowable):
    """Render a KPI label, value, and optional count on separate baselines."""

    def __init__(self, metric: str, value: str, count_note: str, width: float):
        super().__init__()
        self.metric = metric
        self.value = value
        self.count_note = count_note
        self.width = width
        self.height = 70

    def wrap(self, available_width, _):
        return min(self.width, available_width), self.height

    def draw(self):
        canvas = self.canv
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.setFillColor(PALE)
        canvas.roundRect(3, 3, self.width - 6, self.height - 6, 6, stroke=1, fill=1)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT_NAMES["medium"], 10.5)
        canvas.drawString(12, self.height - 18, self.metric)
        canvas.setFillColor(INK)
        canvas.setFont(FONT_NAMES["bold"], 22)
        canvas.drawString(12, self.height - 44, self.value)
        if self.count_note:
            canvas.setFillColor(MUTED)
            canvas.setFont(FONT_NAMES["regular"], 9)
            canvas.drawString(12, 9, self.count_note)
        canvas.restoreState()


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"], fontName=FONT_NAMES["bold"],
            fontSize=24, leading=29, textColor=INK, alignment=TA_LEFT, spaceAfter=5,
        ),
        "athlete": ParagraphStyle(
            "ReportAthlete", parent=base["Normal"], fontName=FONT_NAMES["semibold"],
            fontSize=16, leading=20, textColor=INK, spaceAfter=4,
        ),
        "period": ParagraphStyle(
            "ReportPeriod", parent=base["Normal"], fontName=FONT_NAMES["regular"],
            fontSize=11, leading=14, textColor=SECONDARY, spaceAfter=4,
        ),
        "section": ParagraphStyle(
            "ReportSection", parent=base["Heading2"], fontName=FONT_NAMES["bold"],
            fontSize=15, leading=18, textColor=INK, spaceBefore=8, spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "ReportBody", parent=base["BodyText"], fontName=FONT_NAMES["regular"],
            fontSize=11, leading=14,
            textColor=INK, spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "ReportSmall", parent=base["BodyText"], fontName=FONT_NAMES["regular"],
            fontSize=9, leading=11, textColor=MUTED, spaceAfter=3,
        ),
        "notes": ParagraphStyle(
            "ReportNotes", parent=base["BodyText"], fontName=FONT_NAMES["regular"],
            fontSize=11, leading=14, textColor=INK, spaceAfter=3,
        ),
        "caption": ParagraphStyle(
            "ReportCaption", parent=base["BodyText"], fontName=FONT_NAMES["regular"],
            fontSize=11, leading=14, textColor=MUTED, spaceAfter=3,
        ),
        "table": ParagraphStyle(
            "ReportTable", parent=base["BodyText"], fontName=FONT_NAMES["regular"],
            fontSize=10.5, leading=13, textColor=INK,
        ),
        "table_metric": ParagraphStyle(
            "ReportTableMetric", parent=base["BodyText"], fontName=FONT_NAMES["regular"],
            fontSize=10.5, leading=13, textColor=INK, splitLongWords=0,
        ),
        "table_header": ParagraphStyle(
            "ReportTableHeader", parent=base["BodyText"], fontName=FONT_NAMES["semibold"],
            fontSize=10, leading=12, textColor=INK,
        ),
        "callout": ParagraphStyle(
            "ReportCallout", parent=base["BodyText"], fontName=FONT_NAMES["bold"],
            fontSize=11, leading=14, textColor=colors.HexColor(REPORT_COLORS["warning"]),
        ),
    }


def _table(data, width):
    styles = _styles()
    cells = []
    for row_index, row in enumerate(data):
        rendered_row = []
        for column_index, value in enumerate(row):
            if isinstance(value, Flowable):
                rendered_row.append(value)
            elif column_index == 0 and row_index:
                rendered_row.append(Paragraph(escape(str(value)), styles["table_metric"]))
            else:
                is_header = row_index == 0
                font_name = FONT_NAMES["semibold"] if is_header else FONT_NAMES["regular"]
                font_size = 10 if is_header else 10.5
                rendered_row.append(NoWrapText(
                    str(value),
                    font_name,
                    font_size,
                    color=INK,
                    align="LEFT" if column_index == 0 else "RIGHT",
                    allow_condense=is_header and column_index == 4,
                ))
        cells.append(rendered_row)

    column_widths = [width * 0.32] + [width * 0.68 / 5] * 5
    table = Table(cells, colWidths=column_widths, repeatRows=1, hAlign="LEFT")
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (4, 0), (4, -1), 0.5),
        ("RIGHTPADDING", (4, 0), (4, -1), 0.5),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, GRID),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
    ]
    table.setStyle(TableStyle(commands))
    return table


def _page_chrome(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_HEIGHT - 7, PAGE_WIDTH, 7, stroke=0, fill=1)
    canvas.setStrokeColor(GRID)
    canvas.line(doc.leftMargin, 52, PAGE_WIDTH - doc.rightMargin, 52)
    canvas.setFillColor(INK)
    canvas.setFont(FONT_NAMES["medium"], 11)
    canvas.drawCentredString(PAGE_WIDTH / 2, 36, str(doc.page))
    canvas.restoreState()


def _baseline_rows(report):
    rows = [[
        "Metric", "Latest", "Previous", "Hist. mean", "Change vs mean", "Base n",
    ]]
    for row in report["latest_baseline"].itertuples(index=False):
        label, _, unit = m.METRIC_INFO[row.column]
        rows.append([
            f"{label} ({unit})",
            _format_number(row.column, row.latest),
            _format_number(row.column, row.previous),
            _format_number(row.column, row.historical_mean),
            _comparison_change(row.pct_baseline),
            str(row.baseline_n),
        ])
    return rows


def _format_number(column, value):
    if pd.isna(value):
        return "—"
    decimals = DECIMAL_PLACES[column]
    return f"{float(value):,.{decimals}f}"


def _compact_flag(flag):
    prefix = "High variation (CV "
    if flag.startswith(prefix) and flag.endswith(")"):
        return f"High CV {flag[len(prefix):-1]}"
    return flag


def _observation_note_lines(report):
    parts = str(report["notes"]).split(" | ")
    variation = parts[0].replace("High-speed running ", "HSR ").replace(", ", " · ")
    quality = " · ".join(parts[1:])
    return [variation, quality] if quality else [variation]


def _comparison_change(value):
    if pd.isna(value):
        label = "—"
    elif abs(float(value)) < 0.05:
        label = "– 0.0%"
    else:
        arrow = "▲" if value > 0 else "▼"
        label = f"{arrow} {format_percent(value)}"
    token, bold = classify_change(value)
    return NoWrapText(
        label,
        FONT_NAMES["bold"] if bold else FONT_NAMES["regular"],
        10.5,
        color=colors.HexColor(LIGHT_CHANGE_COLORS[token]),
        align="RIGHT",
    )


def _change_markup(label, value):
    if not label or label == "—":
        label = "—"
    token, bold = classify_change(value)
    color = LIGHT_CHANGE_COLORS[token]
    font_name = FONT_NAMES["bold"] if bold else FONT_NAMES["regular"]
    return f'<font name="{font_name}" color="{color}">{escape(label)}</font>'


def _observation_rows(report):
    data = [[
        "Metric", "Latest", "vs previous session", "vs historical mean", "Flag",
    ]]
    for _, row in report["observations"].iterrows():
        latest = escape(str(row["Latest"]))
        data.append([
            escape(str(row["Metric"])),
            NoWrapText(
                latest,
                FONT_NAMES["regular"],
                10.5,
                color=INK,
                align="RIGHT",
            ),
            Paragraph(
                _change_markup(row["vs previous session"], row["pct_previous"]),
                _styles()["table"],
            ),
            Paragraph(
                _change_markup(row["vs historical mean"], row["pct_historical_mean"]),
                _styles()["table"],
            ),
            (
                NoWrapText(
                    _compact_flag(str(row["Flag"])),
                    FONT_NAMES["medium"],
                    10.5,
                    color=SECONDARY,
                    badge=True,
                    padding=5,
                )
                if row["Flag"]
                else Paragraph("", _styles()["table"])
            ),
        ])
    return data


def _observation_table(report, width):
    column_widths = [width * percent for percent in (0.26, 0.20, 0.18, 0.18, 0.18)]
    table = Table(
        _observation_rows(report),
        colWidths=column_widths,
        repeatRows=1,
        hAlign="LEFT",
    )
    commands = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAMES["regular"]),
        ("FONTSIZE", (0, 0), (-1, -1), 10.5),
        ("FONTNAME", (0, 0), (-1, 0), FONT_NAMES["semibold"]),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, GRID),
        ("ALIGN", (1, 1), (3, -1), "RIGHT"),
    ]
    for row_index in range(2, len(report["observations"]) + 1, 2):
        commands.append(("BACKGROUND", (0, row_index), (-1, row_index), PALE))
    for row_index in range(1, len(report["observations"]) + 1):
        commands.append(("LINEBELOW", (0, row_index), (-1, row_index), 0.35, GRID))
    table.setStyle(TableStyle(commands))
    return table


def _chart_grid_rows(sessions, columns, width):
    chart_width = (width - 4) / 2
    charts = [
        MetricTrendChart(sessions, column, chart_width)
        for column in columns
    ]
    rows = []
    for index in range(0, len(charts), 2):
        left = charts[index]
        right = (
            charts[index + 1]
            if index + 1 < len(charts)
            else ChartLegendKey(chart_width)
        )
        row = Table(
            [[left, right]],
            colWidths=[chart_width + 2, chart_width + 2],
            rowHeights=[158],
            hAlign="LEFT",
        )
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        rows.append(row)
    return rows


def _kpi_count_note(column, valid_count, eligible_count):
    if column == "top_speed_kmh" and int(valid_count) != eligible_count:
        return f"{int(valid_count)} of {eligible_count} sessions"
    return ""


def render_report_pdf(report: dict) -> bytes:
    """Render a concise athlete-specific report with charts and compact comparisons."""
    _register_fonts()
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.43 * inch,
        rightMargin=0.43 * inch,
        topMargin=0.42 * inch,
        bottomMargin=0.85 * inch,
        title=f"Athlete Workload Report - {report['athlete_name']}",
        author="GPS Workload Intelligence - Synthetic Prototype",
    )
    styles = _styles()
    story = []
    athlete_name = escape(str(report["athlete_name"]))
    latest = report["sessions"].iloc[-1] if not report["sessions"].empty else None

    story.append(Paragraph("ATHLETE WORKLOAD REPORT", styles["title"]))
    story.append(Paragraph(
        f"<font name='{FONT_NAMES['bold']}'>{athlete_name}</font> "
        f"| {escape(str(report['position']))} | {escape(str(report['club']))} "
        f"| ID: {escape(str(report['athlete_id']))}",
        styles["athlete"],
    ))
    story.append(Paragraph(
        f"Reporting period: {report['period_start']:%d %b %Y} to {report['period_end']:%d %b %Y}",
        styles["period"],
    ))
    story.append(HRFlowable(
        width="100%", thickness=1.5, color=ACCENT, spaceBefore=3, spaceAfter=8,
    ))
    eligible_count = len(report["sessions"])

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
            count_label = _kpi_count_note(column, metric["n_valid"], eligible_count)
            kpi_row.append(KpiCard(
                str(metric["metric"]),
                format_metric(column, metric["value"]),
                count_label,
                doc.width / 3,
            ))
        kpi_data.append(kpi_row)
    kpi_table = Table(
        kpi_data,
        colWidths=[doc.width / 3] * 3,
        rowHeights=[70] * len(kpi_data),
    )
    kpi_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    latest_date = latest["match_date"].strftime("%d %b %Y") if latest is not None else "not available"
    story.append(KeepTogether([
        kpi_table,
        Paragraph(
            f"Based on {eligible_count} eligible sessions ({latest_date} latest).",
            styles["notes"],
        ),
    ]))

    observation_block = [
        Paragraph("Automated observations", styles["section"]),
        _observation_table(report, doc.width),
        Paragraph(CHANGE_LEGEND, styles["small"]),
        *[
            NoWrapText(line, FONT_NAMES["regular"], 11, color=INK)
            for line in _observation_note_lines(report)
        ],
    ]
    story.append(KeepTogether(observation_block))

    story.append(PageBreak())
    if not report["latest_baseline"].empty:
        baseline_block = [
            Paragraph("Latest session vs historical baseline", styles["title"]),
            _table(
                _baseline_rows(report),
                doc.width,
            ),
            Paragraph(
                "Historical baseline excludes the evaluated session. n is the valid prior-session count per metric.",
                styles["caption"],
            ),
        ]
        story.append(KeepTogether(baseline_block))

    story.append(Spacer(1, 9))
    trend_heading = Paragraph("Individual session trends", styles["section"])
    chart_rows = _chart_grid_rows(
        report["sessions"],
        [
            "total_distance_km", "distance_per_min", "hsr_distance_m",
            "sprint_count", "player_load_au", "accel_count", "decel_count",
        ],
        doc.width,
    )
    if chart_rows:
        story.append(KeepTogether([
            trend_heading,
            Paragraph(
                "Eligible sessions only; missing values remain gaps. Dotted reference: historical mean "
                f"(at least {m.MIN_SESSIONS_FOR_REFERENCE_BAND} valid observations).",
                styles["caption"],
            ),
            chart_rows[0],
        ]))
        story.extend(KeepTogether([row]) for row in chart_rows[1:])

    footer = [
        Paragraph("Data quality and limitations", styles["section"]),
        Paragraph(
            "GPS values are subject to missing-data, device-configuration, and small-sample limitations.<br/>"
            "<b>Synthetic demo data; not for selection, medical, or training decisions.</b>",
            styles["small"],
        ),
    ]
    story.append(KeepTogether(footer))

    doc.build(story, onFirstPage=_page_chrome, onLaterPages=_page_chrome)
    return buffer.getvalue()
