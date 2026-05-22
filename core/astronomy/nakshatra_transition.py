from datetime import date, datetime, time, timedelta
from functools import lru_cache
from typing import List
from zoneinfo import ZoneInfo

import numpy as np
from numpy import ndarray
from pydantic import BaseModel, field_serializer
from skyfield.almanac import find_discrete
from skyfield.api import Time
from core.astronomy.calculations import get_time
from core.astronomy.ephemeris import ephem, ts

from core.astronomy.thithi_transition import get_sidereal_longitude_from_time
from utils.nakshatra import Nakshatra
from utils.utils import calc_nakshatra_from_lon, calc_nakshatra_id_from_lon


class NakshatraTransition(BaseModel):
    name: str
    nakshatra: Nakshatra
    start_time: datetime
    end_time: datetime | None

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

    # scalar case
    print(f"TYPE OF MOON_LONG: {type(moon_lon)}")
    return moon_lon // (360 / 27)



@lru_cache(maxsize=1000)
def get_nakshatra_transition_for_date(date: date, timezone: str):
    print(f"CALCULATING NAKSHATRA TRANSITION FOR DATE: {date}")
    t0 = get_time(datetime.combine(date, time.min), timezone)
    t1 = get_time(datetime.combine(date, time.max), timezone)

    get_nakshatra_transition.step_days = 0.0007 #pyright: ignore

    t, values = find_discrete(t0, t1, get_nakshatra_transition)

    transition_times = [(ti, vi)  for ti, vi in zip(t, values)]

    nakshatras_for_day: List[NakshatraTransition] = []

    timezone_info = ZoneInfo(timezone)
    for i, (ti, vi) in enumerate(transition_times):
        nakshatra_start_utc = ti.utc_datetime()
        nakshatra_start_tz: datetime = nakshatra_start_utc.astimezone(timezone_info)
        nakshatra_end_tz: datetime | None = None
        nakshatra = Nakshatra.from_id(int(vi + 1))
        print(f"=========={nakshatra.en} ==========")
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
    
    return nakshatras_for_day


def calc_nakshatra_transition_for_date(date: date, timezone: str):
    total_transitions: List[NakshatraTransition] = []
    current_day_transitions = get_nakshatra_transition_for_date(date, timezone)
    total_transitions += current_day_transitions

    previous_day = date - timedelta(days=1)
    previous_day_transitions = get_nakshatra_transition_for_date(previous_day, timezone)

    if len(previous_day_transitions) == 0:
        print("========PREVIOUS DAY TRANSITIONS IS EMPTY================")
        previous_day = date - timedelta(days=2)
        previous_day_transitions = get_nakshatra_transition_for_date(previous_day, timezone)

    if len(previous_day_transitions) == 0:
        print("========PREVIOUS DAY TRANSITIONS IS EMPTY AGAINN================")

    total_transitions = previous_day_transitions + total_transitions

    next_day = date + timedelta(days = 1)
    next_day_transitions = get_nakshatra_transition_for_date(next_day, timezone)

    total_transitions += next_day_transitions

    for i, transition in enumerate(total_transitions):
        if i + 1 < len(total_transitions):
            transition.end_time = total_transitions[i + 1].start_time

    final_transitions = [transition for transition in total_transitions if transition.start_time.date() <= date and (transition.end_time is not None and transition.end_time.date() >= date)]
    for transition in final_transitions:
        print(f"{transition.nakshatra.en} - {transition.start_time} -> {transition.end_time}")

    return final_transitions



@lru_cache(maxsize=1000)
def calc_nakshatra_transition(date: date, timezone: str):
    t0 = ts.utc(date.year, date.month, date.day -1 , 0, 0, 0)
    t1 = ts.utc(date.year, date.month, date.day + 1 , 23, 59 , 59)

    get_nakshatra_transition.step_days = 0.0007 #pyright: ignore

    t, values = find_discrete(t0, t1, get_nakshatra_transition)

    transition_times = [ti for ti, vi in zip(t, values) if vi == 1]


    nakshatras_for_day: List = []

    timezone_info = ZoneInfo(timezone)
    for i, ti in enumerate(transition_times):
        if i + 1 >= len(transition_times):
            break
        nakshatra_start_utc = ti.utc_datetime()
        nakshatra_start_tz: datetime = nakshatra_start_utc.astimezone(timezone_info)
        nakshatra_end_tz: datetime | None = None
        nakshatra_id = get_nakshatra_id(ts.from_datetime(nakshatra_start_utc) + timedelta(minutes=10))
        nakshatra = Nakshatra.from_id(nakshatra_id)
        end_time = transition_times[i + 1]
        nakshatra_end_utc = end_time[0].utc_datetime() if isinstance(end_time, ndarray) else end_time.utc_datetime()
        nakshatra_end_tz = nakshatra_end_utc.astimezone(timezone_info)
        nakshatras_for_day.append(NakshatraTransition(
            name = nakshatra.en,
            nakshatra = nakshatra,
            start_time = nakshatra_start_tz,
            end_time = nakshatra_end_tz
        ))
    
    return nakshatras_for_day

