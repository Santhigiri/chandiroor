from contextlib import asynccontextmanager
from time import time

from fastapi import FastAPI
from sqlmodel import Session

from app.features.auth.ports import UserCreate
from core.config import settings
from core.security import hash_password
from db.database import engine, init_db
from features.auth.auth_repository import AuthRepository
from utils.roles import Role


def _seed_admin_user() -> None:
    """
    Create the initial admin from ``INITIAL_ADMIN_USERNAME`` / ``_PASSWORD`` if
    both are configured and the user does not already exist. Idempotent — a
    no-op once the admin has been created (or when the env vars are unset).
    """
    username = settings.initial_admin_username
    password = settings.initial_admin_password
    if not username or not password:
        return

    with Session(engine) as session:
        repo = AuthRepository(session)
        if repo.exists(username):
            return
        repo.create_user(
            UserCreate(
                username=username,
                hashed_password=hash_password(password),
                role=Role.ADMIN,
            )
        )
        print(f"Seeded initial admin user {username!r}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start = time()

    # Ensure the schema exists (idempotent). Seed data is loaded out-of-band via
    # the SQL files in db/sql/ against the Neon/Postgres database — the app no
    # longer imports the pickle cache at startup.
    init_db()
    _seed_admin_user()

    elapsed = time() - start
    print(f"Database ready in {elapsed:.3f}s")

    yield

    print("Shutdown")
