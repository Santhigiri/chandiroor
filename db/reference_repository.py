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

from db.models.location import Location as LocationRow
from db.models.malayalam_masa import MalayalamMasa as MalayalamMasaRow
from db.models.nakshatra import Nakshatra as NakshatraRow
from db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from db.models.thithi import Thithi as ThithiRow
from schemas.compact_panchangam_data import CompactSanthigiriEvent


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
                    "label": {"en": t.paksha.en, "ml": t.paksha.ml},
                }
                if t.paksha
                else None,
                "label": {"en": t.en, "ml": t.ml},
            }
            for t in rows
        ]

    def list_nakshatras(self) -> List[Dict[str, Any]]:
        rows = self._s.exec(select(NakshatraRow).order_by(NakshatraRow.id)).all()
        return [
            {"name": n.name, "id": n.id, "label": {"en": n.en, "ml": n.ml}}
            for n in rows
        ]

    def list_masas(self) -> List[Dict[str, Any]]:
        rows = self._s.exec(select(MalayalamMasaRow).order_by(MalayalamMasaRow.id)).all()
        return [
            {"name": m.name, "id": m.id, "label": {"en": m.en, "ml": m.ml}}
            for m in rows
        ]

    def list_locations(self) -> List[Dict[str, Any]]:
        """Every location the API can serve panchangam data for.

        ``name`` is the stable short code clients pass as ``?location=``.
        Location-independent, so its ETag carries no location component.
        """
        rows = self._s.exec(select(LocationRow).order_by(LocationRow.id)).all()
        return [
            {
                "code": l.name,
                "label": l.label,
                "latitude": l.latitude,
                "longitude": l.longitude,
                "timezone": l.timezone,
            }
            for l in rows
        ]

    def list_events(self) -> List[CompactSanthigiriEvent]:
        """Every defined event, from the editable santhigiri_event table.

        Includes events that do not occur in the loaded date range, ordered by
        ``sort_order`` so the output (and therefore its ETag) is stable and
        identical across instances.
        """
        rows = self._s.exec(
            select(SanthigiriEventRow).order_by(SanthigiriEventRow.sort_order)
        ).all()
        return [
            CompactSanthigiriEvent(id=e.id, name=e.name, description=e.description) for e in rows
        ]
