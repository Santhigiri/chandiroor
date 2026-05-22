from datetime import datetime, timedelta
from typing import List
from core.astronomy.nakshatra_transition import NakshatraTransition
from core.astronomy.thithi_transition import ThithiTransition
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import SANTHIGIRI_EVENTS, EventCondition, PanchangamData, SanthigiriEvent
from typing import List
from utils.lifespan import PANCHANGAM_CACHE


def get_santhigiri_significant_dates_without_occurances(panchangam_data: PanchangamData) -> List[SanthigiriEvent]:
    occurances = []
    events_without_occurances: List[SanthigiriEvent] = [e for e in SANTHIGIRI_EVENTS if e.event_condition.occurance is None and e.event_condition.last_occurance == False]
    for event in events_without_occurances:
        condition: EventCondition = event.event_condition
        if condition.nakshatra is not None and condition.nakshatra != panchangam_data.nakshatra:
            continue
        if condition.thithi is not None and condition.thithi != panchangam_data.thithi:
            continue
        if condition.ml_day is not None and condition.ml_day != panchangam_data.kv.kv_day:
            continue
        if condition.ml_month is not None and condition.ml_month != panchangam_data.kv.kv_month:
            continue
        if condition.ml_year is not None and condition.ml_year != panchangam_data.kv.kv_year:
            continue
        if condition.en_day is not None and condition.en_day != panchangam_data.date.day:
            continue
        if condition.en_month is not None and condition.en_month != panchangam_data.date.month:
            continue
        if condition.en_year is not None and condition.en_year != panchangam_data.date.year:
            continue

        occurances.append(event)

    return occurances

def get_duration_from_sunrise(nakshatra: Nakshatra,nakshatra_transitions: List[NakshatraTransition], sunrise: datetime)-> float:
    print(f"Nakshatra at Sunrise: {nakshatra}")
    print(f"Transtions: {nakshatra_transitions}")
    filtered_transitions = [n for n in nakshatra_transitions if n.nakshatra == nakshatra]
    overlap_start = sunrise if len(filtered_transitions) == 0 else max(sunrise, filtered_transitions[0].start_time)
    next_sunrise = sunrise + timedelta(days=1)
    overlap_end = next_sunrise if filtered_transitions[0].end_time is None else min(next_sunrise, filtered_transitions[0].end_time)
    
    if overlap_end <= overlap_start:
        return 0
    diff =  overlap_end - overlap_start
    return duration_to_nazhika(diff)
    
def duration_to_nazhika(dur: timedelta) -> float:
    return round(dur.total_seconds() / 1440, 2)


def calculate_navapoojitham_for_year(year: int):
    chothi_days = [d for d in PANCHANGAM_CACHE.values() 
        if d.date.year == year and
        d.kv.kv_month == MalayalamMasa.CHINGAM.id and
        d.nakshatra == Nakshatra.CHOTHI
    ]
    print(f"chothi days count: {len(chothi_days)}")

    for d in chothi_days:
        print(f"{d.date}: {get_duration_from_sunrise(Nakshatra.CHOTHI, d.nakshatra_transitions, d.sunrise)}")







