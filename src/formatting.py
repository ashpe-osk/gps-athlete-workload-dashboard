"""Shared display formatting for metrics and report outputs."""
import re

import pandas as pd

from . import metrics as m
from .theme import CHANGE_THRESHOLDS


DECIMAL_PLACES = {
    "minutes_played": 0,
    "total_distance_km": 2,
    "distance_per_min": 1,
    "hsr_distance_m": 0,
    "top_speed_kmh": 1,
    "sprint_count": 0,
    "accel_count": 0,
    "decel_count": 0,
    "peak_accel_ms2": 1,
    "player_load_au": 1,
}


def format_metric(column: str, value, suffix: str = "") -> str:
    """Format a metric with its unit; missing values are always shown as an em dash."""
    base_column = column.removesuffix("_per90")
    if base_column not in m.METRIC_INFO:
        raise KeyError(f"Unknown metric column: {column}")
    if pd.isna(value):
        return "—"

    decimals = DECIMAL_PLACES[base_column]
    formatted = f"{float(value):,.{decimals}f}"
    unit = m.METRIC_INFO[base_column][2]
    if column.endswith("_per90"):
        unit = f"{unit} / 90 min"
    return f"{formatted} {unit}{suffix}"


def format_percent(value, signed: bool = True) -> str | None:
    """Format a percentage, returning None when its value is missing."""
    if pd.isna(value):
        return None
    sign = "+" if signed else ""
    return f"{float(value):{sign}.1f}%"


def classify_change(value) -> tuple[str, bool]:
    """Return the semantic color token and bold state for a percentage change."""
    if isinstance(value, str):
        match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?=%)", value)
        if match is None:
            return "change_neutral", False
        value = float(match.group())
    elif pd.isna(value):
        return "change_neutral", False

    magnitude = abs(float(value))
    if magnitude < CHANGE_THRESHOLDS["neutral_below_pct"]:
        return "change_neutral", False
    color_token = "change_increase" if value > 0 else "change_decrease"
    return color_token, magnitude > CHANGE_THRESHOLDS["bold_above_pct"]


def format_minutes(value, estimated: bool = False) -> str:
    """Format playing time and retain the existing approximate-minutes marker."""
    if pd.isna(value):
        return "—"
    prefix = "~" if estimated else ""
    return f"{prefix}{int(value)} min"
