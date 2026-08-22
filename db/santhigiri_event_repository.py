"""
SanthigiriEventRepository — CRUD for the editable ``santhigiri_event`` table.

This is the definition table that backs the ``/panchangam/events`` reference
endpoint (read via :class:`db.reference_repository.ReferenceRepository`). This
repository owns the *write* side: creating, updating and deleting event
definitions.

Following the convention of :class:`db.repository.PanchangamRepository`, the
mutating methods do NOT commit — the caller owns the transaction so that a
matching ETag refresh can be batched into the same commit.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func
from sqlmodel import Session, col, select

from db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from db.models.santhigiri_event_date import (
    SanthigiriEventDate as SanthigiriEventDateRow,
)

from db.typing_utils import col as TypedColumn


class SanthigiriEventRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ── Getters ────────────────────────────────────────────────────────────────

    def get(self, event_id: str) -> Optional[SanthigiriEventRow]:
        """Return the event definition for *event_id*, or None if absent."""
        return self._s.get(SanthigiriEventRow, event_id)

    def exists(self, event_id: str) -> bool:
        return self.get(event_id) is not None

    def list_all(self) -> List[SanthigiriEventRow]:
        """Every event definition, ordered by ``sort_order`` (stable order for
        bulk occurrence generation)."""
        return list(
            self._s.exec(
                select(SanthigiriEventRow).order_by(TypedColumn(SanthigiriEventRow.sort_order))
            ).all()
        )

    # ── Setters ────────────────────────────────────────────────────────────────

    def create(self, row: SanthigiriEventRow) -> SanthigiriEventRow:
        """Insert a new event definition. Assigns ``sort_order`` if not set.

        Flushes so a duplicate id / bad foreign key surfaces here rather than at
        the caller's commit. Does NOT commit.
        """
        if row.sort_order is None:
            row.sort_order = self._next_sort_order()
        self._s.add(row)
        self._s.flush()
        return row

    def update(self, row: SanthigiriEventRow, changes: dict) -> SanthigiriEventRow:
        """Apply *changes* (column name → value) to an existing row. Does NOT commit."""
        for field, value in changes.items():
            setattr(row, field, value)
        self._s.add(row)
        self._s.flush()
        return row

    def delete(self, row: SanthigiriEventRow) -> List[int]:
        """Delete an event definition and return the years it used to fall on.

        Its rows in ``santhigiri_event_dates`` are removed by the
        ``ON DELETE CASCADE`` foreign key, which changes the ``/year`` payloads
        for those years — the caller must refresh their ETags. Does NOT commit.
        """
        years = self._occurrence_years(row.id)
        self._s.delete(row)
        self._s.flush()
        return years

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _next_sort_order(self) -> int:
        current_max = self._s.exec(
            select(func.max(SanthigiriEventRow.sort_order))
        ).first()
        return (current_max or 0) + 1

    def _occurrence_years(self, event_id: str) -> List[int]:
        dates = self._s.exec(
            select(TypedColumn(SanthigiriEventDateRow.panchangam_date)).where(
                col(SanthigiriEventDateRow.event_id) == event_id
            )
        ).all()
        return sorted({d.year for d in dates})
