-- Adds SanthigiriEvent.yields_to_event_id: a nullable, self-referencing FK
-- letting one event definition defer to another on any date their
-- conditions both match (see SanthigiriEventService._excluded_dates_for_yield
-- and CLAUDE.md's "Editable Santhigiri event definitions" section).
--
-- For an existing deployed database only. `db/database.py::init_db()`'s
-- `SQLModel.metadata.create_all()` only creates missing tables, it does not
-- ALTER existing ones, so a database bootstrapped before this migration needs
-- it applied once, by hand:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/migrations/0001_add_yields_to_event_id.sql
--
-- A fresh database stood up from db/sql/01_schema.sql already has this column
-- (that file is regenerated from db/models/ via scripts/gen_seed_sql.py, which
-- picks it up automatically) — do not re-run this file against one.

ALTER TABLE santhigiri_event
  ADD COLUMN IF NOT EXISTS yields_to_event_id VARCHAR
    REFERENCES santhigiri_event (id) ON DELETE SET NULL;

-- Data fix this migration exists for: Chothi Theertha Yathra matches every
-- Chothi Nakshatra transition in the year, which incidentally includes
-- Navapoojitham's last-Chothi-in-Chingam date. Make it yield to Navapoojitham
-- on that shared date instead of also occurring there.
UPDATE santhigiri_event
   SET yields_to_event_id = 'NAVAPOOJITHAM'
 WHERE id = 'JANMAGRIHA_THEERTHA_YATHRA'
   AND EXISTS (SELECT 1 FROM santhigiri_event WHERE id = 'NAVAPOOJITHAM');

-- Setting the column does not retroactively rewrite already-stored
-- santhigiri_event_dates rows. After applying this migration, regenerate the
-- affected years so the exclusion actually takes effect on stored data:
--
--   POST /api/v1/panchangam/events/JANMAGRIHA_THEERTHA_YATHRA/occurrences
--   {"start_year": 2021, "end_year": 2030}
