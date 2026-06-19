import sqlite3
from pathlib import Path

DB_PATH = Path("data/panchangam.db")

CREATE_PANCHANGAM = """
CREATE TABLE IF NOT EXISTS panchangam (
    date             TEXT PRIMARY KEY,
    is_pournami      INTEGER NOT NULL,
    thithi_id        INTEGER NOT NULL,
    thithi_name      TEXT NOT NULL,
    nakshatra_id     INTEGER NOT NULL,
    nakshatra_name   TEXT NOT NULL,
    sunrise          TEXT NOT NULL,
    sunset           TEXT NOT NULL,
    nazhika_from_sunrise REAL NOT NULL,
    kv_day           INTEGER NOT NULL,
    kv_month         INTEGER NOT NULL,
    kv_year          INTEGER NOT NULL,
    kv_month_name_en TEXT NOT NULL,
    kv_month_name_ml TEXT NOT NULL
);
"""

CREATE_THITHI_TRANSITIONS = """
CREATE TABLE IF NOT EXISTS thithi_transitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date  TEXT NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    thithi_id        INTEGER NOT NULL,
    thithi_name      TEXT NOT NULL,
    start_time       TEXT NOT NULL,
    end_time         TEXT
);
"""

CREATE_NAKSHATRA_TRANSITIONS = """
CREATE TABLE IF NOT EXISTS nakshatra_transitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date  TEXT NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    nakshatra_id     INTEGER NOT NULL,
    nakshatra_name   TEXT NOT NULL,
    start_time       TEXT NOT NULL,
    end_time         TEXT
);
"""

CREATE_SANTHIGIRI_EVENTS = """
CREATE TABLE IF NOT EXISTS santhigiri_significant_dates (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date  TEXT NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    event_id         TEXT NOT NULL,
    name             TEXT NOT NULL,
    description      TEXT NOT NULL
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_thithi_transitions_date ON thithi_transitions(panchangam_date);",
    "CREATE INDEX IF NOT EXISTS idx_nakshatra_transitions_date ON nakshatra_transitions(panchangam_date);",
    "CREATE INDEX IF NOT EXISTS idx_santhigiri_events_date ON santhigiri_significant_dates(panchangam_date);",
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_connection() as conn:
        conn.execute(CREATE_PANCHANGAM)
        conn.execute(CREATE_THITHI_TRANSITIONS)
        conn.execute(CREATE_NAKSHATRA_TRANSITIONS)
        conn.execute(CREATE_SANTHIGIRI_EVENTS)
        for idx in CREATE_INDEXES:
            conn.execute(idx)
        conn.commit()
    print(f"Database initialized at {DB_PATH}")
