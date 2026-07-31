"""
Request/response schemas for the Panchangam generation endpoint under
``/api/v1/panchangam/generate``.

``generate`` recomputes the full :class:`schemas.panchangam_data.PanchangamData`
(thithi, nakshatra, transitions, sunrise/sunset, kollavarsham, nazhika) for every
day in an inclusive date range from the astronomy code and overwrites the stored
rows. These models mirror ``schemas.kollavarsham`` — the request carries the
range (validated here) and the result summarizes what was written.

The endpoint streams one JSON object per line (NDJSON) as it works through the
range: a :class:`PanchangamGenerateProgress` line after each day, then a single
:class:`PanchangamGenerateResult` line once everything is written and the
affected years' ETags are refreshed — or a :class:`PanchangamGenerateError` line
if something fails partway through. Each line's ``type`` field discriminates
which of the three it is.
"""
from __future__ import annotations

from datetime import date
from typing import List, Literal

from pydantic import BaseModel, Field, model_validator

# A defensive, non-editable ceiling no admin setting can exceed — a DoS
# backstop, not the real business rule. The actual cap is the admin-configured
# `max_generate_span_days` setting (shared with schemas.kollavarsham),
# enforced by PanchangamGenerationService (see services/settings_service.py).
_HARD_SPAN_CEILING_DAYS = 3660


class PanchangamGenerateRequest(BaseModel):
    """Inclusive ``[start_date, end_date]`` range to (re)compute and overwrite."""

    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check_range(self) -> "PanchangamGenerateRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        span = (self.end_date - self.start_date).days + 1
        if span > _HARD_SPAN_CEILING_DAYS:
            raise ValueError(
                f"date range too large: {span} days (max {_HARD_SPAN_CEILING_DAYS})"
            )
        return self


class PanchangamGenerateResult(BaseModel):
    """Final line of the stream: summary of what was written."""

    type: Literal["complete"] = "complete"
    start_date: date
    end_date: date
    count: int = Field(description="Number of dates (re)computed and written.")
    years: List[int]


class PanchangamGenerateProgress(BaseModel):
    """One line of the stream, emitted after each day is computed and written."""

    type: Literal["progress"] = "progress"
    completed: int = Field(description="Dates written so far, including this one.")
    total: int
    percent: float
    current_date: date
    elapsed_seconds: float


class PanchangamGenerateError(BaseModel):
    """Emitted instead of the final result line if generation fails partway
    through. The DB write is rolled back (nothing commits until the very end),
    but the HTTP status is already 200 by this point since progress lines were
    already streamed — clients must check ``type`` on the last line rather than
    relying on the status code alone."""

    type: Literal["error"] = "error"
    detail: str
