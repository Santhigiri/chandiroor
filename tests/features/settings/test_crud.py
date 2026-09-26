"""
End-to-end tests for the settings CRUD endpoints under ``/api/v1/settings``.

Uses an in-memory SQLite engine seeded via ``seed_lookup_tables`` (which now
also seeds default ``app_setting`` rows) plus an admin and a regular user.
Writes and reads of most keys require the ``admin`` role (mirroring
``tests/test_santhigiri_event_crud.py``'s fixture pattern), except
``calendar_range``/``languages`` (``features.settings.router.PUBLIC_SETTING_KEYS``),
whose reads are public — see the "Public setting reads" section below.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.db.database  # noqa: F401 — registers the FK pragma listener
import app.db.models  # noqa: F401 — register every table on SQLModel.metadata
from app.db.database import get_session
from app.db.seed import seed_lookup_tables
from app.main import app
from app.utils.roles import Role
from tests.conftest import bearer_header

SETTINGS_URL = "/api/v1/settings"
# Passwords are unused now (Chandiroor trusts a TVM-issued token, never a
# username/password) but kept as placeholders so _bearer()'s call sites below
# don't need touching.
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


def _bearer(client, username, password=None) -> dict:
    # Chandiroor no longer authenticates by username/password — it trusts a
    # TVM-issued access token. Tokens are minted directly here (no DB lookup,
    # no login round trip) keyed by the same ADMIN_USER/NORMAL_USER labels the
    # tests already used.
    role = Role.ADMIN if username == ADMIN_USER else Role.USER
    return bearer_header(role)


@pytest.fixture
def admin_auth(client) -> dict:
    return _bearer(client, ADMIN_USER, ADMIN_PW)


# ── Authorization ────────────────────────────────────────────────────────────

def test_list_is_accessible_anonymously_but_filtered_to_public_keys(client):
    r = client.get(SETTINGS_URL)
    assert r.status_code == 200
    keys = {row["key"] for row in r.json()}
    assert keys == {"calendar_range", "languages"}


def test_list_is_filtered_to_public_keys_for_non_admin(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.get(SETTINGS_URL, headers=user_auth)
    assert r.status_code == 200
    keys = {row["key"] for row in r.json()}
    assert keys == {"calendar_range", "languages"}


def test_list_returns_every_key_for_admin(client, admin_auth):
    r = client.get(SETTINGS_URL, headers=admin_auth)
    assert r.status_code == 200
    keys = {row["key"] for row in r.json()}
    assert "seed_year_range" in keys
    assert "calendar_range" in keys
    assert "languages" in keys


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


# ── Public setting reads (calendar_range, languages) ────────────────────────

def test_get_calendar_range_is_public(client):
    r = client.get(f"{SETTINGS_URL}/calendar_range")
    assert r.status_code == 200
    assert r.json()["value"] == {"start_year": 2021, "end_year": 2035}


def test_get_languages_is_public(client):
    r = client.get(f"{SETTINGS_URL}/languages")
    assert r.status_code == 200
    assert r.json()["value"] == {"codes": ["en", "ml"]}


def test_get_calendar_range_rejects_invalid_bearer_token(client):
    r = client.get(
        f"{SETTINGS_URL}/calendar_range",
        headers={"Authorization": "Bearer not-a-real-token"},
    )
    assert r.status_code == 401


def test_update_calendar_range_still_requires_admin(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.put(
        f"{SETTINGS_URL}/calendar_range",
        headers=user_auth,
        json={"value": {"start_year": 2000, "end_year": 2040}},
    )
    assert r.status_code == 403


def test_admin_can_update_calendar_range_and_public_can_read_it_back(client, admin_auth):
    updated = client.put(
        f"{SETTINGS_URL}/calendar_range",
        headers=admin_auth,
        json={"value": {"start_year": 2000, "end_year": 2040}},
    )
    assert updated.status_code == 200

    fetched = client.get(f"{SETTINGS_URL}/calendar_range")
    assert fetched.status_code == 200
    assert fetched.json()["value"] == {"start_year": 2000, "end_year": 2040}


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


# ── ETag ─────────────────────────────────────────────────────────────────────

def test_list_200_carries_etag(client, admin_auth):
    r = client.get(SETTINGS_URL, headers=admin_auth)
    assert r.status_code == 200
    assert r.headers.get("etag", "").startswith('"')


def test_list_304_when_if_none_match_matches(client, admin_auth):
    first = client.get(SETTINGS_URL, headers=admin_auth)
    etag = first.headers["etag"]

    second = client.get(
        SETTINGS_URL, headers={**admin_auth, "If-None-Match": etag}
    )
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["etag"] == etag


def test_list_200_when_if_none_match_is_stale(client, admin_auth):
    r = client.get(
        SETTINGS_URL,
        headers={**admin_auth, "If-None-Match": '"not-the-current-etag"'},
    )
    assert r.status_code == 200
    assert r.json()


def test_get_one_200_carries_etag(client, admin_auth):
    r = client.get(f"{SETTINGS_URL}/seed_year_range", headers=admin_auth)
    assert r.status_code == 200
    assert r.headers.get("etag", "").startswith('"')


def test_get_one_304_when_if_none_match_matches(client, admin_auth):
    first = client.get(f"{SETTINGS_URL}/seed_year_range", headers=admin_auth)
    etag = first.headers["etag"]

    second = client.get(
        f"{SETTINGS_URL}/seed_year_range",
        headers={**admin_auth, "If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.content == b""


def test_get_one_etag_changes_after_update(client, admin_auth):
    before = client.get(f"{SETTINGS_URL}/seed_year_range", headers=admin_auth)
    etag = before.headers["etag"]

    client.put(
        f"{SETTINGS_URL}/seed_year_range",
        headers=admin_auth,
        json={"value": {"start_year": 2021, "end_year": 2035}},
    )

    after = client.get(
        f"{SETTINGS_URL}/seed_year_range",
        headers={**admin_auth, "If-None-Match": etag},
    )
    assert after.status_code == 200
    assert after.json()["value"] == {"start_year": 2021, "end_year": 2035}
    assert after.headers["etag"] != etag


def test_list_etag_changes_after_update(client, admin_auth):
    before = client.get(SETTINGS_URL, headers=admin_auth)
    etag = before.headers["etag"]

    client.put(
        f"{SETTINGS_URL}/seed_year_range",
        headers=admin_auth,
        json={"value": {"start_year": 2021, "end_year": 2035}},
    )

    after = client.get(SETTINGS_URL, headers={**admin_auth, "If-None-Match": etag})
    assert after.status_code == 200
    assert after.headers["etag"] != etag
