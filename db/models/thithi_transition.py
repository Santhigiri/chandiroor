import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey, Index
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.panchangam import Panchangam
    from db.models.thithi import Thithi


class ThithiTransition(SQLModel, table=True):
    """A thithi (lunar day) phase active during part of a calendar day."""

    __tablename__ = "thithi_transitions"
    __table_args__ = (
        # Composite covers filter-by-date + order-by-time in one scan
        Index("idx_thithi_transitions_date", "panchangam_date", "start_time"),
    )

    id:             Optional[int]  = Field(default=None, primary_key=True)
    panchangam_date: datetime.date = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    thithi_id:  int                          = Field(foreign_key="thithi.id")
    start_time: datetime.datetime
    end_time:   Optional[datetime.datetime]  = None  # NULL = open-ended last transition

    panchangam: Mapped[Optional["Panchangam"]] = Relationship(back_populates="thithi_transitions")
    thithi:     Mapped[Optional["Thithi"]]     = Relationship(back_populates="transitions")
