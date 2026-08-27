
from dataclasses import dataclass
from typing import List, Optional

from sqlmodel import Session, col, func, select

from app.features.santhigiri_events.ports import EventNotFoundException, SanthigiriEventCreate, SanthigiriEventUdpate, SanthigiriEventGet, SanthigiriEventsRepositoryPort
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.models.santhigiri_event_date import SanthigiriEventDate as SanthigiriEventDateRow
from app.db.typing_utils import col as TypedColumn



@dataclass
class SanthigiriEventRepository(SanthigiriEventsRepositoryPort):
    session: Session

    def _get(self, event_id: str) -> Optional[SanthigiriEventRow]:
        """Return the event definition for *event_id*, or None if absent."""
        return self.session.get(SanthigiriEventRow, event_id)

    def exists(self, event_id: str) -> bool:
        return self._get(event_id) is not None

    def _list_all(self) -> List[SanthigiriEventRow]:
        """Every event definition, ordered by ``sort_order`` (stable order for
        bulk occurrence generation)."""
        return list(
            self.session.exec(
                select(SanthigiriEventRow).order_by(TypedColumn(SanthigiriEventRow.sort_order))
            ).all()
        )

    def get_all_events(self) -> List[SanthigiriEventGet]:
        return [event.to_dto() for event in self._list_all()]

    def create(self, event: SanthigiriEventCreate) -> SanthigiriEventGet:
        """Insert a new event definition. Assigns ``sort_order`` if not set.

        Flushes so a duplicate id / bad foreign key surfaces here rather than at
        the caller's commit. Does NOT commit.
        """
        row = SanthigiriEventRow.from_dto(event_id=event.id, event=event)
        if row.sort_order is None:
            row.sort_order = self._nextsessionort_order()

        self.session.add(row)
        self.session.flush()
        return row.to_dto()

    def update(self, event: SanthigiriEventUdpate, event_id: str) -> SanthigiriEventGet:
        """Apply *changes* (column name → value) to an existing row. Does NOT commit."""
        row = self._get(event_id)
        if row is None:
            raise EventNotFoundException()
        updated_row = SanthigiriEventRow.from_dto(event_id=event_id, event=event)
        self.session.add(updated_row)
        self.session.flush()
        return updated_row.to_dto()

    def delete(self, event: SanthigiriEventGet) -> List[int]:
        """Delete an event definition and return the years it used to fall on.

        Its rows in ``santhigiri_event_dates`` are removed by the
        ``ON DELETE CASCADE`` foreign key, which changes the ``/year`` payloads
        for those years — the caller must refresh their ETags. Does NOT commit.
        """
        years = self._occurrence_years(event.id)
        row = SanthigiriEventRow.from_dto(event_id=event.id, event=event)
        self.session.delete(row)
        self.session.flush()
        return years

    # ── Private helpers ─────────────────────────────────────────────────────────

    def _nextsessionort_order(self) -> int:
        current_max = self.session.exec(
            select(func.max(SanthigiriEventRow.sort_order))
        ).first()
        return (current_max or 0) + 1

    def _occurrence_years(self, event_id: str) -> List[int]:
        dates = self.session.exec(
            select(TypedColumn(SanthigiriEventDateRow.panchangam_date)).where(
                col(SanthigiriEventDateRow.event_id) == event_id
            )
        ).all()
        return sorted({d.year for d in dates})
