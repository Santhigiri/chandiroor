"""
PanchangamAdminService — admin write path for a single day's Panchangam data.

The read path (``PanchangamService``) never writes: a date missing from the DB is
computed live but not persisted, so a real gap or a wrong value can only be fixed
by re-applying the offline SQL seed. This service closes that loop for admins:

* :meth:`generate` computes a day astronomically (the same call the read path's
  live fallback makes) and persists it, overwriting any existing row.
* :meth:`edit` overrides the core values (thithi, nakshatra, nazhika,
  sunrise/sunset) of a day already in the DB.

Both mutations mirror ``SanthigiriEventService``: write via ``PanchangamRepository``
(which does not commit) then funnel through a single
:func:`services.etag_service.refresh_etags`, so the data change and the affected
``year:<code>:<year>`` ETag land in one transaction and cached clients revalidate.
The route layer stays thin: it maps :class:`PanchangamDayNotFound` onto a 404.
"""
from __future__ import annotations

from datetime import date

from sqlmodel import Session

from core.calendar.panchangam import get_panchangam_data
from db.repository import PanchangamRepository
from schemas.panchangam_data import PanchangamData
from schemas.panchangam_edit import PanchangamDayUpdate
from services.etag_service import refresh_etags
from utils.location import Location
from utils.nakshatra import Nakshatra
from utils.thithi import Thithi


class PanchangamDayNotFound(Exception):
    """Raised when editing a (date, location) that is not in the DB."""

    def __init__(self, day: date, location: Location) -> None:
        super().__init__(f"No panchangam for {day.isoformat()} at {location.code!r}")
        self.day = day
        self.location = location


class PanchangamAdminService:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = PanchangamRepository(session)

    def generate(self, day: date, location: Location) -> PanchangamData:
        """Compute *day* for *location* astronomically and persist it (overwrite)."""
        data = get_panchangam_data(
            day, location.latitude, location.longitude, location.timezone
        )
        self._repo.upsert(data, location)
        self._commit_with_etags(day, location)
        return data

    def edit(
        self, day: date, location: Location, payload: PanchangamDayUpdate
    ) -> PanchangamData:
        """Override the core values of an existing (date, location) row."""
        existing = self._repo.get_by_date(day, location)
        if existing is None:
            raise PanchangamDayNotFound(day, location)

        changes = payload.model_dump(exclude_unset=True)
        if "thithi_id" in changes:
            changes["thithi"] = Thithi.from_id(changes.pop("thithi_id"))
        if "nakshatra_id" in changes:
            changes["nakshatra"] = Nakshatra.from_id(changes.pop("nakshatra_id"))

        updated = existing.model_copy(update=changes)
        self._repo.upsert(updated, location)
        self._commit_with_etags(day, location)
        return updated

    def _commit_with_etags(self, day: date, location: Location) -> None:
        # refresh_etags recomputes the affected year's payload from the (still
        # pending) session state and commits once, so the upserted rows and the
        # year:<code>:<year> ETag land in a single transaction. Scope to this
        # location so we don't recompute every location's whole year.
        refresh_etags(self._s, [day.year], [location])
