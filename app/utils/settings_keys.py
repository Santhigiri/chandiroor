"""
Known ``app_setting`` keys.

A plain string ``Enum`` (mirrors ``utils.roles.Role``) so call sites reference
a named constant instead of a magic string. Each member's value shape is
defined by the matching Pydantic model in ``shared/schemas/app_setting.py``.
"""
from __future__ import annotations

from enum import Enum


class SettingKey(str, Enum):
    SEED_YEAR_RANGE = "seed_year_range"
    DEFAULT_LOCATION_CODE = "default_location_code"
    MAX_GENERATE_SPAN_DAYS = "max_generate_span_days"
    MAX_EVENT_GENERATE_YEAR_SPAN = "max_event_generate_year_span"
    EVENT_CUTOFFS = "event_cutoffs"
    NAKSHATRA_TRANSITION_STEP_DAYS = "nakshatra_transition_step_days"
    ASTRONOMY_EPSILONS = "astronomy_epsilons"
