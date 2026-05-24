
from datetime import date
from typing import Dict, List

from schemas.panchangam_data import PanchangamData
from utils.santhigiri_events import SanthigiriEvent


PanchangamCache = Dict[date, PanchangamData]
def get_yearly_cache(cache: PanchangamCache, year: int):
    return {k: v for k,v in cache.items() if k.year == year}

def remove_events_from_cache(cache: PanchangamCache, events: List[SanthigiriEvent]) -> PanchangamCache:
    updated_panchangam = cache

    for dt, p_data in updated_panchangam.items():
        day_events = p_data.santhigiri_significant_dates
        common_events = {e.id: e for e in events if e in day_events}
        updated_panchangam[dt].santhigiri_significant_dates = [e for e in day_events if e not in common_events.values()]

    return updated_panchangam
