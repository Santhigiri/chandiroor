from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from core.astronomy.nakshatra import get_duration_from_sunrise
from features.santhigiri_events.offline_cache.cache_crud import load_cache, write_cache
from features.santhigiri_events.offline_cache.cache_navapoojitham import calculate_navapoojitham, get_matching_dates
from features.santhigiri_events.offline_cache.cache_utils import get_yearly_cache, remove_events_from_cache, shift_date_for_offset
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import JANMAGRIHA_THEERTHA_YATHRA, NAVAPOOJITHAM, EventCondition, SanthigiriEvent
from schemas.panchangam_data import PanchangamData

PanchangamCache = Dict[date, PanchangamData]

def calculate_chothi_theerthayathra_for_year(
    yearly_data: PanchangamCache, year: int, transition_hour_cutoff: float = 3.0
)-> List[date]:
    occurances = []
    chothi_date_datas = [p_cache for _, p_cache in yearly_data.items() for t in p_cache.nakshatra_transitions if Nakshatra.CHOTHI == t.nakshatra ]

    chothi_transitions = [t for date_data in chothi_date_datas for t in date_data.nakshatra_transitions if t.nakshatra == Nakshatra.CHOTHI]
    unique = {
    (t.start_time, t.end_time): t
    for t in chothi_transitions
}
    sorted_transitions = sorted(unique.values(), key= lambda t: t.start_time)
    for transition in sorted_transitions:
        if transition.end_time is None:
            raise Exception(f"Transition end time is None for date near: {transition.start_time.date()}")

        if transition.end_time - yearly_data[transition.end_time.date()].sunrise > timedelta(hours=transition_hour_cutoff):
            occurances.append(transition.end_time.date())
            continue
        occurances.append(transition.end_time.date() - timedelta(days=1))

    return occurances





def remove_chothi_theerthayathra():
    panchangam_cache = load_cache()
    events_to_remove: List[SanthigiriEvent] = [JANMAGRIHA_THEERTHA_YATHRA]
    updated_panchangam = remove_events_from_cache(panchangam_cache, events_to_remove)
    write_cache(updated_panchangam)
    

def update_chothi_theerthayathra(
    panchangamCache: PanchangamCache, transition_hour_cutoff: float = 3.0
)-> PanchangamCache:
    """
    Updates Navapoojitham of a panchangam cache and returns the updated cache.
    Iterates through each year in the cache and updates :attr:`PanchangamData.santhigiri_significant_dates` with the :class:`SanthigiriEvent` `NAVAPOOJITHAM`
    """
    start_year = min(panchangamCache.keys())
    end_year = max(panchangamCache.keys())
    updated_panchangam = panchangamCache

    for year in range(start_year.year, end_year.year + 1):
        yearly_data = get_yearly_cache(panchangamCache, year)
        chothi_dates = calculate_chothi_theerthayathra_for_year(
            yearly_data, year, transition_hour_cutoff
        )

        print(f"NAVAPOOJITHAM DATE FOR {year}: {chothi_dates}")
        for dt in chothi_dates:
            target_date = shift_date_for_offset(
                updated_panchangam, dt, JANMAGRIHA_THEERTHA_YATHRA.event_condition.day_offset
            )
            if target_date is None:
                print(
                    f"WARNING: JANMAGRIHA_THEERTHA_YATHRA day_offset shifts {dt} outside "
                    "the loaded pickle range — skipping."
                )
                continue
            updated_events: List[SanthigiriEvent] = updated_panchangam[target_date].santhigiri_significant_dates
            updated_events.append(JANMAGRIHA_THEERTHA_YATHRA)
            unique = {e.id : e for e in updated_events}
            updated_panchangam[target_date].santhigiri_significant_dates = list(unique.values())
    return updated_panchangam


def _resolve_transition_hour_cutoff() -> float:
    """The admin-configured event transition-hour cutoff, resolved from the
    DB (falls back to 3.0 if unset/unavailable — see
    ``services.settings_service.SettingsService.get_event_cutoffs``)."""
    from sqlmodel import Session

    from db.database import engine
    from services.settings_service import SettingsService

    with Session(engine) as s:
        return SettingsService(s).get_event_cutoffs().transition_hour_cutoff


def cache_chothi_theerthayathra(transition_hour_cutoff: Optional[float] = None):
    cutoff = (
        transition_hour_cutoff
        if transition_hour_cutoff is not None
        else _resolve_transition_hour_cutoff()
    )
    cache: PanchangamCache = load_cache()
    updated_cache = update_chothi_theerthayathra(cache, cutoff)
    write_cache(updated_cache)



#remove_chothi_theerthayathra()
#cache_chothi_theerthayathra()


