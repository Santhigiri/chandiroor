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
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Guard against an accidental huge range triggering an enormous number of
# per-event/per-year computations (some of which run live Pournami checks) in
# one request. Generously covers the seeded 2021-2030 range plus headroom.
# Shared by both the single-event and all-events occurrence generation
# endpoints — see SanthigiriEventsGenerateRequest below.
MAX_EVENT_GENERATE_YEAR_SPAN = 15


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

    yields_to_event_id: Optional[str] = Field(
        default=None,
        description=(
            "Id of another event this one yields precedence to: on any date "
            "where that event's own condition also matches, this event's "
            "occurrence is dropped for that date."
        ),
    )


class SanthigiriEventCreate(SanthigiriEventBase):
    id: str = Field(min_length=1, description="Unique event id, e.g. 'POURNAMI'.")

    @model_validator(mode="after")
    def _no_self_yield(self) -> "SanthigiriEventCreate":
        if self.yields_to_event_id is not None and self.yields_to_event_id == self.id:
            raise ValueError("yields_to_event_id cannot reference the event's own id")
        return self


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
    yields_to_event_id: Optional[str] = None


class SanthigiriEventDetail(SanthigiriEventBase):
    """Full event definition, including its matching condition."""

    model_config = ConfigDict(from_attributes=True)

    id: str


# ── Year-range request, shared by the single-event and all-events occurrence
# generation endpoints ────────────────────────────────────────────────────────

class SanthigiriEventsGenerateRequest(BaseModel):
    """Inclusive ``[start_year, end_year]`` range to (re)generate occurrences for."""

    start_year: int = Field(ge=2000, le=2100)
    end_year: int = Field(ge=2000, le=2100)

    @model_validator(mode="after")
    def _check_range(self) -> "SanthigiriEventsGenerateRequest":
        if self.end_year < self.start_year:
            raise ValueError("end_year must be on or after start_year")
        span = self.end_year - self.start_year + 1
        if span > MAX_EVENT_GENERATE_YEAR_SPAN:
            raise ValueError(
                f"year range too large: {span} years (max {MAX_EVENT_GENERATE_YEAR_SPAN})"
            )
        return self


class SanthigiriEventOccurrences(BaseModel):
    """Result of (re)generating one event's occurrence dates across a year range.

    ``occurrences`` maps each year in ``[start_year, end_year]`` to the dates
    written for it that year.
    """

    event_id: str
    start_year: int
    end_year: int
    occurrences: Dict[int, List[date]]


# ── Bulk (all-events) occurrence generation, streamed as NDJSON ──────────────
#
# ``POST /panchangam/events/generate`` regenerates every event definition's
# occurrences across an inclusive ``[start_year, end_year]`` range. Unlike the
# single-event endpoint above, this can take a while (one event may scan all
# 365 days per year, some with live Pournami checks), so the response streams
# one JSON object per line: a :class:`SanthigiriEventsGenerateProgress` line
# after each (year, event) pair, then a final
# :class:`SanthigiriEventsGenerateResult` line — or a
# :class:`SanthigiriEventsGenerateError` line if the whole run fails before
# any event-level result could be produced (e.g. a year in the range isn't
# fully seeded). Each line's ``type`` field discriminates which of the three
# it is. The whole range is one atomic write: nothing commits until every
# year has been processed, so a failure partway through — including on a
# later year — leaves the DB untouched.

class SanthigiriEventsGenerateProgress(BaseModel):
    """One line of the stream, emitted after each (year, event) pair is (re)computed."""

    type: Literal["progress"] = "progress"
    year: int
    event_id: str
    name: str
    status: Literal["generated", "skipped", "error"]
    count: int = Field(description="Occurrence dates written for this event/year; 0 if skipped/error.")
    detail: Optional[str] = Field(
        default=None,
        description="Why the event was skipped or errored; absent when status is 'generated'.",
    )
    completed: int = Field(description="(year, event) pairs processed so far, including this one.")
    total: int
    percent: float
    elapsed_seconds: float


class SanthigiriEventsGenerateResult(BaseModel):
    """Final line of the stream: summary across every year and event definition."""

    type: Literal["complete"] = "complete"
    start_year: int
    end_year: int
    years: List[int]
    total_events: int = Field(description="Total (year, event) pairs processed across the range.")
    generated: int
    skipped: int
    errors: int


class SanthigiriEventsGenerateError(BaseModel):
    """Emitted instead of the final result line if the run fails before
    producing any per-event result (e.g. a year in the range has incomplete
    data). The HTTP status is already 200 by this point if any progress lines
    were streamed — clients must check ``type`` on the last line rather than
    relying on the status code alone."""

    type: Literal["error"] = "error"
    detail: str


# ── Single-event occurrence generation, streamed as NDJSON ───────────────────
#
# ``POST /panchangam/events/{event_id}/occurrences/stream`` is the streaming
# sibling of ``POST /panchangam/events/{event_id}/occurrences``: same
# ``[start_year, end_year]`` range, same event, but a wide range can scan a
# lot of days (occasionally with live Pournami checks), so the response
# streams one JSON object per line: a :class:`SanthigiriEventGenerateProgress`
# line after each year is (re)computed, then a final
# :class:`SanthigiriEventGenerateResult` line — or a
# :class:`SanthigiriEventsGenerateError` line (shared with the all-events
# stream) if the run fails before any year completes. As with the all-events
# stream, the whole range is one atomic write: nothing commits until every
# year has been processed.

class SanthigiriEventGenerateProgress(BaseModel):
    """One line of the stream, emitted after each year is (re)computed."""

    type: Literal["progress"] = "progress"
    year: int
    count: int = Field(description="Occurrence dates written for this year.")
    completed: int = Field(description="Years processed so far, including this one.")
    total: int
    percent: float
    elapsed_seconds: float


class SanthigiriEventGenerateResult(BaseModel):
    """Final line of the stream: summary across every year in the range."""

    type: Literal["complete"] = "complete"
    event_id: str
    start_year: int
    end_year: int
    occurrences: Dict[int, List[date]]
