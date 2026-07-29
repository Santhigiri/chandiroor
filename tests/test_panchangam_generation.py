"""
End-to-end tests for the Panchangam generation endpoint,
``POST /api/v1/panchangam/generate``.

Uses an in-memory SQLite engine seeded from the real 2022 pickle (so every 2022
date already has a ``panchangam`` row) plus an admin and a regular user.
Generation overwrites the ashram's authoritative data, so it requires the
``admin`` role — mirroring ``tests/test_kollavarsham_crud.py``. Because the
seeded rows come from the same ``get_panchangam_data`` the endpoint calls,
regenerating a date reproduces its authoritative values, which we exploit to
assert that a corrupted row is repaired and that the ``/year`` ETag stays in
lockstep with what the read endpoint serves.

The response is streamed as newline-delimited JSON (NDJSON): one ``"progress"``
line per day, then a final ``"complete"`` line. ``TestClient`` (httpx-based)
drives the ASGI app to completion and buffers the whole body in ``.text``
regardless, so tests read it back by splitting on newlines and parsing each
line — see ``_lines`` below.
"""
from __future__ import annotations

import json
import pickle
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — register every table on SQLModel.metadata
from core.security import hash_password
from db.database import get_session
from db.etag_repository import EtagRepository
from db.models.panchangam import Panchangam as PanchangamRow
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from db.user_repository import UserRepository
from main import app
from services.etag_service import refresh_etags, year_key
from utils.location import Location
from utils.roles import Role

PICKLE_2022 = "data/panchangam_2022.pkl"
YEAR = 2022
BASE = "/api/v1/panchangam/generate"
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
    # Login delivers the access token as an HTTP-only cookie; read it from the
    # login response and replay it via the Authorization header (still accepted
    # as a fallback for non-browser clients).
    token = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    ).cookies["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth(client) -> dict:
    return _bearer(client, ADMIN_USER, ADMIN_PW)


def _stored_year_etag(api_engine) -> str:
    with Session(api_engine) as s:
        return EtagRepository(s).get(year_key(YEAR, Location.TVM.code))


def _corrupt_nazhika(api_engine, day: str, value: float) -> None:
    """Directly set a stored row's nazhika to a sentinel, simulating stale data."""
    with Session(api_engine) as s:
        row = s.get(PanchangamRow, (date.fromisoformat(day), Location.TVM.id))
        row.nazhika_from_sunrise = value
        s.add(row)
        s.commit()


def _stored_nazhika(api_engine, day: str) -> float:
    with Session(api_engine) as s:
        return PanchangamRepository(s).get_by_date(
            date.fromisoformat(day), Location.TVM
        ).nazhika_from_sunrise


def _lines(response) -> list[dict]:
    """Parse an NDJSON response body into a list of line objects."""
    return [json.loads(line) for line in response.text.strip().split("\n") if line]


# ── Authorization ────────────────────────────────────────────────────────────────

def test_generate_requires_authentication(client):
    r = client.post(
        BASE, json={"start_date": "2022-03-01", "end_date": "2022-03-02"}
    )
    assert r.status_code == 401


def test_generate_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        BASE,
        headers=user_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-02"},
    )
    assert r.status_code == 403


# ── Generate ─────────────────────────────────────────────────────────────────────

def test_generate_over_range_reports_summary(client, admin_auth):
    r = client.post(
        BASE,
        headers=admin_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-03"},
    )
    assert r.status_code == 200
    lines = _lines(r)
    data = lines[-1]
    assert data["type"] == "complete"
    assert data["count"] == 3
    assert data["years"] == [2022]
    assert data["start_date"] == "2022-03-01"
    assert data["end_date"] == "2022-03-03"


def test_generate_streams_progress_per_day(client, admin_auth):
    r = client.post(
        BASE,
        headers=admin_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-03"},
    )
    lines = _lines(r)
    progress = [line for line in lines if line["type"] == "progress"]
    assert [p["completed"] for p in progress] == [1, 2, 3]
    assert [p["total"] for p in progress] == [3, 3, 3]
    assert [p["percent"] for p in progress] == [pytest.approx(33.3), pytest.approx(66.7), 100.0]
    assert [p["current_date"] for p in progress] == [
        "2022-03-01", "2022-03-02", "2022-03-03",
    ]
    assert lines[-1]["type"] == "complete"


def test_generate_overwrites_existing_row(client, admin_auth, api_engine):
    day = "2022-03-01"
    original = _stored_nazhika(api_engine, day)
    _corrupt_nazhika(api_engine, day, -999.0)
    assert _stored_nazhika(api_engine, day) == -999.0

    r = client.post(
        BASE, headers=admin_auth, json={"start_date": day, "end_date": day}
    )
    assert r.status_code == 200
    assert _lines(r)[-1]["type"] == "complete"
    # The recomputed value replaced the corrupted one.
    assert _stored_nazhika(api_engine, day) != -999.0
    assert _stored_nazhika(api_engine, day) == pytest.approx(original)


def test_generate_keeps_year_etag_in_lockstep(client, admin_auth, api_engine):
    # A corrupted row makes the served /year payload (and thus its live ETag)
    # diverge from the stored one; regenerating must both repair the row and
    # refresh the stored ETag so the two match again.
    _corrupt_nazhika(api_engine, "2022-03-01", -999.0)
    client.post(
        BASE,
        headers=admin_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-03"},
    )
    served = client.get(
        "/api/v1/panchangam/year", params={"year": YEAR}
    ).headers["etag"]
    assert served == _stored_year_etag(api_engine)


# ── Range validation ─────────────────────────────────────────────────────────────

def test_generate_rejects_reversed_range(client, admin_auth):
    r = client.post(
        BASE,
        headers=admin_auth,
        json={"start_date": "2022-03-05", "end_date": "2022-03-01"},
    )
    assert r.status_code == 422


def test_generate_rejects_oversized_range(client, admin_auth):
    r = client.post(
        BASE,
        headers=admin_auth,
        json={"start_date": "2022-01-01", "end_date": "2023-06-01"},
    )
    assert r.status_code == 422
