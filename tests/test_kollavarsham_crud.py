"""
End-to-end tests for the Kollavarsham create/update endpoints under
``/api/v1/panchangam/kollavarsham``.

Both mutations are range-oriented: a request carries ``start_date`` and an
optional ``end_date`` and applies its values to every date in the inclusive span
(a single day when ``end_date`` is omitted). There is no delete endpoint — a
panchangam day is invalid without its Kollavarsham child.

Uses an in-memory SQLite engine seeded from the real 2022 pickle (so a ``/year``
ETag rebuild reads entirely from the DB) plus an admin and a regular user.
Mutations require the ``admin`` role, so the write requests carry an admin bearer
token (mirroring ``tests/test_auth.py``); reading a single record is public.
"""
from __future__ import annotations

import datetime
import pickle

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, col, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — register every table on SQLModel.metadata
from core.security import hash_password
from db.database import get_session
from db.etag_repository import EtagRepository
from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from db.models.panchangam import Panchangam as PanchangamRow
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from db.user_repository import UserRepository
from main import app
from services.etag_service import refresh_etags, year_key
from utils.roles import Role

BASE_URL = "/api/v1/panchangam/kollavarsham"
PICKLE_2022 = "data/panchangam_2022.pkl"
YEAR = 2022

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


def _drop_kv(api_engine, *dates: datetime.date) -> None:
    """Remove only the Kollavarsham rows for *dates*, leaving their panchangam parents.

    Simulates a date whose panchangam day exists but has no kv yet — the state a
    create is meant to fill (the create re-adds the kv before any /year rebuild).
    """
    with Session(api_engine) as s:
        for dt in dates:
            row = s.get(KollavarshamDateRow, dt)
            if row is not None:
                s.delete(row)
        s.commit()


def _drop_day(api_engine, *dates: datetime.date) -> None:
    """Remove whole panchangam days for *dates* (kv cascades) — a true gap.

    Such a date has neither a panchangam row nor kv, so reads/ETag rebuilds fall
    back to live computation for it rather than hitting an orphaned row.
    """
    with Session(api_engine) as s:
        # Core DELETE so the DB-level ON DELETE CASCADE removes kv & children,
        # rather than the ORM trying to blank out their primary-key foreign keys.
        for dt in dates:
            s.exec(delete(PanchangamRow).where(col(PanchangamRow.date) == dt))
        s.commit()


# ── Authorization ────────────────────────────────────────────────────────────────

def test_create_requires_authentication(client):
    r = client.post(BASE_URL, json={"start_date": "2022-06-15", "kv_day": 1, "kv_month": 11, "kv_year": 1197})
    assert r.status_code == 401


def test_create_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        BASE_URL,
        headers=user_auth,
        json={"start_date": "2022-06-15", "kv_day": 1, "kv_month": 11, "kv_year": 1197},
    )
    assert r.status_code == 403


def test_update_requires_admin(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    body = {"start_date": "2022-06-15", "kv_day": 2}
    assert client.put(BASE_URL, json=body).status_code == 401
    assert client.put(BASE_URL, headers=user_auth, json=body).status_code == 403


def test_no_delete_endpoint(client, admin_auth):
    # DELETE is intentionally not exposed — a day cannot lose its kv data.
    assert client.delete(f"{BASE_URL}/2022-06-15", headers=admin_auth).status_code == 405


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


# ── Create (single day) ─────────────────────────────────────────────────────────

def test_create_single_day(client, admin_auth, api_engine):
    dt = datetime.date(2022, 6, 15)
    _drop_kv(api_engine, dt)  # simulate a gap: panchangam day exists, kv missing
    assert client.get(f"{BASE_URL}/2022-06-15").status_code == 404

    body = {"start_date": "2022-06-15", "kv_day": 3, "kv_month": 11, "kv_year": 1197}
    r = client.post(BASE_URL, headers=admin_auth, json=body)
    assert r.status_code == 201
    data = r.json()
    assert isinstance(data, list) and len(data) == 1
    assert data[0]["date"] == "2022-06-15"
    assert data[0]["kv_day"] == 3
    assert data[0]["kv_month_name_en"] == "Kumbham"


def test_create_duplicate_conflicts(client, admin_auth):
    # 2022-06-15 already has kv from the pickle seed.
    r = client.post(
        BASE_URL,
        headers=admin_auth,
        json={"start_date": "2022-06-15", "kv_day": 1, "kv_month": 11, "kv_year": 1197},
    )
    assert r.status_code == 409


def test_create_without_panchangam_day_is_400(client, admin_auth):
    r = client.post(
        BASE_URL,
        headers=admin_auth,
        json={"start_date": "1999-01-01", "kv_day": 1, "kv_month": 11, "kv_year": 1174},
    )
    assert r.status_code == 400


def test_create_invalid_month_is_422(client, admin_auth, api_engine):
    _drop_kv(api_engine, datetime.date(2022, 6, 15))
    r = client.post(
        BASE_URL,
        headers=admin_auth,
        json={"start_date": "2022-06-15", "kv_day": 1, "kv_month": 99, "kv_year": 1197},
    )
    assert r.status_code == 422


# ── Create (range) ──────────────────────────────────────────────────────────────

def test_create_range(client, admin_auth, api_engine):
    span = [datetime.date(2022, 6, d) for d in range(10, 16)]  # 10th–15th
    _drop_kv(api_engine, *span)

    body = {
        "start_date": "2022-06-10",
        "end_date": "2022-06-15",
        "kv_day": 1,
        "kv_month": 11,
        "kv_year": 1197,
    }
    r = client.post(BASE_URL, headers=admin_auth, json=body)
    assert r.status_code == 201
    data = r.json()
    assert [row["date"] for row in data] == [str(d) for d in span]
    assert all(row["kv_month"] == 11 for row in data)
    # every created date is now individually readable
    assert client.get(f"{BASE_URL}/2022-06-12").json()["kv_year"] == 1197


def test_create_range_is_atomic_on_conflict(client, admin_auth, api_engine):
    # Drop all but one; the surviving row makes the range partly-existing.
    _drop_kv(api_engine, datetime.date(2022, 6, 10), datetime.date(2022, 6, 11))
    body = {
        "start_date": "2022-06-10",
        "end_date": "2022-06-12",  # 12th still has kv → conflict
        "kv_day": 1,
        "kv_month": 11,
        "kv_year": 1197,
    }
    r = client.post(BASE_URL, headers=admin_auth, json=body)
    assert r.status_code == 409
    # Nothing was created: the two dropped dates are still missing.
    assert client.get(f"{BASE_URL}/2022-06-10").status_code == 404
    assert client.get(f"{BASE_URL}/2022-06-11").status_code == 404


def test_create_end_before_start_is_422(client, admin_auth):
    r = client.post(
        BASE_URL,
        headers=admin_auth,
        json={"start_date": "2022-06-15", "end_date": "2022-06-01", "kv_day": 1, "kv_month": 11, "kv_year": 1197},
    )
    assert r.status_code == 422


def test_create_bumps_year_etag(client, admin_auth, api_engine):
    _drop_kv(api_engine, datetime.date(2022, 6, 15))
    before = _stored_year_etag(api_engine)
    client.post(
        BASE_URL,
        headers=admin_auth,
        json={"start_date": "2022-06-15", "kv_day": 9, "kv_month": 11, "kv_year": 1197},
    )
    assert _stored_year_etag(api_engine) != before


# ── Update (single day) ──────────────────────────────────────────────────────────

def test_update_is_partial(client, admin_auth):
    original = client.get(f"{BASE_URL}/2022-06-15").json()
    r = client.put(BASE_URL, headers=admin_auth, json={"start_date": "2022-06-15", "kv_day": 27})
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1 and data[0]["kv_day"] == 27
    assert data[0]["kv_month"] == original["kv_month"]  # unchanged
    assert data[0]["kv_year"] == original["kv_year"]    # unchanged


def test_update_empty_body_is_422(client, admin_auth):
    # No value field provided → nothing to change.
    r = client.put(BASE_URL, headers=admin_auth, json={"start_date": "2022-06-15"})
    assert r.status_code == 422


def test_update_missing_range_is_404(client, admin_auth):
    r = client.put(
        BASE_URL,
        headers=admin_auth,
        json={"start_date": "1999-01-01", "end_date": "1999-01-05", "kv_year": 1174},
    )
    assert r.status_code == 404


# ── Update (range) ──────────────────────────────────────────────────────────────

def test_update_range_bulk_corrects(client, admin_auth):
    body = {"start_date": "2022-06-10", "end_date": "2022-06-20", "kv_year": 9999}
    r = client.put(BASE_URL, headers=admin_auth, json=body)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 11
    assert all(row["kv_year"] == 9999 for row in data)
    # persisted
    assert client.get(f"{BASE_URL}/2022-06-15").json()["kv_year"] == 9999


def test_update_range_skips_gaps(client, admin_auth, api_engine):
    # Punch a real hole (no panchangam day) in the middle; update skips it, not 404.
    _drop_day(api_engine, datetime.date(2022, 6, 12))
    body = {"start_date": "2022-06-10", "end_date": "2022-06-14", "kv_year": 8888}
    r = client.put(BASE_URL, headers=admin_auth, json=body)
    assert r.status_code == 200
    dates = [row["date"] for row in r.json()]
    assert "2022-06-12" not in dates
    assert "2022-06-11" in dates and "2022-06-13" in dates


def test_update_bumps_year_etag(client, admin_auth, api_engine):
    before = _stored_year_etag(api_engine)
    client.put(BASE_URL, headers=admin_auth, json={"start_date": "2022-06-15", "kv_day": 30})
    assert _stored_year_etag(api_engine) != before
