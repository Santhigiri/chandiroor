-- Adds the Amanta lunar month (Chandra Masa) feature's DB objects for an
-- existing deployed database: the chandra_masa lookup table (with its
-- ml/en display text, which nothing in app code is allowed to hardcode —
-- see CLAUDE.md), the chandra_masa_date per-day table, and the
-- chandra_masa_day/chandra_masa_month columns on santhigiri_event. See
-- commit 582d479 ("Add Amanta lunar month (Chandra Masa) to the
-- Panchangam").
--
-- For an existing deployed database only. `db/database.py::init_db()`'s
-- `SQLModel.metadata.create_all()` only creates missing tables, it does not
-- ALTER existing ones -- so chandra_masa/chandra_masa_date get created
-- automatically the next time the app starts (they're brand new tables),
-- but santhigiri_event's two new columns and every table's data need this
-- migration applied once, by hand:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/migrations/0007_add_chandra_masa.sql
--
-- A fresh database stood up from db/sql/01_schema.sql + 02_seed.sql already
-- has all of this -- do not re-run this file against one.
--
-- The chandra_masa INSERT uses `DO UPDATE` rather than `DO NOTHING` so this
-- migration still backfills ml/en even if
-- `db.seed.seed_chandra_masa_if_empty()` (app/utils/lifespan.py) already ran
-- against this database first and inserted structural-only (id/name) rows --
-- id/name are unchanged either way, so it's a no-op on those columns.
--
-- After applying, re-run POST /api/v1/panchangam/generate for the seeded
-- year range to backfill chandra_masa_date rows -- this migration only adds
-- the schema and the lookup rows, not per-day data.

CREATE TABLE IF NOT EXISTS chandra_masa (
	id SERIAL NOT NULL,
	name VARCHAR NOT NULL,
	ml VARCHAR,
	en VARCHAR,
	PRIMARY KEY (id),
	UNIQUE (name)
);

CREATE TABLE IF NOT EXISTS chandra_masa_date (
	date DATE NOT NULL,
	location_id INTEGER NOT NULL,
	masa_id INTEGER NOT NULL,
	masa_day INTEGER NOT NULL,
	masa_type INTEGER NOT NULL,
	PRIMARY KEY (date, location_id),
	FOREIGN KEY(date, location_id) REFERENCES panchangam (date, location_id) ON DELETE CASCADE,
	FOREIGN KEY(masa_id) REFERENCES chandra_masa (id)
);

ALTER TABLE santhigiri_event ADD COLUMN IF NOT EXISTS chandra_masa_day INTEGER;
ALTER TABLE santhigiri_event ADD COLUMN IF NOT EXISTS chandra_masa_month INTEGER;

INSERT INTO chandra_masa (id, name, ml, en) VALUES
  (1, 'CHAITRA', 'ചൈത്രം', 'Chaitra'),
  (2, 'VAISHAKHA', 'വൈശാഖം', 'Vaishakha'),
  (3, 'JYESHTHA', 'ജ്യേഷ്ഠം', 'Jyeshtha'),
  (4, 'ASHADHA', 'ആഷാഢം', 'Ashadha'),
  (5, 'SHRAVANA', 'ശ്രാവണം', 'Shravana'),
  (6, 'BHADRAPADA', 'ഭാദ്രപദം', 'Bhadrapada'),
  (7, 'ASHWINA', 'ആശ്വിനം', 'Ashwina'),
  (8, 'KARTIKA', 'കാർത്തികം', 'Kartika'),
  (9, 'MARGASHIRSHA', 'മാർഗശീർഷം', 'Margashirsha'),
  (10, 'PAUSHA', 'പൗഷം', 'Pausha'),
  (11, 'MAGHA', 'മാഘം', 'Magha'),
  (12, 'PHALGUNA', 'ഫാൽഗുനം', 'Phalguna')
ON CONFLICT (id) DO UPDATE SET ml = EXCLUDED.ml, en = EXCLUDED.en;
