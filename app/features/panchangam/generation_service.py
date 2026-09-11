"""
PanchangamGenerationService — computes panchangam data for a date range from the
astronomy code and writes it to the DB, overwriting any existing rows, while
keeping the affected years' ETags in lockstep.

The full :class:`schemas.panchangam_data.PanchangamData` for each day (thithi,
nakshatra, transitions, sunrise/sunset, kollavarsham, nazhika) is embedded in the
compact ``/year`` payload, so every write commits together with a recomputation
of the affected years' ETags via :func:`features.etag.service.refresh_etags` —
exactly as :class:`features.santhigiri_events.service.SanthigiriEventService` does — so cached
clients revalidate correctly. Nothing commits until that single call at the end,
so the whole range is still one atomic transaction — ``generate_streaming``
yielding progress after each day is purely a visibility improvement, it does not
change when the write becomes durable.

This is a dedicated write-path service (a frozen dataclass built from the
``PanchangamRepositoryPort``, ``SettingsServicePort``, ``EtagRepositoryPort``,
``PanchangamServicePort`` (a settings-free binding — see
``core/ports/panchangam_service.py``), ``ReferenceRepositoryPort`` (that
``refresh_etags`` needs to build enum payloads — see
``core/ports/reference_repository.py``), and ``UnitOfWork`` ports) kept
separate from the read-only
:class:`features.panchangam.service.PanchangamService` (which is built from a
repository alone and has no ETag awareness).

Note on Santhigiri events: :func:`core.calendar.panchangam.get_panchangam_data`
returns an **empty** ``santhigiri_significant_dates``, and
``PanchangamRepository.upsert`` only rewrites the (date-keyed, location-independent)
event rows when that list is non-empty. So regenerating a date **preserves** its
existing shared ashram events rather than wiping them — event dates still come
from the offline cache pipeline, matching the current architecture.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from time import perf_counter
from typing import AsyncIterator, Union

from starlette.concurrency import run_in_threadpool

from app.core.ports.panchangam_service import PanchangamServicePort
from app.core.ports.reference_repository import ReferenceRepositoryPort
from app.core.ports.settings_service import SettingsServicePort
from app.core.ports.unit_of_work import UnitOfWork
from app.features.etag.ports import EtagRepositoryPort
from app.features.panchangam.ports import PanchangamRepositoryPort
from app.features.panchangam.schemas.panchangam_generation import (
    PanchangamGenerateProgress,
    PanchangamGenerateRequest,
    PanchangamGenerateResult,
)
from app.features.etag.service import refresh_etags
from app.utils.location import DEFAULT_LOCATION, Location


class SpanTooLarge(Exception):
    """Raised when a generate request's date span exceeds the admin-configured
    ``max_generate_span_days`` setting."""

    def __init__(self, span: int, max_days: int) -> None:
        self.span = span
        self.max_days = max_days
        super().__init__(f"date range too large: {span} days (max {max_days})")


@dataclass(frozen=True)
class PanchangamGenerationService:
    reference_repository: ReferenceRepositoryPort
    repository: PanchangamRepositoryPort
    settings: SettingsServicePort
    etag_repository: EtagRepositoryPort
    panchangam_service_for_etag_refresh: PanchangamServicePort
    unit_of_work: UnitOfWork

    def validate_span(self, req: PanchangamGenerateRequest) -> None:
        """Raise :class:`SpanTooLarge` if *req*'s span exceeds the
        admin-configured cap. Synchronous and side-effect-free, so route
        handlers can call it before opening a streaming response — the only
        way a caller of the streaming ``/generate`` endpoint can get a real
        422 instead of a 200 + NDJSON error line (see
        :meth:`generate_streaming`, which also enforces this as defense in
        depth for any other caller)."""
        span = (req.end_date - req.start_date).days + 1
        max_days = self.settings.get_max_generate_span_days()
        if span > max_days:
            raise SpanTooLarge(span, max_days)

    async def generate_streaming(
        self,
        req: PanchangamGenerateRequest,
        location: Location = DEFAULT_LOCATION,
    ) -> AsyncIterator[Union[PanchangamGenerateProgress, PanchangamGenerateResult]]:
        """Yield a :class:`PanchangamGenerateProgress` after each day is
        computed and written, then a final :class:`PanchangamGenerateResult`.

        Each day's Skyfield-backed computation runs via ``run_in_threadpool``
        so that CPU-bound work doesn't block the event loop — other requests
        stay responsive while a large range streams. The DB write itself stays
        on the calling thread/coroutine: a SQLAlchemy ``Session`` is not safe
        to use from a different thread than the one it was opened on, even
        sequentially across awaits, so ``self._repo.upsert`` is never
        offloaded — it's cheap relative to the Skyfield computation anyway.
        """
        self.validate_span(req)
        span = (req.end_date - req.start_date).days + 1
        dates = [req.start_date + timedelta(days=offset) for offset in range(span)]

        # Imported lazily: pulls in the Skyfield/ephemeris stack only when a
        # generate actually runs, keeping app startup free of it.
        from app.core.calendar.panchangam import get_panchangam_data

        start = perf_counter()
        for i, day in enumerate(dates, start=1):
            data = await run_in_threadpool(
                get_panchangam_data,
                day,
                location.latitude,
                location.longitude,
                location.timezone,
                self.settings.get_astronomy_tuning(day.year),
            )
            self.repository.upsert(data, location)  # does NOT commit
            yield PanchangamGenerateProgress(
                completed=i,
                total=span,
                percent=round(i / span * 100, 1),
                current_date=day,
                elapsed_seconds=round(perf_counter() - start, 1),
            )

        years = sorted({d.year for d in dates})
        refresh_etags(
            self.reference_repository,
            self.panchangam_service_for_etag_refresh,
            self.etag_repository,
            self.unit_of_work,
            years,
            [location],
        )  # commits

        yield PanchangamGenerateResult(
            start_date=req.start_date,
            end_date=req.end_date,
            count=len(dates),
            years=years,
        )
