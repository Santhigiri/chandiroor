from typing import List
from pydantic import BaseModel, field_serializer
from datetime import date, datetime

from core.astronomy.nakshatra_transition import NakshatraTransition
from core.astronomy.thithi_transition import ThithiTransition
from core.calendar.kollavarsham import KollavarshamDate
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import SanthigiriEvent
from utils.thithi import Thithi


class PanchangamData(BaseModel):
    date: date
    kv: KollavarshamDate
    thithi_transitions: List[ThithiTransition]
    nakshatra_transitions: List[NakshatraTransition]
    thithi: Thithi
    nakshatra: Nakshatra
    sunrise: datetime
    sunset: datetime
    nazhika_from_sunrise: float
    santhigiri_significant_dates: List[SanthigiriEvent] = []

    @field_serializer("nakshatra")
    def ser_nakshatra(self, n: Nakshatra):
        return n.to_dict()
    
    @field_serializer('thithi')
    def ser_thithi(self, t: Thithi):
        return t.to_dict()
