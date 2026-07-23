"""
Tests for the madhyahnam (Sankranti-vs-midday) Malayalam month-transition rule.

The Malayalam month begins on the day of the Sankramanam (the Sun's entry into a
new raasi) if that entry occurs at or before madhyahnam (midday — the midpoint
between sunrise and sunset), otherwise the next day. This is implemented by
sampling the Sun's raasi at madhyahnam in
``core.calendar.kollavarsham.get_kollavarsham_date``.

The boundary dates below are cases where the Sankramanam falls in the *afternoon*
(after madhyahnam, before sunset), so the madhyahnam rule yields a month-start
one day later than the retired sunset rule would have.

Makaram 1, 1201 ME is published as 2026-01-15 in the Kerala Malayalam calendar
(the Makara Sankramanam is 2026-01-14 — the one-day offset is exactly this rule).
Medam 1, 1202 ME (Vishu) is published as 2027-04-15 (the Medam Sankramanam falls
2027-04-14 afternoon). See e.g. https://hindupad.com/makara-masam-makaram-month/,
https://www.prokerala.com/calendar/malayalamcalendar-2026.html and
https://www.prokerala.com/festivals/vishu.html
"""
from datetime import date, timedelta

import pytest

from core.constants import Coordinates, DEFAULT_TIMEZONE
from core.calendar.kollavarsham import get_kollavarsham_date

LAT = round(Coordinates.SG_LATITUDE, 3)
LON = round(Coordinates.SG_LONGITUDE, 3)
TZ = DEFAULT_TIMEZONE


def _kv(day: date):
    return get_kollavarsham_date(dt=day, latitude=LAT, longitude=LON, timezone=TZ)


@pytest.mark.parametrize(
    "first_day, masa_id, masa_en, kv_year",
    [
        # Makara Sankramanam on 2026-01-14 afternoon -> Makaram 1 on 2026-01-15.
        (date(2026, 1, 15), 10, "Makaram", 1201),
        # Mithuna Sankramanam on 2026-06-15 afternoon -> Mithunam 1 on 2026-06-16.
        (date(2026, 6, 16), 3, "Mithunam", 1201),
        # Medam Sankramanam on 2027-04-14 afternoon -> Medam 1 (Vishu) on 2027-04-15.
        (date(2027, 4, 15), 1, "Medam", 1202),
    ],
)
def test_month_starts_on_madhyahnam_day(first_day, masa_id, masa_en, kv_year):
    """The first day of the new masa has kv_day == 1 and the new masa's id."""
    kv = _kv(first_day)
    assert kv.kv_day == 1
    assert kv.kv_month == masa_id
    assert kv.kv_month_name_en == masa_en
    assert kv.kv_year == kv_year


@pytest.mark.parametrize(
    "first_day, masa_id",
    [(date(2026, 1, 15), 10), (date(2026, 6, 16), 3), (date(2027, 4, 15), 1)],
)
def test_day_before_is_still_previous_month(first_day, masa_id):
    """The day before the boundary (Sankramanam day) is the last day of the
    previous masa — proving the transition is deferred past midday, one day later
    than the sunset rule (which would have flipped the month on this day)."""
    prev = _kv(first_day - timedelta(days=1))
    assert prev.kv_month != masa_id
    assert prev.kv_day > 1


# ── Kollam year continuity ───────────────────────────────────────────────────
# The Kollam year increments only at Chingam (mid-August). Within a Kollam year
# the number is constant across every masa, including the Meenam -> Medam step
# and the Dhanu December/January straddle. These pin that the year is derived
# correctly rather than flipping at the Gregorian new year.
@pytest.mark.parametrize(
    "day, expected_year",
    [
        (date(2026, 12, 20), 1202),  # Dhanu, December
        (date(2027, 1, 5), 1202),    # Dhanu, January tail (same Kollam year)
        (date(2027, 1, 20), 1202),   # Makaram, January
        (date(2027, 3, 20), 1202),   # Meenam
        (date(2027, 4, 15), 1202),   # Medam (year unchanged across Meenam->Medam)
        (date(2027, 8, 16), 1202),   # Karkidakam, last month of the Kollam year
        (date(2027, 8, 18), 1203),   # Chingam, first day of the next Kollam year
    ],
)
def test_kollam_year_is_continuous_within_the_year(day, expected_year):
    assert _kv(day).kv_year == expected_year
