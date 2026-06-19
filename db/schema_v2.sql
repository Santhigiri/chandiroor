-- =============================================================================
-- Normalized panchangam schema (v2)
-- Mirror of db/database.py — kept here as a readable reference.
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------------
-- LOOKUP TABLES  (seeded once from Python enums, never written at runtime)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paksha (
    id   INTEGER PRIMARY KEY,   -- 1=SHUKLA, 2=KRISHNA
    name TEXT    NOT NULL UNIQUE,
    ml   TEXT    NOT NULL,
    en   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS nakshatra (
    id   INTEGER PRIMARY KEY,   -- 1–27
    name TEXT    NOT NULL UNIQUE,
    ml   TEXT    NOT NULL,
    en   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS thithi (
    id        INTEGER PRIMARY KEY,  -- 1–30
    name      TEXT    NOT NULL UNIQUE,
    paksha_id INTEGER NOT NULL REFERENCES paksha(id),
    day       INTEGER NOT NULL,     -- day within paksha (1–15)
    ml        TEXT    NOT NULL,
    en        TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- FACT TABLES
-- ---------------------------------------------------------------------------

-- One row per calendar date. Holds only date-level astronomical facts.
CREATE TABLE IF NOT EXISTS panchangam (
    date                 TEXT    PRIMARY KEY,
    is_pournami          INTEGER NOT NULL,
    thithi_id            INTEGER NOT NULL REFERENCES thithi(id),
    nakshatra_id         INTEGER NOT NULL REFERENCES nakshatra(id),
    nazhika_from_sunrise REAL    NOT NULL
);

-- 1:1 child — Malayalam solar calendar (Kollavarsham) date for each day.
CREATE TABLE IF NOT EXISTS kollavarsham_date (
    date             TEXT    PRIMARY KEY REFERENCES panchangam(date) ON DELETE CASCADE,
    kv_day           INTEGER NOT NULL,
    kv_month         INTEGER NOT NULL,   -- MalayalamMasa id (1–12)
    kv_year          INTEGER NOT NULL,   -- Kollam Era year
    kv_month_name_en TEXT    NOT NULL,
    kv_month_name_ml TEXT    NOT NULL
);

-- Location-specific — sunrise/sunset varies by latitude & longitude.
-- UNIQUE(date, latitude, longitude) allows caching for multiple locations.
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

-- 1:many — thithi (lunar day) phase transitions within a calendar day.
CREATE TABLE IF NOT EXISTS thithi_transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    thithi_id       INTEGER NOT NULL REFERENCES thithi(id),
    start_time      TEXT    NOT NULL,
    end_time        TEXT
);

-- 1:many — nakshatra (lunar mansion) transitions within a calendar day.
CREATE TABLE IF NOT EXISTS nakshatra_transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    nakshatra_id    INTEGER NOT NULL REFERENCES nakshatra(id),
    start_time      TEXT    NOT NULL,
    end_time        TEXT
);

-- 1:many — significant Santhigiri events falling on a date.
CREATE TABLE IF NOT EXISTS santhigiri_significant_dates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    event_id        TEXT    NOT NULL,
    name            TEXT    NOT NULL,
    description     TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- INDEXES
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_thithi_transitions_date
    ON thithi_transitions(panchangam_date, start_time);

CREATE INDEX IF NOT EXISTS idx_nakshatra_transitions_date
    ON nakshatra_transitions(panchangam_date, start_time);

CREATE INDEX IF NOT EXISTS idx_santhigiri_events_date
    ON santhigiri_significant_dates(panchangam_date);

CREATE INDEX IF NOT EXISTS idx_sunrise_sunset_date
    ON sunrise_sunset(date);
