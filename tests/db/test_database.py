"""Tests for db/database.py — schema creation and SQLite FK enforcement."""
import datetime

import pytest
from sqlalchemy import delete, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

import db.database as database
from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from db.models.panchangam import Panchangam as PanchangamRow
from db.models.sunrise_sunset import SunriseSunset as SunriseSunsetRow
from db.models.thithi_transition import ThithiTransition as ThithiTransitionRow
from db.repository import PanchangamRepository

EXPECTED_TABLES = {
    "paksha",
    "nakshatra",
    "thithi",
    "malayalam_masa",
    "location",
    "panchangam",
    "kollavarsham_date",
    "sunrise_sunset",
    "thithi_transitions",
    "nakshatra_transitions",
    "santhigiri_event",
    "santhigiri_event_dates",
}


def test_init_db_creates_all_tables(temp_db):
    """init_db() creates every model table in the (patched) database file."""
    database.init_db()

    tables = set(inspect(temp_db).get_table_names())
    assert EXPECTED_TABLES <= tables
    assert len(EXPECTED_TABLES) == 12


def test_foreign_keys_pragma_enabled(engine):
    """The global connect listener turns foreign key enforcement ON."""
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1


def test_invalid_foreign_key_rejected(seeded_session):
    """Inserting a panchangam row with an unknown thithi_id raises IntegrityError."""
    seeded_session.add(
        PanchangamRow(
            date=datetime.date(2026, 1, 2),
            is_pournami=True,
            thithi_id=999,        # no such thithi
            nakshatra_id=1,
            nazhika_from_sunrise=0.0,
        )
    )
    with pytest.raises(IntegrityError):
        seeded_session.commit()


def test_delete_panchangam_cascades_to_children(seeded_session, make_panchangam_data):
    """Deleting a panchangam row cascades to its child rows (ON DELETE CASCADE)."""
    date = datetime.date(2026, 1, 2)
    PanchangamRepository(seeded_session).upsert(make_panchangam_data(date))
    seeded_session.commit()

    # Children exist before the delete.
    assert seeded_session.get(KollavarshamDateRow, date) is not None
    assert seeded_session.exec(
        select(SunriseSunsetRow).where(SunriseSunsetRow.date == date)
    ).all()
    assert seeded_session.exec(
        select(ThithiTransitionRow).where(ThithiTransitionRow.panchangam_date == date)
    ).all()

    # Issue a Core DELETE so SQLite's ON DELETE CASCADE (not SQLAlchemy's
    # ORM-level cascade) removes the children — that is what production relies on.
    seeded_session.exec(delete(PanchangamRow).where(PanchangamRow.date == date))
    seeded_session.commit()

    # ... and are gone afterwards.
    assert seeded_session.get(KollavarshamDateRow, date) is None
    assert not seeded_session.exec(
        select(SunriseSunsetRow).where(SunriseSunsetRow.date == date)
    ).all()
    assert not seeded_session.exec(
        select(ThithiTransitionRow).where(ThithiTransitionRow.panchangam_date == date)
    ).all()
