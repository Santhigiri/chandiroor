import pickle

from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

from core.calendar.panchangam import get_panchangam_data
from schemas.panchangam_data import PanchangamData
from utils.location import DEFAULT_LOCATION, Location

if TYPE_CHECKING:
    from sqlmodel import Session



def load_cache():
    cache: Dict[date, PanchangamData] = {}
    cache_files = Path('data').glob("panchangam_*.pkl")
    files = sorted(cache_files)

    for file in files:
        with open(file, 'rb') as f:
            cache.update(pickle.load(f))


    print(f"File loaded with {len(cache.keys())} items")
    return cache


def load_cache_from_db(
    start: date = date(2021, 1, 1),
    end: date = date(2030, 12, 31),
    location: Location = DEFAULT_LOCATION,
    session: "Optional[Session]" = None,
    clear_events: bool = True,
) -> Dict[date, PanchangamData]:
    """Load the base PanchangamData for ``[start, end]`` from Postgres.

    The offline event pipeline's DB-backed counterpart to :func:`load_cache`. It
    returns the same ``date -> PanchangamData`` shape, but reads the already-populated
    sunrise/sunset, thithi/nakshatra transitions and Kollavarsham values straight from
    the database (via ``DATABASE_URL``) instead of the pickle files — so Pournami and
    the other event derivations run on the DB's values.

    ``session`` defaults to a fresh session on the module-level Postgres engine; pass
    an explicit session (e.g. the in-memory SQLite session used in ``tests/db/``) to
    read from another engine. When ``clear_events`` is set, each day's
    ``santhigiri_significant_dates`` is emptied so a rebuild starts from clean base
    data and recomputed occurrences replace — rather than stack on top of — the ones
    already seeded in the DB.
    """
    # Imported lazily so importing this module (and the pickle ``load_cache``) never
    # forces DATABASE_URL resolution or a database connection.
    from sqlmodel import Session

    from db.database import engine
    from db.repository import PanchangamRepository

    def _read(s: "Session") -> Dict[date, PanchangamData]:
        cache = PanchangamRepository(s).get_by_date_range(start, end, location)
        if clear_events:
            for panchangam_data in cache.values():
                panchangam_data.santhigiri_significant_dates = []
        return cache

    if session is not None:
        cache = _read(session)
    else:
        with Session(engine) as owned_session:
            cache = _read(owned_session)

    print(f"DB loaded with {len(cache)} items")
    return cache



def write_cache(cache: Dict[date, PanchangamData], path: Path = Path('data')):
    current = min(cache.keys())
    end = max(cache.keys())

    start_year = current.year
    end_year = end.year

    for year in range(start_year, end_year + 1):
        print(f"writing for year: {year}")
        yearly_data = {k: v for k,v in cache.items() if k.year == year}
        
        file_name = f"{str(path)}/panchangam_{year}.pkl"
        with open(file_name, 'wb') as f:
            pickle.dump(yearly_data, f)


def buildcache(year: int):
    cache = {}

    current = date(year, 1, 1)
    end = date(year, 12, 31)


    while current <= end:
        print("Computing", current)
        cache[current] = get_panchangam_data(current)

        current += timedelta(days=1)

    file_name = f"data/panchangam_{year}.pkl"

    with open(file_name, "wb") as f:
        pickle.dump(cache, f)

    print("Saved", file_name)

#for year in range(2028, 2029):
#    buildcache(year)

#load_cache()

