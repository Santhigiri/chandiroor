"""
Tests for JWT authentication and role-based authorization.

Exercises the auth endpoints end-to-end via ``TestClient`` against an in-memory
SQLite DB seeded with an admin and a regular user, plus the role guards on the
public panchangam router. Mirrors the client fixture in ``tests/test_etag.py``
(deliberately not entered as a context manager, so the real lifespan never runs).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — registers every table on SQLModel.metadata
from core.security import hash_password
from db.database import get_session
from db.user_repository import UserRepository
from main import app
from utils.roles import Role

ADMIN_USER, ADMIN_PW = "admin", "admin-password"
NORMAL_USER, NORMAL_PW = "devotee", "user-password"


@pytest.fixture
def api_engine():
    """In-memory engine with an admin and a regular user seeded."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def _login(client, username, password):
    return client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_returns_access_and_refresh_tokens(client):
    r = _login(client, ADMIN_USER, ADMIN_PW)
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_login_wrong_password_rejected(client):
    r = _login(client, ADMIN_USER, "wrong")
    assert r.status_code == 401


def test_login_unknown_user_rejected(client):
    r = _login(client, "nobody", "whatever")
    assert r.status_code == 401


# ── /auth/me and role hierarchy ───────────────────────────────────────────────

def test_me_requires_authentication(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_reflects_token_identity(client):
    token = _login(client, NORMAL_USER, NORMAL_PW).json()["access_token"]
    r = client.get("/api/v1/auth/me", headers=_bearer(token))
    assert r.status_code == 200
    assert r.json() == {
        "username": NORMAL_USER,
        "role": Role.USER.value,
        "is_active": True,
    }


def test_invalid_token_rejected(client):
    r = client.get("/api/v1/auth/me", headers=_bearer("not-a-real-token"))
    assert r.status_code == 401


# ── Admin-only user management ────────────────────────────────────────────────

def test_create_user_requires_admin_role(client):
    user_token = _login(client, NORMAL_USER, NORMAL_PW).json()["access_token"]
    r = client.post(
        "/api/v1/auth/users",
        headers=_bearer(user_token),
        json={"username": "new", "password": "password123", "role": "user"},
    )
    assert r.status_code == 403


def test_create_user_requires_authentication(client):
    r = client.post(
        "/api/v1/auth/users",
        json={"username": "new", "password": "password123", "role": "user"},
    )
    assert r.status_code == 401


def test_admin_can_create_user_who_can_then_log_in(client):
    admin_token = _login(client, ADMIN_USER, ADMIN_PW).json()["access_token"]
    r = client.post(
        "/api/v1/auth/users",
        headers=_bearer(admin_token),
        json={"username": "acolyte", "password": "password123", "role": "user"},
    )
    assert r.status_code == 201
    assert r.json()["username"] == "acolyte"
    # The new user can authenticate.
    assert _login(client, "acolyte", "password123").status_code == 200


def test_create_duplicate_user_conflicts(client):
    admin_token = _login(client, ADMIN_USER, ADMIN_PW).json()["access_token"]
    r = client.post(
        "/api/v1/auth/users",
        headers=_bearer(admin_token),
        json={"username": NORMAL_USER, "password": "password123", "role": "user"},
    )
    assert r.status_code == 409


# ── Refresh flow & token-type enforcement ─────────────────────────────────────

def test_refresh_issues_working_access_token(client):
    refresh_token = _login(client, NORMAL_USER, NORMAL_PW).json()["refresh_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r.status_code == 200
    new_access = r.json()["access_token"]
    # The freshly minted access token authorizes a protected endpoint.
    assert client.get("/api/v1/auth/me", headers=_bearer(new_access)).status_code == 200


def test_access_token_rejected_on_refresh_endpoint(client):
    access_token = _login(client, NORMAL_USER, NORMAL_PW).json()["access_token"]
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert r.status_code == 401


def test_refresh_token_rejected_as_access_token(client):
    refresh_token = _login(client, NORMAL_USER, NORMAL_PW).json()["refresh_token"]
    r = client.get("/api/v1/auth/me", headers=_bearer(refresh_token))
    assert r.status_code == 401


# ── Public panchangam router guard ────────────────────────────────────────────

def test_panchangam_read_allows_anonymous(client):
    # No credentials: the anonymous principal must pass the guard. We assert on
    # the authorization outcome (not a 401/403) rather than the payload, so the
    # test isolates auth behaviour from live astronomical computation.
    r = client.get("/api/v1/panchangam/day", params={"day": "2026-01-01"})
    assert r.status_code not in (401, 403)


def test_panchangam_read_rejects_malformed_token(client):
    # A supplied-but-invalid token is rejected even on a public endpoint.
    r = client.get(
        "/api/v1/panchangam/day",
        params={"day": "2026-01-01"},
        headers=_bearer("garbage.token.value"),
    )
    assert r.status_code == 401
