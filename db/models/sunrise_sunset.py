from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, Date, ForeignKey, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.panchangam import Panchangam


class SunriseSunset(SQLModel, table=True):
    """
    Sunrise and sunset times for a given date and geographic location.

    Keyed on (date, latitude, longitude) so multiple locations can be
    cached without duplicating astronomical data in the panchangam table.
    """

    __tablename__ = "sunrise_sunset"
    __table_args__ = (
        UniqueConstraint("date", "latitude", "longitude", name="uq_sunrise_sunset_date_loc"),
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
    latitude:  float
    longitude: float
    timezone:  str
    sunrise:   datetime.datetime
    sunset:    datetime.datetime

    panchangam: Optional[Panchangam] = Relationship(back_populates="sunrise_sunsets")
