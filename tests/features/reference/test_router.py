"""
Tests for the static ``/panchangam/event-condition-fields`` reference endpoint.

Unlike the DB-backed enum reference endpoints (thithi/nakshatra/masa/events/
locations), this one needs no database session at all — it serves a
code-defined field registry via ``etag_json_response`` — so ``TestClient(app)``
is driven directly with no ``get_session`` override.
"""
from fastapi.testclient import TestClient

from app.main import app
from app.utils.santhigiri_events import EVENT_CONDITION_FIELDS


def _client() -> TestClient:
    # Not entered as a context manager, so the app lifespan (which would try
    # to reach a real Postgres DB) never runs — this endpoint doesn't need it.
    return TestClient(app)


def test_event_condition_fields_200_lists_every_spec():
    r = _client().get("/api/v1/panchangam/event-condition-fields")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == len(EVENT_CONDITION_FIELDS)
    keys = {f["key"] for f in body}
    assert keys == {f.key for f in EVENT_CONDITION_FIELDS}


def test_event_condition_fields_enum_fields_carry_reference_dataset():
    r = _client().get("/api/v1/panchangam/event-condition-fields")
    by_key = {f["key"]: f for f in r.json()}
    assert by_key["nakshatra"] == {
        "key": "nakshatra",
        "label": "Nakshatra",
        "kind": "nakshatra",
        "reference_dataset": "nakshatra",
    }
    assert by_key["is_poornima"]["kind"] == "bool"
    assert by_key["is_poornima"]["reference_dataset"] is None


def test_event_condition_fields_excludes_non_criterion_fields():
    keys = {f["key"] for f in _client().get("/api/v1/panchangam/event-condition-fields").json()}
    assert "occurance" not in keys
    assert "day_offset" not in keys


def test_event_condition_fields_carries_etag_and_304s():
    client = _client()
    first = client.get("/api/v1/panchangam/event-condition-fields")
    etag = first.headers["etag"]
    second = client.get(
        "/api/v1/panchangam/event-condition-fields",
        headers={"If-None-Match": etag},
    )
    assert second.status_code == 304
    assert second.content == b""
