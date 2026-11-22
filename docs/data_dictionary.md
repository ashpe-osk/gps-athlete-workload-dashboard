# Data dictionary: gps_sessions_synthetic.csv

> ALL ROWS ARE SYNTHETIC. Club names come from a public league table (context only).
> Athletes, fixtures, dates and GPS values are fictional. Not an official GameOn product.

| Column | Type | Unit | Meaning | Aggregation across matches |
|---|---|---|---|---|
| session_id | text | - | match_id + athlete_id; unique key | - |
| athlete_id / athlete_name | text | - | Pseudonymous athlete identity | - |
| position | text | - | Goalkeeper, Defender, Midfielder, Forward | - |
| club | text | - | Club (name controlled by USE_REAL_CLUB_NAMES) | - |
| match_id, match_date | text/date | - | Match identity and date | - |
| opponent, opponent_table_band, home_away | text | - | Context only (band: top 1-4, middle 5-8, bottom 9-12) | - |
| competition | text | - | Labelled as synthetic fixtures | - |
| minutes_played | int | min | Recorded minutes (may be approximate) | Sum |
| minutes_estimated | bool | - | True = minutes rounded/approximate | Count |
| total_distance_km | float | km | Total distance covered | Sum |
| distance_per_min | float | m/min | Rate: distance / recorded minutes | Total distance / total minutes (also show mean of match rates, labelled) |
| hsr_distance_m | float | m | High-speed running distance | Sum |
| top_speed_kmh | float | km/h | Peak value in the match | Max |
| sprint_count | int | count | Sprint efforts | Sum |
| accel_count, decel_count | int | count | Acceleration / deceleration efforts | Sum |
| peak_accel_ms2 | float | m/s2 | Peak value in the match | Max |
| player_load_au | float | AU | Vendor-style composite load (not comparable across GPS brands) | Sum |
| data_source | text | - | Always SYNTHETIC | - |

Missing measurements are blank (NaN) and must never be treated as zero.
`planted_issues_log.csv` lists the problems deliberately planted (ground truth for testing the cleaning step).
