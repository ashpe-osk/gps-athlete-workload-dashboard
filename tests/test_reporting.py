"""Tests for shared formatting, quality summaries, reports, and visual builders."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import charts, metrics as m, quality, report  # noqa: E402
from src.cleaning import clean_pipeline  # noqa: E402
from src.formatting import format_metric, format_minutes, format_percent  # noqa: E402
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
    assert "SYNTHETIC DEMO DATA" in markdown
    assert "Missing measurements are not interpreted as zero." in markdown
    assert "Combined metrics" in markdown
    with pytest.raises(ValueError, match="No sessions found"):
        report.build_report(sessions, issues, "unknown-athlete")


def test_new_charts_build_for_real_cleaned_sessions(cleaned_data):
    sessions, _ = cleaned_data
    athlete_ids = sorted(sessions["athlete_id"].unique())[:2]
    athlete_id = athlete_ids[0]
    athlete = m.add_per90_columns(
        m.usable_sessions(sessions[sessions["athlete_id"] == athlete_id])
    )
    comparison, _ = m.comparison_table(sessions, athlete_ids)

    assert len(charts.workload_composition_chart(athlete).data) == 2
    assert len(charts.match_intensity_scatter(athlete).data) >= 1
    assert len(charts.consistency_heatmap(athlete).data) == 1
    assert len(charts.comparison_radar_chart(comparison).data) == len(athlete_ids)
    assert len(charts.comparison_box_chart(
        sessions, athlete_ids, "sprint_count_per90", "Sprints", "Sprints / 90"
    ).data) == len(athlete_ids)
    assert len(charts.comparison_bubble_chart(comparison).data) >= 1
    quality_map = charts.quality_map_chart(sessions)
    assert len(quality_map.data) == 1
    assert len(set(quality_map.data[0].x)) == sessions["match_id"].nunique()


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
