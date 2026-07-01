"""Tests for db/repository.py — PanchangamRepository get/set + converters."""
import datetime

import pytest
from sqlmodel import Session, select

from db.models.panchangam import Panchangam as PanchangamRow
from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from db.models.santhigiri_event_condition import (
    SanthigiriEventCondition as ConditionRow,
)
from db.models.santhigiri_significant_date import (
    SanthigiriSignificantDate as SsdRow,
)
from db.models.thithi_transition import ThithiTransition as ThithiTransitionRow
from db.repository import (
    PanchangamRepository,
    _event_condition_to_row,
    _row_to_panchangam_data,
)
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import EventCondition, SanthigiriEvent, SanthigiriEventId
from utils.thithi import Thithi


def _pournami_event() -> SanthigiriEvent:
    return SanthigiriEvent(
        id=SanthigiriEventId.POURNAMI,
        name="Pournami",
        description="full moon day",
        event_condition=EventCondition(is_poornima=True),
    )


def _chothi_event() -> SanthigiriEvent:
    return SanthigiriEvent(
        id=SanthigiriEventId.JANMAGRIHA_THEERTHA_YATHRA,
        name="Janmagriha Theertha Yaathra",
        description="chothi day",
        event_condition=EventCondition(nakshatra=Nakshatra.CHOTHI),
    )


def _count(session, model) -> int:
    return len(session.exec(select(model)).all())


# ── Round-trip ────────────────────────────────────────────────────────────────

def test_upsert_then_get_roundtrips(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    data = make_panchangam_data(datetime.date(2026, 3, 3))

    repo.upsert(data)
    seeded_session.commit()

    fetched = repo.get_by_date(data.date)
    assert fetched == data


def test_roundtrip_with_santhigiri_event(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    data = make_panchangam_data(
        datetime.date(2026, 3, 4),
        santhigiri_significant_dates=[_pournami_event()],
    )

    repo.upsert(data)
    seeded_session.commit()

    fetched = repo.get_by_date(data.date)
    assert fetched is not None
    assert len(fetched.santhigiri_significant_dates) == 1
    assert fetched == data


def test_transitions_returned_sorted_by_start_time(seeded_session, make_panchangam_data):
    from core.astronomy.thithi_transition import ThithiTransition

    date = datetime.date(2026, 3, 5)
    day = datetime.datetime.combine(date, datetime.time.min)
    early = ThithiTransition(
        name=Thithi.PRATHAMA_SHUKLA.en, thithi=Thithi.PRATHAMA_SHUKLA,
        start_time=day, end_time=day + datetime.timedelta(hours=10),
    )
    late = ThithiTransition(
        name=Thithi.DWITHIYA_SHUKLA.en, thithi=Thithi.DWITHIYA_SHUKLA,
        start_time=day + datetime.timedelta(hours=10),
        end_time=day + datetime.timedelta(hours=20),
    )
    # Insert deliberately out of order.
    data = make_panchangam_data(date, thithi_transitions=[late, early])

    repo = PanchangamRepository(seeded_session)
    repo.upsert(data)
    seeded_session.commit()

    fetched = repo.get_by_date(date)
    starts = [t.start_time for t in fetched.thithi_transitions]
    assert starts == sorted(starts)


def test_get_by_date_missing_returns_none(seeded_session):
    assert PanchangamRepository(seeded_session).get_by_date(datetime.date(1999, 1, 1)) is None


# ── Upsert replace semantics ──────────────────────────────────────────────────

def test_upsert_replaces_children_cleanly(seeded_session, make_panchangam_data):
    from core.astronomy.thithi_transition import ThithiTransition

    repo = PanchangamRepository(seeded_session)
    date = datetime.date(2026, 3, 6)
    day = datetime.datetime.combine(date, datetime.time.min)

    repo.upsert(make_panchangam_data(date))  # default: 1 thithi transition
    seeded_session.commit()

    two = [
        ThithiTransition(name=Thithi.POORNIMA.en, thithi=Thithi.POORNIMA,
                         start_time=day, end_time=day + datetime.timedelta(hours=12)),
        ThithiTransition(name=Thithi.AMAVASYA.en, thithi=Thithi.AMAVASYA,
                         start_time=day + datetime.timedelta(hours=12),
                         end_time=day + datetime.timedelta(hours=20)),
    ]
    repo.upsert(make_panchangam_data(date, thithi_transitions=two))
    seeded_session.commit()

    rows = seeded_session.exec(
        select(ThithiTransitionRow).where(ThithiTransitionRow.panchangam_date == date)
    ).all()
    assert len(rows) == 2                              # not 3 — old row was cleared
    assert _count(seeded_session, KollavarshamDateRow) == 1
    assert _count(seeded_session, PanchangamRow) == 1


# ── Range / month queries ─────────────────────────────────────────────────────

def _seed_dates(repo, session, make, dates):
    for d in dates:
        repo.upsert(make(d))
    session.commit()


def test_get_by_date_range_inclusive_and_ordered(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    dates = [datetime.date(2026, 1, d) for d in (1, 2, 3, 4)]
    _seed_dates(repo, seeded_session, make_panchangam_data, dates)

    result = repo.get_by_date_range(datetime.date(2026, 1, 2), datetime.date(2026, 1, 3))

    assert set(result) == {datetime.date(2026, 1, 2), datetime.date(2026, 1, 3)}
    assert list(result) == sorted(result)


def test_get_by_date_range_empty(seeded_session):
    result = PanchangamRepository(seeded_session).get_by_date_range(
        datetime.date(2030, 1, 1), datetime.date(2030, 1, 31)
    )
    assert result == {}


def test_get_by_month_normal(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    _seed_dates(
        repo, seeded_session, make_panchangam_data,
        [datetime.date(2026, 2, 1), datetime.date(2026, 2, 15),
         datetime.date(2026, 2, 28), datetime.date(2026, 3, 1)],
    )

    feb = repo.get_by_month(2026, 2)
    assert set(feb) == {
        datetime.date(2026, 2, 1),
        datetime.date(2026, 2, 15),
        datetime.date(2026, 2, 28),
    }


def test_get_by_month_december_boundary(seeded_session, make_panchangam_data):
    """December must roll into the next year to compute its last day."""
    repo = PanchangamRepository(seeded_session)
    _seed_dates(
        repo, seeded_session, make_panchangam_data,
        [datetime.date(2026, 12, 1), datetime.date(2026, 12, 31),
         datetime.date(2027, 1, 1)],
    )

    dec = repo.get_by_month(2026, 12)
    assert set(dec) == {datetime.date(2026, 12, 1), datetime.date(2026, 12, 31)}
    assert datetime.date(2027, 1, 1) not in dec


# ── Event-condition dedup ─────────────────────────────────────────────────────

def test_event_condition_deduplicated_across_dates(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    repo.upsert(make_panchangam_data(
        datetime.date(2026, 4, 1), santhigiri_significant_dates=[_pournami_event()]))
    repo.upsert(make_panchangam_data(
        datetime.date(2026, 4, 2), santhigiri_significant_dates=[_pournami_event()]))
    seeded_session.commit()

    # Same rule on two dates → a single shared condition row.
    assert _count(seeded_session, ConditionRow) == 1
    assert _count(seeded_session, SsdRow) == 2

    # A different rule adds exactly one more condition row.
    repo.upsert(make_panchangam_data(
        datetime.date(2026, 4, 3), santhigiri_significant_dates=[_chothi_event()]))
    seeded_session.commit()
    assert _count(seeded_session, ConditionRow) == 2


def test_delete_children_preserves_shared_condition(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    d1, d2 = datetime.date(2026, 4, 10), datetime.date(2026, 4, 11)
    repo.upsert(make_panchangam_data(d1, santhigiri_significant_dates=[_pournami_event()]))
    repo.upsert(make_panchangam_data(d2, santhigiri_significant_dates=[_pournami_event()]))
    seeded_session.commit()
    assert _count(seeded_session, ConditionRow) == 1

    repo._delete_children(d1)
    seeded_session.commit()

    # d1's significant-date row is gone, d2's remains, the shared rule is kept.
    assert seeded_session.exec(
        select(SsdRow).where(SsdRow.panchangam_date == d1)).all() == []
    assert seeded_session.exec(
        select(SsdRow).where(SsdRow.panchangam_date == d2)).all()
    assert _count(seeded_session, ConditionRow) == 1


# ── Converter units ───────────────────────────────────────────────────────────

def test_event_condition_to_row_none_when_no_criteria():
    event = SanthigiriEvent(
        id=SanthigiriEventId.SAMSKARIKA_DINAM, name="x", description="y",
        event_condition=EventCondition(),
    )
    assert _event_condition_to_row(event) is None


def test_event_condition_to_row_populates_fields():
    row = _event_condition_to_row(_chothi_event())
    assert row is not None
    assert row.event_id == SanthigiriEventId.JANMAGRIHA_THEERTHA_YATHRA.value
    assert row.nakshatra_id == Nakshatra.CHOTHI.id


def test_row_to_panchangam_data_raises_without_kollavarsham():
    """A panchangam row with no kollavarsham child cannot be converted."""
    row = PanchangamRow(
        date=datetime.date(2026, 1, 2), is_pournami=True,
        thithi_id=Thithi.POORNIMA.id, nakshatra_id=Nakshatra.CHOTHI.id,
        nazhika_from_sunrise=0.0,
    )
    with pytest.raises(ValueError):
        _row_to_panchangam_data(row)


def test_get_by_date_raises_without_sunrise(seeded_session):
    """get_by_date surfaces the missing-sunrise guard in _row_to_panchangam_data."""
    date = datetime.date(2026, 1, 2)
    seeded_session.add(PanchangamRow(
        date=date, is_pournami=True, thithi_id=Thithi.POORNIMA.id,
        nakshatra_id=Nakshatra.CHOTHI.id, nazhika_from_sunrise=0.0,
    ))
    seeded_session.add(KollavarshamDateRow(
        date=date, kv_day=1, kv_month=12, kv_year=1201,
    ))
    seeded_session.commit()

    with pytest.raises(ValueError):
        PanchangamRepository(seeded_session).get_by_date(date)


# ── upsert_many ───────────────────────────────────────────────────────────────

def test_upsert_many_commits(engine, seeded_session, make_panchangam_data):
    dates = [datetime.date(2026, 5, d) for d in (1, 2, 3)]
    PanchangamRepository(seeded_session).upsert_many(
        [make_panchangam_data(d) for d in dates]
    )

    # A brand-new session sees the committed rows (upsert_many commits for us).
    with Session(engine) as other:
        assert _count(other, PanchangamRow) == 3
