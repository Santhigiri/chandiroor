"""
Spike/regression test for app/api/envelope.py::register_v2_exception_handlers.

Verifies the riskiest mechanical piece of the v2 envelope rollout first, with a
minimal app + dummy routes, before any real v2 router is built on top of it:
a v2-scoped exception handler must not change v1's error shape at all, and must
enveloped-wrap the same status codes on v2. Re-raising inside a registered
FastAPI exception handler does NOT fall through to the default handler (it
propagates as an unhandled exception) — this module's handlers instead
delegate to fastapi.exception_handlers.http_exception_handler /
request_validation_exception_handler directly for non-v2 paths, which does
reproduce FastAPI's stock behavior exactly (verified here).
"""
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.envelope import AppHTTPException, register_v2_exception_handlers
from app.schemas.api_response import MessageCode


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/boom")
    def v1_boom():
        raise HTTPException(status_code=404, detail="v1 not found")

    @app.get("/api/v2/boom")
    def v2_boom():
        raise HTTPException(status_code=404, detail="v2 not found")

    @app.get("/api/v2/boom-coded")
    def v2_boom_coded():
        raise AppHTTPException(404, "event not found", MessageCode.EVENT_NOT_FOUND)

    @app.get("/api/v1/items")
    def v1_items(x: int):
        return {"x": x}

    @app.get("/api/v2/items")
    def v2_items(x: int):
        return {"x": x}

    register_v2_exception_handlers(app)
    return app


client = TestClient(_build_app())


def test_v1_http_exception_shape_is_untouched():
    r = client.get("/api/v1/boom")
    assert r.status_code == 404
    assert r.json() == {"detail": "v1 not found"}


def test_v2_http_exception_is_enveloped_with_generic_fallback_code():
    r = client.get("/api/v2/boom")
    assert r.status_code == 404
    assert r.json() == {
        "success": False,
        "message": "NOT_FOUND",
        "data": {"detail": "v2 not found"},
    }


def test_v2_app_http_exception_uses_its_explicit_code():
    r = client.get("/api/v2/boom-coded")
    assert r.status_code == 404
    assert r.json()["message"] == "EVENT_NOT_FOUND"
    assert r.json()["data"] == {"detail": "event not found"}


def test_v1_validation_error_shape_is_untouched():
    r = client.get("/api/v1/items")
    assert r.status_code == 422
    body = r.json()
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], list)


def test_v2_validation_error_is_enveloped():
    r = client.get("/api/v2/items")
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["message"] == "VALIDATION_FAILED"
    assert isinstance(body["data"]["detail"], list)
