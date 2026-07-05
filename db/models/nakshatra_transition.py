import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKeyConstraint, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.nakshatra import Nakshatra
    from db.models.panchangam import Panchangam


class NakshatraTransition(SQLModel, table=True):
    """A nakshatra (lunar mansion) active during part of a calendar day at a location."""

    __tablename__ = "nakshatra_transitions" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        ForeignKeyConstraint(
            ["panchangam_date", "location_id"],
            ["panchangam.date", "panchangam.location_id"],
            ondelete="CASCADE",
        ),
        Index("idx_nakshatra_transitions_date", "panchangam_date", "location_id", "start_time"),
    )

    id:             Optional[int]  = Field(default=None, primary_key=True)
    panchangam_date: datetime.date = Field(nullable=False)
    location_id:     int           = Field(nullable=False)
    nakshatra_id: int                         = Field(foreign_key="nakshatra.id")
    start_time:   datetime.datetime
    end_time:     Optional[datetime.datetime] = None

    panchangam: Optional["Panchangam"] = Relationship(back_populates="nakshatra_transitions")
    nakshatra:  Optional["Nakshatra"]  = Relationship(back_populates="transitions")
