from typing import Dict, List, Optional

from pydantic import BaseModel
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.thithi import Thithi


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
    is_poornima: Optional[bool] = None
    last_occurance: Optional[bool] = None
    # Shift the day the other condition fields match by N days. None/0 = no
    # shift; positive = N days after; negative = N days before. Honored
    # identically by the offline pickle pipeline (utils/cache_*.py) and the
    # live DB pipeline (core/calendar/santhigiri_event_occurrences.py).
    day_offset: Optional[int] = None

class SanthigiriEvent(BaseModel):
    id: str
    name: str
    description: str
    event_condition: EventCondition




SANTHIGIRI_EVENTS: List[SanthigiriEvent] = []



POURNAMI = SanthigiriEvent(
    id="POURNAMI",
    name="Pournami",
    description="""
    The full moon day (Pournami) is observed as a day of fasting and prayers at the Ashram. This day is considered very auspicious for spiritual and material wellbeing. It is also an apt time to pray for one’s ancestral lineage (pithrus) and a change in our capability and propensity for action (‘karmagati’). Devotees in large numbers pray through the day and night at the Ashram on ‘Pournami’, with Deepa and Kumbha Pradakshina. Pournami prayers are held at the Ashram Branches also.
    """,
    event_condition=EventCondition(
        is_poornima=True
    )
)


NAVOLI_JYOTHIR_DINAM = SanthigiriEvent(
        id="NAVOLI_JYOTHIR_DINAM",
        name="Navoli Jyothir Dinam",
        description="""
This is the day on which Guru left His physical body and merged in the ‘Adisankalpam’ (The Plane of Primordial Consciousness), on May 6th, 1999. The Guru’s ‘Prakasham’ (Light) is now present in the world as ‘Nava Oli’ (A New Light). The day is observed as ‘Navaolijyothirdinam – Sarvamangala Sudinam’ (the Day of the New Light, Auspicious for All). Devotees observe ‘vratam’ (austerities) for 72 days prior to ‘Navaolijyothirdinam’, commemorating the 72 years that Guru lived, enduring great sacrifices and hardships. A Deepa Pradakshina is held in the evening, followed by a special ‘pushpanjali’ (floral offering) by the sanyasi sangh. A spectacular fireworks and percussion display is held after the 9 p.m. prayers to mark the time of the Guru’s physical departure.
        """,
        event_condition=EventCondition(
            en_day= 6,
            en_month=5
        )
    )
SANTHIGIRI_EVENTS.append(NAVOLI_JYOTHIR_DINAM)

JANMAGRIHA_THEERTHA_YATHRA = SanthigiriEvent(
        id="JANMAGRIHA_THEERTHA_YATHRA",
        name="Janmagriha Theertha Yaathra",
        description="Janmagriha Theertha Yaathra",
        event_condition= EventCondition(
            nakshatra=Nakshatra.CHOTHI
        )
    )
SANTHIGIRI_EVENTS.append(JANMAGRIHA_THEERTHA_YATHRA)

POOJITHA_PEEDA_SAMARPANAM = SanthigiriEvent(
    id="POOJITHA_PEEDA_SAMARPANAM",
    name="Poojitha Peeda Samarppanam Varshikam",
    description="Poojitha Peeda Samarppanam Varshikam Ardhavarshika kumba mela",
    event_condition= EventCondition(
        en_day=22,
        en_month=2
    )
)

SANTHIGIRI_EVENTS.append(POOJITHA_PEEDA_SAMARPANAM)

POOJITHA_PEEDA_VRITHARAMBAM = SanthigiriEvent(
    id="POOJITHA_PEEDA_VRITHARAMBAM",
    name="Poojitha Peeda Vritharambam",
    description="Poojitha Peeda Vritharambam",
    event_condition= EventCondition(
        en_month=1,
        en_day=13
    )
)
SANTHIGIRI_EVENTS.append(POOJITHA_PEEDA_VRITHARAMBAM)

PRATHISTA_VARSHIKAM = SanthigiriEvent(
    id="PRATHISTA_VARSHIKAM",
    name="Prathista Varshikam",
    description="Prathista Varshikam",
    event_condition= EventCondition(
        en_day=10,
        en_month=2
    )
)
SANTHIGIRI_EVENTS.append(PRATHISTA_VARSHIKAM)



NAVOLI_JYOTHIR_DINAM_VRITARAMBAM = SanthigiriEvent(
    id="NAVOLI_JYOTHIR_DINAM_VRITHARAMBAM",
    name="Navoli Jyothir Dinam Vritharambam",
    description="Navoli Jyothir Dinam Vritharambam",
    event_condition= EventCondition(
        en_month=2,
        en_day=24
    )
)
SANTHIGIRI_EVENTS.append(NAVOLI_JYOTHIR_DINAM_VRITARAMBAM)

SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM = SanthigiriEvent(
    id="SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM",
    name="Sahakarana Mandiram Samarpana Varshikam",
    description="""
        On this day the ‘Sahakarana Mandiram’ (Shrine of Togetherness) was dedicated to Guru. The day falls on Kumbham 17 (February-March). It is marked by special prayers at the Ashram.
    """,
    event_condition= EventCondition(
        ml_month=MalayalamMasa.KUMBHAM,
        ml_day=17
    )
)
SANTHIGIRI_EVENTS.append(SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM)

PRATHISTA_POORTHIKARANA_VARSHIKAM = SanthigiriEvent(
    id="PRATHISTA_POORTHIKARANA_VARSHIKAM",
    name="Prathista Poorthikarana Varshikam",
    description="Prathista Poorthikarana Varshikam",
    event_condition= EventCondition(
        ml_day=10,
        ml_month=MalayalamMasa.MEDAM
    )
)
SANTHIGIRI_EVENTS.append(PRATHISTA_POORTHIKARANA_VARSHIKAM)

DIVYA_POOJA_SAMARPANA_VARSHIKAM = SanthigiriEvent(
    id="DIVYA_POOJA_SAMARPANA_VARSHIKAM",
    name="Divya pooja samarpana varshikam",
    description="Divya pooja samarpana varshikam",
    event_condition= EventCondition(
        en_day=7,
        en_month=5
    )
)
SANTHIGIRI_EVENTS.append(DIVYA_POOJA_SAMARPANA_VARSHIKAM)

NAVAPOOJITHAM_VRITHARAMBAM = SanthigiriEvent(
    id="NAVAPOOJITHAM_VRITHARAMBAM",
    name="Navapoojitham vritharambam",
    description="Navapoojitham vritharambam",
    event_condition= EventCondition(
        ml_month=MalayalamMasa.CHINGAM,
    )
)
#SANTHIGIRI_EVENTS.append(NAVAPOOJITHAM_VRITHARAMBAM)

NAVAPOOJITHAM = SanthigiriEvent(
    id="NAVAPOOJITHAM",
    name="Navapoojitham",
    description="""
        Guru was born on September 1, 1927. The birthday celebrations are held as per the Malayalam Calendar, according to which Guru was born under the ‘Chothi’ star in the month of ‘Chingam’ (falling in August-September). The day is celebrated as ‘Navapoojitham - Janmadina Poojitha Samarpanam’. It is a day of special prayers, including Deepa Pradakshina (procession with lit lamps), at the Ashram.
    """,
    event_condition= EventCondition(
        ml_month=MalayalamMasa.CHINGAM,
        nakshatra= Nakshatra.CHOTHI,
        last_occurance=True
    )
)
#SANTHIGIRI_EVENTS.append(NAVAPOOJITHAM)

POORNA_KUMBAMELA = SanthigiriEvent(
    id="POORNA_KUMBAMELA",
    name="Poornakumba mela",
    description="""
The ‘Poorna Kumbhamela’ commemorates the day of the Guru’s spiritual attainment, falling on the 4th of the Malayalam month of ‘Kanni’ (September). The highlight of the celebrations is a colorful procession by devotees, carrying ceremonial parasols and decorated ‘kumbhams’ (earthen pots filled with holy water – theertham), around the Ashram. Taking the ‘kumbham’ for 12 successive times helps to remove the ‘karmadoshas’ (karmic errors) of the self and the family.
    """,
    event_condition= EventCondition(
        ml_month=MalayalamMasa.KANNI,
        ml_day=4
    )
)
SANTHIGIRI_EVENTS.append(POORNA_KUMBAMELA)


#TODO: need to be verified
SANYASADEEKSHA_VARSHIKAM = SanthigiriEvent(
    id="SANYASADHEEKSHA_VARSHIKAM",
    name="Sanyasadheeksha varshikam",
    description="""
        Falling on the Vijayadashami day (mostly in October), this marks the anniversary of the day that Guru first conferred ‘sanyasam’ (vow of renunciation of householder life) on disciples in 1984. Every year on this day, devotees gather to pray for the wellbeing of ‘sanyasis’ (renunciates). This paves the way for greater mutual understanding and spiritual bonding between the renunciate and the householder.
    """,
    event_condition= EventCondition(
        ml_month=MalayalamMasa.THULAM,
        thithi=Thithi.DASHAMI_SHUKLA
    )
)
SANTHIGIRI_EVENTS.append(SANYASADEEKSHA_VARSHIKAM)

SAMSKARIKA_DINAM = SanthigiriEvent(
    id="SAMSKARIKA_DINAM",
    name="Samskarika Dinam",
    description="""
        The formation of a National Centre for Cultural Renaissance (NCCR) on February 17, 1983, marked the beginning of an organized movement for cultural activities in the Ashram. The ‘Santhigiri Vishwa Samskarika Navodhana Kendram’ was registered as a charitable society on June 20, 1984. The organization is engaged in various cultural and voluntary activities to propagate the teachings of Guru for a spiritual and cultural renaissance in the world. The Santhigiri Vishwa Samskarika Navodhana Kendram has more than 200 units in Kerala and elsewhere. The Samskarika Dinam is marked by awareness meetings, seminars and cultural programmes to spread the Guru’s ideology.
    """,
    event_condition= EventCondition(
        en_day=5,
        en_month=11
    )
)

SISHYAPOOJITHA_BDAY = SanthigiriEvent(
    id="SHISHYAPOOJITHA_BDAY",
    name="Shishyapoojitha's Birthday",
    description="Shishyapoojitha's Birthday",
    event_condition= EventCondition(
        ml_month=MalayalamMasa.THULAM,
        nakshatra=Nakshatra.POORADAM,
        last_occurance=True
    )
)


# Every defined event, unlike SANTHIGIRI_EVENTS (which excludes events handled
# by dedicated cache logic, e.g. Pournami/Navapoojitham/Sishya-bday). Used to
# build the id -> definition lookup for the /panchangam/events reference endpoint.
ALL_SANTHIGIRI_EVENTS: List[SanthigiriEvent] = [
    POURNAMI, NAVOLI_JYOTHIR_DINAM, JANMAGRIHA_THEERTHA_YATHRA,
    POOJITHA_PEEDA_SAMARPANAM, POOJITHA_PEEDA_VRITHARAMBAM, PRATHISTA_VARSHIKAM,
    NAVOLI_JYOTHIR_DINAM_VRITARAMBAM, SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM,
    PRATHISTA_POORTHIKARANA_VARSHIKAM, DIVYA_POOJA_SAMARPANA_VARSHIKAM,
    NAVAPOOJITHAM_VRITHARAMBAM, NAVAPOOJITHAM, POORNA_KUMBAMELA,
    SANYASADEEKSHA_VARSHIKAM, SAMSKARIKA_DINAM, SISHYAPOOJITHA_BDAY,
]

# Every event has a distinct string id, so this is a straight id -> definition
# map. ``setdefault`` still guards against an accidental future duplicate (first
# listed wins) rather than silently overwriting.
EVENT_DEFINITIONS_BY_ID: Dict[str, SanthigiriEvent] = {}
for _event in ALL_SANTHIGIRI_EVENTS:
    EVENT_DEFINITIONS_BY_ID.setdefault(_event.id, _event)

