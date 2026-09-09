from datetime import date, timedelta
from functools import lru_cache
from typing import List, Tuple

from app.core.astronomy.calculations import get_sun_sidereal_longitude
from app.core.astronomy.constants import DEFAULT_TIMEZONE, Coordinates
from app.core.astronomy.enums.paksha import Paksha
from app.core.astronomy.enums.thithi import Thithi
from app.core.astronomy.sunrise_sunset import get_sunrise_sunset
from app.core.astronomy.thithi_transition import calc_thithi_transition_for_date
from app.core.astronomy.transitions import ThithiTransition
from app.core.astronomy.tuning import AstronomyTuning
from app.core.chandramasa.chandramasa_models import ChandraMasaDate
from app.core.chandramasa.enums.masa import ChandraMasa
from app.core.kollavarsham.kollavarsham import get_raasi

# A lunar (synodic) month is <=30 days; this margin bounds the day-by-day walks
# below the same way Kollavarsham's masa-start binary search is bounded to 32.
_MAX_MASA_SPAN_DAYS = 32


def _active_thithi(transitions: List[ThithiTransition], instant) -> Thithi:
    """Thithi whose [start_time, end_time) interval contains `instant`.

    Mirrors `core/calendar/panchangam.py::_active_at`, duplicated locally (a
    handful of lines) rather than imported, since `core/calendar/` aggregates
    `core/kollavarsham/`/`core/chandramasa/` and must not be depended on in
    the other direction.
    """
    for transition in transitions:
        if transition.start_time <= instant and (
            transition.end_time is None or instant < transition.end_time
        ):
            return transition.thithi
    if instant < transitions[0].start_time:
        return transitions[0].thithi
    return transitions[-1].thithi


def _sunrise_active_thithi(
    d: date, latitude: float, longitude: float, timezone: str, tuning: AstronomyTuning
) -> Tuple[List[ThithiTransition], Thithi]:
    transitions = calc_thithi_transition_for_date(d, timezone, tuning)
    sunrise, _ = get_sunrise_sunset(d, latitude, longitude, timezone)
    return transitions, _active_thithi(transitions, sunrise)


def _walk_to_paksha_start(
    start: date,
    step: int,
    latitude: float,
    longitude: float,
    timezone: str,
    tuning: AstronomyTuning,
) -> Tuple[date, ThithiTransition]:
    """Walk day-by-day from `start` (in direction `step`) to the nearest day
    whose sunrise Thithi is Shukla Paksha immediately following a Krishna
    Paksha day -- an Amanta month-start day -- and return that day plus the
    Krishna -> Shukla transition itself.

    The boundary is detected by paksha, not a fixed thithi id (Prathama
    Shukla): a fast-moving thithi can occasionally not touch any sunrise at
    all (a "kshaya tithi") and be entirely skipped by the day-attribution
    rule, so the first day of the new paksha is sometimes Dwithiya Shukla or
    later rather than Prathama Shukla.
    """
    current = start
    for _ in range(_MAX_MASA_SPAN_DAYS + 1):
        transitions, active = _sunrise_active_thithi(
            current, latitude, longitude, timezone, tuning
        )
        if active.paksha == Paksha.SHUKLA:
            _, prev_active = _sunrise_active_thithi(
                current - timedelta(days=1), latitude, longitude, timezone, tuning
            )
            if prev_active.paksha == Paksha.KRISHNA:
                transition = next(
                    t for t in transitions if t.thithi.paksha == Paksha.SHUKLA
                )
                return current, transition
        current += timedelta(days=step)
    raise RuntimeError(
        f"No Amanta month start found walking from {start} (step={step})"
    )


@lru_cache(maxsize=1000)
def get_chandra_masa_date(
    dt: date,
    latitude: float = Coordinates.SG_LATITUDE,
    longitude: float = Coordinates.SG_LONGITUDE,
    timezone: str = DEFAULT_TIMEZONE,
    tuning: AstronomyTuning = AstronomyTuning(),
) -> ChandraMasaDate:
    """Amanta lunar month (Chandra Masa) for `dt`.

    The month runs Amavasya -> Amavasya (the Thithi 30 -> 1 boundary); `dt`'s
    calendar day is attributed to a month the same way Thithi/Kollavarsham
    attribute a day -- by the value active at sunrise. The month is named for
    the solar raasi (Sankranti) it carries -- the raasi in effect at the
    month's end, which is the one realized during most of the month, mirroring
    `core/kollavarsham/kollavarsham.py`'s own raasi-to-month-name mapping. A
    month is Adhika (leap) when the Sun's raasi is unchanged from the month's
    start to its end -- no Sankranti occurred within it -- in which case it
    shares its name with the regular month immediately following it.

    Kshaya masa (a solar month with two Sankrantis inside one lunar month) is
    not detected -- rare enough (none in 2021-2030) that it is left as a
    documented, unhandled limitation.
    """
    month_start, month_start_transition = _walk_to_paksha_start(
        dt, -1, latitude, longitude, timezone, tuning
    )
    month_end, month_end_transition = _walk_to_paksha_start(
        dt + timedelta(days=1), 1, latitude, longitude, timezone, tuning
    )

    masa_day = (dt - month_start).days + 1

    start_raasi = get_raasi(
        get_sun_sidereal_longitude(
            localdt=month_start_transition.start_time.replace(tzinfo=None),
            timezone=timezone,
        )
    )
    end_raasi = get_raasi(
        get_sun_sidereal_longitude(
            localdt=month_end_transition.start_time.replace(tzinfo=None),
            timezone=timezone,
        )
    )
    # The Sankramanam the month carries (or, for an Adhika month with none, the
    # raasi it never leaves) names it -- the raasi in effect at the month's end
    # is the one realized during most of the month, the exact analogue of how
    # `core/kollavarsham/kollavarsham.py` names a solar month for its raasi.
    masa = ChandraMasa.from_id(end_raasi + 1)
    is_adhika = start_raasi == end_raasi

    return ChandraMasaDate(
        date=dt,
        masa=masa.id,
        masa_day=masa_day,
        is_adhika=is_adhika,
    )
