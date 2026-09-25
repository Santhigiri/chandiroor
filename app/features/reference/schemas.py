"""
Response schemas for the v2 reference-data endpoints (``features/reference/router_v2.py``).

HTTP-boundary Pydantic shapes, distinct from ``core/ports/reference_repository.py``'s
frozen-dataclass DTOs (``ReferenceItemGet``/``ThithiItemGet``/``ReferenceTranslation``)
that the repository/port speak — same split kumily draws between its ``ports.py``
DTOs and a feature's ``schemas.py``. ``language_code`` is typed as ``LanguageCode``
only here (the HTTP boundary); everywhere below it stays a plain ``str``.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.utils.languages import LanguageCode


class ReferenceTranslationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    language_code: LanguageCode
    text: str


class ReferenceItemSchema(BaseModel):
    """nakshatra / masa / chandra_masa / paksha — structurally identical."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    translations: List[ReferenceTranslationSchema]


class ThithiItemSchema(BaseModel):
    """thithi alone needs ``day`` and a nested paksha."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    day: int
    paksha: Optional[ReferenceItemSchema]
    translations: List[ReferenceTranslationSchema]
