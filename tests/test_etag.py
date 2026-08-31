"""
Tests for the ETag change-detection feature.

Covers the pure helpers (``stable_hash``, ``if_none_match_satisfied``) and the
end-to-end conditional-request behaviour of the year and enum-reference
endpoints via ``TestClient``. The API fixture seeds an in-memory DB from the real
2022 pickle and precomputes ETags via ``refresh_etags`` the same way the SQL
seed data is prepared offline.
"""
import pickle

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — registers every table on SQLModel.metadata
from db.database import get_session
from features.etag.repository import EtagRepository
from db.unit_of_work import SqlUnitOfWork
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from features.panchangam.service import PanchangamService
from main import app
from features.etag.service import refresh_etags, year_key
from utils.content_hash import stable_hash
from utils.etag import if_none_match_satisfied
from utils.location import Location

PICKLE_2022 = "data/panchangam_2022.pkl"
YEAR = 2022


# ── stable_hash ───────────────────────────────────────────────────────────────

def test_stable_hash_deterministic():
    payload = {"b": 1, "a": [1, 2, {"z": 3}]}
    assert stable_hash(payload) == stable_hash(payload)


def test_stable_hash_ignores_key_order():
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})


def test_stable_hash_changes_with_value():
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


# ── if_none_match_satisfied ───────────────────────────────────────────────────

@pytest.mark.parametrize(
    "header,etag,expected",
    [
        ('"x"', '"x"', True),
        ("*", '"x"', True),
        ('"a", "x"', '"x"', True),   # comma list
        ('W/"x"', '"x"', True),      # weak validator prefix ignored
        ('"y"', '"x"', False),
        (None, '"x"', False),
        ("", '"x"', False),
    ],
)
def test_if_none_match_satisfied(header, etag, expected):
    assert if_none_match_satisfied(header, etag) is expected


# ── API fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture
def api_engine():
    """In-memory engine seeded from the 2022 pickle with ETags precomputed."""
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
        refresh_etags(s, PanchangamService(PanchangamRepository(s)), EtagRepository(s), SqlUnitOfWork(s), [YEAR])
    try:
        yield engine
    finally:
        SQLModel.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(api_engine):
    """TestClient with get_session overridden onto the seeded in-memory engine.

    Not entered as a context manager, so the app lifespan (which would ensure the
    real Postgres schema) never runs.
    """
    def _override():
        with Session(api_engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ── Year endpoint ─────────────────────────────────────────────────────────────

def test_year_200_carries_etag(client):
    r = client.get("/api/v1/panchangam/year", params={"year": YEAR})
    assert r.status_code == 200
    assert r.headers.get("etag", "").startswith('"')
    assert len(r.json()) > 300  # a full year of days


def test_year_304_when_if_none_match_matches(client):
    first = client.get("/api/v1/panchangam/year", params={"year": YEAR})
    etag = first.headers["etag"]

    second = client.get(
        "/api/v1/panchangam/year",
        params={"year": YEAR},
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["etag"] == etag


def test_year_200_when_if_none_match_is_stale(client):
    r = client.get(
        "/api/v1/panchangam/year",
        params={"year": YEAR},
        headers={"If-None-Match": '"not-the-current-etag"'},
    )
    assert r.status_code == 200
    assert r.json()


def test_year_served_etag_matches_stored(client, api_engine):
    served = client.get("/api/v1/panchangam/year", params={"year": YEAR}).headers["etag"]
    with Session(api_engine) as s:
        stored = EtagRepository(s).get(year_key(YEAR, Location.TVM.code))
    assert served == stored


def test_year_etag_key_is_location_scoped(client, api_engine):
    """The year ETag is stored under a location-scoped key, not a bare year key."""
    client.get("/api/v1/panchangam/year", params={"year": YEAR})
    with Session(api_engine) as s:
        repo = EtagRepository(s)
        assert repo.get(f"year:tvm:{YEAR}") is not None
        assert repo.get(f"year:{YEAR}") is None  # old un-scoped key must not be used


def test_year_defaults_to_tvm_when_location_omitted(client):
    """Omitting ?location resolves to the ashram (tvm) and serves data."""
    r = client.get("/api/v1/panchangam/year", params={"year": YEAR})
    assert r.status_code == 200
    assert len(r.json()) > 300


def test_unknown_location_is_404(client):
    r = client.get(
        "/api/v1/panchangam/day",
        params={"day": f"{YEAR}-03-20", "location": "atlantis"},
    )
    assert r.status_code == 404


def test_day_response_carries_location_descriptor(client):
    r = client.get("/api/v1/panchangam/day", params={"day": f"{YEAR}-03-20"})
    assert r.status_code == 200
    assert r.json()["location"] == {"code": "tvm", "label": "Trivandrum, Kerala, India"}


# ── Enum reference endpoints ──────────────────────────────────────────────────

@pytest.mark.parametrize("name", ["thithi", "nakshatra", "masa", "events", "locations"])
def test_reference_etag_round_trip(client, name):
    first = client.get(f"/api/v1/panchangam/{name}")
    assert first.status_code == 200
    etag = first.headers["etag"]
    assert etag and first.json()

    second = client.get(f"/api/v1/panchangam/{name}", headers={"If-None-Match": etag})
    assert second.status_code == 304
    assert second.content == b""


def test_locations_reference_lists_tvm(client):
    r = client.get("/api/v1/panchangam/locations")
    assert r.status_code == 200
    codes = {loc["code"] for loc in r.json()}
    assert "tvm" in codes
