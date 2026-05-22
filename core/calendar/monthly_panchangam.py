from datetime import date
from typing import Any, Dict
import calendar
from api.routes import panchangam
from core.astronomy.nakshatra_transition import get_nakshatra_transition_for_date
from core.astronomy.sunrise_sunset import get_sunrise_sunset
from core.astronomy.thithi_transition import get_thithi_transition_by_date
from core.calendar.panchangam import PanchangamData, get_panchangam, get_panchangam_data
from utils.lifespan import PANCHANGAM_CACHE

cal = calendar.Calendar(firstweekday=6)


def get_monthly_panchangam(
    year: int,
    month: int,
    latitude_degrees: float,
    longitude_degrees: float,
    timezone: str,
)-> Dict[date, PanchangamData]:

    data = {}
    #print(min(PANCHANGAM_CACHE.keys()))
    #print(max(PANCHANGAM_CACHE.keys()))
    for day in cal.itermonthdates(year, month):
        panchangam_data = PANCHANGAM_CACHE.get(day)
        #panchangam_data = None # uncomment to ignore cached data
        if panchangam_data is None:
            panchangam_data = get_panchangam_data(day)
            PANCHANGAM_CACHE[day] = panchangam_data

        data[day] = panchangam_data


    return data


def get_monthly_panchangam_2(
        year: int, 
        month: int, 
        latitude_degrees: float,
        longitude_degrees: float,
        timezone: str,
    )-> Dict[str,Any]:
    data = {}
    for day in cal.itermonthdates(year, month):
        panchangam = {}
        sunrise_dt, sunset_dt = get_sunrise_sunset(
                date =day,
        )
        localdt = sunrise_dt.replace(tzinfo=None)
        panchangam = get_panchangam(
            localdt=localdt,
            sunrise_dt=sunrise_dt,
            sunset_dt = sunset_dt,
            latitude=latitude_degrees,
            longitude=longitude_degrees,
            timezone=timezone
        )
        data[day.isoformat()] = panchangam
    print(f"get_sunrise_sunset_cache: {get_sunrise_sunset.cache_info()}")
    print(f"get_thithi_transition_by_date: {get_thithi_transition_by_date.cache_info()}")
    print(f"get_nakshatra_transition_for_date: {get_nakshatra_transition_for_date.cache_info()}")
    return data
