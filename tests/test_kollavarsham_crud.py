"""
End-to-end tests for the Kollavarsham write endpoints under
``/api/v1/panchangam/kollavarsham``.

Uses an in-memory SQLite engine seeded from the real 2022 pickle (so every 2022
date has a ``panchangam`` row, which the ``kollavarsham_date`` FK requires and
which keeps ``refresh_etags`` on the read-from-DB fast path) plus an admin and a
regular user. Mutations require the ``admin`` role, so writes carry an admin
bearer token (mirroring ``tests/test_auth.py``); reading a single date is public.
"""
from __future__ import annotations

import pickle

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — register every table on SQLModel.metadata
from core.security import hash_password
from db.database import get_session
from db.etag_repository import EtagRepository
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from db.user_repository import UserRepository
from main import app
from services.etag_service import refresh_etags, year_key
from utils.location import Location
from utils.roles import Role

PICKLE_2022 = "data/panchangam_2022.pkl"
YEAR = 2022
BASE = "/api/v1/panchangam/kollavarsham"
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
        with open(PICKLE_2022, "rb") as f:
            cache = pickle.load(f)
        PanchangamRepository(s).upsert_many(cache.values(), Location.TVM)
        refresh_etags(s, [YEAR])
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


def _stored_year_etag(api_engine) -> str:
    with Session(api_engine) as s:
        return EtagRepository(s).get(year_key(YEAR, Location.TVM.code))


# ── Authorization ────────────────────────────────────────────────────────────────

def test_generate_requires_authentication(client):
    r = client.post(
        f"{BASE}/generate",
        json={"start_date": "2022-03-01", "end_date": "2022-03-02"},
    )
    assert r.status_code == 401


def test_generate_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        f"{BASE}/generate",
        headers=user_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-02"},
    )
    assert r.status_code == 403


def test_update_requires_admin(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    assert client.put(f"{BASE}/2022-06-15", json={"kv_day": 2}).status_code == 401
    assert (
        client.put(f"{BASE}/2022-06-15", headers=user_auth, json={"kv_day": 2}).status_code
        == 403
    )


def test_get_single_date_is_public(client):
    assert client.get(f"{BASE}/2022-06-15").status_code == 200


# ── Generate ─────────────────────────────────────────────────────────────────────

def test_generate_over_seeded_range(client, admin_auth):
    r = client.post(
        f"{BASE}/generate",
        headers=admin_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-03"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 3
    assert data["years"] == [2022]
    assert data["start_date"] == "2022-03-01"
    assert data["end_date"] == "2022-03-03"


def test_generate_keeps_year_etag_in_lockstep(client, admin_auth, api_engine):
    # Regenerating recomputes the same authoritative values, but the served
    # /year ETag must still equal the stored one afterwards (refresh happened).
    client.post(
        f"{BASE}/generate",
        headers=admin_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-03"},
    )
    served = client.get(
        "/api/v1/panchangam/year", params={"year": YEAR}
    ).headers["etag"]
    assert served == _stored_year_etag(api_engine)


def test_generate_missing_panchangam_is_400(client, admin_auth):
    # 2019 has no panchangam rows, so nothing is generatable.
    r = client.post(
        f"{BASE}/generate",
        headers=admin_auth,
        json={"start_date": "2019-01-01", "end_date": "2019-01-02"},
    )
    assert r.status_code == 400
    assert "2019-01-01" in r.json()["detail"]["missing_dates"]
    # Nothing was written.
    assert client.get(f"{BASE}/2019-01-01").status_code == 404


def test_generate_rejects_reversed_range(client, admin_auth):
    r = client.post(
        f"{BASE}/generate",
        headers=admin_auth,
        json={"start_date": "2022-03-05", "end_date": "2022-03-01"},
    )
    assert r.status_code == 422


# ── Update ───────────────────────────────────────────────────────────────────────

def test_update_overrides_single_date(client, admin_auth):
    current = client.get(f"{BASE}/2022-06-15").json()
    new_day = current["kv_day"] + 1

    r = client.put(
        f"{BASE}/2022-06-15", headers=admin_auth, json={"kv_day": new_day}
    )
    assert r.status_code == 200
    assert r.json()["kv_day"] == new_day
    # Month/year untouched.
    assert r.json()["kv_month"] == current["kv_month"]
    assert r.json()["kv_year"] == current["kv_year"]
    # Reflected on a subsequent read.
    assert client.get(f"{BASE}/2022-06-15").json()["kv_day"] == new_day


def test_update_bumps_year_etag(client, admin_auth, api_engine):
    before = _stored_year_etag(api_engine)
    current = client.get(f"{BASE}/2022-06-15").json()
    client.put(
        f"{BASE}/2022-06-15",
        headers=admin_auth,
        json={"kv_day": current["kv_day"] + 1},
    )
    assert _stored_year_etag(api_engine) != before


def test_update_missing_date_is_404(client, admin_auth):
    r = client.put(f"{BASE}/2019-01-01", headers=admin_auth, json={"kv_day": 2})
    assert r.status_code == 404


def test_update_empty_body_is_422(client, admin_auth):
    r = client.put(f"{BASE}/2022-06-15", headers=admin_auth, json={})
    assert r.status_code == 422
