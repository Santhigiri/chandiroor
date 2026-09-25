"""
The v2 response envelope: {"success": bool, "message": MessageCode, "data": T | null}.

Mirrors the sibling Kotlin service tvm's shared/ApiResponse.kt convention
(ApiResponse<T>(success, message, data) + success()/failure() helpers), adapted
so `message` is a fixed MessageCode value rather than free text — the frontend
maps codes to localized copy itself, same idiom as LanguageCode in
app/utils/languages.py. v1 endpoints are unaffected; only features/*/router_v2.py
and app/api/envelope.py (the FastAPI-aware helpers built on top of this) use it.
"""
from __future__ import annotations

from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel


class MessageCode(str, Enum):
    # ── Success — one per v2 endpoint/action ────────────────────────────────
    PANCHANGAM_DAY_SUCCESS = "PANCHANGAM_DAY_SUCCESS"
    PANCHANGAM_INSTANT_SUCCESS = "PANCHANGAM_INSTANT_SUCCESS"
    PANCHANGAM_MONTH_SUCCESS = "PANCHANGAM_MONTH_SUCCESS"
    PANCHANGAM_YEAR_SUCCESS = "PANCHANGAM_YEAR_SUCCESS"
    SUNRISE_SUNSET_SUCCESS = "SUNRISE_SUNSET_SUCCESS"
    SUNRISE_SUNSET_RANGE_SUCCESS = "SUNRISE_SUNSET_RANGE_SUCCESS"
    THITHI_LIST_SUCCESS = "THITHI_LIST_SUCCESS"
    NAKSHATRA_LIST_SUCCESS = "NAKSHATRA_LIST_SUCCESS"
    MASA_LIST_SUCCESS = "MASA_LIST_SUCCESS"
    CHANDRA_MASA_LIST_SUCCESS = "CHANDRA_MASA_LIST_SUCCESS"
    PAKSHA_LIST_SUCCESS = "PAKSHA_LIST_SUCCESS"
    EVENT_CREATED = "EVENT_CREATED"
    EVENT_FETCHED = "EVENT_FETCHED"
    EVENT_UPDATED = "EVENT_UPDATED"
    EVENT_DELETED = "EVENT_DELETED"
    EVENT_OCCURRENCES_GENERATED = "EVENT_OCCURRENCES_GENERATED"
    SETTINGS_LIST_SUCCESS = "SETTINGS_LIST_SUCCESS"
    SETTING_FETCHED = "SETTING_FETCHED"
    SETTING_UPDATED = "SETTING_UPDATED"

    # ── Errors — resource-specific ──────────────────────────────────────────
    EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
    EVENT_ALREADY_EXISTS = "EVENT_ALREADY_EXISTS"
    SETTING_NOT_FOUND = "SETTING_NOT_FOUND"

    # ── Errors — generic, HTTP-status-driven fallback ───────────────────────
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: MessageCode
    data: Optional[T] = None
