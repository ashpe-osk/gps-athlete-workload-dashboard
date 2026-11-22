"""Tests for metrics.py using small hand-made tables. Run: pytest -v"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import metrics as m  # noqa: E402
from cleaning import clean_pipeline  # noqa: E402


def two_match_athlete():
    """The worked example: A = 9.0 km in 90 min (100 m/min), B = 3.6 km in 30 min (120 m/min)."""
    return pd.DataFrame({
        "total_distance_km": [9.0, 3.6], "minutes_played": [90, 30],
        "distance_per_min": [100.0, 120.0],
        "sprint_count": pd.array([30, pd.NA], dtype="Int64"),
        "top_speed_kmh": [28.0, 30.0], "peak_accel_ms2": [4.5, 5.0],
        "hsr_distance_m": pd.array([500, 200], dtype="Int64"),
        "accel_count": pd.array([60, 20], dtype="Int64"),
        "decel_count": pd.array([60, 20], dtype="Int64"),
        "player_load_au": [200.0, 80.0],
    })


def test_pooled_rate_differs_from_simple_mean():
    a = two_match_athlete()
    stats = m.combined_stats(a).set_index("column")
    assert stats.loc["distance_per_min", "value"] == pytest.approx(105.0)   # 12.6 km / 120 min
    assert m.mean_of_match_rates(a) == pytest.approx(110.0)


def test_peaks_use_maximum_and_totals_use_sum():
    stats = m.combined_stats(two_match_athlete()).set_index("column")
    assert stats.loc["top_speed_kmh", "value"] == 30.0
    assert stats.loc["total_distance_km", "value"] == pytest.approx(12.6)


def test_missing_values_are_skipped_and_counted_not_zeroed():
    stats = m.combined_stats(two_match_athlete()).set_index("column")
    assert stats.loc["sprint_count", "value"] == 30
    assert stats.loc["sprint_count", "n_valid"] == 1
    assert stats.loc["sprint_count", "n_sessions"] == 2


def test_all_missing_total_is_nan_not_zero():
    assert np.isnan(m.safe_sum(pd.Series([np.nan, np.nan])))


def test_pct_change_skips_missing_sessions():
    change = m.pct_change_vs_previous(pd.Series([100.0, np.nan, 110.0]))
    assert np.isnan(change.iloc[0]) and np.isnan(change.iloc[1])
    assert change.iloc[2] == pytest.approx(10.0)


def test_rolling_mean_needs_enough_valid_sessions():
    rolled = m.rolling_mean(pd.Series([10.0, 20.0, np.nan, 30.0]))
    assert rolled.iloc[:3].isna().all()
    assert rolled.iloc[3] == pytest.approx(20.0)


def test_own_history_needs_three_prior_sessions():
    df = pd.DataFrame({"match_id": ["a", "b", "c", "d"],
                       "match_date": pd.to_datetime(["2026-01-01", "2026-01-15", "2026-01-29", "2026-02-12"]),
                       "x": [10.0, 20.0, 30.0, 40.0]})
    early = m.compare_with_own_history(df, "x", "c")      # only 2 prior sessions
    late = m.compare_with_own_history(df, "x", "d")       # 3 prior sessions, mean 20
    assert early["status"] == "insufficient history"
    assert late["status"] == "ok" and late["pct_diff"] == pytest.approx(100.0)


def test_consistency_flags_small_samples():
    assert m.consistency_summary(pd.Series([1.0, 2.0, 3.0]))["low_confidence"] is True
    result = m.consistency_summary(pd.Series([90.0, 100.0, 110.0, 100.0]))
    assert result["low_confidence"] is False and result["cv_pct"] == pytest.approx(8.16, abs=0.01)
    assert np.isnan(m.consistency_summary(pd.Series([5.0]))["sd"])


def test_per90_ignores_short_sessions():
    a = m.add_per90_columns(two_match_athlete())
    assert a["total_distance_km_per90"].iloc[0] == pytest.approx(9.0)
    assert np.isnan(a["total_distance_km_per90"].iloc[1])   # only 30 minutes


def test_comparison_warns_about_goalkeepers_and_small_samples():
    clean, _ = clean_pipeline()
    gk = clean[clean["position"] == "Goalkeeper"]["athlete_id"].iloc[0]
    fw = clean[clean["position"] == "Forward"]["athlete_id"].iloc[0]
    table, warnings = m.comparison_table(clean, [gk, fw])
    assert len(table) == 2
    assert any("Goalkeepers" in w for w in warnings)


def test_real_pipeline_dropout_session_is_excluded():
    clean, _ = clean_pipeline()
    assert len(m.usable_sessions(clean)) == len(clean) - 1
