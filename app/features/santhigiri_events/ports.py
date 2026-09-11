
from abc import abstractmethod
from dataclasses import dataclass

from datetime import date
from typing import List, Optional, Protocol

from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.santhigiri_events import EventCondition
from app.core.astronomy.enums.thithi import Thithi


class EventNotFoundException(Exception):
    pass


@dataclass(frozen=True, kw_only=True)
class SanthigiriEventBase:
    name:        str
    description: str
    sort_order:  int 
    event_condition: EventCondition
    yields_to_event_id: Optional[str] = None

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
    def event_exists(self, event_id: str) -> bool: ...

    @abstractmethod
    def create_event(self, event: SanthigiriEventCreate)-> SanthigiriEventGet: ...

    @abstractmethod
    def update_event(self, event: SanthigiriEventUdpate, event_id: str) -> SanthigiriEventGet: ...

    @abstractmethod
    def delete_event(self, event: SanthigiriEventGet) -> SanthigiriEventGet: ...

    @abstractmethod
    def occurrence_years_before_delete(self, event_id: str) -> List[int]: ...

    @abstractmethod
    def get_event_by_id(self, event_id: str) -> SanthigiriEventGet: ...

    @abstractmethod
    def get_all_events(self)-> List[SanthigiriEventGet]: ...

    @abstractmethod
    def set_event_occurrences_for_year(self, event_id: str, year: int, dates:  List[date])-> List[date]: ...
