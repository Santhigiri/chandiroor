"""
ReferenceRepositoryPort — the subset of ``ReferenceRepository``
(implemented in ``db/reference_repository.py``) that
``features/etag/service.py`` and ``features/panchangam/router.py`` depend on
to read the enum/reference datasets (thithi, nakshatra, masa, events,
locations).

Lives in ``core/ports/`` (alongside ``unit_of_work.py``,
``settings_service.py``, and ``panchangam_service.py``) rather than in a
feature-local ``ports.py`` for the same reason as ``SettingsServicePort``:
``ReferenceRepository`` does not belong to a single feature — it backs the
reference endpoints mounted on ``features/panchangam/router.py`` and is also
consumed directly by ``features/etag/service.py`` to build enum payloads
when refreshing ETags — so the seam other modules depend on is a
``core/ports/`` Protocol, never a direct import of the concrete
``db/reference_repository.py::ReferenceRepository`` class.
"""
from __future__ import annotations

from typing import Any, Dict, List, Protocol

from app.schemas.compact_panchangam_data import CompactSanthigiriEvent


class ReferenceRepositoryPort(Protocol):
    def list_thithis(self) -> List[Dict[str, Any]]: ...

    def list_nakshatras(self) -> List[Dict[str, Any]]: ...

    def list_masas(self) -> List[Dict[str, Any]]: ...

    def list_locations(self) -> List[Dict[str, Any]]: ...

    def list_events(self) -> List[CompactSanthigiriEvent]: ...
