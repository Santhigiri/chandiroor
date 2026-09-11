"""
End-to-end regression test for last-occurrence events whose Malayalam month
straddles the Gregorian year boundary (Dhanu spans December of one year into
January of the next, for a single Kollam year — see CLAUDE.md's Kollavarsham
section).

Before the fix, ``SanthigiriEventService.generate_occurrences`` fetched only
the plain ``Jan 1``-``Dec 31`` window of the requested year, so a Dhanu-based
``last_occurance`` condition whose true last match fell in January was
invisible when generating the December-side year — the (wrong) December
match would be returned instead. This test seeds synthetic data (no live
ephemeris — see ``make_panchangam_data``) around a real December/January
straddle and asserts the fix's behaviour directly.
"""
from __future__ import annotations

import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.db.database  # noqa: F401 — registers the FK pragma listener
import app.db.models  # noqa: F401 — register every table on SQLModel.metadata
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.core.security import hash_password
from app.core.kollavarsham.enums.masa import MalayalamMasa
from app.db.database import get_session
from app.features.auth.auth_repository import AuthRepository
from app.features.auth.ports import UserCreate
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

EVENTS_URL = "/api/v1/panchangam/events"
ADMIN_USER, ADMIN_PW = "admin", "admin-password"

# The straddling Dhanu occurrence: starts December 2025, its true last-match
# (the one the event should resolve to) falls in January 2026.
EARLIER_MATCH = datetime.date(2025, 12, 20)  # a match, but not the last one
LATEST_MATCH = datetime.date(2026, 1, 5)  # the true last occurrence


@pytest.fixture
def synthetic_data(make_panchangam_data):
    """Three full synthetic years (2025-2027) with one Dhanu-Chothi
    occurrence straddling the 2025/2026 boundary."""
    days = {}
    start = datetime.date(2025, 1, 1)
    end = datetime.date(2027, 12, 31)
    d = start
    while d <= end:
        days[d] = make_panchangam_data(d)
        d += datetime.timedelta(days=1)

    for d in (EARLIER_MATCH, LATEST_MATCH):
        days[d] = make_panchangam_data(
            d,
            nakshatra=Nakshatra.CHOTHI,
            kv_month=MalayalamMasa.DHANU,
            kv_year=1201,
            nazhika_from_sunrise=20.0,  # above the 7.5 default cutoff
        )
    return list(days.values())


@pytest.fixture
def api_engine(synthetic_data):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        seed_lookup_tables(s)
        PanchangamRepository(s).upsert_many(synthetic_data, Location.TVM)
        refresh_etags(
            ReferenceRepository(s),
            PanchangamService(PanchangamRepository(s)),
            EtagRepository(s),
            SqlUnitOfWork(s),
            [2025, 2026, 2027],
        )
        repo = AuthRepository(s)
        repo.create_user(UserCreate(ADMIN_USER, hash_password(ADMIN_PW), Role.ADMIN))
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
def admin_auth(client) -> dict:
    token = client.post(
        "/api/v1/auth/login",
        data={"username": ADMIN_USER, "password": ADMIN_PW},
    ).cookies["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def dhanu_event(client, admin_auth):
    r = client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={
            "id": "DHANU_LAST_CHOTHI",
            "name": "n",
            "description": "d",
            "ml_month": MalayalamMasa.DHANU.id,
            "nakshatra_id": Nakshatra.CHOTHI.id,
            "last_occurance": True,
        },
    )
    assert r.status_code == 201
    return "DHANU_LAST_CHOTHI"


def _generate(client, admin_auth, event_id, year):
    return client.post(
        f"{EVENTS_URL}/{event_id}/occurrences",
        headers=admin_auth,
        json={"start_year": year, "end_year": year},
    )


def test_straddling_last_occurrence_resolves_to_the_later_year(
    client, admin_auth, dhanu_event
):
    """The true last occurrence (Jan 5, 2026) is correctly attributed to
    2026, not the earlier (but not-actually-last) December 2025 match."""
    r = _generate(client, admin_auth, dhanu_event, 2026)
    assert r.status_code == 200
    assert r.json()["occurrences"]["2026"] == ["2026-01-05"]


def test_straddling_last_occurrence_is_not_misattributed_to_the_earlier_year(
    client, admin_auth, dhanu_event
):
    """Before the fix, generating 2025 alone (a window that can't see the
    January match at all) would wrongly return the December 2025 match as
    the "last occurrence". With the fix, 2025's window is padded far enough
    to see the true (January) last match, correctly recognizes it does not
    belong to 2025, and reports no computable occurrence for 2025 instead of
    a wrong one.
    """
    r = _generate(client, admin_auth, dhanu_event, 2025)
    assert r.status_code == 422
