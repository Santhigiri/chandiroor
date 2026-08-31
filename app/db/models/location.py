from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.sunrise_sunset import SunriseSunset


class Location(SQLModel, table=True):
    """
    A geographic location panchangam data can be computed for.

    Coordinates and timezone live here, once per location, instead of being
    repeated on every ``sunrise_sunset`` row. Seeded from ``utils.location.Location``.
    """

    __tablename__ = "location" # pyright: ignore[reportAssignmentType]

    id:        int = Field(default=None, primary_key=True)
    name:      str           = Field(unique=True, index=True)  # short code, e.g. 'tvm'
    label:     str           # human-readable, e.g. 'Trivandrum, Kerala, India'
    latitude:  float
    longitude: float
    timezone:  str

    sunrise_sunsets: List["SunriseSunset"] = Relationship(back_populates="location")
