import os
import sqlite3
from typing import Generator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

try:
    # Optional: load a local .env so developers don't have to export the URL by
    # hand. In production (Docker / Neon) the variable is provided by the
    # environment, so a missing python-dotenv is not fatal.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _resolve_database_url() -> str:
    """Read the Postgres/Neon connection string from the environment.

    The credentials and host live entirely in ``DATABASE_URL`` (e.g. a Neon
    ``postgresql://user:password@host/db?sslmode=require`` string) — nothing is
    hardcoded here. SQLAlchemy dropped support for the bare ``postgres://``
    scheme that some providers still emit, so normalise it to ``postgresql://``.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Provide a Postgres connection string, e.g. "
            "postgresql://user:password@host/dbname?sslmode=require "
            "(see .env.example)."
        )
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


DATABASE_URL = _resolve_database_url()

# Neon is serverless Postgres and drops idle connections; ``pool_pre_ping``
# discards a dead connection instead of handing it to a request, and
# ``pool_recycle`` proactively refreshes connections before the server closes
# them. ``sslmode=require`` is expected to be part of DATABASE_URL for Neon.
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    # No-op against Postgres — the guard only fires for SQLite connections, which
    # the test suite uses. Kept so FK enforcement / ON DELETE CASCADE behave the
    # same in tests as they do natively in Postgres.
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def init_db() -> None:
    import app.db.models  # noqa: F401 — registers all model classes with SQLModel metadata
    SQLModel.metadata.create_all(engine)
    print("Database schema ensured")
