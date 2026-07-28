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

import datetime
from typing import Iterable, List

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from core.calendar.santhigiri_event_occurrences import (
    OccurrenceComputationError,
    UnsupportedEventCondition as UnsupportedOccurrenceCondition,
    compute_occurrences,
)
from db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from db.repository import PanchangamRepository, event_row_to_event
from db.santhigiri_event_repository import SanthigiriEventRepository
from schemas.santhigiri_event import SanthigiriEventCreate, SanthigiriEventUpdate
from services.etag_service import refresh_etags
from utils.location import DEFAULT_LOCATION


class EventAlreadyExists(Exception):
    """Raised when creating an event whose id is already taken."""


class EventNotFound(Exception):
    """Raised when updating/deleting/reading an event id that does not exist."""


class InvalidEventReference(Exception):
    """Raised when a condition foreign key (e.g. nakshatra_id) does not resolve."""


class IncompleteYearData(Exception):
    """Raised when *year* is not fully present in the DB, so occurrences
    (especially last-occurrence/transition-series ones) cannot be safely
    computed."""


# OccurrenceComputationError is imported directly above and re-exported as-is;
# UnsupportedEventCondition is aliased on import so callers only need this module.
UnsupportedEventCondition = UnsupportedOccurrenceCondition


class SanthigiriEventService:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = SanthigiriEventRepository(session)
        self._panchangam_repo = PanchangamRepository(session)

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

    def generate_occurrences(self, event_id: str, year: int) -> List[datetime.date]:
        """(Re)compute *event_id*'s occurrence dates for *year* and replace
        whatever was previously stored for that event/year.

        Raises :class:`IncompleteYearData` if the panchangam data for *year*
        is not fully present in the DB, :class:`UnsupportedEventCondition` if
        the event's condition cannot be resolved to a set of days, and
        :class:`OccurrenceComputationError` if a resolvable condition still
        has no computable occurrence in *year*.
        """
        row = self.get(event_id)
        condition = event_row_to_event(row).event_condition

        start = datetime.date(year, 1, 1)
        end = datetime.date(year, 12, 31)
        yearly_data = self._panchangam_repo.get_by_date_range(
            start, end, DEFAULT_LOCATION
        )
        expected_days = (end - start).days + 1
        if len(yearly_data) != expected_days:
            raise IncompleteYearData(year)

        occurrences = compute_occurrences(condition, yearly_data, year)

        self._panchangam_repo.set_event_occurrences_for_year(
            event_id, year, occurrences
        )
        self._commit_with_etags([year])
        return occurrences

    # ── Internal ─────────────────────────────────────────────────────────────────

    def _commit_with_etags(self, years: Iterable[int]) -> None:
        # refresh_etags recomputes the payloads from the (still pending) session
        # state and commits once, so the data change and its ETags land in a
        # single transaction. It always refreshes every enum dataset — including
        # ``events`` — and any years passed here.
        refresh_etags(self._s, years)
