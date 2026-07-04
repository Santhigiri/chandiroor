"""
Request/response schemas for the editable Kollavarsham (Malayalam-calendar) data
of a panchangam day.

These back the admin write endpoints under ``/api/v1/panchangam/kollavarsham``
(create, update, delete). They mirror the columns of
``db.models.kollavarsham_date`` — the flat ``kv_day`` / ``kv_month`` / ``kv_year``
shape stored per date — while the detail response additionally resolves the
month id to its bilingual name (the same enrichment the read paths perform via
``MalayalamMasa``).

``kv_month`` is the ``malayalam_masa`` id (1–12), the same id used by the
``/panchangam/masa`` reference endpoint.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from utils.malayalam_masa import MalayalamMasa


class KollavarshamBase(BaseModel):
    kv_day: int = Field(ge=1, le=32, description="Day of the Malayalam month.")
    kv_month: int = Field(ge=1, le=12, description="MalayalamMasa id (1–12).")
    kv_year: int = Field(description="Kollam Era year.")


class KollavarshamCreate(KollavarshamBase):
    date: _date = Field(
        description="Gregorian date this Kollavarsham record describes; a "
        "panchangam day must already exist for it."
    )


class KollavarshamUpdate(BaseModel):
    """Partial update — only the fields present in the body are changed."""

    kv_day: Optional[int] = Field(default=None, ge=1, le=32)
    kv_month: Optional[int] = Field(default=None, ge=1, le=12)
    kv_year: Optional[int] = None


class KollavarshamDetail(KollavarshamBase):
    """Full Kollavarsham record, including the resolved month names."""

    model_config = ConfigDict(from_attributes=True)

    date: _date
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
