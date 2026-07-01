"""Tests for db/reference_repository.py — reference datasets served from the DB."""
import datetime

from sqlmodel import select

from db.models.santhigiri_significant_date import (
    SanthigiriSignificantDate as SsdRow,
)
from db.reference_repository import ReferenceRepository
from db.repository import PanchangamRepository
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.paksha import Paksha
from utils.santhigiri_events import EventCondition, SanthigiriEvent, SanthigiriEventId
from utils.thithi import Thithi


def _event(id_: SanthigiriEventId, name: str, description: str) -> SanthigiriEvent:
    return SanthigiriEvent(
        id=id_, name=name, description=description, event_condition=EventCondition()
    )


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


# ── Events derived from significant-date occurrences ──────────────────────────

def _seed_events(seeded_session, make_panchangam_data):
    """Two Pournami occurrences (same definition) + one distinct event."""
    repo = PanchangamRepository(seeded_session)
    pournami = _event(SanthigiriEventId.POURNAMI, "Pournami", "full moon day")
    janma = _event(
        SanthigiriEventId.JANMAGRIHA_THEERTHA_YATHRA, "Janmagriha", "chothi day"
    )
    repo.upsert(
        make_panchangam_data(datetime.date(2024, 1, 1), santhigiri_significant_dates=[pournami])
    )
    repo.upsert(
        make_panchangam_data(datetime.date(2024, 1, 2), santhigiri_significant_dates=[pournami])
    )
    repo.upsert(
        make_panchangam_data(datetime.date(2024, 1, 3), santhigiri_significant_dates=[janma])
    )
    seeded_session.commit()


def test_list_events_dedups_across_occurrences(seeded_session, make_panchangam_data):
    _seed_events(seeded_session, make_panchangam_data)

    events = ReferenceRepository(seeded_session).list_events()

    # Two Pournami occurrences collapse to one definition; ordered by event_id.
    assert [e["id"] for e in events] == [
        SanthigiriEventId.JANMAGRIHA_THEERTHA_YATHRA.value,
        SanthigiriEventId.POURNAMI.value,
    ]
    assert events[1]["name"] == "Pournami"
    assert events[1]["description"] == "full moon day"


def test_list_events_reflects_db_edit(seeded_session, make_panchangam_data):
    """Editing the name in the DB changes the endpoint output — the whole point."""
    _seed_events(seeded_session, make_panchangam_data)

    for row in seeded_session.exec(
        select(SsdRow).where(SsdRow.event_id == SanthigiriEventId.POURNAMI.value)
    ).all():
        row.name = "Poornima (corrected)"
        seeded_session.add(row)
    seeded_session.commit()

    events = ReferenceRepository(seeded_session).list_events()
    pournami = next(e for e in events if e["id"] == SanthigiriEventId.POURNAMI.value)
    assert pournami["name"] == "Poornima (corrected)"
