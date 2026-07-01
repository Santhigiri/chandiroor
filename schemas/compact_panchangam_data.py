from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel

from schemas.panchangam_data import PanchangamData
from utils.malayalam_masa import MalayalamMasa
from utils.santhigiri_events import SanthigiriEvent


class CompactKollavarshamDate(BaseModel):
    date: date
    kv_day: int
    kv_year: int
    masa: str


class CompactThithiTransition(BaseModel):
    name: str
    thithi: str
    start_time: datetime
    end_time: Optional[datetime]


class CompactNakshatraTransition(BaseModel):
    name: str
    nakshatra: str
    start_time: datetime
    end_time: Optional[datetime]


class CompactPanchangamData(BaseModel):
    date: date
    kv: CompactKollavarshamDate
    thithi_transitions: List[CompactThithiTransition]
    nakshatra_transitions: List[CompactNakshatraTransition]
    is_pournami: bool
    thithi: str
    nakshatra: str
    sunrise: datetime
    sunset: datetime
    nazhika_from_sunrise: float
    santhigiri_significant_dates: List[SanthigiriEvent] = []

    @classmethod
    def from_panchangam_data(cls, data: PanchangamData) -> "CompactPanchangamData":
        return cls(
            date=data.date,
            kv=CompactKollavarshamDate(
                date=data.kv.date,
                kv_day=data.kv.kv_day,
                kv_year=data.kv.kv_year,
                masa=MalayalamMasa.from_id(data.kv.kv_month).name,
            ),
            thithi_transitions=[
                CompactThithiTransition(
                    name=t.name,
                    thithi=t.thithi.name,
                    start_time=t.start_time,
                    end_time=t.end_time,
                )
                for t in data.thithi_transitions
            ],
            nakshatra_transitions=[
                CompactNakshatraTransition(
                    name=n.name,
                    nakshatra=n.nakshatra.name,
                    start_time=n.start_time,
                    end_time=n.end_time,
                )
                for n in data.nakshatra_transitions
            ],
            is_pournami=data.is_pournami,
            thithi=data.thithi.name,
            nakshatra=data.nakshatra.name,
            sunrise=data.sunrise,
            sunset=data.sunset,
            nazhika_from_sunrise=data.nazhika_from_sunrise,
            santhigiri_significant_dates=data.santhigiri_significant_dates,
        )
