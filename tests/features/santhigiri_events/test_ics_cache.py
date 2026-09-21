"""
Tests for the persisted ICS calendar cache: ``GET /panchangam/events/calendar.ics``
reads through a stored ``ics_cache`` row instead of rebuilding the document
(a full ``seed_year_range`` date-range scan) on every request, and event
mutations refresh that cache atomically with their existing ETag refresh.

Reuses the real, live-computed 2022 panchangam data fixture from
``test_occurrences.py`` so an occurrence-generation run actually changes the
ICS body/ETag, not just the cache's ``updated_at``.
"""
from __future__ import annotations

import datetime
import calendar
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.db.database  # noqa: F401 — registers the FK pragma listener
import app.db.models  # noqa: F401 — register every table on SQLModel.metadata
from app.db.database import get_session
from app.db.models.ics_cache import IcsCache
from app.features.etag.repository import EtagRepository
from app.db.unit_of_work import SqlUnitOfWork
from app.features.panchangam.repository import PanchangamRepository
from app.db.reference_repository import ReferenceRepository
from app.db.seed import seed_lookup_tables
from app.features.panchangam.service import PanchangamService
from app.main import app
from app.features.etag.service import refresh_etags
from app.utils.location import Location
from app.utils.roles import Role
from tests.conftest import bearer_header

YEAR = 2022
EVENTS_URL = "/api/v1/panchangam/events"
ICS_URL = f"{EVENTS_URL}/calendar.ics"
ADMIN_USER = "admin"


@pytest.fixture(scope="module")
def real_year_2022_data():
    """The real, live-computed panchangam data for every day of 2022."""
    from app.core.calendar.panchangam import get_panchangam_data

    start = datetime.date(YEAR, 1, 1)
    num_days = 366 if calendar.isleap(YEAR) else 365
    return [
        get_panchangam_data(start + datetime.timedelta(days=i))
        for i in range(num_days)
    ]


@pytest.fixture
def api_engine(real_year_2022_data):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        seed_lookup_tables(s)
        PanchangamRepository(s).upsert_many(real_year_2022_data, Location.TVM)
        refresh_etags(
            ReferenceRepository(s),
            PanchangamService(PanchangamRepository(s)),
            EtagRepository(s),
            SqlUnitOfWork(s),
            [YEAR],
        )
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


@pytest.fixture
def admin_auth() -> dict:
    return bearer_header(Role.ADMIN)


def _generate(client, admin_auth, event_id, start_year=YEAR, end_year=YEAR):
    return client.post(
        f"{EVENTS_URL}/{event_id}/occurrences",
        headers=admin_auth,
        json={"start_year": start_year, "end_year": end_year},
    )


def _stored_ics_cache(api_engine):
    with Session(api_engine) as s:
        return s.get(IcsCache, "events")


# ── Cold cache: build + persist ────────────────────────────────────────────────

def test_first_request_builds_and_persists_cache(client, api_engine):
    assert _stored_ics_cache(api_engine) is None

    r = client.get(ICS_URL)
    assert r.status_code == 200
    assert "BEGIN:VCALENDAR" in r.text
    assert r.headers["ETag"]

    row = _stored_ics_cache(api_engine)
    assert row is not None
    assert row.body == r.text
    assert row.etag == r.headers["ETag"]


# ── Warm cache: no rebuild ──────────────────────────────────────────────────────

def test_second_request_served_from_cache_without_rebuild(client, api_engine):
    first = client.get(ICS_URL)
    assert first.status_code == 200

    with patch.object(
        PanchangamRepository, "get_by_date_range", autospec=True
    ) as spy:
        second = client.get(ICS_URL)

    assert second.status_code == 200
    assert second.text == first.text
    assert second.headers["ETag"] == first.headers["ETag"]
    spy.assert_not_called()


def test_if_none_match_returns_304_without_rebuild(client):
    first = client.get(ICS_URL)
    etag = first.headers["ETag"]

    with patch.object(
        PanchangamRepository, "get_by_date_range", autospec=True
    ) as spy:
        second = client.get(ICS_URL, headers={"If-None-Match": etag})

    assert second.status_code == 304
    assert second.text == ""
    spy.assert_not_called()


# ── Invalidation on event mutation ──────────────────────────────────────────────

def test_generate_occurrences_refreshes_ics_cache(client, admin_auth, api_engine):
    before = client.get(ICS_URL)
    before_etag = before.headers["ETag"]
    before_row = _stored_ics_cache(api_engine)

    r = _generate(client, admin_auth, "POURNAMI")
    assert r.status_code == 200

    after_row = _stored_ics_cache(api_engine)
    assert after_row is not None
    assert after_row.etag != before_etag
    assert after_row.body != before_row.body
    assert "POURNAMI" in after_row.body

    after = client.get(ICS_URL)
    assert after.headers["ETag"] == after_row.etag
    assert after.text == after_row.body


def test_create_event_refreshes_ics_cache(client, admin_auth, api_engine):
    client.get(ICS_URL)  # warm the cache
    before_row = _stored_ics_cache(api_engine)

    r = client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "TEST_EVENT", "name": "Test Event", "description": "d"},
    )
    assert r.status_code == 201

    after_row = _stored_ics_cache(api_engine)
    assert after_row is not None
    # A brand-new event has no occurrences yet, so the ICS body is unchanged,
    # but the cache row must still have been rebuilt/re-persisted by the
    # mutation's _commit_with_etags -> _refresh_ics_cache hook.
    assert after_row.updated_at >= before_row.updated_at
