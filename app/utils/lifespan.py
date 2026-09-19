from contextlib import asynccontextmanager
from time import time

from fastapi import FastAPI

from app.db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    start = time()

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

    elapsed = time() - start
    print(f"Database ready in {elapsed:.3f}s")

    yield

    print("Shutdown")
