"""
KollavarshamService — orchestrates create/read/update/delete of the editable
Kollavarsham (Malayalam-calendar) data attached to each panchangam day, keeping
the affected ``/year`` ETag in lockstep.

Kollavarsham values appear in every panchangam payload (day / month / year), so
each mutation is committed together with a recomputation of the affected year's
ETag (via :func:`services.etag_service.refresh_etags`) so cached clients always
revalidate correctly.

A panchangam day is invalid without its Kollavarsham child (see
``db.repository``), so this service never orphans a day:

* ``create`` requires the parent panchangam day to already exist;
* ``delete`` removes the whole panchangam day (its children cascade), after
  which the date falls back to live computation.

The route layer stays thin: it maps the domain errors raised here onto HTTP
status codes.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from db.kollavarsham_repository import KollavarshamRepository
from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from schemas.kollavarsham import KollavarshamCreate, KollavarshamUpdate
from services.etag_service import refresh_etags


class KollavarshamNotFound(Exception):
    """Raised when updating/deleting/reading a date that has no Kollavarsham row."""


class KollavarshamAlreadyExists(Exception):
    """Raised when creating a Kollavarsham row for a date that already has one."""


class NoPanchangamDay(Exception):
    """Raised when creating Kollavarsham data for a date with no panchangam day."""


class KollavarshamService:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = KollavarshamRepository(session)

    # ── Read ────────────────────────────────────────────────────────────────────

    def get(self, dt: date) -> KollavarshamDateRow:
        row = self._repo.get(dt)
        if row is None:
            raise KollavarshamNotFound(dt)
        return row

    # ── Write ───────────────────────────────────────────────────────────────────

    def create(self, payload: KollavarshamCreate) -> KollavarshamDateRow:
        if self._repo.exists(payload.date):
            raise KollavarshamAlreadyExists(payload.date)
        if not self._repo.panchangam_exists(payload.date):
            raise NoPanchangamDay(payload.date)
        row = KollavarshamDateRow(**payload.model_dump())
        try:
            self._repo.create(row)
            self._commit_with_etags(payload.date.year)
        except IntegrityError as exc:
            self._s.rollback()
            raise NoPanchangamDay(str(exc.orig)) from exc
        return row

    def update(self, dt: date, payload: KollavarshamUpdate) -> KollavarshamDateRow:
        row = self.get(dt)
        changes = payload.model_dump(exclude_unset=True)
        self._repo.update(row, changes)
        self._commit_with_etags(dt.year)
        return row

    def delete(self, dt: date) -> None:
        # Presence of the Kollavarsham row gates the delete; removing it means
        # removing the whole (now-invalid) panchangam day, which cascades.
        self.get(dt)
        self._repo.delete_day(dt)
        self._commit_with_etags(dt.year)

    # ── Internal ─────────────────────────────────────────────────────────────────

    def _commit_with_etags(self, year: int) -> None:
        # refresh_etags recomputes the payloads from the (still pending) session
        # state and commits once, so the data change and its ETags land in a
        # single transaction. It always refreshes every enum dataset plus the
        # year passed here (the year whose payload embeds this date's kv values).
        refresh_etags(self._s, [year])
