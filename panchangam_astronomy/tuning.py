"""
``AstronomyTuning`` bundles the low-level Skyfield search parameters used by
the transition-detection and Kollavarsham calculations, so callers thread one
object through :func:`core.calendar.panchangam.get_panchangam_data` instead of
five separate scalar parameters.

A plain frozen dataclass, not a Pydantic model: ``core/`` must not define
response/request schemas (see CLAUDE.md's layer-boundary rules) — this is a
parameter bundle, not a schema. Every field defaults to today's hardcoded
constant, so omitting ``tuning`` entirely reproduces current behavior exactly;
``services/`` is the only layer that resolves non-default values (from
``SettingsService``) and passes them in.
"""
from __future__ import annotations

from dataclasses import dataclass

from panchangam_astronomy.constants import NAKSHATRA_TRANSITION_STEP_DAYS


@dataclass(frozen=True)
class AstronomyTuning:
    nakshatra_step_days: float = NAKSHATRA_TRANSITION_STEP_DAYS
    nakshatra_epsilon: float = 1e-8
    nakshatra_num: int = 12
    thithi_step_days: float = 0.01
    thithi_num: int = 100
    kollavarsham_epsilon: float = 1e-6
