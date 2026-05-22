from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, field_serializer
from core.astronomy.nakshatra_transition import NakshatraTransition
from core.astronomy.thithi_transition import ThithiTransition
from core.calendar.kollavarsham import KollavarshamDate
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.thithi import Thithi


class SanthigiriEventId(str, Enum):
    NAVOLI_JYOTHIR_DINAM = "NAVOLI_JYOTHIR_DINAM"
    JANMAGRIHA_THEERTHA_YATHRA = "JANMAGRIHA_THEERTHA_YATHRA"
    POOJITHA_PEEDA_SAMARPANAM = "POOJITHA_PEEDA_SAMARPANAM"
    POOJITHA_PEEDA_VRITHARAMBAM = "POOJITHA_PEEDA_VRITHARAMBAM"
    SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM = "SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM"
    PRATHISTA_VARSHIKAM = "PRATHISTA_VARSHIKAM"
    PRATHISTA_POORTHIKARANA_VARSHIKAM = "PRATHISTA_POORTHIKARANA_VARSHIKAM"
    DIVYA_POOJA_SAMARPANA_VARSHIKAM = "DIVYA_POOJA_SAMARPANA_VARSHIKAM"
    NAVAPOOJITHAM_VRITHARAMBAM = "NAVAPOOJITHAM_VRITHARAMBAM"
    POORNA_KUMBAMELA = "POORNA_KUMBAMELA"
    SANYASADHEEKSHA_VARSHIKAM = "SANYASADHEEKSHA_VARSHIKAM"
    SAMSKARIKA_DINAM = "SAMSKARIKA_DINAM"
    SHISHYAPOOJITHA_BDAY = "SHISHYAPOOJITHA_BDAY"

class EventCondition(BaseModel):
    nakshatra: Optional[Nakshatra] = None
    thithi: Optional[Thithi] = None
    ml_day: Optional[int] = None
    ml_month: Optional[MalayalamMasa] = None
    ml_year: Optional[int] = None
    en_day: Optional[int] = None
    en_month: Optional[int] = None
    en_year: Optional[int] = None
    occurance: Optional[int] = None
    last_occurance: bool = False

class SanthigiriEvent(BaseModel):
    id: SanthigiriEventId
    name: str
    description: str
    event_condition: EventCondition


class PanchangamData(BaseModel):
    date: date
    kv: KollavarshamDate
    thithi_transitions: List[ThithiTransition]
    nakshatra_transitions: List[NakshatraTransition]
    is_pournami: bool
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


SANTHIGIRI_EVENTS: List[SanthigiriEvent] = []

NAVOLI_JYOTHIR_DINAM = SanthigiriEvent(
        id=SanthigiriEventId.NAVOLI_JYOTHIR_DINAM,
        name="Navoli Jyothir Dinam",
        description="Navoli Jyothir Dinam",
        event_condition=EventCondition(
            en_day= 6,
            en_month=5
        )
    )
SANTHIGIRI_EVENTS.append(NAVOLI_JYOTHIR_DINAM)

JANMAGRIHA_THEERTHA_YATHRA = SanthigiriEvent(
        id=SanthigiriEventId.JANMAGRIHA_THEERTHA_YATHRA,
        name="Janmagriha Theertha Yaathra",
        description="Janmagriha Theertha Yaathra",
        event_condition= EventCondition(
            nakshatra=Nakshatra.CHOTHI
        )
    )
SANTHIGIRI_EVENTS.append(JANMAGRIHA_THEERTHA_YATHRA)

POOJITHA_PEEDA_SAMARPANAM = SanthigiriEvent(
    id=SanthigiriEventId.POOJITHA_PEEDA_SAMARPANAM,
    name="Poojitha Peeda Samarppanam Varshikam",
    description="Poojitha Peeda Samarppanam Varshikam Ardhavarshika kumba mela",
    event_condition= EventCondition(
        en_day=22,
        en_month=2
    )
)

SANTHIGIRI_EVENTS.append(POOJITHA_PEEDA_SAMARPANAM)

POOJITHA_PEEDA_VRITHARAMBAM = SanthigiriEvent(
    id= SanthigiriEventId.POOJITHA_PEEDA_VRITHARAMBAM,
    name="Poojitha Peeda Vritharambam",
    description="Poojitha Peeda Vritharambam",
    event_condition= EventCondition(
        en_month=1,
        en_day=13
    )
)
SANTHIGIRI_EVENTS.append(POOJITHA_PEEDA_VRITHARAMBAM)

PRATHISTA_VARSHIKAM = SanthigiriEvent(
    id=SanthigiriEventId.PRATHISTA_VARSHIKAM,
    name="Prathista Varshikam",
    description="Prathista Varshikam",
    event_condition= EventCondition(
        en_day=10,
        en_month=2
    )
)
SANTHIGIRI_EVENTS.append(PRATHISTA_VARSHIKAM)



NAVOLI_JYOTHIR_DINAM_VRITARAMBAM = SanthigiriEvent(
    id=SanthigiriEventId.NAVOLI_JYOTHIR_DINAM,
    name="Navoli Jyothir Dinam Vritharambam",
    description="Navoli Jyothir Dinam Vritharambam",
    event_condition= EventCondition(
        en_month=2,
        en_day=24
    )
)
SANTHIGIRI_EVENTS.append(NAVOLI_JYOTHIR_DINAM_VRITARAMBAM)

SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM = SanthigiriEvent(
    id=SanthigiriEventId.SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM,
    name="Sahakarana Mandiram Samarpana Varshikam",
    description="Sahakarana Mandiram Samarpana Varshikam",
    event_condition= EventCondition(
        en_day=1,
        en_month=3
    )
)
SANTHIGIRI_EVENTS.append(SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM)

PRATHISTA_POORTHIKARANA_VARSHIKAM = SanthigiriEvent(
    id=SanthigiriEventId.PRATHISTA_POORTHIKARANA_VARSHIKAM,
    name="Prathista Poorthikarana Varshikam",
    description="Prathista Poorthikarana Varshikam",
    event_condition= EventCondition(
        ml_day=10,
        ml_month=MalayalamMasa.MEDAM
    )
)
SANTHIGIRI_EVENTS.append(PRATHISTA_POORTHIKARANA_VARSHIKAM)

DIVYA_POOJA_SAMARPANA_VARSHIKAM = SanthigiriEvent(
    id=SanthigiriEventId.DIVYA_POOJA_SAMARPANA_VARSHIKAM,
    name="Divya pooja samarpana varshikam",
    description="Divya pooja samarpana varshikam",
    event_condition= EventCondition(
        en_day=7,
        en_month=5
    )
)
SANTHIGIRI_EVENTS.append(DIVYA_POOJA_SAMARPANA_VARSHIKAM)

NAVAPOOJITHAM_VRITHARAMBAM = SanthigiriEvent(
    id=SanthigiriEventId.NAVAPOOJITHAM_VRITHARAMBAM,
    name="Navapoojitham vritharambam",
    description="Navapoojitham vritharambam",
    event_condition= EventCondition(
        ml_month=MalayalamMasa.CHINGAM,
    )
)
#SANTHIGIRI_EVENTS.append(NAVAPOOJITHAM_VRITHARAMBAM)

POORNA_KUMBAMELA = SanthigiriEvent(
    id=SanthigiriEventId.POORNA_KUMBAMELA,
    name="Poornakumba mela",
    description="Poorna kumbamela",
    event_condition= EventCondition(
        ml_month=MalayalamMasa.KANNI,
        ml_day=4
    )
)
SANTHIGIRI_EVENTS.append(POORNA_KUMBAMELA)


#TODO: need to be verified
SANYASADEEKSHA_VARSHIKAM = SanthigiriEvent(
    id=SanthigiriEventId.SANYASADHEEKSHA_VARSHIKAM,
    name="Sanyasadheeksha varshikam",
    description="Sanyasadheeksha varshikam",
    event_condition= EventCondition(
        ml_month=MalayalamMasa.THULAM,
        thithi=Thithi.DASHAMI_SHUKLA
    )
)
SANTHIGIRI_EVENTS.append(SANYASADEEKSHA_VARSHIKAM)

SAMSKARIKA_DINAM = SanthigiriEvent(
    id=SanthigiriEventId.SAMSKARIKA_DINAM,
    name="Samskarika Dinam",
    description="Samskarika Dinam",
    event_condition= EventCondition(
        en_day=5,
        en_month=11
    )
)

SHISHYAPOOJITHA_BDAY = SanthigiriEvent(
    id=SanthigiriEventId.SHISHYAPOOJITHA_BDAY,
    name="Shishyapoojitha's Birthday",
    description="Shishyapoojitha's Birthday",
    event_condition= EventCondition(
        ml_month=MalayalamMasa.THULAM,
        nakshatra=Nakshatra.POORADAM,
        last_occurance=True
    )
)
