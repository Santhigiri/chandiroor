import pickle

from datetime import date, timedelta

from core.calendar.panchangam import get_panchangam_data


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

for year in range(2020, 2031):
    buildcache(year)


