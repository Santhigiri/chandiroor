from datetime import datetime, time
from time import perf_counter
from typing import Any, Dict, Optional
import pytz
from panchangam_astronomy.calculations import get_sun_sidereal_longitude, get_time
from panchangam_astronomy.nakshatra import get_duration_from_sunrise, get_nakshatra
from panchangam_astronomy.nakshatra_transition import calc_nakshatra_transition_for_date
from panchangam_astronomy.sunrise_sunset import get_sunrise_sunset
from panchangam_astronomy.thithi import get_thithi
from panchangam_astronomy.enums.thithi import Thithi
from panchangam_astronomy.pournami import is_poornima_live
from panchangam_astronomy.thithi_transition import calc_thithi_transition_for_date
from panchangam_astronomy.tuning import AstronomyTuning
from app.core.calendar.kollavarsham import get_kollavarsham_date
from datetime import date
from panchangam_astronomy.constants import DEFAULT_TIMEZONE, Coordinates
from app.schemas.location import LocationInfo
from app.schemas.panchangam_data import PanchangamData
from app.utils.location import Location

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
    timezone: str = DEFAULT_TIMEZONE,
    tuning: AstronomyTuning = AstronomyTuning(),
    instant: Optional[datetime] = None,
):
    kv = get_kollavarsham_date(
        dt = localdt,
        latitude = latitude,
        longitude = longitude,
        timezone = timezone,
        epsilon = tuning.kollavarsham_epsilon)
    thithi_transitions = calc_thithi_transition_for_date(localdt, timezone, tuning)
    nakshatra_transitions = calc_nakshatra_transition_for_date(localdt, timezone, tuning)
    sunrise, sunset = get_sunrise_sunset(localdt, latitude, longitude, timezone)
    # The thithi/nakshatra "of the day" is the one active at sunrise, unless the
    # caller asked for an arbitrary instant (e.g. the Starfinder "what's active
    # right now, anywhere" query). Both transition lists were just computed for
    # this day, so derive it from them instead of doing another ephemeris
    # evaluation at the eval instant.
    eval_instant = instant if instant is not None else sunrise
    thithi = _active_at(thithi_transitions, eval_instant).thithi
    nakshatra = _active_at(nakshatra_transitions, eval_instant).nakshatra
    nazhika_from_sunrise = get_duration_from_sunrise(
        nakshatra=nakshatra,
        nakshatra_transitions=nakshatra_transitions,
        sunrise=sunrise
    )
    # Resolve which known location these coordinates belong to so the response is
    # self-describing. Unknown coordinates (an ad-hoc lat/long) leave it unset.
    try:
        location = LocationInfo.from_location(Location.from_coords(latitude, longitude))
    except KeyError:
        location = None
    panchangam_data = PanchangamData(
        date= localdt,
        kv=kv,
        thithi_transitions= thithi_transitions,
        nakshatra_transitions= nakshatra_transitions,
        thithi = thithi,
        nakshatra = nakshatra,
        nazhika_from_sunrise=nazhika_from_sunrise,
        sunrise = sunrise,
        sunset = sunset,
        location = location,
    )

    # santhigiri_significant_dates are overlaid by PanchangamService from the
    # editable DB event definitions (see core/calendar/santhigiri_significant_dates.py);
    # get_panchangam_data stays pure and returns an empty list here.
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
    thithi: Thithi = get_thithi(localdt=localdt, timezone=timezone)
    sun_sidereal_longitude = get_sun_sidereal_longitude(localdt=localdt, timezone=timezone)

    thithi_transition = calc_thithi_transition_for_date(localdt.date(), timezone=timezone)

    nakshatra_transition = calc_nakshatra_transition_for_date(localdt.date(),timezone)

    is_pournami: bool = is_poornima_live(localdt=localdt, timezone=timezone)
    kv = get_kollavarsham_date(dt=localdt.date(), latitude=latitude, longitude=longitude, timezone=timezone)
    end = perf_counter()
    print(f"Took {end - start:.4f} seconds")
    return {
        "date": localdt.astimezone(tz=pytz.timezone(timezone)),
        "calculated_ml_day": kv.kv_day,
        "calculated_ml_month": kv.kv_month_name_ml,
        "calculated_ml_year": kv.kv_year,
        "nakshatra": nakshatra.name,
        "nakshatra_transitions": nakshatra_transition,
        "thithi": thithi.name,
        "thithi_transitions": thithi_transition,
        "sunrise": sunrise_dt.time().isoformat(timespec="minutes"),
        "sunset": sunset_dt.time().isoformat(timespec="minutes"),
        "is_pournami": is_pournami,
        "sun_sidereal_longitude": sun_sidereal_longitude,
        "moon_sidereal_longitude": moon_sidereal_longitude
    }

