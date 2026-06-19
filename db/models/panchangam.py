from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from db.models.kollavarsham_date import KollavarshamDate
    from db.models.nakshatra_transition import NakshatraTransition
    from db.models.santhigiri_significant_date import SanthigiriSignificantDate
    from db.models.sunrise_sunset import SunriseSunset
    from db.models.thithi_transition import ThithiTransition


class Panchangam(SQLModel, table=True):
    """
    One row per calendar date.

    Holds only date-level astronomical facts. thithi and nakshatra are
    intentionally absent — they are always derivable from the transition
    active at sunrise (thithi_transitions / nakshatra_transitions joined
    with sunrise_sunset), so storing them here would be redundant.
    """

    __tablename__ = "panchangam"

    date:                 datetime.date = Field(primary_key=True)
    is_pournami:          bool
    nazhika_from_sunrise: float

    kollavarsham:          Optional[KollavarshamDate]       = Relationship(back_populates="panchangam")
    sunrise_sunsets:       List[SunriseSunset]              = Relationship(back_populates="panchangam")
    thithi_transitions:    List[ThithiTransition]           = Relationship(back_populates="panchangam")
    nakshatra_transitions: List[NakshatraTransition]        = Relationship(back_populates="panchangam")
    santhigiri_events:     List[SanthigiriSignificantDate]  = Relationship(back_populates="panchangam")
