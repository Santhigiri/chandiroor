"""
ReferenceRepository — serve the enum/reference datasets from the database.

These lists (thithi, nakshatra, masa, events) back the ``/panchangam/*``
reference endpoints. Reading them from the DB rather than the Python enums means
corrections made in the database — especially to Santhigiri event names and
descriptions, which are editable — are reflected by the API without a code
change. The returned dicts intentionally match the shapes the endpoints have
always produced.
"""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from db.models.malayalam_masa import MalayalamMasa as MalayalamMasaRow
from db.models.nakshatra import Nakshatra as NakshatraRow
from db.models.santhigiri_significant_date import (
    SanthigiriSignificantDate as SanthigiriSignificantDateRow,
)
from db.models.thithi import Thithi as ThithiRow


class ReferenceRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_thithis(self) -> List[Dict[str, Any]]:
        rows = self._s.exec(
            select(ThithiRow)
            .options(selectinload(ThithiRow.paksha))
            .order_by(ThithiRow.id)
        ).all()
        return [
            {
                "name": t.name,
                "id": t.id,
                "paksha": {
                    "name": t.paksha.name,
                    "id": t.paksha.id,
                    "ml": t.paksha.ml,
                    "en": t.paksha.en,
                }
                if t.paksha
                else None,
                "ml": t.ml,
                "en": t.en,
            }
            for t in rows
        ]

    def list_nakshatras(self) -> List[Dict[str, Any]]:
        rows = self._s.exec(select(NakshatraRow).order_by(NakshatraRow.id)).all()
        return [
            {"name": n.name, "id": n.id, "ml": n.ml, "en": n.en} for n in rows
        ]

    def list_masas(self) -> List[Dict[str, Any]]:
        rows = self._s.exec(select(MalayalamMasaRow).order_by(MalayalamMasaRow.id)).all()
        return [
            {"name": m.name, "id": m.id, "ml": m.ml, "en": m.en} for m in rows
        ]

    def list_events(self) -> List[Dict[str, Any]]:
        """Distinct event definitions drawn from the significant-date rows.

        Ordered by ``event_id`` so the output (and therefore its ETag) is stable
        and identical across instances.
        """
        rows = self._s.exec(
            select(
                SanthigiriSignificantDateRow.event_id,
                SanthigiriSignificantDateRow.name,
                SanthigiriSignificantDateRow.description,
            )
            .distinct()
            .order_by(
                SanthigiriSignificantDateRow.event_id,
                SanthigiriSignificantDateRow.name,
            )
        ).all()
        return [
            {"id": event_id, "name": name, "description": description}
            for event_id, name, description in rows
        ]
