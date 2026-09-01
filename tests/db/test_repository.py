"""Tests for db/repository.py — PanchangamRepository get/set + converters."""
import datetime
import types

import pytest
import pytz
from sqlmodel import Session, select

from app.db.models.location import Location as LocationRow
from app.db.models.panchangam import Panchangam as PanchangamRow
from app.db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from app.db.models.nakshatra_transition import NakshatraTransition as NakshatraTransitionRow
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.models.santhigiri_event_date import (
    SanthigiriEventDate as SsdRow,
)
from app.db.models.sunrise_sunset import SunriseSunset as SunriseSunsetRow
from app.db.models.thithi_transition import ThithiTransition as ThithiTransitionRow
from app.features.panchangam.repository import (
    PanchangamRepository,
    _row_to_panchangam_data,
    event_row_to_event,
)
from app.utils.location import Location
from app.utils.nakshatra import Nakshatra
from app.utils.santhigiri_events import (
    EVENT_DEFINITIONS_BY_ID,
    EventCondition,
    SanthigiriEvent,
)
from app.utils.thithi import Thithi

TVM = Location.TVM


def _pournami_event() -> SanthigiriEvent:
    # name/description now come from the seeded definition, so build from it to
    # keep the get→domain round-trip equal.
    return EVENT_DEFINITIONS_BY_ID["POURNAMI"].model_copy(deep=True)


def _chothi_event() -> SanthigiriEvent:
    return EVENT_DEFINITIONS_BY_ID[
        "JANMAGRIHA_THEERTHA_YATHRA"
    ].model_copy(deep=True)


def _count(session, model) -> int:
    return len(session.exec(select(model)).all())


# A second location that does not exist in the ``Location`` enum, used to prove
# per-location isolation. Its coordinates are irrelevant to the DB round-trip —
# the repository keys everything on ``location.id``.
SECOND_LOCATION = types.SimpleNamespace(
    id=2, code="test2", label="Test City",
    latitude=1.234, longitude=5.678, timezone="UTC",
)


@pytest.fixture
def two_location_session(seeded_session):
    """A seeded session with a second location row (id=2) inserted."""
    seeded_session.add(LocationRow(
        id=SECOND_LOCATION.id, name=SECOND_LOCATION.code, label=SECOND_LOCATION.label,
        latitude=SECOND_LOCATION.latitude, longitude=SECOND_LOCATION.longitude,
        timezone=SECOND_LOCATION.timezone,
    ))
    seeded_session.commit()
    return seeded_session


# ── Round-trip ────────────────────────────────────────────────────────────────

def test_upsert_then_get_roundtrips(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    data = make_panchangam_data(datetime.date(2026, 3, 3))

    repo.upsert(data, TVM)
    seeded_session.commit()

    fetched = repo.get_by_date(data.date, TVM)
    assert fetched == data


def test_roundtrip_with_santhigiri_event(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    data = make_panchangam_data(
        datetime.date(2026, 3, 4),
        santhigiri_significant_dates=[_pournami_event()],
    )

    repo.upsert(data, TVM)
    seeded_session.commit()

    fetched = repo.get_by_date(data.date, TVM)
    assert fetched is not None
    assert len(fetched.santhigiri_significant_dates) == 1
    assert fetched == data


def test_event_row_to_event_maps_day_offset():
    row = SanthigiriEventRow(
        id="SHIFTED", name="Shifted", description="d", sort_order=0, day_offset=3,
    )
    cond = event_row_to_event(row).event_condition
    assert cond.day_offset == 3


def test_event_row_to_event_defaults_day_offset_to_none():
    row = SanthigiriEventRow(id="PLAIN", name="Plain", description="d", sort_order=0)
    cond = event_row_to_event(row).event_condition
    assert cond.day_offset is None


def test_transitions_returned_sorted_by_start_time(seeded_session, make_panchangam_data):
    from app.core.astronomy.thithi_transition import ThithiTransition

    date = datetime.date(2026, 3, 5)
    day = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.timezone.utc)
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
    repo.upsert(data, TVM)
    seeded_session.commit()

    fetched = repo.get_by_date(date, TVM)
    starts = [t.start_time for t in fetched.thithi_transitions]
    assert starts == sorted(starts)


def test_get_by_date_missing_returns_none(seeded_session):
    assert PanchangamRepository(seeded_session).get_by_date(datetime.date(1999, 1, 1), TVM) is None


# ── Timezone-aware input is normalized to UTC ───────────────────────────────
#
# core/astronomy returns tz-aware Asia/Kolkata datetimes for sunrise/sunset and
# transitions. The DB columns are TIMESTAMPTZ via db.models.types.UTCDateTime,
# which converts any aware input to UTC on write and always hands back
# UTC-aware datetimes on read, regardless of the connection's session
# TimeZone — so an IST-aware input round-trips as the equivalent UTC instant.

def test_upsert_normalizes_sunrise_sunset_to_utc(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    date = datetime.date(2026, 8, 1)
    tz = pytz.timezone("Asia/Kolkata")
    data = make_panchangam_data(
        date,
        thithi_transitions=[],
        nakshatra_transitions=[],
    )
    aware_sunrise = tz.localize(datetime.datetime(2026, 8, 1, 6, 17, 16, 917196))
    aware_sunset = tz.localize(datetime.datetime(2026, 8, 1, 18, 39, 51, 962109))
    data = data.model_copy(
        update={"sunrise": aware_sunrise, "sunset": aware_sunset}
    )

    repo.upsert(data, TVM)
    seeded_session.flush()

    row = seeded_session.exec(
        select(SunriseSunsetRow).where(SunriseSunsetRow.date == date)
    ).one()
    assert row.sunrise.tzinfo == datetime.timezone.utc
    assert row.sunset.tzinfo == datetime.timezone.utc
    # Same instant as the IST input, just re-expressed in UTC.
    assert row.sunrise == aware_sunrise
    assert row.sunset == aware_sunset


def test_upsert_normalizes_transitions_to_utc(seeded_session, make_panchangam_data):
    from app.core.astronomy.nakshatra_transition import NakshatraTransition
    from app.core.astronomy.thithi_transition import ThithiTransition

    repo = PanchangamRepository(seeded_session)
    date = datetime.date(2026, 8, 2)
    tz = pytz.timezone("Asia/Kolkata")
    aware_start = tz.localize(datetime.datetime(2026, 8, 1, 23, 7, 48, 10297))
    aware_end = tz.localize(datetime.datetime(2026, 8, 2, 23, 15, 49, 68802))

    data = make_panchangam_data(
        date,
        thithi_transitions=[
            ThithiTransition(
                name=Thithi.CHATURTHI_KRISHNA.en, thithi=Thithi.CHATURTHI_KRISHNA,
                start_time=aware_start, end_time=aware_end,
            )
        ],
        nakshatra_transitions=[
            NakshatraTransition(
                name=Nakshatra.POORURUTTATHI.en, nakshatra=Nakshatra.POORURUTTATHI,
                start_time=aware_start, end_time=aware_end,
            )
        ],
    )

    repo.upsert(data, TVM)
    seeded_session.flush()

    thithi_row = seeded_session.exec(
        select(ThithiTransitionRow).where(ThithiTransitionRow.panchangam_date == date)
    ).one()
    nakshatra_row = seeded_session.exec(
        select(NakshatraTransitionRow).where(NakshatraTransitionRow.panchangam_date == date)
    ).one()

    for row in (thithi_row, nakshatra_row):
        assert row.start_time.tzinfo == datetime.timezone.utc
        assert row.end_time.tzinfo == datetime.timezone.utc
        assert row.start_time == aware_start
        assert row.end_time == aware_end


# ── Multi-location isolation ──────────────────────────────────────────────────

def test_two_locations_same_date_are_independent(two_location_session, make_panchangam_data):
    """Same date, two locations → independent sunrise/nazhika/thithi, no bleed."""
    repo = PanchangamRepository(two_location_session)
    date = datetime.date(2026, 4, 10)

    tvm_data = make_panchangam_data(
        date, thithi=Thithi.POORNIMA, nazhika_from_sunrise=12.5, location=TVM,
    )
    other_data = make_panchangam_data(
        date, thithi=Thithi.AMAVASYA, nazhika_from_sunrise=40.0,
        location=SECOND_LOCATION,
    )
    repo.upsert(tvm_data, TVM)
    repo.upsert(other_data, SECOND_LOCATION)
    two_location_session.commit()

    got_tvm = repo.get_by_date(date, TVM)
    got_other = repo.get_by_date(date, SECOND_LOCATION)

    assert got_tvm.nazhika_from_sunrise == 12.5
    assert got_other.nazhika_from_sunrise == 40.0
    assert got_tvm.thithi == Thithi.POORNIMA
    assert got_other.thithi == Thithi.AMAVASYA
    assert got_tvm.location.code == "tvm"
    assert got_other.location.code == "test2"
    # Two distinct panchangam rows for the one date.
    assert _count(two_location_session, PanchangamRow) == 2


def test_santhigiri_events_shared_across_locations(two_location_session, make_panchangam_data):
    """Ashram events are location-independent: same list for every location."""
    repo = PanchangamRepository(two_location_session)
    date = datetime.date(2026, 4, 11)

    repo.upsert(
        make_panchangam_data(date, santhigiri_significant_dates=[_pournami_event()], location=TVM),
        TVM,
    )
    # The second location's day carries no events of its own.
    repo.upsert(make_panchangam_data(date, location=SECOND_LOCATION), SECOND_LOCATION)
    two_location_session.commit()

    got_tvm = repo.get_by_date(date, TVM)
    got_other = repo.get_by_date(date, SECOND_LOCATION)

    assert [e.id for e in got_tvm.santhigiri_significant_dates] == ["POURNAMI"]
    # Same shared event calendar appears for the other location too.
    assert [e.id for e in got_other.santhigiri_significant_dates] == ["POURNAMI"]
    # Only one underlying (date-keyed) event row despite two locations.
    assert _count(two_location_session, SsdRow) == 1


def test_delete_children_scoped_to_location(two_location_session, make_panchangam_data):
    """Re-upserting one location must not disturb another location's rows."""
    repo = PanchangamRepository(two_location_session)
    date = datetime.date(2026, 4, 12)
    repo.upsert(make_panchangam_data(date, location=TVM), TVM)
    repo.upsert(make_panchangam_data(date, location=SECOND_LOCATION), SECOND_LOCATION)
    two_location_session.commit()

    # Re-upsert TVM only.
    repo.upsert(make_panchangam_data(date, nazhika_from_sunrise=99.0, location=TVM), TVM)
    two_location_session.commit()

    assert repo.get_by_date(date, SECOND_LOCATION) is not None
    assert repo.get_by_date(date, TVM).nazhika_from_sunrise == 99.0
    assert _count(two_location_session, PanchangamRow) == 2


# ── Upsert replace semantics ──────────────────────────────────────────────────

def test_upsert_replaces_children_cleanly(seeded_session, make_panchangam_data):
    from app.core.astronomy.thithi_transition import ThithiTransition

    repo = PanchangamRepository(seeded_session)
    date = datetime.date(2026, 3, 6)
    day = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.timezone.utc)

    repo.upsert(make_panchangam_data(date), TVM)  # default: 1 thithi transition
    seeded_session.commit()

    two = [
        ThithiTransition(name=Thithi.POORNIMA.en, thithi=Thithi.POORNIMA,
                         start_time=day, end_time=day + datetime.timedelta(hours=12)),
        ThithiTransition(name=Thithi.AMAVASYA.en, thithi=Thithi.AMAVASYA,
                         start_time=day + datetime.timedelta(hours=12),
                         end_time=day + datetime.timedelta(hours=20)),
    ]
    repo.upsert(make_panchangam_data(date, thithi_transitions=two), TVM)
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
        repo.upsert(make(d), TVM)
    session.commit()


def test_get_by_date_range_inclusive_and_ordered(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    dates = [datetime.date(2026, 1, d) for d in (1, 2, 3, 4)]
    _seed_dates(repo, seeded_session, make_panchangam_data, dates)

    result = repo.get_by_date_range(datetime.date(2026, 1, 2), datetime.date(2026, 1, 3), TVM)

    assert set(result) == {datetime.date(2026, 1, 2), datetime.date(2026, 1, 3)}
    assert list(result) == sorted(result)


def test_get_by_date_range_empty(seeded_session):
    result = PanchangamRepository(seeded_session).get_by_date_range(
        datetime.date(2030, 1, 1), datetime.date(2030, 1, 31), TVM
    )
    assert result == {}


def test_get_by_month_normal(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    _seed_dates(
        repo, seeded_session, make_panchangam_data,
        [datetime.date(2026, 2, 1), datetime.date(2026, 2, 15),
         datetime.date(2026, 2, 28), datetime.date(2026, 3, 1)],
    )

    feb = repo.get_by_month(2026, 2, TVM)
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

    dec = repo.get_by_month(2026, 12, TVM)
    assert set(dec) == {datetime.date(2026, 12, 1), datetime.date(2026, 12, 31)}
    assert datetime.date(2027, 1, 1) not in dec


# ── Event definition FK ───────────────────────────────────────────────────────

def test_event_name_description_derive_from_definition(seeded_session, make_panchangam_data):
    """Editing the definition changes what get_by_date reconstructs — no stale copy."""
    repo = PanchangamRepository(seeded_session)
    date = datetime.date(2026, 6, 2)
    repo.upsert(make_panchangam_data(date, santhigiri_significant_dates=[_pournami_event()]), TVM)
    seeded_session.commit()

    definition = seeded_session.get(SanthigiriEventRow, "POURNAMI")
    definition.name = "Poornima (edited)"
    definition.description = "edited description"
    seeded_session.add(definition)
    seeded_session.commit()

    event = repo.get_by_date(date, TVM).santhigiri_significant_dates[0]
    assert event.name == "Poornima (edited)"
    assert event.description == "edited description"


def test_deleting_definition_cascades_to_occurrences(seeded_session, make_panchangam_data):
    repo = PanchangamRepository(seeded_session)
    repo.upsert(make_panchangam_data(
        datetime.date(2026, 6, 3), santhigiri_significant_dates=[_pournami_event()]), TVM)
    seeded_session.commit()
    assert _count(seeded_session, SsdRow) == 1

    definition = seeded_session.get(SanthigiriEventRow, "POURNAMI")
    seeded_session.delete(definition)
    seeded_session.commit()

    # ON DELETE CASCADE removed the occurrence row with the definition.
    assert _count(seeded_session, SsdRow) == 0


# ── Converter units ───────────────────────────────────────────────────────────

def test_row_to_panchangam_data_raises_without_kollavarsham():
    """A panchangam row with no kollavarsham child cannot be converted."""
    row = PanchangamRow(
        date=datetime.date(2026, 1, 2), location_id=TVM.id,
        thithi_id=Thithi.POORNIMA.id, nakshatra_id=Nakshatra.CHOTHI.id,
        nazhika_from_sunrise=0.0,
    )
    with pytest.raises(ValueError):
        _row_to_panchangam_data(row, TVM, [])


def test_get_by_date_raises_without_sunrise(seeded_session):
    """get_by_date surfaces the missing-sunrise guard in _row_to_panchangam_data."""
    date = datetime.date(2026, 1, 2)
    seeded_session.add(PanchangamRow(
        date=date, location_id=TVM.id, thithi_id=Thithi.POORNIMA.id,
        nakshatra_id=Nakshatra.CHOTHI.id, nazhika_from_sunrise=0.0,
    ))
    seeded_session.add(KollavarshamDateRow(
        date=date, location_id=TVM.id, kv_day=1, kv_month=12, kv_year=1201,
    ))
    seeded_session.commit()

    with pytest.raises(ValueError):
        PanchangamRepository(seeded_session).get_by_date(date, TVM)


# ── upsert_many ───────────────────────────────────────────────────────────────

def test_upsert_many_commits(engine, seeded_session, make_panchangam_data):
    dates = [datetime.date(2026, 5, d) for d in (1, 2, 3)]
    PanchangamRepository(seeded_session).upsert_many(
        [make_panchangam_data(d) for d in dates], TVM
    )

    # A brand-new session sees the committed rows (upsert_many commits for us).
    with Session(engine) as other:
        assert _count(other, PanchangamRow) == 3
