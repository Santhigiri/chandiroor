"""Tests for db/reference_repository.py — reference datasets served from the DB."""
from db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from db.reference_repository import ReferenceRepository
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.paksha import Paksha
from utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID, SanthigiriEventId
from utils.thithi import Thithi


# ── Lookup-table datasets ─────────────────────────────────────────────────────

def test_list_thithis_matches_enum_with_nested_paksha(seeded_session):
    thithis = ReferenceRepository(seeded_session).list_thithis()

    assert len(thithis) == 30
    # Ordered by id, and each carries the same shape the endpoint always returned.
    poornima = next(t for t in thithis if t["id"] == Thithi.POORNIMA.id)
    assert poornima["name"] == Thithi.POORNIMA.name
    assert poornima["ml"] == Thithi.POORNIMA.ml
    assert poornima["en"] == Thithi.POORNIMA.en
    assert poornima["paksha"] == {
        "name": Paksha.SHUKLA.name,
        "id": Paksha.SHUKLA.id,
        "ml": Paksha.SHUKLA.ml,
        "en": Paksha.SHUKLA.en,
    }


def test_list_nakshatras_and_masas(seeded_session):
    repo = ReferenceRepository(seeded_session)
    assert len(repo.list_nakshatras()) == 27
    assert len(repo.list_masas()) == 12
    chothi = next(n for n in repo.list_nakshatras() if n["id"] == Nakshatra.CHOTHI.id)
    assert (chothi["name"], chothi["ml"], chothi["en"]) == (
        Nakshatra.CHOTHI.name,
        Nakshatra.CHOTHI.ml,
        Nakshatra.CHOTHI.en,
    )
    meenam = next(m for m in repo.list_masas() if m["id"] == MalayalamMasa.MEENAM.id)
    assert meenam["name"] == MalayalamMasa.MEENAM.name


# ── Events from the editable definition table ─────────────────────────────────

def test_list_events_returns_every_defined_event(seeded_session):
    """All defined events appear regardless of whether they occur in the data."""
    events = ReferenceRepository(seeded_session).list_events()

    assert len(events) == len(EVENT_DEFINITIONS_BY_ID)
    assert {e.id for e in events} == {
        e.id.value for e in EVENT_DEFINITIONS_BY_ID.values()
    }
    # Ordered by the seeded display order (sort_order).
    first = next(iter(EVENT_DEFINITIONS_BY_ID.values()))
    assert events[0].id == first.id.value


def test_list_events_reflects_db_edit(seeded_session):
    """Editing the name in the DB changes the endpoint output — the whole point."""
    row = seeded_session.get(SanthigiriEventRow, SanthigiriEventId.POURNAMI.value)
    assert row is not None
    row.name = "Poornima (corrected)"
    seeded_session.add(row)
    seeded_session.commit()

    events = ReferenceRepository(seeded_session).list_events()
    pournami = next(e for e in events if e.id == SanthigiriEventId.POURNAMI.value)
    assert pournami.name == "Poornima (corrected)"
