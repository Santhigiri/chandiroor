"""Lightweight transition value-objects.

These Pydantic models describe a Thithi/Nakshatra interval within a day. They are
kept free of any Skyfield/ephemeris imports so that the API response schema
(``schemas.panchangam_data``) and the DB repository can import them without
pulling in the heavy astronomy stack. The compute modules
(``core.astronomy.thithi_transition`` / ``nakshatra_transition``) import these
classes back and populate them; that stack loads only when live computation is
actually needed.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_serializer

from app.utils.nakshatra import Nakshatra
from app.utils.thithi import Thithi


class ThithiTransition(BaseModel):
    name: str
    thithi: Thithi
    start_time: datetime
    end_time: datetime | None

    @field_serializer("thithi")
    def ser_thithi(self, t: Thithi):
        return t.to_dict()


class NakshatraTransition(BaseModel):
    name: str
    nakshatra: Nakshatra
    start_time: datetime
    end_time: Optional[datetime]

    @field_serializer("nakshatra")
    def ser_nakshatra(self, n: Nakshatra):
        return n.to_dict()
