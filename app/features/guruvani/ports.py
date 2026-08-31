from abc import abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Protocol


class GuruvaniNotFoundException(Exception):
    """Raised when reading/updating/deleting a Guruvani id that does not exist."""


@dataclass(frozen=True, kw_only=True)
class GuruvaniBase:
    text_en: str
    text_ml: str
    sort_order: Optional[int] = None


@dataclass(frozen=True, kw_only=True)
class GuruvaniGet(GuruvaniBase):
    id: int


@dataclass(frozen=True, kw_only=True)
class GuruvaniCreate(GuruvaniBase):
    pass


@dataclass(frozen=True, kw_only=True)
class GuruvaniUpdate:
    text_en: Optional[str] = None
    text_ml: Optional[str] = None
    sort_order: Optional[int] = None


class GuruvaniRepositoryPort(Protocol):

    @abstractmethod
    def get(self, guruvani_id: int) -> Optional[GuruvaniGet]: ...

    @abstractmethod
    def list_all(self) -> List[GuruvaniGet]: ...

    @abstractmethod
    def get_random(self) -> Optional[GuruvaniGet]: ...

    @abstractmethod
    def create(self, guruvani: GuruvaniCreate) -> GuruvaniGet: ...

    @abstractmethod
    def update(self, guruvani_id: int, changes: GuruvaniUpdate) -> GuruvaniGet: ...

    @abstractmethod
    def delete(self, guruvani_id: int) -> None: ...
