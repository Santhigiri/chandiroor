"""Tests for db/seed.py — lookup-table seeding from the Python enums."""
from sqlmodel import select

from app.db.models.location import Location as LocationRow
from app.db.models.malayalam_masa import MalayalamMasa as MalayalamMasaRow
from app.db.models.nakshatra import Nakshatra as NakshatraRow
from app.db.models.paksha import Paksha as PakshaRow
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.models.thithi import Thithi as ThithiRow
from app.db.seed import seed_lookup_tables
from app.utils.location import Location
from app.utils.malayalam_masa import MalayalamMasa
from panchangam_astronomy.enums.nakshatra import Nakshatra
from panchangam_astronomy.enums.paksha import Paksha
from app.utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID
from panchangam_astronomy.enums.thithi import Thithi


def _count(session, model) -> int:
    return len(session.exec(select(model)).all())


def test_seed_inserts_exact_enum_counts(session):
    seed_lookup_tables(session)

    assert _count(session, PakshaRow) == len(list(Paksha))
    assert _count(session, ThithiRow) == 30
    assert _count(session, NakshatraRow) == 27
    assert _count(session, MalayalamMasaRow) == 12
    assert _count(session, LocationRow) == len(list(Location))
    assert _count(session, SanthigiriEventRow) == len(EVENT_DEFINITIONS_BY_ID)


def test_seed_carries_day_offset_from_event_condition(session):
    seed_lookup_tables(session)

    for event in EVENT_DEFINITIONS_BY_ID.values():
        row = session.get(SanthigiriEventRow, event.id)
        assert row.day_offset == event.event_condition.day_offset


def test_seed_values_match_enums(session):
    seed_lookup_tables(session)

    poornima = session.get(ThithiRow, Thithi.POORNIMA.id)
    assert poornima is not None
    assert poornima.name == Thithi.POORNIMA.name
    assert poornima.paksha_id == Thithi.POORNIMA.paksha.id
    assert poornima.day == Thithi.POORNIMA.day
    assert poornima.ml == Thithi.POORNIMA.ml
    assert poornima.en == Thithi.POORNIMA.en

    chothi = session.get(NakshatraRow, Nakshatra.CHOTHI.id)
    assert chothi is not None
    assert (chothi.name, chothi.ml, chothi.en) == (
        Nakshatra.CHOTHI.name,
        Nakshatra.CHOTHI.ml,
        Nakshatra.CHOTHI.en,
    )

    masa = session.get(MalayalamMasaRow, MalayalamMasa.MEENAM.id)
    assert masa is not None and masa.name == MalayalamMasa.MEENAM.name

    tvm = session.get(LocationRow, Location.TVM.id)
    assert tvm is not None
    assert tvm.name == Location.TVM.code
    assert tvm.label == Location.TVM.label
    assert tvm.latitude == Location.TVM.latitude
    assert tvm.longitude == Location.TVM.longitude
    assert tvm.timezone == Location.TVM.timezone


def test_seed_is_idempotent(session):
    """Re-seeding must not raise or duplicate rows (session.merge on existing PKs)."""
    seed_lookup_tables(session)
    seed_lookup_tables(session)

    assert _count(session, ThithiRow) == 30
    assert _count(session, NakshatraRow) == 27
    assert _count(session, MalayalamMasaRow) == 12
    assert _count(session, PakshaRow) == len(list(Paksha))
    assert _count(session, LocationRow) == len(list(Location))
