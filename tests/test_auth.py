"""
Tests for JWT authentication and role-based authorization.

Exercises the auth endpoints end-to-end via ``TestClient`` against an in-memory
SQLite DB seeded with an admin and a regular user, plus the role guards on the
public panchangam router. Mirrors the client fixture in ``tests/test_etag.py``
(deliberately not entered as a context manager, so the real lifespan never runs).

Tokens are delivered as HTTP-only cookies rather than in the response body, so
these tests lean on the ``TestClient`` cookie jar: after ``/auth/login`` the
client automatically replays the ``access_token`` / ``refresh_token`` cookies on
subsequent requests. ``cookie_secure`` is forced off in the ``client`` fixture so
the cookies are resent over the plain-HTTP ``testserver`` transport.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — registers every table on SQLModel.metadata
from core.config import settings
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
def client(api_engine, monkeypatch):
    # The test transport is plain HTTP (http://testserver), so Secure cookies
    # would never be replayed by the jar. Turn Secure off for the tests.
    monkeypatch.setattr(settings, "cookie_secure", False)

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


def _set_cookie_headers(response):
    """All raw Set-Cookie header values on a response."""
    return [v for k, v in response.headers.multi_items() if k.lower() == "set-cookie"]


# ── Login ─────────────────────────────────────────────────────────────────────

def test_login_sets_httponly_cookies_and_returns_user(client):
    r = _login(client, ADMIN_USER, ADMIN_PW)
    assert r.status_code == 200
    # The body is the (non-sensitive) current user — never the tokens.
    assert r.json() == {
        "username": ADMIN_USER,
        "role": Role.ADMIN.value,
        "is_active": True,
    }
    assert "access_token" not in r.json()
    # Tokens are delivered as cookies instead.
    assert r.cookies.get("access_token")
    assert r.cookies.get("refresh_token")
    # And both cookies are flagged HttpOnly.
    set_cookies = _set_cookie_headers(r)
    assert any("access_token=" in c and "httponly" in c.lower() for c in set_cookies)
    assert any("refresh_token=" in c and "httponly" in c.lower() for c in set_cookies)


def test_login_wrong_password_rejected(client):
    r = _login(client, ADMIN_USER, "wrong")
    assert r.status_code == 401


def test_login_unknown_user_rejected(client):
    r = _login(client, "nobody", "whatever")
    assert r.status_code == 401


# ── /auth/me and role hierarchy ───────────────────────────────────────────────

def test_me_requires_authentication(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_reflects_cookie_identity(client):
    # Login seeds the cookie jar; /me is then authenticated by the cookie alone.
    _login(client, NORMAL_USER, NORMAL_PW)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json() == {
        "username": NORMAL_USER,
        "role": Role.USER.value,
        "is_active": True,
    }


def test_invalid_token_rejected(client):
    # The Authorization header fallback still validates the token.
    r = client.get("/api/v1/auth/me", headers=_bearer("not-a-real-token"))
    assert r.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────

def test_logout_clears_cookies(client):
    _login(client, ADMIN_USER, ADMIN_PW)
    assert client.get("/api/v1/auth/me").status_code == 200
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    # Cookies are expired, so the session no longer authenticates.
    assert client.get("/api/v1/auth/me").status_code == 401


# ── Admin-only user management ────────────────────────────────────────────────

def test_create_user_requires_admin_role(client):
    _login(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        "/api/v1/auth/users",
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
    _login(client, ADMIN_USER, ADMIN_PW)
    r = client.post(
        "/api/v1/auth/users",
        json={"username": "acolyte", "password": "password123", "role": "user"},
    )
    assert r.status_code == 201
    assert r.json()["username"] == "acolyte"
    # The new user can authenticate (this overwrites the admin cookies).
    assert _login(client, "acolyte", "password123").status_code == 200


def test_create_duplicate_user_conflicts(client):
    _login(client, ADMIN_USER, ADMIN_PW)
    r = client.post(
        "/api/v1/auth/users",
        json={"username": NORMAL_USER, "password": "password123", "role": "user"},
    )
    assert r.status_code == 409


# ── Refresh flow & token-type enforcement ─────────────────────────────────────

def test_refresh_rotates_cookies_and_keeps_session(client):
    _login(client, NORMAL_USER, NORMAL_PW)
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 204
    # Refresh re-set the cookies; the session still authorizes a protected call.
    assert client.get("/api/v1/auth/me").status_code == 200


def test_refresh_without_cookie_rejected(client):
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


def test_access_token_rejected_on_refresh_endpoint(client):
    r = _login(client, NORMAL_USER, NORMAL_PW)
    access_token = r.cookies["access_token"]
    # Present an access token in the refresh cookie: wrong token type → 401.
    client.cookies.clear()
    client.cookies.set("refresh_token", access_token, domain="testserver", path="/")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


def test_refresh_token_rejected_as_access_token(client):
    r = _login(client, NORMAL_USER, NORMAL_PW)
    refresh_token = r.cookies["refresh_token"]
    # A refresh token supplied as an access token (header path) is rejected.
    client.cookies.clear()
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
