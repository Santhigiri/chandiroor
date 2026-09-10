from datetime import datetime, time
from time import perf_counter
from typing import Any, Callable, Dict, Optional
import pytz
from app.core.astronomy.calculations import get_sun_sidereal_longitude, get_time
from app.core.astronomy.nakshatra import get_duration_from_sunrise, get_nakshatra
from app.core.astronomy.nakshatra_transition import (
    calc_nakshatra_transition_for_date,
    calc_nakshatra_transitions_for_range,
)
from app.core.astronomy.sunrise_sunset import get_sunrise_sunset, get_sunrise_sunset_for_range
from app.core.astronomy.thithi import get_thithi
from app.core.astronomy.enums.thithi import Thithi
from app.core.astronomy.pournami import is_poornima_live
from app.core.astronomy.thithi_transition import (
    calc_thithi_transition_for_date,
    calc_thithi_transitions_for_range,
)
from app.core.astronomy.tuning import AstronomyTuning
from app.core.chandramasa.chandramasa import (
    _MAX_MASA_SPAN_DAYS,
    get_chandra_masa_date,
    get_chandra_masa_dates_for_range,
)
from app.core.kollavarsham.kollavarsham import (
    get_kollavarsham_date,
    get_kollavarsham_dates_for_range,
    get_madhyahnam_raasi_for_range,
)
from datetime import date, timedelta
from app.core.astronomy.constants import DEFAULT_TIMEZONE, Coordinates
from app.schemas.location import LocationInfo
from app.schemas.panchangam_data import PanchangamData
from app.utils.location import Location

# Chunk size for get_panchangam_data_range's range-batched transition search --
# see that function's docstring for why this isn't "one find_discrete call for
# the whole range": benchmarked sweet spot between Skyfield's non-linear
# large-array nutation cost and a plain per-day loop's per-call overhead.
_TRANSITION_CHUNK_DAYS = 30


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


def _build_panchangam_data(
    localdt: date,
    thithi_transitions,
    nakshatra_transitions,
    kv,
    chandra_masa,
    sunrise: datetime,
    sunset: datetime,
    latitude: float,
    longitude: float,
    instant: Optional[datetime],
) -> PanchangamData:
    """Shared tail of :func:`get_panchangam_data`/:func:`get_panchangam_data_range`:
    everything after the Thithi/Nakshatra transitions, Kollavarsham, Chandra
    Masa, and sunrise/sunset are known for *localdt* -- callers compute those
    (per-day or range-batched) and pass them in.
    """
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
    # santhigiri_significant_dates are overlaid by PanchangamService from the
    # editable DB event definitions (see core/events/significant_dates.py);
    # get_panchangam_data(_range) stays pure and returns an empty list here.
    return PanchangamData(
        date= localdt,
        kv=kv,
        chandra_masa=chandra_masa,
        thithi_transitions= thithi_transitions,
        nakshatra_transitions= nakshatra_transitions,
        thithi = thithi,
        nakshatra = nakshatra,
        nazhika_from_sunrise=nazhika_from_sunrise,
        sunrise = sunrise,
        sunset = sunset,
        location = location,
    )


def get_panchangam_data(
    localdt: date,
    latitude: float = Coordinates.SG_LATITUDE,
    longitude: float = Coordinates.SG_LONGITUDE,
    timezone: str = DEFAULT_TIMEZONE,
    tuning: AstronomyTuning = AstronomyTuning(),
    instant: Optional[datetime] = None,
):
    thithi_transitions = calc_thithi_transition_for_date(localdt, timezone, tuning)
    nakshatra_transitions = calc_nakshatra_transition_for_date(localdt, timezone, tuning)
    kv = get_kollavarsham_date(
        dt=localdt, latitude=latitude, longitude=longitude, timezone=timezone,
        epsilon=tuning.kollavarsham_epsilon,
    )
    chandra_masa = get_chandra_masa_date(
        dt=localdt, latitude=latitude, longitude=longitude, timezone=timezone, tuning=tuning,
    )
    sunrise, sunset = get_sunrise_sunset(localdt, latitude, longitude, timezone)
    return _build_panchangam_data(
        localdt, thithi_transitions, nakshatra_transitions, kv, chandra_masa,
        sunrise, sunset, latitude, longitude, instant,
    )


def get_panchangam_data_range(
    start: date,
    end: date,
    latitude: float = Coordinates.SG_LATITUDE,
    longitude: float = Coordinates.SG_LONGITUDE,
    timezone: str = DEFAULT_TIMEZONE,
    tuning_for_year: Callable[[int], AstronomyTuning] = lambda year: AstronomyTuning(),
) -> Dict[date, PanchangamData]:
    """Bulk equivalent of calling :func:`get_panchangam_data` once per day in
    ``[start, end]`` (inclusive) -- used by the admin generation write path,
    never by a single-day/instant read (those keep calling
    :func:`get_panchangam_data`, which stays untouched).

    Thithi/Nakshatra transitions are computed with one range-batched
    ``find_discrete`` call per ~``_TRANSITION_CHUNK_DAYS``-day chunk (via
    :func:`core.astronomy.thithi_transition.calc_thithi_transitions_for_range`/
    :func:`core.astronomy.nakshatra_transition.calc_nakshatra_transitions_for_range`)
    instead of one 3-/5-day-window call per day -- the redundant boundary
    search across overlapping per-day windows is what made the per-day loop
    slow for a large generate range. Chunked rather than one single call for
    the whole requested range: benchmarking showed Skyfield's own nutation
    calculation (``iau2000a``) does not scale linearly with array size, so one
    ``find_discrete`` call spanning a whole year is measurably *slower* than
    the equivalent per-day loop, while ~30-day chunks land in the sweet spot
    between that per-array cost and the per-call overhead a plain per-day loop
    pays 365 times over.

    Kollavarsham and Chandra Masa are each computed with one pass over the
    range (:func:`core.kollavarsham.kollavarsham.get_kollavarsham_dates_for_range`/
    :func:`core.chandramasa.chandramasa.get_chandra_masa_dates_for_range`)
    instead of once per day -- profiling showed Chandra Masa's independent
    per-day backward/forward month-boundary walk dominating total per-day
    pipeline time; see those functions' docstrings. Chandra Masa's month-boundary
    detection needs Thithi paksha for up to ``_MAX_MASA_SPAN_DAYS`` days on either
    side of ``[start, end]``, so the range-batched Thithi search below actually
    covers that padded span, not just ``[start, end]`` -- otherwise Chandra Masa
    would fall back to re-deriving paksha per padding day via the single-day
    Thithi path, reopening the exact redundant ``find_discrete`` calls this was
    meant to eliminate.

    Sunrise/sunset is computed with :func:`core.astronomy.sunrise_sunset.get_sunrise_sunset_for_range`,
    one ``find_discrete`` call per ``_SUNRISE_SUNSET_CHUNK_DAYS``-day chunk
    over the same padded range Chandra Masa needs (its own paksha detection
    above also needs sunrise, to know which Thithi is active *at* sunrise) --
    profiling found this the single largest remaining cost after batching
    Thithi/Nakshatra/Kollavarsham/Chandra Masa.

    *tuning_for_year* is called once per distinct year in the range (tuning,
    notably ``nakshatra_step_days``, is admin-configurable per year -- see
    ``SettingsService.get_astronomy_tuning``) so a range spanning a tuning
    change at a year boundary still batches correctly -- chunk boundaries never
    cross a year boundary, so each chunk uses exactly one tuning. Kollavarsham/
    Chandra Masa are computed per calendar-year segment of ``[start, end]`` for
    the same reason, matching :func:`get_chandra_masa_date`'s/
    :func:`get_kollavarsham_date`'s own per-``dt``-year tuning resolution.
    """
    masa_padded_start = start - timedelta(days=_MAX_MASA_SPAN_DAYS + 1)
    masa_padded_end = end + timedelta(days=_MAX_MASA_SPAN_DAYS)

    thithi_by_day: Dict[date, list] = {}
    nakshatra_by_day: Dict[date, list] = {}

    chunk_start = masa_padded_start
    while chunk_start <= masa_padded_end:
        tuning = tuning_for_year(chunk_start.year)
        year_end = date(chunk_start.year, 12, 31)
        chunk_end = min(masa_padded_end, year_end, chunk_start + timedelta(days=_TRANSITION_CHUNK_DAYS - 1))
        thithi_by_day.update(
            calc_thithi_transitions_for_range(chunk_start, chunk_end, timezone, tuning)
        )
        # Nakshatra isn't needed by Chandra Masa/Kollavarsham -- only compute it
        # for the actually-requested (unpadded) span.
        seg_start, seg_end = max(chunk_start, start), min(chunk_end, end)
        if seg_start <= seg_end:
            nakshatra_by_day.update(
                calc_nakshatra_transitions_for_range(seg_start, seg_end, timezone, tuning)
            )
        chunk_start = chunk_end + timedelta(days=1)

    sunrise_sunset_by_day = get_sunrise_sunset_for_range(
        masa_padded_start, masa_padded_end, latitude, longitude, timezone
    )

    paksha_by_day: Dict[date, object] = {}
    d = masa_padded_start
    while d <= masa_padded_end:
        sunrise, _ = sunrise_sunset_by_day[d]
        paksha_by_day[d] = _active_at(thithi_by_day[d], sunrise).thithi.paksha
        d += timedelta(days=1)

    # Single epsilon for the whole padded range, from start's own year's tuning:
    # kollavarsham_epsilon has no per-year admin override (unlike
    # nakshatra_step_days), so unlike the Thithi/Nakshatra chunking above, there
    # is no real per-year value to stitch across -- matches the same
    # single-tuning-per-month simplification Chandra Masa's own classification
    # already makes.
    raasi_by_day = get_madhyahnam_raasi_for_range(
        masa_padded_start, masa_padded_end, latitude, longitude, timezone,
        tuning_for_year(start.year).kollavarsham_epsilon, sunrise_sunset_by_day,
    )

    kv_by_day: Dict[date, object] = {}
    chandra_masa_by_day: Dict[date, object] = {}
    seg_start = start
    while seg_start <= end:
        tuning = tuning_for_year(seg_start.year)
        seg_end = min(end, date(seg_start.year, 12, 31))
        kv_by_day.update(
            get_kollavarsham_dates_for_range(
                seg_start, seg_end, latitude, longitude, timezone, tuning.kollavarsham_epsilon,
                raasi_by_day,
            )
        )
        chandra_masa_by_day.update(
            get_chandra_masa_dates_for_range(
                seg_start, seg_end, latitude, longitude, timezone, tuning, paksha_by_day, raasi_by_day,
            )
        )
        seg_start = seg_end + timedelta(days=1)

    result: Dict[date, PanchangamData] = {}
    d = start
    while d <= end:
        sunrise, sunset = sunrise_sunset_by_day[d]
        result[d] = _build_panchangam_data(
            d, thithi_by_day[d], nakshatra_by_day[d], kv_by_day[d], chandra_masa_by_day[d],
            sunrise, sunset, latitude, longitude, instant=None,
        )
        d += timedelta(days=1)
    return result


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
        "calculated_ml_month": kv.kv_month,
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

