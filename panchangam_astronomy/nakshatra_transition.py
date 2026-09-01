from datetime import date, datetime, time, timedelta
from typing import List
from zoneinfo import ZoneInfo

from numpy import ndarray
from skyfield.searchlib import find_discrete
from skyfield.api import Time
from panchangam_astronomy.calculations import get_time

from panchangam_astronomy.thithi_transition import get_sidereal_longitude_from_time
from panchangam_astronomy.transitions import NakshatraTransition
from panchangam_astronomy.tuning import AstronomyTuning
from panchangam_astronomy.enums.nakshatra import Nakshatra
from panchangam_astronomy.nakshatra_calc import calc_nakshatra_from_lon, calc_nakshatra_id_from_lon


def get_nakshatra_id(t: Time)-> int:
    moon_sidereal_longitude = get_sidereal_longitude_from_time(t, "moon")
    nakshatra_id = calc_nakshatra_id_from_lon(moon_sidereal_longitude)
    return nakshatra_id

def get_nakshatra(t: Time)->Nakshatra:
    moon_sidereal_longitude = get_sidereal_longitude_from_time(t, "moon")
    nakshatra = calc_nakshatra_from_lon(moon_sidereal_longitude)
    return nakshatra


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


#@lru_cache(maxsize=1000)
def get_nakshatra_transition_for_date(
    date: date, timezone: str, tuning: AstronomyTuning = AstronomyTuning()
):
    t0 = get_time(datetime.combine(date, time.min), timezone)
    t1 = get_time(datetime.combine(date, time.max), timezone)

    transition_fn = make_nakshatra_transition_fn(
        tuning.nakshatra_epsilon, tuning.nakshatra_step_days
    )
    t, values = find_discrete(t0, t1, transition_fn, num=tuning.nakshatra_num)

    transition_times = [(ti, vi)  for ti, vi in zip(t, values)]
    #print(f"===========TRANSITIONS FOR DAY {date}============")
    #for ti, vi in transition_times:
    #    print(f"{ti} => {vi}")

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
            name= nakshatra.en,
            nakshatra = nakshatra,
            start_time=nakshatra_start_tz,
            end_time= nakshatra_end_tz
        ))
        #print(
        #ti.utc_datetime(),
        #vi,
        #Nakshatra.from_id(int(vi)+1).en
        #)
    
    return nakshatras_for_day

def find_previous_transitions(
    date: date, timezone: str, tuning: AstronomyTuning = AstronomyTuning()
):
    transitions = []
    for i in range(1,4):
        offset_date = date - timedelta(days=i)
        transitions = get_nakshatra_transition_for_date(
            offset_date,
            timezone,
            tuning,
        )

        if len(transitions) > 0:
            break

    return transitions



def find_next_transitions(
    date: date, timezone: str, tuning: AstronomyTuning = AstronomyTuning()
):
    transitions = []
    for i in range(1,4):
        offset_date = date + timedelta(days=i)
        transitions = get_nakshatra_transition_for_date(
            offset_date,
            timezone,
            tuning,
        )

        if len(transitions) > 0:
            break

    return transitions


def calc_nakshatra_transition_for_date(
    date: date, timezone: str, tuning: AstronomyTuning = AstronomyTuning()
):
    total_transitions: List[NakshatraTransition] = []
    current_day_transitions = get_nakshatra_transition_for_date(date, timezone, tuning)
    previous_transitions = find_previous_transitions(date, timezone, tuning)
    next_transitions = find_next_transitions(date, timezone, tuning)

    total_transitions = previous_transitions + current_day_transitions + next_transitions

    tzinfo = ZoneInfo(timezone)
    day_start = datetime.combine(date, time.min, tzinfo= tzinfo)
    day_end = datetime.combine(date, time.max, tzinfo= tzinfo)

    #for t in total_transitions:
    #    print(f"{t.nakshatra.en} ( {t.nakshatra.id} ) => {t.start_time.ctime()}")

    for i, transition in enumerate(total_transitions):
        if i + 1 < len(total_transitions):
            transition.end_time = total_transitions[i + 1].start_time

    final_transitions = [transition for transition in total_transitions if transition.start_time <= day_end and (transition.end_time is not None and transition.end_time >= day_start)]

    return final_transitions


