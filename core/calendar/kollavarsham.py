from datetime import date, timedelta
from functools import lru_cache
from typing import Dict, Any

from pydantic import BaseModel

from core.astronomy.calculations import (
    get_sun_sidereal_longitude,
)

from core.constants import (
    DEFAULT_TIMEZONE,
    MALAYALAM_MONTH_ML,
)

from core.astronomy.sunrise_sunset import get_sunrise_sunset
from utils.malayalam_masa import MalayalamMasa

MALAYALAM_MONTHS = [
    "Medam",
    "Edavam",
    "Mithunam",
    "Karkidakam",
    "Chingam",
    "Kanni",
    "Thulam",
    "Vrischikam",
    "Dhanu",
    "Makaram",
    "Kumbham",
    "Meenam"
]

class KollavarshamDate(BaseModel):
    date: date
    kv_day: int
    kv_month: int
    kv_year: int
    kv_month_name_en: str
    kv_month_name_ml: str


def get_raasi(longitude: float) -> int:
    """
    Convert sidereal longitude to raasi index.
    """
    EPSILON = 1e-6
    normalized = (longitude - EPSILON) % 360
    return int(normalized // 30)


@lru_cache(maxsize=1000)
def get_sunset_raasi(
    dt: date,
    latitude: float,
    longitude: float,
    timezone: str = DEFAULT_TIMEZONE
) -> int:
    """
    Get Sun's raasi at local sunset.
    """

    _, sunset = get_sunrise_sunset(
        date=dt,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
    )


    longitude = get_sun_sidereal_longitude(
        localdt=sunset.replace(tzinfo=None),
        timezone=timezone
    )

    return get_raasi(longitude)


@lru_cache(maxsize=1000)
def get_kollavarsham_date(
    dt: date,
    latitude: float,
    longitude: float,
    timezone: str = DEFAULT_TIMEZONE
) -> KollavarshamDate:


    # Today's raasi at sunset
    today_raasi = get_sunset_raasi(
        dt=dt,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude
    )

    # The Malayalam day is the count of sunsets since the Sun entered the current
    # raasi (the Sankranti). The sunset-raasi is constant within a month and changes
    # exactly at the month boundary, so instead of walking backwards one day at a time
    # we binary-search for the largest offset `k` (a Malayalam month is < 32 days) whose
    # sunset-raasi still equals today's. `malayalam_day` is then `k + 1`.
    lo, hi = 0, 32
    while lo < hi:
        mid = (lo + hi + 1) // 2
        mid_raasi = get_sunset_raasi(
            dt=dt - timedelta(days=mid),
            latitude=latitude,
            longitude=longitude,
            timezone=timezone
        )
        if mid_raasi == today_raasi:
            lo = mid
        else:
            hi = mid - 1

    malayalam_day = lo + 1


    # Kollam Era year starts at Chingam
    if today_raasi >= 4:
        kollam_year = dt.year - 824
    else:
        kollam_year = dt.year - 825

    malayalam_masa = MalayalamMasa.from_id(today_raasi + 1)

    # Current solar longitude
    return KollavarshamDate(
        date= dt,
        kv_year= kollam_year,
        kv_month= malayalam_masa.id,
        kv_day= malayalam_day,
        kv_month_name_en=malayalam_masa.en,
        kv_month_name_ml=malayalam_masa.ml
    )

