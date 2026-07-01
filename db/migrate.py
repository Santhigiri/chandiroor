"""
One-shot migration that mirrors the pickle cache into the SQLite database.

``init_db_from_pickle`` is called at startup (see ``utils/lifespan.py``). It
creates the schema if missing and, when the ``panchangam`` table is empty,
imports every date from ``data/panchangam_*.pkl`` into the relational tables.
The runtime read path still serves from the in-memory ``PANCHANGAM_CACHE``; this
DB is a persisted mirror, rebuilt from the pickle files whenever it is absent.
"""
from typing import List

from sqlmodel import Session, select

from db.database import engine, init_db
from db.models.dataset_etag import DatasetEtag as DatasetEtagRow
from db.models.panchangam import Panchangam as PanchangamRow
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables, seed_santhigiri_events_if_empty
from services.etag_service import refresh_etags
from utils.cache_crud import load_cache


def _is_db_populated(session: Session) -> bool:
    """True when at least one panchangam row already exists."""
    return session.exec(select(PanchangamRow).limit(1)).first() is not None


def _has_etags(session: Session) -> bool:
    """True when at least one dataset ETag has been stored."""
    return session.exec(select(DatasetEtagRow).limit(1)).first() is not None


def _stored_years(session: Session) -> List[int]:
    """Distinct calendar years present in the panchangam table, sorted."""
    dates = session.exec(select(PanchangamRow.date)).all()
    return sorted({d.year for d in dates})


def init_db_from_pickle(force: bool = False) -> None:
    """
    Create the DB schema if needed, fill it from the pickle cache, and make sure
    the reference tables and dataset ETags are present.

    The pickle import is a no-op when the ``panchangam`` table already has rows
    (unless ``force`` is set). The santhigiri_event definitions and the dataset
    ETags are (re)computed whenever data is imported, and are also **backfilled**
    for an already-populated DB that predates those tables — so both the /events
    reference and conditional requests work immediately after deploy rather than
    lazily. Lookup tables are seeded before the panchangam rows because
    ``panchangam.thithi_id``/``nakshatra_id`` are foreign keys into them.
    """
    init_db()

    with Session(engine) as session:
        imported = force or not _is_db_populated(session)

        if imported:
            seed_lookup_tables(session)
            cache = load_cache()
            PanchangamRepository(session).upsert_many(cache.values())
            print(f"Imported {len(cache)} dates from pickle into DB")
        else:
            # Backfill reference tables added after this DB was first populated.
            seeded_events = seed_santhigiri_events_if_empty(session)
            if _has_etags(session) and not seeded_events:
                print("DB already populated; skipping pickle import")
                return
            print("DB already populated; backfilling missing reference data / ETags")

        # Precompute ETags for every stored year and the enum references so
        # conditional requests can be answered without rebuilding the payload.
        years = _stored_years(session)
        refresh_etags(session, years)
        print(f"Refreshed ETags for {len(years)} years and enum references")
