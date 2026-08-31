
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from sqlmodel import Session, col, delete, func, select

from app.features.santhigiri_events.ports import EventNotFoundException, SanthigiriEventCreate, SanthigiriEventUdpate, SanthigiriEventGet, SanthigiriEventsRepositoryPort
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.models.santhigiri_event_date import SanthigiriEventDate as SanthigiriEventDateRow
from app.db.typing_utils import col as TypedColumn



@dataclass
class SanthigiriEventRepository(SanthigiriEventsRepositoryPort):
    session: Session


    def event_exists(self, event_id: str) -> bool:
        return self._get(event_id) is not None

    def get_event_by_id(self, event_id: str) -> SanthigiriEventGet:
        row = self._get(event_id)
        if row is None:
            raise EventNotFoundException()
        return row.to_dto()

    def get_all_events(self) -> List[SanthigiriEventGet]:
        return [event.to_dto() for event in self._list_all()]

    def create_event(self, event: SanthigiriEventCreate) -> SanthigiriEventGet:
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

    # Columns from_dto populates on a row — used to copy values field-by-field
    # onto an already-persistent row on update, rather than replacing it with a
    # new transient object (which would collide with the session's identity map
    # and attempt an INSERT instead of an UPDATE).
    _MUTABLE_FIELDS = (
        "name", "description", "sort_order", "nakshatra_id", "thithi_id",
        "ml_day", "ml_month", "ml_year", "en_day", "en_month", "en_year",
        "occurance", "is_poornima", "last_occurance", "day_offset",
        "yields_to_event_id",
    )

    def update_event(self, event: SanthigiriEventUdpate, event_id: str) -> SanthigiriEventGet:
        """Apply *event*'s fields onto the existing row in place. Does NOT commit."""
        row = self._get(event_id)
        if row is None:
            raise EventNotFoundException()
        fresh = SanthigiriEventRow.from_dto(event_id=event_id, event=event)
        for field in self._MUTABLE_FIELDS:
            setattr(row, field, getattr(fresh, field))
        self.session.add(row)
        self.session.flush()
        return row.to_dto()

    def delete_event(self, event: SanthigiriEventGet) -> SanthigiriEventGet:
        """Delete an event definition. Does NOT commit.

        Its rows in ``santhigiri_event_dates`` are removed by the
        ``ON DELETE CASCADE`` foreign key, which changes the ``/year`` payloads
        for the years the event used to fall on — see
        :meth:`occurrence_years_before_delete`, which the caller must call
        *before* this to know which years' ETags to refresh.
        """
        row = self._get(event.id)
        if row is None:
            raise EventNotFoundException()
        dto = row.to_dto()
        self.session.delete(row)
        self.session.flush()
        return dto

    def occurrence_years_before_delete(self, event_id: str) -> List[int]:
        """Years *event_id* currently has occurrences in — call before
        :meth:`delete_event` so the caller knows which years' ETags the
        cascade delete will affect."""
        return self._occurrence_years(event_id)

    def set_event_occurrences_for_year(
        self, event_id: str, year: int, dates: List[date]
    ) -> List[date]:
        """Replace *event_id*'s occurrences within *year* with *dates*.

        Unlike :meth:`_replace_santhigiri_events` (which replaces every
        event's occurrences for one date), this replaces one event's
        occurrences across an entire year — the shape needed to regenerate a
        single event's dates without disturbing any other event's dates that
        happen to fall on the same days. Does NOT commit.
        """
        start = date(year, 1, 1)
        end = date(year, 12, 31)
        self.session.exec(
            delete(SanthigiriEventDateRow).where(
                col(SanthigiriEventDateRow.event_id) == event_id,
                col(SanthigiriEventDateRow.panchangam_date) >= start,
                col(SanthigiriEventDateRow.panchangam_date) <= end,
            )
        )
        for d in dates:
            self.session.add(SanthigiriEventDateRow(panchangam_date=d, event_id=event_id))
        return dates


    # ── Private helpers ─────────────────────────────────────────────────────────
    def _get(self, event_id: str) -> Optional[SanthigiriEventRow]:
        """Return the event definition for *event_id*, or None if absent."""
        return self.session.get(SanthigiriEventRow, event_id)

    def _list_all(self) -> List[SanthigiriEventRow]:
        """Every event definition, ordered by ``sort_order`` (stable order for
        bulk occurrence generation)."""
        return list(
            self.session.exec(
                select(SanthigiriEventRow).order_by(TypedColumn(SanthigiriEventRow.sort_order))
            ).all()
        )

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
