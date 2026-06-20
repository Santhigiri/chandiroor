from contextlib import asynccontextmanager
from time import time

from fastapi import FastAPI
from sqlmodel import Session

from db.database import engine, init_db
from db.seed import seed_lookup_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    start = time()

    init_db()
    with Session(engine) as session:
        seed_lookup_tables(session)

    elapsed = time() - start
    print(f"Database ready in {elapsed:.3f}s")

    yield

    print("Shutdown")
