import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey, Index
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.panchangam import Panchangam
    from db.models.santhigiri_event_condition import SanthigiriEventCondition


class SanthigiriSignificantDate(SQLModel, table=True):
    """A significant Santhigiri ashram event that falls on a panchangam date."""

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
    event_id:            str           # SanthigiriEventId str-enum value
    name:                str
    description:         str
    event_condition_id:  Optional[int] = Field(
        default=None, foreign_key="santhigiri_event_condition.id"
    )

    panchangam:      Optional["Panchangam"]               = Relationship(back_populates="santhigiri_events")
    event_condition: Mapped[Optional["SanthigiriEventCondition"]] = Relationship(back_populates="significant_dates")
