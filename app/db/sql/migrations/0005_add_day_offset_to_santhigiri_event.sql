-- Adds SanthigiriEvent.day_offset: shifts a matched occurrence date by N
-- days (positive = after, negative = before). See
-- utils/santhigiri_events.py's EventCondition.day_offset and
-- core/calendar/santhigiri_event_occurrences.py::compute_occurrences.
--
-- For an existing deployed database only. `db/database.py::init_db()`'s
-- `SQLModel.metadata.create_all()` only creates missing tables, it does not
-- ALTER existing ones, so a database bootstrapped before this migration needs
-- it applied once, by hand:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/migrations/0005_add_day_offset_to_santhigiri_event.sql
--
-- A fresh database stood up from db/sql/01_schema.sql already has this column
-- (that file is regenerated from db/models/ via scripts/gen_seed_sql.py, which
-- picks it up automatically) — do not re-run this file against one.

ALTER TABLE santhigiri_event ADD COLUMN IF NOT EXISTS day_offset INTEGER;
