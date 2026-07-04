"""
KollavarshamRepository — CRUD for the ``kollavarsham_date`` table.

The table holds one Malayalam solar-calendar row per panchangam day. Its
primary key ``date`` is a foreign key to ``panchangam.date`` (``ON DELETE
CASCADE``), so a row can only exist where a panchangam row already exists —
:meth:`missing_panchangam_dates` lets the service reject a generate request
up-front instead of failing on an insert.

Following :class:`db.repository.PanchangamRepository` and
:class:`db.santhigiri_event_repository.SanthigiriEventRepository`, the mutating
methods flush but do NOT commit — the caller owns the transaction so a matching
ETag refresh can be batched into the same commit.
"""
from __future__ import annotations

import datetime
from typing import List, Optional

from sqlmodel import Session, col, select

from db.models.kollavarsham_date import KollavarshamDate as KollavarshamDateRow
from db.models.panchangam import Panchangam as PanchangamRow


class KollavarshamRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ── Getters ────────────────────────────────────────────────────────────────

    def get(self, date: datetime.date) -> Optional[KollavarshamDateRow]:
        """Return the Kollavarsham row for *date*, or None if absent."""
        return self._s.get(KollavarshamDateRow, date)

    def missing_panchangam_dates(
        self, dates: List[datetime.date]
    ) -> List[datetime.date]:
        """Return the subset of *dates* that have no ``panchangam`` row.

        Used to validate a generate range before any write, since the FK to
        ``panchangam.date`` would otherwise reject those inserts.
        """
        if not dates:
            return []
        existing = set(
            self._s.exec(
                select(PanchangamRow.date).where(col(PanchangamRow.date).in_(dates))
            ).all()
        )
        return [d for d in dates if d not in existing]

    # ── Setters ────────────────────────────────────────────────────────────────

    def upsert(
        self,
        date: datetime.date,
        kv_day: int,
        kv_month: int,
        kv_year: int,
    ) -> KollavarshamDateRow:
        """Insert or replace the Kollavarsham row for *date*. Does NOT commit."""
        row = self._s.merge(
            KollavarshamDateRow(
                date=date,
                kv_day=kv_day,
                kv_month=kv_month,
                kv_year=kv_year,
            )
        )
        self._s.flush()
        return row

    def update(
        self, row: KollavarshamDateRow, changes: dict
    ) -> KollavarshamDateRow:
        """Apply *changes* (column name → value) to an existing row. Does NOT commit."""
        for field, value in changes.items():
            setattr(row, field, value)
        self._s.add(row)
        self._s.flush()
        return row
