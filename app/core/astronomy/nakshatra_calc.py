from core.constants import NAKSHATRA_BOUNDARIES, NAKSHATRA_NAMES_ML
from utils.nakshatra import Nakshatra


def calc_nakshatra_id_from_lon(longitude: float) -> int:
    for i, boundary in enumerate(NAKSHATRA_BOUNDARIES):
        if longitude < boundary:
            nakshatra_id = i + 1
            break
    else:
        nakshatra_id = len(NAKSHATRA_BOUNDARIES)

    return nakshatra_id


def calc_nakshatra_from_lon(longitude: float) -> Nakshatra:
    for i, boundary in enumerate(NAKSHATRA_BOUNDARIES):
        if longitude < boundary:
            nakshatra =  Nakshatra.from_id(i)
            break
    else:
        nakshatra = Nakshatra.from_id(27)

    return nakshatra
