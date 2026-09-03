from datetime import datetime
from functools import lru_cache
import numpy as np
import pytz
from pytz.exceptions import Error
from skyfield.api import Time
from skyfield.framelib import ecliptic_frame
from app.core.astronomy.ayanamsa import get_ayanamsa
import pytz
from .ephemeris import sun, moon, earth, ts


def get_time(localdt: datetime, timezone: str)-> Time: 
    # Date: May 7, 2026, 6:00 AM IST
    tz = pytz.timezone(timezone)
    local_time = tz.localize(localdt)
    utc_time = local_time.astimezone(pytz.UTC)
    t = ts.utc(utc_time.year, utc_time.month, utc_time.day,
            utc_time.hour, utc_time.minute, utc_time.second)
    return t


def get_tropical_longitude( t: Time, body: str) -> float:
    pos = None
    if body == 'moon':
        pos = earth.at(t).observe(moon).apparent().frame_latlon(ecliptic_frame) #pyright: ignore
    elif body == 'sun':
        pos = earth.at(t).observe(sun).apparent().frame_latlon(ecliptic_frame) #pyright: ignore
    else:
        raise Error("Invalid body. body should be 'moon' or 'sun'")
    tropical_longitude = float(pos[1].degrees) % 360
    return tropical_longitude


def get_sidereal_longitude_from_time(
    t: Time,
    body: str) -> float:
    tropical_longitude = get_tropical_longitude(
        t=t,
        body=body
    )
    dt = t.utc_datetime()

    if isinstance(dt, np.ndarray):
        raise ValueError("Time became vector inside Skyfield chain")
    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour

    ayanamsa = get_ayanamsa(year = year, month =  month, day=day, hour=hour)
    
    return (tropical_longitude - ayanamsa) % 360

def get_sidereal_longitude(
    localdt: datetime,
    timezone: str,
    body: str) -> float:
    t = get_time(localdt, timezone)
    tropical_longitude = get_tropical_longitude(
        t=t,
        body=body
    )
    dt = t.utc_datetime()
    year = dt[0].year if isinstance(dt, np.ndarray)  else dt.year
    month = dt[0].month if isinstance(dt, np.ndarray)  else dt.month
    day = dt[0].day if isinstance(dt, np.ndarray)  else dt.day
    hour = dt[0].hour if isinstance(dt, np.ndarray)  else dt.hour

    ayanamsa = get_ayanamsa(year = year, month =  month, day=day, hour=hour)
    
    return (tropical_longitude - ayanamsa) % 360

def get_moon_sidereal_longitude(
    localdt: datetime,
    timezone: str
)-> float:
    return get_sidereal_longitude(localdt=localdt, timezone=timezone, body= "moon")

@lru_cache(maxsize=1000)
def get_sun_sidereal_longitude(
    localdt: datetime,
    timezone: str
    ):
    return get_sidereal_longitude(localdt=localdt, timezone=timezone, body= "sun")
