"""
End-to-end tests for the v2 reference endpoints under
``/api/v2/panchangam/{thithi,nakshatra,masa,chandra-masa,paksha}``.

These read the row-per-(parent, language_code) translation tables, additive
to the unchanged v1 endpoints (``features/reference/router.py``). Translation
rows are inserted directly in each test body — a real DB gets them from
``db/sql/02_seed.sql``, and a test DB otherwise leaves them empty, same as
``ml``/``en`` on the parent tables (see ``tests/db/test_seed.py``).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.db.database  # noqa: F401 — registers the FK pragma listener
import app.db.models  # noqa: F401 — register every table on SQLModel.metadata
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.core.astronomy.enums.paksha import Paksha
from app.core.astronomy.enums.thithi import Thithi
from app.db.database import get_session
from app.db.models.nakshatra import NakshatraTranslation as NakshatraTranslationRow
from app.db.models.thithi import ThithiTranslation as ThithiTranslationRow
from app.db.seed import seed_lookup_tables
from app.main import app

V2 = "/api/v2/panchangam"


def _data(response):
    """Unwrap the {success, message, data} envelope, asserting it's well-formed."""
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["message"], str) and body["message"]
    return body["data"]


@pytest.fixture
def api_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        seed_lookup_tables(s)
        s.add(ThithiTranslationRow(thithi_id=Thithi.POORNIMA.id, language_code="en", text="Purnima"))
        s.add(ThithiTranslationRow(thithi_id=Thithi.POORNIMA.id, language_code="ml", text="പൗർണമി"))
        s.add(NakshatraTranslationRow(nakshatra_id=Nakshatra.CHOTHI.id, language_code="en", text="Chothi"))
        s.add(NakshatraTranslationRow(nakshatra_id=Nakshatra.CHOTHI.id, language_code="ml", text="ചോതി"))
        s.commit()
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(api_engine):
    def _override():
        with Session(api_engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ── Shape / translations list ──────────────────────────────────────────────────

def test_thithi_v2_returns_every_translation_and_nested_paksha(client):
    r = client.get(f"{V2}/thithi")
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "THITHI_LIST_SUCCESS"
    poornima = next(t for t in body["data"] if t["id"] == Thithi.POORNIMA.id)
    assert poornima["name"] == Thithi.POORNIMA.name
    assert poornima["day"] == Thithi.POORNIMA.day
    assert {(t["language_code"], t["text"]) for t in poornima["translations"]} == {
        ("en", "Purnima"),
        ("ml", "പൗർണമി"),
    }
    assert poornima["paksha"]["id"] == Paksha.SHUKLA.id


def test_nakshatra_v2_returns_every_translation(client):
    r = client.get(f"{V2}/nakshatra")
    assert r.status_code == 200
    body = r.json()
    assert body["message"] == "NAKSHATRA_LIST_SUCCESS"
    chothi = next(n for n in body["data"] if n["id"] == Nakshatra.CHOTHI.id)
    assert {(t["language_code"], t["text"]) for t in chothi["translations"]} == {
        ("en", "Chothi"),
        ("ml", "ചോതി"),
    }


def test_masa_chandra_masa_paksha_v2_are_served(client):
    for path in ("masa", "chandra-masa", "paksha"):
        r = client.get(f"{V2}/{path}")
        assert r.status_code == 200
        assert _data(r)


# ── ?language_code= filtering ───────────────────────────────────────────────────

def test_list_filters_by_language_code(client):
    r = client.get(f"{V2}/thithi", params={"language_code": "en"})
    assert r.status_code == 200
    poornima = next(t for t in _data(r) if t["id"] == Thithi.POORNIMA.id)
    assert poornima["translations"] == [{"language_code": "en", "text": "Purnima"}]
    assert poornima["paksha"]["translations"] == []  # paksha has no seeded translations here


def test_list_rejects_unsupported_language_code(client):
    r = client.get(f"{V2}/thithi", params={"language_code": "fr"})
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["message"] == "VALIDATION_FAILED"


def test_filtered_list_has_its_own_etag_not_the_persisted_all_etag(client):
    all_etag = client.get(f"{V2}/thithi").headers["etag"]
    filtered_etag = client.get(f"{V2}/thithi", params={"language_code": "en"}).headers["etag"]
    assert all_etag != filtered_etag


# ── Auth guard (anonymous read, any supplied token still validated) ────────────

def test_v2_reads_are_public(client):
    assert client.get(f"{V2}/thithi").status_code == 200


def test_v2_rejects_invalid_bearer_token(client):
    r = client.get(f"{V2}/thithi", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code == 401
