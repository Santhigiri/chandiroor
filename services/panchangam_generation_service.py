"""
PanchangamGenerationService — computes panchangam data for a date range from the
astronomy code and writes it to the DB, overwriting any existing rows, while
keeping the affected years' ETags in lockstep.

The full :class:`schemas.panchangam_data.PanchangamData` for each day (thithi,
nakshatra, transitions, sunrise/sunset, kollavarsham, nazhika) is embedded in the
compact ``/year`` payload, so every write commits together with a recomputation
of the affected years' ETags via :func:`services.etag_service.refresh_etags` —
exactly as :class:`services.kollavarsham_service.KollavarshamService` and
:class:`services.santhigiri_event_service.SanthigiriEventService` do — so cached
clients revalidate correctly.

This is a dedicated write-path service (constructed from a ``Session``) kept
separate from the read-only :class:`services.panchangam_service.PanchangamService`
(which is built from a repository alone and has no ETag awareness).

Note on Santhigiri events: :func:`core.calendar.panchangam.get_panchangam_data`
returns an **empty** ``santhigiri_significant_dates``, and
``PanchangamRepository.upsert`` only rewrites the (date-keyed, location-independent)
event rows when that list is non-empty. So regenerating a date **preserves** its
existing shared ashram events rather than wiping them — event dates still come
from the offline cache pipeline, matching the current architecture.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlmodel import Session

from db.repository import PanchangamRepository
from schemas.panchangam_generation import (
    PanchangamGenerateRequest,
    PanchangamGenerateResult,
)
from services.etag_service import refresh_etags
from utils.location import DEFAULT_LOCATION, Location


class PanchangamGenerationService:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = PanchangamRepository(session)

    def generate(
        self,
        req: PanchangamGenerateRequest,
        location: Location = DEFAULT_LOCATION,
    ) -> PanchangamGenerateResult:
        span = (req.end_date - req.start_date).days + 1
        dates = [req.start_date + timedelta(days=offset) for offset in range(span)]

        # Imported lazily: pulls in the Skyfield/ephemeris stack only when a
        # generate actually runs, keeping app startup free of it.
        from core.calendar.panchangam import get_panchangam_data

        for day in dates:
            data = get_panchangam_data(
                day,
                location.latitude,
                location.longitude,
                location.timezone,
            )
            self._repo.upsert(data, location)  # overwrites; does NOT commit

        years = sorted({d.year for d in dates})
        refresh_etags(self._s, years, [location])  # recompute ETags + commit

        return PanchangamGenerateResult(
            start_date=req.start_date,
            end_date=req.end_date,
            count=len(dates),
            years=years,
        )
