"""Request/response schemas for the editable Guruvani quotes.

Back the endpoints under ``/api/v1/guruvani``. Reads are public; writes
require the ``admin`` role (see ``features/guruvani/router.py``).
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GuruvaniBase(BaseModel):
    text_en: str = Field(min_length=1)
    text_ml: str = Field(min_length=1)
    sort_order: Optional[int] = Field(
        default=None,
        description="Display order; assigned automatically when omitted on create.",
    )


class GuruvaniCreate(GuruvaniBase):
    pass


class GuruvaniUpdate(BaseModel):
    """Partial update — only the fields present in the body are changed."""

    text_en: Optional[str] = Field(default=None, min_length=1)
    text_ml: Optional[str] = Field(default=None, min_length=1)
    sort_order: Optional[int] = None


class GuruvaniDetail(GuruvaniBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
