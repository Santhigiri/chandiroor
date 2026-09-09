# Alembic migrations

Schema migrations for `app/db/models/`, generated with `alembic revision
--autogenerate` and reviewed by hand before committing (autogenerate misses
data backfills, some renames, and CHECK constraints — always read the diff).

## Setup

`app/db/alembic/env.py` resolves the connection string from `DATABASE_URL`
the same way `app/db/database.py` does (same `postgres://` ->
`postgresql://` normalisation) — there is no `sqlalchemy.url` in
`alembic.ini`. It also imports `app.db.models` so `SQLModel.metadata` is
fully populated before Alembic compares it against the database, same as
`init_db()` does at startup.

Run every command below from the repo root, with `DATABASE_URL` set (or a
local `.env`, same as running the app):

```bash
alembic upgrade head          # apply all pending migrations
alembic revision --autogenerate -m "add foo column"   # generate a new one
alembic downgrade -1          # roll back one migration
alembic history                # list migrations
alembic current                # show the DB's current revision
```

## `0001_baseline_schema`

This is a snapshot of the schema as it stood the moment Alembic was
introduced — equivalent to `db/sql/01_schema.sql` plus every hand-written
migration under `db/sql/migrations/` (0001-0006) applied on top of it. Its
`upgrade()` only matters for a brand-new, empty database (e.g. a fresh local
Postgres or a test container) that has never been bootstrapped any other way.

**A database that was already bootstrapped from `db/sql/01_schema.sql` +
`db/sql/02_seed.sql`** (this includes the existing Neon/production database)
is already at this schema — do not run `alembic upgrade head` against it, it
would try to `CREATE TABLE` things that already exist. Instead, tell Alembic
it's already there without touching any DDL:

```bash
alembic stamp 0001_baseline_schema
```

(or `alembic stamp head`, equivalent right after introducing Alembic — but
naming the baseline revision explicitly is safer if new migrations have
landed since). After stamping, `alembic upgrade head` applies only the
migrations that come *after* the baseline.

## Going forward

New schema changes to `app/db/models/` are made through Alembic migrations
here, not through new files in `db/sql/migrations/` — that directory is now
historical (pre-Alembic) and is not being added to. `db/sql/01_schema.sql` /
`02_seed.sql` remain the one-time bootstrap snapshot for standing up a brand
new database from scratch; they are not regenerated when a migration is
added (see `db/sql/README.md`).

Typical workflow for a model change:

1. Edit the SQLModel table definition(s) in `app/db/models/`.
2. `alembic revision --autogenerate -m "<description>"` — inspect the
   generated file under `versions/` and adjust it (column defaults, data
   backfills, renames autogenerate sees as drop+add, etc.).
3. `alembic upgrade head` against a local/dev database to verify it applies
   cleanly, and that `alembic revision --autogenerate` afterwards produces an
   empty diff (confirms the migration matches the models exactly).
4. Apply the same migration to Neon/production (`alembic upgrade head`) as
   part of the deploy, before the new code that depends on the schema change
   goes live.
