
from datetime import date
from typing import Dict

from schemas.panchangam_data import PanchangamData
from utils.cache_crud import load_cache
from utils.santhigiri_events import SanthigiriEvent


PanchangamCache = Dict[date, PanchangamData]
def get_yearly_cache(cache: PanchangamCache, year: int):
    return {k: v for k,v in cache.items() if k.year == year}

def remove_event_from_cache(cache: PanchangamCache, event: SanthigiriEvent) -> PanchangamCache:
    updated_panchangam = cache

    for dt, p_data in updated_panchangam.items():
        if event in p_data.santhigiri_significant_dates:
            updated_panchangam[dt].santhigiri_significant_dates.remove(event)

    return updated_panchangam
