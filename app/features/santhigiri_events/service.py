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
from time import perf_counter
from typing import AsyncIterator, Dict, Iterable, List, Set, Union

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app.core.calendar.santhigiri_event_occurrences import (
    OccurrenceComputationError,
    PanchangamYear,
    UnsupportedEventCondition as UnsupportedOccurrenceCondition,
    compute_occurrences,
)
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.panchangam_repository import PanchangamRepository, event_row_to_event
from app.db.santhigiri_event_repository import SanthigiriEventRepository
from app.features.santhigiri_events.schemas import (
    SanthigiriEventCreate,
    SanthigiriEventGenerateProgress,
    SanthigiriEventGenerateResult,
    SanthigiriEventUpdate,
    SanthigiriEventsGenerateProgress,
    SanthigiriEventsGenerateResult,
)
from app.schemas.app_setting import EventCutoffsValue
from app.services.etag_service import refresh_etags
from app.services.settings_service import SettingsService
from app.utils.location import DEFAULT_LOCATION


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


class YearSpanTooLarge(Exception):
    """Raised when a generate request's year span exceeds the admin-configured
    ``max_event_generate_year_span`` setting."""

    def __init__(self, span: int, max_years: int) -> None:
        self.span = span
        self.max_years = max_years
        super().__init__(f"year range too large: {span} years (max {max_years})")


# OccurrenceComputationError is imported directly above and re-exported as-is;
# UnsupportedEventCondition is aliased on import so callers only need this module.
UnsupportedEventCondition = UnsupportedOccurrenceCondition


class SanthigiriEventService:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = SanthigiriEventRepository(session)
        self._panchangam_repo = PanchangamRepository(session)
        self._settings = SettingsService(session)

    def validate_year_span(self, start_year: int, end_year: int) -> None:
        """Raise :class:`YearSpanTooLarge` if the span exceeds the
        admin-configured cap. Synchronous and side-effect-free, so route
        handlers can call it before opening a streaming response — the only
        way a caller of a streaming generate endpoint can get a real 422
        instead of a 200 + NDJSON error line. The three ``generate_*`` methods
        below also enforce this themselves as defense in depth for any other
        caller."""
        span = end_year - start_year + 1
        max_years = self._settings.get_max_event_generate_year_span()
        if span > max_years:
            raise YearSpanTooLarge(span, max_years)

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
        if changes.get("yields_to_event_id") == event_id:
            raise InvalidEventReference(
                f"yields_to_event_id cannot reference the event's own id ({event_id!r})"
            )
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

    def generate_occurrences(
        self, event_id: str, start_year: int, end_year: int
    ) -> Dict[int, List[datetime.date]]:
        """(Re)compute *event_id*'s occurrence dates across the inclusive
        ``[start_year, end_year]`` range and replace whatever was previously
        stored for that event in each of those years.

        Raises :class:`IncompleteYearData` for the first year in the range
        whose panchangam data is not fully present in the DB,
        :class:`UnsupportedEventCondition` if the event's condition cannot be
        resolved to a set of days (this is year-independent, so it surfaces
        on the first year), and :class:`OccurrenceComputationError` if a
        resolvable condition still has no computable occurrence in a given
        year. Any of these aborts the whole range — nothing commits until
        every year has been computed, so a failure on a later year still
        rolls back years already processed.
        """
        self.validate_year_span(start_year, end_year)
        row = self.get(event_id)
        condition = event_row_to_event(row).event_condition
        cutoffs = self._settings.get_event_cutoffs()

        years = list(range(start_year, end_year + 1))
        results: Dict[int, List[datetime.date]] = {}
        for year in years:
            start = datetime.date(year, 1, 1)
            end = datetime.date(year, 12, 31)
            yearly_data = self._panchangam_repo.get_by_date_range(
                start, end, DEFAULT_LOCATION
            )
            expected_days = (end - start).days + 1
            if len(yearly_data) != expected_days:
                raise IncompleteYearData(year)

            occurrences = compute_occurrences(
                condition, yearly_data, year,
                cutoffs.nazhika_cutoff, cutoffs.transition_hour_cutoff,
            )
            excluded = self._excluded_dates_for_yield(row, yearly_data, year, cutoffs)
            if excluded:
                occurrences = [d for d in occurrences if d not in excluded]
            self._panchangam_repo.set_event_occurrences_for_year(
                event_id, year, occurrences
            )
            results[year] = occurrences

        self._commit_with_etags(years)
        return results

    async def generate_occurrences_streaming(
        self, event_id: str, start_year: int, end_year: int
    ) -> AsyncIterator[Union[SanthigiriEventGenerateProgress, SanthigiriEventGenerateResult]]:
        """Streaming sibling of :meth:`generate_occurrences`: same
        computation, one year at a time, yielding a
        :class:`SanthigiriEventGenerateProgress` line after each year and a
        final :class:`SanthigiriEventGenerateResult`.

        Same error semantics as :meth:`generate_occurrences` —
        :class:`IncompleteYearData`, :class:`UnsupportedEventCondition`, and
        :class:`OccurrenceComputationError` all abort the whole range and
        propagate to the caller; nothing commits until every year has been
        computed, so a failure on a later year still rolls back years already
        processed.

        Each year's computation runs via ``run_in_threadpool`` since a
        last-occurrence condition with an ``is_poornima`` field can trigger a
        live ephemeris check per candidate day, which is CPU-bound and would
        otherwise block the event loop.
        """
        self.validate_year_span(start_year, end_year)
        row = self.get(event_id)
        condition = event_row_to_event(row).event_condition
        cutoffs = self._settings.get_event_cutoffs()

        years = list(range(start_year, end_year + 1))
        total = len(years)
        completed = 0
        results: Dict[int, List[datetime.date]] = {}

        clock = perf_counter()
        for year in years:
            start = datetime.date(year, 1, 1)
            end = datetime.date(year, 12, 31)
            yearly_data = self._panchangam_repo.get_by_date_range(
                start, end, DEFAULT_LOCATION
            )
            expected_days = (end - start).days + 1
            if len(yearly_data) != expected_days:
                raise IncompleteYearData(year)

            occurrences = await run_in_threadpool(
                compute_occurrences, condition, yearly_data, year,
                cutoffs.nazhika_cutoff, cutoffs.transition_hour_cutoff,
            )
            excluded = await run_in_threadpool(
                self._excluded_dates_for_yield, row, yearly_data, year, cutoffs
            )
            if excluded:
                occurrences = [d for d in occurrences if d not in excluded]
            self._panchangam_repo.set_event_occurrences_for_year(
                event_id, year, occurrences
            )
            results[year] = occurrences
            completed += 1

            yield SanthigiriEventGenerateProgress(
                year=year,
                count=len(occurrences),
                completed=completed,
                total=total,
                percent=round(completed / total * 100, 1) if total else 100.0,
                elapsed_seconds=round(perf_counter() - clock, 1),
            )

        self._commit_with_etags(years)

        yield SanthigiriEventGenerateResult(
            event_id=event_id,
            start_year=start_year,
            end_year=end_year,
            occurrences=results,
        )

    async def generate_all_occurrences_streaming(
        self, start_year: int, end_year: int
    ) -> AsyncIterator[Union[SanthigiriEventsGenerateProgress, SanthigiriEventsGenerateResult]]:
        """(Re)compute every event definition's occurrence dates across the
        inclusive ``[start_year, end_year]`` range, yielding a
        :class:`SanthigiriEventsGenerateProgress` line after each
        ``(year, event)`` pair, then a final :class:`SanthigiriEventsGenerateResult`.

        Raises :class:`IncompleteYearData` for the first year in the range
        whose panchangam data is not fully present in the DB — the same
        precondition :meth:`generate_occurrences` enforces per-year — which
        aborts the whole range (nothing has committed yet, so no year's
        writes stick). An individual event whose condition can't be resolved
        (:class:`UnsupportedEventCondition`) or has no computable occurrence
        in a given year (:class:`OccurrenceComputationError`) is reported as
        ``"skipped"``/``"error"`` in its progress line instead — one bad
        event definition shouldn't block regenerating the rest.

        Each event's computation runs via ``run_in_threadpool``: a
        last-occurrence condition with an ``is_poornima`` field can trigger a
        live ephemeris check per candidate day, which is CPU-bound and would
        otherwise block the event loop. All writes across every year land in
        one session and commit together with every affected year's ETag
        refresh at the very end — the whole range is one atomic transaction,
        so a failure on a later year still rolls back years already processed.
        """
        self.validate_year_span(start_year, end_year)
        years = list(range(start_year, end_year + 1))
        rows = self._repo.list_all()
        total = len(rows) * len(years)
        generated = skipped = errors = 0
        completed = 0
        cutoffs = self._settings.get_event_cutoffs()

        clock = perf_counter()
        for year in years:
            start = datetime.date(year, 1, 1)
            end = datetime.date(year, 12, 31)
            yearly_data = self._panchangam_repo.get_by_date_range(
                start, end, DEFAULT_LOCATION
            )
            expected_days = (end - start).days + 1
            if len(yearly_data) != expected_days:
                raise IncompleteYearData(year)

            for row in rows:
                completed += 1
                condition = event_row_to_event(row).event_condition
                count = 0
                status = "generated"
                detail = None
                try:
                    occurrences = await run_in_threadpool(
                        compute_occurrences, condition, yearly_data, year,
                        cutoffs.nazhika_cutoff, cutoffs.transition_hour_cutoff,
                    )
                except UnsupportedOccurrenceCondition as exc:
                    status, skipped, detail = "skipped", skipped + 1, str(exc)
                except OccurrenceComputationError as exc:
                    status, errors, detail = "error", errors + 1, str(exc)
                else:
                    if row.yields_to_event_id is None:
                        excluded: Set[datetime.date] = set()
                    else:
                        excluded = await run_in_threadpool(
                            self._excluded_dates_for_yield, row, yearly_data, year, cutoffs
                        )
                    if excluded:
                        occurrences = [d for d in occurrences if d not in excluded]
                    self._panchangam_repo.set_event_occurrences_for_year(
                        row.id, year, occurrences
                    )
                    generated += 1
                    count = len(occurrences)

                yield SanthigiriEventsGenerateProgress(
                    year=year,
                    event_id=row.id,
                    name=row.name,
                    status=status,
                    count=count,
                    detail=detail,
                    completed=completed,
                    total=total,
                    percent=round(completed / total * 100, 1) if total else 100.0,
                    elapsed_seconds=round(perf_counter() - clock, 1),
                )

        self._commit_with_etags(years)

        yield SanthigiriEventsGenerateResult(
            start_year=start_year,
            end_year=end_year,
            years=years,
            total_events=total,
            generated=generated,
            skipped=skipped,
            errors=errors,
        )

    # ── Internal ─────────────────────────────────────────────────────────────────

    def _excluded_dates_for_yield(
        self,
        row: SanthigiriEventRow,
        yearly_data: PanchangamYear,
        year: int,
        cutoffs: EventCutoffsValue,
    ) -> Set[datetime.date]:
        """Dates *row* must NOT occur on for *year* because it "yields to"
        another event whose condition also matches those dates.

        Resolves the sibling event's condition and recomputes its
        occurrences live against the same ``yearly_data`` already fetched
        for *row* — never a DB read of the sibling's currently-stored
        ``santhigiri_event_dates`` rows. This makes the exclusion
        independent of whether the sibling has been (re)generated yet in
        this run, and independent of how stale its stored dates are.

        Never raises: a missing sibling row, or a sibling condition that
        can't be classified (:class:`UnsupportedEventCondition`) or computed
        (:class:`OccurrenceComputationError`), degrades to "nothing
        excluded" — this event's own generation must never fail because of
        a problem with the event it yields to.
        """
        if row.yields_to_event_id is None:
            return set()
        sibling = self._repo.get(row.yields_to_event_id)
        if sibling is None:
            return set()
        sibling_condition = event_row_to_event(sibling).event_condition
        try:
            return set(
                compute_occurrences(
                    sibling_condition, yearly_data, year,
                    cutoffs.nazhika_cutoff, cutoffs.transition_hour_cutoff,
                )
            )
        except (UnsupportedOccurrenceCondition, OccurrenceComputationError):
            return set()

    def _commit_with_etags(self, years: Iterable[int]) -> None:
        # refresh_etags recomputes the payloads from the (still pending) session
        # state and commits once, so the data change and its ETags land in a
        # single transaction. It always refreshes every enum dataset — including
        # ``events`` — and any years passed here.
        refresh_etags(self._s, years)
