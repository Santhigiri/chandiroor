from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import FastAPI

from app.db.database import init_db
from app.utils.startup_timing import IMPORT_STARTED_AT


@asynccontextmanager
async def lifespan(app: FastAPI):
    start = perf_counter()

    # Defensive safety net only — Alembic (`alembic upgrade head`, run before
    # this process starts; see Dockerfile and db/sql/README.md) is the
    # authoritative way schema changes reach a database. create_all() only
    # creates *missing* tables and never alters an existing one, so it's a
    # harmless no-op once migrations have run; it exists so a local
    # `uvicorn --reload` dev flow that hasn't run migrations yet still gets a
    # usable schema. Seed data is loaded out-of-band via the SQL files in
    # db/sql/ against the Neon/Postgres database — the app no longer imports
    # the pickle cache at startup.
    init_db()

    elapsed = perf_counter() - start
    print(f"Database ready in {elapsed:.3f}s")

    # Total time from the first line of app/main.py to "ready to serve" —
    # always logged, in every environment, not gated behind a debug flag.
    # This is the number that regressed to begin with when the Skyfield/
    # ephemeris stack loaded eagerly at import time instead of lazily on
    # first live computation (see tests/core/astronomy/test_lazy_astronomy.py
    # and app/utils/startup_timing.py) — worth always having visible so a
    # future regression like that one shows up in every boot's logs, not
    # just an ad hoc local benchmark.
    startup_elapsed = perf_counter() - IMPORT_STARTED_AT
    print(f"App startup took {startup_elapsed:.3f}s (import + schema check)")

    yield

    print("Shutdown")
