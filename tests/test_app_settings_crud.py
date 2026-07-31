"""
End-to-end tests for the admin settings CRUD endpoints under
``/api/v1/settings``.

Uses an in-memory SQLite engine seeded via ``seed_lookup_tables`` (which now
also seeds default ``app_setting`` rows) plus an admin and a regular user.
Unlike the Santhigiri event definitions, every endpoint here — including
reads — requires the ``admin`` role, mirroring ``tests/test_santhigiri_event_crud.py``'s
fixture pattern.
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
from db.seed import seed_lookup_tables
from db.user_repository import UserRepository
from main import app
from utils.roles import Role

SETTINGS_URL = "/api/v1/settings"
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


def _bearer(client, username, password) -> dict:
    token = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    ).cookies["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth(client) -> dict:
    return _bearer(client, ADMIN_USER, ADMIN_PW)


# ── Authorization ────────────────────────────────────────────────────────────

def test_list_requires_authentication(client):
    assert client.get(SETTINGS_URL).status_code == 401


def test_list_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    assert client.get(SETTINGS_URL, headers=user_auth).status_code == 403


def test_get_one_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    assert (
        client.get(f"{SETTINGS_URL}/seed_year_range", headers=user_auth).status_code
        == 403
    )


def test_update_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.put(
        f"{SETTINGS_URL}/seed_year_range",
        headers=user_auth,
        json={"value": {"start_year": 2021, "end_year": 2035}},
    )
    assert r.status_code == 403


# ── Read ─────────────────────────────────────────────────────────────────────

def test_list_returns_seeded_defaults(client, admin_auth):
    r = client.get(SETTINGS_URL, headers=admin_auth)
    assert r.status_code == 200
    keys = {row["key"] for row in r.json()}
    assert "seed_year_range" in keys
    assert "nakshatra_transition_step_days" in keys


def test_get_seed_year_range_default(client, admin_auth):
    r = client.get(f"{SETTINGS_URL}/seed_year_range", headers=admin_auth)
    assert r.status_code == 200
    assert r.json()["value"] == {"start_year": 2021, "end_year": 2030}


def test_get_unknown_key_is_404(client, admin_auth):
    r = client.get(f"{SETTINGS_URL}/not_a_real_key", headers=admin_auth)
    assert r.status_code == 404


# ── Write ────────────────────────────────────────────────────────────────────

def test_update_seed_year_range(client, admin_auth):
    r = client.put(
        f"{SETTINGS_URL}/seed_year_range",
        headers=admin_auth,
        json={"value": {"start_year": 2021, "end_year": 2035}},
    )
    assert r.status_code == 200
    assert r.json()["value"] == {"start_year": 2021, "end_year": 2035}

    again = client.get(f"{SETTINGS_URL}/seed_year_range", headers=admin_auth)
    assert again.json()["value"] == {"start_year": 2021, "end_year": 2035}


def test_update_unknown_key_is_404(client, admin_auth):
    r = client.put(
        f"{SETTINGS_URL}/not_a_real_key",
        headers=admin_auth,
        json={"value": {"foo": "bar"}},
    )
    assert r.status_code == 404


def test_update_bad_shape_is_400(client, admin_auth):
    r = client.put(
        f"{SETTINGS_URL}/seed_year_range",
        headers=admin_auth,
        json={"value": {"start_year": "not-a-number", "end_year": 2030}},
    )
    assert r.status_code == 400


def test_update_default_location_code_rejects_unknown_code(client, admin_auth):
    r = client.put(
        f"{SETTINGS_URL}/default_location_code",
        headers=admin_auth,
        json={"value": {"code": "not-a-real-location"}},
    )
    assert r.status_code == 400


def test_update_default_location_code_accepts_known_code(client, admin_auth):
    r = client.put(
        f"{SETTINGS_URL}/default_location_code",
        headers=admin_auth,
        json={"value": {"code": "tvm"}},
    )
    assert r.status_code == 200
    assert r.json()["value"] == {"code": "tvm"}


def test_update_nakshatra_step_days_with_year_override(client, admin_auth):
    r = client.put(
        f"{SETTINGS_URL}/nakshatra_transition_step_days",
        headers=admin_auth,
        json={"value": {"default": 0.01, "overrides": {"2028": 0.05}}},
    )
    assert r.status_code == 200
    assert r.json()["value"] == {"default": 0.01, "overrides": {"2028": 0.05}}
