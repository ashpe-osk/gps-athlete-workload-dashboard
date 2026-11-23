"""
generate_data.py
----------------
Creates a reproducible SYNTHETIC GPS dataset (same seed = same file).

Steps:
  1. Build fixtures (match_id, date, opponent, home/away) for each cast club.
  2. Simulate one session row per athlete per match.
  3. Plant known data-quality problems and log exactly what was planted.
  4. Save data/raw/gps_sessions_synthetic.csv and an issues log.

Run from the project root:   python src/generate_data.py
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

import config as cfg

SEED = 42
N_MATCHES = 8                      # matches per club
FIRST_MATCH_DATE = date(2026, 8, 8)
CLUB_DATE_OFFSET = {"ZET": 0, "MAT": 1, "KIB": 0}   # days after the fortnightly date
REAL_SESSION_DATE = date(2026, 11, 7)               # a real GameOn session: avoid it

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def build_fixtures(rng: np.random.Generator) -> pd.DataFrame:
    """One row per club per match. Opponents are never one of our cast clubs."""
    rows = []
    for club in cfg.CAST_CLUBS:
        opponents = rng.choice(cfg.OPPONENT_POOL, size=N_MATCHES, replace=False)
        home_flags = rng.permutation([True] * 4 + [False] * 4)
        for i in range(N_MATCHES):
            match_date = FIRST_MATCH_DATE + timedelta(days=14 * i + CLUB_DATE_OFFSET[club])
            assert match_date != REAL_SESSION_DATE, "Must not reuse a real GameOn session date"
            rows.append({
                "match_id": f"M-{club}-{i + 1:02d}",
                "club_key": club,
                "match_date": match_date,
                "opponent": cfg.club_name(str(opponents[i])),
                "opponent_table_band": cfg.table_band(str(opponents[i])),
                "home_away": "Home" if home_flags[i] else "Away",
                "match_number": i + 1,
            })
    return pd.DataFrame(rows)


def draw_minutes(rng, position):
    """Return (true_minutes, recorded_minutes, minutes_estimated_flag)."""
    if position == "Goalkeeper":
        return 90, 90, False
    roll = rng.random()
    if roll < 0.60:                                  # played the full match
        return 90, 90, False
    if roll < 0.85:                                  # came off late
        true_min = int(rng.integers(65, 90))
    else:                                            # substitute / early exit
        true_min = int(rng.integers(30, 65))
    # Simulate approximate recorded minutes.
    if rng.random() < 0.35:
        return true_min, int(round(true_min / 15) * 15), True
    return true_min, true_min, False


def simulate_sessions(rng, fixtures: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for ath in cfg.ATHLETES:
        prof = cfg.POSITION_PROFILES[ath["position"]]
        level = rng.normal(1.0, 0.03)       # athlete's own baseline vs the position norm
        trend = rng.normal(0.0, 0.01)       # slow drift per match (+/- about 1%)
        club_fixtures = fixtures[fixtures["club_key"] == ath["club"]]

        for _, fx in club_fixtures.iterrows():
            # Some outfield players have no recorded session.
            if ath["position"] != "Goalkeeper" and rng.random() < 0.08:
                continue

            true_min, rec_min, estimated = draw_minutes(rng, ath["position"])

            # Combine baseline, gradual trend, and match variation.
            mpm = prof["mpm"] * level * (1 + trend * (fx["match_number"] - 4.5))
            mpm *= rng.normal(1.0, 0.04)
            mpm *= 1 + (90 - true_min) / 90 * 0.12     # shorter spells are a bit more intense
            distance_m = mpm * true_min

            hsr_m = max(0.0, distance_m * prof["hsr"] * rng.normal(1.0, 0.18))
            scale = true_min / 90 * level
            rows.append({
                "session_id": f"{fx['match_id']}-{ath['athlete_id']}",
                "athlete_id": ath["athlete_id"],
                "athlete_name": ath["athlete_name"],
                "position": ath["position"],
                "club": cfg.club_name(ath["club"]),
                "match_id": fx["match_id"],
                "match_date": fx["match_date"],
                "opponent": fx["opponent"],
                "opponent_table_band": fx["opponent_table_band"],
                "home_away": fx["home_away"],
                "competition": cfg.COMPETITION_LABEL,
                "minutes_played": rec_min,
                "minutes_estimated": estimated,
                "total_distance_km": round(distance_m / 1000, 2),
                "hsr_distance_m": round(hsr_m),
                "top_speed_kmh": round(rng.normal(prof["top"], 1.2), 1),
                "sprint_count": int(rng.poisson(prof["sprints"] * scale)),
                "accel_count": int(rng.poisson(prof["accels"] * scale)),
                "decel_count": int(rng.poisson(prof["decels"] * scale)),
                "peak_accel_ms2": round(rng.normal(prof["pa"], 0.4), 1),
                "player_load_au": round(distance_m / 1000 * 1000 * 0.0245 * rng.normal(1.0, 0.05), 2),
                "data_source": cfg.DATA_SOURCE_LABEL,
            })

    df = pd.DataFrame(rows)
    # Recompute the rate from recorded minutes.
    df["distance_per_min"] = (df["total_distance_km"] * 1000 / df["minutes_played"]).round(1)
    return df


def plant_issues(rng, df: pd.DataFrame):
    log = []
    pool = list(rng.permutation(len(df)))

    def take(n, only=None):
        """Take n unused row positions (optionally only those meeting a condition)."""
        chosen = []
        for idx in list(pool):
            if len(chosen) == n:
                break
            if only is None or only(df.iloc[idx]):
                chosen.append(idx)
                pool.remove(idx)
        return chosen

    def record(idx, issue, column, note):
        log.append({"session_id": df.iloc[idx]["session_id"], "issue_type": issue,
                    "column": column, "note": note})

    # Missing measurements remain NaN.
    for idx in take(3):
        df.iloc[idx, df.columns.get_loc("sprint_count")] = np.nan
        record(idx, "missing_value", "sprint_count", "sprint count not recorded")
    for idx in take(2):
        df.iloc[idx, df.columns.get_loc("top_speed_kmh")] = np.nan
        record(idx, "missing_value", "top_speed_kmh", "top speed not recorded")
    for idx in take(2):
        df.iloc[idx, df.columns.get_loc("hsr_distance_m")] = np.nan
        record(idx, "missing_value", "hsr_distance_m", "HSR not recorded")
    for idx in take(1):
        df.iloc[idx, df.columns.get_loc("player_load_au")] = np.nan
        record(idx, "missing_value", "player_load_au", "player load not recorded")

    # Simulate partial sensor dropout.
    for idx in take(1, only=lambda r: r["minutes_played"] >= 85 and r["position"] != "Goalkeeper"):
        row_cols = df.columns
        df.iloc[idx, row_cols.get_loc("total_distance_km")] = round(df.iloc[idx]["total_distance_km"] * 0.55, 2)
        df.iloc[idx, row_cols.get_loc("player_load_au")] = round(df.iloc[idx]["player_load_au"] * 0.55, 2) \
            if pd.notna(df.iloc[idx]["player_load_au"]) else np.nan
        df.iloc[idx, row_cols.get_loc("distance_per_min")] = round(
            df.iloc[idx]["total_distance_km"] * 1000 / df.iloc[idx]["minutes_played"], 1)
        df.iloc[idx, row_cols.get_loc("hsr_distance_m")] = np.nan
        df.iloc[idx, row_cols.get_loc("sprint_count")] = np.nan
        record(idx, "partial_record", "multiple",
               "sensor dropout: distance/load ~55% of expected, HSR and sprints missing")

    # Plant implausible measurements.
    for idx in take(1):
        df.iloc[idx, df.columns.get_loc("top_speed_kmh")] = 52.0
        record(idx, "invalid_value", "top_speed_kmh", "52.0 km/h is physiologically implausible")
    for idx in take(1):
        df.iloc[idx, df.columns.get_loc("peak_accel_ms2")] = 14.2
        record(idx, "invalid_value", "peak_accel_ms2", "14.2 m/s2 is implausible")

    # Record approximate-minute labels in the issue log.
    for i in np.where(df["minutes_estimated"])[0]:
        record(i, "estimated_minutes", "minutes_played", "minutes rounded to nearest 15 (approximate)")

    dup_idx = pool[0]
    duplicate = df.iloc[[dup_idx]].copy()
    record(dup_idx, "duplicate_record", "all", "exact copy of this session appended")
    df = pd.concat([df, duplicate], ignore_index=True)

    return df, pd.DataFrame(log)


def main():
    rng = np.random.default_rng(SEED)
    fixtures = build_fixtures(rng)
    sessions = simulate_sessions(rng, fixtures)
    sessions, issues_log = plant_issues(rng, sessions)

    sessions = sessions.sort_values(["athlete_id", "match_date", "session_id"]).reset_index(drop=True)
    column_order = [
        "session_id", "athlete_id", "athlete_name", "position", "club",
        "match_id", "match_date", "opponent", "opponent_table_band", "home_away", "competition",
        "minutes_played", "minutes_estimated",
        "total_distance_km", "distance_per_min", "hsr_distance_m", "top_speed_kmh",
        "sprint_count", "accel_count", "decel_count", "peak_accel_ms2", "player_load_au",
        "data_source",
    ]
    sessions = sessions[column_order]

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    sessions.to_csv(RAW_DIR / "gps_sessions_synthetic.csv", index=False)
    issues_log.to_csv(RAW_DIR / "planted_issues_log.csv", index=False)

    print(f"Saved {len(sessions)} rows for {sessions['athlete_id'].nunique()} athletes")
    print(f"Planted issues logged: {len(issues_log)}")
    print(sessions.head(8).to_string())


if __name__ == "__main__":
    main()
