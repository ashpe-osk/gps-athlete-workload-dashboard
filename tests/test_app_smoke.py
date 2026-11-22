"""Smoke test: the app runs without errors for every athlete and every match."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cleaning import clean_pipeline  # noqa: E402

APP = str(ROOT / "app" / "app.py")
CLEAN, _ = clean_pipeline()


def run_app():
    return AppTest.from_file(APP, default_timeout=60).run()


def test_app_starts_with_synthetic_banner():
    at = run_app()
    assert not at.exception
    assert any("SYNTHETIC" in w.value for w in at.warning)


def test_every_athlete_renders():
    at = run_app()
    for athlete_id in sorted(CLEAN["athlete_id"].unique()):
        at.sidebar.selectbox[0].set_value(athlete_id).run()
        assert not at.exception, f"error for {athlete_id}: {at.exception}"


def test_every_match_renders_for_every_athlete():
    at = run_app()
    for athlete_id in sorted(CLEAN["athlete_id"].unique()):
        at.sidebar.selectbox[0].set_value(athlete_id).run()
        for match_id in CLEAN.loc[CLEAN["athlete_id"] == athlete_id, "match_id"]:
            match_box = next(s for s in at.selectbox if s.label == "Select a match")
            match_box.set_value(match_id).run()
            assert not at.exception, f"error for {athlete_id} / {match_id}: {at.exception}"
