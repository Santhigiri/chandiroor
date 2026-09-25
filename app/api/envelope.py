"""
FastAPI-aware machinery for the v2 response envelope (app/schemas/api_response.py).

Parallel to api/deps.py: this is API-boundary plumbing, not business logic or a
shared schema. `envelope()`/`ok()` build the {success, message, data} body;
register_v2_exception_handlers() scopes enveloped errors to /api/v2/* only —
v1 keeps FastAPI's stock {"detail": ...} shape byte-for-byte, since the handlers
below delegate to FastAPI's own default handler functions for any non-v2 path
rather than re-raising (re-raising from inside a registered exception handler
does not fall through to the default handler — it propagates as an unhandled
exception; verified against this FastAPI/Starlette version before writing this).
"""
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.schemas.api_response import ApiResponse, MessageCode

_V2_PREFIX = "/api/v2"


class AppHTTPException(HTTPException):
    """HTTPException carrying an explicit MessageCode, for v2 routes that need a
    resource-specific code (EVENT_NOT_FOUND, ...) instead of the generic
    status-code-driven fallback the v2 exception handler applies otherwise."""

    def __init__(self, status_code: int, detail: str, code: MessageCode) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


def envelope(message: MessageCode) -> Callable[[Any], ApiResponse]:
    """Closure passed as `body_transform` to conditional_json_response/etag_json_response
    (features/etag/service.py) — wraps an already-hashed payload in the envelope
    without changing what gets hashed for the ETag."""

    def _wrap(data: Any) -> ApiResponse:
        return ApiResponse(success=True, message=message, data=data)

    return _wrap


def ok(data: Any, message: MessageCode, status_code: int = status.HTTP_200_OK) -> JSONResponse:
    body = ApiResponse(success=True, message=message, data=data)
    return JSONResponse(content=jsonable_encoder(body), status_code=status_code)


_STATUS_TO_CODE = {
    400: MessageCode.BAD_REQUEST,
    401: MessageCode.UNAUTHORIZED,
    403: MessageCode.FORBIDDEN,
    404: MessageCode.NOT_FOUND,
    409: MessageCode.CONFLICT,
    422: MessageCode.VALIDATION_FAILED,
}


def _error_body(message: MessageCode, detail: Any) -> dict:
    return jsonable_encoder(ApiResponse(success=False, message=message, data={"detail": detail}))


def _is_v2(request: Request) -> bool:
    return request.url.path.startswith(_V2_PREFIX)


def register_v2_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def v2_http_exception_handler(request: Request, exc: HTTPException):
        if not _is_v2(request):
            return await http_exception_handler(request, exc)
        code: MessageCode = (
            exc.code if isinstance(exc, AppHTTPException) else _STATUS_TO_CODE.get(
                exc.status_code, MessageCode.INTERNAL_ERROR
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, exc.detail),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def v2_validation_exception_handler(request: Request, exc: RequestValidationError):
        if not _is_v2(request):
            return await request_validation_exception_handler(request, exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(MessageCode.VALIDATION_FAILED, exc.errors()),
        )
