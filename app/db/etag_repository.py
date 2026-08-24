"""
EtagRepository — get and set persisted dataset ETags.

Backed by the ``dataset_etag`` table. Reads are a single indexed primary-key
lookup, which is what lets a conditional request short-circuit to ``304`` without
rebuilding the response body. Writes use ``session.merge`` so ``set`` is an
idempotent upsert. Following the convention of ``PanchangamRepository``, ``set``
does NOT commit — the caller owns the transaction.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlmodel import Session

from db.models.dataset_etag import DatasetEtag


class EtagRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def get(self, key: str) -> Optional[str]:
        """Return the stored ETag for *key*, or None if none is stored yet."""
        row = self._s.get(DatasetEtag, key)
        return row.etag if row else None

    def set(self, key: str, etag: str) -> None:
        """Insert or replace the ETag for *key*. Does NOT commit."""
        self._s.merge(
            DatasetEtag(
                key=key,
                etag=etag,
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
        )
