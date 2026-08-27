
from abc import abstractmethod
from dataclasses import dataclass

from typing import List, Optional, Protocol

from app.utils.nakshatra import Nakshatra
from app.utils.thithi import Thithi


class EventNotFoundException(Exception):
    pass

@dataclass(frozen=True, kw_only=True)
class SanthigiriEventBase:
    name:        str
    description: str
    sort_order:  int 
    nakshatra: Optional[Nakshatra]
    thithi: Optional[Thithi]
    ml_day:         Optional[int]  = None
    ml_month:       Optional[int]  = None
    ml_year:        Optional[int]  = None
    en_day:         Optional[int]  = None
    en_month:       Optional[int]  = None
    en_year:        Optional[int]  = None
    occurance:      Optional[int]  = None
    is_poornima:    Optional[bool] = None
    last_occurance: Optional[bool] = None
    day_offset: Optional[int] = None
    yields_to_event: Optional[str] = None

@dataclass(frozen=True, kw_only=True)
class SanthigiriEventGet(SanthigiriEventBase):
    id: str 

@dataclass(frozen=True, kw_only=True)
class SanthigiriEventCreate(SanthigiriEventBase):
    id: str

@dataclass(frozen=True, kw_only=True)
class SanthigiriEventUdpate(SanthigiriEventBase):
    pass

class SanthigiriEventsRepositoryPort(Protocol):
    @abstractmethod
    def create_event(self, event: SanthigiriEventCreate)-> SanthigiriEventGet: ...

    @abstractmethod
    def update_event(self, event: SanthigiriEventUdpate, event_id: str) -> SanthigiriEventGet: ...

    @abstractmethod
    def delete_event(self, event: SanthigiriEventGet) -> SanthigiriEventGet: ...

    @abstractmethod
    def get_event_by_id(self, event_id: str) -> SanthigiriEventGet: ...

    @abstractmethod
    def get_all_events(self)-> List[SanthigiriEventGet]: ...
