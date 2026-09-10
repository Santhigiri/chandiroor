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
so the whole range lands in the DB as one atomic transaction — this is
deliberate, not incidental: :func:`features.generation_jobs.service.stream_generation_job`
(this service's only caller) commits the *shared* session after every yielded
event to persist that event into the job row, and since that's the same
session ``self.repository``/``self.unit_of_work`` were built from, a progress
line yielded per day would mean a real per-day commit too. ``generate_streaming``
avoids that by yielding only heartbeat lines (no per-day data) while the range
is computed, and no lines at all during the write loop — see its own
docstring — so the "one write" semantics hold regardless of how many progress
lines happen to be yielded along the way.

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

import asyncio
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


# How often to yield a heartbeat progress line while the batched computation
# (below) is in flight and has nothing real to report yet. Matches the
# frontend's own poll interval (GENERATION_JOB_POLL_INTERVAL_MS) closely
# enough that a client polling the job row sees the elapsed-time counter
# actually moving, without flooding the NDJSON stream/job row with writes.
_HEARTBEAT_INTERVAL_SECONDS = 2.0


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
        """Yield a heartbeat :class:`PanchangamGenerateProgress` every
        ``_HEARTBEAT_INTERVAL_SECONDS`` while the range is computed, then a
        final :class:`PanchangamGenerateResult` once every day has been
        written.

        The whole range's Thithi/Nakshatra transitions are computed together
        in one ``run_in_threadpool`` call via
        :func:`core.calendar.panchangam.get_panchangam_data_range` (one
        range-batched ``find_discrete`` search instead of one per day — see
        its docstring) so that CPU-bound work doesn't block the event loop —
        other requests stay responsive while a large range streams. That call
        has no notion of "day 3 of 9 done" to report — it returns one finished
        dict — so there is nothing true to say about progress until it comes
        back. Rather than staying silent for however long that takes (which
        looks identical to "stuck" from a client's perspective), this awaits
        the computation as a task and yields a ``completed=0`` heartbeat every
        few seconds in the meantime, with ``elapsed_seconds`` ticking up, so a
        polling/streaming client can tell the run is alive.

        Once the computation returns, every day is written in one pass with
        **no** per-day progress line and **no** intermediate commit — the
        whole write (plus the ETag refresh below) lands in the single
        ``refresh_etags(...)`` commit at the end, exactly like a plain
        transaction would. This is deliberate: :func:`features.generation_jobs.service.stream_generation_job`
        (this method's only caller) commits the shared session after *every*
        yielded event to persist that event into the job row, and since that
        session is the same one ``self.repository`` writes through, a
        progress line yielded per day would mean a real commit per day too
        (see the note this docstring used to have, and the module docstring's
        history of that point). Yielding nothing during the write loop keeps
        the whole range's data landing atomically, as one write, rather than
        trickling into the DB row by row.
        """
        self.validate_span(req)
        span = (req.end_date - req.start_date).days + 1
        dates = [req.start_date + timedelta(days=offset) for offset in range(span)]

        # Imported lazily: pulls in the Skyfield/ephemeris stack only when a
        # generate actually runs, keeping app startup free of it.
        from app.core.calendar.panchangam import get_panchangam_data_range

        start = perf_counter()
        # Resolve every year's tuning up front, on this coroutine, rather than
        # handing get_panchangam_data_range the live self.settings.get_astronomy_tuning
        # bound method: that method queries the DB through self.settings'
        # AppSettingRepositoryPort, which shares this service's Session — and
        # get_panchangam_data_range runs inside run_in_threadpool, a *different*
        # OS thread. A DB call from that thread racing the heartbeat loop's
        # job_repository.update_progress()/commit() below (same Session, main
        # thread) corrupts SQLAlchemy's Session state ("This session is in
        # 'prepared' state; no further SQL can be emitted..."). A plain dict
        # lookup has no such thread-safety concern. +/-1 year covers the
        # padding get_panchangam_data_range applies internally for Chandra
        # Masa's month-boundary walk (up to _MAX_MASA_SPAN_DAYS days either
        # side — see its docstring), which can spill into an adjacent year.
        tuning_by_year = {
            year: self.settings.get_astronomy_tuning(year)
            for year in range(req.start_date.year - 1, req.end_date.year + 2)
        }

        compute_task = asyncio.ensure_future(
            run_in_threadpool(
                get_panchangam_data_range,
                req.start_date,
                req.end_date,
                location.latitude,
                location.longitude,
                location.timezone,
                lambda year: tuning_by_year[year],
            )
        )
        while not compute_task.done():
            try:
                await asyncio.wait_for(asyncio.shield(compute_task), timeout=_HEARTBEAT_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                yield PanchangamGenerateProgress(
                    completed=0,
                    total=span,
                    percent=0.0,
                    current_date=req.start_date,
                    elapsed_seconds=round(perf_counter() - start, 1),
                )
        data_by_day = compute_task.result()

        for day in dates:
            self.repository.upsert(data_by_day[day], location)  # does NOT commit

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
