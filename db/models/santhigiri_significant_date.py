import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.panchangam import Panchangam
    from db.models.santhigiri_event import SanthigiriEvent
    from db.models.santhigiri_event_condition import SanthigiriEventCondition


class SanthigiriSignificantDate(SQLModel, table=True):
    """A significant Santhigiri ashram event that falls on a panchangam date.

    ``event_id`` is a foreign key into ``santhigiri_event``: that definition
    table is the single source of truth for the event's name and description, so
    they are not duplicated here — read them via the ``event`` relationship.
    """

    __tablename__ = "santhigiri_significant_dates" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        Index("idx_santhigiri_events_date", "panchangam_date"),
    )

    id:             Optional[int]  = Field(default=None, primary_key=True)
    panchangam_date: datetime.date = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    event_id:            str           = Field(
        sa_column=Column(
            String,
            ForeignKey("santhigiri_event.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    event_condition_id:  Optional[int] = Field(
        default=None, foreign_key="santhigiri_event_condition.id"
    )

    panchangam:      Optional["Panchangam"]                       = Relationship(back_populates="santhigiri_events")
    event:           Mapped[Optional["SanthigiriEvent"]]          = Relationship()
    event_condition: Mapped[Optional["SanthigiriEventCondition"]] = Relationship(back_populates="significant_dates")
