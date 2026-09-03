"""
Tests for GET /api/v1/panchangam/instant and the underlying
get_panchangam_data(instant=...) / PanchangamService.get_panchangam_at_instant.

2022-03-20 (Santhigiri Ashram coordinates) has two known transitions, taken
from data/panchangam_2022.pkl:

  Nakshatra: CHITHIRA -> CHOTHI at 2022-03-20 22:40:37 +05:30
  Thithi:    DWITHIYA_KRISHNA -> TRITHIYA_KRISHNA at 2022-03-20 10:06:51 +05:30

Sunrise that day is 06:30, before both transitions, so the "day" values (as
served by /day) are CHITHIRA / DWITHIYA_KRISHNA. Querying instants straddling
each transition confirms /instant reflects the instant given, not sunrise.
"""
from datetime import date, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.db.database  # noqa: F401 — registers the FK pragma listener
import app.db.models  # noqa: F401 — registers every table on SQLModel.metadata
from app.core.calendar.panchangam import get_panchangam_data
from app.core.astronomy.constants import Coordinates, DEFAULT_TIMEZONE
from app.db.database import get_session
from app.db.seed import seed_lookup_tables
from app.main import app

DAY = date(2022, 3, 20)
BEFORE_THITHI_TRANSITION = time(9, 0)
AFTER_THITHI_TRANSITION = time(12, 0)
AFTER_NAKSHATRA_TRANSITION = time(23, 0)


def _instant(t: time):
    from zoneinfo import ZoneInfo
    from datetime import datetime
    return datetime.combine(DAY, t, tzinfo=ZoneInfo(DEFAULT_TIMEZONE))


# ── core.calendar.panchangam.get_panchangam_data(instant=...) ────────────────

def test_default_instant_is_unchanged_and_matches_sunrise_value():
    data = get_panchangam_data(DAY, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE)
    assert data.thithi.name == "DWITHIYA_KRISHNA"
    assert data.nakshatra.name == "CHITHIRA"


def test_instant_before_thithi_transition():
    data = get_panchangam_data(
        DAY, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE,
        instant=_instant(BEFORE_THITHI_TRANSITION),
    )
    assert data.thithi.name == "DWITHIYA_KRISHNA"
    assert data.nakshatra.name == "CHITHIRA"


def test_instant_after_thithi_transition():
    data = get_panchangam_data(
        DAY, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE,
        instant=_instant(AFTER_THITHI_TRANSITION),
    )
    assert data.thithi.name == "TRITHIYA_KRISHNA"
    assert data.nakshatra.name == "CHITHIRA"


def test_instant_after_nakshatra_transition():
    data = get_panchangam_data(
        DAY, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE,
        instant=_instant(AFTER_NAKSHATRA_TRANSITION),
    )
    assert data.thithi.name == "TRITHIYA_KRISHNA"
    assert data.nakshatra.name == "CHOTHI"


# ── API ────────────────────────────────────────────────────────────────────

@pytest.fixture
def api_engine():
    """In-memory engine with lookup tables seeded (no panchangam rows needed —
    /instant is always live-computed)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        seed_lookup_tables(s)
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


def _params(t: str):
    return {
        "day": str(DAY),
        "time": t,
        "latitude": Coordinates.SG_LATITUDE,
        "longitude": Coordinates.SG_LONGITUDE,
        "timezone": DEFAULT_TIMEZONE,
    }


def test_instant_endpoint_reflects_the_given_time(client):
    r = client.get("/api/v1/panchangam/instant", params=_params("23:00"))
    assert r.status_code == 200
    body = r.json()
    assert body["nakshatra"] == "CHOTHI"
    assert body["thithi"] == "TRITHIYA_KRISHNA"


def test_instant_endpoint_out_of_range_latitude_is_422(client):
    params = _params("12:00")
    params["latitude"] = 999
    r = client.get("/api/v1/panchangam/instant", params=params)
    assert r.status_code == 422


def test_instant_endpoint_unknown_timezone_is_400(client):
    params = _params("12:00")
    params["timezone"] = "Not/A_Zone"
    r = client.get("/api/v1/panchangam/instant", params=params)
    assert r.status_code == 400
