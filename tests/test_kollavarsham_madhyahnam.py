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

Makaram 1, 1202 ME is published as 2026-01-15 in the Kerala Malayalam calendar
(the Makara Sankramanam is 2026-01-14 — the one-day offset is exactly this rule).
See e.g. https://hindupad.com/makara-masam-makaram-month/ and
https://www.prokerala.com/calendar/malayalamcalendar-2026.html
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
    "first_day, masa_id, masa_en",
    [
        # Makara Sankramanam on 2026-01-14 afternoon -> Makaram 1 on 2026-01-15.
        (date(2026, 1, 15), 10, "Makaram"),
        # Mithuna Sankramanam on 2026-06-15 afternoon -> Mithunam 1 on 2026-06-16.
        (date(2026, 6, 16), 3, "Mithunam"),
    ],
)
def test_month_starts_on_madhyahnam_day(first_day, masa_id, masa_en):
    """The first day of the new masa has kv_day == 1 and the new masa's id."""
    kv = _kv(first_day)
    assert kv.kv_day == 1
    assert kv.kv_month == masa_id
    assert kv.kv_month_name_en == masa_en


@pytest.mark.parametrize("first_day, masa_id", [(date(2026, 1, 15), 10), (date(2026, 6, 16), 3)])
def test_day_before_is_still_previous_month(first_day, masa_id):
    """The day before the boundary (Sankramanam day) is the last day of the
    previous masa — proving the transition is deferred past midday, one day later
    than the sunset rule (which would have flipped the month on this day)."""
    prev = _kv(first_day - timedelta(days=1))
    assert prev.kv_month != masa_id
    assert prev.kv_day > 1
