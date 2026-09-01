"""
Request/response schemas for the admin-editable ``app_setting`` table
(``/api/v1/settings``), plus the per-key value shapes stored in its JSON
``value`` column.

``AppSettingRead``/``AppSettingUpdate`` are the generic envelope; the actual
shape of ``value`` depends on the key (see ``utils.settings_keys.SettingKey``)
and is validated by ``features.settings.service.SettingsService`` against one
of the models below before a write is ever persisted. Each model's field
defaults intentionally mirror today's hardcoded constants, so constructing one
with no arguments reproduces current behavior exactly — the fallback
``SettingsService`` uses when a key's row is absent.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from panchangam_astronomy.constants import NAKSHATRA_TRANSITION_STEP_DAYS
from app.utils.location import DEFAULT_LOCATION_CODE


class AppSettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: dict
    description: Optional[str] = None
    updated_at: datetime
    updated_by: Optional[str] = None


class AppSettingUpdate(BaseModel):
    """Full replace of a setting's ``value``."""

    value: dict


# ── Per-key value shapes ──────────────────────────────────────────────────────

class SeedYearRangeValue(BaseModel):
    """The inclusive year range the DB is expected to have panchangam data
    seeded for. Drives the valid ``year`` bound on ``/panchangam/month`` and
    ``/panchangam/year``, and the default range offline tooling reads."""

    start_year: int = Field(default=2021, ge=1)
    end_year: int = Field(default=2030, ge=1)


class DefaultLocationCodeValue(BaseModel):
    """The location code (``location.name`` in the DB, e.g. ``"tvm"``) served
    when a request omits ``?location=``. Validated against a known
    ``utils.location.Location`` code by ``SettingsService`` on write — this
    schema only pins the JSON shape."""

    code: str = Field(default=DEFAULT_LOCATION_CODE, min_length=1)


class MaxGenerateSpanDaysValue(BaseModel):
    """Shared cap on the size of a live-generation date range (panchangam
    and kollavarsham ``/generate`` endpoints) — bounds Skyfield work per
    request."""

    max_days: int = Field(default=366, ge=1)


class MaxEventGenerateYearSpanValue(BaseModel):
    """Cap on the size of a Santhigiri event occurrence-generation year range."""

    max_years: int = Field(default=15, ge=1)


class EventCutoffsValue(BaseModel):
    """Day-attribution conventions used when computing Santhigiri event
    occurrences: the "7.5 Nazhika rule" for last-occurrence events, and the
    "3-hour" cutoff for nakshatra-transition-series events."""

    nazhika_cutoff: float = Field(default=7.5, ge=0, le=60)
    transition_hour_cutoff: float = Field(default=3.0, ge=0, le=24)


class NakshatraStepDaysValue(BaseModel):
    """Skyfield search step (days) used to find Nakshatra transitions, with
    optional per-year overrides (e.g. 2028 needs a coarser 0.05 step — see
    CLAUDE.md's "Transitions" section). ``overrides`` keys are Gregorian
    years as strings (JSON object keys are always strings)."""

    default: float = Field(default=NAKSHATRA_TRANSITION_STEP_DAYS, gt=0, le=1)
    overrides: Dict[str, float] = Field(default_factory=dict)

    def step_days_for_year(self, year: int) -> float:
        return self.overrides.get(str(year), self.default)


class AstronomyEpsilonsValue(BaseModel):
    """Small boundary-tie epsilons used by the discrete-transition search and
    the Kollavarsham raasi calculation. Fragile, correctness-critical
    internals — see CLAUDE.md's warning on ``NAKSHATRA_TRANSITION_STEP_DAYS``;
    the same caution applies here."""

    nakshatra_epsilon: float = Field(default=1e-8, gt=0, lt=1)
    kollavarsham_epsilon: float = Field(default=1e-6, gt=0, lt=1)
