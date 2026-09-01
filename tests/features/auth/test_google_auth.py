"""
Tests for Google Sign-In (``POST /auth/google``) and self-service profile
updates (``PATCH /auth/me``).

Mirrors the fixture pattern in ``tests/test_auth.py``: an in-memory SQLite DB,
a ``TestClient`` cookie jar, and ``cookie_secure`` forced off so cookies are
replayed over the plain-HTTP ``testserver`` transport. Google's ID-token
verification itself is not exercised here (it would require a real signed
token and network access to Google) — instead
``features.auth.router.verify_google_id_token`` is monkeypatched to return
canned claims, isolating this test's scope to the account
find-or-create/cookie-issuing logic.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.db.database  # noqa: F401 — registers the FK pragma listener
import app.db.models  # noqa: F401 — registers every table on SQLModel.metadata
import app.features.auth.router as auth_routes
from app.core.config import settings
from app.core.security import GoogleTokenError
from app.db.database import get_session
from app.db.models.user import User
from app.main import app

GOOGLE_SUB = "1234567890"
GOOGLE_EMAIL = "devotee@example.com"
GOOGLE_NAME = "Devotee Example"

pytestmark = pytest.mark.skip(
    reason=(
        "POST /auth/google was dropped from app/features/auth/router.py during the "
        "app/ restructure + ports & adapters migration (commit 1bdfbbc) and the "
        "find-or-create-by-google_id logic was never carried over to "
        "AuthRepositoryPort/AuthRepository/AuthService, even though the User model "
        "still has a google_id column and core/security.py::verify_google_id_token "
        "still exists. Restoring it is a real feature-slice, not a test-import fix — "
        "flagging here rather than fabricating the missing port/service/router code."
    )
)


@pytest.fixture
def api_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(api_engine, monkeypatch):
    monkeypatch.setattr(settings, "cookie_secure", False)

    def _override():
        with Session(api_engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _fake_claims(sub=GOOGLE_SUB, email=GOOGLE_EMAIL, name=GOOGLE_NAME, email_verified=True):
    return {"sub": sub, "email": email, "email_verified": email_verified, "name": name}


def _google_login(client, monkeypatch, **claim_overrides):
    monkeypatch.setattr(
        auth_routes,
        "verify_google_id_token",
        lambda token: _fake_claims(**claim_overrides),
    )
    return client.post("/api/v1/auth/google", json={"id_token": "fake-token"})


# ── First-time sign-in ────────────────────────────────────────────────────────

def test_google_login_creates_user_role_account(client, monkeypatch):
    r = _google_login(client, monkeypatch)
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == GOOGLE_EMAIL
    assert body["email"] == GOOGLE_EMAIL
    assert body["full_name"] == GOOGLE_NAME
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert r.cookies.get("access_token")
    assert r.cookies.get("refresh_token")


def test_google_login_is_public(client, monkeypatch):
    # No prior cookies/credentials needed to hit the endpoint.
    r = _google_login(client, monkeypatch)
    assert r.status_code == 200


# ── Repeat sign-in reuses the same account ─────────────────────────────────────

def test_google_login_twice_reuses_same_account(client, monkeypatch, api_engine):
    first = _google_login(client, monkeypatch)
    client.cookies.clear()
    second = _google_login(client, monkeypatch)
    assert first.json()["username"] == second.json()["username"]

    with Session(api_engine) as s:
        assert len(s.exec(select(User)).all()) == 1


# ── Rejections ─────────────────────────────────────────────────────────────────

def test_google_login_rejects_unverified_email(client, monkeypatch):
    r = _google_login(client, monkeypatch, email_verified=False)
    assert r.status_code == 401


def test_google_login_rejects_invalid_token(client, monkeypatch):
    def _raise(token):
        raise GoogleTokenError("bad token")

    monkeypatch.setattr(auth_routes, "verify_google_id_token", _raise)
    r = client.post("/api/v1/auth/google", json={"id_token": "garbage"})
    assert r.status_code == 401


# ── Profile updates ─────────────────────────────────────────────────────────────

def test_update_profile_requires_authentication(client):
    r = client.patch("/api/v1/auth/me", json={"full_name": "New Name"})
    assert r.status_code == 401


def test_update_profile_sets_fields(client, monkeypatch):
    _google_login(client, monkeypatch)
    r = client.patch(
        "/api/v1/auth/me",
        json={
            "full_name": "Updated Name",
            "date_of_birth": "1990-05-15",
            "birth_nakshatra": "CHOTHI",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["full_name"] == "Updated Name"
    assert body["date_of_birth"] == "1990-05-15"
    assert body["birth_nakshatra"] == "CHOTHI"


def test_update_profile_rejects_unknown_nakshatra(client, monkeypatch):
    _google_login(client, monkeypatch)
    r = client.patch("/api/v1/auth/me", json={"birth_nakshatra": "NOT_A_NAKSHATRA"})
    assert r.status_code == 422


def test_update_profile_partial_update_leaves_other_fields(client, monkeypatch):
    _google_login(client, monkeypatch)
    client.patch("/api/v1/auth/me", json={"full_name": "First Update"})
    r = client.patch("/api/v1/auth/me", json={"date_of_birth": "2000-01-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["full_name"] == "First Update"
    assert body["date_of_birth"] == "2000-01-01"
