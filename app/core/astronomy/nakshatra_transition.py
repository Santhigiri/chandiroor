from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import List
from zoneinfo import ZoneInfo

from numpy import ndarray
from skyfield.searchlib import find_discrete
from skyfield.api import Time
from app.core.astronomy.calculations import get_time

from app.core.astronomy.thithi_transition import get_sidereal_longitude_from_time
from app.core.astronomy.transitions import NakshatraTransition
from app.core.astronomy.tuning import AstronomyTuning
from app.core.astronomy.enums.nakshatra import Nakshatra


def make_nakshatra_transition_fn(eps: float, step_days: float):
    """Build a fresh ``find_discrete`` predicate bound to *eps*/*step_days*.

    A closure per call, not a shared module-level function with a mutated
    ``.step_days`` attribute: the old approach was a race condition once the
    step size can vary per call (e.g. concurrently regenerating two years
    with different overrides) — the mutation from one call could be read by
    another call's ``find_discrete`` before it runs.
    """

    def _nakshatra_transition(t: Time):
        moon_lon = get_sidereal_longitude_from_time(t, "moon")
        idx = ((moon_lon + eps) / (360/27)).astype(int)
        return idx % 27

    _nakshatra_transition.step_days = step_days  # pyright: ignore adjust value to fetch all transition_times
    return _nakshatra_transition


@lru_cache(maxsize=1000)
def _get_nakshatra_transition_for_date(
    date: date, timezone: str, nakshatra_epsilon: float, nakshatra_step_days: float, nakshatra_num: int
) -> List[NakshatraTransition]:
    """Cache-friendly core: hashable args only. See ``get_nakshatra_transition_for_date``.

    ``calc_nakshatra_transition_for_date`` calls this for a five-day window
    around each date, so the overlap between consecutive dates is served from
    cache rather than recomputed — mirroring ``get_thithi_transition_by_date``.
    """
    t0 = get_time(datetime.combine(date, time.min), timezone)
    t1 = get_time(datetime.combine(date, time.max), timezone)

    transition_fn = make_nakshatra_transition_fn(nakshatra_epsilon, nakshatra_step_days)
    t, values = find_discrete(t0, t1, transition_fn, num=nakshatra_num)

    transition_times = [(ti, vi)  for ti, vi in zip(t, values)]

    nakshatras_for_day: List[NakshatraTransition] = []

    timezone_info = ZoneInfo(timezone)
    for i, (ti, vi) in enumerate(transition_times):
        nakshatra_start_utc = ti.utc_datetime()
        nakshatra_start_tz: datetime = nakshatra_start_utc.astimezone(timezone_info)
        nakshatra_end_tz: datetime | None = None
        nakshatra = Nakshatra.from_id(vi + 1)
        if i + 1 < len(transition_times):
            end_time, _ = transition_times[i + 1]
            nakshatra_end_utc = end_time[0].utc_datetime() if isinstance(end_time, ndarray) else end_time.utc_datetime()
            nakshatra_end_tz = nakshatra_end_utc.astimezone(timezone_info)
        nakshatras_for_day.append(NakshatraTransition(
            nakshatra = nakshatra,
            start_time=nakshatra_start_tz,
            end_time= nakshatra_end_tz
        ))

    return nakshatras_for_day


def get_nakshatra_transition_for_date(
    date: date, timezone: str, tuning: AstronomyTuning = AstronomyTuning()
) -> List[NakshatraTransition]:
    """Nakshatra transitions whose start falls within *date* (local midnight to
    23:59:59.999999). Thin wrapper unpacking *tuning* so the cached core keeps
    hashable args."""
    return _get_nakshatra_transition_for_date(
        date, timezone,
        tuning.nakshatra_epsilon, tuning.nakshatra_step_days, tuning.nakshatra_num,
    )


def calc_nakshatra_transition_for_date(
    date: date, timezone: str, tuning: AstronomyTuning = AstronomyTuning()
):
    # A nakshatra rarely starts and ends on the same calendar day, so the day's
    # transitions are stitched from a window of nearby days and then filtered to
    # those overlapping this day. The window is date-2..date+2, not just date±1:
    # a nakshatra lasts ~1.0-1.13 days, so a single long one can span a whole
    # calendar day, leaving that day with zero transition *starts*. date-2 is
    # then needed to pick up a transition still active at this day's 00:00, and
    # date+2 to give the last transition of this day a valid end_time via
    # stitching. Two consecutive start-less days would need one nakshatra
    # spanning >2 days, which cannot happen, so ±2 is always sufficient.
    total_transitions = [
        t
        for offset in (-2, -1, 0, 1, 2)
        for t in get_nakshatra_transition_for_date(
            date + timedelta(days=offset), timezone, tuning
        )
    ]

    tzinfo = ZoneInfo(timezone)
    day_start = datetime.combine(date, time.min, tzinfo= tzinfo)
    day_end = datetime.combine(date, time.max, tzinfo= tzinfo)

    for i, transition in enumerate(total_transitions):
        if i + 1 < len(total_transitions):
            transition.end_time = total_transitions[i + 1].start_time

    final_transitions = [transition for transition in total_transitions if transition.start_time <= day_end and (transition.end_time is not None and transition.end_time >= day_start)]

    return final_transitions


