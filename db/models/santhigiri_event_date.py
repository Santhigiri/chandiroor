import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.panchangam import Panchangam
    from db.models.santhigiri_event import SanthigiriEvent


class SanthigiriEventDate(SQLModel, table=True):
    """A significant Santhigiri ashram event that falls on a panchangam date.

    ``event_id`` is a foreign key into ``santhigiri_event``: that definition
    table is the single source of truth for the event's name, description, and
    matching condition, so they are not duplicated here — read them via the
    ``event`` relationship.
    """

    __tablename__ = "santhigiri_event_dates" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        Index("idx_santhigiri_event_dates_date", "panchangam_date"),
    )

    id:             Optional[int]  = Field(default=None, primary_key=True)
    panchangam_date: datetime.date = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    event_id: str = Field(
        sa_column=Column(
            String,
            ForeignKey("santhigiri_event.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    panchangam: Optional["Panchangam"]              = Relationship(back_populates="santhigiri_events")
    event:      Mapped[Optional["SanthigiriEvent"]] = Relationship()
