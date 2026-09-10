from datetime import datetime, timedelta

import pytz

from app.core.astronomy.enums.nakshatra import Nakshatra
from app.core.astronomy.transitions import NakshatraTransition
from app.core.calendar.panchangam import _nakshatra_at

_IST = pytz.timezone("Asia/Kolkata")


def _dt(hour: int, minute: int = 0, day: int = 22) -> datetime:
    return _IST.localize(datetime(2026, 9, day, hour, minute))


def _transitions():
    # Mirrors the real Sept 22 2026 Santhigiri-coordinate transitions: Uthradam
    # active at sunrise (06:14:55) but ending only ~2.16 nazhika later, at
    # 07:06:43, handing off to Thiruvonam.
    return [
        NakshatraTransition(
            nakshatra=Nakshatra.POORADAM, start_time=_dt(1, 42, day=20), end_time=_dt(4, 34, day=21),
        ),
        NakshatraTransition(
            nakshatra=Nakshatra.UTHRADAM, start_time=_dt(4, 34, day=21), end_time=_dt(7, 6, day=22),
        ),
        NakshatraTransition(
            nakshatra=Nakshatra.THIRUVONAM, start_time=_dt(7, 6, day=22), end_time=_dt(9, 9, day=23),
        ),
    ]


def test_get_nakshathra():
    pass


def test_nakshatra_at_sunrise_below_cutoff_shifts_to_incoming_nakshatra():
    sunrise = _dt(6, 14)  # ~2.16 nazhika before Uthradam ends at 07:06
    assert _nakshatra_at(_transitions(), sunrise, nazhika_cutoff=7.5) == Nakshatra.THIRUVONAM


def test_nakshatra_at_sunrise_above_cutoff_keeps_active_nakshatra():
    sunrise = _dt(6, 14)
    # A cutoff below the ~2.16 nazhika actually remaining never triggers the shift.
    assert _nakshatra_at(_transitions(), sunrise, nazhika_cutoff=2.0) == Nakshatra.UTHRADAM


def test_nakshatra_at_zero_cutoff_never_shifts():
    sunrise = _dt(6, 14)
    assert _nakshatra_at(_transitions(), sunrise, nazhika_cutoff=0) == Nakshatra.UTHRADAM


def test_nakshatra_at_applies_relative_to_any_instant_not_just_sunrise():
    # Same cutoff rule generalizes to an arbitrary instant (the /instant
    # endpoint), not only a sunrise-anchored day lookup.
    near_end_of_uthradam = _dt(6, 50)  # ~0.4 nazhika before it ends at 07:06
    assert _nakshatra_at(_transitions(), near_end_of_uthradam, nazhika_cutoff=7.5) == Nakshatra.THIRUVONAM

    far_from_end = _dt(1, 0)
    assert _nakshatra_at(_transitions(), far_from_end, nazhika_cutoff=7.5) == Nakshatra.UTHRADAM


def test_nakshatra_at_unaffected_when_far_from_any_transition():
    # A day where the sunrise-active Nakshatra has plenty of runway left is
    # untouched by the cutoff regardless of its value.
    sunrise = _dt(6, 15, day=21)
    assert _nakshatra_at(_transitions(), sunrise, nazhika_cutoff=7.5) == Nakshatra.UTHRADAM
    assert _nakshatra_at(_transitions(), sunrise, nazhika_cutoff=0) == Nakshatra.UTHRADAM
