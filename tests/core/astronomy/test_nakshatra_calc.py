"""Tests for core/astronomy/nakshatra_calc.py::calc_nakshatra_from_lon."""
import pytest

from app.core.astronomy.constants import NAKSHATRA_BOUNDARIES
from app.core.astronomy.enums.nakshatra import Nakshatra
from app.core.astronomy.nakshatra_calc import calc_nakshatra_from_lon


def test_zero_longitude_is_first_nakshatra():
    """Regression: longitude in [0, 13.33) must resolve to Aswathy (id 1), not
    raise on Nakshatra.from_id(0) -- the ids are 1-indexed."""
    assert calc_nakshatra_from_lon(0.0) == Nakshatra.ASWATHI


@pytest.mark.parametrize(
    "longitude, expected",
    [
        (0.0, Nakshatra.ASWATHI),
        (NAKSHATRA_BOUNDARIES[0] - 0.01, Nakshatra.ASWATHI),
        (NAKSHATRA_BOUNDARIES[0] + 0.01, Nakshatra.BHARANI),
        (359.99, Nakshatra.REVATHI),
    ],
)
def test_boundaries_resolve_to_expected_nakshatra(longitude, expected):
    assert calc_nakshatra_from_lon(longitude) == expected


def test_every_boundary_segment_resolves_without_error():
    """Every one of the 27 segments must resolve to a valid Nakshatra."""
    lower = 0.0
    for i, boundary in enumerate(NAKSHATRA_BOUNDARIES):
        midpoint = (lower + boundary) / 2
        nakshatra = calc_nakshatra_from_lon(midpoint)
        assert nakshatra == Nakshatra.from_id(i + 1)
        lower = boundary
