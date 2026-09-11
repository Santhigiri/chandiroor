"""
PanchangamRepositoryPort — what ``PanchangamService``/``PanchangamGenerationService``
need from persistence, without depending on the concrete Postgres adapter.

Unlike ``AuthRepositoryPort``/``SanthigiriEventsRepositoryPort``, this port has no
DTOs of its own: ``PanchangamData`` (``schemas/panchangam_data.py``) and
``SanthigiriEvent`` (``utils/santhigiri_events.py``) are already plain,
framework-independent domain objects — not SQLModel rows — so they serve directly
as the boundary contract instead of being duplicated into new dataclasses. Nothing
here imports SQLModel or a ``Session``.
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, List, Optional, Protocol

from app.schemas.panchangam_data import PanchangamData
from app.utils.location import Location
from app.utils.santhigiri_events import SanthigiriEvent


class PanchangamRepositoryPort(Protocol):
    def get_by_date(
        self, date: date, location: Location
    ) -> Optional[PanchangamData]: ...

    def get_by_date_range(
        self, start: date, end: date, location: Location
    ) -> Dict[date, PanchangamData]: ...

    def get_by_month(
        self, year: int, month: int, location: Location
    ) -> Dict[date, PanchangamData]: ...

    def list_event_definitions(self) -> List[SanthigiriEvent]: ...

    def upsert(self, data: PanchangamData, location: Location) -> None: ...

    def upsert_many(
        self, data: Iterable[PanchangamData], location: Location
    ) -> None: ...

    def set_event_occurrences_for_year(
        self, event_id: str, year: int, dates: Iterable[date]
    ) -> None: ...
