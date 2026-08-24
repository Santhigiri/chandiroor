from datetime import date, timedelta
from functools import lru_cache

from core.astronomy.calculations import (
    get_sun_sidereal_longitude,
)

from core.constants import (
    DEFAULT_TIMEZONE,
)

from core.astronomy.sunrise_sunset import get_sunrise_sunset
from core.calendar.kollavarsham_models import KollavarshamDate
from utils.malayalam_masa import MalayalamMasa


def get_raasi(longitude: float, epsilon: float = 1e-6) -> int:
    """
    Convert sidereal longitude to raasi index.
    """
    normalized = (longitude - epsilon) % 360
    return int(normalized // 30)


@lru_cache(maxsize=1000)
def get_madhyahnam_raasi(
    dt: date,
    latitude: float,
    longitude: float,
    timezone: str = DEFAULT_TIMEZONE,
    epsilon: float = 1e-6,
) -> int:
    """
    Get Sun's raasi at the end of Modyana (madhyahnam).

    The daytime (sunrise -> sunset) is split into five equal parts; Modyana is the
    third part, spanning 40%-60% of the daytime. The Kerala month-transition rule
    is: the Malayalam month begins on the day of the Sankramanam if the Sun enters
    the new raasi *before or during* Modyana, otherwise the next day. Sampling the
    Sun's raasi at the *end* of Modyana (sunrise + 3/5 of the daytime) is the exact
    realization of that rule: the raasi at that instant is the new raasi iff the
    Sankramanam occurred at or before the end of Modyana.
    """

    sunrise, sunset = get_sunrise_sunset(
        date=dt,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone,
    )

    # End of Modyana = end of the third of five equal daytime parts (the 60% point).
    madhyahnam = sunrise + (sunset - sunrise) * 3 / 5

    longitude = get_sun_sidereal_longitude(
        localdt=madhyahnam.replace(tzinfo=None),
        timezone=timezone
    )

    return get_raasi(longitude, epsilon)


@lru_cache(maxsize=1000)
def get_kollavarsham_date(
    dt: date,
    latitude: float,
    longitude: float,
    timezone: str = DEFAULT_TIMEZONE,
    epsilon: float = 1e-6,
) -> KollavarshamDate:


    # Today's raasi at madhyahnam (midday)
    today_raasi = get_madhyahnam_raasi(
        dt=dt,
        timezone=timezone,
        latitude=latitude,
        longitude=longitude,
        epsilon=epsilon,
    )

    # The Malayalam day is the count of days since the Sun entered the current
    # raasi (the Sankranti) as decided at madhyahnam. The madhyahnam-raasi is
    # constant within a month and changes exactly at the month boundary, so
    # instead of walking backwards one day at a time we binary-search for the
    # largest offset `k` (a Malayalam month is < 32 days) whose madhyahnam-raasi
    # still equals today's. `malayalam_day` is then `k + 1`.
    lo, hi = 0, 32
    while lo < hi:
        mid = (lo + hi + 1) // 2
        mid_raasi = get_madhyahnam_raasi(
            dt=dt - timedelta(days=mid),
            latitude=latitude,
            longitude=longitude,
            timezone=timezone,
            epsilon=epsilon,
        )
        if mid_raasi == today_raasi:
            lo = mid
        else:
            hi = mid - 1

    malayalam_day = lo + 1


    # Kollam Era year starts at Chingam (raasi index 4), which falls in mid-August.
    # A Kollam year spans Chingam..Karkidakam and straddles two Gregorian years:
    # its Chingam..Dhanu months fall in Aug-Dec of Gregorian year `Y` (`Y - 824`)
    # and its Makaram..Karkidakam months fall in Jan-Aug of `Y + 1` (`Y - 825`).
    # Dhanu straddles the Dec/Jan boundary, so the Gregorian month disambiguates
    # its December (`-824`) from its January tail (`-825`).
    if 4 <= today_raasi <= 8 and dt.month >= 8:
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

