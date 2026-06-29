from datetime import datetime, timedelta
from typing import List, Tuple
from core.astronomy.calculations import get_moon_sidereal_longitude
from core.astronomy.nakshatra_transition import NakshatraTransition
from utils.nakshatra import Nakshatra
from utils.utils import calc_nakshatra_from_lon

def get_nakshatra(localdt: datetime, timezone: str)->Tuple[str, float]:
    # Calculate Moon's sidereal longitude
    moon_sidereal_longitude = get_moon_sidereal_longitude(localdt=localdt, timezone=timezone)

    # Determine Nakshatra using sidereal longitude
    nakshatra = calc_nakshatra_from_lon(moon_sidereal_longitude)

    return nakshatra, moon_sidereal_longitude



def get_duration_from_sunrise(nakshatra: Nakshatra,nakshatra_transitions: List[NakshatraTransition], sunrise: datetime)-> float:
    filtered_transitions = [n for n in nakshatra_transitions if n.nakshatra == nakshatra]
    next_sunrise = sunrise + timedelta(days=1)
    if filtered_transitions:
        overlap_start = max(sunrise, filtered_transitions[0].start_time)
        overlap_end = next_sunrise if filtered_transitions[0].end_time is None else min(next_sunrise, filtered_transitions[0].end_time)
    else:
        overlap_start = sunrise
        overlap_end = next_sunrise

    if overlap_end <= overlap_start:
        return 0
    diff =  overlap_end - overlap_start
    return duration_to_nazhika(diff)
    
def duration_to_nazhika(dur: timedelta) -> float:
    return round(dur.total_seconds() / 1440, 2)
