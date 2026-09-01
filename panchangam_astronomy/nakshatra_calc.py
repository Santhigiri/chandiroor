from panchangam_astronomy.constants import NAKSHATRA_BOUNDARIES
from panchangam_astronomy.enums.nakshatra import Nakshatra


def calc_nakshatra_from_lon(longitude: float) -> Nakshatra:
    for i, boundary in enumerate(NAKSHATRA_BOUNDARIES):
        if longitude < boundary:
            nakshatra =  Nakshatra.from_id(i)
            break
    else:
        nakshatra = Nakshatra.from_id(27)

    return nakshatra
