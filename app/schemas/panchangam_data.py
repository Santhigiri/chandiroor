from typing import List, Optional
from pydantic import BaseModel, field_serializer
from datetime import date, datetime

from app.core.astronomy.transitions import NakshatraTransition, ThithiTransition
from app.core.kollavarsham.kollavarsham_models import KollavarshamDate
from app.schemas.location import LocationInfo
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.utils.santhigiri_events import SanthigiriEvent
from app.core.astronomy.enums.thithi import Thithi


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
    # Which location these values were computed for. Optional/defaulted so
    # existing constructors keep working; set on the repository and
    # live-computation paths where the location is known.
    location: Optional[LocationInfo] = None

    @field_serializer("nakshatra")
    def ser_nakshatra(self, n: Nakshatra):
        return n.to_dict()
    
    @field_serializer('thithi')
    def ser_thithi(self, t: Thithi):
        return t.to_dict()
