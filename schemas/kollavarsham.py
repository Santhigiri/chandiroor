"""
Request/response schemas for the Kollavarsham (Malayalam solar calendar) write
endpoints under ``/api/v1/panchangam/kollavarsham``.

``generate`` (bulk astronomical (re)computation over a date range) and the
single-date manual override (``PUT``) back these models. The stored row keeps
only ``kv_day``/``kv_month``/``kv_year`` (month as its MalayalamMasa id); the
bilingual month names in :class:`KollavarshamDateRead` are derived at read time.
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# A defensive, non-editable ceiling no admin setting can exceed — a DoS
# backstop, not the real business rule. The actual cap is the admin-configured
# `max_generate_span_days` setting (shared with schemas.panchangam_generation),
# enforced by KollavarshamService (see services/settings_service.py).
_HARD_SPAN_CEILING_DAYS = 3660


class KollavarshamGenerateRequest(BaseModel):
    """Inclusive ``[start_date, end_date]`` range to (re)compute and overwrite."""

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check_range(self) -> "KollavarshamGenerateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        span = (self.end_date - self.start_date).days + 1
        if span > _HARD_SPAN_CEILING_DAYS:
            raise ValueError(
                f"date range too large: {span} days (max {_HARD_SPAN_CEILING_DAYS})"
            )
        return self


class KollavarshamDateUpdate(BaseModel):
    """Partial manual override for a single date — at least one field required."""

    kv_day: Optional[int] = Field(default=None, ge=1, le=32)
    kv_month: Optional[int] = Field(default=None, ge=1, le=12)
    kv_year: Optional[int] = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "KollavarshamDateUpdate":
        if self.kv_day is None and self.kv_month is None and self.kv_year is None:
            raise ValueError("at least one of kv_day, kv_month, kv_year is required")
        return self


class KollavarshamDateRead(BaseModel):
    """Full Kollavarsham date, including the derived bilingual month names."""

    model_config = ConfigDict(from_attributes=True)

    date: date
    kv_day: int
    kv_month: int
    kv_year: int
    kv_month_name_en: str
    kv_month_name_ml: str


class KollavarshamGenerateResult(BaseModel):
    """Summary returned by the generate endpoint."""

    start_date: date
    end_date: date
    count: int
    years: List[int]
