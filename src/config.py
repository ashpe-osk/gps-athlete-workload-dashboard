"""
config.py
---------
Central settings for the SYNTHETIC GPS dashboard project.

IMPORTANT: Club names come from the public league table (context only).
All athletes, fixtures, dates and GPS values are FICTIONAL.
"""

# Flip to False to replace real club names with "Club A", "Club B", ...
USE_REAL_CLUB_NAMES = True

DATA_SOURCE_LABEL = "SYNTHETIC"
COMPETITION_LABEL = "Kenya Women's Premier League (synthetic fixtures)"

# League table snapshot supplied by the project author (undated, unverified).
# table_pos is only used to tag opponents as top / middle / bottom band.
CLUBS = {
    "POL": {"real": "Police Bullets",       "generic": "Club A", "table_pos": 1},
    "ULI": {"real": "Ulinzi Starlets",      "generic": "Club B", "table_pos": 2},
    "KIB": {"real": "Kibera Soccer Women",  "generic": "Club C", "table_pos": 3},
    "ZET": {"real": "Zetech Sparks",        "generic": "Club D", "table_pos": 4},
    "MAT": {"real": "Mathare United Women", "generic": "Club E", "table_pos": 5},
    "SHA": {"real": "Shabana Starlets",     "generic": "Club F", "table_pos": 6},
    "KAY": {"real": "Kayole Starlet",       "generic": "Club G", "table_pos": 7},
    "GID": {"real": "Gideon Starlets",      "generic": "Club H", "table_pos": 8},
    "TRI": {"real": "Trinity Starlets",     "generic": "Club I", "table_pos": 9},
    "BUN": {"real": "Bungoma Queens",       "generic": "Club J", "table_pos": 10},
    "ELI": {"real": "Elim White Ladies",    "generic": "Club K", "table_pos": 11},
    "VIH": {"real": "Vihiga Queens",        "generic": "Club L", "table_pos": 12},
}

# Clubs our fictional athletes "play for". They never face each other in the
# synthetic fixtures, so we do not recreate any real club-vs-club fixture.
CAST_CLUBS = ["ZET", "MAT", "KIB"]
OPPONENT_POOL = [k for k in CLUBS if k not in CAST_CLUBS]

# Fictional athletes (pseudonyms). Any resemblance to real people is coincidental.
ATHLETES = [
    {"athlete_id": "ATH-01", "athlete_name": "Wanjiru Mutiso", "club": "ZET", "position": "Midfielder"},
    {"athlete_id": "ATH-02", "athlete_name": "Akinyi Odera",   "club": "ZET", "position": "Forward"},
    {"athlete_id": "ATH-03", "athlete_name": "Nekesa Barasa",  "club": "MAT", "position": "Defender"},
    {"athlete_id": "ATH-04", "athlete_name": "Chebet Kiprop",  "club": "MAT", "position": "Midfielder"},
    {"athlete_id": "ATH-05", "athlete_name": "Mwende Kilonzo", "club": "KIB", "position": "Goalkeeper"},
    {"athlete_id": "ATH-06", "athlete_name": "Auma Ojwang",    "club": "KIB", "position": "Forward"},
]


def club_name(key: str) -> str:
    """Return the display name for a club key, honouring the toggle."""
    return CLUBS[key]["real" if USE_REAL_CLUB_NAMES else "generic"]


def table_band(key: str) -> str:
    """Context tag only: top (1-4), middle (5-8), bottom (9-12)."""
    pos = CLUBS[key]["table_pos"]
    return "top" if pos <= 4 else "middle" if pos <= 8 else "bottom"


# "Typical" per-position values used ONLY to generate plausible synthetic data.
# They are broad assumptions, not measurements of any real athlete.
POSITION_PROFILES = {
    #               m/min  HSR share  sprints/90  accels/90  decels/90  top km/h  peak accel
    "Goalkeeper": dict(mpm=55,  hsr=0.005, sprints=4,  accels=25, decels=25, top=23.5, pa=3.8),
    "Defender":   dict(mpm=88,  hsr=0.060, sprints=30, accels=55, decels=55, top=27.5, pa=4.5),
    "Midfielder": dict(mpm=98,  hsr=0.080, sprints=38, accels=65, decels=62, top=28.3, pa=4.7),
    "Forward":    dict(mpm=90,  hsr=0.095, sprints=46, accels=60, decels=58, top=29.6, pa=5.0),
}
