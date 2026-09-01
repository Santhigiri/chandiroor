import pytest
from datetime import datetime
from panchangam_astronomy.pournami import is_poornima_live
from panchangam_astronomy.constants import DEFAULT_TIMEZONE


TEST_CASES = [
    (datetime(2022,1,17),DEFAULT_TIMEZONE, True),
    (datetime(2022,2,15),DEFAULT_TIMEZONE, True),
    (datetime(2022,3,17),DEFAULT_TIMEZONE, True),
    (datetime(2022,4,16),DEFAULT_TIMEZONE, True),
    (datetime(2022,5,15),DEFAULT_TIMEZONE, True),
    (datetime(2022,6,13),DEFAULT_TIMEZONE, True),
    (datetime(2022,7,13),DEFAULT_TIMEZONE, True),
    (datetime(2022,8,11),DEFAULT_TIMEZONE, True),
    (datetime(2022,9,9),DEFAULT_TIMEZONE, True) ,
    (datetime(2022,10,9),DEFAULT_TIMEZONE, True),
    (datetime(2022,11,7),DEFAULT_TIMEZONE, True),
    (datetime(2022,12,7),DEFAULT_TIMEZONE, True),
    (datetime(2026,5,15), DEFAULT_TIMEZONE, False),
    (datetime(2026,1,2), DEFAULT_TIMEZONE, True),
    (datetime(2026,2,1), DEFAULT_TIMEZONE, True),
    (datetime(2026,3,2), DEFAULT_TIMEZONE, True),
    (datetime(2026,4,1), DEFAULT_TIMEZONE, True),
    (datetime(2026,5,30), DEFAULT_TIMEZONE, True),
    (datetime(2026,6,29), DEFAULT_TIMEZONE, True),
    (datetime(2026,7,28), DEFAULT_TIMEZONE, True),
    (datetime(2026,8,27), DEFAULT_TIMEZONE, True),
    (datetime(2026,9,25), DEFAULT_TIMEZONE, True),
    (datetime(2026,10,25), DEFAULT_TIMEZONE, True),
    (datetime(2026,11,23), DEFAULT_TIMEZONE, True),
    (datetime(2026,12,23), DEFAULT_TIMEZONE, True),
]

@pytest.mark.parametrize(
    "input_date, timezone, expected",
    TEST_CASES,
    ids=lambda x: str(x)
)
def test_is_pournami(input_date, timezone, expected):
    assert is_poornima_live(input_date, timezone) == expected
