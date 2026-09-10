"""Regression coverage for get_chandra_masa_dates_for_range: must match calling
get_chandra_masa_date once per day. The range function replaces per-day
independent backward/forward month-boundary walks with a single forward pass
that finds every boundary once -- a performance optimization, not a behavior
change.
"""
from datetime import date, timedelta

from app.core.astronomy.thithi_transition import calc_thithi_transitions_for_range
from app.core.astronomy.sunrise_sunset import get_sunrise_sunset
from app.core.astronomy.tuning import AstronomyTuning
from app.core.calendar.panchangam import _active_at
from app.core.chandramasa.chandramasa import (
    _MAX_MASA_SPAN_DAYS,
    get_chandra_masa_date,
    get_chandra_masa_dates_for_range,
)
from app.core.astronomy.constants import DEFAULT_TIMEZONE, Coordinates

START = date(2026, 2, 1)
END = date(2026, 4, 15)  # spans at least 2 Chandra Masa month boundaries
TUNING = AstronomyTuning()


def _paksha_by_day(start: date, end: date):
    """Build the paksha_by_day map the same way the real caller
    (core.calendar.panchangam.get_panchangam_data_range) does: from a
    range-batched Thithi transition search, not the per-day path."""
    padded_start = start - timedelta(days=_MAX_MASA_SPAN_DAYS + 1)
    padded_end = end + timedelta(days=_MAX_MASA_SPAN_DAYS)
    thithi_by_day = calc_thithi_transitions_for_range(padded_start, padded_end, DEFAULT_TIMEZONE, TUNING)
    out = {}
    d = padded_start
    while d <= padded_end:
        sunrise, _ = get_sunrise_sunset(d, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE)
        out[d] = _active_at(thithi_by_day[d], sunrise).thithi.paksha
        d += timedelta(days=1)
    return out


def test_range_matches_per_day():
    batched = get_chandra_masa_dates_for_range(
        START, END, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE, TUNING,
        _paksha_by_day(START, END),
    )
    d = START
    while d <= END:
        expected = get_chandra_masa_date(
            dt=d, latitude=Coordinates.SG_LATITUDE, longitude=Coordinates.SG_LONGITUDE,
            timezone=DEFAULT_TIMEZONE,
        )
        actual = batched[d]
        assert actual.masa == expected.masa, f"{d}: masa mismatch"
        assert actual.masa_day == expected.masa_day, f"{d}: masa_day mismatch"
        assert actual.masa_type == expected.masa_type, f"{d}: masa_type mismatch"
        d += timedelta(days=1)


def test_range_matches_across_a_chunk_boundary():
    """get_panchangam_data_range calls this in ~30-day chunks; a range spanning
    two chunks must stitch back together with no gap or duplicate."""
    start = date(2026, 1, 20)
    end = date(2026, 3, 10)  # 50 days -- crosses at least one 30-day chunk edge
    batched = get_chandra_masa_dates_for_range(
        start, end, Coordinates.SG_LATITUDE, Coordinates.SG_LONGITUDE, DEFAULT_TIMEZONE, TUNING,
        _paksha_by_day(start, end),
    )
    d = start
    while d <= end:
        expected = get_chandra_masa_date(
            dt=d, latitude=Coordinates.SG_LATITUDE, longitude=Coordinates.SG_LONGITUDE,
            timezone=DEFAULT_TIMEZONE,
        )
        assert batched[d].masa == expected.masa, f"{d}: masa mismatch"
        assert batched[d].masa_day == expected.masa_day, f"{d}: masa_day mismatch"
        d += timedelta(days=1)
