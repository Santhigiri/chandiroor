import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey, Index
from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.nakshatra import Nakshatra
    from db.models.panchangam import Panchangam


class NakshatraTransition(SQLModel, table=True):
    """A nakshatra (lunar mansion) active during part of a calendar day."""

    __tablename__ = "nakshatra_transitions"
    __table_args__ = (
        Index("idx_nakshatra_transitions_date", "panchangam_date", "start_time"),
    )

    id:             Optional[int]  = Field(default=None, primary_key=True)
    panchangam_date: datetime.date = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    nakshatra_id: int                         = Field(foreign_key="nakshatra.id")
    start_time:   datetime.datetime
    end_time:     Optional[datetime.datetime] = None

    panchangam: Mapped[Optional["Panchangam"]] = Relationship(back_populates="nakshatra_transitions")
    nakshatra:  Mapped[Optional["Nakshatra"]]  = Relationship(back_populates="transitions")
