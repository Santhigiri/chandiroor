"""
Request/response schemas for the editable Santhigiri event definitions.

These back the write endpoints under ``/api/v1/panchangam/events`` (create,
update, delete). They mirror the columns of ``db.models.santhigiri_event`` — a
flat shape rather than the nested ``EventCondition`` used internally — so the
matching rule can be edited field-by-field. The read-only list endpoint keeps
returning the compact ``CompactSanthigiriEvent`` (id/name/description only).

``id``/``nakshatra_id``/``thithi_id``/``ml_month`` etc. are the same integer ids
used everywhere else in the API (see the ``/panchangam/nakshatra`` and
``/panchangam/thithi`` reference endpoints); ``None`` on any condition field
means "any" / "not applicable".
"""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SanthigiriEventBase(BaseModel):
    name: str = Field(min_length=1)
    description: str
    sort_order: Optional[int] = Field(
        default=None,
        description="Display order in the /events list; assigned automatically when omitted on create.",
    )

    # Condition columns — None means "any"
    nakshatra_id: Optional[int] = Field(default=None, ge=1, le=27)
    thithi_id: Optional[int] = Field(default=None, ge=1, le=30)
    ml_day: Optional[int] = Field(default=None, ge=1, le=32)
    ml_month: Optional[int] = Field(default=None, ge=1, le=12)
    ml_year: Optional[int] = None
    en_day: Optional[int] = Field(default=None, ge=1, le=31)
    en_month: Optional[int] = Field(default=None, ge=1, le=12)
    en_year: Optional[int] = None
    occurance: Optional[int] = None
    is_poornima: Optional[bool] = None
    last_occurance: Optional[bool] = None


class SanthigiriEventCreate(SanthigiriEventBase):
    id: str = Field(min_length=1, description="Unique event id, e.g. 'POURNAMI'.")


class SanthigiriEventUpdate(BaseModel):
    """Partial update — only the fields present in the body are changed."""

    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    sort_order: Optional[int] = None

    nakshatra_id: Optional[int] = Field(default=None, ge=1, le=27)
    thithi_id: Optional[int] = Field(default=None, ge=1, le=30)
    ml_day: Optional[int] = Field(default=None, ge=1, le=32)
    ml_month: Optional[int] = Field(default=None, ge=1, le=12)
    ml_year: Optional[int] = None
    en_day: Optional[int] = Field(default=None, ge=1, le=31)
    en_month: Optional[int] = Field(default=None, ge=1, le=12)
    en_year: Optional[int] = None
    occurance: Optional[int] = None
    is_poornima: Optional[bool] = None
    last_occurance: Optional[bool] = None


class SanthigiriEventDetail(SanthigiriEventBase):
    """Full event definition, including its matching condition."""

    model_config = ConfigDict(from_attributes=True)

    id: str


class SanthigiriEventOccurrences(BaseModel):
    """Result of (re)generating an event's occurrence dates for a year."""

    event_id: str
    year: int
    dates: List[date]
