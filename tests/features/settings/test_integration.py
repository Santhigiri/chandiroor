"""
Cross-cutting tests demonstrating that admin-editable settings actually
change behavior end-to-end, not just that the CRUD endpoints round-trip a
JSON blob (see tests/test_app_settings_crud.py for that).
"""
from __future__ import annotations

import datetime
from typing import Dict

import pytest

from panchangam_astronomy.nakshatra_transition import make_nakshatra_transition_fn
from panchangam_astronomy.thithi_transition import make_thithi_transition_fn
from app.core.calendar.santhigiri_event_occurrences import compute_last_occurrence
from app.schemas.app_setting import AppSettingUpdate
from app.db.unit_of_work import SqlUnitOfWork
from app.features.panchangam.service import PanchangamService, YearOutOfRange
from app.features.settings.repository import AppSettingRepository
from app.features.settings.service import SettingsService
from app.utils.malayalam_masa import MalayalamMasa
from panchangam_astronomy.enums.nakshatra import Nakshatra
from app.utils.santhigiri_events import EventCondition
from app.utils.settings_keys import SettingKey


# ── seed_year_range gates PanchangamService.get_by_year/get_by_month ────────

class _FullYearStubRepo:
    """A fake PanchangamRepository that always has every requested day —
    so the range check is what's under test, not live computation."""

    def __init__(self, make_panchangam_data):
        self._make = make_panchangam_data

    def get_by_date_range(self, start, end, location):
        days: Dict[datetime.date, object] = {}
        d = start
        while d <= end:
            days[d] = self._make(d)
            d += datetime.timedelta(days=1)
        return days

    def list_event_definitions(self):
        return []


def test_seed_year_range_setting_gates_get_by_year(session, make_panchangam_data):
    settings_service = SettingsService(AppSettingRepository(session), SqlUnitOfWork(session))
    service = PanchangamService(_FullYearStubRepo(make_panchangam_data), settings_service)

    # Default setting (2021-2030, from SettingsService's fallback) rejects 2031.
    with pytest.raises(YearOutOfRange):
        service.get_by_year(2031)

    # Widen the range via the admin API's underlying service call.
    settings_service.update(
        SettingKey.SEED_YEAR_RANGE.value,
        AppSettingUpdate(value={"start_year": 2021, "end_year": 2035}),
    )

    # 2031 is now accepted and served (from the stub repo, no live compute needed).
    result = service.get_by_year(2031)
    assert len(result) == 365


def test_seed_year_range_setting_gates_get_by_month(session, make_panchangam_data):
    settings_service = SettingsService(AppSettingRepository(session), SqlUnitOfWork(session))
    service = PanchangamService(_FullYearStubRepo(make_panchangam_data), settings_service)

    with pytest.raises(YearOutOfRange):
        service.get_by_month(2031, 1)

    settings_service.update(
        SettingKey.SEED_YEAR_RANGE.value,
        AppSettingUpdate(value={"start_year": 2021, "end_year": 2035}),
    )
    result = service.get_by_month(2031, 1)
    assert len(result) > 0


# ── event_cutoffs changes which day a last-occurrence event lands on ────────

def test_event_nazhika_cutoff_flips_last_occurrence_day(make_panchangam_data):
    year = 2026
    target = datetime.date(year, 8, 20)
    yearly = {
        target: make_panchangam_data(
            target,
            kv_month=MalayalamMasa.CHINGAM,
            nakshatra=Nakshatra.CHOTHI,
            nazhika_from_sunrise=6.0,
        )
    }
    condition = EventCondition(
        ml_month=MalayalamMasa.CHINGAM, nakshatra=Nakshatra.CHOTHI, last_occurance=True
    )

    # Default cutoff (7.5): 6.0 nazhikas is below it -> shifts back a day.
    assert compute_last_occurrence(condition, yearly, year) == target - datetime.timedelta(days=1)

    # A lower admin-configured cutoff (e.g. 5.0) puts 6.0 above it -> stays on the day.
    assert compute_last_occurrence(condition, yearly, year, nazhika_cutoff=5.0) == target


# ── nakshatra_transition_step_days per-year override resolves via SettingsService ──

def test_nakshatra_step_days_per_year_override(session):
    settings_service = SettingsService(AppSettingRepository(session), SqlUnitOfWork(session))

    # No row stored yet -> falls back to core.constants' global default for every year.
    from panchangam_astronomy.constants import NAKSHATRA_TRANSITION_STEP_DAYS

    assert settings_service.get_astronomy_tuning(2027).nakshatra_step_days == NAKSHATRA_TRANSITION_STEP_DAYS
    assert settings_service.get_astronomy_tuning(2028).nakshatra_step_days == NAKSHATRA_TRANSITION_STEP_DAYS

    settings_service.update(
        SettingKey.NAKSHATRA_TRANSITION_STEP_DAYS.value,
        AppSettingUpdate(value={"default": 0.01, "overrides": {"2028": 0.05}}),
    )

    assert settings_service.get_astronomy_tuning(2027).nakshatra_step_days == 0.01
    assert settings_service.get_astronomy_tuning(2028).nakshatra_step_days == 0.05
    assert settings_service.get_astronomy_tuning(2029).nakshatra_step_days == 0.01


# ── Closure-factory regression: independent step_days per call ──────────────

def test_nakshatra_transition_closures_are_independent():
    """Regression test for the module-attribute-mutation bug this refactor
    fixes: two concurrently-built transition functions with different step
    sizes must not clobber each other's `.step_days`."""
    fn_a = make_nakshatra_transition_fn(eps=1e-8, step_days=0.01)
    fn_b = make_nakshatra_transition_fn(eps=1e-8, step_days=0.05)

    assert fn_a.step_days == 0.01
    assert fn_b.step_days == 0.05
    # Building fn_b did not retroactively change fn_a's step_days (would have,
    # under the old shared-module-attribute-mutation approach).
    assert fn_a.step_days == 0.01


def test_thithi_transition_closures_are_independent():
    fn_a = make_thithi_transition_fn(step_days=0.01)
    fn_b = make_thithi_transition_fn(step_days=0.0007)

    assert fn_a.step_days == 0.01
    assert fn_b.step_days == 0.0007
    assert fn_a.step_days == 0.01
