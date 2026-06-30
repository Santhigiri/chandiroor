from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.nakshatra import Nakshatra
    from db.models.santhigiri_significant_date import SanthigiriSignificantDate
    from db.models.thithi import Thithi


class SanthigiriEventCondition(SQLModel, table=True):
    """
    The rule that determines when a Santhigiri event falls on a given day.

    Mirrors the EventCondition Pydantic model from utils/santhigiri_events.py.
    event_id identifies which event this condition belongs to but is not the
    primary key — it is indexed so all conditions for a given event type can
    be looked up efficiently.
    """

    __tablename__ = "santhigiri_event_condition" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        Index("idx_santhigiri_event_condition_event_id", "event_id"),
    )

    id:       Optional[int] = Field(default=None, primary_key=True)
    event_id: str           # SanthigiriEventId str-enum value — indexed, not PK

    # Astronomical / calendar match criteria (all optional; NULL means "any")
    nakshatra_id:   Optional[int]  = Field(default=None, foreign_key="nakshatra.id")
    thithi_id:      Optional[int]  = Field(default=None, foreign_key="thithi.id")

    ml_day:         Optional[int]  = None   # day of the Malayalam month
    ml_month:       Optional[int]  = None   # MalayalamMasa id (1–12)
    ml_year:        Optional[int]  = None

    en_day:         Optional[int]  = None   # Gregorian day
    en_month:       Optional[int]  = None   # Gregorian month
    en_year:        Optional[int]  = None

    occurance:      Optional[int]  = None   # nth occurrence within the period
    is_poornima:    Optional[bool] = None
    last_occurance: Optional[bool] = None   # True = last matching occurrence

    # Lookup relationships (unidirectional — no back_populates needed on lookup side)
    nakshatra: Optional["Nakshatra"] = Relationship()
    thithi:    Optional["Thithi"]    = Relationship()

    # Occurrences that were matched by this condition
    significant_dates: List["SanthigiriSignificantDate"] = Relationship(
        back_populates="event_condition"
    )
