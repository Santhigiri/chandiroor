"""Pournami (full-moon) day detection.

The full moon is a **night** observance at the Ashram, so a day is the Pournami
day when its night — the window from that day's *sunset* to the next day's
*sunrise* — contains the greatest duration of the Pournami thithi (Thithi 15).

We take the Pournami thithi interval, measure how much of it falls inside each
candidate night window, and attribute Pournami to the **sunset day** of the night
with the maximum overlap. This replaces the older day-end (23:59:59) heuristic,
which misattributed Pournami near sunrise/sunset boundaries.
"""
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from core.astronomy.sunrise_sunset import get_sunrise_sunset
from core.astronomy.thithi_transition import calc_thithi_transition_for_date
from utils.thithi import Thithi

_POURNAMI_ID = Thithi.POORNIMA.id  # 15


def _pournami_interval(target: date, timezone: str) -> Optional[Tuple[datetime, datetime]]:
    """Return the (start, end) of the Pournami thithi interval near ``target``.

    Scans the thithi transitions of ``target`` and its immediate neighbours and
    returns the single Pournami (Thithi 15) interval found there. There is exactly
    one Pournami per lunar month, so within a ±1 day window at most one interval
    exists. Returns ``None`` when no Pournami interval is near ``target``.
    """
    candidates = {}
    for offset in (-1, 0, 1):
        d = target + timedelta(days=offset)
        for transition in calc_thithi_transition_for_date(d, timezone):
            if transition.thithi.id == _POURNAMI_ID and transition.end_time is not None:
                # Deduplicate by start_time: the overlapping day-windows return the
                # same interval more than once.
                candidates[transition.start_time] = (transition.start_time, transition.end_time)

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
    day: date, interval: Tuple[datetime, datetime], timezone: str
) -> timedelta:
    """Overlap between ``day``'s night (sunset → next sunrise) and ``interval``."""
    p_start, p_end = interval
    night_start = get_sunrise_sunset(day, timezone=timezone)[1]
    night_end = get_sunrise_sunset(day + timedelta(days=1), timezone=timezone)[0]
    overlap = min(p_end, night_end) - max(p_start, night_start)
    return overlap if overlap > timedelta(0) else timedelta(0)


def is_poornima(localdt: datetime, timezone: str) -> bool:
    """Return whether ``localdt`` is the Pournami day.

    The Pournami day is the day whose night (its sunset → the next sunrise) holds
    the greatest span of the Pournami thithi. ``localdt`` is that day when the night
    beginning at its sunset wins that comparison against the neighbouring nights.
    """
    target = localdt.date()
    interval = _pournami_interval(target, timezone)
    if interval is None:
        return False

    best_day: Optional[date] = None
    best_overlap = timedelta(0)
    for offset in (-1, 0, 1):
        d = target + timedelta(days=offset)
        overlap = _night_overlap(d, interval, timezone)
        if overlap > best_overlap:
            best_overlap = overlap
            best_day = d

    return best_day == target and best_overlap > timedelta(0)
