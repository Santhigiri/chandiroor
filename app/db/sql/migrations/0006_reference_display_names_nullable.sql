-- Makes the localized display-name columns (ml, en) nullable on the four
-- reference lookup tables. The Python enums (app.core.astronomy.enums.* and
-- app/utils/malayalam_masa.py) no longer carry display text — they hold only
-- id/name(+paksha/day) — so db/seed.py seeds those columns as NULL. Real
-- databases still get the names from db/sql/02_seed.sql; this only relaxes the
-- constraint so a DB seeded without them is valid.
--
-- For an existing deployed database only. `db/database.py::init_db()`'s
-- `SQLModel.metadata.create_all()` only creates missing tables, it does not
-- ALTER existing ones, so a database bootstrapped before this migration needs
-- it applied once, by hand:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/migrations/0006_reference_display_names_nullable.sql
--
-- A fresh database stood up from db/sql/01_schema.sql already has these columns
-- nullable — do not re-run this file against one.

ALTER TABLE paksha         ALTER COLUMN ml DROP NOT NULL;
ALTER TABLE paksha         ALTER COLUMN en DROP NOT NULL;
ALTER TABLE nakshatra      ALTER COLUMN ml DROP NOT NULL;
ALTER TABLE nakshatra      ALTER COLUMN en DROP NOT NULL;
ALTER TABLE thithi         ALTER COLUMN ml DROP NOT NULL;
ALTER TABLE thithi         ALTER COLUMN en DROP NOT NULL;
ALTER TABLE malayalam_masa ALTER COLUMN ml DROP NOT NULL;
ALTER TABLE malayalam_masa ALTER COLUMN en DROP NOT NULL;
