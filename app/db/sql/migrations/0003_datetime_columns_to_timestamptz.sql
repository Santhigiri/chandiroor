-- Converts every datetime column to TIMESTAMPTZ, storing UTC, replacing the
-- naive-local-time convention (see db/repository.py's now-removed `_naive()`
-- and db/models/types.py::UTCDateTime, which normalizes every read/write to
-- UTC-aware regardless of the connection's session TimeZone).
--
-- sunrise_sunset.sunrise/sunset and thithi_transitions/nakshatra_transitions
-- start_time/end_time were stored as naive Asia/Kolkata wall-clock, so this
-- migration reinterprets those digits as IST and converts to UTC via
-- `AT TIME ZONE 'Asia/Kolkata'` — a real value shift to the correct instant.
--
-- dataset_etag.updated_at and user.created_at were already populated with
-- UTC-instant values in Python (silently truncated to naive on insert), so
-- their digits are already UTC and only need a type change via
-- `AT TIME ZONE 'UTC'` — no value shift.
--
-- For an existing deployed database only. `db/database.py::init_db()`'s
-- `SQLModel.metadata.create_all()` only creates missing tables, it does not
-- ALTER existing ones, so a database bootstrapped before this migration needs
-- it applied once, by hand:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/migrations/0003_datetime_columns_to_timestamptz.sql
--
-- A fresh database stood up from db/sql/01_schema.sql already has these
-- columns as TIMESTAMPTZ (that file is regenerated from db/models/ via
-- scripts/gen_seed_sql.py, which picks it up automatically) — do not re-run
-- this file against one.
--
-- UNLIKE the ADD COLUMN IF NOT EXISTS migrations before this one, `ALTER
-- COLUMN ... TYPE` is NOT safely re-runnable: running this a second time
-- against an already-converted (TIMESTAMPTZ) column will misinterpret the
-- `AT TIME ZONE` conversion (the value is already UTC-correct, and shifting
-- it a second time corrupts it). Apply this exactly once.

ALTER TABLE sunrise_sunset
  ALTER COLUMN sunrise TYPE TIMESTAMPTZ USING sunrise AT TIME ZONE 'Asia/Kolkata',
  ALTER COLUMN sunset  TYPE TIMESTAMPTZ USING sunset  AT TIME ZONE 'Asia/Kolkata';

ALTER TABLE thithi_transitions
  ALTER COLUMN start_time TYPE TIMESTAMPTZ USING start_time AT TIME ZONE 'Asia/Kolkata',
  ALTER COLUMN end_time   TYPE TIMESTAMPTZ USING end_time   AT TIME ZONE 'Asia/Kolkata';

ALTER TABLE nakshatra_transitions
  ALTER COLUMN start_time TYPE TIMESTAMPTZ USING start_time AT TIME ZONE 'Asia/Kolkata',
  ALTER COLUMN end_time   TYPE TIMESTAMPTZ USING end_time   AT TIME ZONE 'Asia/Kolkata';

ALTER TABLE dataset_etag
  ALTER COLUMN updated_at TYPE TIMESTAMPTZ USING updated_at AT TIME ZONE 'UTC';

ALTER TABLE "user"
  ALTER COLUMN created_at TYPE TIMESTAMPTZ USING created_at AT TIME ZONE 'UTC';
