"""
Compute which calendar days in a given year an event's condition matches,
generalized over *any* :class:`EventCondition` rather than hardcoded to one
event. The same resolution serves the built-in Santhigiri observances and any
custom (e.g. personal) event definition sharing the ``EventCondition`` shape.

It is intentionally *pure*: it imports only domain/schema types — never
``db/`` or ``api/`` — so it respects the layer boundaries and stays
independently testable.

Conditions fall into three algorithm classes:

* **single_day** — the condition pins one calendar day (see
  :func:`core.events.significant_dates.pins_single_day`).
  Every day is matched independently via
  :func:`core.events.significant_dates.event_matches`.
* **last_occurrence** — ``last_occurance=True``: the last day in the
  condition's Malayalam month whose sunrise-Nakshatra matches, with the
  7.5-Nazhika cutoff rule, falling back to the last Nakshatra-transition in
  that month when no sunrise match exists in the year.
* **transition_series** — a bare ``nakshatra`` (no day pin, no
  ``last_occurance``): every Nakshatra-transition into that nakshatra during
  the year, with a 3-hours-after-sunrise cutoff rule.

Any other shape (e.g. a month-only condition with no nakshatra) cannot be
resolved to a set of days and raises :class:`UnsupportedEventCondition`.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Dict, List, Literal

import pytz

from app.core.astronomy.pournami import is_poornima_live
from app.core.events.significant_dates import event_matches, pins_single_day
from app.core.astronomy.constants import DEFAULT_TIMEZONE
from app.schemas.panchangam_data import PanchangamData
from app.utils.santhigiri_events import EventCondition

PanchangamYear = Dict[date, PanchangamData]

ConditionClass = Literal["single_day", "last_occurrence", "transition_series"]

_IST = pytz.timezone(DEFAULT_TIMEZONE)


def _ist_date(dt: datetime) -> date:
    """The calendar date *dt* falls on in Asia/Kolkata.

    Transition timestamps read back from the DB are UTC-aware; calendar-day
    bucketing here is Ashram-observance logic and must stay IST regardless of
    the storage/display timezone.
    """
    return dt.astimezone(_IST).date()


class UnsupportedEventCondition(Exception):
    """Raised when a condition cannot be resolved to a set of occurrence days."""


class OccurrenceComputationError(Exception):
    """Raised when a resolvable condition has no computable occurrence in the year."""


def classify_condition(condition: EventCondition) -> ConditionClass:
    if pins_single_day(condition):
        return "single_day"
    if condition.last_occurance:
        return "last_occurrence"
    if condition.nakshatra is not None:
        return "transition_series"
    raise UnsupportedEventCondition(
        "Condition does not pin a single day, is not a last-occurrence "
        "condition, and does not constrain a nakshatra — it cannot be "
        "resolved to a set of occurrence days."
    )


def _matches_fields(condition: EventCondition, data: PanchangamData) -> bool:
    """Field-by-field equality check against every set field of *condition*,
    ignoring ``last_occurance`` (unlike :func:`event_matches`, which treats a
    last-occurrence condition as never matching a single day on its own —
    exactly the case :func:`compute_last_occurrence` needs to check directly).
    """
    if condition.nakshatra is not None and condition.nakshatra != data.nakshatra:
        return False
    if condition.thithi is not None and condition.thithi != data.thithi:
        return False
    if condition.ml_day is not None and condition.ml_day != data.kv.kv_day:
        return False
    if condition.ml_month is not None and condition.ml_month.id != data.kv.kv_month:
        return False
    if condition.ml_year is not None and condition.ml_year != data.kv.kv_year:
        return False
    if condition.en_day is not None and condition.en_day != data.date.day:
        return False
    if condition.en_month is not None and condition.en_month != data.date.month:
        return False
    if condition.en_year is not None and condition.en_year != data.date.year:
        return False
    if condition.is_poornima is not None and condition.is_poornima != is_poornima_live(
        datetime.combine(data.date, time.min), DEFAULT_TIMEZONE
    ):
        return False
    return True


def compute_single_day_occurrences(
    condition: EventCondition, yearly_data: PanchangamYear
) -> List[date]:
    """Every day in *yearly_data* whose fields satisfy *condition*."""
    return sorted(
        d for d, data in yearly_data.items() if event_matches(condition, data)
    )


def _last_occurrence_candidates(
    condition: EventCondition,
    yearly_data: PanchangamYear,
    nazhika_cutoff: float,
) -> List[date]:
    """One resolved last-occurrence date per distinct Kollam year
    (``data.kv.kv_year``) present in *yearly_data*, applying the Nazhika
    sunrise cutoff / Nakshatra-transition fallback independently within
    each Kollam-year group.

    Grouping by Kollam year (rather than treating *yearly_data* as one
    contiguous run) is what keeps a straddling Malayalam month — Dhanu spans
    December of one Gregorian year into January of the next, per a single
    Kollam year — from having its occurrence conflated with the neighboring
    Kollam year's Dhanu that may also be present in a padded window.
    """
    by_kv_year: Dict[int, List[date]] = {}
    for d, data in yearly_data.items():
        if _matches_fields(condition, data):
            by_kv_year.setdefault(data.kv.kv_year, []).append(d)

    if by_kv_year:
        candidates = []
        for dates in by_kv_year.values():
            dt = max(dates)
            data = yearly_data[dt]
            if data.nazhika_from_sunrise > nazhika_cutoff:
                candidates.append(dt)
            else:
                candidates.append(dt - timedelta(days=1))
        return candidates

    if condition.ml_month is None or condition.nakshatra is None:
        raise OccurrenceComputationError(
            "No day matched the condition, and no Malayalam month/"
            "nakshatra fallback is available."
        )

    transitions_by_kv_year: Dict[int, List] = {}
    for data in yearly_data.values():
        if data.kv.kv_month != condition.ml_month.id:
            continue
        for t in data.nakshatra_transitions:
            if t.nakshatra == condition.nakshatra:
                transitions_by_kv_year.setdefault(data.kv.kv_year, []).append(t)

    if not transitions_by_kv_year:
        raise OccurrenceComputationError(
            f"No Nakshatra transition into {condition.nakshatra.name} found in "
            f"{condition.ml_month.name}."
        )
    return [
        _ist_date(max(transitions, key=lambda t: t.start_time).start_time)
        for transitions in transitions_by_kv_year.values()
    ]


def compute_last_occurrence(
    condition: EventCondition,
    yearly_data: PanchangamYear,
    year: int,
    nazhika_cutoff: float = 7.5,
) -> date:
    """The last day matching *condition* whose date falls in *year*,
    applying the Nazhika sunrise cutoff, falling back to the last
    Nakshatra-transition into ``condition.nakshatra`` within
    ``condition.ml_month`` if no day matches directly.

    *yearly_data* may span more than *year* — callers pad the fetched window
    across the Gregorian year boundary for ``last_occurance`` conditions,
    since a straddling Malayalam month (Dhanu) needs visibility into the
    neighboring year to resolve correctly (see
    :func:`_last_occurrence_candidates`). Only the resulting candidate whose
    Gregorian year equals *year* is returned — a straddling month's true
    last occurrence may legitimately resolve to either the requested year or
    the adjacent one, depending on which day it lands on.
    """
    candidates = _last_occurrence_candidates(condition, yearly_data, nazhika_cutoff)
    in_year = [d for d in candidates if d.year == year]
    if not in_year:
        raise OccurrenceComputationError(
            f"No occurrence of the condition resolved to a date in {year} "
            "from the data available."
        )
    if len(in_year) > 1:
        raise OccurrenceComputationError(
            f"Condition resolved to multiple candidate dates in {year}: "
            f"{sorted(in_year)} — ambiguous last-occurrence condition."
        )
    return in_year[0]


def compute_transition_series(
    condition: EventCondition,
    yearly_data: PanchangamYear,
    year: int,
    transition_hour_cutoff: float = 3.0,
) -> List[date]:
    """Every Nakshatra-transition into ``condition.nakshatra`` during the
    year, applying the hours-after-sunrise cutoff rule.
    """
    transitions = {
        (t.start_time, t.end_time): t
        for data in yearly_data.values()
        for t in data.nakshatra_transitions
        if t.nakshatra == condition.nakshatra
    }
    sorted_transitions = sorted(transitions.values(), key=lambda t: t.start_time)

    occurrences: List[date] = []
    for transition in sorted_transitions:
        if transition.end_time is None:
            raise OccurrenceComputationError(
                f"Transition end time is missing near {_ist_date(transition.start_time)} "
                f"in {year}."
            )
        end_date = _ist_date(transition.end_time)
        end_date_data = yearly_data.get(end_date)
        if end_date_data is not None and (
            transition.end_time - end_date_data.sunrise > timedelta(hours=transition_hour_cutoff)
        ):
            occurrences.append(end_date)
        else:
            occurrences.append(end_date - timedelta(days=1))
    return occurrences


def _apply_day_offset(dates: List[date], day_offset: int | None, year: int) -> List[date]:
    """Shift every date in *dates* by *day_offset* days.

    Raises :class:`OccurrenceComputationError` if a shift pushes a date out
    of *year* — ``set_event_occurrences_for_year`` (``db/repository.py``)
    deletes/reinserts strictly within the requested year, so a date that
    crosses into a neighboring year would either get silently dropped by
    that year's own regeneration or leak in undetected. Rejecting here keeps
    that invariant intact rather than attempting to resolve it.
    """
    if not day_offset:
        return dates
    shifted = []
    for d in dates:
        nd = d + timedelta(days=day_offset)
        if nd.year != year:
            raise OccurrenceComputationError(
                f"day_offset={day_offset} shifts {d} to {nd}, crossing out of "
                f"{year} — not supported."
            )
        shifted.append(nd)
    return shifted


def compute_occurrences(
    condition: EventCondition,
    yearly_data: PanchangamYear,
    year: int,
    nazhika_cutoff: float = 7.5,
    transition_hour_cutoff: float = 3.0,
) -> List[date]:
    """Dispatch to the algorithm matching *condition*'s class and return the
    resulting occurrence dates for *year*, sorted, shifted by
    ``condition.day_offset`` if set."""
    condition_class = classify_condition(condition)
    if condition_class == "single_day":
        occurrences = compute_single_day_occurrences(condition, yearly_data)
    elif condition_class == "last_occurrence":
        occurrences = [
            compute_last_occurrence(condition, yearly_data, year, nazhika_cutoff)
        ]
    else:
        occurrences = sorted(
            compute_transition_series(condition, yearly_data, year, transition_hour_cutoff)
        )
    return _apply_day_offset(occurrences, condition.day_offset, year)
