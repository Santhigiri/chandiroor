"""GuruvaniService — orchestrates create/read/update/delete of Guruvani quotes."""
from __future__ import annotations

from typing import List

from sqlmodel import Session

from db.guruvani_repository import GuruvaniRepository
from db.models.guruvani import Guruvani
from schemas.guruvani import GuruvaniCreate, GuruvaniUpdate


class GuruvaniNotFound(Exception):
    """Raised when reading/updating/deleting a Guruvani id that does not exist."""


class GuruvaniService:
    def __init__(self, session: Session) -> None:
        self._s = session
        self._repo = GuruvaniRepository(session)

    def list_all(self) -> List[Guruvani]:
        return self._repo.list_all()

    def get(self, guruvani_id: int) -> Guruvani:
        row = self._repo.get(guruvani_id)
        if row is None:
            raise GuruvaniNotFound(guruvani_id)
        return row

    def get_random(self) -> Guruvani:
        row = self._repo.get_random()
        if row is None:
            raise GuruvaniNotFound("no Guruvani entries exist")
        return row

    def create(self, payload: GuruvaniCreate) -> Guruvani:
        row = Guruvani(**payload.model_dump())
        self._repo.create(row)
        self._s.commit()
        self._s.refresh(row)
        return row

    def update(self, guruvani_id: int, payload: GuruvaniUpdate) -> Guruvani:
        row = self.get(guruvani_id)
        changes = payload.model_dump(exclude_unset=True)
        self._repo.update(row, changes)
        self._s.commit()
        self._s.refresh(row)
        return row

    def delete(self, guruvani_id: int) -> None:
        row = self.get(guruvani_id)
        self._repo.delete(row)
        self._s.commit()
