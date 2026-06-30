"""
One-shot migration that mirrors the pickle cache into the SQLite database.

``init_db_from_pickle`` is called at startup (see ``utils/lifespan.py``). It
creates the schema if missing and, when the ``panchangam`` table is empty,
imports every date from ``data/panchangam_*.pkl`` into the relational tables.
The runtime read path still serves from the in-memory ``PANCHANGAM_CACHE``; this
DB is a persisted mirror, rebuilt from the pickle files whenever it is absent.
"""
from sqlmodel import Session, select

from db.database import engine, init_db
from db.models.panchangam import Panchangam as PanchangamRow
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from utils.cache_crud import load_cache


def _is_db_populated(session: Session) -> bool:
    """True when at least one panchangam row already exists."""
    return session.exec(select(PanchangamRow).limit(1)).first() is not None


def init_db_from_pickle(force: bool = False) -> None:
    """
    Create the DB schema if needed and fill it from the pickle cache.

    No-op (apart from ``create_all``) when the ``panchangam`` table already has
    rows, unless ``force`` is set. Lookup tables are seeded before the panchangam
    rows because ``panchangam.thithi_id``/``nakshatra_id`` are foreign keys into
    them.
    """
    init_db()

    with Session(engine) as session:
        if not force and _is_db_populated(session):
            print("DB already populated; skipping pickle import")
            return

        seed_lookup_tables(session)

        cache = load_cache()
        PanchangamRepository(session).upsert_many(cache.values())

        print(f"Imported {len(cache)} dates from pickle into DB")
