import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.kollavarsham_date import KollavarshamDate
    from db.models.location import Location
    from db.models.nakshatra import Nakshatra
    from db.models.nakshatra_transition import NakshatraTransition
    from db.models.sunrise_sunset import SunriseSunset
    from db.models.thithi import Thithi
    from db.models.thithi_transition import ThithiTransition


class Panchangam(SQLModel, table=True):
    """
    One row per calendar date *per location*.

    The primary key is the composite ``(date, location_id)`` so the same
    calendar date can hold independent panchangam values for multiple
    locations (sunrise/sunset, the thithi/nakshatra active at sunrise, and the
    nazhika all depend on the observer's coordinates). Santhigiri ashram events
    are location-independent and live in ``santhigiri_event_dates`` keyed by
    date alone.

    thithi_id and nakshatra_id are FK columns required by SQLModel to back
    the thithi / nakshatra relationships. Access them as objects via those
    relationships rather than using the raw id fields directly.
    """

    __tablename__ = "panchangam" # pyright: ignore[reportAssignmentType]

    date:                 datetime.date = Field(primary_key=True)
    location_id:          int           = Field(foreign_key="location.id", primary_key=True)
    thithi_id:            int           = Field(foreign_key="thithi.id")
    nakshatra_id:         int           = Field(foreign_key="nakshatra.id")
    nazhika_from_sunrise: float

    thithi:                Optional["Thithi"]           = Relationship(back_populates="panchangams")
    nakshatra:             Optional["Nakshatra"]                = Relationship(back_populates="panchangams")
    location:              Optional["Location"]                 = Relationship()
    kollavarsham:          Optional["KollavarshamDate"] = Relationship(back_populates="panchangam")
    sunrise_sunset:        Optional["SunriseSunset"]    = Relationship(
        back_populates="panchangam",
        # location_id is shared with SunriseSunset.location's FK to location.
        sa_relationship_kwargs={"overlaps": "sunrise_sunsets"},
    )
    thithi_transitions:    List["ThithiTransition"]     = Relationship(back_populates="panchangam")
    nakshatra_transitions: List["NakshatraTransition"]  = Relationship(back_populates="panchangam")
