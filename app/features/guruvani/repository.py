"""
GuruvaniRepository — concrete adapter for ``GuruvaniRepositoryPort``, CRUD for
the ``guruvani`` table against SQLModel.

Following the convention of ``PanchangamRepository``/
``features.santhigiri_events.repository.SanthigiriEventRepository``, mutating
methods do NOT commit — the caller (``features.guruvani.service``) owns the
transaction.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from app.db.models.guruvani import Guruvani as GuruvaniRow
from app.db.typing_utils import col
from app.features.guruvani.ports import GuruvaniCreate, GuruvaniGet, GuruvaniUpdate


@dataclass()
class GuruvaniRepository:
    _s: Session

    def _row_to_guruvani_get(self, row: GuruvaniRow) -> GuruvaniGet:
        assert row.id is not None
        return GuruvaniGet(
            id=row.id,
            text_en=row.text_en,
            text_ml=row.text_ml,
            sort_order=row.sort_order,
        )

    # ── Getters ────────────────────────────────────────────────────────────────

    def get(self, guruvani_id: int) -> Optional[GuruvaniGet]:
        row = self._s.get(GuruvaniRow, guruvani_id)
        if row is None:
            return None
        return self._row_to_guruvani_get(row)

    def list_all(self) -> List[GuruvaniGet]:
        rows = self._s.exec(
            select(GuruvaniRow).order_by(col(GuruvaniRow.sort_order))
        ).all()
        return [self._row_to_guruvani_get(row) for row in rows]

    def get_random(self) -> Optional[GuruvaniGet]:
        """One row picked at random, or None if the table is empty.

        ``func.random()`` is the SQL standard name for this and works
        identically on both Postgres and SQLite (the test suite's engine).
        """
        row = self._s.exec(
            select(GuruvaniRow).order_by(func.random()).limit(1)
        ).first()
        if row is None:
            return None
        return self._row_to_guruvani_get(row)

    # ── Setters ────────────────────────────────────────────────────────────────

    def create(self, guruvani: GuruvaniCreate) -> GuruvaniGet:
        """Insert a new Guruvani entry. Assigns ``sort_order`` if not set. Does NOT commit."""
        sort_order = (
            guruvani.sort_order
            if guruvani.sort_order is not None
            else self._next_sort_order()
        )
        row = GuruvaniRow(
            text_en=guruvani.text_en,
            text_ml=guruvani.text_ml,
            sort_order=sort_order,
        )
        self._s.add(row)
        self._s.flush()
        return self._row_to_guruvani_get(row)

    def update(self, guruvani_id: int, changes: GuruvaniUpdate) -> GuruvaniGet:
        """Apply the set fields of *changes* to an existing row. Does NOT commit."""
        row = self._s.get(GuruvaniRow, guruvani_id)
        assert row is not None
        if changes.text_en is not None:
            row.text_en = changes.text_en
        if changes.text_ml is not None:
            row.text_ml = changes.text_ml
        if changes.sort_order is not None:
            row.sort_order = changes.sort_order
        self._s.add(row)
        self._s.flush()
        return self._row_to_guruvani_get(row)

    def delete(self, guruvani_id: int) -> None:
        row = self._s.get(GuruvaniRow, guruvani_id)
        assert row is not None
        self._s.delete(row)
        self._s.flush()

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _next_sort_order(self) -> int:
        current_max = self._s.exec(select(func.max(GuruvaniRow.sort_order))).first()
        return (current_max or 0) + 1
