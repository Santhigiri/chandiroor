import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.location import Location
    from db.models.panchangam import Panchangam


class SunriseSunset(SQLModel, table=True):
    """
    Sunrise and sunset times for a given date and geographic location.

    Keyed on (date, location_id) so multiple locations can be cached without
    duplicating astronomical data in the panchangam table. The location's
    coordinates and timezone live in the ``location`` table.
    """

    __tablename__ = "sunrise_sunset" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        UniqueConstraint("date", "location_id", name="uq_sunrise_sunset_date_loc"),
        Index("idx_sunrise_sunset_date", "date"),
    )

    id:        Optional[int]   = Field(default=None, primary_key=True)
    date:      datetime.date   = Field(
        sa_column=Column(
            Date,
            ForeignKey("panchangam.date", ondelete="CASCADE"),
            nullable=False,
        )
    )
    location_id: int           = Field(foreign_key="location.id")
    sunrise:   datetime.datetime
    sunset:    datetime.datetime

    location:   Optional["Location"]   = Relationship(back_populates="sunrise_sunsets")
    panchangam: Optional["Panchangam"] = Relationship(back_populates="sunrise_sunsets")
