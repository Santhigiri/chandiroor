from datetime import date, datetime, time, timedelta
from typing import Dict, List, Tuple
from core.astronomy.pournami import is_poornima
from core.constants import DEFAULT_TIMEZONE
from utils.cache_crud import load_cache, write_cache
from utils.cache_utils import remove_events_from_cache
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import NAVAPOOJITHAM, EventCondition
from schemas.panchangam_data import PanchangamData

PanchangamCache = Dict[date, PanchangamData]

def get_yearly_cache(cache: PanchangamCache, year: int):
    return {k: v for k,v in cache.items() if k.year == year}

def calculate_navapoojitham(yearly_cache: PanchangamCache, year: int)-> date:
    filtered_events  = get_matching_dates(yearly_cache, NAVAPOOJITHAM.event_condition)
    if len(filtered_events) > 0:
        dt, p_data = filtered_events[-1]
        if p_data.nazhika_from_sunrise > 7.5:
            return dt
        else:
            return dt - timedelta(days= 1)
    chingam_transitions = {dt: p_cache for dt, p_cache in yearly_cache.items() if p_cache.kv.kv_month == MalayalamMasa.CHINGAM.id}
    chothi_transitions = [t for _, data in chingam_transitions.items() for t in data.nakshatra_transitions if t.nakshatra == Nakshatra.CHOTHI]
    if len(chothi_transitions) == 0:
        raise Exception(f"No nakshatra transition found for chothi in the month of Chingam in {year}")
    last_transition = chothi_transitions[-1]
    return last_transition.start_time.date()


def get_matching_dates(data: PanchangamCache, event_condition: EventCondition) -> List[Tuple[date, PanchangamData]]:
    occurances = []
    for d, panchangam_data in data.items():
        if event_condition.nakshatra is not None and event_condition.nakshatra != panchangam_data.nakshatra:
            continue
        if event_condition.thithi is not None and event_condition.thithi != panchangam_data.thithi:
            continue
        if event_condition.ml_day is not None and event_condition.ml_day != panchangam_data.kv.kv_day:
            continue
        if event_condition.ml_month is not None and event_condition.ml_month.id != panchangam_data.kv.kv_month:
            continue
        if event_condition.ml_year is not None and event_condition.ml_year != panchangam_data.kv.kv_year:
            continue
        if event_condition.en_day is not None and event_condition.en_day != panchangam_data.date.day:
            continue
        if event_condition.en_month is not None and event_condition.en_month != panchangam_data.date.month:
            continue
        if event_condition.en_year is not None and event_condition.en_year != panchangam_data.date.year:
            continue
        if event_condition.is_poornima is not None and event_condition.is_poornima != is_poornima(datetime.combine(panchangam_data.date, time.min), DEFAULT_TIMEZONE):
            continue

        occurances.append((d, panchangam_data))

    return occurances


def remove_navapoojitham():
    panchangam_cache = load_cache()
    events_to_remove = [NAVAPOOJITHAM]
    updated_cache = remove_events_from_cache(panchangam_cache, events_to_remove)
    write_cache(updated_cache)
    

def update_navapoojitham(panchangamCache: PanchangamCache)-> PanchangamCache:
    """
    Updates Navapoojitham of a panchangam cache and returns the updated cache. 
    Iterates through each year in the cache and updates :attr:`PanchangamData.santhigiri_significant_dates` with the :class:`SanthigiriEvent` `NAVAPOOJITHAM`
    """
    start_year = min(panchangamCache.keys())
    end_year = max(panchangamCache.keys())
    updated_panchangam = panchangamCache

    for year in range(start_year.year, end_year.year + 1):
        yearly_data = get_yearly_cache(panchangamCache, year)
        navapoojitham_date = calculate_navapoojitham(yearly_data, year)

        print(f"NAVAPOOJITHAM DATE FOR {year}: {navapoojitham_date}")
        updated_events = updated_panchangam[navapoojitham_date].santhigiri_significant_dates
        updated_events.append(NAVAPOOJITHAM)
        updated_panchangam[navapoojitham_date].santhigiri_significant_dates = list(set(updated_events))
    return updated_panchangam


def cache_navapoojitham():
    cache: PanchangamCache = load_cache()
    updated_cache = update_navapoojitham(cache)
    write_cache(updated_cache)



#remove_navapoojitham()
#cache_navapoojitham()


