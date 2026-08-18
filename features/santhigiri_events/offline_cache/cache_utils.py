
from datetime import date, timedelta
from typing import Dict, List, Optional, Set

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


def shift_date_for_offset(cache: PanchangamCache, dt: date, day_offset: Optional[int]) -> Optional[date]:
    """*dt* shifted by *day_offset* days (None/0 = unchanged), or ``None`` if
    the shifted date falls outside the loaded pickle range in *cache*."""
    target = dt + timedelta(days=day_offset) if day_offset else dt
    return target if target in cache else None


def shift_and_record(
    cache: PanchangamCache,
    dt: date,
    day_offset: Optional[int],
    event: SanthigiriEvent,
    modified_dates: Set[date],
) -> None:
    """Append *event* to the day ``cache[dt + day_offset]`` (or ``cache[dt]``
    if no offset), warning and skipping if the shifted date falls outside
    the loaded pickle range."""
    target = shift_date_for_offset(cache, dt, day_offset)
    if target is None:
        shifted = dt + timedelta(days=day_offset) if day_offset else dt
        print(
            f"WARNING: {event.id} day_offset shifts {dt} to {shifted}, "
            "outside the loaded pickle range — skipping."
        )
        return
    cache[target].santhigiri_significant_dates.append(event)
    modified_dates.add(target)
