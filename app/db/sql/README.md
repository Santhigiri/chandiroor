# SQL seeding files (PostgreSQL / Neon)

Standalone SQL to stand up the Panchangam database on Postgres without the
Python pickle-import path. Apply them in order:

1. **`01_schema.sql`** — `CREATE TABLE` / index DDL for every table. Generated
   from the SQLModel definitions in `db/models/`, so it mirrors the ORM schema
   exactly (autoincrement PKs become `SERIAL`, `datetime` columns become
   `TIMESTAMP WITH TIME ZONE` via `db.models.types.UTCDateTime`).
2. **`02_seed.sql`** — all seed data wrapped in a single transaction:
   - Lookup tables (`paksha`, `nakshatra`, `thithi`, `malayalam_masa`,
     `location`, `santhigiri_event`) from the Python enums / event definitions.
   - Default `app_setting` rows (admin-editable settings — see
     `services/settings_service.py`), one per known `utils.settings_keys.SettingKey`,
     each seeded with a value identical to the hardcoded constant it replaces.
   - 10 years of Panchangam data (2021-01-01 … 2030-12-31, 3652 days):
     `panchangam`, `kollavarsham_date`, `sunrise_sunset`,
     `thithi_transitions`, `nakshatra_transitions`, `santhigiri_event_dates`.

`INSERT`s are ordered to satisfy every foreign key. `dataset_etag` is left empty
on purpose — those values are derived and recomputed by the app.

## Multi-location keying

`panchangam` is keyed by the composite `(date, location_id)`, and its
location-dependent children — `kollavarsham_date`, `sunrise_sunset`,
`thithi_transitions`, `nakshatra_transitions` — all carry a `location_id` and
reference that composite key with `ON DELETE CASCADE`. This lets the same
calendar date hold independent panchangam values for multiple locations
(sunrise/sunset, the thithi/nakshatra active at sunrise, the nazhika, and the
Malayalam date all depend on the observer's coordinates).

`santhigiri_event_dates` is **location-independent** — the ashram observance
calendar is the same for every location — so it is keyed by date alone and is
not a child of the panchangam row.

All seeded data is for the ashram, `location_id = 1` (`tvm`). Additional
locations are added by inserting a `location` row and generating that location's
data.

## Applying

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/01_schema.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/02_seed.sql
```

Timestamps are stored as UTC, matching the `TIMESTAMPTZ` columns.

## Regenerating

These files are a one-time bootstrap snapshot; there is no build-time tool in
this repo that regenerates them anymore (the old `scripts/gen_seed_sql.py` /
pickle-cache pipeline has been removed — base panchangam data and Santhigiri
event occurrences are now (re)computed live against an already-running
Postgres database via the admin `POST /api/v1/panchangam/generate` and
`POST /api/v1/panchangam/events/{event_id}/occurrences` / `.../events/generate`
endpoints, not by regenerating and re-applying SQL files). Standing up a new
database from scratch still uses `01_schema.sql` + `02_seed.sql` as-is; a
`db/models/` schema change only needs a hand-written migration (see below), not
a full regeneration of these files.

## Migrations (Alembic)

Schema changes are now managed by **Alembic**, configured at the repo root
(`alembic.ini`) with its environment/scripts under `db/alembic/`
(`env.py`, `script.py.mako`, `versions/`). `env.py` reads `DATABASE_URL` from
`app.db.database` (the same variable/`.env` the app itself uses) and points
`target_metadata` at `SQLModel.metadata` (`app.db.models` is imported for its
side effect of registering every table), so `alembic revision --autogenerate`
diffs the live database against the current `db/models/` definitions.

`db/sql/migrations/0001`–`0008` (listed below) are retired — they are a
historical record of hand-written `ALTER TABLE` scripts from before Alembic
was adopted, folded into the single Alembic baseline revision
(`db/alembic/versions/6c71c83ad4a0_baseline_schema.py`). Do not add new files
to `db/sql/migrations/`; do not apply the old ones to a database that's
already on Alembic (`alembic_version` table present) — they predate that
baseline and re-running them (e.g. `0008`'s `DROP TABLE "user"`, `0002`'s
`ALTER TABLE "user"` against a database where that table no longer exists)
will error or double-apply.

### Applying migrations

```bash
# Fresh database — creates every table (equivalent to the old 01_schema.sql):
alembic upgrade head
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/sql/02_seed.sql   # then seed data as before

# Already-deployed database that predates Alembic (has all the tables from
# 01_schema.sql/the old migrations, but no alembic_version table yet) — mark
# it as already at the baseline without re-running any DDL:
alembic stamp head

# Bring any database up to the latest schema:
alembic upgrade head
```

The Docker image runs `alembic upgrade head` automatically before starting
`uvicorn` (see `Dockerfile`) — every deploy brings the schema current. For
local development outside Docker, run `alembic upgrade head` yourself after
pulling a change that touches `db/models/` (`app/utils/lifespan.py`'s
`init_db()` is only a defensive `create_all()` fallback for tables Alembic
hasn't created yet; it never `ALTER`s a table, so it cannot apply a column/type
change on its own).

### Adding a new migration

After changing a table in `db/models/`:

```bash
alembic revision --autogenerate -m "add foo column to bar"
```

Then **read the generated file in `db/alembic/versions/`** — autogenerate
reliably detects new/dropped tables and columns, but misses some things (pure
data migrations, some constraint/index renames, server-side defaults) and
needs the same two imports added by hand if `script.py.mako`'s import block
is ever bypassed:

```python
import sqlmodel.sql.sqltypes
import app.db.models.types
```

(`script.py.mako` already includes these for every new revision — they're
needed because SQLModel's `AutoString` and this project's `UTCDateTime`
column type aren't in `sqlalchemy`'s own namespace, which is all Alembic
imports by default.)

Test the migration locally before committing — `alembic upgrade head` then
`alembic downgrade -1` against a scratch database — and commit the generated
file under `db/alembic/versions/`. There is no need to touch `01_schema.sql`
or `db/sql/migrations/` for new changes; those are frozen as the pre-Alembic
historical snapshot.

### Historical migrations (pre-Alembic, retired)

`0004_add_app_setting_table.sql` added the `app_setting` table (DB-backed
admin-editable settings) plus its default rows to an already-deployed
database.

`0006_reference_display_names_nullable.sql` dropped the `NOT NULL` on the
`ml`/`en` columns of `paksha`/`nakshatra`/`thithi`/`malayalam_masa`.

`0007_add_chandra_masa.sql` added the `chandra_masa`/`chandra_masa_date`
tables and `santhigiri_event.chandra_masa_day`/`chandra_masa_month` columns
for a database bootstrapped before the Chandra Masa feature merged
(`582d479`), plus the 12 lookup rows with their `ml`/`en` text.

`0008_drop_user_table.sql` dropped the local `user` table when Chandiroor
became a JWT resource server for TVM (see the project's `CLAUDE.md`,
"Authentication & Authorization").

All of the above are already reflected in the current `db/models/` state and
therefore in the Alembic baseline revision — nothing further needs to be done
with them on a database that's been stamped/upgraded to that baseline.
