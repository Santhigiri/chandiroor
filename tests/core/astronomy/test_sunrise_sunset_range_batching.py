"""Regression coverage for get_sunrise_sunset_for_range: must match calling
get_sunrise_sunset once per day. The range function replaces one find_discrete
call per day with one call per ~30-day chunk -- a performance optimization,
not a behavior change.
"""
from datetime import date, timedelta

from app.core.astronomy.constants import DEFAULT_TIMEZONE, Coordinates
from app.core.astronomy.sunrise_sunset import get_sunrise_sunset, get_sunrise_sunset_for_range

START = date(2026, 1, 1)
END = date(2026, 2, 20)  # spans a chunk boundary (>30 days)


def test_range_matches_per_day():
    batched = get_sunrise_sunset_for_range(
        START, END, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE
    )
    d = START
    while d <= END:
        expected_sunrise, expected_sunset = get_sunrise_sunset(
            d, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE
        )
        actual_sunrise, actual_sunset = batched[d]
        assert abs((actual_sunrise - expected_sunrise).total_seconds()) < 1, f"{d}: sunrise mismatch"
        assert abs((actual_sunset - expected_sunset).total_seconds()) < 1, f"{d}: sunset mismatch"
        d += timedelta(days=1)


def test_range_covers_every_requested_day_exactly_once():
    batched = get_sunrise_sunset_for_range(
        START, END, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE
    )
    expected_days = (END - START).days + 1
    assert len(batched) == expected_days
    d = START
    while d <= END:
        assert d in batched
        d += timedelta(days=1)
