from datetime import datetime
from .calculations import get_moon_sidereal_longitude, get_sun_sidereal_longitude
import math
from core.constants import THITHI_NAMES

def get_thithi(
    localdt: datetime,
    timezone: str
)-> str:
    # Thithi calculation
    moon_sidereal_longitude = get_moon_sidereal_longitude(localdt, timezone)
    sun_sidereal_longitude = get_sun_sidereal_longitude(localdt, timezone)
    elongation = (moon_sidereal_longitude - sun_sidereal_longitude) % 360
    thithi_number = math.floor(elongation / 12) + 1
    if thithi_number > 30:
        thithi_number = 30  # Amavasya
    thithi_name = THITHI_NAMES[thithi_number - 1]
    return thithi_name
