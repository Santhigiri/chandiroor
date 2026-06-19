import sqlite3
from pathlib import Path

DB_PATH = Path("data/panchangam.db")

# ---------------------------------------------------------------------------
# Lookup tables — seeded once from Python enums, never written at runtime
# ---------------------------------------------------------------------------

CREATE_PAKSHA = """
CREATE TABLE IF NOT EXISTS paksha (
    id   INTEGER PRIMARY KEY,   -- 1=SHUKLA, 2=KRISHNA
    name TEXT    NOT NULL UNIQUE,  -- Python enum member name
    ml   TEXT    NOT NULL,
    en   TEXT    NOT NULL
);
"""

CREATE_NAKSHATRA = """
CREATE TABLE IF NOT EXISTS nakshatra (
    id   INTEGER PRIMARY KEY,   -- 1–27
    name TEXT    NOT NULL UNIQUE,  -- Python enum member name e.g. 'ASWATHI'
    ml   TEXT    NOT NULL,
    en   TEXT    NOT NULL
);
"""

CREATE_THITHI = """
CREATE TABLE IF NOT EXISTS thithi (
    id        INTEGER PRIMARY KEY,  -- 1–30
    name      TEXT    NOT NULL UNIQUE,  -- Python enum member name e.g. 'PRATHAMA_SHUKLA'
    paksha_id INTEGER NOT NULL REFERENCES paksha(id),
    day       INTEGER NOT NULL,     -- day within paksha (1–15)
    ml        TEXT    NOT NULL,
    en        TEXT    NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Core fact table — one row per calendar date
# ---------------------------------------------------------------------------

CREATE_PANCHANGAM = """
CREATE TABLE IF NOT EXISTS panchangam (
    date                 TEXT    PRIMARY KEY,   -- ISO date 'YYYY-MM-DD'
    is_pournami          INTEGER NOT NULL,      -- 0 | 1
    thithi_id            INTEGER NOT NULL REFERENCES thithi(id),
    nakshatra_id         INTEGER NOT NULL REFERENCES nakshatra(id),
    nazhika_from_sunrise REAL    NOT NULL
);
"""

# ---------------------------------------------------------------------------
# 1:1 child — Kollavarsham (Malayalam solar calendar) date for each day
# ---------------------------------------------------------------------------

CREATE_KOLLAVARSHAM_DATE = """
CREATE TABLE IF NOT EXISTS kollavarsham_date (
    date             TEXT    PRIMARY KEY REFERENCES panchangam(date) ON DELETE CASCADE,
    kv_day           INTEGER NOT NULL,
    kv_month         INTEGER NOT NULL,   -- MalayalamMasa id (1–12)
    kv_year          INTEGER NOT NULL,   -- Kollam Era year
    kv_month_name_en TEXT    NOT NULL,
    kv_month_name_ml TEXT    NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Location-specific — sunrise/sunset varies by latitude & longitude
# ---------------------------------------------------------------------------

CREATE_SUNRISE_SUNSET = """
CREATE TABLE IF NOT EXISTS sunrise_sunset (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date      TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    latitude  REAL    NOT NULL,
    longitude REAL    NOT NULL,
    timezone  TEXT    NOT NULL,
    sunrise   TEXT    NOT NULL,  -- ISO-8601 datetime with tz offset
    sunset    TEXT    NOT NULL,
    UNIQUE(date, latitude, longitude)
);
"""

# ---------------------------------------------------------------------------
# 1:many — thithi (lunar day) phase transitions within a calendar day
# ---------------------------------------------------------------------------

CREATE_THITHI_TRANSITIONS = """
CREATE TABLE IF NOT EXISTS thithi_transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    thithi_id       INTEGER NOT NULL REFERENCES thithi(id),
    start_time      TEXT    NOT NULL,  -- ISO-8601 datetime with tz offset
    end_time        TEXT               -- NULL = open-ended last transition
);
"""

# ---------------------------------------------------------------------------
# 1:many — nakshatra (lunar mansion) transitions within a calendar day
# ---------------------------------------------------------------------------

CREATE_NAKSHATRA_TRANSITIONS = """
CREATE TABLE IF NOT EXISTS nakshatra_transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    nakshatra_id    INTEGER NOT NULL REFERENCES nakshatra(id),
    start_time      TEXT    NOT NULL,
    end_time        TEXT
);
"""

# ---------------------------------------------------------------------------
# 1:many — Santhigiri ashram significant events that fall on a date
# ---------------------------------------------------------------------------

CREATE_SANTHIGIRI_EVENTS = """
CREATE TABLE IF NOT EXISTS santhigiri_significant_dates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    event_id        TEXT    NOT NULL,  -- SanthigiriEventId str-enum value
    name            TEXT    NOT NULL,
    description     TEXT    NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------

INDEXES = [
    # Transition tables: composite covers filter-by-date + order-by-time in one step
    "CREATE INDEX IF NOT EXISTS idx_thithi_transitions_date    ON thithi_transitions(panchangam_date, start_time);",
    "CREATE INDEX IF NOT EXISTS idx_nakshatra_transitions_date ON nakshatra_transitions(panchangam_date, start_time);",
    # Event and sunrise lookups filter by date only
    "CREATE INDEX IF NOT EXISTS idx_santhigiri_events_date     ON santhigiri_significant_dates(panchangam_date);",
    "CREATE INDEX IF NOT EXISTS idx_sunrise_sunset_date        ON sunrise_sunset(date);",
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        # Lookup tables first (referenced by FK in later tables)
        conn.execute(CREATE_PAKSHA)
        conn.execute(CREATE_NAKSHATRA)
        conn.execute(CREATE_THITHI)
        # Fact tables
        conn.execute(CREATE_PANCHANGAM)
        conn.execute(CREATE_KOLLAVARSHAM_DATE)
        conn.execute(CREATE_SUNRISE_SUNSET)
        conn.execute(CREATE_THITHI_TRANSITIONS)
        conn.execute(CREATE_NAKSHATRA_TRANSITIONS)
        conn.execute(CREATE_SANTHIGIRI_EVENTS)
        # Indexes
        for idx in INDEXES:
            conn.execute(idx)
        conn.commit()
    print(f"Database initialized at {DB_PATH}")
