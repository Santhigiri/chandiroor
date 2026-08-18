"""
Match editable Santhigiri event definitions against a single computed day.

This is the live-computation counterpart to the offline cache pipeline
(``features/santhigiri_events/offline_cache/cache_common_events.py``). It lets the ``PanchangamService`` fallback
overlay condition-based events onto a date the DB has no pre-computed occurrence
row for, so events added via the admin CRUD show up automatically on
live-fallback dates.

It is intentionally *pure*: it imports only domain/astronomy helpers and the
response schema — never ``db/`` or ``api/`` — so it respects the layer
boundaries and stays independently testable.

Only events whose condition pins a **single day** are matched here. Events that
need whole-year context ("last occurrence" rules like Navapoojitham and the
Shishyapoojitha birthday) or that only constrain a month/nakshatra without
fixing a day (e.g. the nakshatra-only Janmagriha, the month-only Navapoojitham
Vritharambam) are deliberately excluded — they are bespoke and remain the job of
the dedicated offline cache scripts.
"""
from __future__ import annotations

from datetime import datetime, time
from typing import List

from core.astronomy.pournami import is_poornima_live
from core.constants import DEFAULT_TIMEZONE
from schemas.panchangam_data import PanchangamData
from utils.santhigiri_events import EventCondition, SanthigiriEvent


def pins_single_day(condition: EventCondition) -> bool:
    """True when the condition fixes an event to one calendar day.

    A day is pinned by any of: a full-moon requirement, an English day, a
    Malayalam day, or a Thithi. Conditions with none of these constrain at most a
    month or a nakshatra and would match many days a year, so they are left to
    the bespoke offline logic.
    """
    return bool(
        condition.is_poornima
        or condition.en_day is not None
        or condition.ml_day is not None
        or condition.thithi is not None
    )


def event_matches(
    condition: EventCondition,
    data: PanchangamData,
    timezone: str = DEFAULT_TIMEZONE,
) -> bool:
    """Return True if *data*'s day satisfies every set field of *condition*.

    Mirrors the field-by-field equality used offline in
    ``features.santhigiri_events.offline_cache.cache_navapoojitham.get_matching_dates``. "Last occurrence" events
    and conditions that pin no single day never match here (see the module
    docstring).
    """
    if condition.last_occurance:
        return False
    if not pins_single_day(condition):
        return False

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
        datetime.combine(data.date, time.min), timezone
    ):
        return False

    return True


def match_condition_based_events(
    data: PanchangamData,
    event_defs: List[SanthigiriEvent],
    timezone: str = DEFAULT_TIMEZONE,
) -> List[SanthigiriEvent]:
    """Return the subset of *event_defs* whose condition matches *data*'s day.

    Events with a ``day_offset`` are excluded here: this matcher only ever
    sees one day's data, so it cannot tell whether *this* day is the shifted
    target of some other day's match (that requires whole-year context, see
    ``core.calendar.santhigiri_event_occurrences.compute_occurrences``).
    """
    return [
        event
        for event in event_defs
        if not event.event_condition.day_offset
        and event_matches(event.event_condition, data, timezone)
    ]
