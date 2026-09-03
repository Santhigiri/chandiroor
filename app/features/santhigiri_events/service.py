"""
SanthigiriEventService — orchestrates create/read/update/delete of the editable
Santhigiri event definitions and keeps the affected dataset ETags in lockstep.

Every mutation is committed together with a recomputation of the affected ETags
(via :func:`features.etag.service.refresh_etags`), so a cached client always
revalidates correctly:

* the ``events`` reference dataset changes on every create/update/delete;
* a delete additionally cascades to ``santhigiri_event_dates``, changing the
  ``/year`` payload for each year the event used to fall on — those years' ETags
  are refreshed too.

The route layer stays thin: it maps the domain errors raised here onto HTTP
status codes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import AsyncIterator, Dict, Iterable, List, Set, Union

from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.core.calendar.santhigiri_event_occurrences import (
    OccurrenceComputationError,
    PanchangamYear,
    UnsupportedEventCondition as UnsupportedOccurrenceCondition,
    compute_occurrences,
)
from app.core.ports.panchangam_service import PanchangamServicePort
from app.core.ports.reference_repository import ReferenceRepositoryPort
from app.core.ports.settings_service import SettingsServicePort
from app.core.ports.unit_of_work import UnitOfWork
from app.features.panchangam.ports import PanchangamRepositoryPort
from app.features.etag.ports import EtagRepositoryPort
from app.features.santhigiri_events.ports import (
    SanthigiriEventCreate as SanthigiriEventCreatePort,
    SanthigiriEventGet,
    SanthigiriEventUdpate as SanthigiriEventUpdatePort,
    SanthigiriEventsRepositoryPort,
)
from app.features.santhigiri_events.schemas import (
    SanthigiriEventCreate as SanthigiriEventCreateRequest,
    SanthigiriEventDetail,
    SanthigiriEventGenerateProgress,
    SanthigiriEventGenerateResult,
    SanthigiriEventsGenerateProgress,
    SanthigiriEventsGenerateResult,
    SanthigiriEventUpdate as SanthigiriEventUpdateRequest,
)

from app.schemas.app_setting import EventCutoffsValue
from app.features.etag.service import refresh_etags
from app.utils.location import DEFAULT_LOCATION
from app.utils.malayalam_masa import MalayalamMasa
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.santhigiri_events import EventCondition
from app.core.astronomy.enums.thithi import Thithi


class EventAlreadyExistsException(Exception):
    """Raised when creating an event whose id is already taken."""


class InvalidEventReferenceException(Exception):
    """Raised when a condition foreign key (e.g. nakshatra_id) does not resolve."""


class IncompleteYearDataException(Exception):
    """Raised when *year* is not fully present in the DB, so occurrences
    (especially last-occurrence/transition-series ones) cannot be safely
    computed."""


class YearSpanTooLargeException(Exception):
    """Raised when a generate request's year span exceeds the admin-configured
    ``max_event_generate_year_span`` setting."""

    def __init__(self, span: int, max_years: int) -> None:
        self.span = span
        self.max_years = max_years
        super().__init__(f"year range too large: {span} years (max {max_years})")


# OccurrenceComputationError is imported directly above and re-exported as-is;
# UnsupportedEventCondition is aliased on import so callers only need this module.
UnsupportedEventCondition = UnsupportedOccurrenceCondition


@dataclass(frozen=True)
class SanthigiriEventService:
    reference_repository: ReferenceRepositoryPort
    event_repository: SanthigiriEventsRepositoryPort
    etag_repository: EtagRepositoryPort
    panchangam_repo: PanchangamRepositoryPort
    settings: SettingsServicePort
    panchangam_service_for_etag_refresh: PanchangamServicePort
    unit_of_work: UnitOfWork


    def validate_year_span(self, start_year: int, end_year: int) -> None:
        """Raise :class:`YearSpanTooLarge` if the span exceeds the
        admin-configured cap. Synchronous and side-effect-free, so route
        handlers can call it before opening a streaming response — the only
        way a caller of a streaming generate endpoint can get a real 422
        instead of a 200 + NDJSON error line. The three ``generate_*`` methods
        below also enforce this themselves as defense in depth for any other
        caller."""
        span = end_year - start_year + 1
        max_years = self.settings.get_max_event_generate_year_span()
        if span > max_years:
            raise YearSpanTooLargeException(span, max_years)

    # ── Read ────────────────────────────────────────────────────────────────────

    def get_event_by_id(self, event_id: str) -> SanthigiriEventDetail:
        event = self.event_repository.get_event_by_id(event_id)
        return self._to_detail(event)

    # ── Write ───────────────────────────────────────────────────────────────────

    def create_event(self, payload: SanthigiriEventCreateRequest) -> SanthigiriEventDetail:
        if self.event_repository.event_exists(payload.id):
            raise EventAlreadyExistsException(payload.id)
        port_event = SanthigiriEventCreatePort(
            id=payload.id,
            name=payload.name,
            description=payload.description,
            sort_order=payload.sort_order,  # type: ignore[arg-type]  # None → repository assigns the next sort_order
            event_condition=self._event_condition_from_request(payload),
            yields_to_event_id=payload.yields_to_event_id,
        )
        try:
            with self.unit_of_work:
                new_event = self.event_repository.create_event(port_event)
                self._commit_with_etags([])
        except IntegrityError as exc:
            raise InvalidEventReferenceException(str(exc.orig)) from exc
        return self._to_detail(new_event)

    def update(self, event_id: str, payload: SanthigiriEventUpdateRequest) -> SanthigiriEventDetail:
        existing = self._to_detail(self.event_repository.get_event_by_id(event_id))
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("yields_to_event_id") == event_id:
            raise InvalidEventReferenceException(
                f"yields_to_event_id cannot reference the event's own id ({event_id!r})"
            )
        merged = self._merge_update_request(existing, changes)
        port_event = SanthigiriEventUpdatePort(
            name=merged["name"],
            description=merged["description"],
            sort_order=merged["sort_order"],
            event_condition=self._event_condition_from_request(merged),
            yields_to_event_id=merged["yields_to_event_id"],
        )
        try:
            with self.unit_of_work:
                updated_event = self.event_repository.update_event(port_event, event_id)
                self._commit_with_etags([])
        except IntegrityError as exc:
            raise InvalidEventReferenceException(str(exc.orig)) from exc
        return self._to_detail(updated_event)

    def delete(self, event_id: str) -> SanthigiriEventDetail:
        event = self.event_repository.get_event_by_id(event_id)
        affected_years = self.event_repository.occurrence_years_before_delete(event_id)
        with self.unit_of_work:
            deleted_event = self.event_repository.delete_event(event)
            self._commit_with_etags(affected_years)
        return self._to_detail(deleted_event)

    def generate_occurrences(
        self, event_id: str, start_year: int, end_year: int
    ) -> Dict[int, List[date]]:
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
        event = self.event_repository.get_event_by_id(event_id)
        condition = event.event_condition
        cutoffs = self.settings.get_event_cutoffs()

        years = list(range(start_year, end_year + 1))
        results: Dict[int, List[date]] = {}
        for year in years:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            yearly_data = self.panchangam_repo.get_by_date_range(
                start, end, DEFAULT_LOCATION
            )
            expected_days = (end - start).days + 1
            if len(yearly_data) != expected_days:
                raise IncompleteYearDataException(year)

            occurrences = compute_occurrences(
                condition, yearly_data, year,
                cutoffs.nazhika_cutoff, cutoffs.transition_hour_cutoff,
            )
            excluded = self._excluded_dates_for_yield(event, yearly_data, year, cutoffs)
            if excluded:
                occurrences = [d for d in occurrences if d not in excluded]
            self.event_repository.set_event_occurrences_for_year(
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
        event = self.event_repository.get_event_by_id(event_id)
        condition = event.event_condition
        cutoffs = self.settings.get_event_cutoffs()

        years = list(range(start_year, end_year + 1))
        total = len(years)
        completed = 0
        results: Dict[int, List[date]] = {}

        clock = perf_counter()
        for year in years:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            yearly_data = self.panchangam_repo.get_by_date_range(
                start, end, DEFAULT_LOCATION
            )
            expected_days = (end - start).days + 1
            if len(yearly_data) != expected_days:
                raise IncompleteYearDataException(year)

            occurrences = await run_in_threadpool(
                compute_occurrences, condition, yearly_data, year,
                cutoffs.nazhika_cutoff, cutoffs.transition_hour_cutoff,
            )
            excluded = await run_in_threadpool(
                self._excluded_dates_for_yield, event, yearly_data, year, cutoffs
            )
            if excluded:
                occurrences = [d for d in occurrences if d not in excluded]
            self.event_repository.set_event_occurrences_for_year(
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

        Raises :class:`IncompleteYearDataException` for the first year in the
        range whose panchangam data is not fully present in the DB — the same
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
        rows = self.event_repository.get_all_events()
        total = len(rows) * len(years)
        generated = skipped = errors = 0
        completed = 0
        cutoffs = self.settings.get_event_cutoffs()

        clock = perf_counter()
        for year in years:
            start = date(year, 1, 1)
            end = date(year, 12, 31)
            yearly_data = self.panchangam_repo.get_by_date_range(
                start, end, DEFAULT_LOCATION
            )
            expected_days = (end - start).days + 1
            if len(yearly_data) != expected_days:
                raise IncompleteYearDataException(year)

            for row in rows:
                completed += 1
                condition = row.event_condition
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
                    excluded = await run_in_threadpool(
                        self._excluded_dates_for_yield, row, yearly_data, year, cutoffs
                    )
                    if excluded:
                        occurrences = [d for d in occurrences if d not in excluded]
                    self.event_repository.set_event_occurrences_for_year(
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

    def _to_detail(self, event: SanthigiriEventGet) -> SanthigiriEventDetail:
        """Flatten the port's nested ``event_condition`` into the flat
        request/response schema shape used at the HTTP boundary."""
        ec = event.event_condition
        return SanthigiriEventDetail(
            id=event.id,
            name=event.name,
            description=event.description,
            sort_order=event.sort_order,
            nakshatra_id=ec.nakshatra.id if ec.nakshatra is not None else None,
            thithi_id=ec.thithi.id if ec.thithi is not None else None,
            ml_day=ec.ml_day,
            ml_month=ec.ml_month.id if ec.ml_month is not None else None,
            ml_year=ec.ml_year,
            en_day=ec.en_day,
            en_month=ec.en_month,
            en_year=ec.en_year,
            occurance=ec.occurance,
            is_poornima=ec.is_poornima,
            last_occurance=ec.last_occurance,
            day_offset=ec.day_offset,
            yields_to_event_id=event.yields_to_event_id,
        )

    def _event_condition_from_request(self, fields) -> EventCondition:
        """Build the nested ``EventCondition`` from the flat id-based fields
        on a create/merged-update request. ``fields`` supports both attribute
        access (a schema instance) and dict-style ``["key"]`` access (the
        merged dict :meth:`_merge_update_request` produces)."""
        get = fields.__getitem__ if isinstance(fields, dict) else fields.__getattribute__
        nakshatra_id = get("nakshatra_id")
        thithi_id = get("thithi_id")
        ml_month = get("ml_month")
        return EventCondition(
            nakshatra=Nakshatra.from_id(nakshatra_id) if nakshatra_id is not None else None,
            thithi=Thithi.from_id(thithi_id) if thithi_id is not None else None,
            ml_day=get("ml_day"),
            ml_month=MalayalamMasa.from_id(ml_month) if ml_month is not None else None,
            ml_year=get("ml_year"),
            en_day=get("en_day"),
            en_month=get("en_month"),
            en_year=get("en_year"),
            occurance=get("occurance"),
            is_poornima=get("is_poornima"),
            last_occurance=get("last_occurance"),
            day_offset=get("day_offset"),
        )

    _UPDATE_FIELDS = (
        "name", "description", "sort_order", "nakshatra_id", "thithi_id",
        "ml_day", "ml_month", "ml_year", "en_day", "en_month", "en_year",
        "occurance", "is_poornima", "last_occurance", "day_offset",
        "yields_to_event_id",
    )

    def _merge_update_request(
        self, existing: SanthigiriEventDetail, changes: dict
    ) -> dict:
        """Apply the partial ``changes`` (from ``model_dump(exclude_unset=True)``)
        on top of *existing*'s current values, since the port's update DTO
        (unlike the request schema) requires every field."""
        return {field: changes.get(field, getattr(existing, field)) for field in self._UPDATE_FIELDS}

    def _excluded_dates_for_yield(
        self,
        row: SanthigiriEventGet,
        yearly_data: PanchangamYear,
        year: int,
        cutoffs: EventCutoffsValue,
    ) -> Set[date]:
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
        sibling = self.event_repository.get_event_by_id(row.yields_to_event_id)
        if sibling is None:
            return set()
        sibling_condition = sibling.event_condition
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
        refresh_etags(
            self.reference_repository,
            self.panchangam_service_for_etag_refresh,
            self.etag_repository,
            self.unit_of_work,
            years,
        )
