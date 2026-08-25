
from dataclasses import dataclass

from typing import List, Protocol

@dataclass()
class SanthigiriEventGet:
    pass

@dataclass 
class SanthigiriEventCreate:
    pass

@dataclass
class SanthigiriEventUdpate:
    pass


class SanthigiriEventsRepositoryPort(Protocol):
    def create_event(self, event: SanthigiriEventCreate)-> SanthigiriEventGet: ...
    def update_event(self, event: SanthigiriEventUdpate) -> SanthigiriEventGet: ...
    def delete_event(self, event: SanthigiriEventGet) -> SanthigiriEventGet: ...
    def get_event_by_id(self, event_id: str) -> SanthigiriEventGet: ...
    def get_all_events(self)-> List[SanthigiriEventGet]: ...
