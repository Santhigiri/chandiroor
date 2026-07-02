from datetime import date, datetime, time, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from numpy import ndarray
from pydantic import BaseModel, field_serializer
from skyfield.searchlib import find_discrete
from skyfield.api import Time
from core.astronomy.calculations import get_time

from core.astronomy.thithi_transition import get_sidereal_longitude_from_time
from core.constants import NAKSHATRA_TRANSITION_STEP_DAYS
from utils.nakshatra import Nakshatra
from utils.utils import calc_nakshatra_from_lon, calc_nakshatra_id_from_lon


class NakshatraTransition(BaseModel):
    name: str
    nakshatra: Nakshatra
    start_time: datetime
    end_time: Optional[datetime]

    @field_serializer('nakshatra')
    def ser_nakshatra(self, n: Nakshatra):
        return n.to_dict()


def get_nakshatra_id(t: Time)-> int:
    moon_sidereal_longitude = get_sidereal_longitude_from_time(t, "moon")
    nakshatra_id = calc_nakshatra_id_from_lon(moon_sidereal_longitude)
    return nakshatra_id

def get_nakshatra(t: Time):
    moon_sidereal_longitude = get_sidereal_longitude_from_time(t, "moon")
    nakshatra = calc_nakshatra_from_lon(moon_sidereal_longitude)
    return nakshatra


def get_nakshatra_transition(t: Time):
    moon_lon = get_sidereal_longitude_from_time(t, "moon")

    eps = 1e-8
    idx = ((moon_lon + eps) / (360/27)).astype(int)

    #for ml, i, ts in zip(moon_lon, idx, t):
    #    if ts.utc_datetime().date().day == 13:
    #        print(f"{ml} -> {i} at {ts.utc_datetime()}")
        #pass

    #return moon_lon % (360/27)

    return idx % 27

get_nakshatra_transition.step_days = NAKSHATRA_TRANSITION_STEP_DAYS #pyright: ignore adjust value to fetch all transition_times


#@lru_cache(maxsize=1000)
def get_nakshatra_transition_for_date(date: date, timezone: str):
    t0 = get_time(datetime.combine(date, time.min), timezone)
    t1 = get_time(datetime.combine(date, time.max), timezone)


    #print(
    #    "date=", date,
    #    "t0=", t0.utc_datetime(),
    #    "t1=", t1.utc_datetime()
    #)


    t, values = find_discrete(t0, t1, get_nakshatra_transition, num = 12)

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

def find_previous_transitions(date: date, timezone: str):
    transitions = []
    for i in range(1,4):
        offset_date = date - timedelta(days=i)
        transitions = get_nakshatra_transition_for_date(
            offset_date,
            timezone
        )

        if len(transitions) > 0:
            break

    return transitions



def find_next_transitions(date: date, timezone: str):
    transitions = []
    for i in range(1,4):
        offset_date = date + timedelta(days=i)
        transitions = get_nakshatra_transition_for_date(
            offset_date,
            timezone
        )

        if len(transitions) > 0:
            break

    return transitions


def calc_nakshatra_transition_for_date(date: date, timezone: str):
    total_transitions: List[NakshatraTransition] = []
    current_day_transitions = get_nakshatra_transition_for_date(date, timezone)
    previous_transitions = find_previous_transitions(date, timezone)
    next_transitions = find_next_transitions(date, timezone)

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


