import swisseph as swe

def get_ayanamsa(
    year: int,
    month: int = 1,
    day: int = 1,
    hour: float = 0.0
) -> float:
    """
    Calculate Lahiri Ayanamsa using Swiss Ephemeris.

    Returns:
        float: Lahiri ayanamsa in degrees
    """

    # Set Lahiri ayanamsa mode
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    # Convert date to Julian Day
    jd = swe.julday(year, month, day, hour)

    # Get ayanamsa
    ayanamsa = swe.get_ayanamsa(jd)

    return ayanamsa

