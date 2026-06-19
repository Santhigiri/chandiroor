import pickle

from datetime import date, timedelta
from pathlib import Path
from typing import Dict

from core.calendar.panchangam import get_panchangam_data
from schemas.panchangam_data import PanchangamData



def load_cache():
    cache: Dict[date, PanchangamData] = {}
    cache_files = Path('data').glob("panchangam_*.pkl")
    files = sorted(cache_files)

    for file in files:
        with open(file, 'rb') as f:
            cache.update(pickle.load(f))


    print(f"File loaded with {len(cache.keys())} items")
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

