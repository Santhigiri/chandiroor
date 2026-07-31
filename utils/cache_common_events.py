from datetime import date
from typing import List, Set
from utils.cache_crud import load_cache, write_cache
from utils.cache_navapoojitham import get_matching_dates
from utils.cache_utils import PanchangamCache, remove_events_from_cache, shift_and_record
from utils.santhigiri_events import DIVYA_POOJA_SAMARPANA_VARSHIKAM, NAVOLI_JYOTHIR_DINAM, POOJITHA_PEEDA_SAMARPANAM, POORNA_KUMBAMELA, POURNAMI, PRATHISTA_POORTHIKARANA_VARSHIKAM, PRATHISTA_VARSHIKAM, SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM, SAMSKARIKA_DINAM, SISHYAPOOJITHA_BDAY, SanthigiriEvent


_COMMON_EVENTS: List[SanthigiriEvent] = [
    SAMSKARIKA_DINAM,
    NAVOLI_JYOTHIR_DINAM,
    POORNA_KUMBAMELA,
    DIVYA_POOJA_SAMARPANA_VARSHIKAM,
    PRATHISTA_POORTHIKARANA_VARSHIKAM,
    SAHAKARANA_MANDIRAM_SAMARPANA_VARSHIKAM,
    POOJITHA_PEEDA_SAMARPANAM,
    PRATHISTA_VARSHIKAM,
    SISHYAPOOJITHA_BDAY,
    POURNAMI
]

def remove_common_events():
    cache = load_cache()
    updated_cache = remove_events_from_cache(cache, _COMMON_EVENTS)
    write_cache(updated_cache) 

def update_common_events(cache: PanchangamCache) -> PanchangamCache:
    # Track which dates were modified
    modified_dates: Set[date] = set()

    for event in _COMMON_EVENTS:
        matching_dates = get_matching_dates(cache, event.event_condition)
        for dt, _ in matching_dates:
            shift_and_record(cache, dt, event.event_condition.day_offset, event, modified_dates)

    # Deduplicate only modified dates
    for dt in modified_dates:
        unique_events = {e.id: e for e in cache[dt].santhigiri_significant_dates}
        cache[dt].santhigiri_significant_dates[:] = list(unique_events.values())

    return cache

def cache_common_events():
    cache = load_cache()
    update_common_events(cache)
    write_cache(cache)

#remove_common_events()
#cache_common_events()
