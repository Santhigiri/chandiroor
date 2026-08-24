"""
KollavarshamService — orchestrates (re)generation and manual override of the
editable ``kollavarsham_date`` table, keeping the affected years' ETags in
lockstep.

Kollavarsham values (``kv_day``/``kv_year``/``masa``) are part of the compact
``/year`` payload (see ``schemas.compact_panchangam_data.CompactKollavarshamDate``),
so every mutation commits together with a recomputation of the affected years'
ETags via :func:`services.etag_service.refresh_etags` — exactly as
:class:`features.santhigiri_events.service.SanthigiriEventService` does — so
cached clients revalidate correctly.

* **generate** recomputes every day in an inclusive date range from the astronomy
  code (:func:`core.calendar.kollavarsham.get_kollavarsham_date`) and overwrites
  the rows. The whole range is validated first: if any date lacks a
  ``panchangam`` row (the FK target) the request is rejected and nothing is
  written.
* **update** applies a partial manual override to a single date's row.

The route layer stays thin: it maps the domain errors raised here onto HTTP
status codes.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import List

from sqlmodel import Session

from app.db.kollavarsham_repository import KollavarshamRepository
from app.db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from app.features.kollavarsham.schemas import (
    KollavarshamDateUpdate,
    KollavarshamGenerateRequest,
    KollavarshamGenerateResult,
)
from app.services.etag_service import refresh_etags
from app.services.settings_service import SettingsService
from app.utils.location import DEFAULT_LOCATION, Location


class KollavarshamDateNotFound(Exception):
    """Raised when updating/reading a date with no Kollavarsham row."""


class UngeneratableDates(Exception):
    """Raised when a generate range includes dates with no ``panchangam`` row.

    Carries the offending dates so the route can list them in the 400 response.
    """

    def __init__(self, dates: List[date]) -> None:
        self.dates = dates
        super().__init__(
            "no panchangam row for: " + ", ".join(d.isoformat() for d in dates)
        )


class SpanTooLarge(Exception):
    """Raised when a generate request's date span exceeds the admin-configured
    ``max_generate_span_days`` setting (shared with panchangam generation)."""

    def __init__(self, span: int, max_days: int) -> None:
        self.span = span
        self.max_days = max_days
        super().__init__(f"date range too large: {span} days (max {max_days})")


class KollavarshamService:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = KollavarshamRepository(session)
        self._settings = SettingsService(session)

    # ── Read ────────────────────────────────────────────────────────────────────

    def get(
        self, day: date, location: Location = DEFAULT_LOCATION
    ) -> KollavarshamDateRow:
        row = self._repo.get(day, location)
        if row is None:
            raise KollavarshamDateNotFound(day)
        return row

    # ── Write ───────────────────────────────────────────────────────────────────

    def generate(
        self,
        req: KollavarshamGenerateRequest,
        location: Location = DEFAULT_LOCATION,
    ) -> KollavarshamGenerateResult:
        span = (req.end_date - req.start_date).days + 1
        max_days = self._settings.get_max_generate_span_days()
        if span > max_days:
            raise SpanTooLarge(span, max_days)
        dates = [req.start_date + timedelta(days=offset) for offset in range(span)]

        missing = self._repo.missing_panchangam_dates(dates, location)
        if missing:
            raise UngeneratableDates(missing)

        # Imported lazily: pulls in the Skyfield/ephemeris stack only when a
        # generate actually runs, keeping app startup free of it.
        from core.calendar.kollavarsham import get_kollavarsham_date

        for day in dates:
            tuning = self._settings.get_astronomy_tuning(day.year)
            kv = get_kollavarsham_date(
                dt=day,
                latitude=location.latitude,
                longitude=location.longitude,
                timezone=location.timezone,
                epsilon=tuning.kollavarsham_epsilon,
            )
            self._repo.upsert(day, location, kv.kv_day, kv.kv_month, kv.kv_year)

        years = sorted({d.year for d in dates})
        refresh_etags(self._s, years, [location])  # commits

        return KollavarshamGenerateResult(
            start_date=req.start_date,
            end_date=req.end_date,
            count=len(dates),
            years=years,
        )

    def update(
        self,
        day: date,
        payload: KollavarshamDateUpdate,
        location: Location = DEFAULT_LOCATION,
    ) -> KollavarshamDateRow:
        row = self.get(day, location)
        changes = payload.model_dump(exclude_unset=True)
        self._repo.update(row, changes)
        refresh_etags(self._s, [day.year], [location])  # commits
        return row
