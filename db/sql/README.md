# SQL seeding files (PostgreSQL / Neon)

Standalone SQL to stand up the Panchangam database on Postgres without the
Python pickle-import path. Apply them in order:

1. **`01_schema.sql`** — `CREATE TABLE` / index DDL for every table. Generated
   from the SQLModel definitions in `db/models/`, so it mirrors the ORM schema
   exactly (autoincrement PKs become `SERIAL`, `datetime` columns become
   `TIMESTAMP WITHOUT TIME ZONE`).
2. **`02_seed.sql`** — all seed data wrapped in a single transaction:
   - Lookup tables (`paksha`, `nakshatra`, `thithi`, `malayalam_masa`,
     `location`, `santhigiri_event`) from the Python enums / event definitions.
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

Timestamps are stored as naive local wall-clock in `Asia/Kolkata`, matching the
tz-naive columns.

## Regenerating

Both files are produced by `scripts/gen_seed_sql.py` (a build-time tool, not
imported at runtime). Re-run it after changing the `db/models/` schema, the
domain enums, the event definitions, or the `data/panchangam_*.pkl` caches.
