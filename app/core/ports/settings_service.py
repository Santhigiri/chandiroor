"""
SettingsServicePort — the subset of ``SettingsService`` (implemented in
``features/settings/service.py``) that other features' own services depend
on for typed setting getters.

This lives in ``core/ports/`` (alongside ``unit_of_work.py``) rather than in
``features/settings/ports.py`` because, unlike a repository port, it is
consumed directly by 3+ *other* features' ``service.py`` modules
(``panchangam``, its generation path, and ``santhigiri_events``) — the same
reason ``SettingsService`` itself used to live outside any feature folder.
Depending on this Protocol instead of the concrete ``SettingsService`` class
is what lets those cross-feature imports satisfy CLAUDE.md's layer-boundary
rule while ``SettingsService`` lives inside ``features/settings/``.

CRUD methods (``list_all``/``get_row``/``update``) are not part of this
port — only ``features/settings/router.py`` calls those, and it may depend
on the concrete ``SettingsService`` directly since it owns that feature.
"""
from __future__ import annotations

from typing import Protocol, Tuple

from app.core.astronomy.tuning import AstronomyTuning
from app.schemas.app_setting import EventCutoffsValue


class SettingsServicePort(Protocol):
    def get_seed_year_range(self) -> Tuple[int, int]: ...

    def get_max_generate_span_days(self) -> int: ...

    def get_max_event_generate_year_span(self) -> int: ...

    def get_event_cutoffs(self) -> EventCutoffsValue: ...

    def get_astronomy_tuning(self, year: int) -> AstronomyTuning: ...
