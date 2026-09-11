from typing import Optional

from pydantic import BaseModel

from app.utils.santhigiri_events import EventConditionFieldKind


class EventConditionFieldInfo(BaseModel):
    """One filterable ``EventCondition`` field, as served by
    ``GET /panchangam/event-condition-fields`` for a client building an
    "add condition" UI without hardcoding the field list."""

    key: str
    label: str
    kind: EventConditionFieldKind
    reference_dataset: Optional[str] = None
