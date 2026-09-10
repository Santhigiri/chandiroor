"""Regression coverage for the range-batched transition search
(``calc_thithi_transitions_for_range``/``calc_nakshatra_transitions_for_range``,
and ``core.calendar.panchangam.get_panchangam_data_range``): every result must
match calling the existing per-day functions once per day, since the batched
path exists purely as a performance optimization for
``PanchangamGenerationService`` -- not a behavior change.

Also guards against the bug this batching surfaced: ``get_sidereal_longitude_from_time``
used to compute ayanamsa once from a ``find_discrete`` sample array's first
element and broadcast it across the whole array. Harmless for the ~1-5 day
windows the per-day search opens, but wrong once ``find_discrete`` is handed a
much wider range in one call (its first, coarse pass sees the *entire* range as
one array) -- a stale ayanamsa value could tip a sample right at a boundary to
the wrong side, producing a spurious extra transition. These tests would catch
that regressing.
"""
from datetime import date, timedelta

from app.core.astronomy.nakshatra_transition import (
    calc_nakshatra_transition_for_date,
    calc_nakshatra_transitions_for_range,
)
from app.core.astronomy.thithi_transition import (
    calc_thithi_transition_for_date,
    calc_thithi_transitions_for_range,
)
from app.core.astronomy.tuning import AstronomyTuning
from app.core.calendar.panchangam import get_panchangam_data, get_panchangam_data_range
from app.core.astronomy.constants import DEFAULT_TIMEZONE

START = date(2026, 2, 1)
END = date(2026, 2, 14)  # 14 days -- enough to span several transitions of each kind
TUNING = AstronomyTuning()


def _dates():
    d = START
    while d <= END:
        yield d
        d += timedelta(days=1)


def test_thithi_range_matches_per_day():
    batched = calc_thithi_transitions_for_range(START, END, DEFAULT_TIMEZONE, TUNING)
    for d in _dates():
        expected = calc_thithi_transition_for_date(d, DEFAULT_TIMEZONE, TUNING)
        actual = batched[d]
        assert len(actual) == len(expected), f"{d}: transition count differs"
        for e, a in zip(expected, actual):
            assert e.thithi == a.thithi
            assert abs((e.start_time - a.start_time).total_seconds()) < 1
            assert e.end_time is None or abs((e.end_time - a.end_time).total_seconds()) < 1


def test_nakshatra_range_matches_per_day():
    batched = calc_nakshatra_transitions_for_range(START, END, DEFAULT_TIMEZONE, TUNING)
    for d in _dates():
        expected = calc_nakshatra_transition_for_date(d, DEFAULT_TIMEZONE, TUNING)
        actual = batched[d]
        assert len(actual) == len(expected), f"{d}: transition count differs"
        for e, a in zip(expected, actual):
            assert e.nakshatra == a.nakshatra
            assert abs((e.start_time - a.start_time).total_seconds()) < 1
            assert e.end_time is None or abs((e.end_time - a.end_time).total_seconds()) < 1


def test_panchangam_data_range_matches_per_day_calls():
    batched = get_panchangam_data_range(
        START, END, timezone=DEFAULT_TIMEZONE, tuning_for_year=lambda year: TUNING
    )
    for d in _dates():
        expected = get_panchangam_data(d, timezone=DEFAULT_TIMEZONE, tuning=TUNING)
        actual = batched[d]
        assert actual.thithi == expected.thithi
        assert actual.nakshatra == expected.nakshatra
        assert actual.sunrise == expected.sunrise
        assert actual.sunset == expected.sunset
        assert actual.kv == expected.kv
        assert abs(actual.nazhika_from_sunrise - expected.nazhika_from_sunrise) < 1e-6


def test_panchangam_data_range_matches_across_a_chunk_boundary():
    """get_panchangam_data_range internally splits into ~30-day chunks (see its
    docstring); a range spanning two chunks must stitch back together with no
    gap or duplicate at the boundary."""
    start = date(2026, 1, 20)
    end = date(2026, 3, 10)  # 50 days -- crosses at least one 30-day chunk edge
    batched = get_panchangam_data_range(
        start, end, timezone=DEFAULT_TIMEZONE, tuning_for_year=lambda year: TUNING
    )
    d = start
    while d <= end:
        expected = get_panchangam_data(d, timezone=DEFAULT_TIMEZONE, tuning=TUNING)
        actual = batched[d]
        assert actual.thithi == expected.thithi, f"{d}: thithi mismatch"
        assert actual.nakshatra == expected.nakshatra, f"{d}: nakshatra mismatch"
        d += timedelta(days=1)
