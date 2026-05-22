
from contextlib import asynccontextmanager
from datetime import date
import pickle
from typing import Dict

from fastapi import FastAPI

from utils.check_nakshatra_transitions import check_nakshatra_transitions_miss
from utils.check_thithi_transitions import check_thithi_transitions_miss
from utils.santhigiri_events import PanchangamData

PANCHANGAM_CACHE: Dict[date, PanchangamData] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global PANCHANGAM_CACHE
    for year in range(2021, 2031):
        file_name = f"data/panchangam_{year}.pkl"
        with open(file_name, "rb") as f:
            PANCHANGAM_CACHE.update(pickle.load(f))

    print("Cache loaded", len(PANCHANGAM_CACHE))
    #check_nakshatra_transitions_miss(PANCHANGAM_CACHE)
    #check_thithi_transitions_miss(PANCHANGAM_CACHE)
    
    yield

    print("Shutdown")
