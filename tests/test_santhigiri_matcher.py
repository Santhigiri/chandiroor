"""Tests for core/calendar/santhigiri_significant_dates.py — the live-fallback
event matcher — and the PanchangamService overlay that uses it."""
import datetime

from core.calendar.santhigiri_significant_dates import (
    event_matches,
    match_condition_based_events,
)
from db.repository import PanchangamRepository
from features.panchangam.service import PanchangamService
from utils.location import Location
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import EVENT_DEFINITIONS_BY_ID
from utils.thithi import Thithi

TVM = Location.TVM


def _event(event_id):
    return EVENT_DEFINITIONS_BY_ID[event_id]


# ── event_matches: positives ──────────────────────────────────────────────────

def test_matches_pournami_on_real_full_moon(make_panchangam_data):
    """POURNAMI (is_poornima only) matches on a real full-moon Gregorian date."""
    # 2026-01-02 is a Pournami per tests/test_is_pournami.py.
    data = make_panchangam_data(datetime.date(2026, 1, 2))
    assert event_matches(_event("POURNAMI").event_condition, data) is True


def test_matches_navoli_on_english_date(make_panchangam_data):
    """NAVOLI_JYOTHIR_DINAM matches by English day/month (May 6)."""
    data = make_panchangam_data(datetime.date(2026, 5, 6))
    assert event_matches(_event("NAVOLI_JYOTHIR_DINAM").event_condition, data) is True


def test_matches_poornakumbamela_on_malayalam_date(make_panchangam_data):
    """POORNA_KUMBAMELA matches by Malayalam month/day (Kanni 4)."""
    data = make_panchangam_data(
        datetime.date(2026, 9, 20), kv_month=MalayalamMasa.KANNI, kv_day=4
    )
    assert event_matches(_event("POORNA_KUMBAMELA").event_condition, data) is True


def test_matches_sanyasadeeksha_on_thithi(make_panchangam_data):
    """SANYASADHEEKSHA matches on Thulam + Dashami (Shukla)."""
    data = make_panchangam_data(
        datetime.date(2026, 10, 20),
        kv_month=MalayalamMasa.THULAM,
        thithi=Thithi.DASHAMI_SHUKLA,
    )
    assert event_matches(
        _event("SANYASADHEEKSHA_VARSHIKAM").event_condition, data
    ) is True


# ── event_matches: negatives ──────────────────────────────────────────────────

def test_pournami_condition_does_not_match_non_full_moon(make_panchangam_data):
    """A day that is not a full moon must not match POURNAMI."""
    # 2026-05-15 is not a Pournami per tests/test_is_pournami.py.
    data = make_panchangam_data(datetime.date(2026, 5, 15))
    assert event_matches(_event("POURNAMI").event_condition, data) is False


def test_last_occurance_event_never_matches(make_panchangam_data):
    """NAVAPOOJITHAM (last_occurance) needs whole-year context — never matched here,
    even on a day satisfying its Chingam + Chothi fields."""
    data = make_panchangam_data(
        datetime.date(2026, 8, 30),
        kv_month=MalayalamMasa.CHINGAM,
        nakshatra=Nakshatra.CHOTHI,
    )
    assert event_matches(_event("NAVAPOOJITHAM").event_condition, data) is False


def test_nakshatra_only_event_never_matches(make_panchangam_data):
    """JANMAGRIHA (nakshatra-only) pins no single day — never matched here, even on
    a Chothi day."""
    data = make_panchangam_data(
        datetime.date(2026, 3, 3), nakshatra=Nakshatra.CHOTHI
    )
    assert event_matches(
        _event("JANMAGRIHA_THEERTHA_YATHRA").event_condition, data
    ) is False


# ── match_condition_based_events: day_offset exclusion ────────────────────────

def test_match_condition_based_events_excludes_day_offset_conditions(make_panchangam_data):
    """An event with a nonzero day_offset is excluded from the single-day
    matcher even when its other fields would otherwise match — this matcher
    only sees one day and cannot tell if that day is a shift target."""
    data = make_panchangam_data(datetime.date(2026, 5, 6))
    offset_event = _event("NAVOLI_JYOTHIR_DINAM").model_copy(
        update={
            "event_condition": _event("NAVOLI_JYOTHIR_DINAM").event_condition.model_copy(
                update={"day_offset": 1}
            )
        }
    )
    matched = match_condition_based_events(data, [offset_event])
    assert matched == []


# ── match_condition_based_events ──────────────────────────────────────────────

def test_match_condition_based_events_filters_the_list(make_panchangam_data):
    data = make_panchangam_data(datetime.date(2026, 5, 6))
    matched = match_condition_based_events(
        data, list(EVENT_DEFINITIONS_BY_ID.values())
    )
    ids = {e.id for e in matched}
    # The English-dated Navoli matches; bespoke/last-occurrence events do not.
    assert "NAVOLI_JYOTHIR_DINAM" in ids
    assert "NAVAPOOJITHAM" not in ids
    assert "JANMAGRIHA_THEERTHA_YATHRA" not in ids


# ── Service overlay on a live-fallback date ───────────────────────────────────

def test_service_overlays_events_on_live_fallback_date(seeded_session):
    """A date absent from the DB is computed live and still carries its
    condition-based events, pulled from the seeded event definitions."""
    service = PanchangamService(PanchangamRepository(seeded_session))

    # No panchangam rows are seeded, so this always takes the live-compute path.
    data = service.get_by_date(datetime.date(2035, 5, 6), TVM)

    ids = {e.id for e in data.santhigiri_significant_dates}
    assert "NAVOLI_JYOTHIR_DINAM" in ids
