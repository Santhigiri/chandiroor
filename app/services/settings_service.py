"""
SettingsService — CRUD for the admin-editable ``app_setting`` table, plus
typed getters used by the rest of the app (``services/``, offline
``features/santhigiri_events/offline_cache/cache_*.py`` tooling).

Every typed getter falls back to today's hardcoded constant when a key's row
is absent (or, defensively, if a stored value somehow fails validation) — see
each per-key Pydantic model in ``schemas/app_setting.py``, whose defaults
mirror the constants being replaced. This makes rollout zero-downtime: a
freshly-deployed database with no ``app_setting`` rows yet behaves exactly
like the pre-settings code (see ``db/sql/migrations/0004_add_app_setting_table.sql``).

``core/`` never resolves settings itself (per CLAUDE.md's layer boundaries) —
only this service does, translating a stored JSON value into the plain
scalars/dataclasses that ``core/astronomy`` and ``core/calendar`` accept as
function parameters.

This module stays in ``services/`` (not ``features/settings/service.py``)
because, unlike ``AuthService``/``SanthigiriEventService``, it is used
directly by 3+ other features' own services (see CLAUDE.md's "services/"
section) — but it is otherwise built the same way as a migrated feature's
service: a frozen dataclass depending on ``AppSettingRepositoryPort`` (from
``features/settings/ports.py``) and a ``UnitOfWork``, never on the concrete
adapter class.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.astronomy.tuning import AstronomyTuning
from app.core.ports.unit_of_work import UnitOfWork
from app.features.settings.ports import AppSettingGet, AppSettingRepositoryPort
from app.schemas.app_setting import (
    AppSettingUpdate,
    AstronomyEpsilonsValue,
    DefaultLocationCodeValue,
    EventCutoffsValue,
    MaxEventGenerateYearSpanValue,
    MaxGenerateSpanDaysValue,
    NakshatraStepDaysValue,
    SeedYearRangeValue,
)
from app.utils.location import DEFAULT_LOCATION_CODE, Location
from app.utils.settings_keys import SettingKey

T = TypeVar("T", bound=BaseModel)

_VALUE_MODELS: Dict[SettingKey, Type[BaseModel]] = {
    SettingKey.SEED_YEAR_RANGE: SeedYearRangeValue,
    SettingKey.DEFAULT_LOCATION_CODE: DefaultLocationCodeValue,
    SettingKey.MAX_GENERATE_SPAN_DAYS: MaxGenerateSpanDaysValue,
    SettingKey.MAX_EVENT_GENERATE_YEAR_SPAN: MaxEventGenerateYearSpanValue,
    SettingKey.EVENT_CUTOFFS: EventCutoffsValue,
    SettingKey.NAKSHATRA_TRANSITION_STEP_DAYS: NakshatraStepDaysValue,
    SettingKey.ASTRONOMY_EPSILONS: AstronomyEpsilonsValue,
}


class SettingNotFound(Exception):
    """Raised when reading/updating a key name that isn't a known SettingKey."""


class InvalidSettingValue(Exception):
    """Raised when a PUT payload's ``value`` doesn't match the key's expected shape."""


@dataclass(frozen=True)
class SettingsService:
    app_setting_repository: AppSettingRepositoryPort
    uow: UnitOfWork

    # ── Generic CRUD (admin API) ──────────────────────────────────────────────

    def list_all(self) -> list[AppSettingGet]:
        return self.app_setting_repository.list_all()

    def get_row(self, key: str) -> AppSettingGet:
        """Return the stored row for *key*, or a synthesized (unpersisted)
        default row if *key* is a known :class:`SettingKey` with no row yet —
        so an admin GET always reflects the value actually in effect, even
        before the seed migration has run. Only an unknown key name 404s."""
        try:
            setting_key = SettingKey(key)
        except ValueError as exc:
            raise SettingNotFound(key) from exc
        row = self.app_setting_repository.get(key)
        if row is not None:
            return row
        model = _VALUE_MODELS[setting_key]
        return AppSettingGet(
            key=key,
            value=model().model_dump(),
            description=None,
            updated_at=datetime.now(timezone.utc),
            updated_by=None,
        )

    def update(
        self, key: str, payload: AppSettingUpdate, updated_by: Optional[str] = None
    ) -> AppSettingGet:
        """Validate *payload.value* against *key*'s shape and persist it.

        Unknown *key* -> :class:`SettingNotFound`. A shape/range mismatch ->
        :class:`InvalidSettingValue`. ``default_location_code`` additionally
        validates the code resolves to a real :class:`Location`. Commits.
        """
        try:
            setting_key = SettingKey(key)
        except ValueError as exc:
            raise SettingNotFound(key) from exc

        model = _VALUE_MODELS[setting_key]
        try:
            validated = model.model_validate(payload.value)
        except ValidationError as exc:
            raise InvalidSettingValue(str(exc)) from exc

        if setting_key is SettingKey.DEFAULT_LOCATION_CODE:
            assert isinstance(validated, DefaultLocationCodeValue)
            try:
                Location.from_code(validated.code)
            except KeyError as exc:
                raise InvalidSettingValue(
                    f"Unknown location code: {validated.code!r}"
                ) from exc

        with self.uow as uow:
            row = self.app_setting_repository.upsert(
                key, validated.model_dump(), updated_by=updated_by
            )
            uow.commit()
            return row

    # ── Typed getters (used by services/ & offline tooling) ────────────────────

    def _value(self, key: SettingKey, model: Type[T]) -> T:
        row = self.app_setting_repository.get(key.value)
        if row is None:
            return model()
        try:
            return model.model_validate(row.value)
        except ValidationError:
            return model()

    def get_seed_year_range(self) -> Tuple[int, int]:
        v = self._value(SettingKey.SEED_YEAR_RANGE, SeedYearRangeValue)
        return v.start_year, v.end_year

    def get_default_location_code(self) -> str:
        row = self.app_setting_repository.get(SettingKey.DEFAULT_LOCATION_CODE.value)
        if row is None:
            return DEFAULT_LOCATION_CODE
        try:
            code = DefaultLocationCodeValue.model_validate(row.value).code
            Location.from_code(code)
        except (ValidationError, KeyError):
            return DEFAULT_LOCATION_CODE
        return code

    def get_max_generate_span_days(self) -> int:
        return self._value(
            SettingKey.MAX_GENERATE_SPAN_DAYS, MaxGenerateSpanDaysValue
        ).max_days

    def get_max_event_generate_year_span(self) -> int:
        return self._value(
            SettingKey.MAX_EVENT_GENERATE_YEAR_SPAN, MaxEventGenerateYearSpanValue
        ).max_years

    def get_event_cutoffs(self) -> EventCutoffsValue:
        return self._value(SettingKey.EVENT_CUTOFFS, EventCutoffsValue)

    def get_astronomy_tuning(self, year: int) -> AstronomyTuning:
        """Resolve the concrete tuning to use for *year* — the per-year
        Nakshatra step override (see ``NakshatraStepDaysValue``) plus the
        shared epsilon settings. Never touches ``core/`` — the caller passes
        the returned dataclass straight through."""
        step_days_value = self._value(
            SettingKey.NAKSHATRA_TRANSITION_STEP_DAYS, NakshatraStepDaysValue
        )
        epsilons = self._value(SettingKey.ASTRONOMY_EPSILONS, AstronomyEpsilonsValue)
        return AstronomyTuning(
            nakshatra_step_days=step_days_value.step_days_for_year(year),
            nakshatra_epsilon=epsilons.nakshatra_epsilon,
            kollavarsham_epsilon=epsilons.kollavarsham_epsilon,
        )
