"""Tests for the arbitrary-coordinate sunrise/sunset endpoint."""
from datetime import timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.db.database import get_session
from app.main import app


@pytest.fixture
def client(engine):
    """TestClient with get_session overridden onto a schema-only in-memory engine.

    The sunrise/sunset endpoint never touches the repository, so no seed data
    is needed — just a session FastAPI's Depends can resolve.
    """

    def _override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_sunrise_sunset_200_returns_utc(client):
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset",
        params={"latitude": 8.645, "longitude": 76.938, "day": "2026-07-30"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["latitude"] == 8.645
    assert body["longitude"] == 76.938
    assert body["day"] == "2026-07-30"

    sunrise = _parse(body["sunrise"])
    sunset = _parse(body["sunset"])
    assert sunrise.tzinfo is not None and sunrise.utcoffset() == timezone.utc.utcoffset(None)
    assert sunset.tzinfo is not None and sunset.utcoffset() == timezone.utc.utcoffset(None)
    assert sunrise < sunset

    # Ashram sunrise/sunset (IST, UTC+5:30) is roughly 06:00-06:20 / 18:30-18:50
    # local for late July, i.e. ~00:30-00:50 / ~13:00-13:20 UTC.
    assert sunrise.hour == 0
    assert sunset.hour in (12, 13)


def test_sunrise_sunset_422_for_invalid_latitude(client):
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset",
        params={"latitude": 999, "longitude": 76.938, "day": "2026-07-30"},
    )
    assert r.status_code == 422


def test_sunrise_sunset_422_for_invalid_longitude(client):
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset",
        params={"latitude": 8.645, "longitude": -181, "day": "2026-07-30"},
    )
    assert r.status_code == 422


def test_sunrise_sunset_400_for_polar_night(client):
    # Svalbard in December: polar night, no sunrise/sunset to find.
    r = client.get(
        "/api/v1/panchangam/sunrise-sunset",
        params={"latitude": 78.2, "longitude": 15.6, "day": "2026-12-21"},
    )
    assert r.status_code == 400


def _parse(iso_str: str):
    from datetime import datetime

    return datetime.fromisoformat(iso_str)
