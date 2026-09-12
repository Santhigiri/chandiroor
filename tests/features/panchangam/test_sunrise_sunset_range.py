"""Tests for the arbitrary-coordinate sunrise/sunset range endpoint."""
from datetime import date, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.database import get_session
from app.features.panchangam.schemas.get_sunrise_sunset_range_params import (
    MAX_SUNRISE_SUNSET_RANGE_DAYS,
)
from app.main import app


@pytest.fixture
def client(engine):
    """TestClient with get_session overridden onto a schema-only in-memory engine.

    The sunrise/sunset range endpoint never touches the repository, so no
    seed data is needed -- just a session FastAPI's Depends can resolve.
    """

    def _override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_sunrise_sunset_range_200_returns_utc(client):
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset/range",
        params={
            "latitude": 8.645,
            "longitude": 76.938,
            "start_date": "2026-07-29",
            "end_date": "2026-07-31",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["latitude"] == 8.645
    assert body["longitude"] == 76.938
    assert body["start_date"] == "2026-07-29"
    assert body["end_date"] == "2026-07-31"

    assert set(body["results"].keys()) == {"2026-07-29", "2026-07-30", "2026-07-31"}
    for day_result in body["results"].values():
        sunrise = _parse(day_result["sunrise"])
        sunset = _parse(day_result["sunset"])
        assert sunrise.tzinfo is not None and sunrise.utcoffset() == timezone.utc.utcoffset(None)
        assert sunset.tzinfo is not None and sunset.utcoffset() == timezone.utc.utcoffset(None)
        assert sunrise < sunset


def test_sunrise_sunset_range_matches_single_day_endpoint(client):
    range_r = client.get(
        "/api/v1/panchangam/sunrise-sunset/range",
        params={
            "latitude": 8.645,
            "longitude": 76.938,
            "start_date": "2026-07-30",
            "end_date": "2026-07-30",
        },
    )
    single_r = client.get(
        "/api/v1/panchangam/sunrise-sunset",
        params={"latitude": 8.645, "longitude": 76.938, "day": "2026-07-30"},
    )
    assert range_r.status_code == 200 and single_r.status_code == 200
    range_day = range_r.json()["results"]["2026-07-30"]
    single_body = single_r.json()
    assert range_day["sunrise"] == single_body["sunrise"]
    assert range_day["sunset"] == single_body["sunset"]


def test_sunrise_sunset_range_422_for_invalid_latitude(client):
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset/range",
        params={
            "latitude": 999,
            "longitude": 76.938,
            "start_date": "2026-07-29",
            "end_date": "2026-07-31",
        },
    )
    assert r.status_code == 422


def test_sunrise_sunset_range_422_when_end_before_start(client):
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset/range",
        params={
            "latitude": 8.645,
            "longitude": 76.938,
            "start_date": "2026-07-31",
            "end_date": "2026-07-29",
        },
    )
    assert r.status_code == 422


def test_sunrise_sunset_range_422_when_span_too_large(client):
    start = date(2026, 1, 1)
    end = start + timedelta(days=MAX_SUNRISE_SUNSET_RANGE_DAYS)
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset/range",
        params={
            "latitude": 8.645,
            "longitude": 76.938,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        },
    )
    assert r.status_code == 422


def test_sunrise_sunset_range_400_for_polar_night(client):
    # Svalbard in December: polar night, no sunrise/sunset to find.
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset/range",
        params={
            "latitude": 78.2,
            "longitude": 15.6,
            "start_date": "2026-12-20",
            "end_date": "2026-12-22",
        },
    )
    assert r.status_code == 400


def _parse(iso_str: str):
    from datetime import datetime

    return datetime.fromisoformat(iso_str)
