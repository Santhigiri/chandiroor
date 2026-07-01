from contextlib import asynccontextmanager
from time import time

from fastapi import FastAPI

from db.migrate import init_db_from_pickle


@asynccontextmanager
async def lifespan(app: FastAPI):
    start = time()

    init_db_from_pickle()

    elapsed = time() - start
    print(f"Database ready in {elapsed:.3f}s")

    yield

    print("Shutdown")
