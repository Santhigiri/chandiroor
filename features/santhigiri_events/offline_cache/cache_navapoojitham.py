from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from core.astronomy.pournami import is_poornima
from features.santhigiri_events.offline_cache.cache_crud import load_cache, write_cache
from features.santhigiri_events.offline_cache.cache_utils import remove_events_from_cache, shift_date_for_offset
from utils.malayalam_masa import MalayalamMasa
from utils.nakshatra import Nakshatra
from utils.santhigiri_events import NAVAPOOJITHAM, EventCondition
from schemas.panchangam_data import PanchangamData

PanchangamCache = Dict[date, PanchangamData]

def get_yearly_cache(cache: PanchangamCache, year: int):
    return {k: v for k,v in cache.items() if k.year == year}

def calculate_navapoojitham(
    yearly_cache: PanchangamCache, year: int, nazhika_cutoff: float = 7.5
)-> date:
    filtered_events  = get_matching_dates(yearly_cache, NAVAPOOJITHAM.event_condition)
    if len(filtered_events) > 0:
        dt, p_data = filtered_events[-1]
        if p_data.nazhika_from_sunrise > nazhika_cutoff:
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


def remove_navapoojitham():
    panchangam_cache = load_cache()
    events_to_remove = [NAVAPOOJITHAM]
    updated_cache = remove_events_from_cache(panchangam_cache, events_to_remove)
    write_cache(updated_cache)
    

def update_navapoojitham(
    panchangamCache: PanchangamCache, nazhika_cutoff: float = 7.5
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
        navapoojitham_date = calculate_navapoojitham(yearly_data, year, nazhika_cutoff)

        target_date = shift_date_for_offset(
            updated_panchangam, navapoojitham_date, NAVAPOOJITHAM.event_condition.day_offset
        )
        if target_date is None:
            print(
                f"WARNING: NAVAPOOJITHAM day_offset shifts {navapoojitham_date} outside "
                "the loaded pickle range — skipping."
            )
            continue

        print(f"NAVAPOOJITHAM DATE FOR {year}: {target_date}")
        updated_events = updated_panchangam[target_date].santhigiri_significant_dates
        updated_events.append(NAVAPOOJITHAM)
        updated_panchangam[target_date].santhigiri_significant_dates = list(set(updated_events))
    return updated_panchangam


def _resolve_nazhika_cutoff() -> float:
    """The admin-configured event Nazhika cutoff, resolved from the DB
    (falls back to 7.5 if unset/unavailable — see
    ``services.settings_service.SettingsService.get_event_cutoffs``)."""
    from sqlmodel import Session

    from db.database import engine
    from services.settings_service import SettingsService

    with Session(engine) as s:
        return SettingsService(s).get_event_cutoffs().nazhika_cutoff


def cache_navapoojitham(nazhika_cutoff: Optional[float] = None):
    cutoff = nazhika_cutoff if nazhika_cutoff is not None else _resolve_nazhika_cutoff()
    cache: PanchangamCache = load_cache()
    updated_cache = update_navapoojitham(cache, cutoff)
    write_cache(updated_cache)



#remove_navapoojitham()
#cache_navapoojitham()


