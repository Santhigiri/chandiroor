"""Tests for db/seed.py — lookup-table seeding from the Python enums."""
from sqlmodel import select

from db.models.location import Location as LocationRow
from db.models.malayalam_masa import MalayalamMasa as MalayalamMasaRow
from db.models.nakshatra import Nakshatra as NakshatraRow
from db.models.paksha import Paksha as PakshaRow
from db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from db.models.thithi import Thithi as ThithiRow
from db.seed import seed_lookup_tables
from utils.location import Location
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.paksha import Paksha
from utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID
from utils.thithi import Thithi


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
