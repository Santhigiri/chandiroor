
from dataclasses import dataclass
from typing import List

from sqlmodel import Session

from app.features.santhigiri_events.ports import SanthigiriEventCreate, SanthigiriEventUdpate, SanthigiriEventGet


@dataclass(frozen=True)
class SanthigirEventRepository:
    session: Session

    def create_event(self, event: SanthigiriEventCreate)-> SanthigiriEventGet: ...
    def update_event(self, event: SanthigiriEventUdpate) -> SanthigiriEventGet: ...
    def delete_event(self, event: SanthigiriEventGet) -> SanthigiriEventGet: ...
    def get_event_by_id(self, event_id: str) -> SanthigiriEventGet: ...
    def get_all_events(self)-> List[SanthigiriEventGet]: ...
