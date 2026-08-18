"""GuruvaniRepository — CRUD for the ``guruvani`` table.

Following the convention of :class:`db.repository.PanchangamRepository`, the
mutating methods do NOT commit — the caller (``features.guruvani.service``)
owns the transaction.
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from db.models.guruvani import Guruvani


class GuruvaniRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    # ── Getters ────────────────────────────────────────────────────────────────

    def get(self, guruvani_id: int) -> Optional[Guruvani]:
        return self._s.get(Guruvani, guruvani_id)

    def list_all(self) -> List[Guruvani]:
        return list(
            self._s.exec(select(Guruvani).order_by(Guruvani.sort_order)).all()
        )

    def get_random(self) -> Optional[Guruvani]:
        """One row picked at random, or None if the table is empty.

        ``func.random()`` is the SQL standard name for this and works
        identically on both Postgres and SQLite (the test suite's engine).
        """
        return self._s.exec(select(Guruvani).order_by(func.random()).limit(1)).first()

    # ── Setters ────────────────────────────────────────────────────────────────

    def create(self, row: Guruvani) -> Guruvani:
        """Insert a new Guruvani entry. Assigns ``sort_order`` if not set. Does NOT commit."""
        if row.sort_order is None:
            row.sort_order = self._next_sort_order()
        self._s.add(row)
        self._s.flush()
        return row

    def update(self, row: Guruvani, changes: dict) -> Guruvani:
        """Apply *changes* (column name -> value) to an existing row. Does NOT commit."""
        for field, value in changes.items():
            setattr(row, field, value)
        self._s.add(row)
        self._s.flush()
        return row

    def delete(self, row: Guruvani) -> None:
        self._s.delete(row)
        self._s.flush()

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _next_sort_order(self) -> int:
        current_max = self._s.exec(select(func.max(Guruvani.sort_order))).first()
        return (current_max or 0) + 1
