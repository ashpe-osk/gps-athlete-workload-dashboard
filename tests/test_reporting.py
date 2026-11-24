"""Tests for shared formatting, quality summaries, reports, and visual builders."""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from reportlab.pdfbase import pdfmetrics

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import charts, metrics as m, pdf_report, quality, report  # noqa: E402
from src.cleaning import clean_pipeline  # noqa: E402
from src.formatting import classify_change, format_metric, format_minutes, format_percent  # noqa: E402
from src import theme as theme_module  # noqa: E402
from src.theme import THEMES, colors_for  # noqa: E402


@pytest.fixture(scope="module")
def cleaned_data():
    return clean_pipeline()


def test_shared_formatting_handles_units_missing_values_and_minutes():
    assert format_metric("total_distance_km", 9.245) == "9.24 km"
    assert format_metric("total_distance_km", np.nan) == "—"
    assert format_metric("hsr_distance_m_per90", 420) == "420 m / 90 min"
    assert format_percent(-2.25) == "-2.2%"
    assert format_percent(np.nan) is None
    assert format_minutes(78, estimated=True) == "~78 min"
    with pytest.raises(KeyError):
        format_metric("unrecognized_metric", 1)


@pytest.mark.parametrize(
    ("value", "token", "bold"),
    [
        ("▲ +4.9%", "change_neutral", False),
        ("▼ -4.9%", "change_neutral", False),
        ("▲ +5.0%", "change_increase", False),
        ("▼ -5.0%", "change_decrease", False),
        ("▲ +15.0%", "change_increase", False),
        ("▼ -15.0%", "change_decrease", False),
        ("▲ +15.1%", "change_increase", True),
        ("▼ -15.1%", "change_decrease", True),
        ("– 0.0%", "change_neutral", False),
        ("—", "change_neutral", False),
        (None, "change_neutral", False),
    ],
)
def test_change_classification_uses_named_thresholds(value, token, bold):
    assert classify_change(value) == (token, bold)


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_dataframe_style_uses_selected_theme_colors(theme):
    styler = theme_module.style_dataframe(pd.DataFrame({"Metric": ["Distance"]}), theme)
    html = styler.to_html()
    colors = colors_for(theme)

    assert colors["surface"] in html
    assert colors["text"] in html


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_app_css_styles_warning_and_metric_delta_for_selected_theme(theme):
    css = theme_module.app_css(theme)
    colors = colors_for(theme)

    assert '[data-testid="stAlertContentWarning"]' in css
    assert '[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"])' in css
    assert '[data-testid="stMetricDelta"]' in css
    assert f'--warning-bg: {colors["warning_bg"]}' in css
    assert f'--warning-text: {colors["warning_text"]}' in css
    assert f'--metric-delta-bg: {colors["metric_delta_bg"]}' in css
    assert f'--metric-delta-text: {colors["metric_delta_text"]}' in css


def test_quality_summary_and_register_retain_audit_context(cleaned_data):
    sessions, issues = cleaned_data
    summary = quality.quality_summary(sessions, issues)
    register = quality.issue_register(sessions, issues)

    assert summary["total_sessions"] == len(sessions)
    assert summary["excluded_sessions"] == 1
    assert summary["issue_records"] == len(issues)
    assert summary["affected_sessions"] > 0
    assert len(register) == len(issues)
    assert {"athlete_name", "quality_status", "issue_label"} <= set(register.columns)


def test_report_calls_out_synthetic_scope_and_respects_analysis_eligibility(cleaned_data):
    sessions, issues = cleaned_data
    athlete_id = sessions["athlete_id"].iloc[0]
    payload = report.build_report(sessions, issues, athlete_id)
    markdown = report.render_report_markdown(payload)

    assert len(payload["sessions"]) == len(
        m.usable_sessions(sessions[sessions["athlete_id"] == athlete_id])
    )
    assert "Automated observations" in markdown
    assert "| Metric | Latest | vs previous session | vs historical mean | Flag |" in markdown
    assert "Latest session vs historical baseline" in markdown
    assert "Synthetic demo data;" in markdown
    assert markdown.count("not for selection, medical, or training decisions") == 1
    assert "Combined metrics" not in markdown
    assert "Statistical observation:" not in markdown
    assert "Combined value" not in markdown
    with pytest.raises(ValueError, match="No sessions found"):
        report.build_report(sessions, issues, "unknown-athlete")


def test_pdf_report_is_a_multi_page_athlete_specific_document(cleaned_data):
    sessions, issues = cleaned_data
    athlete_id = sessions["athlete_id"].iloc[0]
    payload = report.build_report(sessions, issues, athlete_id)
    pdf = pdf_report.render_report_pdf(payload)

    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert len(pdf) > 10_000
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) <= 3
    assert all(font_name.encode() in pdf for font_name in pdf_report.FONT_NAMES.values())
    assert b"/FontFile2" in pdf


def test_pdf_table_columns_flags_and_notes_stay_compact(cleaned_data):
    sessions, issues = cleaned_data
    payload = report.build_report(sessions, issues, sessions["athlete_id"].iloc[0])
    pdf_report._register_fonts()

    observation_table = pdf_report._observation_table(payload, 550)
    assert observation_table._colWidths == pytest.approx([143, 110, 99, 99, 99])
    assert pdf_report._compact_flag("High variation (CV 21%)") == "High CV 21%"
    badges = [
        cell
        for row in observation_table._cellvalues
        for cell in row
        if isinstance(cell, pdf_report.NoWrapText) and cell.badge
    ]
    assert badges
    assert all(badge.text.startswith("High CV ") for badge in badges)
    assert all(badge.text_width + 10 <= 99 - 10 for badge in badges)

    note_lines = pdf_report._observation_note_lines(payload)
    assert len(note_lines) == 2
    assert note_lines[0] == (
        "Highest variation: HSR 21.0% · Sprints 19.0% · Decelerations 15.6%"
    )
    assert note_lines[1] == "1 session excluded · 3 missing values · 1 invalid value"
    assert all(
        pdfmetrics.stringWidth(line, "Inter-Regular", 11) <= 550
        for line in note_lines
    )


def test_pdf_comparison_table_moves_units_to_metric_and_uses_fixed_columns(cleaned_data):
    sessions, issues = cleaned_data
    payload = report.build_report(sessions, issues, sessions["athlete_id"].iloc[0])
    rows = pdf_report._baseline_rows(payload)
    assert rows[0] == [
        "Metric", "Latest", "Previous", "Hist. mean", "Change vs mean", "Base n",
    ]
    assert "Historical median" not in rows[0]
    distance_row = next(row for row in rows[1:] if row[0] == "Distance per minute (m/min)")
    assert all("m/min" not in value for value in distance_row[1:4])
    assert all(" km" not in value for value in distance_row[1:4])

    table = pdf_report._table(rows, 550)
    assert table._colWidths == pytest.approx([176, 74.8, 74.8, 74.8, 74.8, 74.8])
    assert all(
        isinstance(cell, pdf_report.NoWrapText)
        for row in table._cellvalues
        for cell in row[1:]
    )
    assert table._cellvalues[0][4].allow_condense
    assert pdf_report._styles()["table_metric"].splitLongWords == 0


def test_kpi_session_count_is_only_shown_in_top_speed_card():
    assert pdf_report._kpi_count_note("top_speed_kmh", 6, 7) == "6 of 7 sessions"
    assert pdf_report._kpi_count_note("total_distance_km", 6, 7) == ""
    assert pdf_report._kpi_count_note("top_speed_kmh", 7, 7) == ""


def test_kpi_card_labels_values_and_count_have_separate_fitting_baselines(cleaned_data):
    sessions, issues = cleaned_data
    athlete_id = sessions["athlete_id"].iloc[0]
    payload = report.build_report(sessions, issues, athlete_id)
    pdf_report._register_fonts()
    stats = payload["metrics"].set_index("column")
    available_text_width = (
        (pdf_report.PAGE_WIDTH - 2 * 0.43 * 72) / 3
    ) - 24

    for column in (
        "total_distance_km", "distance_per_min", "hsr_distance_m",
        "sprint_count", "player_load_au", "top_speed_kmh",
    ):
        metric = stats.loc[column]
        assert pdfmetrics.stringWidth(
            str(metric["metric"]), "Inter-Medium", 10.5
        ) <= available_text_width
        assert pdfmetrics.stringWidth(
            pdf_report.format_metric(column, metric["value"]),
            "Inter-Bold",
            22,
        ) <= available_text_width

    label_descent = pdfmetrics.getAscentDescent("Inter-Medium", 10.5)[1]
    value_ascent, value_descent = pdfmetrics.getAscentDescent("Inter-Bold", 22)
    count_ascent = pdfmetrics.getAscentDescent("Inter-Regular", 9)[0]
    label_baseline = 70 - 18
    value_baseline = 70 - 44
    count_baseline = 9
    assert label_baseline + label_descent > value_baseline + value_ascent
    assert value_baseline + value_descent > count_baseline + count_ascent


def test_trend_chart_draws_every_date_and_always_shows_mean_legend(cleaned_data):
    class CanvasRecorder:
        def __init__(self):
            self.events = []

        def __getattr__(self, name):
            return lambda *args, **kwargs: self.events.append((name, args))

    sessions, issues = cleaned_data
    athlete_id = sorted(sessions["athlete_id"].unique())[1]
    payload = report.build_report(sessions, issues, athlete_id)
    pdf_report._register_fonts()
    chart_width = (550.08 - 4) / 2
    chart = pdf_report.MetricTrendChart(
        payload["sessions"], "total_distance_km", chart_width,
    )
    canvas = CanvasRecorder()
    chart.canv = canvas
    chart.draw()

    date_labels = [
        args[2]
        for name, args in canvas.events
        if name == "drawCentredString"
    ]
    expected_dates = [
        date.strftime("%d %b")
        for date in payload["sessions"]["match_date"]
    ]
    assert date_labels == expected_dates
    assert any(args[2] == "Historical mean" for name, args in canvas.events if name == "drawString")

    spacing = (chart_width - 17 - 35) / (len(expected_dates) - 1)
    widest_date = max(
        pdfmetrics.stringWidth(label, "Inter-Regular", 9)
        for label in expected_dates
    )
    assert widest_date <= spacing


def test_trend_chart_only_draws_reference_line_with_six_valid_observations(cleaned_data):
    class CanvasRecorder:
        def __init__(self):
            self.events = []

        def __getattr__(self, name):
            return lambda *args, **kwargs: self.events.append((name, args))

    sessions, _ = cleaned_data
    athlete_id = sorted(sessions["athlete_id"].unique())[0]
    athlete = m.usable_sessions(sessions[sessions["athlete_id"] == athlete_id])
    for session_count, expected_dash_count in ((5, 1), (6, 2)):
        sample = athlete.iloc[:session_count].copy()
        sample["total_distance_km"] = np.arange(1, session_count + 1, dtype=float)
        chart = pdf_report.MetricTrendChart(sample, "total_distance_km", 272)
        canvas = CanvasRecorder()
        chart.canv = canvas
        chart.draw()
        assert sum(name == "setDash" for name, _ in canvas.events) == expected_dash_count


def test_seven_trends_fill_the_last_grid_cell_with_a_reading_key(cleaned_data):
    sessions, issues = cleaned_data
    payload = report.build_report(sessions, issues, sessions["athlete_id"].iloc[0])
    chart_rows = pdf_report._chart_grid_rows(
        payload["sessions"], m.TREND_METRICS, 550.08,
    )

    assert len(chart_rows) == 4
    assert isinstance(chart_rows[-1]._cellvalues[0][1], pdf_report.ChartLegendKey)


def test_report_fonts_use_tabular_digits_and_requested_type_scale():
    pdf_report._register_fonts()
    for font_name in pdf_report.FONT_NAMES.values():
        font = pdfmetrics.getFont(font_name)
        digit_widths = {
            font.face.charWidths[ord(character)]
            for character in "0123456789"
        }
        assert len(digit_widths) == 1

    styles = pdf_report._styles()
    assert styles["title"].fontSize == 24
    assert styles["athlete"].fontSize == 16
    assert styles["period"].fontSize == 11
    assert styles["section"].fontSize == 15
    assert styles["body"].fontSize == 11
    assert styles["table"].fontSize == 10.5
    assert styles["table_header"].fontSize == 10
    assert styles["small"].fontSize >= 9


def test_page_number_is_a_centered_plain_digit_with_a_12mm_bottom_margin():
    class CanvasRecorder:
        def __init__(self):
            self.events = []

        def __getattr__(self, name):
            return lambda *args, **kwargs: self.events.append((name, args))

    class Document:
        page = 2
        leftMargin = 40
        rightMargin = 40

    canvas = CanvasRecorder()
    pdf_report._page_chrome(canvas, Document())

    assert ("setFont", ("Inter-Medium", 11)) in canvas.events
    assert ("drawCentredString", (pdf_report.PAGE_WIDTH / 2, 36, "2")) in canvas.events
    assert all(event[0] != "drawRightString" for event in canvas.events)
    assert 36 / 72 * 25.4 >= 12


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_all_plotly_charts_use_theme_legend_text_color(cleaned_data, theme):
    sessions, _ = cleaned_data
    athlete_ids = sorted(sessions["athlete_id"].unique())[:2]
    athlete_id = athlete_ids[0]
    athlete = m.add_per90_columns(
        m.usable_sessions(sessions[sessions["athlete_id"] == athlete_id])
    )
    comparison, _ = m.comparison_table(sessions, athlete_ids)

    figures = [
        charts.workload_composition_chart(athlete, theme),
        charts.match_intensity_scatter(athlete, theme),
        charts.consistency_heatmap(athlete, theme),
        charts.comparison_radar_chart(comparison, theme),
        charts.comparison_box_chart(
            sessions, athlete_ids, "sprint_count_per90", "Sprints", "Sprints / 90", theme
        ),
        charts.comparison_bubble_chart(comparison, theme),
        charts.quality_map_chart(sessions, theme),
    ]

    assert len(figures[0].data) == 2
    assert len(figures[1].data) >= 1
    assert len(figures[2].data) == 1
    assert len(figures[3].data) == len(athlete_ids)
    assert len(figures[4].data) == len(athlete_ids)
    assert len(figures[5].data) >= 1
    quality_map = figures[6]
    assert len(quality_map.data) == 1
    assert len(set(quality_map.data[0].x)) == sessions["match_id"].nunique()
    assert all(
        figure.layout.legend.font.color == colors_for(theme)["text"]
        for figure in figures
    )


@pytest.mark.parametrize("theme", ["Light", "Dark"])
def test_trend_chart_legend_explains_series_and_uses_theme_text_color(cleaned_data, theme):
    sessions, _ = cleaned_data
    athlete_id = sessions["athlete_id"].iloc[0]
    athlete = m.add_per90_columns(
        m.usable_sessions(sessions[sessions["athlete_id"] == athlete_id])
    )
    figure = charts.trend_chart(
        athlete,
        "sprint_count",
        "Sprints",
        "count",
        decimals=0,
        show_rolling=True,
        theme=theme,
        show_labels=True,
    )
    traces = {trace.name: trace for trace in figure.data}
    assert {
        "Session values",
        "Rolling average (3 sessions)",
        "Historical mean",
        "Descriptive mean ± 1 SD",
    } <= set(traces)
    assert traces["Session values"].connectgaps is False
    assert traces["Session values"].text is not None
    assert figure.layout.legend.font.color == colors_for(theme)["text"]
    assert traces["Historical mean"].line.dash == "dot"
    assert traces["Descriptive mean ± 1 SD"].fill == "toself"


def test_observation_table_is_sorted_compact_and_labels_change_direction(cleaned_data):
    sessions, issues = cleaned_data
    payload = report.build_report(sessions, issues, sessions["athlete_id"].iloc[0])
    observations = payload["observations"]

    assert len(observations) == len(m.HISTORICAL_METRICS)
    assert list(observations.columns[:5]) == [
        "column", "Metric", "Latest", "pct_previous", "vs previous session",
    ]
    assert observations["_change_magnitude"].dropna().is_monotonic_decreasing
    assert observations["vs previous session"].map(
        lambda value: value == "—" or value.startswith(("▲", "▼", "–"))
    ).all()
    assert " | " in payload["notes"]


def test_date_range_tokens_and_calendar_selectors_have_accessible_contrast():
    for theme in theme_module.THEMES:
        palette = colors_for(theme)
        css = theme_module.app_css(theme)
        assert _contrast_ratio(palette["text"], palette["surface"]) >= 4.5
        assert _contrast_ratio(palette["muted"], palette["surface"]) >= 4.5
        assert _contrast_ratio(palette["control_border"], palette["surface"]) >= 3
        assert all(
            _contrast_ratio(palette[token], palette["surface"]) >= 4.5
            for token in ("change_increase", "change_decrease", "change_neutral")
        )
        assert palette["change_increase"] == (
            "#1D4ED8" if theme == "Light" else "#93C5FD"
        )
        assert palette["change_decrease"] == (
            "#B45309" if theme == "Light" else "#FDBA74"
        )
        assert theme_module.CHANGE_THRESHOLDS == {
            "neutral_below_pct": 5.0,
            "bold_above_pct": 15.0,
        }
        assert "--control-border:" in css
        assert "[data-testid=\"stDateInputField\"]" in css
        assert "[role=\"application\"][aria-label^=\"Choose date range\"]" in css
        assert "border: 1px solid var(--control-border) !important;" in css
        assert "[data-testid=\"stDateInput\"] input::placeholder" in css


def test_download_buttons_use_visible_theme_colors_in_both_themes():
    for theme in theme_module.THEMES:
        palette = colors_for(theme)
        css = theme_module.app_css(theme)

        assert _contrast_ratio(palette["text"], palette["surface"]) >= 4.5
        assert _contrast_ratio(palette["control_border"], palette["surface"]) >= 3
        assert _contrast_ratio(
            palette["download_primary_text"], theme_module.BRAND
        ) >= 4.5
        assert '[data-testid="stDownloadButton"] button[kind="secondary"]' in css
        assert "background: var(--surface) !important;" in css
        assert "border: 1px solid var(--control-border) !important;" in css
        assert "color: var(--ink) !important;" in css
        assert "color: var(--download-primary-text) !important;" in css
        assert "--download-primary-text:" in css
        assert '[data-testid="stDownloadButton"] button:hover' in css
        assert '[data-testid="stDownloadButton"] button:focus-visible' in css


def test_chart_module_is_imported_from_project_package():
    assert Path(charts.__file__).resolve() == ROOT / "src" / "charts.py"
    assert callable(charts.consistency_heatmap)


def _contrast_ratio(foreground, background):
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_light_and_dark_text_tokens_meet_wcag_contrast():
    for theme in theme_module.THEMES:
        palette = colors_for(theme)
        assert _contrast_ratio(palette["text"], palette["surface"]) >= 7
        assert _contrast_ratio(palette["muted"], palette["surface"]) >= 4.5
        assert _contrast_ratio(palette["kicker"], palette["surface"]) >= 4.5
        assert all(_contrast_ratio(color, palette["surface"]) >= 3 for color in palette["series"])

    assert _contrast_ratio(theme_module.REPORT_COLORS["ink"], "#FFFFFF") >= 7
    assert _contrast_ratio(theme_module.REPORT_COLORS["secondary"], "#FFFFFF") >= 7
    for token in ("muted", "increase", "decrease", "neutral", "warning"):
        assert _contrast_ratio(theme_module.REPORT_COLORS[token], "#FFFFFF") >= 4.5


def test_pdf_change_text_uses_percentage_thresholds_and_no_cell_fill():
    cases = [
        ("▲ +4.9%", 4.9, "#4B5563", "Inter-Regular"),
        ("▲ +5.0%", 5.0, "#1D4ED8", "Inter-Regular"),
        ("▼ -15.0%", -15.0, "#B45309", "Inter-Regular"),
        ("▼ -15.1%", -15.1, "#B45309", "Inter-Bold"),
    ]
    for label, value, color, font_name in cases:
        markup = pdf_report._change_markup(label, value)
        assert f'color="{color}"' in markup
        assert f'name="{font_name}"' in markup
        assert "background" not in markup

    cell = pdf_report._comparison_change(15.1)
    assert cell.text.startswith("▲ ")
    assert cell.color == pdf_report.colors.HexColor("#1D4ED8")
    assert cell.font_name == "Inter-Bold"


def test_collapsed_sidebar_arrow_uses_theme_contrast():
    for theme in theme_module.THEMES:
        css = theme_module.app_css(theme)
        assert '[data-testid="stExpandSidebarButton"]' in css
        assert "color: var(--ink) !important;" in css


def test_athlete_dropdown_uses_theme_colors_and_highlights_selection():
    for theme in theme_module.THEMES:
        css = theme_module.app_css(theme)
        assert '[data-testid="stSelectboxVirtualDropdown"]' in css
        assert '[role="option"][aria-selected="true"]' in css
        assert "background: var(--surface-tint) !important;" in css
        assert "color: var(--ink) !important;" in css


def test_hero_heading_resets_streamlit_default_padding():
    for theme in theme_module.THEMES:
        assert ".brand-title" in theme_module.app_css(theme)
        assert "line-height: 1.1;" in theme_module.app_css(theme)
        assert "padding-top: 4rem;" in theme_module.app_css(theme)


def test_chart_builders_use_requested_theme_surfaces(cleaned_data):
    sessions, _ = cleaned_data
    athlete_id = sessions["athlete_id"].iloc[0]
    athlete = m.add_per90_columns(
        m.usable_sessions(sessions[sessions["athlete_id"] == athlete_id])
    )
    for theme, expected_surface in [("Light", "#FFFFFF"), ("Dark", "#1B2732")]:
        figure = charts.consistency_heatmap(athlete, theme)
        assert figure.layout.plot_bgcolor == expected_surface
        assert figure.layout.paper_bgcolor == expected_surface
        assert figure.layout.font.color == colors_for(theme)["text"]
    with pytest.raises(ValueError, match="Unknown theme"):
        charts.consistency_heatmap(athlete, "Sepia")
