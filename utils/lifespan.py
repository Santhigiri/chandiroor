from contextlib import asynccontextmanager
from time import time

from fastapi import FastAPI

from db.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    start = time()

    # Ensure the schema exists (idempotent). Seed data is loaded out-of-band via
    # the SQL files in db/sql/ against the Neon/Postgres database — the app no
    # longer imports the pickle cache at startup.
    init_db()

    elapsed = time() - start
    print(f"Database ready in {elapsed:.3f}s")

    yield

    print("Shutdown")
