"""
End-to-end tests for the admin Panchangam write endpoints:

* ``POST  /api/v1/panchangam/day/generate`` — compute + persist a day (overwrite).
* ``PATCH /api/v1/panchangam/day``          — override an existing day's core values.

Uses the same self-contained fixture style as ``test_santhigiri_event_crud.py``:
an in-memory SQLite engine seeded with the lookup tables plus an admin and a
regular user, with ``get_session`` overridden onto it and the app driven by
``TestClient``. The generate path's astronomy call is monkeypatched to the
``make_panchangam_data`` factory so tests stay fast and deterministic (no
ephemeris load, no transition search).
"""
from __future__ import annotations

import datetime as _dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — register every table on SQLModel.metadata
import services.panchangam_admin_service as admin_service
import services.panchangam_service as read_service
from core.security import hash_password
from db.database import get_session
from db.etag_repository import EtagRepository
from db.models.santhigiri_event_date import SanthigiriEventDate
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from db.user_repository import UserRepository
from main import app
from services.etag_service import refresh_etags, year_key
from utils.location import Location
from utils.nakshatra import Nakshatra
from utils.roles import Role
from utils.thithi import Thithi

GENERATE_URL = "/api/v1/panchangam/day/generate"
EDIT_URL = "/api/v1/panchangam/day"
DAY_URL = "/api/v1/panchangam/day"
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


def _stored_year_etag(api_engine, year: int):
    with Session(api_engine) as s:
        return EtagRepository(s).get(year_key(year, Location.TVM.code))


def _seed_day(api_engine, data, *, event_ids=(), refresh_year=False) -> None:
    """Persist a day (and optional event occurrences) directly, as the DB would hold it."""
    with Session(api_engine) as s:
        PanchangamRepository(s).upsert(data, Location.TVM)
        for eid in event_ids:
            s.add(SanthigiriEventDate(panchangam_date=data.date, event_id=eid))
        s.commit()
    if refresh_year:
        with Session(api_engine) as s:
            refresh_etags(s, [data.date.year], [Location.TVM])


@pytest.fixture(autouse=True)
def mock_compute(monkeypatch, make_panchangam_data):
    """Replace the astronomy call everywhere it is used so tests stay fast and
    deterministic.

    Both the admin write path (``generate``) and the read path's live fallback
    call ``get_panchangam_data``. The latter matters because every mutation
    refreshes the whole-year ETag payload, which live-computes each day absent
    from the DB — with real Skyfield that is hundreds of transition searches per
    test. Patching both keeps the suite fast without touching production code.
    """

    def _fake(day, *args, **kwargs):
        return make_panchangam_data(day)

    monkeypatch.setattr(admin_service, "get_panchangam_data", _fake)
    monkeypatch.setattr(read_service, "get_panchangam_data", _fake)
    return make_panchangam_data


# ── Authorization ────────────────────────────────────────────────────────────────

def test_generate_requires_authentication(client):
    assert client.post(f"{GENERATE_URL}?day=2035-01-01").status_code == 401


def test_generate_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(f"{GENERATE_URL}?day=2035-01-01", headers=user_auth)
    assert r.status_code == 403


def test_edit_requires_authentication(client):
    r = client.patch(f"{EDIT_URL}?day=2035-01-01", json={"nazhika_from_sunrise": 1.0})
    assert r.status_code == 401


def test_edit_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.patch(
        f"{EDIT_URL}?day=2035-01-01",
        headers=user_auth,
        json={"nazhika_from_sunrise": 1.0},
    )
    assert r.status_code == 403


# ── Generate ─────────────────────────────────────────────────────────────────────

def test_generate_persists_day(client, admin_auth, api_engine):
    # Absent from the DB before generating.
    with Session(api_engine) as s:
        assert PanchangamRepository(s).get_by_date(_dt.date(2035, 1, 1), Location.TVM) is None

    r = client.post(f"{GENERATE_URL}?day=2035-01-01", headers=admin_auth)
    assert r.status_code == 201
    assert r.json()["date"] == "2035-01-01"

    # Now persisted: read straight from the DB.
    with Session(api_engine) as s:
        assert PanchangamRepository(s).get_by_date(_dt.date(2035, 1, 1), Location.TVM) is not None
    assert client.get(f"{DAY_URL}?day=2035-01-01").status_code == 200


def test_generate_sets_year_etag(client, admin_auth, api_engine):
    assert _stored_year_etag(api_engine, 2035) is None  # not pre-seeded

    client.post(f"{GENERATE_URL}?day=2035-01-01", headers=admin_auth)

    assert _stored_year_etag(api_engine, 2035) is not None


def test_generate_overwrites_existing(
    client, admin_auth, api_engine, make_panchangam_data
):
    # Seed a day with a distinctive nazhika, then regenerate — the compute mock
    # returns the factory default (12.5), overwriting the seeded value.
    day = _dt.date(2035, 3, 3)
    _seed_day(api_engine, make_panchangam_data(day, nazhika_from_sunrise=99.0))

    r = client.post(f"{GENERATE_URL}?day={day.isoformat()}", headers=admin_auth)
    assert r.status_code == 201
    assert r.json()["nazhika_from_sunrise"] == 12.5

    persisted = client.get(f"{DAY_URL}?day={day.isoformat()}").json()
    assert persisted["nazhika_from_sunrise"] == 12.5


# ── Edit ─────────────────────────────────────────────────────────────────────────

def test_edit_missing_day_is_404(client, admin_auth):
    r = client.patch(
        f"{EDIT_URL}?day=2035-06-06",
        headers=admin_auth,
        json={"nazhika_from_sunrise": 5.0},
    )
    assert r.status_code == 404


def test_edit_overrides_only_supplied_fields(
    client, admin_auth, api_engine, make_panchangam_data
):
    day = _dt.date(2025, 4, 10)
    _seed_day(
        api_engine,
        make_panchangam_data(
            day,
            thithi=Thithi.POORNIMA,
            nakshatra=Nakshatra.CHOTHI,
            nazhika_from_sunrise=12.5,
        ),
    )

    r = client.patch(
        f"{EDIT_URL}?day={day.isoformat()}",
        headers=admin_auth,
        json={"thithi_id": Thithi.AMAVASYA.id, "nazhika_from_sunrise": 7.25},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["thithi"]["id"] == Thithi.AMAVASYA.id          # overridden
    assert body["nazhika_from_sunrise"] == 7.25                 # overridden
    assert body["nakshatra"]["id"] == Nakshatra.CHOTHI.id       # untouched

    # Persisted: a fresh read reflects the change (compact schema uses the enum name).
    persisted = client.get(f"{DAY_URL}?day={day.isoformat()}").json()
    assert persisted["thithi"] == Thithi.AMAVASYA.name


def test_edit_preserves_santhigiri_events(
    client, admin_auth, api_engine, make_panchangam_data
):
    day = _dt.date(2025, 5, 12)
    _seed_day(
        api_engine,
        make_panchangam_data(day),
        event_ids=["POURNAMI"],  # seeded event definition
    )

    r = client.patch(
        f"{EDIT_URL}?day={day.isoformat()}",
        headers=admin_auth,
        json={"nazhika_from_sunrise": 3.0},
    )
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()["santhigiri_significant_dates"]]
    assert "POURNAMI" in ids


def test_edit_bumps_year_etag(client, admin_auth, api_engine, make_panchangam_data):
    day = _dt.date(2025, 7, 1)
    _seed_day(
        api_engine,
        make_panchangam_data(day, nazhika_from_sunrise=12.5),
        refresh_year=True,
    )
    before = _stored_year_etag(api_engine, 2025)
    assert before is not None

    client.patch(
        f"{EDIT_URL}?day={day.isoformat()}",
        headers=admin_auth,
        json={"nazhika_from_sunrise": 42.0},
    )
    assert _stored_year_etag(api_engine, 2025) != before
