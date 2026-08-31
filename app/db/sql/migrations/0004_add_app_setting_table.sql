-- Adds the app_setting table: DB-backed, admin-editable application settings
-- (see shared/services/settings_service.py, api/routes/v1/settings.py). Every key is
-- seeded with a value identical to the hardcoded constant it replaces, so
-- applying this migration is behaviorally a no-op until an admin edits a
-- value through the API.
--
-- For an existing deployed database only. `db/database.py::init_db()`'s
-- `SQLModel.metadata.create_all()` only creates missing tables, it does not
-- ALTER existing ones — but it WILL create app_setting automatically the next
-- time the app starts against this database, since it's a brand new table
-- (not an existing one being altered). This migration exists to also seed
-- the default rows, which init_db() never does:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/migrations/0004_add_app_setting_table.sql
--
-- A fresh database stood up from db/sql/01_schema.sql + 02_seed.sql already
-- has this table and its default rows — do not re-run this file against one.
--
-- Every SettingsService getter falls back to the equivalent hardcoded
-- constant when a key's row is absent, so this migration is safe to apply at
-- any time relative to a code deploy — there is no ordering dependency.

CREATE TABLE IF NOT EXISTS app_setting (
    key         VARCHAR NOT NULL PRIMARY KEY,
    value       JSON NOT NULL,
    description VARCHAR,
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_by  VARCHAR
);

-- Note on nakshatra_transition_step_days: today's code applies
-- core.constants.NAKSHATRA_TRANSITION_STEP_DAYS (0.01) unconditionally to
-- every year at runtime — the "2028 needs 0.05" fact documented in
-- CLAUDE.md/core/constants.py is tribal knowledge applied by temporarily
-- hand-editing the constant when that year's offline pickle cache was last
-- rebuilt, not an active runtime branch. So the true no-op default here is
-- an empty `overrides` map (0.01 for every year, same as today); an admin
-- can add a `"2028": 0.05` override via PUT /api/v1/settings/nakshatra_transition_step_days
-- before the next time 2028 is regenerated.
INSERT INTO app_setting (key, value, updated_at) VALUES
  ('seed_year_range', '{"start_year": 2021, "end_year": 2030}', now()),
  ('default_location_code', '{"code": "tvm"}', now()),
  ('max_generate_span_days', '{"max_days": 366}', now()),
  ('max_event_generate_year_span', '{"max_years": 15}', now()),
  ('event_cutoffs', '{"nazhika_cutoff": 7.5, "transition_hour_cutoff": 3.0}', now()),
  ('nakshatra_transition_step_days', '{"default": 0.01, "overrides": {}}', now()),
  ('astronomy_epsilons', '{"nakshatra_epsilon": 1e-8, "kollavarsham_epsilon": 1e-6}', now())
ON CONFLICT (key) DO NOTHING;
