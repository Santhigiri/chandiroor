"""
Tests for the Modyana Malayalam month-transition rule.

The daytime (sunrise -> sunset) is split into five equal parts; Modyana is the
third part (40%-60% of the daytime). The Malayalam month begins on the day of the
Sankramanam (the Sun's entry into a new raasi) if that entry happens *before or
during* Modyana, otherwise the next day. This is implemented by sampling the Sun's
raasi at the *end* of Modyana (sunrise + 3/5 of the daytime) in
``core.calendar.kollavarsham.get_kollavarsham_date``.

The boundaries below are cross-checked against published Kerala calendars:
* Makaram 1, 1201 ME = 2026-01-15 (Makara Sankramanam 2026-01-14 afternoon,
  after that day's Modyana -> next day).
* Mithunam 1, 1201 ME = 2026-06-15 (Mithuna Sankramanam ~12:49 PM 2026-06-15 is
  before the end of Modyana ~1:36 PM -> same day). Note the 50% midpoint rule
  wrongly gave 2026-06-16; the end-of-Modyana (60%) cutoff matches the calendar.
* Medam 1, 1202 ME (Vishu) = 2027-04-15 (Medam Sankramanam 2027-04-14 afternoon,
  after that day's Modyana -> next day).
See e.g. https://www.prokerala.com/calendar/malayalamcalendar-2026.html,
https://www.prokerala.com/astrology/mithuna-sankranti-15-june-2026-timings.htm and
https://www.prokerala.com/festivals/vishu.html
"""
from datetime import date, timedelta

import pytest

from panchangam_astronomy.constants import Coordinates, DEFAULT_TIMEZONE
from app.core.calendar.kollavarsham import get_kollavarsham_date
from app.utils.malayalam_masa import MalayalamMasa

LAT = round(Coordinates.SG_LATITUDE, 3)
LON = round(Coordinates.SG_LONGITUDE, 3)
TZ = DEFAULT_TIMEZONE


def _kv(day: date):
    return get_kollavarsham_date(dt=day, latitude=LAT, longitude=LON, timezone=TZ)


@pytest.mark.parametrize(
    "first_day, masa, kv_year",
    [
        # Makara Sankramanam 2026-01-14, after that day's Modyana -> Makaram 1 = 01-15.
        (date(2026, 1, 15), MalayalamMasa.MAKARAM, 1201),
        # Mithuna Sankramanam ~12:49 PM 2026-06-15, before end of Modyana -> same day.
        (date(2026, 6, 15), MalayalamMasa.MITHUNAM, 1201),
        # Medam Sankramanam 2027-04-14, after that day's Modyana -> Medam 1 = 04-15.
        (date(2027, 4, 15), MalayalamMasa.MEDAM, 1202),
    ],
)
def test_month_starts_on_modyana_day(first_day, masa, kv_year):
    """The first day of the new masa has kv_day == 1 and the new masa's id."""
    kv = _kv(first_day)
    assert kv.kv_day == 1
    assert kv.kv_month == masa.id
    assert kv.kv_year == kv_year


@pytest.mark.parametrize(
    "first_day, masa_id",
    [(date(2026, 1, 15), 10), (date(2026, 6, 15), 3), (date(2027, 4, 15), 1)],
)
def test_day_before_is_still_previous_month(first_day, masa_id):
    """The day before a month-start is the last day of the previous masa: at the
    end of Modyana on that earlier day the Sun had not yet entered the new raasi."""
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
