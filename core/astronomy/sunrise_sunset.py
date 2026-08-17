from typing import Literal, NamedTuple, Optional, Tuple
from functools import lru_cache
from skyfield.api import Topos
from skyfield import almanac
from datetime import date, datetime
import pytz
from core.constants import DEFAULT_TIMEZONE, Coordinates
from core.astronomy.ephemeris import ephem, ts, sun, earth

SunriseSunsetStatus = Literal["normal", "polar_day", "polar_night"]


class SunriseSunsetResult(NamedTuple):
    """Result of a sunrise/sunset lookup that may have no rising/setting event.

    status is "normal" when both sunrise and sunset are populated. Otherwise
    sunrise and sunset are both None and status says why: "polar_day" (the
    sun stayed up all day) or "polar_night" (the sun stayed down all day).
    """

    sunrise: Optional[datetime]
    sunset: Optional[datetime]
    status: SunriseSunsetStatus


@lru_cache(maxsize=1000)
def get_sunrise_sunset_status(
        date: date,
        latitude: float = round(Coordinates.SG_LATITUDE, 3),
        longitude: float = round(Coordinates.SG_LONGITUDE, 3),
        timezone: str = DEFAULT_TIMEZONE) -> SunriseSunsetResult:
    """
    Calculate sunrise and sunset times for a given date, location, and timezone.

    Unlike get_sunrise_sunset(), this never raises for a missing rising/setting
    event — at high latitudes the sun can stay continuously above or below the
    horizon for the whole day (polar day/night). In that case the returned
    result has sunrise=None, sunset=None, and status set accordingly.

    Args:
        date (date): The date for which to calculate sunrise/sunset.
        latitude (float): Latitude in degrees.
        longitude (float): Longitude in degrees.
        timezone (str): The timezone (e.g., 'Asia/Kolkata') for local time conversion.

    Returns:
        SunriseSunsetResult: (sunrise_local, sunset_local, status).
    """
    horizon = 0.0  # for traditional panchang, the sun's horizon is taken as 0 degrees

    # Define the time range for the day (UTC)
    t0 = ts.utc(date.year, date.month, date.day)
    t1 = ts.utc(date.year, date.month, date.day + 1)

    location = Topos(latitude_degrees=latitude, longitude_degrees=longitude)

    # Find sunrise and sunset times (UTC)
    t, y = almanac.find_discrete(t0, t1, almanac.risings_and_settings(
        ephemeris=ephem,
        target=sun,
        topos=location,
        horizon_degrees=horizon
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
        return SunriseSunsetResult(sunrise_local, sunset_local, "normal")

    # No rising/setting event in the UTC day window: the sun stayed continuously
    # above or below the horizon (polar day/night). Sample its altitude at
    # midday to say which.
    midday = ts.utc(date.year, date.month, date.day, 12)
    observer = earth + location
    altitude, _, _ = observer.at(midday).observe(sun).apparent().altaz()

    status: SunriseSunsetStatus = "polar_day" if altitude.degrees > horizon else "polar_night"
    return SunriseSunsetResult(None, None, status)


def get_sunrise_sunset(
        date: date,
        latitude: float = round(Coordinates.SG_LATITUDE, 3),
        longitude: float = round(Coordinates.SG_LONGITUDE, 3),
        timezone: str = DEFAULT_TIMEZONE) -> Tuple[datetime, datetime]:
    """
    Calculate sunrise and sunset times for a given date, location, and timezone.

    Args:
        date (date): The date for which to calculate sunrise/sunset.
        latitude (float): Latitude in degrees.
        longitude (float): Longitude in degrees.
        timezone (str): The timezone (e.g., 'Asia/Kolkata') for local time conversion.

    Returns:
        Tuple[datetime, datetime]: (sunrise_local, sunset_local) in the specified timezone.

    Raises:
        ValueError: If sunrise or sunset times are unavailable (polar day/night).
    """
    result = get_sunrise_sunset_status(date, latitude, longitude, timezone)

    if result.status == "normal":
        return result.sunrise, result.sunset

    if result.status == "polar_day":
        raise ValueError(
            "No sunrise or sunset on this date at this location: the sun does not "
            "set (polar day / midnight sun)."
        )
    raise ValueError(
        "No sunrise or sunset on this date at this location: the sun does not "
        "rise (polar night)."
    )
