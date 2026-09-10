from datetime import date, timedelta
from functools import lru_cache
from typing import Dict

from app.core.astronomy.calculations import (
    get_sun_sidereal_longitude,
)

from app.core.astronomy.constants import (
    DEFAULT_TIMEZONE,
)

from app.core.astronomy.sunrise_sunset import get_sunrise_sunset
from app.core.kollavarsham.kollavarsham_models import KollavarshamDate
from app.core.kollavarsham.enums.masa import MalayalamMasa


# A Malayalam solar month is <32 days; both the per-day binary search below and
# the range-batched forward pass rely on this bound.
_MAX_MALAYALAM_MONTH_DAYS = 32


def get_raasi(longitude: float, epsilon: float = 1e-6) -> int:
    """
    Convert sidereal longitude to raasi index.
    """
    normalized = (longitude - epsilon) % 360
    return int(normalized // 30)


# ~2 entries/day during a generation sweep (the backward masa-start walk), so
# 4000 keeps ~5 years of a contiguous regeneration resident; LRU still retains
# the recent days a linear sweep reuses beyond that.
@lru_cache(maxsize=4000)
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
    lo, hi = 0, _MAX_MALAYALAM_MONTH_DAYS
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


    return _build_kollavarsham_date(dt, today_raasi, malayalam_day)


def _build_kollavarsham_date(dt: date, raasi: int, malayalam_day: int) -> KollavarshamDate:
    # Kollam Era year starts at Chingam (raasi index 4), which falls in mid-August.
    # A Kollam year spans Chingam..Karkidakam and straddles two Gregorian years:
    # its Chingam..Dhanu months fall in Aug-Dec of Gregorian year `Y` (`Y - 824`)
    # and its Makaram..Karkidakam months fall in Jan-Aug of `Y + 1` (`Y - 825`).
    # Dhanu straddles the Dec/Jan boundary, so the Gregorian month disambiguates
    # its December (`-824`) from its January tail (`-825`).
    if 4 <= raasi <= 8 and dt.month >= 8:
        kollam_year = dt.year - 824
    else:
        kollam_year = dt.year - 825

    malayalam_masa = MalayalamMasa.from_id(raasi + 1)

    return KollavarshamDate(
        date=dt,
        kv_year=kollam_year,
        kv_month=malayalam_masa.id,
        kv_day=malayalam_day,
    )


def get_kollavarsham_dates_for_range(
    start: date,
    end: date,
    latitude: float,
    longitude: float,
    timezone: str = DEFAULT_TIMEZONE,
    epsilon: float = 1e-6,
) -> Dict[date, KollavarshamDate]:
    """Bulk equivalent of calling :func:`get_kollavarsham_date` once per day in
    ``[start, end]`` (inclusive).

    :func:`get_kollavarsham_date` finds ``malayalam_day`` with an O(log 32)
    binary search per call, each step calling the ``lru_cache``d
    :func:`get_madhyahnam_raasi` -- so a full year already gets its raasi
    *values* from cache on repeat days, but still pays ~5-6 Python-level calls
    and comparisons *per day* to re-derive a count that, within one Malayalam
    month, is simply "yesterday's count + 1".

    This instead walks the range once, in order, incrementing a running day
    count and resetting it to 1 whenever the raasi changes from the previous
    day -- O(1) *Python-level* work per day instead of O(log 32), on top of
    the same per-day ``get_madhyahnam_raasi`` calls either approach needs.

    Padded ``_MAX_MALAYALAM_MONTH_DAYS`` days before ``start``: a Malayalam
    month is always shorter than that, so at least one genuine raasi change
    (a real month boundary) is guaranteed inside the padding -- from that
    reset onward, the running count is exactly right for every day from
    ``start`` through ``end``, even though the padding days themselves may
    undercount (their preceding raasi run is unknown and irrelevant, since
    they are not part of the returned result).
    """
    padded_start = start - timedelta(days=_MAX_MALAYALAM_MONTH_DAYS)

    result: Dict[date, KollavarshamDate] = {}
    running_day = 0
    prev_raasi = None
    d = padded_start
    while d <= end:
        raasi = get_madhyahnam_raasi(
            dt=d, latitude=latitude, longitude=longitude, timezone=timezone, epsilon=epsilon
        )
        running_day = running_day + 1 if raasi == prev_raasi else 1
        prev_raasi = raasi
        if d >= start:
            result[d] = _build_kollavarsham_date(d, raasi, running_day)
        d += timedelta(days=1)
    return result

