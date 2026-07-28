"""
End-to-end tests for the Santhigiri event CRUD endpoints under
``/api/v1/panchangam/events``.

Uses an in-memory SQLite engine seeded with the lookup tables (which include the
default Santhigiri event definitions) plus an admin and a regular user. No
pickle/panchangam data is needed: the created events have no occurrences, so a
delete refreshes only the enum ETags. Each mutation is asserted to be reflected
by the read-only ``GET /panchangam/events`` list and its ETag.

Mutations require the ``admin`` role, so the write requests carry an admin
bearer token (mirroring ``tests/test_auth.py``); reading a single event is
public.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — register every table on SQLModel.metadata
from core.security import hash_password
from db.database import get_session
from db.etag_repository import EtagRepository
from db.seed import seed_lookup_tables
from db.user_repository import UserRepository
from main import app
from services.etag_service import enum_key, refresh_etags
from utils.roles import Role

EVENTS_URL = "/api/v1/panchangam/events"
ADMIN_USER, ADMIN_PW = "admin", "admin-password"
NORMAL_USER, NORMAL_PW = "devotee", "user-password"


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
        refresh_etags(s, [])  # precompute enum ETags exactly as db.migrate does
        repo = UserRepository(s)
        repo.create(ADMIN_USER, hash_password(ADMIN_PW), Role.ADMIN)
        repo.create(NORMAL_USER, hash_password(NORMAL_PW), Role.USER)
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


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _bearer(client, username, password) -> dict:
    token = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth(client) -> dict:
    return _bearer(client, ADMIN_USER, ADMIN_PW)


def _stored_events_etag(api_engine) -> str:
    with Session(api_engine) as s:
        return EtagRepository(s).get(enum_key("events"))


# ── Authorization ────────────────────────────────────────────────────────────────

def test_create_requires_authentication(client):
    r = client.post(
        EVENTS_URL, json={"id": "X", "name": "X", "description": "d"}
    )
    assert r.status_code == 401


def test_create_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        EVENTS_URL,
        headers=user_auth,
        json={"id": "X", "name": "X", "description": "d"},
    )
    assert r.status_code == 403


def test_update_and_delete_require_admin(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    assert client.put(f"{EVENTS_URL}/POURNAMI", json={"name": "x"}).status_code == 401
    assert (
        client.put(f"{EVENTS_URL}/POURNAMI", headers=user_auth, json={"name": "x"}).status_code
        == 403
    )
    assert client.delete(f"{EVENTS_URL}/POURNAMI").status_code == 401
    assert client.delete(f"{EVENTS_URL}/POURNAMI", headers=user_auth).status_code == 403


def test_get_single_event_is_public(client):
    # No credentials: the read must pass the anonymous guard (not 401/403).
    assert client.get(f"{EVENTS_URL}/POURNAMI").status_code == 200


# ── Create ─────────────────────────────────────────────────────────────────────

def test_create_event(client, admin_auth):
    body = {
        "id": "TEST_EVENT",
        "name": "Test Event",
        "description": "A brand new event",
        "en_day": 1,
        "en_month": 1,
    }
    r = client.post(EVENTS_URL, headers=admin_auth, json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["id"] == "TEST_EVENT"
    assert data["name"] == "Test Event"
    assert data["en_day"] == 1
    assert data["nakshatra_id"] is None
    assert data["sort_order"] is not None  # auto-assigned


def test_create_shows_up_in_list_and_bumps_etag(client, admin_auth, api_engine):
    before_etag = _stored_events_etag(api_engine)
    before = client.get(EVENTS_URL)
    assert not any(e["id"] == "TEST_EVENT" for e in before.json())

    client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "TEST_EVENT", "name": "Test Event", "description": "d"},
    )

    after = client.get(EVENTS_URL)
    assert any(e["id"] == "TEST_EVENT" for e in after.json())
    assert _stored_events_etag(api_engine) != before_etag


def test_create_duplicate_id_conflicts(client, admin_auth):
    r = client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "POURNAMI", "name": "dup", "description": "d"},
    )
    assert r.status_code == 409


def test_create_invalid_nakshatra_id_is_422(client, admin_auth):
    r = client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "BAD", "name": "n", "description": "d", "nakshatra_id": 999},
    )
    assert r.status_code == 422


def test_create_self_referential_yield_is_422(client, admin_auth):
    # Caught by the SanthigiriEventCreate model validator before the service is
    # ever called (id is in the same payload) — 422, unlike the update case
    # below, where the id comes from the URL and can only be checked in the
    # service, so it maps to InvalidEventReference (400) instead.
    r = client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "SELFY", "name": "n", "description": "d", "yields_to_event_id": "SELFY"},
    )
    assert r.status_code == 422


def test_create_invalid_yields_to_event_id_is_400(client, admin_auth):
    # yields_to_event_id is a free-form id with no ge/le range to catch a bad
    # value pre-DB (unlike nakshatra_id above) — it only surfaces via the FK's
    # IntegrityError -> InvalidEventReference -> 400, same path as a bad
    # nakshatra_id/thithi_id that isn't caught by a range constraint.
    r = client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "NEWEVT", "name": "n", "description": "d", "yields_to_event_id": "NOPE"},
    )
    assert r.status_code == 400


# ── Read ───────────────────────────────────────────────────────────────────────

def test_get_existing_event(client):
    r = client.get(f"{EVENTS_URL}/POURNAMI")
    assert r.status_code == 200
    assert r.json()["id"] == "POURNAMI"
    assert r.json()["is_poornima"] is True


def test_get_missing_event_is_404(client):
    assert client.get(f"{EVENTS_URL}/NOPE").status_code == 404


# ── Update ─────────────────────────────────────────────────────────────────────

def test_update_is_partial(client, admin_auth):
    r = client.put(
        f"{EVENTS_URL}/POURNAMI",
        headers=admin_auth,
        json={"description": "Updated description"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["description"] == "Updated description"
    assert data["name"] == "Pournami"          # unchanged
    assert data["is_poornima"] is True          # condition untouched


def test_update_missing_event_is_404(client, admin_auth):
    r = client.put(f"{EVENTS_URL}/NOPE", headers=admin_auth, json={"name": "x"})
    assert r.status_code == 404


def test_update_bumps_events_etag(client, admin_auth, api_engine):
    before = _stored_events_etag(api_engine)
    client.put(
        f"{EVENTS_URL}/POURNAMI",
        headers=admin_auth,
        json={"name": "Pournami (edited)"},
    )
    assert _stored_events_etag(api_engine) != before


def test_update_self_referential_yield_is_400(client, admin_auth):
    r = client.put(
        f"{EVENTS_URL}/POURNAMI",
        headers=admin_auth,
        json={"yields_to_event_id": "POURNAMI"},
    )
    assert r.status_code == 400


def test_update_invalid_yields_to_event_id_is_400(client, admin_auth):
    r = client.put(
        f"{EVENTS_URL}/POURNAMI",
        headers=admin_auth,
        json={"yields_to_event_id": "NOPE"},
    )
    assert r.status_code == 400


def test_update_sets_yields_to_event_id(client, admin_auth):
    r = client.put(
        f"{EVENTS_URL}/JANMAGRIHA_THEERTHA_YATHRA",
        headers=admin_auth,
        json={"yields_to_event_id": "NAVAPOOJITHAM"},
    )
    assert r.status_code == 200
    assert r.json()["yields_to_event_id"] == "NAVAPOOJITHAM"


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_delete_event(client, admin_auth):
    client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "TEMP", "name": "temp", "description": "d"},
    )
    assert client.delete(f"{EVENTS_URL}/TEMP", headers=admin_auth).status_code == 204
    assert client.get(f"{EVENTS_URL}/TEMP").status_code == 404


def test_delete_missing_event_is_404(client, admin_auth):
    assert client.delete(f"{EVENTS_URL}/NOPE", headers=admin_auth).status_code == 404


def test_delete_removes_from_list(client, admin_auth):
    client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "TEMP", "name": "temp", "description": "d"},
    )
    client.delete(f"{EVENTS_URL}/TEMP", headers=admin_auth)
    listing = client.get(EVENTS_URL).json()
    assert not any(e["id"] == "TEMP" for e in listing)
