"""
Unit tests for the offline pickle-cache day_offset shift logic:
features/santhigiri_events/offline_cache/cache_utils.py::shift_and_record/shift_date_for_offset and
features/santhigiri_events/offline_cache/cache_common_events.py::update_common_events.
"""
from __future__ import annotations

import datetime

from features.santhigiri_events.offline_cache import cache_common_events
from features.santhigiri_events.offline_cache.cache_common_events import update_common_events
from features.santhigiri_events.offline_cache.cache_utils import shift_and_record, shift_date_for_offset
from utils.santhigiri_events import EventCondition, SanthigiriEvent


def _cache(make_panchangam_data, year: int, days: int = 5):
    start = datetime.date(year, 1, 1)
    return {
        start + datetime.timedelta(days=i): make_panchangam_data(start + datetime.timedelta(days=i))
        for i in range(days)
    }


def _event(event_id: str, **condition_kwargs) -> SanthigiriEvent:
    return SanthigiriEvent(
        id=event_id, name=event_id, description=event_id,
        event_condition=EventCondition(**condition_kwargs),
    )


# ── shift_date_for_offset ────────────────────────────────────────────────────

def test_shift_date_for_offset_no_offset(make_panchangam_data):
    cache = _cache(make_panchangam_data, 2026)
    d = datetime.date(2026, 1, 1)
    assert shift_date_for_offset(cache, d, None) == d
    assert shift_date_for_offset(cache, d, 0) == d


def test_shift_date_for_offset_within_range(make_panchangam_data):
    cache = _cache(make_panchangam_data, 2026)
    d = datetime.date(2026, 1, 1)
    assert shift_date_for_offset(cache, d, 2) == datetime.date(2026, 1, 3)


def test_shift_date_for_offset_out_of_range_returns_none(make_panchangam_data):
    cache = _cache(make_panchangam_data, 2026, days=3)
    d = datetime.date(2026, 1, 3)
    assert shift_date_for_offset(cache, d, 5) is None


# ── shift_and_record ──────────────────────────────────────────────────────────

def test_shift_and_record_writes_to_shifted_date(make_panchangam_data):
    cache = _cache(make_panchangam_data, 2026)
    event = _event("TEST_EVENT")
    modified = set()
    dt = datetime.date(2026, 1, 1)
    shift_and_record(cache, dt, 2, event, modified)

    target = datetime.date(2026, 1, 3)
    assert event in cache[target].santhigiri_significant_dates
    assert cache[dt].santhigiri_significant_dates == []
    assert modified == {target}


def test_shift_and_record_dedups_two_events_onto_same_target(make_panchangam_data):
    cache = _cache(make_panchangam_data, 2026)
    modified = set()
    event_a = _event("EVENT_A")
    event_b = _event("EVENT_B")
    shift_and_record(cache, datetime.date(2026, 1, 1), 2, event_a, modified)
    shift_and_record(cache, datetime.date(2026, 1, 2), 1, event_b, modified)

    target = datetime.date(2026, 1, 3)
    assert modified == {target}
    ids = {e.id for e in cache[target].santhigiri_significant_dates}
    assert ids == {"EVENT_A", "EVENT_B"}


def test_shift_and_record_out_of_range_skips_without_raising(make_panchangam_data, capsys):
    cache = _cache(make_panchangam_data, 2026, days=3)
    event = _event("TEST_EVENT")
    modified = set()
    shift_and_record(cache, datetime.date(2026, 1, 3), 5, event, modified)

    assert modified == set()
    assert "WARNING" in capsys.readouterr().out


# ── update_common_events ───────────────────────────────────────────────────────

def test_update_common_events_applies_day_offset(make_panchangam_data, monkeypatch):
    cache = _cache(make_panchangam_data, 2026)
    event = _event("SHIFTED_EVENT", en_day=1, en_month=1, day_offset=2)
    monkeypatch.setattr(cache_common_events, "_COMMON_EVENTS", [event])

    updated = update_common_events(cache)

    target = datetime.date(2026, 1, 3)
    matched = datetime.date(2026, 1, 1)
    ids_at_target = {e.id for e in updated[target].santhigiri_significant_dates}
    assert "SHIFTED_EVENT" in ids_at_target
    assert updated[matched].santhigiri_significant_dates == []
