from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — registers every table on SQLModel.metadata
from core.calendar.panchangam import get_panchangam_data, get_panchangam_data_at_instant
from core.constants import DEFAULT_TIMEZONE
from db.database import get_session
from main import app


def test_get_nakshathra():
    pass


# ── get_panchangam_data_at_instant (core, no DB) ────────────────────────────

def test_instant_anchored_thithi_matches_active_transition():
    """The thithi returned for a given instant equals whichever transition's
    [start, end) window actually contains that instant, per the same
    transition list the function itself computed from."""
    instant = datetime(2022, 6, 15, 12, 0, tzinfo=ZoneInfo(DEFAULT_TIMEZONE))
    data = get_panchangam_data_at_instant(instant, timezone=DEFAULT_TIMEZONE)

    matching = [
        t for t in data.thithi_transitions
        if t.start_time <= instant and (t.end_time is None or instant < t.end_time)
    ]
    assert matching
    assert matching[0].thithi == data.thithi


def test_instant_anchored_differs_from_sunrise_anchored_across_a_transition():
    """Find a date whose thithi transition falls strictly after sunrise, then
    confirm querying just before vs. just after that boundary yields
    different thithi — proving the endpoint anchors at the requested
    instant, not always at sunrise (unlike get_panchangam_data())."""
    transition_after_sunrise = None
    day = None
    for offset in range(60):
        candidate_day = date(2022, 1, 1) + timedelta(days=offset)
        sunrise_data = get_panchangam_data(candidate_day, timezone=DEFAULT_TIMEZONE)
        transition_after_sunrise = next(
            (
                t for t in sunrise_data.thithi_transitions
                if t.start_time > sunrise_data.sunrise
                and t.end_time is not None
                and t.start_time.date() == candidate_day
            ),
            None,
        )
        if transition_after_sunrise is not None:
            day = candidate_day
            break

    assert transition_after_sunrise is not None, "no mid-day thithi transition found in fixture range"

    just_before = get_panchangam_data_at_instant(
        transition_after_sunrise.start_time - timedelta(minutes=1), timezone=DEFAULT_TIMEZONE
    )
    just_after = get_panchangam_data_at_instant(
        transition_after_sunrise.start_time + timedelta(minutes=1), timezone=DEFAULT_TIMEZONE
    )
    assert just_before.thithi != just_after.thithi


# ── GET /api/v1/panchangam/instant ──────────────────────────────────────────

@pytest.fixture
def instant_client():
    """TestClient with get_session overridden onto a fresh, unseeded in-memory
    engine. /instant never reads through the repository (arbitrary coordinates
    are never in the seeded DB) or event definitions, so no seed data is needed
    — only the schema, so SettingsService has tables to (not) find rows in."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def _override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


def test_instant_endpoint_200_for_arbitrary_coordinate(instant_client):
    r = instant_client.get(
        "/api/v1/panchangam/instant",
        params={
            "day": "2022-06-15",
            "time": "12:00:00",
            "latitude": 10.0,
            "longitude": 76.0,
            "timezone": "Asia/Kolkata",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2022-06-15"
    assert body["location"] is None  # not the Santhigiri Ashram coordinate


def test_instant_bad_timezone_returns_400(instant_client):
    r = instant_client.get(
        "/api/v1/panchangam/instant",
        params={
            "day": "2022-06-15",
            "time": "12:00:00",
            "latitude": 10.0,
            "longitude": 76.0,
            "timezone": "Not/AZone",
        },
    )
    assert r.status_code == 400


@pytest.mark.parametrize(
    "field,value", [("latitude", 91), ("latitude", -91), ("longitude", 181), ("longitude", -181)]
)
def test_instant_lat_lon_out_of_bounds_returns_422(instant_client, field, value):
    params = {
        "day": "2022-06-15",
        "time": "12:00:00",
        "latitude": 10.0,
        "longitude": 76.0,
        "timezone": "Asia/Kolkata",
    }
    params[field] = value
    r = instant_client.get("/api/v1/panchangam/instant", params=params)
    assert r.status_code == 422


def test_instant_requires_time_param(instant_client):
    r = instant_client.get(
        "/api/v1/panchangam/instant",
        params={"day": "2022-06-15", "latitude": 10.0, "longitude": 76.0},
    )
    assert r.status_code == 422
