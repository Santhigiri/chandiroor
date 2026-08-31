"""GuruvaniService — orchestrates create/read/update/delete of Guruvani quotes.

Built the same way as any other migrated feature's service: a frozen
dataclass depending on ``GuruvaniRepositoryPort`` (from
``features/guruvani/ports.py``) and a ``UnitOfWork``, never on the concrete
adapter class. Request-schema -> DTO conversion (and the reverse) happens
here, not in the router.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.core.ports.unit_of_work import UnitOfWork
from app.features.guruvani.ports import (
    GuruvaniCreate as GuruvaniCreateDto,
)
from app.features.guruvani.ports import (
    GuruvaniGet,
    GuruvaniNotFoundException,
    GuruvaniRepositoryPort,
)
from app.features.guruvani.ports import (
    GuruvaniUpdate as GuruvaniUpdateDto,
)
from app.features.guruvani.schemas import GuruvaniCreate, GuruvaniDetail, GuruvaniUpdate

GuruvaniNotFound = GuruvaniNotFoundException


@dataclass(frozen=True)
class GuruvaniService:
    guruvani_repository: GuruvaniRepositoryPort
    uow: UnitOfWork

    def _guruvani_get_to_detail(self, row: GuruvaniGet) -> GuruvaniDetail:
        return GuruvaniDetail(
            id=row.id,
            text_en=row.text_en,
            text_ml=row.text_ml,
            sort_order=row.sort_order,
        )

    def list_all(self) -> List[GuruvaniDetail]:
        rows = self.guruvani_repository.list_all()
        return [self._guruvani_get_to_detail(row) for row in rows]

    def get(self, guruvani_id: int) -> GuruvaniDetail:
        row = self.guruvani_repository.get(guruvani_id)
        if row is None:
            raise GuruvaniNotFoundException(guruvani_id)
        return self._guruvani_get_to_detail(row)

    def get_random(self) -> GuruvaniDetail:
        row = self.guruvani_repository.get_random()
        if row is None:
            raise GuruvaniNotFoundException("no Guruvani entries exist")
        return self._guruvani_get_to_detail(row)

    def create(self, payload: GuruvaniCreate) -> GuruvaniDetail:
        dto = GuruvaniCreateDto(
            text_en=payload.text_en,
            text_ml=payload.text_ml,
            sort_order=payload.sort_order,
        )
        with self.uow as uow:
            row = self.guruvani_repository.create(dto)
            uow.commit()
            return self._guruvani_get_to_detail(row)

    def update(self, guruvani_id: int, payload: GuruvaniUpdate) -> GuruvaniDetail:
        if self.guruvani_repository.get(guruvani_id) is None:
            raise GuruvaniNotFoundException(guruvani_id)
        changes = GuruvaniUpdateDto(
            text_en=payload.text_en,
            text_ml=payload.text_ml,
            sort_order=payload.sort_order,
        )
        with self.uow as uow:
            row = self.guruvani_repository.update(guruvani_id, changes)
            uow.commit()
            return self._guruvani_get_to_detail(row)

    def delete(self, guruvani_id: int) -> None:
        if self.guruvani_repository.get(guruvani_id) is None:
            raise GuruvaniNotFoundException(guruvani_id)
        with self.uow as uow:
            self.guruvani_repository.delete(guruvani_id)
            uow.commit()
