from datetime import date, datetime, timedelta, time
from functools import lru_cache
from typing import Dict, List
from pytz.exceptions import Error
from skyfield.almanac import ecliptic_frame, find_discrete
from skyfield.api import Time
from skyfield.units import Angle, Distance
from app.core.astronomy.ayanamsa import get_ayanamsa
from app.core.astronomy.calculations import get_time
from zoneinfo import ZoneInfo
import numpy as np
import math
from app.core.astronomy.ephemeris import earth, sun, moon
from app.core.astronomy.transitions import ThithiTransition
from app.core.astronomy.tuning import AstronomyTuning
from app.core.astronomy.enums.thithi import Thithi


def get_tropical_longitude(t: Time, body: str) -> float | np.ndarray:
    pos: tuple[Angle, Angle, Distance] | None = None
    if body == 'moon':
        pos = earth.at(t).observe(moon).apparent().frame_latlon(ecliptic_frame) #pyright: ignore
    elif body == 'sun':
        pos = earth.at(t).observe(sun).apparent().frame_latlon(ecliptic_frame) #pyright: ignore
    else:
        raise Error("Invalid body. body should be 'moon' or 'sun'")
    tropical_longitude = pos[1].degrees
    return tropical_longitude


def get_sidereal_longitude_from_time(
    t: Time,
    body: str) -> float | np.ndarray:
    tropical_longitude = get_tropical_longitude(
        t=t,
        body=body
    )
    dt = t.utc_datetime()
    if isinstance(dt, np.ndarray):
        ayanamsa = get_ayanamsa_for_datetimes(dt)
    else:
        ayanamsa = _ayanamsa_for_date(dt.year, dt.month, dt.day)

    return (tropical_longitude - ayanamsa) % 360


@lru_cache(maxsize=8000)
def _ayanamsa_for_date(year: int, month: int, day: int) -> float:
    """Ayanamsa for a calendar day, at a fixed representative hour (noon).

    Ayanamsa changes far too slowly (~50 arcsec/year, i.e. a few thousandths of
    a degree over a whole day) for hour-of-day precision to matter, so it only
    varies per calendar day, not per sample or per hour. Cached at module
    (process) scope rather than per ``find_discrete`` call: a single range-batched
    search re-invokes its predicate many times as it refines each transition's
    bracket, and a per-call cache would recompute the same dates' ayanamsa from
    scratch on every one of those invocations.
    """
    return get_ayanamsa(year=year, month=month, day=day, hour=12.0)


def get_ayanamsa_for_datetimes(dt: np.ndarray) -> np.ndarray:
    """Ayanamsa for each element of a ``Time.utc_datetime()`` array.

    ``find_discrete`` calls its predicate with progressively narrower ``Time``
    arrays during its search -- its very first (coarsest) pass can span the
    *entire* requested window, which may be months wide once callers batch a
    whole date range into one ``find_discrete`` call instead of one per day.
    Evaluating ayanamsa once from ``dt[0]`` and broadcasting it across the
    whole array (the previous behavior) is harmless for a same-day/few-day
    window -- ayanamsa barely moves in a few hours -- but silently wrong once
    the array spans months: a sample near the end of the array would be
    ayanamsa-shifted using a value computed from the *start* of the array,
    which is enough to misclassify a sample sitting right at a Thithi/
    Nakshatra boundary and produce a spurious extra transition.

    ``pyswisseph`` has no vectorized entry point, so this evaluates the
    (process-cached) per-date ayanamsa once per unique date in *dt* rather
    than once per sample.
    """
    out = np.empty(len(dt), dtype=float)
    for i, d in enumerate(dt):
        out[i] = _ayanamsa_for_date(d.year, d.month, d.day)
    return out


def get_elongations(t: Time) -> float | np.ndarray:
    moon_sidereal_longitude = get_sidereal_longitude_from_time(t,"moon")
    sun_sidereal_longitude = get_sidereal_longitude_from_time(t, "sun")
    elongation = (moon_sidereal_longitude - sun_sidereal_longitude) % 360
    return elongation

def get_thithi(
    t: Time
)-> Thithi:
    # Thithi calculation
    elongation = get_elongations(t)
    thithi_number = math.floor(elongation / 12) + 1
    if thithi_number > 30:
        thithi_number = 30  # Amavasya
    return Thithi.from_id(thithi_number)

def make_thithi_transition_fn(step_days: float):
    """Build a fresh ``find_discrete`` predicate bound to *step_days*.

    A closure per call, not a shared module-level function with a mutated
    ``.step_days`` attribute: the old approach was a race condition once the
    step size can vary per call (e.g. concurrently regenerating two years
    with different overrides) — the mutation from one call could be read by
    another call's ``find_discrete`` before it runs.
    """

    def _thithi_transition(t: Time):
        elongation = get_elongations(t)
        return np.floor(elongation // 12).astype(int)

    _thithi_transition.step_days = step_days  # pyright: ignore adjust values to fetch all transition_times
    return _thithi_transition


@lru_cache(maxsize=1000)
def get_thithi_transition_by_date(
    date: date, timezone: str, step_days: float = 0.01, num: int = 100
) -> List[ThithiTransition]:
    transition_fn = make_thithi_transition_fn(step_days)

    t0 = get_time(datetime.combine(date, time.min), timezone)
    t1 = get_time(datetime.combine(date, time.max), timezone)

    t, values = find_discrete(t0, t1, transition_fn, num=num)

    # Filter to keep only the start of transitions (values == 1)
    transition_times = [(ti, vi) for ti, vi in zip(t, values)]

    thithis_for_day: List[ThithiTransition] = []

    # Convert UTC to IST (UTC+05:30)
    ist_timezone = ZoneInfo(timezone)
    for i, (ti, vi) in enumerate(transition_times):
        utc_start_time = ti.utc_datetime()
        ist_start_time: datetime = utc_start_time.astimezone(ist_timezone)
        ist_end_time = None
        if i + 1 != len(transition_times):
            utc_end_time, _ = transition_times[i+1]
            ist_end_time = utc_end_time.utc_datetime().astimezone(ist_timezone)
        thithi = Thithi.from_id(int(vi) + 1)
        thithis_for_day.append(ThithiTransition(
            thithi = thithi,
            start_time=ist_start_time,
            end_time=ist_end_time
        ))

    return thithis_for_day


def calc_thithi_transition_for_date(
    date: date,
    timezone: str,
    tuning: AstronomyTuning = AstronomyTuning(),
) -> List[ThithiTransition]:
    step_days, num = tuning.thithi_step_days, tuning.thithi_num
    current_day_transition: List[ThithiTransition] = get_thithi_transition_by_date(
        date, timezone, step_days, num
    )
    total_thithi_transitions: List[ThithiTransition] = current_day_transition

    previous_day = date - timedelta(days=1)
    previous_day_transition = get_thithi_transition_by_date(
        previous_day, timezone, step_days, num
    )
    total_thithi_transitions = previous_day_transition + total_thithi_transitions

    next_day = date + timedelta(days=1)
    next_day_transition = get_thithi_transition_by_date(
        next_day, timezone, step_days, num
    )

    total_thithi_transitions += next_day_transition

    for i, transition in enumerate(total_thithi_transitions):
        if i + 1 < len(total_thithi_transitions):
            transition.end_time = total_thithi_transitions[i + 1].start_time



    total_thithi_transitions = [transition for transition in total_thithi_transitions if transition.start_time.date() <= date and (transition.end_time is not None and transition.end_time.date() >= date)]

    return total_thithi_transitions


def calc_thithi_transitions_for_range(
    start: date,
    end: date,
    timezone: str,
    tuning: AstronomyTuning = AstronomyTuning(),
) -> Dict[date, List[ThithiTransition]]:
    """Same semantics as calling :func:`calc_thithi_transition_for_date` once per
    day in ``[start, end]`` (inclusive), but with a single ``find_discrete`` call
    over the whole padded range instead of one 3-day-window call per day.

    Not ``@lru_cache``d -- callers pass a range once per generation run, so
    there is no repeated-call benefit to caching, and caching by ``(start, end)``
    would not help the per-day cache hits ``get_thithi_transition_by_date``
    relies on for the single-day path anyway.
    """
    padded_start = start - timedelta(days=1)
    padded_end = end + timedelta(days=1)
    t0 = get_time(datetime.combine(padded_start, time.min), timezone)
    t1 = get_time(datetime.combine(padded_end, time.max), timezone)

    transition_fn = make_thithi_transition_fn(tuning.thithi_step_days)
    t, values = find_discrete(t0, t1, transition_fn, num=tuning.thithi_num)

    ist_timezone = ZoneInfo(timezone)
    all_transitions: List[ThithiTransition] = []
    for ti, vi in zip(t, values):
        start_time = ti.utc_datetime().astimezone(ist_timezone)
        thithi = Thithi.from_id(int(vi) + 1)
        all_transitions.append(ThithiTransition(thithi=thithi, start_time=start_time, end_time=None))
    for i in range(len(all_transitions) - 1):
        all_transitions[i].end_time = all_transitions[i + 1].start_time

    by_day: Dict[date, List[ThithiTransition]] = {}
    d = start
    while d <= end:
        by_day[d] = [
            transition
            for transition in all_transitions
            if transition.start_time.date() <= d
            and transition.end_time is not None
            and transition.end_time.date() >= d
        ]
        d += timedelta(days=1)
    return by_day

