"""Regression coverage for get_madhyahnam_raasi_for_range: must match calling
get_madhyahnam_raasi once per day. The range function replaces N scalar
Skyfield position calls with one vectorized call per ~30-day chunk -- a
performance optimization, not a behavior change.
"""
from datetime import date, timedelta

from app.core.astronomy.constants import DEFAULT_TIMEZONE, Coordinates
from app.core.kollavarsham.kollavarsham import get_madhyahnam_raasi, get_madhyahnam_raasi_for_range

START = date(2026, 1, 1)
END = date(2026, 2, 20)  # spans a chunk boundary (>30 days)


def test_range_matches_per_day():
    batched = get_madhyahnam_raasi_for_range(
        START, END, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE
    )
    d = START
    while d <= END:
        expected = get_madhyahnam_raasi(
            dt=d, latitude=Coordinates.SG_LATITUDE, longitude=Coordinates.SG_LONGITUDE,
            timezone=DEFAULT_TIMEZONE,
        )
        assert batched[d] == expected, f"{d}: raasi mismatch ({batched[d]} vs {expected})"
        d += timedelta(days=1)


def test_range_covers_every_requested_day_exactly_once():
    batched = get_madhyahnam_raasi_for_range(
        START, END, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE
    )
    expected_days = (END - START).days + 1
    assert len(batched) == expected_days
