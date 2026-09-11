"""
EtagRepositoryPort — the persistence contract ``services/etag_service.py``
depends on for reading/writing a dataset's stored ETag.

No DTO is defined here: the boundary value is a bare ETag string keyed by a
dataset name (e.g. ``"year:tvm:2026"``, ``"enum:thithi"``), so there is no
row shape to translate the way ``AppSettingGet``/``SanthigiriEventGet`` do
for their features.
"""
from __future__ import annotations

from typing import Optional, Protocol


class EtagRepositoryPort(Protocol):
    def get(self, key: str) -> Optional[str]:
        """Return the stored ETag for *key*, or None if none is stored yet."""
        ...

    def set(self, key: str, etag: str) -> None:
        """Insert or replace the ETag for *key*. Does NOT commit."""
        ...
