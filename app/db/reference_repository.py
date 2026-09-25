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

from app.core.ports.reference_repository import (
    ReferenceItemGet,
    ReferenceTranslation,
    ThithiItemGet,
)
from app.db.models.chandra_masa import ChandraMasa as ChandraMasaRow
from app.db.models.location import Location as LocationRow
from app.db.models.malayalam_masa import MalayalamMasa as MalayalamMasaRow
from app.db.models.nakshatra import Nakshatra as NakshatraRow
from app.db.models.paksha import Paksha as PakshaRow
from app.db.models.santhigiri_event import SanthigiriEvent as SanthigiriEventRow
from app.db.models.thithi import Thithi as ThithiRow
from app.db.typing_utils import col
from app.schemas.compact_panchangam_data import CompactSanthigiriEvent


class ReferenceRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def list_thithis(self) -> List[Dict[str, Any]]:
        rows = self._s.exec(
            select(ThithiRow)
            .options(selectinload(col(ThithiRow.paksha)))
            .order_by(col(ThithiRow.id))
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
        rows = self._s.exec(select(NakshatraRow).order_by(col(NakshatraRow.id))).all()
        return [
            {"name": n.name, "id": n.id, "ml": n.ml, "en": n.en} for n in rows
        ]

    def list_masas(self) -> List[Dict[str, Any]]:
        rows = self._s.exec(select(MalayalamMasaRow).order_by(col(MalayalamMasaRow.id))).all()
        return [
            {"name": m.name, "id": m.id, "ml": m.ml, "en": m.en} for m in rows
        ]

    def list_chandra_masas(self) -> List[Dict[str, Any]]:
        rows = self._s.exec(select(ChandraMasaRow).order_by(col(ChandraMasaRow.id))).all()
        return [
            {"name": m.name, "id": m.id, "ml": m.ml, "en": m.en} for m in rows
        ]

    def list_locations(self) -> List[Dict[str, Any]]:
        """Every location the API can serve panchangam data for.

        ``name`` is the stable short code clients pass as ``?location=``.
        Location-independent, so its ETag carries no location component.
        """
        rows = self._s.exec(select(LocationRow).order_by(col(LocationRow.id))).all()
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
            select(SanthigiriEventRow).order_by(col(SanthigiriEventRow.sort_order))
        ).all()
        return [
            CompactSanthigiriEvent(id=e.id, name=e.name, description=e.description) for e in rows
        ]

    # ── v2: row-per-(parent, language_code) translation reads ──────────────────
    # Additive to the six methods above (which back the unchanged v1 endpoints
    # and must keep reading `.ml`/`.en` directly). These read the new
    # `*_translation` tables instead.

    @staticmethod
    def _translations(rows: List[object]) -> List[ReferenceTranslation]:
        return [
            ReferenceTranslation(language_code=r.language_code, text=r.text)  # type: ignore[attr-defined]
            for r in sorted(rows, key=lambda r: r.language_code)  # type: ignore[attr-defined]
        ]

    @classmethod
    def _paksha_to_item(cls, p: PakshaRow) -> ReferenceItemGet:
        return ReferenceItemGet(id=p.id, name=p.name, translations=cls._translations(p.translations))

    def list_thithis_v2(self) -> List[ThithiItemGet]:
        rows = self._s.exec(
            select(ThithiRow)
            .options(
                selectinload(col(ThithiRow.translations)),
                selectinload(col(ThithiRow.paksha)).selectinload(col(PakshaRow.translations)),
            )
            .order_by(col(ThithiRow.id))
        ).all()
        return [
            ThithiItemGet(
                id=t.id,
                name=t.name,
                day=t.day,
                paksha=self._paksha_to_item(t.paksha) if t.paksha else None,
                translations=self._translations(t.translations),
            )
            for t in rows
        ]

    def list_nakshatras_v2(self) -> List[ReferenceItemGet]:
        rows = self._s.exec(
            select(NakshatraRow)
            .options(selectinload(col(NakshatraRow.translations)))
            .order_by(col(NakshatraRow.id))
        ).all()
        return [
            ReferenceItemGet(id=n.id, name=n.name, translations=self._translations(n.translations))
            for n in rows
        ]

    def list_masas_v2(self) -> List[ReferenceItemGet]:
        rows = self._s.exec(
            select(MalayalamMasaRow)
            .options(selectinload(col(MalayalamMasaRow.translations)))
            .order_by(col(MalayalamMasaRow.id))
        ).all()
        return [
            ReferenceItemGet(id=m.id, name=m.name, translations=self._translations(m.translations))
            for m in rows
        ]

    def list_chandra_masas_v2(self) -> List[ReferenceItemGet]:
        rows = self._s.exec(
            select(ChandraMasaRow)
            .options(selectinload(col(ChandraMasaRow.translations)))
            .order_by(col(ChandraMasaRow.id))
        ).all()
        return [
            ReferenceItemGet(id=m.id, name=m.name, translations=self._translations(m.translations))
            for m in rows
        ]

    def list_pakshas_v2(self) -> List[ReferenceItemGet]:
        rows = self._s.exec(
            select(PakshaRow)
            .options(selectinload(col(PakshaRow.translations)))
            .order_by(col(PakshaRow.id))
        ).all()
        return [self._paksha_to_item(p) for p in rows]
