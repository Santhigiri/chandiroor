"""
Shared fixtures for the DB-layer test suite.

The unit fixtures use a shared in-memory SQLite database (``sqlite://`` with a
``StaticPool`` so every connection sees the same schema/data). Importing
``db.database`` registers its module-level ``PRAGMA foreign_keys = ON`` connect
listener against the SQLAlchemy ``Engine`` class, so FK enforcement and
``ON DELETE CASCADE`` behave exactly as they do in production.
"""
from __future__ import annotations

import datetime as _dt
import os
from typing import Callable, List, Optional

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

# db.database now requires DATABASE_URL (Postgres/Neon) at import time. The tests
# build their own in-memory SQLite engines and never touch the module-level
# engine, so a throwaway value just satisfies the import — no real connection is
# ever opened against it. Must be set before ``import db.database`` below.
os.environ.setdefault("DATABASE_URL", "sqlite://")

# Importing db.database registers the shared "connect" pragma listener that
# turns foreign_keys ON for every SQLite connection, including our test engine.
import app.db.database  # noqa: F401
import app.db.models  # noqa: F401 — register every table on SQLModel.metadata
from app.db.seed import seed_lookup_tables

from app.core.astronomy.nakshatra_transition import NakshatraTransition
from app.core.astronomy.thithi_transition import ThithiTransition
from app.core.calendar.kollavarsham import KollavarshamDate
from app.schemas.location import LocationInfo
from app.schemas.panchangam_data import PanchangamData
from app.utils.location import Location
from app.utils.malayalam_masa import MalayalamMasa
from app.utils.nakshatra import Nakshatra
from app.utils.santhigiri_events import SanthigiriEvent
from app.utils.thithi import Thithi


# ── Engine / session fixtures ─────────────────────────────────────────────────

@pytest.fixture
def engine():
    """A fresh, isolated in-memory SQLite engine with the full schema created."""
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    try:
        yield eng
    finally:
        SQLModel.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session(engine):
    """A Session bound to the in-memory engine (schema only, no seed data)."""
    with Session(engine) as s:
        yield s


@pytest.fixture
def seeded_session(session):
    """A Session with the immutable lookup tables already seeded."""
    seed_lookup_tables(session)
    return session


# ── PanchangamData factory ────────────────────────────────────────────────────

@pytest.fixture
def make_panchangam_data() -> Callable[..., PanchangamData]:
    """
    Factory that builds a valid ``PanchangamData`` from the real domain enums.

    Datetimes are UTC-aware: the DB columns are TIMESTAMPTZ and
    ``db.models.types.UTCDateTime`` normalizes every round trip (on both
    SQLite and Postgres) to UTC-aware, so fixtures must be aware too for
    ``upsert`` → ``get_by_date`` round-trip comparisons to hold.
    """

    def _build(
        date: _dt.date,
        *,
        thithi: Thithi = Thithi.POORNIMA,
        nakshatra: Nakshatra = Nakshatra.CHOTHI,
        nazhika_from_sunrise: float = 12.5,
        kv_month: MalayalamMasa = MalayalamMasa.MEENAM,
        kv_day: int = 5,
        kv_year: int = 1201,
        thithi_transitions: Optional[List[ThithiTransition]] = None,
        nakshatra_transitions: Optional[List[NakshatraTransition]] = None,
        santhigiri_significant_dates: Optional[List[SanthigiriEvent]] = None,
        location: Location = Location.TVM,
    ) -> PanchangamData:
        sunrise = _dt.datetime.combine(date, _dt.time(6, 15), tzinfo=_dt.timezone.utc)
        sunset = _dt.datetime.combine(date, _dt.time(18, 30), tzinfo=_dt.timezone.utc)
        day_start = _dt.datetime.combine(date, _dt.time.min, tzinfo=_dt.timezone.utc)

        if thithi_transitions is None:
            thithi_transitions = [
                ThithiTransition(
                    name=thithi.en,
                    thithi=thithi,
                    start_time=day_start,
                    end_time=day_start + _dt.timedelta(hours=20),
                )
            ]
        if nakshatra_transitions is None:
            nakshatra_transitions = [
                NakshatraTransition(
                    name=nakshatra.en,
                    nakshatra=nakshatra,
                    start_time=day_start,
                    end_time=day_start + _dt.timedelta(hours=20),
                )
            ]

        kv = KollavarshamDate(
            date=date,
            kv_day=kv_day,
            kv_month=kv_month.id,
            kv_year=kv_year,
            kv_month_name_en=kv_month.en,
            kv_month_name_ml=kv_month.ml,
        )

        return PanchangamData(
            date=date,
            kv=kv,
            thithi_transitions=thithi_transitions,
            nakshatra_transitions=nakshatra_transitions,
            thithi=thithi,
            nakshatra=nakshatra,
            sunrise=sunrise,
            sunset=sunset,
            nazhika_from_sunrise=nazhika_from_sunrise,
            santhigiri_significant_dates=santhigiri_significant_dates or [],
            location=LocationInfo.from_location(location),
        )

    return _build


# ── Temp-file DB for the on-disk schema test ──────────────────────────────────

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """
    Point ``db.database`` at a throwaway on-disk SQLite file and return its engine.
    """
    import app.db.database as database

    db_path = tmp_path / "panchangam_test.db"
    test_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )

    monkeypatch.setattr(database, "engine", test_engine)

    yield test_engine
    test_engine.dispose()
