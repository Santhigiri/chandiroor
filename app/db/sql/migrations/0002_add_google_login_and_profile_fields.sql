-- Adds Google Sign-In support and self-service profile fields to the "user"
-- table: hashed_password becomes nullable (a Google-only account has no local
-- password), plus new columns email, full_name, google_id, date_of_birth,
-- birth_nakshatra. See CLAUDE.md's "Authentication & Authorization" section
-- and db/models/user.py for the authoritative field descriptions.
--
-- For an existing deployed database only. `db/database.py::init_db()`'s
-- `SQLModel.metadata.create_all()` only creates missing tables, it does not
-- ALTER existing ones, so a database bootstrapped before this migration needs
-- it applied once, by hand:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/migrations/0002_add_google_login_and_profile_fields.sql
--
-- A fresh database stood up from db/sql/01_schema.sql already has these
-- columns (that file is regenerated from db/models/ via
-- scripts/gen_seed_sql.py, which picks them up automatically) — do not
-- re-run this file against one.

ALTER TABLE "user" ALTER COLUMN hashed_password DROP NOT NULL;

ALTER TABLE "user" ADD COLUMN IF NOT EXISTS email VARCHAR;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS full_name VARCHAR;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS google_id VARCHAR;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS date_of_birth DATE;
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS birth_nakshatra VARCHAR;

CREATE UNIQUE INDEX IF NOT EXISTS ix_user_email ON "user" (email);
CREATE UNIQUE INDEX IF NOT EXISTS ix_user_google_id ON "user" (google_id);
