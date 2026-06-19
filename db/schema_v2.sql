-- =============================================================================
-- Normalized panchangam schema (v2)
--
-- Changes from v1 (db/database.py):
--   - KollavarshamDate moved from inline kv_* columns → kollavarsham_date table (1:1)
--   - Thithi, Nakshatra, Paksha get lookup tables (seeded from Python enums at init)
--   - Redundant name/thithi_name/nakshatra_name TEXT columns dropped from
--     thithi_transitions and nakshatra_transitions (join the lookup table instead)
--   - thithi_id / nakshatra_id in panchangam now carry declared FK constraints
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ---------------------------------------------------------------------------
-- LOOKUP TABLES  (2 / 27 / 30 rows — seeded once at init, never written again)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS paksha (
    id   INTEGER PRIMARY KEY,   -- 1=SHUKLA, 2=KRISHNA
    name TEXT    NOT NULL UNIQUE,  -- Python enum member name
    ml   TEXT    NOT NULL,
    en   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS nakshatra (
    id   INTEGER PRIMARY KEY,   -- 1–27
    name TEXT    NOT NULL UNIQUE,  -- Python enum member name e.g. 'ASWATHI'
    ml   TEXT    NOT NULL,
    en   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS thithi (
    id        INTEGER PRIMARY KEY,  -- 1–30
    name      TEXT    NOT NULL UNIQUE,  -- Python enum member name e.g. 'PRATHAMA_SHUKLA'
    paksha_id INTEGER NOT NULL REFERENCES paksha(id),
    day       INTEGER NOT NULL,     -- day within paksha (1–15)
    ml        TEXT    NOT NULL,
    en        TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- FACT TABLES
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS panchangam (
    date                 TEXT    PRIMARY KEY,   -- ISO date 'YYYY-MM-DD'
    is_pournami          INTEGER NOT NULL,      -- 0 | 1
    thithi_id            INTEGER NOT NULL REFERENCES thithi(id),
    nakshatra_id         INTEGER NOT NULL REFERENCES nakshatra(id),
    sunrise              TEXT    NOT NULL,      -- ISO-8601 with tz offset
    sunset               TEXT    NOT NULL,
    nazhika_from_sunrise REAL    NOT NULL
);

-- 1:1 child of panchangam; splits out the KollavarshamDate model
CREATE TABLE IF NOT EXISTS kollavarsham_date (
    date             TEXT    PRIMARY KEY REFERENCES panchangam(date) ON DELETE CASCADE,
    kv_day           INTEGER NOT NULL,
    kv_month         INTEGER NOT NULL,   -- MalayalamMasa.id (1–12)
    kv_year          INTEGER NOT NULL,   -- Kollam Era year
    kv_month_name_en TEXT    NOT NULL,
    kv_month_name_ml TEXT    NOT NULL
);

-- 1:many — thithi phase transitions within a day
CREATE TABLE IF NOT EXISTS thithi_transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    thithi_id       INTEGER NOT NULL REFERENCES thithi(id),
    start_time      TEXT    NOT NULL,   -- ISO-8601 with tz offset
    end_time        TEXT                -- NULL = open-ended (last transition of day)
);

-- 1:many — nakshatra (star) transitions within a day
CREATE TABLE IF NOT EXISTS nakshatra_transitions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    nakshatra_id    INTEGER NOT NULL REFERENCES nakshatra(id),
    start_time      TEXT    NOT NULL,
    end_time        TEXT
);

-- 1:many — significant Santhigiri events that fall on a day
CREATE TABLE IF NOT EXISTS santhigiri_significant_dates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    panchangam_date TEXT    NOT NULL REFERENCES panchangam(date) ON DELETE CASCADE,
    event_id        TEXT    NOT NULL,   -- SanthigiriEventId str-enum value
    name            TEXT    NOT NULL,
    description     TEXT    NOT NULL
);

-- ---------------------------------------------------------------------------
-- INDEXES
-- ---------------------------------------------------------------------------

-- Composite index covers filter-by-date + order-by-time in one step
CREATE INDEX IF NOT EXISTS idx_thithi_transitions_date
    ON thithi_transitions(panchangam_date, start_time);

CREATE INDEX IF NOT EXISTS idx_nakshatra_transitions_date
    ON nakshatra_transitions(panchangam_date, start_time);

CREATE INDEX IF NOT EXISTS idx_santhigiri_events_date
    ON santhigiri_significant_dates(panchangam_date);

-- Lookup tables (≤30 rows) live in a single page — no additional indexes needed.
