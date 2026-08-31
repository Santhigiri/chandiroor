"""
End-to-end tests for the "generate occurrences over a year range" endpoint:
``POST /api/v1/panchangam/events/{event_id}/occurrences``, plus its all-events
counterpart ``POST /api/v1/panchangam/events/generate``.

Seeds an in-memory DB from the real 2022 pickle cache (same fixture pattern as
``tests/test_etag.py``), so occurrences are computed against real astronomical
data rather than synthetic fixtures. The pickle's own
``santhigiri_significant_dates`` were themselves derived by the offline cache
pipeline (``features/santhigiri_events/offline_cache/cache_common_events.py``, ``cache_navapoojitham.py``,
``cache_sishya_bday.py``, ``cache_chothi_theerthayathra.py``), so re-deriving
the same dates via the new endpoint is a strong cross-check that the
generalized algorithms in ``core/calendar/santhigiri_event_occurrences.py``
agree with the bespoke offline ones.
"""
from __future__ import annotations

import datetime
import json
import pickle

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import db.database  # noqa: F401 — registers the FK pragma listener
import db.models  # noqa: F401 — register every table on SQLModel.metadata
from core.security import hash_password
from db.database import get_session
from features.etag.repository import EtagRepository
from db.unit_of_work import SqlUnitOfWork
from db.repository import PanchangamRepository
from db.seed import seed_lookup_tables
from db.user_repository import UserRepository
from main import app
from features.etag.service import refresh_etags, year_key
from utils.location import Location
from utils.roles import Role

PICKLE_2022 = "data/panchangam_2022.pkl"
YEAR = 2022
EVENTS_URL = "/api/v1/panchangam/events"
ADMIN_USER, ADMIN_PW = "admin", "admin-password"
NORMAL_USER, NORMAL_PW = "devotee", "user-password"


@pytest.fixture
def api_engine():
    """In-memory engine seeded from the 2022 pickle, plus an admin/normal user."""
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
        refresh_etags(s, EtagRepository(s), SqlUnitOfWork(s), [YEAR])
        repo = UserRepository(s)
        repo.create(ADMIN_USER, hash_password(ADMIN_PW), Role.ADMIN)
        repo.create(NORMAL_USER, hash_password(NORMAL_PW), Role.USER)
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


def _generate(client, admin_auth, event_id, start_year=YEAR, end_year=YEAR):
    return client.post(
        f"{EVENTS_URL}/{event_id}/occurrences",
        headers=admin_auth,
        json={"start_year": start_year, "end_year": end_year},
    )


def _stored_etag(api_engine) -> str:
    with Session(api_engine) as s:
        return EtagRepository(s).get(year_key(YEAR, Location.TVM.code))


def _lines(response) -> list[dict]:
    """Parse an NDJSON response body into a list of line objects."""
    return [json.loads(line) for line in response.text.strip().split("\n") if line]


def _generate_all(client, admin_auth, start_year=YEAR, end_year=YEAR):
    return client.post(
        f"{EVENTS_URL}/generate",
        headers=admin_auth,
        json={"start_year": start_year, "end_year": end_year},
    )


# ── Authorization ────────────────────────────────────────────────────────────

def test_generate_requires_authentication(client):
    r = client.post(
        f"{EVENTS_URL}/POURNAMI/occurrences",
        json={"start_year": YEAR, "end_year": YEAR},
    )
    assert r.status_code == 401


def test_generate_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        f"{EVENTS_URL}/POURNAMI/occurrences",
        headers=user_auth,
        json={"start_year": YEAR, "end_year": YEAR},
    )
    assert r.status_code == 403


def test_generate_rejects_end_year_before_start_year(client, admin_auth):
    r = client.post(
        f"{EVENTS_URL}/POURNAMI/occurrences",
        headers=admin_auth,
        json={"start_year": YEAR, "end_year": YEAR - 1},
    )
    assert r.status_code == 422


def test_generate_rejects_oversized_range(client, admin_auth):
    r = client.post(
        f"{EVENTS_URL}/POURNAMI/occurrences",
        headers=admin_auth,
        json={"start_year": 2021, "end_year": 2021 + 20},
    )
    assert r.status_code == 422


# ── Class A: single-day-pinned ──────────────────────────────────────────────

def test_generate_single_day_event_matches_offline_pipeline(client, admin_auth):
    r = _generate(client, admin_auth, "POURNAMI")
    assert r.status_code == 200
    body = r.json()
    assert body["event_id"] == "POURNAMI"
    assert body["start_year"] == YEAR
    assert body["end_year"] == YEAR
    assert len(body["occurrences"][str(YEAR)]) == 12  # one per lunar month


# ── Class B: last-occurrence-in-month ───────────────────────────────────────

def test_generate_last_occurrence_event_matches_offline_pipeline(client, admin_auth):
    r = _generate(client, admin_auth, "NAVAPOOJITHAM")
    assert r.status_code == 200
    body = r.json()
    assert body["occurrences"][str(YEAR)] == ["2022-09-01"]


def test_generate_sishya_bday_matches_offline_pipeline(client, admin_auth):
    r = _generate(client, admin_auth, "SHISHYAPOOJITHA_BDAY")
    assert r.status_code == 200
    assert r.json()["occurrences"][str(YEAR)] == ["2022-10-30"]


# ── Class C: every-transition-in-year ───────────────────────────────────────

def test_generate_transition_series_event_matches_offline_pipeline(client, admin_auth):
    r = _generate(client, admin_auth, "JANMAGRIHA_THEERTHA_YATHRA")
    assert r.status_code == 200
    assert len(r.json()["occurrences"][str(YEAR)]) == 13


# ── yields_to_event_id: cross-event exclusion ───────────────────────────────
#
# NAVAPOOJITHAM's last-Chothi-in-Chingam date is, incidentally, also a routine
# Chothi transition — so it's included in JANMAGRIHA_THEERTHA_YATHRA's set by
# default (confirmed above: 13 dates for 2022, including 2022-09-01, the same
# date NAVAPOOJITHAM resolves to). Setting yields_to_event_id makes the
# transition-series event defer to the last-occurrence event on that date.

def _set_yields_to(client, admin_auth, event_id, yields_to_event_id):
    return client.put(
        f"{EVENTS_URL}/{event_id}",
        headers=admin_auth,
        json={"yields_to_event_id": yields_to_event_id},
    )


def test_yields_to_excludes_shared_date_single_event(client, admin_auth):
    assert _set_yields_to(
        client, admin_auth, "JANMAGRIHA_THEERTHA_YATHRA", "NAVAPOOJITHAM"
    ).status_code == 200

    nav = _generate(client, admin_auth, "NAVAPOOJITHAM").json()
    jty = _generate(client, admin_auth, "JANMAGRIHA_THEERTHA_YATHRA").json()

    assert nav["occurrences"][str(YEAR)] == ["2022-09-01"]
    assert "2022-09-01" not in jty["occurrences"][str(YEAR)]
    assert len(jty["occurrences"][str(YEAR)]) == 12  # 13 minus the shared date


def test_yields_to_excludes_shared_date_bulk_generate(client, admin_auth):
    _set_yields_to(client, admin_auth, "JANMAGRIHA_THEERTHA_YATHRA", "NAVAPOOJITHAM")

    r = _generate_all(client, admin_auth)
    progress = {
        line["event_id"]: line for line in _lines(r) if line["type"] == "progress"
    }

    assert progress["NAVAPOOJITHAM"]["status"] == "generated"
    assert progress["JANMAGRIHA_THEERTHA_YATHRA"]["status"] == "generated"
    assert progress["JANMAGRIHA_THEERTHA_YATHRA"]["count"] == 12

    jty = _generate(client, admin_auth, "JANMAGRIHA_THEERTHA_YATHRA").json()
    assert "2022-09-01" not in jty["occurrences"][str(YEAR)]


def test_yields_to_survives_sibling_deletion(client, admin_auth):
    _set_yields_to(client, admin_auth, "JANMAGRIHA_THEERTHA_YATHRA", "NAVAPOOJITHAM")
    assert (
        client.delete(f"{EVENTS_URL}/NAVAPOOJITHAM", headers=admin_auth).status_code
        == 204
    )

    # ON DELETE SET NULL cleared yields_to_event_id — exclusion no longer applies.
    r = _generate(client, admin_auth, "JANMAGRIHA_THEERTHA_YATHRA")
    assert r.status_code == 200
    dates = r.json()["occurrences"][str(YEAR)]
    assert "2022-09-01" in dates
    assert len(dates) == 13


# ── day_offset ───────────────────────────────────────────────────────────────

def _set_day_offset(client, admin_auth, event_id, day_offset):
    return client.put(
        f"{EVENTS_URL}/{event_id}",
        headers=admin_auth,
        json={"day_offset": day_offset},
    )


def test_generate_shifts_single_day_occurrences_by_day_offset(client, admin_auth):
    baseline = _generate(client, admin_auth, "POURNAMI").json()["occurrences"][str(YEAR)]

    assert _set_day_offset(client, admin_auth, "POURNAMI", 2).status_code == 200
    shifted = _generate(client, admin_auth, "POURNAMI").json()["occurrences"][str(YEAR)]

    expected = [
        (datetime.date.fromisoformat(d) + datetime.timedelta(days=2)).isoformat()
        for d in baseline
    ]
    assert shifted == expected


def test_generate_offset_crossing_year_boundary_is_422(client, admin_auth):
    # NAVOLI_JYOTHIR_DINAM is pinned to May 6 — shifting it far enough to cross
    # into a different year isn't possible with a small offset, so instead pin
    # a fresh event right at year-end and shift it across the boundary.
    client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "YEAR_END", "name": "n", "description": "d", "en_day": 31, "en_month": 12, "day_offset": 2},
    )
    r = _generate(client, admin_auth, "YEAR_END")
    assert r.status_code == 422


# ── Errors ───────────────────────────────────────────────────────────────────

def test_generate_missing_event_is_404(client, admin_auth):
    r = _generate(client, admin_auth, "NOPE")
    assert r.status_code == 404


def test_generate_incomplete_year_is_422(client, admin_auth):
    r = _generate(client, admin_auth, "POURNAMI", start_year=2023, end_year=2023)
    assert r.status_code == 422


def test_generate_multi_year_range_incomplete_year_is_422(client, admin_auth):
    # 2022 is fully seeded but 2023 is not — the whole range must fail, and
    # nothing for 2022 should be (re)written as a side effect.
    r = _generate(client, admin_auth, "POURNAMI", start_year=YEAR, end_year=2023)
    assert r.status_code == 422


def test_generate_unsupported_condition_is_422(client, admin_auth):
    client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "MONTH_ONLY", "name": "n", "description": "d", "ml_month": 5},
    )
    r = _generate(client, admin_auth, "MONTH_ONLY")
    assert r.status_code == 422


# ── Idempotency / replace semantics ─────────────────────────────────────────

def test_regenerate_replaces_rather_than_appends(client, admin_auth):
    first = _generate(client, admin_auth, "POURNAMI").json()["occurrences"]
    second = _generate(client, admin_auth, "POURNAMI").json()["occurrences"]
    assert first == second


# ── ETag invalidation ────────────────────────────────────────────────────────

def test_generate_bumps_year_etag(client, admin_auth, api_engine):
    client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "NEW_EVENT", "name": "n", "description": "d", "en_day": 1, "en_month": 1},
    )
    before = _stored_etag(api_engine)

    _generate(client, admin_auth, "NEW_EVENT")

    after = _stored_etag(api_engine)
    assert after != before


# ── Bulk generation (streamed): POST /panchangam/events/generate ────────────

def test_generate_all_requires_authentication(client):
    r = client.post(
        f"{EVENTS_URL}/generate", json={"start_year": YEAR, "end_year": YEAR}
    )
    assert r.status_code == 401


def test_generate_all_requires_admin_role(client):
    user_auth = _bearer(client, NORMAL_USER, NORMAL_PW)
    r = client.post(
        f"{EVENTS_URL}/generate",
        headers=user_auth,
        json={"start_year": YEAR, "end_year": YEAR},
    )
    assert r.status_code == 403


def test_generate_all_rejects_end_year_before_start_year(client, admin_auth):
    r = client.post(
        f"{EVENTS_URL}/generate",
        headers=admin_auth,
        json={"start_year": YEAR, "end_year": YEAR - 1},
    )
    assert r.status_code == 422


def test_generate_all_rejects_oversized_range(client, admin_auth):
    r = client.post(
        f"{EVENTS_URL}/generate",
        headers=admin_auth,
        json={"start_year": 2021, "end_year": 2021 + 20},
    )
    assert r.status_code == 422


def test_generate_all_streams_progress_per_event(client, admin_auth):
    r = _generate_all(client, admin_auth)
    assert r.status_code == 200
    lines = _lines(r)

    progress = [line for line in lines if line["type"] == "progress"]
    assert len(progress) >= 1
    assert [p["completed"] for p in progress] == list(range(1, len(progress) + 1))
    assert all(p["total"] == len(progress) for p in progress)
    assert all(p["year"] == YEAR for p in progress)
    assert progress[-1]["percent"] == 100.0

    pournami = next(p for p in progress if p["event_id"] == "POURNAMI")
    assert pournami["status"] == "generated"
    assert pournami["count"] == 12

    result = lines[-1]
    assert result["type"] == "complete"
    assert result["start_year"] == YEAR
    assert result["end_year"] == YEAR
    assert result["years"] == [YEAR]
    assert result["total_events"] == len(progress)
    assert result["generated"] + result["skipped"] + result["errors"] == len(progress)
    assert result["generated"] >= 1


def test_generate_all_reports_unsupported_condition_as_skipped(client, admin_auth):
    client.post(
        EVENTS_URL,
        headers=admin_auth,
        json={"id": "MONTH_ONLY", "name": "n", "description": "d", "ml_month": 5},
    )
    r = _generate_all(client, admin_auth)
    lines = _lines(r)
    month_only = next(
        line
        for line in lines
        if line["type"] == "progress" and line["event_id"] == "MONTH_ONLY"
    )
    assert month_only["status"] == "skipped"
    assert month_only["count"] == 0
    assert month_only["detail"]

    result = lines[-1]
    assert result["type"] == "complete"
    assert result["skipped"] >= 1


def test_generate_all_incomplete_year_is_error_line(client, admin_auth):
    r = _generate_all(client, admin_auth, start_year=2023, end_year=2023)
    assert r.status_code == 200
    lines = _lines(r)
    assert lines == [
        {"type": "error", "detail": "Panchangam data for 2023 is not fully seeded."}
    ]


def test_generate_all_multi_year_range_reports_first_incomplete_year(client, admin_auth):
    # Only 2022 is seeded; a range spanning into 2023 must fail on 2023 without
    # persisting anything for 2022, even though 2022 alone would succeed.
    r = _generate_all(client, admin_auth, start_year=YEAR, end_year=2023)
    assert r.status_code == 200
    lines = _lines(r)
    assert lines[-1] == {
        "type": "error",
        "detail": "Panchangam data for 2023 is not fully seeded.",
    }


def test_generate_all_replaces_rather_than_appends(client, admin_auth):
    first = _generate_all(client, admin_auth)
    second = _generate_all(client, admin_auth)
    first_pournami = next(
        line for line in _lines(first) if line.get("event_id") == "POURNAMI"
    )
    second_pournami = next(
        line for line in _lines(second) if line.get("event_id") == "POURNAMI"
    )
    assert first_pournami["count"] == second_pournami["count"]


def test_generate_all_bumps_year_etag(client, admin_auth, api_engine):
    before = _stored_etag(api_engine)
    _generate_all(client, admin_auth)
    after = _stored_etag(api_engine)
    assert after != before
