"""
PanchangamServicePort — the subset of ``PanchangamService`` (implemented in
``features/panchangam/service.py``) that ``features/etag/service.py`` depends
on to rebuild a year's compact payload when recomputing ETags.

Lives in ``core/ports/`` (alongside ``unit_of_work.py`` and
``settings_service.py``) for the same reason as ``SettingsServicePort``: it
is the seam a *different* feature's module (`etag`) depends on instead of
importing ``features.panchangam.service.PanchangamService`` directly, which
the layer-boundary rule forbids.

Deliberately narrower than the full read-service: it does not carry
``PanchangamService``'s ``seed_year_range`` enforcement as part of the
contract. The instance ``api/deps.py`` binds for ETag-refresh callers is
built without a ``SettingsServicePort``, so ``get_by_year`` never raises
``YearOutOfRange`` there — preserving the range-check-free behaviour the
bulk ETag refresh has always had (it runs right after a write that may
target years outside the currently configured ``seed_year_range``).
"""
from __future__ import annotations

from datetime import date
from typing import Dict, Protocol

from app.schemas.panchangam_data import PanchangamData
from app.utils.location import Location


class PanchangamServicePort(Protocol):
    def get_by_year(
        self, year: int, location: Location
    ) -> Dict[date, PanchangamData]: ...
