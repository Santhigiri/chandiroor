"""
End-to-end tests for the Kollavarsham CRUD endpoints under
``/api/v1/panchangam/kollavarsham``.

Uses an in-memory SQLite engine seeded from the real 2022 pickle (so a ``/year``
ETag rebuild reads entirely from the DB) plus an admin and a regular user.
Mutations require the ``admin`` role, so the write requests carry an admin bearer
token (mirroring ``tests/test_auth.py``); reading a single record is public.

Because a panchangam day is invalid without its Kollavarsham child, ``DELETE``
removes the whole day — after which reads for that date 404 at this endpoint and
the ``/year`` payload recomputes that one date live.
"""
from __future__ import annotations

import datetime
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
from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from db.user_repository import UserRepository
from main import app
from services.etag_service import refresh_etags, year_key
from utils.roles import Role

BASE_URL = "/api/v1/panchangam/kollavarsham"
PICKLE_2022 = "data/panchangam_2022.pkl"
YEAR = 2022
TEST_DATE = datetime.date(2022, 6, 15)

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
        PanchangamRepository(s).upsert_many(cache.values())
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
        return EtagRepository(s).get(year_key(YEAR))


def _drop_kv(api_engine, dt: datetime.date) -> None:
    """Remove only the Kollavarsham row for *dt*, leaving its panchangam parent."""
    with Session(api_engine) as s:
        row = s.get(KollavarshamDateRow, dt)
        s.delete(row)
        s.commit()


# ── Authorization ────────────────────────────────────────────────────────────────

def test_create_requires_authentication(client):
    r = client.post(BASE_URL, json={"date": "2022-06-15", "kv_day": 1, "kv_month": 11, "kv_year": 1197})
    assert r.status_code == 401


def test_create_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        BASE_URL,
        headers=user_auth,
        json={"date": "2022-06-15", "kv_day": 1, "kv_month": 11, "kv_year": 1197},
    )
    assert r.status_code == 403


def test_update_and_delete_require_admin(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    assert client.put(f"{BASE_URL}/2022-06-15", json={"kv_day": 2}).status_code == 401
    assert (
        client.put(f"{BASE_URL}/2022-06-15", headers=user_auth, json={"kv_day": 2}).status_code
        == 403
    )
    assert client.delete(f"{BASE_URL}/2022-06-15").status_code == 401
    assert client.delete(f"{BASE_URL}/2022-06-15", headers=user_auth).status_code == 403


def test_get_single_record_is_public(client):
    # No credentials: the read must pass the anonymous guard (not 401/403).
    assert client.get(f"{BASE_URL}/2022-06-15").status_code == 200


# ── Read ───────────────────────────────────────────────────────────────────────

def test_get_existing_record(client):
    r = client.get(f"{BASE_URL}/2022-06-15")
    assert r.status_code == 200
    data = r.json()
    assert data["date"] == "2022-06-15"
    assert 1 <= data["kv_month"] <= 12
    assert data["kv_month_name_en"]  # resolved name present
    assert data["kv_month_name_ml"]


def test_get_missing_record_is_404(client):
    assert client.get(f"{BASE_URL}/1999-01-01").status_code == 404


# ── Create ─────────────────────────────────────────────────────────────────────

def test_create_record(client, admin_auth, api_engine):
    # Simulate a gap: the panchangam day exists but its kv row is missing.
    _drop_kv(api_engine, TEST_DATE)
    assert client.get(f"{BASE_URL}/2022-06-15").status_code == 404

    body = {"date": "2022-06-15", "kv_day": 3, "kv_month": 11, "kv_year": 1197}
    r = client.post(BASE_URL, headers=admin_auth, json=body)
    assert r.status_code == 201
    data = r.json()
    assert data["date"] == "2022-06-15"
    assert data["kv_day"] == 3
    assert data["kv_month"] == 11
    assert data["kv_year"] == 1197
    assert data["kv_month_name_en"] == "Kumbham"


def test_create_duplicate_conflicts(client, admin_auth):
    # 2022-06-15 already has kv from the pickle seed.
    r = client.post(
        BASE_URL,
        headers=admin_auth,
        json={"date": "2022-06-15", "kv_day": 1, "kv_month": 11, "kv_year": 1197},
    )
    assert r.status_code == 409


def test_create_without_panchangam_day_is_400(client, admin_auth):
    r = client.post(
        BASE_URL,
        headers=admin_auth,
        json={"date": "1999-01-01", "kv_day": 1, "kv_month": 11, "kv_year": 1174},
    )
    assert r.status_code == 400


def test_create_invalid_month_is_422(client, admin_auth, api_engine):
    _drop_kv(api_engine, TEST_DATE)
    r = client.post(
        BASE_URL,
        headers=admin_auth,
        json={"date": "2022-06-15", "kv_day": 1, "kv_month": 99, "kv_year": 1197},
    )
    assert r.status_code == 422


def test_create_bumps_year_etag(client, admin_auth, api_engine):
    _drop_kv(api_engine, TEST_DATE)
    before = _stored_year_etag(api_engine)
    client.post(
        BASE_URL,
        headers=admin_auth,
        json={"date": "2022-06-15", "kv_day": 9, "kv_month": 11, "kv_year": 1197},
    )
    assert _stored_year_etag(api_engine) != before


# ── Update ─────────────────────────────────────────────────────────────────────

def test_update_is_partial(client, admin_auth):
    original = client.get(f"{BASE_URL}/2022-06-15").json()
    r = client.put(
        f"{BASE_URL}/2022-06-15",
        headers=admin_auth,
        json={"kv_day": 27},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["kv_day"] == 27
    assert data["kv_month"] == original["kv_month"]   # unchanged
    assert data["kv_year"] == original["kv_year"]     # unchanged


def test_update_missing_record_is_404(client, admin_auth):
    r = client.put(f"{BASE_URL}/1999-01-01", headers=admin_auth, json={"kv_day": 2})
    assert r.status_code == 404


def test_update_bumps_year_etag(client, admin_auth, api_engine):
    before = _stored_year_etag(api_engine)
    client.put(f"{BASE_URL}/2022-06-15", headers=admin_auth, json={"kv_day": 30})
    assert _stored_year_etag(api_engine) != before


# ── Delete ─────────────────────────────────────────────────────────────────────

def test_delete_record(client, admin_auth):
    assert client.delete(f"{BASE_URL}/2022-06-15", headers=admin_auth).status_code == 204
    assert client.get(f"{BASE_URL}/2022-06-15").status_code == 404


def test_delete_missing_record_is_404(client, admin_auth):
    assert client.delete(f"{BASE_URL}/1999-01-01", headers=admin_auth).status_code == 404


def test_delete_removes_the_whole_day(client, admin_auth):
    # After delete the panchangam day is gone; the single-day endpoint recomputes
    # it live rather than 500ing on an orphaned row.
    client.delete(f"{BASE_URL}/2022-06-15", headers=admin_auth)
    r = client.get("/api/v1/panchangam/day", params={"day": "2022-06-15"})
    assert r.status_code == 200
