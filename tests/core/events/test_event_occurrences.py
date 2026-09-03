"""
Unit tests for the pure occurrence-computation algorithms in
core/events/event_occurrences.py — no DB involved.
"""
from __future__ import annotations

import datetime

import pytest

from app.core.astronomy.transitions import NakshatraTransition
from app.core.events.event_occurrences import (
    OccurrenceComputationError,
    UnsupportedEventCondition,
    classify_condition,
    compute_last_occurrence,
    compute_occurrences,
    compute_single_day_occurrences,
    compute_transition_series,
)
from app.core.kollavarsham.enums.masa import MalayalamMasa
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.santhigiri_events import EventCondition
from app.core.astronomy.enums.thithi import Thithi


def _year_days(year: int, make, **overrides):
    start = datetime.date(year, 1, 1)
    days = (datetime.date(year, 12, 31) - start).days + 1
    return {
        start + datetime.timedelta(days=i): make(start + datetime.timedelta(days=i), **overrides)
        for i in range(days)
    }


# ── classify_condition ──────────────────────────────────────────────────────

def test_classify_single_day_conditions():
    assert classify_condition(EventCondition(is_poornima=True)) == "single_day"
    assert classify_condition(EventCondition(en_day=1, en_month=1)) == "single_day"
    assert classify_condition(EventCondition(ml_day=10, ml_month=MalayalamMasa.MEDAM)) == "single_day"
    assert classify_condition(EventCondition(thithi=Thithi.DASHAMI_SHUKLA)) == "single_day"


def test_classify_last_occurrence_condition():
    cond = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI, last_occurance=True
    )
    assert classify_condition(cond) == "last_occurrence"


def test_classify_transition_series_condition():
    assert classify_condition(EventCondition(nakshatra=Nakshatra.CHOTHI)) == "transition_series"


def test_classify_unsupported_condition():
    with pytest.raises(UnsupportedEventCondition):
        classify_condition(EventCondition(ml_month=MalayalamMasa.CHINGAM))


# ── compute_single_day_occurrences ──────────────────────────────────────────

def test_single_day_matches_every_matching_day(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    # Override one day to be a poornima match.
    target = datetime.date(year, 3, 15)
    yearly[target] = make_panchangam_data(target, thithi=Thithi.POORNIMA)

    condition = EventCondition(en_day=5, en_month=11)
    matches = compute_single_day_occurrences(condition, yearly)
    assert matches == [datetime.date(year, 11, 5)]


def test_single_day_no_matches_returns_empty(make_panchangam_data):
    yearly = _year_days(2026, make_panchangam_data)
    condition = EventCondition(en_day=31, en_month=2)  # Feb 31 never exists
    assert compute_single_day_occurrences(condition, yearly) == []


# ── compute_last_occurrence ──────────────────────────────────────────────────

def test_last_occurrence_picks_last_direct_match_above_cutoff(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI, last_occurance=True
    )
    earlier = datetime.date(year, 8, 20)
    later = datetime.date(year, 8, 28)
    yearly[earlier] = make_panchangam_data(
        earlier, nakshatra=Nakshatra.CHOTHI, kv_month=MalayalamMasa.CHINGAM,
        nazhika_from_sunrise=10.0,
    )
    yearly[later] = make_panchangam_data(
        later, nakshatra=Nakshatra.CHOTHI, kv_month=MalayalamMasa.CHINGAM,
        nazhika_from_sunrise=20.0,
    )

    result = compute_last_occurrence(condition, yearly, year)
    assert result == later


def test_last_occurrence_shifts_back_a_day_below_cutoff(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI, last_occurance=True
    )
    matched = datetime.date(year, 8, 28)
    yearly[matched] = make_panchangam_data(
        matched, nakshatra=Nakshatra.CHOTHI, kv_month=MalayalamMasa.CHINGAM,
        nazhika_from_sunrise=5.0,  # below the 7.5 cutoff
    )

    result = compute_last_occurrence(condition, yearly, year)
    assert result == matched - datetime.timedelta(days=1)


def test_last_occurrence_falls_back_to_nakshatra_transition(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data, nakshatra=Nakshatra.ASWATHI)
    condition = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI, last_occurance=True
    )
    transition_day = datetime.date(year, 8, 25)
    start_time = datetime.datetime.combine(
        transition_day, datetime.time(4, 0), tzinfo=datetime.timezone.utc
    )
    yearly[transition_day] = make_panchangam_data(
        transition_day,
        nakshatra=Nakshatra.ASWATHI,
        kv_month=MalayalamMasa.CHINGAM,
        nakshatra_transitions=[
            NakshatraTransition(
                nakshatra=Nakshatra.CHOTHI,
                start_time=start_time,
                end_time=start_time + datetime.timedelta(hours=2),
            )
        ],
    )

    result = compute_last_occurrence(condition, yearly, year)
    assert result == transition_day


def test_last_occurrence_transition_date_uses_ist_not_utc(make_panchangam_data):
    """A transition just after IST midnight is still UTC-previous-day; the
    returned occurrence date must be the IST calendar day, not the UTC one."""
    year = 2026
    yearly = _year_days(year, make_panchangam_data, nakshatra=Nakshatra.ASWATHI)
    condition = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI, last_occurance=True
    )
    transition_day = datetime.date(year, 8, 25)
    # 00:30 IST on Aug 25 == 19:00 UTC on Aug 24.
    start_time = datetime.datetime(year, 8, 24, 19, 0, tzinfo=datetime.timezone.utc)
    yearly[transition_day] = make_panchangam_data(
        transition_day,
        nakshatra=Nakshatra.ASWATHI,
        kv_month=MalayalamMasa.CHINGAM,
        nakshatra_transitions=[
            NakshatraTransition(
                nakshatra=Nakshatra.CHOTHI,
                start_time=start_time,
                end_time=start_time + datetime.timedelta(hours=2),
            )
        ],
    )

    result = compute_last_occurrence(condition, yearly, year)
    assert result == transition_day


def test_last_occurrence_raises_when_nothing_found(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data, nakshatra=Nakshatra.ASWATHI)
    condition = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI, last_occurance=True
    )
    with pytest.raises(OccurrenceComputationError):
        compute_last_occurrence(condition, yearly, year)


# ── compute_transition_series ───────────────────────────────────────────────

def test_transition_series_lands_after_cutoff(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data, nakshatra=Nakshatra.ASWATHI)
    condition = EventCondition(nakshatra=Nakshatra.CHOTHI)

    d = datetime.date(year, 4, 10)
    sunrise = yearly[d].sunrise
    start_time = sunrise - datetime.timedelta(hours=1)
    end_time = sunrise + datetime.timedelta(hours=5)  # >3h after sunrise
    yearly[d] = make_panchangam_data(
        d,
        nakshatra_transitions=[
            NakshatraTransition(
                nakshatra=Nakshatra.CHOTHI,
                start_time=start_time, end_time=end_time,
            )
        ],
    )

    result = compute_transition_series(condition, yearly, year)
    assert result == [d]


def test_transition_series_shifts_back_within_cutoff(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data, nakshatra=Nakshatra.ASWATHI)
    condition = EventCondition(nakshatra=Nakshatra.CHOTHI)

    d = datetime.date(year, 4, 10)
    sunrise = yearly[d].sunrise
    start_time = sunrise - datetime.timedelta(hours=3)
    end_time = sunrise + datetime.timedelta(hours=1)  # within 3h of sunrise
    yearly[d] = make_panchangam_data(
        d,
        nakshatra_transitions=[
            NakshatraTransition(
                nakshatra=Nakshatra.CHOTHI,
                start_time=start_time, end_time=end_time,
            )
        ],
    )

    result = compute_transition_series(condition, yearly, year)
    assert result == [d - datetime.timedelta(days=1)]


def test_transition_series_returns_multiple_occurrences(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data, nakshatra=Nakshatra.ASWATHI)
    condition = EventCondition(nakshatra=Nakshatra.CHOTHI)

    for month, day in [(2, 5), (6, 12), (10, 20)]:
        d = datetime.date(year, month, day)
        sunrise = yearly[d].sunrise
        start_time = sunrise - datetime.timedelta(hours=1)
        end_time = sunrise + datetime.timedelta(hours=5)
        yearly[d] = make_panchangam_data(
            d,
            nakshatra_transitions=[
                NakshatraTransition(
                    nakshatra=Nakshatra.CHOTHI,
                    start_time=start_time, end_time=end_time,
                )
            ],
        )

    result = compute_transition_series(condition, yearly, year)
    assert result == [datetime.date(year, 2, 5), datetime.date(year, 6, 12), datetime.date(year, 10, 20)]


# ── compute_occurrences dispatch ────────────────────────────────────────────

def test_compute_occurrences_dispatches_single_day(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(en_day=5, en_month=11)
    result = compute_occurrences(condition, yearly, year)
    assert result == [datetime.date(year, 11, 5)]


def test_compute_occurrences_dispatches_last_occurrence(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI, last_occurance=True
    )
    match = datetime.date(year, 8, 28)
    yearly[match] = make_panchangam_data(
        match, nakshatra=Nakshatra.CHOTHI, kv_month=MalayalamMasa.CHINGAM,
        nazhika_from_sunrise=20.0,
    )
    assert compute_occurrences(condition, yearly, year) == [match]


def test_compute_occurrences_raises_for_unsupported(make_panchangam_data):
    yearly = _year_days(2026, make_panchangam_data)
    condition = EventCondition(ml_month=MalayalamMasa.CHINGAM)
    with pytest.raises(UnsupportedEventCondition):
        compute_occurrences(condition, yearly, 2026)


# ── compute_occurrences day_offset ──────────────────────────────────────────

def test_compute_occurrences_applies_positive_offset_single_day(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(en_day=5, en_month=11, day_offset=3)
    result = compute_occurrences(condition, yearly, year)
    assert result == [datetime.date(year, 11, 8)]


def test_compute_occurrences_applies_negative_offset_single_day(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(en_day=5, en_month=11, day_offset=-1)
    result = compute_occurrences(condition, yearly, year)
    assert result == [datetime.date(year, 11, 4)]


def test_compute_occurrences_applies_offset_to_transition_series(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data, nakshatra=Nakshatra.ASWATHI)
    condition = EventCondition(nakshatra=Nakshatra.CHOTHI, day_offset=2)

    d = datetime.date(year, 4, 10)
    sunrise = yearly[d].sunrise
    start_time = sunrise - datetime.timedelta(hours=1)
    end_time = sunrise + datetime.timedelta(hours=5)
    yearly[d] = make_panchangam_data(
        d,
        nakshatra_transitions=[
            NakshatraTransition(
                nakshatra=Nakshatra.CHOTHI,
                start_time=start_time, end_time=end_time,
            )
        ],
    )

    result = compute_occurrences(condition, yearly, year)
    assert result == [d + datetime.timedelta(days=2)]


def test_compute_occurrences_applies_offset_to_last_occurrence(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI,
        last_occurance=True, day_offset=-2,
    )
    match = datetime.date(year, 8, 28)
    yearly[match] = make_panchangam_data(
        match, nakshatra=Nakshatra.CHOTHI, kv_month=MalayalamMasa.CHINGAM,
        nazhika_from_sunrise=20.0,
    )
    assert compute_occurrences(condition, yearly, year) == [
        match - datetime.timedelta(days=2)
    ]


def test_compute_occurrences_zero_offset_is_noop(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(en_day=5, en_month=11, day_offset=0)
    assert compute_occurrences(condition, yearly, year) == [datetime.date(year, 11, 5)]


def test_compute_occurrences_offset_crossing_year_boundary_raises(make_panchangam_data):
    year = 2026
    yearly = _year_days(year, make_panchangam_data)
    condition = EventCondition(en_day=31, en_month=12, day_offset=2)
    with pytest.raises(OccurrenceComputationError):
        compute_occurrences(condition, yearly, year)
