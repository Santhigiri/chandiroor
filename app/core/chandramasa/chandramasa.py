from datetime import date, timedelta
from functools import lru_cache
from typing import List, Tuple

from app.core.astronomy.constants import DEFAULT_TIMEZONE, Coordinates
from app.core.astronomy.enums.paksha import Paksha
from app.core.astronomy.enums.thithi import Thithi
from app.core.astronomy.sunrise_sunset import get_sunrise_sunset
from app.core.astronomy.thithi_transition import calc_thithi_transition_for_date
from app.core.astronomy.transitions import ThithiTransition
from app.core.astronomy.tuning import AstronomyTuning
from app.core.chandramasa.chandramasa_models import ChandraMasaDate
from app.core.chandramasa.enums.masa import ChandraMasa
from app.core.chandramasa.enums.masa_type import MasaType
from app.core.kollavarsham.kollavarsham import get_madhyahnam_raasi

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
) -> Thithi:
    transitions = calc_thithi_transition_for_date(d, timezone, tuning)
    sunrise, _ = get_sunrise_sunset(d, latitude, longitude, timezone)
    return _active_thithi(transitions, sunrise)


def _walk_to_paksha_start(
    start: date,
    step: int,
    latitude: float,
    longitude: float,
    timezone: str,
    tuning: AstronomyTuning,
) -> date:
    """Walk day-by-day from `start` (in direction `step`) to the nearest day
    whose sunrise Thithi is Shukla Paksha immediately following a Krishna
    Paksha day -- an Amanta month-start day.

    The boundary is detected by paksha, not a fixed thithi id (Prathama
    Shukla): a fast-moving thithi can occasionally not touch any sunrise at
    all (a "kshaya tithi") and be entirely skipped by the day-attribution
    rule, so the first day of the new paksha is sometimes Dwithiya Shukla or
    later rather than Prathama Shukla.
    """
    current = start
    for _ in range(_MAX_MASA_SPAN_DAYS + 1):
        active = _sunrise_active_thithi(current, latitude, longitude, timezone, tuning)
        if active.paksha == Paksha.SHUKLA:
            prev_active = _sunrise_active_thithi(
                current - timedelta(days=1), latitude, longitude, timezone, tuning
            )
            if prev_active.paksha == Paksha.KRISHNA:
                return current
        current += timedelta(days=step)
    raise RuntimeError(
        f"No Amanta month start found walking from {start} (step={step})"
    )


def classify_masa_type(raasi_sequence: List[int]) -> MasaType:
    """Classify a lunar month from the sequence of Sun raasi values sampled
    once per calendar day across it. Include one leading sample from the day
    *before* the month starts (see `get_chandra_masa_date`), so a Sankranti
    landing exactly on the month's first day is counted rather than missed.

    Counts Sankrantis (raasi changes) within the sequence:
    - 0 crossings -> Adhika (leap): the Sun never changed raasi in the month.
    - 1 crossing  -> Nija (regular): the ordinary case.
    - 2+ crossings -> Kshaya (deficit): two Sankrantis fall inside one lunar
      month, so the solar month between them has no lunar month named for it.
    """
    crossings = sum(
        1 for a, b in zip(raasi_sequence, raasi_sequence[1:]) if a != b
    )
    if crossings == 0:
        return MasaType.ADHIKA
    if crossings == 1:
        return MasaType.NIJA
    return MasaType.KSHAYA


@lru_cache(maxsize=1000)
def get_chandra_masa_date(
    dt: date,
    latitude: float = Coordinates.SG_LATITUDE,
    longitude: float = Coordinates.SG_LONGITUDE,
    timezone: str = DEFAULT_TIMEZONE,
    tuning: AstronomyTuning = AstronomyTuning(),
) -> ChandraMasaDate:
    """Amanta lunar month (Chandra Masa) for `dt`.

    The month runs Amavasya -> Amavasya (the Krishna -> Shukla paksha
    boundary); `dt`'s calendar day is attributed to a month the same way
    Thithi/Kollavarsham attribute a day -- by the value active at sunrise.
    The month is named for the solar raasi it carries at its end (the raasi
    realized during most of the month), mirroring
    `core/kollavarsham/kollavarsham.py`'s own raasi-to-month-name mapping.
    `masa_type` classifies the month by how many Sankrantis (solar raasi
    changes, sampled the same way Kollavarsham samples them -- at madhyahnam
    each day) fall within it: Adhika (leap, none), Nija (regular, one), or
    Kshaya (deficit, two or more) -- see `classify_masa_type`.
    """
    month_start = _walk_to_paksha_start(dt, -1, latitude, longitude, timezone, tuning)
    month_end = _walk_to_paksha_start(
        dt + timedelta(days=1), 1, latitude, longitude, timezone, tuning
    )

    masa_day = (dt - month_start).days + 1

    # Starts one day before `month_start`: a Sankranti can land exactly on the
    # month's first day, which a sequence starting *at* month_start would miss
    # entirely (no earlier sample to compare it against) -- undercounting
    # crossings and misclassifying the month as Adhika.
    raasi_sequence = []
    d = month_start - timedelta(days=1)
    while d < month_end:
        raasi_sequence.append(
            get_madhyahnam_raasi(
                dt=d,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                epsilon=tuning.kollavarsham_epsilon,
            )
        )
        d += timedelta(days=1)

    masa = ChandraMasa.from_id(raasi_sequence[-1] + 1)
    masa_type = classify_masa_type(raasi_sequence)

    return ChandraMasaDate(
        date=dt,
        masa=masa.id,
        masa_day=masa_day,
        masa_type=masa_type.id,
    )
