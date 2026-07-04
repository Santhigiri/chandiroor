"""
KollavarshamService — orchestrates create/read/update of the editable
Kollavarsham (Malayalam-calendar) data attached to panchangam days, keeping the
affected ``/year`` ETags in lockstep.

Both mutations are **range-oriented**: they apply to every date in a request's
``[start_date, end_date]`` span (a single date being the degenerate range). Each
mutation is committed together with a recomputation of every spanned year's ETag
(via :func:`services.etag_service.refresh_etags`), all in one transaction, so
cached clients always revalidate.

A panchangam day is invalid without its Kollavarsham child (see ``db.repository``),
so this service is create/update only — there is no delete — and:

* ``create`` requires every targeted date to already have a panchangam day and to
  not yet have a Kollavarsham row (atomic: any violation aborts the whole call);
* ``update`` edits the existing Kollavarsham rows in the range and leaves dates
  without one untouched.

The route layer stays thin: it maps the domain errors raised here onto HTTP
status codes.
"""
from __future__ import annotations

from datetime import date
from typing import List, Sequence

from sqlmodel import Session

from db.kollavarsham_repository import KollavarshamRepository
from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from schemas.kollavarsham import KollavarshamCreate, KollavarshamUpdate
from services.etag_service import refresh_etags


class KollavarshamNotFound(Exception):
    """Raised when an update range contains no existing Kollavarsham rows."""


class KollavarshamAlreadyExists(Exception):
    """Raised when a create range hits a date that already has a Kollavarsham row.

    Carries the offending dates for the caller to surface.
    """

    def __init__(self, dates: Sequence[date]) -> None:
        self.dates = list(dates)
        super().__init__(f"Kollavarsham data already exists for: {self.dates}")


class NoPanchangamDay(Exception):
    """Raised when a create range hits a date with no panchangam day.

    Carries the offending dates for the caller to surface.
    """

    def __init__(self, dates: Sequence[date]) -> None:
        self.dates = list(dates)
        super().__init__(f"No panchangam day exists for: {self.dates}")


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

    def create(self, payload: KollavarshamCreate) -> List[KollavarshamDateRow]:
        dates = payload.dates()

        # Validate the whole range up front so the call is all-or-nothing.
        missing_parents = [d for d in dates if not self._repo.panchangam_exists(d)]
        if missing_parents:
            raise NoPanchangamDay(missing_parents)
        already = [d for d in dates if self._repo.exists(d)]
        if already:
            raise KollavarshamAlreadyExists(already)

        values = payload.values()
        rows = [
            self._repo.create(KollavarshamDateRow(date=d, **values)) for d in dates
        ]
        self._commit_with_etags(payload.years())
        return rows

    def update(self, payload: KollavarshamUpdate) -> List[KollavarshamDateRow]:
        changes = payload.changes()
        rows: List[KollavarshamDateRow] = []
        for d in payload.dates():
            row = self._repo.get(d)
            if row is None:
                continue  # leave gaps in the range untouched
            rows.append(self._repo.update(row, changes))

        if not rows:
            raise KollavarshamNotFound(
                f"No Kollavarsham data in range {payload.start_date}..{payload.end_date}"
            )

        self._commit_with_etags(sorted({r.date.year for r in rows}))
        return rows

    # ── Internal ─────────────────────────────────────────────────────────────────

    def _commit_with_etags(self, years: Sequence[int]) -> None:
        # refresh_etags recomputes the payloads from the (still pending) session
        # state and commits once, so the data change and its ETags land in a
        # single transaction. It refreshes every enum dataset plus the years
        # passed here (whose payloads embed these dates' kv values).
        refresh_etags(self._s, years)
