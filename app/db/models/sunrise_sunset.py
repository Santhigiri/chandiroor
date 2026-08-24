import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Column, ForeignKeyConstraint, Index, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from db.models.types import UTCDateTime

if TYPE_CHECKING:
    from db.models.location import Location
    from db.models.panchangam import Panchangam


class SunriseSunset(SQLModel, table=True):
    """
    Sunrise and sunset times for a given date and geographic location.

    Keyed on (date, location_id) — one-to-one with the ``(date, location_id)``
    panchangam row it belongs to. The location's coordinates and timezone live
    in the ``location`` table.
    """

    __tablename__ = "sunrise_sunset" # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        ForeignKeyConstraint(
            ["date", "location_id"],
            ["panchangam.date", "panchangam.location_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("date", "location_id", name="uq_sunrise_sunset_date_loc"),
        Index("idx_sunrise_sunset_date", "date"),
    )

    id:          Optional[int]      = Field(default=None, primary_key=True)
    date:        datetime.date
    location_id: int                = Field(foreign_key="location.id")
    sunrise:     datetime.datetime = Field(sa_column=Column(UTCDateTime, nullable=False))
    sunset:      datetime.datetime = Field(sa_column=Column(UTCDateTime, nullable=False))

    # location_id is shared between the FK to ``location`` and the composite FK
    # to ``panchangam``; overlaps annotations tell SQLAlchemy this is intentional.
    location:   Optional["Location"]   = Relationship(
        back_populates="sunrise_sunsets",
        sa_relationship_kwargs={"overlaps": "sunrise_sunset"},
    )
    panchangam: Optional["Panchangam"] = Relationship(
        back_populates="sunrise_sunset",
        sa_relationship_kwargs={"overlaps": "location,sunrise_sunsets"},
    )
