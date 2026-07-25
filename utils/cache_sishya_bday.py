from datetime import date, timedelta
from typing import Dict, List, Tuple
from core.astronomy.pournami import is_poornima
from utils.cache_crud import load_cache, write_cache
from utils.cache_utils import remove_events_from_cache
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import NAVAPOOJITHAM, SISHYAPOOJITHA_BDAY, EventCondition
from schemas.panchangam_data import PanchangamData

PanchangamCache = Dict[date, PanchangamData]

def get_yearly_cache(cache: PanchangamCache, year: int):
    return {k: v for k,v in cache.items() if k.year == year}

def calculate_sishya_bday(yearly_cache: PanchangamCache, year: int)-> date:
    event = SISHYAPOOJITHA_BDAY
    filtered_events  = get_matching_dates(yearly_cache, event.event_condition)
    if len(filtered_events) > 0:
        dt, p_data = filtered_events[-1]
        if p_data.nazhika_from_sunrise > 7.5:
            return dt
        else:
            return dt - timedelta(days= 1)
    month_transitions = {dt: p_cache for dt, p_cache in yearly_cache.items() if event.event_condition.ml_month is not None and  p_cache.kv.kv_month == event.event_condition.ml_month.id}
    nakshatra_transitions = [t for _, data in month_transitions.items() for t in data.nakshatra_transitions if t.nakshatra == event.event_condition.nakshatra]
    if len(nakshatra_transitions) == 0:
        raise Exception(f"No nakshatra transition in {year}")
    last_transition = nakshatra_transitions[-1]
    return last_transition.start_time.date()


def get_matching_dates(data: PanchangamCache, event_condition: EventCondition) -> List[Tuple[date, PanchangamData]]:
    # Reuse the sunrise/sunset and thithi transitions already populated on each
    # PanchangamData (from the cache/DB) so Pournami is derived without recomputing
    # them via the ephemeris.
    thithi_transitions_by_date = {d: pd.thithi_transitions for d, pd in data.items()}
    sunrise_sunset_by_date = {d: (pd.sunrise, pd.sunset) for d, pd in data.items()}
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
        if event_condition.is_poornima is not None and event_condition.is_poornima != is_poornima(panchangam_data.date, thithi_transitions_by_date, sunrise_sunset_by_date):
            continue

        occurances.append((d, panchangam_data))

    return occurances


def remove_sishya_bday():
    panchangam_cache = load_cache()
    events_to_remove = [SISHYAPOOJITHA_BDAY]
    updated_cache = remove_events_from_cache(panchangam_cache, events_to_remove)
    write_cache(updated_cache)
    

def update_sishya_bday(panchangamCache: PanchangamCache)-> PanchangamCache:
    """
    Updates Navapoojitham of a panchangam cache and returns the updated cache. 
    Iterates through each year in the cache and updates :attr:`PanchangamData.santhigiri_significant_dates` with the :class:`SanthigiriEvent` `NAVAPOOJITHAM`
    """
    start_year = min(panchangamCache.keys())
    end_year = max(panchangamCache.keys())
    updated_panchangam = panchangamCache

    for year in range(start_year.year, end_year.year + 1):
        yearly_data = get_yearly_cache(panchangamCache, year)
        bday_date = calculate_sishya_bday(yearly_data, year)

        print(f"SISHYA_BDAY DATE FOR {year}: {bday_date}")
        updated_events = updated_panchangam[bday_date].santhigiri_significant_dates
        updated_events.append(SISHYAPOOJITHA_BDAY)
        unique = {e.id : e for e in updated_events}
        updated_panchangam[bday_date].santhigiri_significant_dates = list(unique.values())
    return updated_panchangam


def cache_sishya_bday():
    cache: PanchangamCache = load_cache()
    updated_cache = update_sishya_bday(cache)
    write_cache(updated_cache)



#remove_sishya_bday()
cache_sishya_bday()


