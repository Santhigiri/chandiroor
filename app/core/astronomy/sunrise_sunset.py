from typing import Dict, Tuple, Optional
from functools import lru_cache
from skyfield.api import Topos
from skyfield import almanac
from datetime import date, datetime, timedelta
import pytz
from app.core.astronomy.constants import DEFAULT_TIMEZONE, Coordinates
from app.core.astronomy.ephemeris import ephem, ts, sun

# Unlike the Thithi/Nakshatra transition search (see
# ``core.calendar.panchangam._TRANSITION_CHUNK_DAYS``'s docstring), risings_and_settings
# uses skyfield's cheaper iau2000b nutation series, which does not show the same
# non-linear blowup for a large array -- a single whole-year find_discrete call
# actually beats a plain per-day loop outright. Benchmarking still found a mild
# sweet spot around ~90 days (chunk sizes from 30 to a full year all land within
# ~25% of each other, all roughly 8-9x faster than one call per day).
_SUNRISE_SUNSET_CHUNK_DAYS = 90


# A generation sweep produces ~2 distinct keys/day (this day plus the
# kollavarsham masa-start walk's look-back), so 4000 keeps ~5 years of a
# contiguous regeneration resident. Beyond that, LRU still retains the recent
# days a linear sweep actually reuses.
@lru_cache(maxsize=4000)
def get_sunrise_sunset(
        date: date,
        latitude: float=round(Coordinates.SG_LATITUDE,3),
        longitude: float = round(Coordinates.SG_LONGITUDE, 3),
        timezone: str = DEFAULT_TIMEZONE) -> Tuple[datetime, datetime]:
    """
    Calculate sunrise and sunset times for a given date, location, and timezone.

    Args:
        date (date): The date for which to calculate sunrise/sunset.
        location (Topos): The location (latitude, longitude) for calculations.
        timezone (str): The timezone (e.g., 'Asia/Kolkata') for local time conversion.

    Returns:
        Tuple[datetime, datetime]: (sunrise_local, sunset_local) in the specified timezone.

    Raises:
        ValueError: If sunrise or sunset times are unavailable.
    """
    horizon = 0.0 # for traditional panchang, the sun's horizon is taken as 0 degrees

    # Define the time range for the day (UTC)
    t0 = ts.utc(date.year, date.month, date.day)
    t1 = ts.utc(date.year, date.month, date.day + 1)

    location = Topos(latitude_degrees=latitude, longitude_degrees=longitude)

    # Find sunrise and sunset times (UTC)
    t, y = almanac.find_discrete(t0, t1, almanac.risings_and_settings(
        ephemeris=ephem,
        target= sun,
        topos= location,
        horizon_degrees= horizon
    ))

    # Convert to local timezone
    tz = pytz.timezone(timezone)
    sunrise_local: Optional[datetime] = None
    sunset_local: Optional[datetime] = None

    for time_utc, is_rising in zip(t, y):
        # Convert skyfield Time to Python datetime (UTC)
        utc_dt: datetime = time_utc.utc_datetime()

        local_dt = utc_dt.astimezone(tz)

        if is_rising:
            sunrise_local = local_dt
        else:
            sunset_local = local_dt

    if sunrise_local is not None and sunset_local is not None:
        return sunrise_local, sunset_local

    raise ValueError("Sunrise and sunset times unavailable for the given date and location.")


def get_sunrise_sunset_for_range(
    start: date,
    end: date,
    latitude: float = round(Coordinates.SG_LATITUDE, 3),
    longitude: float = round(Coordinates.SG_LONGITUDE, 3),
    timezone: str = DEFAULT_TIMEZONE,
) -> Dict[date, Tuple[datetime, datetime]]:
    """Bulk equivalent of calling :func:`get_sunrise_sunset` once per day in
    ``[start, end]`` (inclusive).

    Same ``find_discrete``-based rise/set search as the single-day function
    (``almanac.risings_and_settings``, the same engine used by the Thithi/
    Nakshatra transition search), but run once per
    ``_SUNRISE_SUNSET_CHUNK_DAYS``-day chunk instead of once per day -- see
    ``core.calendar.panchangam._TRANSITION_CHUNK_DAYS``'s docstring for why
    chunked rather than either "one call per day" or "one call for the whole
    range".

    Each rising/setting instant is bucketed by the *UTC* calendar day its
    search window belongs to (matching the single-day function's own [UTC
    midnight, next UTC midnight) window) before being converted to *timezone*
    -- not by the local calendar day the converted instant happens to fall on,
    which can differ from the UTC day for a non-UTC timezone.
    """
    horizon = 0.0
    location = Topos(latitude_degrees=latitude, longitude_degrees=longitude)
    tz = pytz.timezone(timezone)

    pending: Dict[date, list] = {}  # UTC day -> [sunrise_local, sunset_local]
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(end, chunk_start + timedelta(days=_SUNRISE_SUNSET_CHUNK_DAYS - 1))
        t0 = ts.utc(chunk_start.year, chunk_start.month, chunk_start.day)
        t1 = ts.utc(chunk_end.year, chunk_end.month, chunk_end.day + 1)
        t, y = almanac.find_discrete(t0, t1, almanac.risings_and_settings(
            ephemeris=ephem, target=sun, topos=location, horizon_degrees=horizon,
        ))
        for time_utc, is_rising in zip(t, y):
            utc_dt = time_utc.utc_datetime()
            d = utc_dt.date()
            local_dt = utc_dt.astimezone(tz)
            slot = pending.setdefault(d, [None, None])
            slot[0 if is_rising else 1] = local_dt
        chunk_start = chunk_end + timedelta(days=1)

    result: Dict[date, Tuple[datetime, datetime]] = {}
    d = start
    while d <= end:
        sunrise_local, sunset_local = pending.get(d, [None, None])
        if sunrise_local is None or sunset_local is None:
            raise ValueError(
                f"Sunrise and sunset times unavailable for {d} and the given location."
            )
        result[d] = (sunrise_local, sunset_local)
        d += timedelta(days=1)
    return result
