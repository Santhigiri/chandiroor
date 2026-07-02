from datetime import datetime, time
from time import perf_counter
from typing import Any, Dict
import pytz
from core.astronomy.calculations import get_sun_sidereal_longitude, get_time
from core.astronomy.nakshatra import get_duration_from_sunrise, get_nakshatra
from core.astronomy.nakshatra_transition import  calc_nakshatra_transition_for_date, get_nakshatra_id
from core.astronomy.sunrise_sunset import get_sunrise_sunset
from core.astronomy.thithi import get_thithi
from core.astronomy.pournami import is_poornima
from core.astronomy.thithi_transition import   calc_thithi_transition_for_date, get_thithi_id, get_thithi_transition
from core.calendar.kollavarsham import get_kollavarsham_date
from datetime import date
from core.constants import DEFAULT_TIMEZONE, Coordinates
from schemas.panchangam_data import PanchangamData

def _active_at(transitions, instant):
    """Return the transition whose [start_time, end_time) interval contains `instant`.

    Falls back to the nearest edge transition if `instant` lies just outside the
    covered range (e.g. rounding at a day boundary). Assumes `transitions` is
    non-empty and ordered by start_time.
    """
    for transition in transitions:
        if transition.start_time <= instant and (
            transition.end_time is None or instant < transition.end_time
        ):
            return transition
    # instant precedes the first interval -> first; otherwise -> last
    if instant < transitions[0].start_time:
        return transitions[0]
    return transitions[-1]


def get_panchangam_data(
    localdt: date,
    latitude: float = Coordinates.SG_LATITUDE,
    longitude: float = Coordinates.SG_LONGITUDE,
    timezone: str = DEFAULT_TIMEZONE
):
    kv = get_kollavarsham_date(
        dt = localdt,
        latitude = latitude,
        longitude = longitude,
        timezone = timezone)
    thithi_transitions = calc_thithi_transition_for_date(localdt, timezone)
    nakshatra_transitions = calc_nakshatra_transition_for_date(localdt, timezone)
    sunrise, sunset = get_sunrise_sunset(localdt, latitude, longitude, timezone)
    is_pournami = is_poornima(datetime.combine(localdt, time.min),timezone)
    # The thithi/nakshatra "of the day" is the one active at sunrise. Both transition
    # lists were just computed for this day, so derive it from them instead of doing
    # two more ephemeris evaluations at sunrise.
    thithi = _active_at(thithi_transitions, sunrise).thithi
    nakshatra = _active_at(nakshatra_transitions, sunrise).nakshatra
    nazhika_from_sunrise = get_duration_from_sunrise(
        nakshatra=nakshatra,
        nakshatra_transitions=nakshatra_transitions,
        sunrise=sunrise
    )
    panchangam_data = PanchangamData(
        date= localdt,
        kv=kv,
        thithi_transitions= thithi_transitions,
        nakshatra_transitions= nakshatra_transitions,
        thithi = thithi,
        nakshatra = nakshatra,
        nazhika_from_sunrise=nazhika_from_sunrise,
        sunrise = sunrise,
        sunset = sunset
    )

    #santhigiri_significant_dates = get_santhigiri_significant_dates_without_occurances(panchangam_data)

    #panchangam_data.santhigiri_significant_dates = santhigiri_significant_dates

    return panchangam_data


def get_panchangam(
    localdt: datetime,
    sunrise_dt: datetime,
    sunset_dt: datetime,
    latitude: float,
    longitude: float,
    timezone: str = 'Asia/Kolkata'
    )->Dict[str,Any]:
    #TODO: calculate and return all values as json
    start = perf_counter()
    nakshatra, moon_sidereal_longitude = get_nakshatra(localdt= localdt,timezone=timezone)
    thithi: str = get_thithi(localdt=localdt, timezone=timezone)
    sun_sidereal_longitude = get_sun_sidereal_longitude(localdt=localdt, timezone=timezone)

    thithi_transition = calc_thithi_transition_for_date(localdt.date(), timezone=timezone)

    nakshatra_transition = calc_nakshatra_transition_for_date(localdt.date(),timezone)

    is_pournami: bool = is_poornima(localdt=localdt, timezone=timezone)
    kv = get_kollavarsham_date(dt=localdt.date(), latitude=latitude, longitude=longitude, timezone=timezone)
    end = perf_counter()
    print(f"Took {end - start:.4f} seconds")
    return {
        "date": localdt.astimezone(tz=pytz.timezone(timezone)),
        "calculated_ml_day": kv.kv_day,
        "calculated_ml_month": kv.kv_month_name_ml,
        "calculated_ml_year": kv.kv_year,
        "nakshatra": nakshatra,
        "nakshatra_transitions": nakshatra_transition,
        "thithi": thithi,
        "thithi_transitions": thithi_transition,
        "sunrise": sunrise_dt.time().isoformat(timespec="minutes"),
        "sunset": sunset_dt.time().isoformat(timespec="minutes"),
        "is_pournami": is_pournami,
        "sun_sidereal_longitude": sun_sidereal_longitude,
        "moon_sidereal_longitude": moon_sidereal_longitude
    }

