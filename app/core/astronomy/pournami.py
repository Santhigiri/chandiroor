"""Pournami (full-moon) day detection.

The full moon is a **night** observance at the Ashram, so a day is the Pournami
day when its night — the window from that day's *sunset* to the next day's
*sunrise* — contains the greatest duration of the Pournami thithi (Thithi 15).

We take the Pournami thithi interval, measure how much of it falls inside each
candidate night window, and attribute Pournami to the **sunset day** of the night
with the maximum overlap. This replaces the older day-end (23:59:59) heuristic,
which misattributed Pournami near sunrise/sunset boundaries.

The night windows and the Pournami thithi interval are read from **already-computed
values** — each day's sunrise/sunset and thithi transitions — supplied by the
caller. In the offline event pipeline (and at runtime) these are the values already
persisted in the cache/DB, so the full-moon day is derived without any redundant
ephemeris computation. :func:`is_poornima_live` is a convenience for callers that do
*not* already hold those values (the single-day live fallback, legacy paths, tests):
it computes them on the fly and delegates to :func:`is_poornima`.
"""
from datetime import date, datetime, timedelta
from typing import Dict, Mapping, Optional, Sequence, Tuple

from core.astronomy.transitions import ThithiTransition
from utils.thithi import Thithi

_POURNAMI_ID = Thithi.POORNIMA.id  # 15

# (sunrise, sunset) for a given date, in the same timezone as the transitions.
SunriseSunset = Tuple[datetime, datetime]


def _pournami_interval(
    target: date,
    thithi_transitions_by_date: Mapping[date, Sequence[ThithiTransition]],
) -> Optional[Tuple[datetime, datetime]]:
    """Return the (start, end) of the Pournami thithi interval near ``target``.

    Scans the thithi transitions of ``target`` and its immediate neighbours and
    returns the single Pournami (Thithi 15) interval found there. The Pournami
    transition is present in every day's transition list it overlaps, so the
    interval is recoverable even when a neighbour's data is absent. There is exactly
    one Pournami per lunar month, so within a ±1 day window at most one interval
    exists. Returns ``None`` when no Pournami interval is near ``target``.
    """
    candidates: Dict[datetime, Tuple[datetime, datetime]] = {}
    for offset in (-1, 0, 1):
        d = target + timedelta(days=offset)
        for transition in thithi_transitions_by_date.get(d, []):
            if transition.thithi.id == _POURNAMI_ID and transition.end_time is not None:
                # Deduplicate by start_time: the Pournami interval recurs in each
                # day-window it overlaps.
                candidates[transition.start_time] = (
                    transition.start_time,
                    transition.end_time,
                )

    if not candidates:
        return None

    if len(candidates) == 1:
        return next(iter(candidates.values()))

    # Defensive: if the window somehow surfaced more than one interval, keep the one
    # whose start sits closest to ``target``'s midday (matching timezone-awareness of
    # the interval timestamps).
    tzinfo = next(iter(candidates.values()))[0].tzinfo
    reference = datetime.combine(target, datetime.min.time().replace(hour=12), tzinfo)
    return min(
        candidates.values(),
        key=lambda interval: abs((interval[0] - reference).total_seconds()),
    )


def _night_overlap(
    interval: Tuple[datetime, datetime],
    night_start: datetime,
    night_end: datetime,
) -> timedelta:
    """Overlap between the night ``[night_start, night_end]`` and ``interval``."""
    p_start, p_end = interval
    overlap = min(p_end, night_end) - max(p_start, night_start)
    return overlap if overlap > timedelta(0) else timedelta(0)


def is_poornima(
    target: date,
    thithi_transitions_by_date: Mapping[date, Sequence[ThithiTransition]],
    sunrise_sunset_by_date: Mapping[date, SunriseSunset],
) -> bool:
    """Return whether ``target`` is the Pournami day, using pre-computed values.

    ``thithi_transitions_by_date`` and ``sunrise_sunset_by_date`` supply the already
    populated values (typically straight from the cache/DB) for ``target`` and its
    neighbours. ``target`` is the Pournami day when the night beginning at its sunset
    holds the greatest span of the Pournami thithi. Nights whose sunrise/sunset are
    missing from the mapping are skipped, so a partial store still resolves correctly
    away from its edges.
    """
    interval = _pournami_interval(target, thithi_transitions_by_date)
    if interval is None:
        return False

    best_day: Optional[date] = None
    best_overlap = timedelta(0)
    for offset in (-1, 0, 1):
        d = target + timedelta(days=offset)
        today = sunrise_sunset_by_date.get(d)
        tomorrow = sunrise_sunset_by_date.get(d + timedelta(days=1))
        if today is None or tomorrow is None:
            continue
        # night d = sunset(d) -> sunrise(d + 1)
        overlap = _night_overlap(interval, today[1], tomorrow[0])
        if overlap > best_overlap:
            best_overlap = overlap
            best_day = d

    return best_day == target and best_overlap > timedelta(0)


def is_poornima_live(localdt: datetime, timezone: str) -> bool:
    """Compute Pournami for a single day without a pre-populated store.

    Builds the sunrise/sunset and thithi-transition inputs for the day and its
    neighbours via live ephemeris computation, then applies the same night-overlap
    rule as :func:`is_poornima`. Used by the single-day live-fallback and legacy
    paths; prefer :func:`is_poornima` with cached/DB values when a store is available.
    """
    # Imported lazily so importing this module for the pure, data-driven path does
    # not drag in the ephemeris stack.
    from core.astronomy.sunrise_sunset import get_sunrise_sunset
    from core.astronomy.thithi_transition import calc_thithi_transition_for_date

    target = localdt.date()
    thithi_transitions_by_date: Dict[date, Sequence[ThithiTransition]] = {}
    sunrise_sunset_by_date: Dict[date, SunriseSunset] = {}
    # -1..+2 covers every night the ±1 day scan needs: night(target+1) reads
    # sunrise(target+2).
    for offset in (-1, 0, 1, 2):
        d = target + timedelta(days=offset)
        thithi_transitions_by_date[d] = calc_thithi_transition_for_date(d, timezone)
        sunrise_sunset_by_date[d] = get_sunrise_sunset(d, timezone=timezone)

    return is_poornima(target, thithi_transitions_by_date, sunrise_sunset_by_date)
