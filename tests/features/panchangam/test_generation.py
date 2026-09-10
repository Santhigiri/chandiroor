"""
End-to-end tests for the Panchangam generation endpoint,
``POST /api/v1/panchangam/generate``.

Uses an in-memory SQLite engine seeded with a full year of *real* (live-computed)
2022 panchangam rows — there is no offline pickle-cache pipeline any more (see
CLAUDE.md's "Regenerating data" section) — plus an admin and a regular user.
Generation overwrites the ashram's authoritative data, so it requires the
``admin`` role — mirroring ``tests/test_kollavarsham_crud.py``. Because the
seeded rows come from the same ``get_panchangam_data`` the endpoint calls,
regenerating a date reproduces its authoritative values, which we exploit to
assert that a corrupted row is repaired and that the ``/year`` ETag stays in
lockstep with what the read endpoint serves.

The full-year live computation is fairly expensive (~0.1s/day), so it is done
once per test module via the session/module-scoped ``real_year_2022_data``
fixture and reused to seed a fresh in-memory engine per test.

The endpoint streams progress as NDJSON while it works — the job's id is on
the response's ``X-Job-Id`` header, available before the body is read — and
keeps running to completion even if the client disconnects mid-stream (see
``features/generation_jobs/streaming.py::ResilientStreamingResponse``),
persisting every event into the job row as it goes. ``TestClient`` reads the
whole streamed body synchronously before a call returns, so by the time
``client.post(...)`` comes back the job has already finished — ``_run_job``
below does the POST (draining the stream) and then a single GET on
``/api/v1/generation-jobs/{job_id}`` to read its final status/result.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.db.database  # noqa: F401 — registers the FK pragma listener
import app.db.models  # noqa: F401 — register every table on SQLModel.metadata
from app.core.security import hash_password
from app.db.database import get_session
from app.features.auth.auth_repository import AuthRepository
from app.features.auth.ports import UserCreate
from app.features.etag.repository import EtagRepository
from app.db.unit_of_work import SqlUnitOfWork
from app.db.models.panchangam import Panchangam as PanchangamRow
from app.features.panchangam.repository import PanchangamRepository
from app.db.reference_repository import ReferenceRepository
from app.db.seed import seed_lookup_tables
from app.features.panchangam.service import PanchangamService
from app.main import app
from app.features.etag.service import refresh_etags, year_key
from app.utils.location import Location
from app.utils.roles import Role

YEAR = 2022
BASE = "/api/v1/panchangam/generate"
ADMIN_USER, ADMIN_PW = "admin", "admin-password"
NORMAL_USER, NORMAL_PW = "devotee", "user-password"


@pytest.fixture(scope="module")
def real_year_2022_data():
    """The real, live-computed panchangam data for every day of 2022.

    Computed once per module (not per test) since it's the same expensive
    astronomy stack ``POST /generate`` itself calls.
    """
    from app.core.calendar.panchangam import get_panchangam_data

    start = date(YEAR, 1, 1)
    num_days = 366 if calendar.isleap(YEAR) else 365
    return [get_panchangam_data(start + timedelta(days=i)) for i in range(num_days)]


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
        repo = AuthRepository(s)
        repo.create_user(UserCreate(ADMIN_USER, hash_password(ADMIN_PW), Role.ADMIN))
        repo.create_user(UserCreate(NORMAL_USER, hash_password(NORMAL_PW), Role.USER))
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


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _bearer(client, username, password) -> dict:
    # Login delivers the access token as an HTTP-only cookie; read it from the
    # login response and replay it via the Authorization header (still accepted
    # as a fallback for non-browser clients).
    token = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    ).cookies["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth(client) -> dict:
    return _bearer(client, ADMIN_USER, ADMIN_PW)


def _stored_year_etag(api_engine) -> str:
    with Session(api_engine) as s:
        return EtagRepository(s).get(year_key(YEAR, Location.TVM.code))


def _corrupt_nazhika(api_engine, day: str, value: float) -> None:
    """Directly set a stored row's nazhika to a sentinel, simulating stale data."""
    with Session(api_engine) as s:
        row = s.get(PanchangamRow, (date.fromisoformat(day), Location.TVM.id))
        row.nazhika_from_sunrise = value
        s.add(row)
        s.commit()


def _stored_nazhika(api_engine, day: str) -> float:
    with Session(api_engine) as s:
        return PanchangamRepository(s).get_by_date(
            date.fromisoformat(day), Location.TVM
        ).nazhika_from_sunrise


def _run_job(client, headers, payload: dict) -> dict:
    """POST to ``BASE`` and return the finished job's status dict.

    ``TestClient`` drains the endpoint's NDJSON stream to completion as part
    of the same call, so the job is already ``succeeded``/``failed`` by the
    time the initial POST returns — no real polling needed here."""
    started = client.post(BASE, headers=headers, json=payload)
    assert started.status_code == 200, started.text
    job_id = started.headers["x-job-id"]
    job = client.get(f"/api/v1/generation-jobs/{job_id}", headers=headers).json()
    assert job["status"] == "succeeded", job
    return job["result"]


# ── Authorization ────────────────────────────────────────────────────────────────

def test_generate_requires_authentication(client):
    r = client.post(
        BASE, json={"start_date": "2022-03-01", "end_date": "2022-03-02"}
    )
    assert r.status_code == 401


def test_generate_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        BASE,
        headers=user_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-02"},
    )
    assert r.status_code == 403


# ── Generate ─────────────────────────────────────────────────────────────────────

def test_generate_over_range_reports_summary(client, admin_auth):
    result = _run_job(
        client, admin_auth, {"start_date": "2022-03-01", "end_date": "2022-03-03"}
    )
    assert result["type"] == "complete"
    assert result["count"] == 3
    assert result["years"] == [2022]
    assert result["start_date"] == "2022-03-01"
    assert result["end_date"] == "2022-03-03"


def test_generate_reports_final_result(client, admin_auth):
    # generate_streaming yields only heartbeat progress lines (completed=0)
    # while the range is computed, then writes every day in one pass with no
    # per-day progress line — so the whole range lands in the DB as one
    # write, the same as before per-day progress lines existed at all (see
    # PanchangamGenerationService.generate_streaming's docstring). The job's
    # "progress" column may therefore still hold a stale heartbeat (or None,
    # for a run that finished inside the first heartbeat interval) once the
    # job has succeeded — "result" is what carries the real completion data.
    started = client.post(
        BASE,
        headers=admin_auth,
        json={"start_date": "2022-03-01", "end_date": "2022-03-03"},
    )
    assert started.status_code == 200
    job = client.get(
        f"/api/v1/generation-jobs/{started.headers['x-job-id']}", headers=admin_auth
    ).json()
    assert job["status"] == "succeeded"
    result = job["result"]
    assert result["count"] == 3
    assert result["start_date"] == "2022-03-01"
    assert result["end_date"] == "2022-03-03"
    if job["progress"] is not None:
        assert job["progress"]["completed"] == 0


def test_generate_overwrites_existing_row(client, admin_auth, api_engine):
    day = "2022-03-01"
    original = _stored_nazhika(api_engine, day)
    _corrupt_nazhika(api_engine, day, -999.0)
    assert _stored_nazhika(api_engine, day) == -999.0

    _run_job(client, admin_auth, {"start_date": day, "end_date": day})
    # The recomputed value replaced the corrupted one.
    assert _stored_nazhika(api_engine, day) != -999.0
    assert _stored_nazhika(api_engine, day) == pytest.approx(original)


def test_generate_keeps_year_etag_in_lockstep(client, admin_auth, api_engine):
    # A corrupted row makes the served /year payload (and thus its live ETag)
    # diverge from the stored one; regenerating must both repair the row and
    # refresh the stored ETag so the two match again.
    _corrupt_nazhika(api_engine, "2022-03-01", -999.0)
    _run_job(
        client, admin_auth, {"start_date": "2022-03-01", "end_date": "2022-03-03"}
    )
    served = client.get(
        "/api/v1/panchangam/year", params={"year": YEAR}
    ).headers["etag"]
    assert served == _stored_year_etag(api_engine)


# ── Range validation ─────────────────────────────────────────────────────────────

def test_generate_rejects_reversed_range(client, admin_auth):
    r = client.post(
        BASE,
        headers=admin_auth,
        json={"start_date": "2022-03-05", "end_date": "2022-03-01"},
    )
    assert r.status_code == 422


def test_generate_rejects_oversized_range(client, admin_auth):
    r = client.post(
        BASE,
        headers=admin_auth,
        json={"start_date": "2022-01-01", "end_date": "2023-06-01"},
    )
    assert r.status_code == 422
