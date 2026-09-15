-- Drops the local "user" table. Chandiroor no longer issues its own tokens or
-- stores credentials/profile data — identity is now verified against TVM
-- (the Ashram's auth microservice) via its JWKS; see CLAUDE.md's
-- "Authentication & Authorization" section. A fresh database stood up from
-- db/sql/01_schema.sql never had this table created in the first place.
--
-- For an existing deployed database only:
--
--   psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/migrations/0008_drop_user_table.sql

DROP TABLE IF EXISTS "user";
