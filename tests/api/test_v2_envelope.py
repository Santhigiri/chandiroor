"""
Envelope-shape, ETag-equivalence, and error-mapping tests for the v2
panchangam/settings/santhigiri-events endpoints added in this pass
(app/features/panchangam/router_v2.py, app/features/santhigiri_events/router_v2.py,
app/features/settings/router_v2.py) — see app/api/envelope.py and
app/schemas/api_response.py for the shared {success, message, data} envelope.

Reference-endpoint envelope tests already live in
tests/features/reference/test_router_v2.py (retrofitted in this same pass).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import datetime

import app.db.database  # noqa: F401 — registers the FK pragma listener
import app.db.models  # noqa: F401 — register every table on SQLModel.metadata
from app.db.database import get_session
from app.db.seed import seed_lookup_tables
from app.features.etag.repository import EtagRepository
from app.features.etag.service import refresh_etags
from app.db.unit_of_work import SqlUnitOfWork
from app.db.reference_repository import ReferenceRepository
from app.features.panchangam.repository import PanchangamRepository
from app.features.panchangam.service import PanchangamService
from app.main import app
from app.utils.location import Location
from app.utils.roles import Role
from tests.conftest import bearer_header

V1 = "/api/v1"
V2 = "/api/v2"


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


def _assert_envelope(body, message: str):
    assert body["success"] is True
    assert body["message"] == message
    return body["data"]


ADMIN_AUTH = bearer_header(Role.ADMIN)
USER_AUTH = bearer_header(Role.USER)


# ── panchangam v2 ────────────────────────────────────────────────────────────

def test_sunrise_sunset_v2_is_enveloped(client):
    r = client.get(
        f"{V2}/panchangam/sunrise-sunset",
        params={"latitude": 8.645, "longitude": 76.938, "day": "2022-03-20"},
    )
    assert r.status_code == 200
    data = _assert_envelope(r.json(), "SUNRISE_SUNSET_SUCCESS")
    assert data["latitude"] == 8.645


def test_sunrise_sunset_v1_and_v2_data_matches(client):
    params = {"latitude": 8.645, "longitude": 76.938, "day": "2022-03-20"}
    v1 = client.get(f"{V1}/panchangam/sunrise-sunset", params=params).json()
    v2 = _assert_envelope(
        client.get(f"{V2}/panchangam/sunrise-sunset", params=params).json(),
        "SUNRISE_SUNSET_SUCCESS",
    )
    assert v2 == v1


def test_sunrise_sunset_v2_invalid_coordinates_is_bad_request(client):
    r = client.get(
        f"{V2}/panchangam/sunrise-sunset",
        params={"latitude": 999, "longitude": 76.938, "day": "2022-03-20"},
    )
    assert r.status_code == 422  # latitude out of [-90, 90] fails Pydantic field validation
    body = r.json()
    assert body["success"] is False
    assert body["message"] == "VALIDATION_FAILED"


YEAR = 2022


@pytest.fixture
def year_client(api_engine, make_panchangam_data):
    """Same shape as tests/features/etag/test_service.py's api_engine fixture:
    a full year of synthetic-but-schema-valid data, precomputed ETags — so
    /year doesn't fall back to a full year of live Skyfield computation."""
    with Session(api_engine) as s:
        start = datetime.date(YEAR, 1, 1)
        days = 366 if YEAR % 4 == 0 else 365
        year_data = [make_panchangam_data(start + datetime.timedelta(days=i)) for i in range(days)]
        PanchangamRepository(s).upsert_many(year_data, Location.TVM)
        refresh_etags(
            ReferenceRepository(s),
            PanchangamService(PanchangamRepository(s)),
            EtagRepository(s),
            SqlUnitOfWork(s),
            [YEAR],
        )

    def _override():
        with Session(api_engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_year_v1_and_v2_share_the_same_etag(year_client):
    v1 = year_client.get(f"{V1}/panchangam/year", params={"year": YEAR})
    v2 = year_client.get(f"{V2}/panchangam/year", params={"year": YEAR})
    assert v1.status_code == 200 and v2.status_code == 200
    assert v1.headers["etag"] == v2.headers["etag"]
    body = v2.json()
    assert body["success"] is True
    assert body["message"] == "PANCHANGAM_YEAR_SUCCESS"


def test_year_v2_304_on_matching_etag_has_empty_body(year_client):
    first = year_client.get(f"{V2}/panchangam/year", params={"year": YEAR})
    etag = first.headers["etag"]
    second = year_client.get(
        f"{V2}/panchangam/year", params={"year": YEAR}, headers={"If-None-Match": etag}
    )
    assert second.status_code == 304
    assert second.content == b""


# ── santhigiri events v2 ─────────────────────────────────────────────────────

EVENTS_V2 = f"{V2}/panchangam/events"

_NEW_EVENT = {
    "id": "TEST_EVENT_V2",
    "name": "Test Event",
    "description": "d",
}


def test_create_get_update_delete_event_v2_round_trip(client):
    created = client.post(EVENTS_V2, json=_NEW_EVENT, headers=ADMIN_AUTH)
    assert created.status_code == 201
    data = _assert_envelope(created.json(), "EVENT_CREATED")
    assert data["id"] == "TEST_EVENT_V2"

    fetched = client.get(f"{EVENTS_V2}/TEST_EVENT_V2")
    assert fetched.status_code == 200
    assert _assert_envelope(fetched.json(), "EVENT_FETCHED")["name"] == "Test Event"

    updated = client.put(
        f"{EVENTS_V2}/TEST_EVENT_V2", json={"name": "Renamed"}, headers=ADMIN_AUTH
    )
    assert updated.status_code == 200
    assert _assert_envelope(updated.json(), "EVENT_UPDATED")["name"] == "Renamed"

    deleted = client.delete(f"{EVENTS_V2}/TEST_EVENT_V2", headers=ADMIN_AUTH)
    assert deleted.status_code == 200  # not 204 — see router_v2.py's module docstring
    assert _assert_envelope(deleted.json(), "EVENT_DELETED") is None

    gone = client.get(f"{EVENTS_V2}/TEST_EVENT_V2")
    assert gone.status_code == 404
    assert gone.json()["message"] == "EVENT_NOT_FOUND"


def test_create_event_v2_requires_admin_role(client):
    r = client.post(EVENTS_V2, json=_NEW_EVENT, headers=USER_AUTH)
    assert r.status_code == 403
    assert r.json()["message"] == "FORBIDDEN"


def test_create_duplicate_event_v2_is_enveloped_conflict(client):
    client.post(EVENTS_V2, json=_NEW_EVENT, headers=ADMIN_AUTH)
    dup = client.post(EVENTS_V2, json=_NEW_EVENT, headers=ADMIN_AUTH)
    assert dup.status_code == 409
    body = dup.json()
    assert body["success"] is False
    assert body["message"] == "EVENT_ALREADY_EXISTS"
    assert "TEST_EVENT_V2" in body["data"]["detail"]


def test_generate_event_occurrences_v2_is_enveloped(client):
    client.post(EVENTS_V2, json={**_NEW_EVENT, "is_poornima": True}, headers=ADMIN_AUTH)
    r = client.post(
        f"{EVENTS_V2}/TEST_EVENT_V2/occurrences",
        json={"start_year": 2000, "end_year": 2000},  # unseeded year -> IncompleteYearDataException
        headers=ADMIN_AUTH,
    )
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["message"] == "VALIDATION_FAILED"


# ── settings v2 ──────────────────────────────────────────────────────────────

def test_list_settings_v2_is_enveloped(client):
    r = client.get(f"{V2}/settings", headers=ADMIN_AUTH)
    assert r.status_code == 200
    data = _assert_envelope(r.json(), "SETTINGS_LIST_SUCCESS")
    assert isinstance(data, list) and data


def test_get_setting_v2_not_found_is_enveloped(client):
    r = client.get(f"{V2}/settings/does-not-exist", headers=ADMIN_AUTH)
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert body["message"] == "SETTING_NOT_FOUND"


def test_get_setting_v1_error_shape_is_untouched(client):
    r = client.get(f"{V1}/settings/does-not-exist", headers=ADMIN_AUTH)
    assert r.status_code == 404
    assert set(r.json()) == {"detail"}


def test_settings_v2_requires_admin_even_for_reads(client):
    r = client.get(f"{V2}/settings", headers=USER_AUTH)
    assert r.status_code == 403
    assert r.json()["message"] == "FORBIDDEN"
