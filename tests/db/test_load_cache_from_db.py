"""Tests for utils.cache_crud.load_cache_from_db.

Proves the offline event pipeline can source its base PanchangamData (sunrise/sunset
+ thithi transitions) from the database instead of the pickle cache, and that Pournami
is then derived from those DB-sourced values via the existing matcher.

The tests drive an in-memory SQLite session (the same engine the rest of tests/db/
uses) into ``load_cache_from_db(session=...)`` — no live Postgres required.
"""
import datetime

from core.astronomy.transitions import ThithiTransition
from db.repository import PanchangamRepository
from utils.cache_crud import load_cache_from_db
from utils.cache_navapoojitham import get_matching_dates
from utils.location import Location
from utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID, POURNAMI
from utils.thithi import Thithi

TVM = Location.TVM

# A full-moon window: the Pournami thithi runs midday->night on D, so D's night
# (sunset 18:30 -> next sunrise 06:15) holds all of it and D is the Pournami day.
D_PREV = datetime.date(2026, 3, 3)
D = datetime.date(2026, 3, 4)
D_NEXT = datetime.date(2026, 3, 5)


def _dt(d: datetime.date, hour: int, minute: int = 0) -> datetime.datetime:
    return datetime.datetime.combine(d, datetime.time(hour, minute))


def _seed_full_moon_window(session, make_panchangam_data) -> None:
    repo = PanchangamRepository(session)

    prev = make_panchangam_data(
        D_PREV,
        thithi=Thithi.CHATURDASHI_SHUKLA,
        thithi_transitions=[
            ThithiTransition(
                name=Thithi.CHATURDASHI_SHUKLA.en,
                thithi=Thithi.CHATURDASHI_SHUKLA,
                start_time=_dt(D_PREV, 0),
                end_time=_dt(D, 12),
            )
        ],
    )
    day = make_panchangam_data(
        D,
        thithi=Thithi.POORNIMA,
        thithi_transitions=[
            ThithiTransition(
                name=Thithi.POORNIMA.en,
                thithi=Thithi.POORNIMA,
                start_time=_dt(D, 12),
                end_time=_dt(D, 23),
            )
        ],
    )
    nxt = make_panchangam_data(
        D_NEXT,
        thithi=Thithi.PRATHAMA_KRISHNA,
        thithi_transitions=[
            ThithiTransition(
                name=Thithi.PRATHAMA_KRISHNA.en,
                thithi=Thithi.PRATHAMA_KRISHNA,
                start_time=_dt(D, 23),
                end_time=_dt(D_NEXT, 22),
            )
        ],
    )

    for data in (prev, day, nxt):
        repo.upsert(data, TVM)
    session.commit()


def test_load_cache_from_db_reads_base_and_derives_pournami(
    seeded_session, make_panchangam_data
):
    _seed_full_moon_window(seeded_session, make_panchangam_data)

    cache = load_cache_from_db(
        start=D_PREV, end=D_NEXT, location=TVM, session=seeded_session
    )

    # Base astronomical values came from the DB.
    assert set(cache) == {D_PREV, D, D_NEXT}
    assert cache[D].sunrise is not None and cache[D].sunset is not None
    assert any(t.thithi == Thithi.POORNIMA for t in cache[D].thithi_transitions)

    # Pournami is derived from those DB-sourced values, attributed to exactly D.
    matched = {d for d, _ in get_matching_dates(cache, POURNAMI.event_condition)}
    assert matched == {D}


def test_load_cache_from_db_clears_events_by_default(
    seeded_session, make_panchangam_data
):
    repo = PanchangamRepository(seeded_session)
    seeded_event = EVENT_DEFINITIONS_BY_ID["POURNAMI"].model_copy(deep=True)
    repo.upsert(
        make_panchangam_data(D, santhigiri_significant_dates=[seeded_event]),
        TVM,
    )
    seeded_session.commit()

    cleared = load_cache_from_db(
        start=D, end=D, location=TVM, session=seeded_session, clear_events=True
    )
    assert cleared[D].santhigiri_significant_dates == []

    kept = load_cache_from_db(
        start=D, end=D, location=TVM, session=seeded_session, clear_events=False
    )
    assert [e.id for e in kept[D].santhigiri_significant_dates] == ["POURNAMI"]
