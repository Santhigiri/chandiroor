import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from db.models import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./panchangam.db")

engine = create_engine(
    DATABASE_URL,
    # Required for SQLite when the same connection is used across threads
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def create_tables() -> None:
    """Create all tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that yields a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
