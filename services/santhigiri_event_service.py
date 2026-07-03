"""
SanthigiriEventService — orchestrates create/read/update/delete of the editable
Santhigiri event definitions and keeps the affected dataset ETags in lockstep.

Every mutation is committed together with a recomputation of the affected ETags
(via :func:`services.etag_service.refresh_etags`), so a cached client always
revalidates correctly:

* the ``events`` reference dataset changes on every create/update/delete;
* a delete additionally cascades to ``santhigiri_event_dates``, changing the
  ``/year`` payload for each year the event used to fall on — those years' ETags
  are refreshed too.

The route layer stays thin: it maps the domain errors raised here onto HTTP
status codes.
"""
from __future__ import annotations

from typing import Iterable

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from db.santhigiri_event_repository import SanthigiriEventRepository
from schemas.santhigiri_event import SanthigiriEventCreate, SanthigiriEventUpdate
from services.etag_service import refresh_etags


class EventAlreadyExists(Exception):
    """Raised when creating an event whose id is already taken."""


class EventNotFound(Exception):
    """Raised when updating/deleting/reading an event id that does not exist."""


class InvalidEventReference(Exception):
    """Raised when a condition foreign key (e.g. nakshatra_id) does not resolve."""


class SanthigiriEventService:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = SanthigiriEventRepository(session)

    # ── Read ────────────────────────────────────────────────────────────────────

    def get(self, event_id: str) -> SanthigiriEventRow:
        row = self._repo.get(event_id)
        if row is None:
            raise EventNotFound(event_id)
        return row

    # ── Write ───────────────────────────────────────────────────────────────────

    def create(self, payload: SanthigiriEventCreate) -> SanthigiriEventRow:
        if self._repo.exists(payload.id):
            raise EventAlreadyExists(payload.id)
        row = SanthigiriEventRow(**payload.model_dump())
        try:
            self._repo.create(row)
            self._commit_with_etags([])
        except IntegrityError as exc:
            self._s.rollback()
            raise InvalidEventReference(str(exc.orig)) from exc
        return row

    def update(self, event_id: str, payload: SanthigiriEventUpdate) -> SanthigiriEventRow:
        row = self.get(event_id)
        changes = payload.model_dump(exclude_unset=True)
        try:
            self._repo.update(row, changes)
            self._commit_with_etags([])
        except IntegrityError as exc:
            self._s.rollback()
            raise InvalidEventReference(str(exc.orig)) from exc
        return row

    def delete(self, event_id: str) -> None:
        row = self.get(event_id)
        affected_years = self._repo.delete(row)
        self._commit_with_etags(affected_years)

    # ── Internal ─────────────────────────────────────────────────────────────────

    def _commit_with_etags(self, years: Iterable[int]) -> None:
        # refresh_etags recomputes the payloads from the (still pending) session
        # state and commits once, so the data change and its ETags land in a
        # single transaction. It always refreshes every enum dataset — including
        # ``events`` — and any years passed here.
        refresh_etags(self._s, years)
