import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy.orm import Mapped
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.kollavarsham_date import KollavarshamDate
    from db.models.nakshatra import Nakshatra
    from db.models.nakshatra_transition import NakshatraTransition
    from db.models.santhigiri_event_date import SanthigiriEventDate
    from db.models.sunrise_sunset import SunriseSunset
    from db.models.thithi import Thithi
    from db.models.thithi_transition import ThithiTransition


class Panchangam(SQLModel, table=True):
    """
    One row per calendar date.

    thithi_id and nakshatra_id are FK columns required by SQLModel to back
    the thithi / nakshatra relationships. Access them as objects via those
    relationships rather than using the raw id fields directly.
    """

    __tablename__ = "panchangam" # pyright: ignore[reportAssignmentType]

    date:                 datetime.date = Field(primary_key=True)
    is_pournami:          bool
    thithi_id:            int           = Field(foreign_key="thithi.id")
    nakshatra_id:         int           = Field(foreign_key="nakshatra.id")
    nazhika_from_sunrise: float

    thithi:                Mapped[Optional["Thithi"]]                = Relationship(back_populates="panchangams")
    nakshatra:             Optional["Nakshatra"]              = Relationship(back_populates="panchangams")
    kollavarsham:          Mapped[Optional["KollavarshamDate"]]       = Relationship(back_populates="panchangam")
    sunrise_sunsets:       Mapped[List["SunriseSunset"]]              = Relationship(back_populates="panchangam")
    thithi_transitions:    Mapped[List["ThithiTransition"]]           = Relationship(back_populates="panchangam")
    nakshatra_transitions: Mapped[List["NakshatraTransition"]]        = Relationship(back_populates="panchangam")
    santhigiri_events:     Mapped[List["SanthigiriEventDate"]]  = Relationship(back_populates="panchangam")
