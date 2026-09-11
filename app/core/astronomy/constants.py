# Nakshatra sidereal-longitude boundaries (27 equal segments of 360/27°).
NAKSHATRA_BOUNDARIES = [i*(360/27) for i in range(1,28)]


class Coordinates:
    SG_LATITUDE: float = 8.645
    SG_LONGITUDE: float = 76.938

DEFAULT_TIMEZONE = 'Asia/Kolkata'

NAKSHATRA_TRANSITION_STEP_DAYS = 0.01 # 0.01 for 2021-2027, 2029-2030 0.05 for 2028
