"""
ReferenceRepositoryPort — the subset of ``ReferenceRepository``
(implemented in ``db/reference_repository.py``) that
``features/etag/service.py`` and ``features/reference/router.py`` depend on
to read the enum/reference datasets (thithi, nakshatra, masa, events,
locations).

Lives in ``core/ports/`` (alongside ``unit_of_work.py``,
``settings_service.py``, and ``panchangam_service.py``) rather than in
``features/reference/ports.py`` for the same reason as
``SettingsServicePort``: ``ReferenceRepository`` is a genuine cross-feature
dependency — it backs the reference endpoints in ``features/reference/router.py``
*and* is consumed directly by ``features/etag/service.py`` to build enum
payloads when refreshing ETags — so the seam other modules depend on is a
``core/ports/`` Protocol, never a direct import of the concrete
``db/reference_repository.py::ReferenceRepository`` class.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol

from app.schemas.compact_panchangam_data import CompactSanthigiriEvent


@dataclass(frozen=True, kw_only=True)
class ReferenceTranslation:
    """One reference-item's display text in one language — the v2 payload shape."""

    language_code: str
    text: str


@dataclass(frozen=True, kw_only=True)
class ReferenceItemGet:
    """v2 shape for nakshatra/masa/chandra_masa/paksha — structurally identical."""

    id: int
    name: str
    translations: List[ReferenceTranslation]


@dataclass(frozen=True, kw_only=True)
class ThithiItemGet:
    """v2 shape for thithi — needs ``day`` and a nested paksha, unlike the other four."""

    id: int
    name: str
    day: int
    paksha: Optional[ReferenceItemGet]
    translations: List[ReferenceTranslation]


class ReferenceRepositoryPort(Protocol):
    def list_thithis(self) -> List[Dict[str, Any]]: ...

    def list_nakshatras(self) -> List[Dict[str, Any]]: ...

    def list_masas(self) -> List[Dict[str, Any]]: ...

    def list_chandra_masas(self) -> List[Dict[str, Any]]: ...

    def list_locations(self) -> List[Dict[str, Any]]: ...

    def list_events(self) -> List[CompactSanthigiriEvent]: ...

    # ── v2: row-per-(parent, language_code) translation reads ──────────────────
    # Additive to the six methods above (which back the unchanged v1 endpoints).
    # See features/reference/router_v2.py.

    def list_thithis_v2(self) -> List[ThithiItemGet]: ...

    def list_nakshatras_v2(self) -> List[ReferenceItemGet]: ...

    def list_masas_v2(self) -> List[ReferenceItemGet]: ...

    def list_chandra_masas_v2(self) -> List[ReferenceItemGet]: ...

    def list_pakshas_v2(self) -> List[ReferenceItemGet]: ...
