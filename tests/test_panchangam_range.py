"""
End-to-end tests for the date-range panchangam endpoint
(``POST /api/v1/panchangam/range``).

Seeds an in-memory DB from the real 2022 pickle (the same fixture shape as
``test_etag.py``) and drives the app with ``TestClient``.
"""
import pickle

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — registers every table on SQLModel.metadata
from db.database import get_session
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from main import app
from schemas.GetRangePanchangamParams import MAX_RANGE_DAYS
from utils.location import Location

PICKLE_2022 = "data/panchangam_2022.pkl"


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


def test_range_returns_every_day_inclusive(client):
    r = client.post(
        "/api/v1/panchangam/range",
        json={"start": "2022-03-01", "end": "2022-03-10"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 10  # inclusive of both endpoints
    assert "2022-03-01" in body
    assert "2022-03-10" in body
    # Each entry is a compact panchangam record carrying the requested location.
    assert body["2022-03-01"]["location"] == {
        "code": "tvm",
        "label": "Trivandrum, Kerala, India",
    }


def test_range_single_day(client):
    r = client.post(
        "/api/v1/panchangam/range",
        json={"start": "2022-03-05", "end": "2022-03-05"},
    )
    assert r.status_code == 200
    assert list(r.json().keys()) == ["2022-03-05"]


def test_range_end_before_start_is_422(client):
    r = client.post(
        "/api/v1/panchangam/range",
        json={"start": "2022-03-10", "end": "2022-03-01"},
    )
    assert r.status_code == 422


def test_range_exceeding_max_span_is_422(client):
    from datetime import date, timedelta

    start = date(2022, 1, 1)
    end = start + timedelta(days=MAX_RANGE_DAYS)  # one day past the limit
    r = client.post(
        "/api/v1/panchangam/range",
        json={"start": start.isoformat(), "end": end.isoformat()},
    )
    assert r.status_code == 422


def test_range_unknown_location_is_404(client):
    r = client.post(
        "/api/v1/panchangam/range",
        params={"location": "atlantis"},
        json={"start": "2022-03-01", "end": "2022-03-02"},
    )
    assert r.status_code == 404
