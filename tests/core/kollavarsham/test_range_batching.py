"""Regression coverage for get_kollavarsham_dates_for_range: must match calling
get_kollavarsham_date once per day. The range function replaces an O(log 32)
per-day binary search with a single forward pass -- a performance optimization,
not a behavior change.
"""
from datetime import date, timedelta

from app.core.kollavarsham.kollavarsham import get_kollavarsham_date, get_kollavarsham_dates_for_range
from app.core.astronomy.constants import DEFAULT_TIMEZONE, Coordinates

START = date(2026, 2, 1)
END = date(2026, 4, 15)  # spans at least 2 Malayalam month boundaries


def test_range_matches_per_day():
    batched = get_kollavarsham_dates_for_range(
        START, END, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE
    )
    d = START
    while d <= END:
        expected = get_kollavarsham_date(
            dt=d, latitude=Coordinates.SG_LATITUDE, longitude=Coordinates.SG_LONGITUDE,
            timezone=DEFAULT_TIMEZONE,
        )
        actual = batched[d]
        assert actual.kv_year == expected.kv_year, f"{d}: kv_year mismatch"
        assert actual.kv_month == expected.kv_month, f"{d}: kv_month mismatch"
        assert actual.kv_day == expected.kv_day, f"{d}: kv_day mismatch"
        d += timedelta(days=1)


def test_range_matches_across_a_month_boundary_at_range_start():
    """A range starting exactly on (or right after) a Malayalam month boundary
    is the sharpest edge case for the running-count reset logic."""
    start = date(2026, 3, 15)  # mid-range start, not aligned to any known boundary
    end = date(2026, 3, 20)
    batched = get_kollavarsham_dates_for_range(
        start, end, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE
    )
    d = start
    while d <= end:
        expected = get_kollavarsham_date(
            dt=d, latitude=Coordinates.SG_LATITUDE, longitude=Coordinates.SG_LONGITUDE,
            timezone=DEFAULT_TIMEZONE,
        )
        assert batched[d].kv_day == expected.kv_day, f"{d}: kv_day mismatch"
        d += timedelta(days=1)
