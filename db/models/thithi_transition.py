import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKeyConstraint, Index
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.panchangam import Panchangam
    from db.models.thithi import Thithi


class ThithiTransition(SQLModel, table=True):
    """A thithi (lunar day) phase active during part of a calendar day at a location."""

    __tablename__ = "thithi_transitions" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        ForeignKeyConstraint(
            ["panchangam_date", "location_id"],
            ["panchangam.date", "panchangam.location_id"],
            ondelete="CASCADE",
        ),
        # Composite covers filter-by-(date, location) + order-by-time in one scan
        Index("idx_thithi_transitions_date", "panchangam_date", "location_id", "start_time"),
    )

    id:             Optional[int]  = Field(default=None, primary_key=True)
    panchangam_date: datetime.date = Field(nullable=False)
    location_id:     int           = Field(nullable=False)
    thithi_id:  int                          = Field(foreign_key="thithi.id")
    start_time: datetime.datetime
    end_time:   Optional[datetime.datetime]  = None  # NULL = open-ended last transition

    panchangam: Optional["Panchangam"] = Relationship(back_populates="thithi_transitions")
    thithi:     Optional["Thithi"]     = Relationship(back_populates="transitions")
