"""Tests for db/reference_repository.py — reference datasets served from the DB."""
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.models.thithi import ThithiTranslation as ThithiTranslationRow
from app.db.reference_repository import ReferenceRepository
from app.core.kollavarsham.enums.masa import MalayalamMasa
from app.core.chandramasa.enums.masa import ChandraMasa
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.core.astronomy.enums.paksha import Paksha
from app.utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID
from app.core.astronomy.enums.thithi import Thithi


# ── Lookup-table datasets ─────────────────────────────────────────────────────

def test_list_thithis_matches_enum_with_nested_paksha(seeded_session):
    thithis = ReferenceRepository(seeded_session).list_thithis()

    assert len(thithis) == 30
    # Ordered by id, and each carries the same shape the endpoint always returned.
    # Display text (ml/en) is not seeded in tests — only structural fields are
    # asserted here.
    poornima = next(t for t in thithis if t["id"] == Thithi.POORNIMA.id)
    assert poornima["name"] == Thithi.POORNIMA.name
    assert set(poornima) == {"name", "id", "paksha", "ml", "en"}
    assert poornima["paksha"]["name"] == Paksha.SHUKLA.name
    assert poornima["paksha"]["id"] == Paksha.SHUKLA.id


def test_list_nakshatras_and_masas(seeded_session):
    repo = ReferenceRepository(seeded_session)
    assert len(repo.list_nakshatras()) == 27
    assert len(repo.list_masas()) == 12
    chothi = next(n for n in repo.list_nakshatras() if n["id"] == Nakshatra.CHOTHI.id)
    assert chothi["name"] == Nakshatra.CHOTHI.name
    meenam = next(m for m in repo.list_masas() if m["id"] == MalayalamMasa.MEENAM.id)
    assert meenam["name"] == MalayalamMasa.MEENAM.name


def test_list_chandra_masas(seeded_session):
    repo = ReferenceRepository(seeded_session)
    masas = repo.list_chandra_masas()
    assert len(masas) == 12
    phalguna = next(m for m in masas if m["id"] == ChandraMasa.PHALGUNA.id)
    assert phalguna["name"] == ChandraMasa.PHALGUNA.name


# ── Events from the editable definition table ─────────────────────────────────

def test_list_events_returns_every_defined_event(seeded_session):
    """All defined events appear regardless of whether they occur in the data."""
    events = ReferenceRepository(seeded_session).list_events()

    assert len(events) == len(EVENT_DEFINITIONS_BY_ID)
    assert {e.id for e in events} == {
        e.id for e in EVENT_DEFINITIONS_BY_ID.values()
    }
    # Ordered by the seeded display order (sort_order).
    first = next(iter(EVENT_DEFINITIONS_BY_ID.values()))
    assert events[0].id == first.id


# ── v2: row-per-(parent, language_code) translation reads ─────────────────────

def test_list_thithis_v2_matches_v1_structural_shape_with_no_translations(seeded_session):
    """Translations are empty in a test DB (db/seed.py leaves ml/en NULL, same
    convention as v1) — this asserts the v2 shape/count, not translated text."""
    thithis = ReferenceRepository(seeded_session).list_thithis_v2()

    assert len(thithis) == 30
    poornima = next(t for t in thithis if t.id == Thithi.POORNIMA.id)
    assert poornima.name == Thithi.POORNIMA.name
    assert poornima.day == Thithi.POORNIMA.day
    assert poornima.translations == []
    assert poornima.paksha is not None
    assert poornima.paksha.id == Paksha.SHUKLA.id
    assert poornima.paksha.name == Paksha.SHUKLA.name
    assert poornima.paksha.translations == []


def test_list_nakshatras_v2_and_masas_v2(seeded_session):
    repo = ReferenceRepository(seeded_session)
    nakshatras = repo.list_nakshatras_v2()
    masas = repo.list_masas_v2()

    assert len(nakshatras) == 27
    assert len(masas) == 12
    chothi = next(n for n in nakshatras if n.id == Nakshatra.CHOTHI.id)
    assert chothi.name == Nakshatra.CHOTHI.name
    meenam = next(m for m in masas if m.id == MalayalamMasa.MEENAM.id)
    assert meenam.name == MalayalamMasa.MEENAM.name


def test_list_chandra_masas_v2(seeded_session):
    masas = ReferenceRepository(seeded_session).list_chandra_masas_v2()
    assert len(masas) == 12
    phalguna = next(m for m in masas if m.id == ChandraMasa.PHALGUNA.id)
    assert phalguna.name == ChandraMasa.PHALGUNA.name


def test_list_pakshas_v2(seeded_session):
    pakshas = ReferenceRepository(seeded_session).list_pakshas_v2()
    assert len(pakshas) == 2
    shukla = next(p for p in pakshas if p.id == Paksha.SHUKLA.id)
    assert shukla.name == Paksha.SHUKLA.name


def test_list_thithis_v2_groups_inserted_translation_rows(seeded_session):
    """Inserting translation rows directly (mirroring how a real DB is seeded
    via db/sql/02_seed.sql) groups them correctly onto the right thithi."""
    seeded_session.add(
        ThithiTranslationRow(thithi_id=Thithi.POORNIMA.id, language_code="en", text="Purnima")
    )
    seeded_session.add(
        ThithiTranslationRow(thithi_id=Thithi.POORNIMA.id, language_code="ml", text="പൗർണമി")
    )
    seeded_session.commit()

    thithis = ReferenceRepository(seeded_session).list_thithis_v2()
    poornima = next(t for t in thithis if t.id == Thithi.POORNIMA.id)
    assert {(tr.language_code, tr.text) for tr in poornima.translations} == {
        ("en", "Purnima"),
        ("ml", "പൗർണമി"),
    }
    # Every other thithi stays untranslated.
    other = next(t for t in thithis if t.id != Thithi.POORNIMA.id)
    assert other.translations == []


def test_list_events_reflects_db_edit(seeded_session):
    """Editing the name in the DB changes the endpoint output — the whole point."""
    row = seeded_session.get(SanthigiriEventRow, "POURNAMI")
    assert row is not None
    row.name = "Poornima (corrected)"
    seeded_session.add(row)
    seeded_session.commit()

    events = ReferenceRepository(seeded_session).list_events()
    pournami = next(e for e in events if e.id == "POURNAMI")
    assert pournami.name == "Poornima (corrected)"
