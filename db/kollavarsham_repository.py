"""
KollavarshamRepository — create/read/update for the ``kollavarsham_date`` table.

``kollavarsham_date`` holds one row per panchangam day (its ``date`` is a
foreign key into ``panchangam.date``). A panchangam day is invalid without its
Kollavarsham child — ``db.repository`` refuses to convert such a row — so this
repository is create/update only: there is deliberately no delete, since
removing a day's Kollavarsham data would break that day.

Following the convention of :class:`db.repository.PanchangamRepository`, the
mutating methods do NOT commit — the caller owns the transaction so a matching
ETag refresh can be batched into the same commit.
"""
from __future__ import annotations

import datetime
from typing import Optional

from sqlmodel import Session

from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from db.models.panchangam import Panchangam as PanchangamRow


class KollavarshamRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ── Getters ────────────────────────────────────────────────────────────────

    def get(self, dt: datetime.date) -> Optional[KollavarshamDateRow]:
        """Return the Kollavarsham row for *dt*, or None if absent."""
        return self._s.get(KollavarshamDateRow, dt)

    def exists(self, dt: datetime.date) -> bool:
        return self.get(dt) is not None

    def panchangam_exists(self, dt: datetime.date) -> bool:
        """Whether a parent panchangam day exists for *dt* (required to create kv)."""
        return self._s.get(PanchangamRow, dt) is not None

    # ── Setters ────────────────────────────────────────────────────────────────

    def create(self, row: KollavarshamDateRow) -> KollavarshamDateRow:
        """Insert a new Kollavarsham row.

        Flushes so a duplicate date / missing panchangam parent / bad month id
        surfaces here rather than at the caller's commit. Does NOT commit.
        """
        self._s.add(row)
        self._s.flush()
        return row

    def update(self, row: KollavarshamDateRow, changes: dict) -> KollavarshamDateRow:
        """Apply *changes* (column name → value) to an existing row. Does NOT commit."""
        for field, value in changes.items():
            setattr(row, field, value)
        self._s.add(row)
        self._s.flush()
        return row
