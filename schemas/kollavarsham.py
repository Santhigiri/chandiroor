"""
Request/response schemas for the editable Kollavarsham (Malayalam-calendar) data
of a panchangam day.

These back the admin write endpoints under ``/api/v1/panchangam/kollavarsham``
(create, update). Both endpoints are **range-oriented**: a request carries a
``start_date`` and an optional ``end_date`` and applies its values to every date
in the inclusive ``[start_date, end_date]`` span. Omit ``end_date`` to target a
single day. The range is capped at :data:`MAX_RANGE_DAYS` days so a bulk write
never triggers an unbounded ETag rebuild.

``kv_month`` is the ``malayalam_masa`` id (1–12), the same id used by the
``/panchangam/masa`` reference endpoint. The detail response additionally
resolves that id to its bilingual month name.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import timedelta
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from utils.malayalam_masa import MalayalamMasa

# Upper bound on how many dates one create/update call may touch. Bounds the work
# of the per-year ETag rebuilds each mutation triggers.
MAX_RANGE_DAYS = 366

# The editable value columns of a Kollavarsham row.
_KV_FIELDS = ("kv_day", "kv_month", "kv_year")


class _DateRange(BaseModel):
    """A ``[start_date, end_date]`` inclusive span; ``end_date`` defaults to start."""

    start_date: _date = Field(description="First date the values apply to.")
    end_date: Optional[_date] = Field(
        default=None,
        description="Last date (inclusive); defaults to start_date for a single day.",
    )

    @model_validator(mode="after")
    def _validate_range(self) -> "_DateRange":
        if self.end_date is None:
            self.end_date = self.start_date
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.span_days > MAX_RANGE_DAYS:
            raise ValueError(f"date range must not exceed {MAX_RANGE_DAYS} days")
        return self

    @property
    def span_days(self) -> int:
        assert self.end_date is not None  # set in _validate_range
        return (self.end_date - self.start_date).days + 1

    def dates(self) -> List[_date]:
        """Every date in the inclusive range, ascending."""
        return [self.start_date + timedelta(days=i) for i in range(self.span_days)]

    def years(self) -> List[int]:
        """Distinct calendar years the range spans (for ETag refresh)."""
        return sorted({d.year for d in self.dates()})


class KollavarshamCreate(_DateRange):
    """Create a Kollavarsham record for every date in the range, with these values."""

    kv_day: int = Field(ge=1, le=32, description="Day of the Malayalam month.")
    kv_month: int = Field(ge=1, le=12, description="MalayalamMasa id (1–12).")
    kv_year: int = Field(description="Kollam Era year.")

    def values(self) -> dict:
        return {f: getattr(self, f) for f in _KV_FIELDS}


class KollavarshamUpdate(_DateRange):
    """Partial-update every existing Kollavarsham record in the range.

    Only the value fields present in the body are changed; at least one is
    required. Dates in the range without a record are left untouched.
    """

    kv_day: Optional[int] = Field(default=None, ge=1, le=32)
    kv_month: Optional[int] = Field(default=None, ge=1, le=12)
    kv_year: Optional[int] = None

    @model_validator(mode="after")
    def _require_a_change(self) -> "KollavarshamUpdate":
        if not self.changes():
            raise ValueError(
                "at least one of kv_day, kv_month, kv_year must be provided"
            )
        return self

    def changes(self) -> dict:
        """The value fields explicitly set in the request (column → value)."""
        provided = self.model_dump(exclude_unset=True)
        return {f: provided[f] for f in _KV_FIELDS if f in provided}


class KollavarshamDetail(BaseModel):
    """A single Kollavarsham record, with the month id resolved to its names."""

    model_config = ConfigDict(from_attributes=True)

    date: _date
    kv_day: int
    kv_month: int
    kv_year: int
    kv_month_name_en: str
    kv_month_name_ml: str

    @classmethod
    def from_row(cls, row) -> "KollavarshamDetail":
        """Build the response from a ``KollavarshamDate`` ORM row, resolving names."""
        masa = MalayalamMasa.from_id(row.kv_month)
        return cls(
            date=row.date,
            kv_day=row.kv_day,
            kv_month=row.kv_month,
            kv_year=row.kv_year,
            kv_month_name_en=masa.en,
            kv_month_name_ml=masa.ml,
        )
