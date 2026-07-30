"""
Compute which calendar days in a given year a Santhigiri event's condition
matches, generalized over *any* :class:`EventCondition` rather than hardcoded
to one event.

This is a live, DB-data-driven counterpart to the offline scripts
(``utils/cache_navapoojitham.py``, ``utils/cache_sishya_bday.py``,
``utils/cache_chothi_theerthayathra.py``) that compute the same three classes
of condition against the pickle cache. It is intentionally *pure*: it imports
only domain/schema types — never ``db/`` or ``api/`` — so it respects the
layer boundaries and stays independently testable.

Conditions fall into three algorithm classes:

* **single_day** — the condition pins one calendar day (see
  :func:`core.calendar.santhigiri_significant_dates.pins_single_day`).
  Every day is matched independently via
  :func:`core.calendar.santhigiri_significant_dates.event_matches`.
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

from core.astronomy.pournami import is_poornima_live
from core.calendar.santhigiri_significant_dates import event_matches, pins_single_day
from core.constants import DEFAULT_TIMEZONE
from schemas.panchangam_data import PanchangamData
from utils.santhigiri_events import EventCondition

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


def compute_last_occurrence(
    condition: EventCondition, yearly_data: PanchangamYear, year: int
) -> date:
    """The last day in *yearly_data* matching *condition*, applying the
    7.5-Nazhika sunrise cutoff, falling back to the last Nakshatra-transition
    into ``condition.nakshatra`` within ``condition.ml_month`` if no day in
    the year matches directly.

    Generalizes ``utils.cache_sishya_bday.calculate_sishya_bday`` to run off
    any condition instead of a hardcoded event.
    """
    matches = sorted(
        d for d, data in yearly_data.items() if _matches_fields(condition, data)
    )
    if matches:
        dt = matches[-1]
        data = yearly_data[dt]
        if data.nazhika_from_sunrise > 7.5:
            return dt
        return dt - timedelta(days=1)

    if condition.ml_month is None or condition.nakshatra is None:
        raise OccurrenceComputationError(
            f"No day in {year} matched the condition, and no Malayalam month/"
            "nakshatra fallback is available."
        )

    month_data = [
        data
        for data in yearly_data.values()
        if data.kv.kv_month == condition.ml_month.id
    ]
    transitions = [
        t
        for data in month_data
        for t in data.nakshatra_transitions
        if t.nakshatra == condition.nakshatra
    ]
    if not transitions:
        raise OccurrenceComputationError(
            f"No Nakshatra transition into {condition.nakshatra.en} found in "
            f"{condition.ml_month.en} of {year}."
        )
    last_transition = sorted(transitions, key=lambda t: t.start_time)[-1]
    return _ist_date(last_transition.start_time)


def compute_transition_series(
    condition: EventCondition, yearly_data: PanchangamYear, year: int
) -> List[date]:
    """Every Nakshatra-transition into ``condition.nakshatra`` during the
    year, applying the 3-hours-after-sunrise cutoff rule.

    Generalizes
    ``utils.cache_chothi_theerthayathra.calculate_chothi_theerthayathra_for_year``
    to run off ``condition.nakshatra`` instead of the hardcoded Chothi
    nakshatra.
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
            transition.end_time - end_date_data.sunrise > timedelta(hours=3)
        ):
            occurrences.append(end_date)
        else:
            occurrences.append(end_date - timedelta(days=1))
    return occurrences


def compute_occurrences(
    condition: EventCondition, yearly_data: PanchangamYear, year: int
) -> List[date]:
    """Dispatch to the algorithm matching *condition*'s class and return the
    resulting occurrence dates for *year*, sorted."""
    condition_class = classify_condition(condition)
    if condition_class == "single_day":
        return compute_single_day_occurrences(condition, yearly_data)
    if condition_class == "last_occurrence":
        return [compute_last_occurrence(condition, yearly_data, year)]
    return sorted(compute_transition_series(condition, yearly_data, year))
