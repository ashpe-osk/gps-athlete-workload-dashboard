"""
Checks the cleaning step against the "answer key" (data/raw/planted_issues_log.csv).
Run from the project root:   pytest -v
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cleaning import clean_pipeline, load_raw  # noqa: E402

PLANTED = pd.read_csv(ROOT / "data" / "raw" / "planted_issues_log.csv")
CLEAN, ISSUES = clean_pipeline()


def pairs(table, issue_type, with_column=False):
    """Set of (session_id[, column]) for one issue type."""
    rows = table[table["issue_type"] == issue_type]
    cols = ["session_id", "column"] if with_column else ["session_id"]
    return set(map(tuple, rows[cols].values))


def test_every_planted_missing_value_is_found():
    assert pairs(PLANTED, "missing_value", True) <= pairs(ISSUES, "missing_value", True)


def test_every_planted_invalid_value_is_found():
    assert pairs(PLANTED, "invalid_value", True) <= pairs(ISSUES, "invalid_value", True)


def test_planted_dropout_is_found():
    assert pairs(PLANTED, "partial_record") <= pairs(ISSUES, "possible_dropout")


def test_estimated_minutes_are_found():
    assert pairs(PLANTED, "estimated_minutes") == pairs(ISSUES, "estimated_minutes")


def test_duplicate_is_found_and_removed():
    assert pairs(PLANTED, "duplicate_record") <= pairs(ISSUES, "duplicate_record")
    assert CLEAN["session_id"].is_unique


def test_missing_values_are_never_turned_into_zero():
    raw = load_raw().drop_duplicates(subset="session_id")
    for column in ["sprint_count", "hsr_distance_m", "top_speed_kmh", "player_load_au"]:
        assert CLEAN[column].isna().sum() >= raw[column].isna().sum()


def test_invalid_values_become_missing_not_zero():
    assert CLEAN["top_speed_kmh"].max(skipna=True) <= 38
    assert CLEAN["peak_accel_ms2"].max(skipna=True) <= 10


def test_normal_sessions_are_not_flagged_as_dropouts():
    # Only the one planted dropout should be flagged in this dataset
    assert CLEAN["possible_dropout"].sum() == 1
